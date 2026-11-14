"""Endpoints de chat del agente.

Flujo con confirmación:
1. `POST /chat` → si el modelo quiere crear o modificar algo, la respuesta trae
   `pending_actions` (no vacío) y la acción NO se ejecutó todavía.
2. `POST /chat/{conversation_id}/decision` con `approve` o `reject` → se ejecuta
   (o se descarta) y el agente responde.
Mientras haya acciones pendientes, `POST /chat` en esa conversación devuelve 409.

Adjuntos (F02): primero `POST /chat/upload` (multipart, campo `files`) devuelve
un id por archivo; después `POST /chat` con `upload_ids` los manda al agente
junto con el mensaje.
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Path, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.agent.orchestrator import (
    AgentReply,
    NoPendingAction,
    PendingActionExists,
    resume_agent,
    run_agent,
)
from src.agent.multimodal import build_content
from src.api.deps import get_current_user, get_db
from src.core.config import settings
from src.models import User
from src.services import upload_service
from src.services.exceptions import NotFound, ValidationError

MAX_FILES_PER_MESSAGE = 5

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = Field(default=None, max_length=100)
    upload_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_FILES_PER_MESSAGE,
        description="Ids devueltos por POST /chat/upload para mandar con este mensaje.",
    )


class UploadOut(BaseModel):
    id: int
    filename: str
    kind: str = Field(description="imagen, txt o log")
    size_bytes: int


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


@router.post("/chat/upload", response_model=list[UploadOut], status_code=201)
async def upload_files(
    files: list[UploadFile] = File(description=f"Hasta {MAX_FILES_PER_MESSAGE} archivos"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[UploadOut]:
    if len(files) > MAX_FILES_PER_MESSAGE:
        raise HTTPException(
            status_code=422,
            detail=f"Máximo {MAX_FILES_PER_MESSAGE} archivos por vez.",
        )
    max_bytes = settings.max_upload_mb * 1024 * 1024
    out: list[UploadOut] = []
    for f in files:
        # Lee un byte de más para detectar archivos grandes sin cargarlos enteros.
        data = await f.read(max_bytes + 1)
        try:
            u = upload_service.save_upload(db, current_user, f.filename, data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        out.append(UploadOut(id=u.id, filename=u.filename, kind=u.kind, size_bytes=u.size_bytes))
    return out


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    runner=Depends(get_run_agent),
) -> ChatResponse:
    conversation_id = payload.conversation_id or uuid4().hex
    try:
        uploads = upload_service.get_owned_uploads(db, current_user, payload.upload_ids)
        content = build_content(payload.message, uploads)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except OSError:
        logger.exception("No se pudo leer un adjunto")
        raise HTTPException(
            status_code=410, detail="Un adjunto ya no está disponible; volvé a subirlo."
        )
    result = await _call(runner, current_user.id, conversation_id, content)
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
