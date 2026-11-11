"""Validación de src.config.Settings."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from pydantic import ValidationError  # noqa: E402


def test_settings_requires_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    # env_file de la raíz no debe filtrar la variable para este test
    import src.config as config

    with pytest.raises(ValidationError):
        config.Settings(_env_file=None)


def test_settings_rejects_non_postgresql_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@host/db")
    import src.config as config

    with pytest.raises(ValidationError):
        config.Settings(_env_file=None)


def test_settings_accepts_valid_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    import src.config as config

    s = config.Settings(_env_file=None)
    assert s.database_url.startswith("postgresql")
