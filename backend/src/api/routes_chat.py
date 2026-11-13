"""Endpoint de chat del agente."""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.agent.orchestrator import run_agent
from src.api.deps import get_current_user
from src.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


def get_run_agent():
    """Dependencia inyectable: los tests la reemplazan por un runner fake."""
    return run_agent


def _friendly_error(exc: Exception) -> HTTPException:
    """Traduce errores del LLM a una respuesta util en vez de un 500 mudo."""
    name = type(exc).__name__
    text = str(exc)

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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    runner=Depends(get_run_agent),
) -> ChatResponse:
    conversation_id = payload.conversation_id or uuid4().hex
    try:
        reply = await runner(current_user.id, conversation_id, payload.message)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Fallo el agente")
        raise _friendly_error(exc)
    return ChatResponse(reply=reply, conversation_id=conversation_id)
