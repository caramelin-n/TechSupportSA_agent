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
