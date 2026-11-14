"""Fixtures de test: DB con rollback por test."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings  # noqa: E402
from src.db import Base, engine  # noqa: E402
from src.models import *  # noqa: E402,F401
import seed  # noqa: E402

# Asegura que las tablas existan.
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    seed.main()
    yield


@pytest.fixture()
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    from src.api.deps import get_db
    from src.main import app

    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class FakeEmbedder:
    """Embeddings deterministas sin red: bolsa de palabras en 1536 dimensiones.

    Textos con palabras en común quedan cerca, como con un modelo real, así se
    puede probar la detección de duplicados sin gastar cuota.
    """

    model = "fake-embedder"

    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def _words(text: str) -> list[str]:
        import re
        import unicodedata

        plain = unicodedata.normalize("NFKD", text.lower())
        plain = "".join(c for c in plain if not unicodedata.combining(c))
        return [w for w in re.findall(r"[a-z0-9]+", plain) if len(w) > 3]

    def embed(self, texts: list[str]) -> list[list[float]]:
        import hashlib
        import math

        self.calls += 1
        out = []
        for t in texts:
            v = [0.0] * 1536
            for w in self._words(t):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 1536] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


@pytest.fixture(autouse=True)
def fake_embedder():
    """Ningún test llama a la API real de embeddings, aunque haya GOOGLE_API_KEY."""
    from src.services import similarity_service

    embedder = FakeEmbedder()
    similarity_service.set_embedder(embedder)
    yield embedder
    similarity_service.set_embedder(embedder)
