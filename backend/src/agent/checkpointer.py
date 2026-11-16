"""Checkpointer de LangGraph: dónde se guarda cada conversación.

Con `postgres` las conversaciones y las acciones pendientes de confirmación
sobreviven a un reinicio del contenedor. Las tablas (`checkpoints`,
`checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) las crea y
migra la propia librería con `setup()`; Alembic las ignora (ver
`migrations/env.py`).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.core.config import settings

CHECKPOINT_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[BaseCheckpointSaver]:
    """Abre el checkpointer configurado y lo cierra al apagar la app."""
    if settings.checkpointer == "memory":
        yield InMemorySaver()
        return

    # Pool y no una conexión única: varias requests concurrentes de /chat
    # no se bloquean entre sí. Los kwargs son los que exige AsyncPostgresSaver.
    pool = AsyncConnectionPool(
        conninfo=settings.checkpoint_db_url,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    await pool.open()
    try:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        yield saver
    finally:
        await pool.close()
