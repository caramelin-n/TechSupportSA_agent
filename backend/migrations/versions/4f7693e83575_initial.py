"""initial schema

Revision ID: 4f7693e83575
Revises:
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "4f7693e83575"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("area", sa.Text(), nullable=False),
    )

    op.create_table(
        "categories",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("examples", JSONB, nullable=True),
    )

    op.create_table(
        "priorities",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("definition", sa.Text(), nullable=True),
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("requester_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("assignee_id", sa.Text(), sa.ForeignKey("users.id"), nullable=True),
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Text(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("analysis_summary", sa.Text(), nullable=True),
        sa.Column("added_at", sa.Text(), nullable=False),
        sa.Column("added_by", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Text(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("author_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )

    op.create_table(
        "history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.Text(), sa.ForeignKey("tickets.id"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timestamp", sa.Text(), nullable=False),
    )

    op.create_table(
        "documentos_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("documentos_embeddings")
    op.drop_table("history")
    op.drop_table("comments")
    op.drop_table("attachments")
    op.drop_table("tickets")
    op.drop_table("priorities")
    op.drop_table("categories")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
