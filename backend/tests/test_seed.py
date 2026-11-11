"""Smoke test del seed: ejecuta seed.py y verifica los conteos."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import seed  # noqa: E402
from src.db import SessionLocal  # noqa: E402
from src.models import (  # noqa: E402
    Attachment,
    Category,
    HistoryEvent,
    Priority,
    Ticket,
    User,
)


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
