"""Endpoint de chat del agente."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.agent.orchestrator import run_agent
from src.api.deps import get_current_user
from src.models import User

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


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    runner=Depends(get_run_agent),
) -> ChatResponse:
    conversation_id = payload.conversation_id or uuid4().hex
    reply = await runner(current_user.id, conversation_id, payload.message)
    return ChatResponse(reply=reply, conversation_id=conversation_id)
