"""Endpoints de tickets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db, require_roles
from src.schemas.ticket import (
    CommentCreate,
    CommentResponse,
    IncidentSummary,
    Priority,
    Status,
    TicketAssign,
    TicketCreate,
    TicketFilters,
    TicketPriorityUpdate,
    TicketResponse,
    TicketStatusUpdate,
)
from src.services import ticket_service as svc
from src.services.exceptions import DomainError

router = APIRouter(prefix="/tickets", tags=["tickets"])


def _handle(exc: DomainError):
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.post("", response_model=TicketResponse, status_code=201)
def create(payload: TicketCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return svc.create_ticket(db, current_user, payload)
    except DomainError as exc:
        _handle(exc)


@router.get("", response_model=list[TicketResponse])
def search(
    status: Status | None = Query(default=None),
    category: str | None = Query(default=None),
    priority: Priority | None = Query(default=None),
    requester_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = TicketFilters(
        status=status,
        category=category,
        priority=priority,
        requester_id=requester_id,
        limit=limit,
        offset=offset,
    )
    try:
        return svc.search_tickets(db, current_user, filters)
    except DomainError as exc:
        _handle(exc)


@router.get("/summary", response_model=IncidentSummary)
def summary(current_user=Depends(require_roles("soporte", "admin")), db: Session = Depends(get_db)):
    try:
        return svc.generate_summary(db, current_user)
    except DomainError as exc:
        _handle(exc)


@router.get("/{ticket_id}", response_model=TicketResponse)
def get_one(ticket_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return svc.get_ticket(db, current_user, ticket_id)
    except DomainError as exc:
        _handle(exc)


@router.get("/{ticket_id}/history", response_model=list)
def history(ticket_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    from src.schemas.ticket import HistoryResponse

    try:
        items = svc.get_history(db, current_user, ticket_id)
    except DomainError as exc:
        _handle(exc)
    return [HistoryResponse.model_validate(h) for h in items]


@router.patch("/{ticket_id}/status", response_model=TicketResponse)
def update_status(ticket_id: str, payload: TicketStatusUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return svc.update_status(db, current_user, ticket_id, payload)
    except DomainError as exc:
        _handle(exc)


@router.patch("/{ticket_id}/priority", response_model=TicketResponse)
def update_priority(ticket_id: str, payload: TicketPriorityUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return svc.update_priority(db, current_user, ticket_id, payload)
    except DomainError as exc:
        _handle(exc)


@router.patch("/{ticket_id}/assignee", response_model=TicketResponse)
def assign(ticket_id: str, payload: TicketAssign, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return svc.assign_ticket(db, current_user, ticket_id, payload.assignee_id)
    except DomainError as exc:
        _handle(exc)


@router.post("/{ticket_id}/comments", response_model=dict, status_code=201)
def add_comment(ticket_id: str, payload: CommentCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        c = svc.add_comment(db, current_user, ticket_id, payload)
    except DomainError as exc:
        _handle(exc)
    return {"id": c.id, "ticket_id": c.ticket_id, "author_id": c.author_id, "text": c.text, "created_at": c.created_at}
