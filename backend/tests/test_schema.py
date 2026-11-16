"""Tests del schema: constraints nombradas y paridad modelo/DB."""
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from src.db import SessionLocal
from src.models import User


def _constraint_names(session):
    inspector = inspect(session.get_bind())
    return {
        c["name"]
        for c in inspector.get_unique_constraints("users")
        if c.get("name")
    }


def test_users_email_tiene_unique_nombrada(client):
    """uq_users_email debe existir en la DB real (no solo en el modelo)."""
    session = SessionLocal()
    try:
        assert "uq_users_email" in _constraint_names(session)
    finally:
        session.close()


def test_no_se_puede_insertar_email_duplicado(client):
    """La constraint debe aplicarse en la DB, no solo declararse en el modelo."""
    session = SessionLocal()
    try:
        session.add(User(
            id="U999",
            name="Duplicado",
            email="lucia.benitez@cliente-demo.com",
            password_hash="x",
            role="usuario",
            area="Test",
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    finally:
        session.close()
