"""Lógica de negocio de tickets (sin IA)."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models import Attachment, Comment, HistoryEvent, Ticket, User
from src.schemas.ticket import (
    AttachmentCreate,
    CommentCreate,
    IncidentSummary,
    TicketCreate,
    TicketFilters,
    TicketPriorityUpdate,
    TicketStatusUpdate,
)
from src.services.exceptions import (
    Forbidden,
    InvalidTransition,
    NotFound,
    ValidationError,
)


TRANSITIONS: dict[str, set[str]] = {
    "Abierto": {"En revisión"},
    "En revisión": {"En progreso", "Pendiente"},
    "En progreso": {"Resuelto", "Pendiente"},
    "Pendiente": {"En progreso"},
    "Resuelto": {"Cerrado"},
    "Cerrado": set(),
}

CLOSABLE_STATUSES = {"Cerrado"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next_ticket_id(session: Session) -> str:
    # ponytail: max+1; concurrencia no es crítico en esta fase (demo).
    last = session.execute(select(Ticket.id).order_by(Ticket.id.desc()).limit(1)).scalar_one_or_none()
    n = 1000
    if last and last.startswith("TCK-"):
        try:
            n = int(last.split("-", 1)[1])
        except ValueError:
            pass
    return f"TCK-{n + 1}"


def _user(session: Session, user_id: str) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise NotFound(f"Usuario {user_id} no encontrado")
    return u


def _ticket(session: Session, ticket_id: str) -> Ticket:
    t = session.get(Ticket, ticket_id)
    if t is None:
        raise NotFound(f"Ticket {ticket_id} no encontrado")
    return t


def _can_read(actor: User, ticket: Ticket) -> bool:
    return actor.role in ("soporte", "admin") or ticket.requester_id == actor.id


def create_ticket(session: Session, actor: User, data: TicketCreate) -> Ticket:
    # Valida categoría contra el catálogo.
    from src.models import Category

    cat = session.get(Category, data.category)
    if cat is None:
        raise ValidationError(f"Categoría '{data.category}' no existe")

    ticket = Ticket(
        id=_next_ticket_id(session),
        created_at=_now(),
        requester_id=actor.id,
        title=data.title,
        description=data.description,
        category=data.category,
        priority=data.priority.value,
        status="Abierto",
        assignee_id=None,
    )
    session.add(ticket)
    session.flush()

    session.add(HistoryEvent(
        ticket_id=ticket.id, event_type="CREATED", old_value=None,
        new_value="Abierto", actor_id=actor.id, timestamp=_now(),
    ))

    for a in data.attachments:
        session.add(Attachment(
            ticket_id=ticket.id, filename=a.filename, path=a.path,
            kind=a.kind, analysis_summary=a.analysis_summary,
            added_at=_now(), added_by=actor.id,
        ))
        session.add(HistoryEvent(
            ticket_id=ticket.id, event_type="FILE_ATTACHED", old_value=None,
            new_value=a.filename, actor_id=actor.id, timestamp=_now(),
        ))

    session.commit()
    session.refresh(ticket)
    return ticket


def get_ticket(session: Session, actor: User, ticket_id: str) -> Ticket:
    t = _ticket(session, ticket_id)
    if not _can_read(actor, t):
        raise Forbidden("No tenés permiso para ver este ticket")
    return t


def search_tickets(session: Session, actor: User, filters: TicketFilters) -> list[Ticket]:
    stmt = select(Ticket)
    if actor.role == "usuario":
        stmt = stmt.where(Ticket.requester_id == actor.id)
    if filters.status is not None:
        stmt = stmt.where(Ticket.status == filters.status.value)
    if filters.category:
        stmt = stmt.where(Ticket.category == filters.category)
    if filters.priority is not None:
        stmt = stmt.where(Ticket.priority == filters.priority.value)
    if filters.requester_id:
        stmt = stmt.where(Ticket.requester_id == filters.requester_id)
    stmt = stmt.offset(filters.offset).limit(filters.limit)
    return list(session.execute(stmt).scalars().all())


def update_status(session: Session, actor: User, ticket_id: str, data: TicketStatusUpdate) -> Ticket:
    if actor.role not in ("soporte", "admin"):
        raise Forbidden("Solo soporte/admin puede cambiar el estado")
    t = _ticket(session, ticket_id)
    new = data.new_status.value
    if new == t.status:
        return t
    if new not in TRANSITIONS.get(t.status, set()):
        raise InvalidTransition(f"Transición inválida: {t.status} -> {new}")
    if new == "Cerrado" and actor.role != "admin":
        raise Forbidden("Solo admin puede cerrar un ticket")
    old = t.status
    t.status = new
    session.add(HistoryEvent(
        ticket_id=t.id, event_type="STATUS_CHANGED", old_value=old,
        new_value=new, actor_id=actor.id, timestamp=_now(),
    ))
    session.commit()
    session.refresh(t)
    return t


def update_priority(session: Session, actor: User, ticket_id: str, data: TicketPriorityUpdate) -> Ticket:
    if actor.role != "admin":
        raise Forbidden("Solo admin puede cambiar la prioridad")
    t = _ticket(session, ticket_id)
    old = t.priority
    new = data.priority.value
    if old != new:
        t.priority = new
        session.add(HistoryEvent(
            ticket_id=t.id, event_type="PRIORITY_CHANGED", old_value=old,
            new_value=new, actor_id=actor.id, timestamp=_now(),
        ))
        session.commit()
    session.refresh(t)
    return t


def assign_ticket(session: Session, actor: User, ticket_id: str, assignee_id: str) -> Ticket:
    if actor.role not in ("soporte", "admin"):
        raise Forbidden("Solo soporte/admin puede asignar")
    t = _ticket(session, ticket_id)
    assignee = _user(session, assignee_id)
    old = t.assignee_id
    t.assignee_id = assignee.id
    session.add(HistoryEvent(
        ticket_id=t.id, event_type="ASSIGNED", old_value=old,
        new_value=assignee.id, actor_id=actor.id, timestamp=_now(),
    ))
    session.commit()
    session.refresh(t)
    return t


def add_comment(session: Session, actor: User, ticket_id: str, data: CommentCreate) -> Comment:
    t = _ticket(session, ticket_id)
    if not (_can_read(actor, t)):
        raise Forbidden("No tenés permiso para comentar este ticket")
    c = Comment(ticket_id=t.id, author_id=actor.id, text=data.text, created_at=_now())
    session.add(c)
    session.flush()
    session.add(HistoryEvent(
        ticket_id=t.id, event_type="COMMENT_ADDED", old_value=None,
        new_value=c.text, actor_id=actor.id, timestamp=_now(),
    ))
    session.commit()
    session.refresh(c)
    return c


def get_history(session: Session, actor: User, ticket_id: str) -> list[HistoryEvent]:
    t = _ticket(session, ticket_id)
    if not _can_read(actor, t):
        raise Forbidden("No tenés permiso para ver este historial")
    return list(session.execute(
        select(HistoryEvent).where(HistoryEvent.ticket_id == ticket_id).order_by(HistoryEvent.id)
    ).scalars().all())


def generate_summary(session: Session, actor: User) -> IncidentSummary:
    if actor.role not in ("soporte", "admin"):
        raise Forbidden("Solo soporte/admin puede generar resúmenes")
    by_status = dict(session.execute(
        select(Ticket.status, func.count()).group_by(Ticket.status)
    ).all())
    by_category = dict(session.execute(
        select(Ticket.category, func.count()).group_by(Ticket.category)
    ).all())
    by_priority = dict(session.execute(
        select(Ticket.priority, func.count()).group_by(Ticket.priority)
    ).all())
    total = session.execute(select(func.count()).select_from(Ticket)).scalar_one()
    return IncidentSummary(
        by_status=by_status, by_category=by_category,
        by_priority=by_priority, total=total,
    )
