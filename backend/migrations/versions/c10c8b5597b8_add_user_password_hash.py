"""add user password hash

Revision ID: c10c8b5597b8
Revises: 4f7693e83575
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c10c8b5597b8"
down_revision: Union[str, None] = "4f7693e83575"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    # Backfill placeholder; seed.py sobrescribe con hash real.
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", nullable=False)


def downgrade() -> None:
    op.drop_column("users", "password_hash")
