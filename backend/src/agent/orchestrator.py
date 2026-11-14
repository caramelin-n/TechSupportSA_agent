"""Orquestador del agente: LLM + herramientas + memoria + confirmaciones.

Las herramientas que cambian datos (crear, cambiar estado o prioridad,
asignar) no se ejecutan cuando el modelo las pide: el grafo se pausa y la
acción queda pendiente hasta que el usuario la aprueba o la rechaza por
`POST /chat/{conversation_id}/decision`. La confirmación la impone el código
(`HumanInTheLoopMiddleware`), no el prompt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import TOOLS, AgentContext
from src.core.config import settings

# Herramientas que requieren confirmación explícita del usuario.
# Solo approve/reject: con "edit" el cliente podría cambiar los argumentos.
CONFIRMABLE_TOOLS: tuple[str, ...] = (
    "crear_ticket",
    "actualizar_estado",
    "actualizar_prioridad",
    "asignar_ticket",
)

Decision = Literal["approve", "reject"]


# --------------------------------------------------------------------------
# Tipos de respuesta
# --------------------------------------------------------------------------


@dataclass
class PendingAction:
    """Acción que el modelo quiere ejecutar y espera confirmación."""

    tool: str
    args: dict[str, Any]
    description: str


@dataclass
class AgentReply:
    reply: str
    pending_actions: list[PendingAction] = field(default_factory=list)


class PendingActionExists(Exception):
    """Llegó un mensaje nuevo pero hay una acción esperando confirmación."""


class NoPendingAction(Exception):
    """Llegó una decisión pero no hay nada que confirmar."""


# --------------------------------------------------------------------------
# Construcción del agente
# --------------------------------------------------------------------------

# Hasta que el lifespan de FastAPI instale el de Postgres, se usa memoria
# (así los scripts y tests que importan este módulo no necesitan base).
_checkpointer: BaseCheckpointSaver = InMemorySaver()
_agent = None


def build_agent(llm: BaseChatModel, checkpointer: BaseCheckpointSaver):
    """Arma el grafo. Separado de `get_agent` para poder testearlo con un LLM falso."""
    return create_agent(
        llm,
        TOOLS,
        system_prompt=SYSTEM_PROMPT,
        context_schema=AgentContext,
        checkpointer=checkpointer,
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    name: {"allowed_decisions": ["approve", "reject"]}
                    for name in CONFIRMABLE_TOOLS
                },
                description_prefix="Acción que requiere confirmación",
            )
        ],
    )


def set_checkpointer(checkpointer: BaseCheckpointSaver) -> None:
    """Lo llama el lifespan de la app al arrancar. Invalida el agente cacheado."""
    global _checkpointer, _agent
    _checkpointer = checkpointer
    _agent = None


def get_agent():
    """Construye el agente una sola vez (lazy).

    Es lazy a propósito: si se construyera al importar, los tests (que importan
    `app`) fallarían cuando no hay GOOGLE_API_KEY.
    """
    global _agent
    if _agent is None:
        if not settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY no configurada: el agente no puede inicializarse"
            )
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(
            model=settings.llm_model,
            temperature=0.2,
            max_retries=2,
        )
        _agent = build_agent(llm, _checkpointer)
    return _agent


def thread_id(user_id: str, conversation_id: str) -> str:
    """Namespace por usuario: evita que dos usuarios compartan contexto.

    También impide que un usuario confirme acciones de la conversación de otro.
    """
    return f"{user_id}:{conversation_id}"


# --------------------------------------------------------------------------
# Formateo de la respuesta
# --------------------------------------------------------------------------

_DESCRIPTIONS = {
    "crear_ticket": lambda a: (
        f"Crear el ticket «{a.get('title', '')}» "
        f"(categoría {a.get('category', '?')}, prioridad {a.get('priority', '?')})"
    ),
    "actualizar_estado": lambda a: (
        f"Cambiar el estado de {a.get('ticket_id', '?')} a «{a.get('nuevo_estado', '?')}»"
    ),
    "actualizar_prioridad": lambda a: (
        f"Cambiar la prioridad de {a.get('ticket_id', '?')} a «{a.get('prioridad', '?')}»"
    ),
    "asignar_ticket": lambda a: (
        f"Asignar {a.get('ticket_id', '?')} a {a.get('assignee_id', '?')}"
    ),
}


def _describe(tool: str, args: dict[str, Any]) -> str:
    fmt = _DESCRIPTIONS.get(tool)
    return fmt(args) if fmt else f"Ejecutar {tool}"


def _pending_from_interrupts(interrupts) -> list[PendingAction]:
    actions: list[PendingAction] = []
    for intr in interrupts:
        for req in (intr.value or {}).get("action_requests", []):
            args = dict(req.get("args", {}))
            actions.append(PendingAction(req["name"], args, _describe(req["name"], args)))
    return actions


def _last_ai_text(messages) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg.text.strip()
    return ""


def _to_reply(result) -> AgentReply:
    """Convierte la salida `version="v2"` del grafo en la respuesta de la API."""
    pending = _pending_from_interrupts(result.interrupts)
    text = _last_ai_text(result.value["messages"])
    if pending and not text:
        lines = "\n".join(f"- {p.description}" for p in pending)
        text = f"Antes de seguir necesito que confirmes:\n{lines}"
    return AgentReply(reply=text, pending_actions=pending)


async def _pending_interrupts(agent, config) -> tuple:
    state = await agent.aget_state(config)
    return tuple(state.interrupts)


# --------------------------------------------------------------------------
# API pública (la usa routes_chat)
# --------------------------------------------------------------------------


async def run_agent(user_id: str, conversation_id: str, content) -> AgentReply:
    """Envía un mensaje del usuario al agente.

    `content` es str o una lista de bloques multimodales.
    Si la conversación tiene una acción esperando confirmación, no se puede
    seguir hablando hasta resolverla (si no, el modelo quedaría con una llamada
    a herramienta sin respuesta).
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id(user_id, conversation_id)}}
    if await _pending_interrupts(agent, config):
        raise PendingActionExists(
            "Hay una acción esperando confirmación en esta conversación. "
            "Aprobala o rechazala antes de enviar otro mensaje."
        )
    result = await agent.ainvoke(
        {"messages": [HumanMessage(content=content)]},
        config=config,
        context=AgentContext(user_id=user_id),
        version="v2",
    )
    return _to_reply(result)


async def resume_agent(
    user_id: str,
    conversation_id: str,
    decision: Decision,
    message: str | None = None,
) -> AgentReply:
    """Retoma la conversación aplicando la decisión a TODAS las acciones pendientes.

    En modo `batched`, si el modelo pidió dos acciones confirmables en el mismo
    turno, llegan juntas y se aprueban o rechazan juntas.
    """
    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id(user_id, conversation_id)}}
    interrupts = await _pending_interrupts(agent, config)
    if not interrupts:
        raise NoPendingAction("No hay ninguna acción pendiente de confirmación.")

    n_actions = len(_pending_from_interrupts(interrupts))
    one: dict[str, Any] = {"type": decision}
    if decision == "reject" and message:
        one["message"] = message
    result = await agent.ainvoke(
        Command(resume={"decisions": [dict(one) for _ in range(n_actions)]}),
        config=config,
        context=AgentContext(user_id=user_id),
        version="v2",
    )
    return _to_reply(result)


def reset_agent() -> None:
    """Descarta el agente y su memoria. Solo para tests."""
    set_checkpointer(InMemorySaver())
