"""IDs de tickets: secuencia de Postgres y normalización de lo que escribe el usuario."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from src.agent.tools import _consultar_ticket_impl
from src.db import engine
from src.models import User
from src.schemas.ticket import Priority, TicketCreate
from src.services import ticket_service

NUEVO = TicketCreate(
    title="Monitor sin imagen",
    description="El monitor del puesto 4 no muestra imagen desde hoy.",
    category="Hardware",
    priority=Priority.MEDIA,
)


def _num(ticket_id: str) -> int:
    return int(ticket_id.split("-")[1])


@pytest.fixture()
def restore_seq():
    """nextval/setval no se deshacen con el rollback: se resincroniza al final
    desde otra conexión, que no ve los tickets del test."""
    yield
    with engine.begin() as conn:
        with sessionmaker(bind=conn)() as s:
            ticket_service.sync_ticket_number_seq(s)


def test_ids_consecutivos(db_session, restore_seq):
    lucia = db_session.get(User, "U001")
    a = ticket_service.create_ticket(db_session, lucia, NUEVO)
    b = ticket_service.create_ticket(db_session, lucia, NUEVO)
    assert _num(a.id) > 1013
    assert _num(b.id) == _num(a.id) + 1


def test_despues_de_9999_sigue_10000(db_session, restore_seq):
    db_session.execute(text("SELECT setval('ticket_number_seq', 9999)"))
    lucia = db_session.get(User, "U001")
    assert ticket_service.create_ticket(db_session, lucia, NUEVO).id == "TCK-10000"
    assert ticket_service.create_ticket(db_session, lucia, NUEVO).id == "TCK-10001"


def test_dos_creaciones_simultaneas_no_repiten_id(restore_seq):
    # Dos transacciones abiertas a la vez: con max+1 las dos tomaban el mismo.
    with engine.connect() as c1, engine.connect() as c2:
        s1, s2 = sessionmaker(bind=c1)(), sessionmaker(bind=c2)()
        try:
            assert ticket_service._next_ticket_id(s1) != ticket_service._next_ticket_id(s2)
        finally:
            s1.rollback()
            s2.rollback()


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("TCK-1001", "TCK-1001"),
        ("tck-1001", "TCK-1001"),
        ("TCK1001", "TCK-1001"),
        ("tck 1001", "TCK-1001"),
        ("#1001", "TCK-1001"),
        ("1001", "TCK-1001"),
        (" 1052 ", "TCK-1052"),
        ("otra-cosa", "otra-cosa"),
    ],
)
def test_normaliza_ids(raw, expected):
    assert ticket_service.normalize_ticket_id(raw) == expected


def test_consulta_con_solo_el_numero(db_session):
    # F09: "¿Cuál es el estado del ticket 1052?"
    out = _consultar_ticket_impl("U001", "1001", session=db_session)
    assert "TCK-1001" in out and "En progreso" in out


def test_api_acepta_solo_el_numero(client):
    r = client.post(
        "/auth/login",
        json={"email": "lucia.benitez@cliente-demo.com", "password": "techsupport123"},
    )
    token = r.json()["access_token"]
    r = client.get("/tickets/1001", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["id"] == "TCK-1001"
    r = client.get("/tickets/1001/history", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and len(r.json()) > 0
