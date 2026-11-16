"""Schemas Pydantic — tickets."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    BAJA = "Baja"
    MEDIA = "Media"
    ALTA = "Alta"
    CRITICA = "Crítica"


class Status(str, Enum):
    ABIERTO = "Abierto"
    EN_REVISION = "En revisión"
    EN_PROGRESO = "En progreso"
    PENDIENTE = "Pendiente"
    RESUELTO = "Resuelto"
    CERRADO = "Cerrado"


class HistoryEventType(str, Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    COMMENT_ADDED = "COMMENT_ADDED"
    FILE_ATTACHED = "FILE_ATTACHED"
    ASSIGNED = "ASSIGNED"


class AttachmentCreate(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1)
    kind: str = Field(min_length=1, max_length=50)
    analysis_summary: Optional[str] = None


class AttachmentResponse(BaseModel):
    id: int
    ticket_id: str
    filename: str
    path: str
    kind: str
    analysis_summary: Optional[str] = None
    added_at: str
    added_by: str

    model_config = {"from_attributes": True}


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class CommentResponse(BaseModel):
    id: int
    ticket_id: str
    author_id: str
    text: str
    created_at: str

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    id: int
    ticket_id: str
    event_type: HistoryEventType
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    actor_id: str
    timestamp: str

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10)
    category: str = Field(min_length=1, max_length=100)
    priority: Priority
    attachments: list[AttachmentCreate] = Field(default_factory=list)

    @field_validator("category")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("category no puede estar vacío")
        return value


class TicketStatusUpdate(BaseModel):
    new_status: Status


class TicketPriorityUpdate(BaseModel):
    priority: Priority


class TicketAssign(BaseModel):
    assignee_id: str = Field(min_length=1)


class TicketResponse(BaseModel):
    id: str
    created_at: str
    requester_id: str
    title: str
    description: str
    category: str
    priority: Priority
    status: Status
    assignee_id: Optional[str] = None

    model_config = {"from_attributes": True}


class TicketFilters(BaseModel):
    status: Optional[Status] = None
    category: Optional[str] = None
    priority: Optional[Priority] = None
    requester_id: Optional[str] = None
    # Solo tickets sin resolver: todo menos Resuelto y Cerrado.
    unresolved: bool = False
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class IncidentSummary(BaseModel):
    by_status: dict[str, int]
    by_category: dict[str, int]
    by_priority: dict[str, int]
    total: int
