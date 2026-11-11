"""SQLAlchemy models — TechSupport S.A. (PostgreSQL + pgvector)."""
from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str] = mapped_column(Text, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    requester_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id"), nullable=True
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tickets.id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[str] = mapped_column(Text, nullable=False)
    added_by: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tickets.id"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class HistoryEvent(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tickets.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class Priority(Base):
    __tablename__ = "priorities"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentEmbedding(Base):
    __tablename__ = "documentos_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(1536), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
