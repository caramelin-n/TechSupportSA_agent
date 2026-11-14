"""Endpoints de chat del agente.

Flujo con confirmación:
1. `POST /chat` → si el modelo quiere crear o modificar algo, la respuesta trae
   `pending_actions` (no vacío) y la acción NO se ejecutó todavía.
2. `POST /chat/{conversation_id}/decision` con `approve` o `reject` → se ejecuta
   (o se descarta) y el agente responde.
Mientras haya acciones pendientes, `POST /chat` en esa conversación devuelve 409.
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field

from src.agent.orchestrator import (
    AgentReply,
    NoPendingAction,
    PendingActionExists,
    resume_agent,
    run_agent,
)
from src.api.deps import get_current_user
from src.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=100)


class PendingActionOut(BaseModel):
    tool: str = Field(description="Nombre de la herramienta, p. ej. crear_ticket")
    args: dict[str, Any]
    description: str = Field(description="Texto en español para mostrar al usuario")


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    pending_actions: list[PendingActionOut] = Field(
        default_factory=list,
        description="Acciones esperando confirmación. Vacío si no hay ninguna.",
    )


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    message: str | None = Field(
        default=None,
        max_length=1000,
        description="Motivo del rechazo; el agente lo lee. Se ignora al aprobar.",
    )


def get_run_agent():
    """Dependencia inyectable: los tests la reemplazan por un runner fake."""
    return run_agent


def get_resume_agent():
    """Dependencia inyectable para la decisión de confirmación."""
    return resume_agent


def _friendly_error(exc: Exception) -> HTTPException:
    """Traduce errores del LLM a una respuesta útil en vez de un 500 mudo."""
    name = type(exc).__name__
    text = str(exc)

    if isinstance(exc, PendingActionExists):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=text)
    if isinstance(exc, NoPendingAction):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=text)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Cuota del modelo agotada. Cambiá LLM_MODEL en .env "
                "(por ejemplo gemini-2.5-flash-lite) o esperá a que se renueve. "
                "Ver https://aistudio.google.com/docs/rate-limits"
            ),
        )
    if "API key" in text or "API_KEY" in text or "PERMISSION_DENIED" in text:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Problema con GOOGLE_API_KEY: revisá la clave en .env.",
        )
    if "RuntimeError" in name:
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=text)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Error del agente ({name}). Revisá los logs del backend.",
    )


def _response(result: AgentReply | str, conversation_id: str) -> ChatResponse:
    # Un runner puede devolver solo texto (por ejemplo, los fakes de los tests).
    if isinstance(result, str):
        return ChatResponse(reply=result, conversation_id=conversation_id)
    return ChatResponse(
        reply=result.reply,
        conversation_id=conversation_id,
        pending_actions=[
            PendingActionOut(tool=p.tool, args=p.args, description=p.description)
            for p in result.pending_actions
        ],
    )


async def _call(fn, *args) -> AgentReply | str:
    try:
        return await fn(*args)
    except HTTPException:
        raise
    except (PendingActionExists, NoPendingAction) as exc:
        raise _friendly_error(exc)
    except Exception as exc:
        logger.exception("Falló el agente")
        raise _friendly_error(exc)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    runner=Depends(get_run_agent),
) -> ChatResponse:
    conversation_id = payload.conversation_id or uuid4().hex
    result = await _call(runner, current_user.id, conversation_id, payload.message)
    return _response(result, conversation_id)


@router.post("/chat/{conversation_id}/decision", response_model=ChatResponse)
async def decide(
    payload: DecisionRequest,
    conversation_id: str = Path(max_length=100),
    current_user: User = Depends(get_current_user),
    resumer=Depends(get_resume_agent),
) -> ChatResponse:
    result = await _call(
        resumer, current_user.id, conversation_id, payload.decision, payload.message
    )
    return _response(result, conversation_id)
