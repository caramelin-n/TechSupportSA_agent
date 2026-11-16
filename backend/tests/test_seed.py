"""Smoke test del seed: ejecuta seed.py y verifica los conteos."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

import seed  # noqa: E402
from src.core.config import settings  # noqa: E402
from src.db import SessionLocal  # noqa: E402
from src.models import (  # noqa: E402
    Attachment,
    Category,
    HistoryEvent,
    Priority,
    Ticket,
    TicketEmbedding,
    Upload,
    User,
)

DIM = 1536


def _vector(value: float) -> list[float]:
    # 0.5 es exacto en float4, así el round-trip no pierde precisión.
    return [value] * DIM


def test_seed_counts():
    seed.main()
    session = SessionLocal()
    try:
        assert session.query(User).count() == 6
        assert session.query(Ticket).count() == 13
        assert session.query(Category).count() == 7
        assert session.query(Priority).count() == 4
        assert session.query(Attachment).count() >= 1
        assert session.query(HistoryEvent).count() >= 1
    finally:
        session.close()


def test_seed_preserva_embeddings_de_tickets_del_seed():
    """Correr los tests no debe vaciar el índice semántico (criterio 10)."""
    # Guarda el embedding previo (la base de dev puede tener el índice real) y
    # lo restaura al final: este test commitea de verdad.
    original = None
    session = SessionLocal()
    try:
        prev = session.get(TicketEmbedding, "TCK-1001")
        if prev is not None:
            original = (list(prev.embedding), prev.model, prev.updated_at)
        session.merge(TicketEmbedding(
            ticket_id="TCK-1001",
            embedding=_vector(0.5),
            model="modelo-de-prueba",
            updated_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()
    finally:
        session.close()

    seed.main()

    session = SessionLocal()
    try:
        emb = session.get(TicketEmbedding, "TCK-1001")
        assert emb is not None
        assert len(emb.embedding) == DIM
        assert emb.embedding[0] == pytest.approx(0.5)
        assert emb.model == "modelo-de-prueba"

        # Restaura el estado previo.
        if original is None:
            session.delete(emb)
        else:
            emb.embedding, emb.model, emb.updated_at = original
        session.commit()
    finally:
        session.close()


def test_seed_descarta_embeddings_de_tickets_ajenos():
    """Un ticket que no está en el seed desaparece, y su embedding también."""
    session = SessionLocal()
    try:
        session.add(Ticket(
            id="TCK-9999",
            created_at=datetime.now(timezone.utc).isoformat(),
            requester_id="U001",
            title="Ticket ajeno al seed",
            description="Este ticket no forma parte de los datos del seed.",
            category="Otros",
            priority="Baja",
            status="Abierto",
            assignee_id=None,
        ))
        session.flush()
        session.add(TicketEmbedding(
            ticket_id="TCK-9999",
            embedding=_vector(0.25),
            model="modelo-de-prueba",
            updated_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()
    finally:
        session.close()

    seed.main()

    session = SessionLocal()
    try:
        assert session.get(Ticket, "TCK-9999") is None
        assert session.get(TicketEmbedding, "TCK-9999") is None
    finally:
        session.close()


def test_seed_borra_archivos_de_uploads():
    """El seed borra las filas de Upload y también los archivos del disco."""
    root = Path(settings.upload_dir) / "tests"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{uuid4().hex}.txt"
    path.write_text("contenido de prueba", encoding="utf-8")

    session = SessionLocal()
    try:
        session.add(Upload(
            user_id="U001",
            filename="prueba.txt",
            path=str(path),
            kind="txt",
            mime_type="text/plain",
            size_bytes=path.stat().st_size,
            created_at=datetime.now(timezone.utc).isoformat(),
        ))
        session.commit()
    finally:
        session.close()

    seed.main()

    session = SessionLocal()
    try:
        assert session.query(Upload).count() == 0
    finally:
        session.close()
    assert not path.exists()
