"""Orquestador del agente: LLM + herramientas + memoria conversacional."""
from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from src.agent.prompts import SYSTEM_PROMPT
from src.agent.tools import TOOLS, AgentContext
from src.core.config import settings

LLM_MODEL = "gemini-2.5-flash"

# Memoria en proceso: sobrevive entre turnos, se pierde al reiniciar el
# contenedor. Para persistencia real, cambiar por AsyncPostgresSaver.
_checkpointer = InMemorySaver()
_agent = None


def get_agent():
    """Construye el agente una sola vez (lazy).

    Es lazy a proposito: si se construyera al importar, los tests (que importan
    `app`) fallarian cuando no hay GOOGLE_API_KEY.
    """
    global _agent
    if _agent is None:
        if not settings.google_api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY no configurada: el agente no puede inicializarse"
            )
        llm = ChatGoogleGenerativeAI(
            model=LLM_MODEL,
            temperature=0.2,
            max_retries=2,
        )
        _agent = create_agent(
            llm,
            TOOLS,
            system_prompt=SYSTEM_PROMPT,
            context_schema=AgentContext,
            checkpointer=_checkpointer,
        )
    return _agent


def thread_id(user_id: str, conversation_id: str) -> str:
    """Namespace por usuario: evita que dos usuarios compartan contexto."""
    return f"{user_id}:{conversation_id}"


async def run_agent(user_id: str, conversation_id: str, content) -> str:
    """Invoca al agente con el usuario autenticado como contexto.

    `content` es str o una lista de bloques multimodales.
    """
    result = await get_agent().ainvoke(
        {"messages": [HumanMessage(content=content)]},
        config={"configurable": {"thread_id": thread_id(user_id, conversation_id)}},
        context=AgentContext(user_id=user_id),
    )
    return result["messages"][-1].text


def reset_agent() -> None:
    """Descarta el agente y su memoria. Solo para tests."""
    global _agent
    _agent = None
