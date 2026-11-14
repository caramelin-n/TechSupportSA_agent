"""Herramientas del agente: envuelven `ticket_service` sin modificarlo.

El actor (usuario autenticado) NO lo elige el LLM: se inyecta desde el contexto
del runtime, que a su vez viene del JWT en `POST /chat`. Así los permisos de
`ticket_service` siguen vigentes.

Cada impl es una función pura y testeable; el wrapper `@tool` solo resuelve el
contexto.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Callable

from langchain.tools import ToolRuntime, tool
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.models import Ticket, User
from src.schemas.ticket import (
    CommentCreate,
    Priority,
    Status,
    TicketCreate,
    TicketFilters,
    TicketPriorityUpdate,
    TicketStatusUpdate,
)
from src.services import ticket_service, user_service
from src.services.exceptions import DomainError, Forbidden, NotFound


@dataclass
class AgentContext:
    """Contexto inyectado por el runtime; nunca lo controla el LLM."""

    user_id: str


_PRIORITIES = ", ".join(p.value for p in Priority)
_STATUSES = ", ".join(s.value for s in Status)


def _session(session: Session | None) -> Session:
    return session if session is not None else SessionLocal()


def _actor(session: Session, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFound(f"Usuario {user_id} no encontrado")
    return user


def _parse_priority(value: str) -> Priority:
    try:
        return Priority(value)
    except ValueError:
        raise ValueError(f"Prioridad inválida '{value}'. Válidas: {_PRIORITIES}")


def _parse_status(value: str) -> Status:
    try:
        return Status(value)
    except ValueError:
        raise ValueError(f"Estado inválido '{value}'. Válidos: {_STATUSES}")


def _safe(fn: Callable) -> Callable:
    """Convierte cualquier error en un string que el LLM pueda explicar."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except DomainError as exc:
            return f"Error: {exc}"
        except PydanticValidationError as exc:
            first = exc.errors()[0]
            return f"Error de validación en '{'.'.join(str(x) for x in first['loc'])}': {first['msg']}"
        except ValueError as exc:
            return f"Error: {exc}"
        except Exception as exc:  # no filtrar stack traces al modelo
            return f"Error inesperado ({type(exc).__name__}). No se pudo completar la operación."

    return wrapper


def _fmt_ticket(t: Ticket) -> str:
    assignee = t.assignee_id or "sin asignar"
    return (
        f"{t.id} | {t.status} | {t.priority} | {t.category} | "
        f"solicitante {t.requester_id} | asignado {assignee} | {t.title}"
    )


# --------------------------------------------------------------------------
# Implementaciones (puras, testeables sin LLM)
# --------------------------------------------------------------------------


@_safe
def _crear_ticket_impl(
    user_id: str,
    *,
    title: str,
    description: str,
    category: str,
    priority: str,
    session: Session | None = None,
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        data = TicketCreate(
            title=title,
            description=description,
            category=category,
            priority=_parse_priority(priority),
        )
        t = ticket_service.create_ticket(s, actor, data)
        return f"Ticket creado: {t.id} (estado {t.status}, prioridad {t.priority})."
    finally:
        if session is None:
            s.close()


@_safe
def _consultar_ticket_impl(
    user_id: str, ticket_id: str, *, session: Session | None = None
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        t = ticket_service.get_ticket(s, actor, ticket_id)
        return (
            f"{t.id}\nTítulo: {t.title}\nDescripción: {t.description}\n"
            f"Categoría: {t.category}\nPrioridad: {t.priority}\nEstado: {t.status}\n"
            f"Solicitante: {t.requester_id}\nAsignado: {t.assignee_id or 'sin asignar'}\n"
            f"Creado: {t.created_at}"
        )
    finally:
        if session is None:
            s.close()


@_safe
def _buscar_tickets_impl(
    user_id: str,
    *,
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    requester_id: str | None = None,
    limite: int = 20,
    session: Session | None = None,
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        filters = TicketFilters(
            status=_parse_status(status) if status else None,
            category=category or None,
            priority=_parse_priority(priority) if priority else None,
            requester_id=requester_id or None,
            limit=max(1, min(limite, 200)),
            offset=0,
        )
        tickets = ticket_service.search_tickets(s, actor, filters)
        if not tickets:
            return "No se encontraron tickets con esos filtros."
        return f"{len(tickets)} ticket(s):\n" + "\n".join(_fmt_ticket(t) for t in tickets)
    finally:
        if session is None:
            s.close()


@_safe
def _actualizar_estado_impl(
    user_id: str,
    ticket_id: str,
    nuevo_estado: str,
    *,
    session: Session | None = None,
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        t = ticket_service.update_status(
            s, actor, ticket_id, TicketStatusUpdate(new_status=_parse_status(nuevo_estado))
        )
        return f"Estado actualizado: {t.id} ahora está en '{t.status}'."
    finally:
        if session is None:
            s.close()


@_safe
def _actualizar_prioridad_impl(
    user_id: str,
    ticket_id: str,
    prioridad: str,
    *,
    session: Session | None = None,
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        t = ticket_service.update_priority(
            s, actor, ticket_id, TicketPriorityUpdate(priority=_parse_priority(prioridad))
        )
        return f"Prioridad actualizada: {t.id} ahora es '{t.priority}'."
    finally:
        if session is None:
            s.close()


@_safe
def _asignar_ticket_impl(
    user_id: str, ticket_id: str, assignee_id: str, *, session: Session | None = None
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        t = ticket_service.assign_ticket(s, actor, ticket_id, assignee_id)
        return f"Ticket {t.id} asignado a {t.assignee_id}."
    finally:
        if session is None:
            s.close()


@_safe
def _agregar_comentario_impl(
    user_id: str, ticket_id: str, texto: str, *, session: Session | None = None
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        c = ticket_service.add_comment(s, actor, ticket_id, CommentCreate(text=texto))
        return f"Comentario agregado al ticket {c.ticket_id} (id {c.id})."
    finally:
        if session is None:
            s.close()


@_safe
def _consultar_historial_impl(
    user_id: str, ticket_id: str, *, session: Session | None = None
) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        events = ticket_service.get_history(s, actor, ticket_id)
        if not events:
            return f"El ticket {ticket_id} no tiene eventos registrados."
        lines = [
            f"{e.timestamp} | {e.event_type} | {e.old_value or '-'} -> {e.new_value or '-'} | actor {e.actor_id}"
            for e in events
        ]
        return f"Historial de {ticket_id} ({len(events)} eventos):\n" + "\n".join(lines)
    finally:
        if session is None:
            s.close()


@_safe
def _resumen_incidencias_impl(user_id: str, *, session: Session | None = None) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        summary = ticket_service.generate_summary(s, actor)
        return (
            f"Total de tickets: {summary.total}\n"
            f"Por estado: {summary.by_status}\n"
            f"Por categoría: {summary.by_category}\n"
            f"Por prioridad: {summary.by_priority}"
        )
    finally:
        if session is None:
            s.close()


@_safe
def _listar_usuarios_impl(user_id: str, *, session: Session | None = None) -> str:
    s = _session(session)
    try:
        actor = _actor(s, user_id)
        # `list_users` no valida permisos: lo hace el router. Acá lo replicamos.
        if actor.role not in ("soporte", "admin"):
            raise Forbidden("Solo soporte/admin puede listar usuarios")
        users = user_service.list_users(s)
        return "\n".join(
            f"{u.id} | {u.name} | {u.role} | {u.area} | {u.email}" for u in users
        )
    finally:
        if session is None:
            s.close()


# --------------------------------------------------------------------------
# Wrappers expuestos al LLM
# --------------------------------------------------------------------------


@tool
def crear_ticket(
    title: str,
    description: str,
    category: str,
    priority: str,
    runtime: ToolRuntime[AgentContext],
) -> str:
    """Crea un ticket de soporte. Antes de usarla, descartá duplicados con
    buscar_tickets. No pidas confirmación por texto: el sistema se la pide al
    usuario antes de ejecutarla. `category` debe ser una de:
    Hardware, Software, Redes y conectividad, Sistemas y aplicaciones,
    Accesos y permisos, Infraestructura, Otros. `priority`: Baja, Media, Alta,
    Crítica."""
    return _crear_ticket_impl(
        runtime.context.user_id,
        title=title,
        description=description,
        category=category,
        priority=priority,
    )


@tool
def consultar_ticket(ticket_id: str, runtime: ToolRuntime[AgentContext]) -> str:
    """Devuelve el detalle de un ticket por su identificador (TCK-####)."""
    return _consultar_ticket_impl(runtime.context.user_id, ticket_id)


@tool
def buscar_tickets(
    runtime: ToolRuntime[AgentContext],
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
    requester_id: str | None = None,
    limite: int = 20,
) -> str:
    """Busca tickets. Todos los filtros son opcionales. `status` (Abierto,
    En revisión, En progreso, Pendiente, Resuelto, Cerrado) y `priority`
    (Baja, Media, Alta, Crítica) usan el texto en español."""
    return _buscar_tickets_impl(
        runtime.context.user_id,
        status=status,
        category=category,
        priority=priority,
        requester_id=requester_id,
        limite=limite,
    )


@tool
def actualizar_estado(
    ticket_id: str, nuevo_estado: str, runtime: ToolRuntime[AgentContext]
) -> str:
    """Cambia el estado de un ticket respetando las transiciones permitidas.
    `nuevo_estado`: Abierto, En revisión, En progreso, Pendiente, Resuelto,
    Cerrado. Solo soporte/admin; Cerrado solo admin."""
    return _actualizar_estado_impl(runtime.context.user_id, ticket_id, nuevo_estado)


@tool
def actualizar_prioridad(
    ticket_id: str, prioridad: str, runtime: ToolRuntime[AgentContext]
) -> str:
    """Cambia la prioridad de un ticket. Solo admin. `prioridad`: Baja, Media,
    Alta, Crítica."""
    return _actualizar_prioridad_impl(runtime.context.user_id, ticket_id, prioridad)


@tool
def asignar_ticket(
    ticket_id: str, assignee_id: str, runtime: ToolRuntime[AgentContext]
) -> str:
    """Asigna un ticket a una persona de soporte. `assignee_id` es el id del
    usuario (por ejemplo S001); usá listar_usuarios para resolverlo."""
    return _asignar_ticket_impl(runtime.context.user_id, ticket_id, assignee_id)


@tool
def agregar_comentario(
    ticket_id: str, texto: str, runtime: ToolRuntime[AgentContext]
) -> str:
    """Agrega un comentario al ticket. Queda registrado en el historial."""
    return _agregar_comentario_impl(runtime.context.user_id, ticket_id, texto)


@tool
def consultar_historial(ticket_id: str, runtime: ToolRuntime[AgentContext]) -> str:
    """Devuelve el historial de eventos de un ticket."""
    return _consultar_historial_impl(runtime.context.user_id, ticket_id)


@tool
def resumen_incidencias(runtime: ToolRuntime[AgentContext]) -> str:
    """Devuelve conteos de tickets por estado, categoría y prioridad.
    Solo soporte/admin."""
    return _resumen_incidencias_impl(runtime.context.user_id)


@tool
def listar_usuarios(runtime: ToolRuntime[AgentContext]) -> str:
    """Lista los usuarios con id, nombre, rol y área. Sirve para resolver el
    `assignee_id` al asignar un ticket. Solo soporte/admin."""
    return _listar_usuarios_impl(runtime.context.user_id)


TOOLS = [
    crear_ticket,
    consultar_ticket,
    buscar_tickets,
    actualizar_estado,
    actualizar_prioridad,
    asignar_ticket,
    agregar_comentario,
    consultar_historial,
    resumen_incidencias,
    listar_usuarios,
]
