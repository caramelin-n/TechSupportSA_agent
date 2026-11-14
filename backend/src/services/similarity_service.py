"""Detección de tickets duplicados por similitud semántica (criterio 10).

Cada ticket se convierte en un vector (embedding) a partir de su título,
categoría y descripción. Dos tickets que describen la misma incidencia con
otras palabras quedan cerca: se comparan con distancia coseno en pgvector.

El generador de embeddings es inyectable (`set_embedder`): en producción usa
Gemini; los tests usan uno falso y determinista, sin red.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models import Ticket, TicketEmbedding, User
from src.schemas.ticket import Status

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 1536  # tamaño de la columna ticket_embeddings.embedding
BATCH_SIZE = 50

# Un ticket resuelto o cerrado no es un duplicado: la incidencia volvió a pasar.
CLOSED_STATUSES = (Status.RESUELTO.value, Status.CERRADO.value)


class Embedder(Protocol):
    model: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbedder:
    """Embeddings con la API de Gemini (paquete google-genai)."""

    def __init__(self, api_key: str, model: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types

        out: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            result = self._client.models.embed_content(
                model=self.model,
                contents=texts[i : i + BATCH_SIZE],
                config=types.EmbedContentConfig(
                    output_dimensionality=EMBEDDING_DIM,
                    task_type="SEMANTIC_SIMILARITY",
                ),
            )
            out.extend(list(e.values) for e in result.embeddings)
        return out


_embedder: Embedder | None = None
_configured = False


def set_embedder(embedder: Embedder | None) -> None:
    """Reemplaza el generador de embeddings (tests o scripts). None lo desactiva."""
    global _embedder, _configured
    _embedder = embedder
    _configured = True


def get_embedder() -> Embedder | None:
    """El embedder configurado, o None si no hay GOOGLE_API_KEY."""
    global _embedder, _configured
    if not _configured:
        _configured = True
        if settings.google_api_key:
            _embedder = GeminiEmbedder(settings.google_api_key, settings.embedding_model)
    return _embedder


def ticket_text(title: str, category: str, description: str) -> str:
    return f"{title}\nCategoría: {category}\n{description}"


def embed_one(text: str) -> list[float] | None:
    """Vector de un texto, o None si el servicio no está disponible.

    Nunca lanza: si los embeddings fallan, el ticket se crea igual y se avisa
    que no se pudo verificar duplicados.
    """
    embedder = get_embedder()
    if embedder is None:
        return None
    try:
        [vector] = embedder.embed([text])
    except Exception:
        logger.exception("Falló la generación de embeddings")
        return None
    if len(vector) != EMBEDDING_DIM:
        logger.error("Embedding de %s dimensiones (se esperaban %s)", len(vector), EMBEDDING_DIM)
        return None
    return vector


@dataclass
class SimilarTicket:
    ticket: Ticket
    distance: float

    @property
    def similarity_pct(self) -> int:
        return round((1 - self.distance) * 100)


def find_similar(
    session: Session,
    actor: User,
    vector: list[float],
    *,
    limit: int = 3,
    max_distance: float | None = None,
    exclude_ticket_id: str | None = None,
) -> list[SimilarTicket]:
    """Tickets abiertos parecidos que el usuario puede ver, del más parecido al menos.

    Respeta la misma regla de visibilidad que el resto del sistema: un usuario
    solo compara contra sus propios tickets; soporte y admin, contra todos.
    """
    if max_distance is None:
        max_distance = settings.duplicate_max_distance
    distance = TicketEmbedding.embedding.cosine_distance(vector).label("distance")
    stmt = (
        select(Ticket, distance)
        .join(TicketEmbedding, TicketEmbedding.ticket_id == Ticket.id)
        .where(Ticket.status.not_in(CLOSED_STATUSES))
        .where(distance <= max_distance)
        .order_by(distance)
        .limit(limit)
    )
    if actor.role == "usuario":
        stmt = stmt.where(Ticket.requester_id == actor.id)
    if exclude_ticket_id:
        stmt = stmt.where(Ticket.id != exclude_ticket_id)
    return [SimilarTicket(t, float(d)) for t, d in session.execute(stmt).all()]


def store_embedding(session: Session, ticket_id: str, vector: list[float], model: str) -> None:
    session.merge(
        TicketEmbedding(
            ticket_id=ticket_id,
            embedding=vector,
            model=model,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    )
    session.commit()


def tickets_without_embedding(session: Session) -> list[Ticket]:
    stmt = (
        select(Ticket)
        .outerjoin(TicketEmbedding, TicketEmbedding.ticket_id == Ticket.id)
        .where(TicketEmbedding.ticket_id.is_(None))
        .order_by(Ticket.id)
    )
    return list(session.execute(stmt).scalars().all())


def index_tickets(session: Session, tickets: list[Ticket], embedder: Embedder) -> int:
    """Genera y guarda los embeddings de varios tickets (en lotes)."""
    if not tickets:
        return 0
    texts = [ticket_text(t.title, t.category, t.description) for t in tickets]
    vectors = embedder.embed(texts)
    now = datetime.now(timezone.utc).isoformat()
    for t, v in zip(tickets, vectors):
        session.merge(
            TicketEmbedding(ticket_id=t.id, embedding=v, model=embedder.model, updated_at=now)
        )
    session.commit()
    return len(tickets)
