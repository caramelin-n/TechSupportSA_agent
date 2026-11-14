"""ticket number sequence

Antes el próximo ID salía de ordenar los IDs como texto (después de
TCK-9999 venía mal) y dos creaciones simultáneas podían tomar el mismo número.
Una secuencia de Postgres resuelve las dos cosas.

Revision ID: dd298544509b
Revises: 7f1eadfa70d3
Create Date: 2026-11-14 13:41:39.999821

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd298544509b'
down_revision: Union[str, Sequence[str], None] = '7f1eadfa70d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYNC_SQL = """
SELECT setval(
    'ticket_number_seq',
    GREATEST(1000, COALESCE(
        (SELECT MAX(CAST(substring(id FROM 5) AS integer))
         FROM tickets WHERE id ~ '^TCK-[0-9]+$'),
        1000))
)
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq MINVALUE 1000 START 1001")
    # Continúa desde el ticket más alto que ya exista.
    op.execute(SYNC_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SEQUENCE IF EXISTS ticket_number_seq")
