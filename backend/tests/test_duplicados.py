"""Detección de tickets duplicados (criterio 10) con el embedder falso del conftest.

El embedder falso ordena los tickets como uno real, pero con distancias más
grandes, así que el umbral se sube a 0.6. El valor real se calibra con
`scripts/indexar_tickets.py --calibrar`.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from src.agent.tools import _buscar_similares_impl, _crear_ticket_impl
from src.core.config import settings
from src.models import Ticket, TicketEmbedding, User
from src.services import similarity_service

# Lucía (U001) tiene abierto TCK-1001 «Sistema de facturación no abre».
FACTURACION = dict(
    title="El sistema de facturación no abre",
    description="Cuando intento abrir el sistema de facturación no abre y queda la pantalla en blanco.",
    category="Sistemas y aplicaciones",
    priority="Alta",
)
OTRA_COSA = dict(
    title="Mouse inalámbrico sin batería",
    description="El mouse inalámbrico del puesto dejó de responder, parece la batería.",
    category="Hardware",
    priority="Baja",
)


@pytest.fixture(autouse=True)
def umbral(monkeypatch):
    monkeypatch.setattr(settings, "duplicate_max_distance", 0.6)


@pytest.fixture()
def indexed(db_session, fake_embedder):
    """Indexa los tickets del seed, como hace scripts/indexar_tickets.py."""
    tickets = similarity_service.tickets_without_embedding(db_session)
    similarity_service.index_tickets(db_session, tickets, fake_embedder)
    return db_session


def _count(db_session) -> int:
    return db_session.execute(select(func.count()).select_from(Ticket)).scalar_one()


def _user(db_session, user_id) -> User:
    return db_session.get(User, user_id)


# --------------------------------------------------------------------------
# Servicio
# --------------------------------------------------------------------------


def test_encuentra_el_ticket_parecido(indexed):
    vector = similarity_service.embed_one(
        similarity_service.ticket_text(
            FACTURACION["title"], FACTURACION["category"], FACTURACION["description"]
        )
    )
    [top, *_] = similarity_service.find_similar(indexed, _user(indexed, "U001"), vector)
    assert top.ticket.id == "TCK-1001"
    assert 0 <= top.distance <= settings.duplicate_max_distance
    assert top.similarity_pct == round((1 - top.distance) * 100)


def test_un_usuario_no_ve_tickets_parecidos_de_otros(indexed):
    # TCK-1006 (backup) es de U003: Lucía no lo puede ver.
    vector = similarity_service.embed_one("Servidor caído, el backup no completa")
    lucia = similarity_service.find_similar(indexed, _user(indexed, "U001"), vector, max_distance=1)
    soporte = similarity_service.find_similar(indexed, _user(indexed, "S001"), vector)
    assert all(s.ticket.requester_id == "U001" for s in lucia)
    assert soporte[0].ticket.id == "TCK-1006"


def test_ignora_tickets_resueltos_y_cerrados(indexed):
    # TCK-1005 «Office no abre al iniciar» está Resuelto.
    vector = similarity_service.embed_one("Office no abre al iniciar")
    found = similarity_service.find_similar(indexed, _user(indexed, "A001"), vector, max_distance=1)
    assert "TCK-1005" not in {s.ticket.id for s in found}
    assert all(s.ticket.status not in ("Resuelto", "Cerrado") for s in found)


def test_sin_api_key_no_hay_embeddings():
    similarity_service.set_embedder(None)
    assert similarity_service.embed_one("hola") is None


def test_error_de_la_api_no_rompe(fake_embedder, monkeypatch):
    def boom(texts):
        raise RuntimeError("RESOURCE_EXHAUSTED")

    monkeypatch.setattr(fake_embedder, "embed", boom)
    assert similarity_service.embed_one("hola") is None


def test_dimension_incorrecta_se_descarta(fake_embedder, monkeypatch):
    monkeypatch.setattr(fake_embedder, "embed", lambda texts: [[0.1] * 3072])
    assert similarity_service.embed_one("hola") is None


# --------------------------------------------------------------------------
# crear_ticket
# --------------------------------------------------------------------------


def test_crear_ticket_parecido_no_crea_y_devuelve_candidatos(indexed):
    before = _count(indexed)
    out = _crear_ticket_impl("U001", **FACTURACION, session=indexed)
    assert out.startswith("No se creó el ticket")
    assert "TCK-1001" in out and "% parecido" in out
    assert "confirmar_duplicado=true" in out
    assert _count(indexed) == before


def test_confirmar_duplicado_crea_igual_y_guarda_embedding(indexed):
    out = _crear_ticket_impl("U001", **FACTURACION, confirmar_duplicado=True, session=indexed)
    assert out.startswith("Ticket creado:")
    ticket_id = out.split()[2]
    emb = indexed.get(TicketEmbedding, ticket_id)
    assert emb is not None and emb.model == "fake-embedder"


def test_ticket_distinto_se_crea_y_queda_indexado(indexed):
    out = _crear_ticket_impl("U001", **OTRA_COSA, session=indexed)
    assert out.startswith("Ticket creado:") and "Aviso" not in out
    ticket_id = out.split()[2]
    assert indexed.get(TicketEmbedding, ticket_id) is not None

    # El siguiente reporte del mismo problema ya lo encuentra.
    again = _crear_ticket_impl("U001", **OTRA_COSA, session=indexed)
    assert again.startswith("No se creó el ticket") and ticket_id in again


def test_sin_embeddings_crea_y_avisa(indexed):
    similarity_service.set_embedder(None)
    out = _crear_ticket_impl("U001", **FACTURACION, session=indexed)
    assert out.startswith("Ticket creado:")
    assert "no se pudo verificar" in out


def test_datos_invalidos_no_gastan_embeddings(indexed, fake_embedder):
    calls = fake_embedder.calls
    out = _crear_ticket_impl("U001", **{**OTRA_COSA, "priority": "Urgentísima"}, session=indexed)
    assert out.startswith("Error")
    assert fake_embedder.calls == calls


# --------------------------------------------------------------------------
# buscar_tickets_similares
# --------------------------------------------------------------------------


def test_buscar_similares_lista_coincidencias(indexed):
    out = _buscar_similares_impl("U001", "no abre el sistema de facturación", session=indexed)
    assert out.startswith("Tickets abiertos parecidos:")
    assert "TCK-1001" in out


def test_buscar_similares_sin_coincidencias(indexed):
    out = _buscar_similares_impl("U001", "quiero cambiar el fondo de pantalla", session=indexed)
    assert out == "No hay tickets abiertos parecidos."


def test_buscar_similares_sin_servicio(indexed):
    similarity_service.set_embedder(None)
    out = _buscar_similares_impl("U001", "no abre facturación", session=indexed)
    assert out.startswith("Error") and "buscar_tickets" in out


# --------------------------------------------------------------------------
# Gemini (con cliente falso) y recorrido completo por el agente
# --------------------------------------------------------------------------


def test_gemini_embedder_pide_1536_dimensiones_en_lotes():
    from types import SimpleNamespace

    calls = []

    def embed_content(model, contents, config):
        calls.append((model, len(contents), config))
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=[0.0] * 1536) for _ in contents]
        )

    embedder = similarity_service.GeminiEmbedder.__new__(similarity_service.GeminiEmbedder)
    embedder.model = "gemini-embedding-001"
    embedder._client = SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))

    vectors = embedder.embed([f"ticket {i}" for i in range(120)])
    assert len(vectors) == 120
    assert [n for _, n, _ in calls] == [50, 50, 20]
    model, _, config = calls[0]
    assert model == "gemini-embedding-001"
    assert config.output_dimensionality == 1536
    assert config.task_type == "SEMANTIC_SIMILARITY"


def test_agente_duplicado_y_luego_confirmado(indexed, monkeypatch):
    """crear_ticket aprobado → encuentra duplicado y no crea → el usuario dice
    que es otra → crear_ticket(confirmar_duplicado) → aprobado → se crea."""
    import asyncio

    from langchain_core.messages import AIMessage
    from langgraph.checkpoint.memory import InMemorySaver

    from src.agent import orchestrator, tools
    from tests.test_agent_confirmations import ScriptedModel, _tool_call

    monkeypatch.setattr(tools, "SessionLocal", lambda: indexed)
    llm = ScriptedModel(messages=iter([
        _tool_call("crear_ticket", **FACTURACION),
        AIMessage(content="Ya tenés TCK-1001 abierto por esto. ¿Es lo mismo?"),
        _tool_call("crear_ticket", **FACTURACION, confirmar_duplicado=True),
        AIMessage(content="Listo, creé un ticket nuevo."),
    ]))
    monkeypatch.setattr(orchestrator, "_agent", orchestrator.build_agent(llm, InMemorySaver()))
    run = asyncio.run
    before = _count(indexed)
    try:
        run(orchestrator.run_agent("U001", "dup-1", "No abre facturación"))
        r = run(orchestrator.resume_agent("U001", "dup-1", "approve"))
        assert "TCK-1001" in r.reply and r.pending_actions == []
        assert _count(indexed) == before  # aprobado, pero el código lo frenó

        r = run(orchestrator.run_agent("U001", "dup-1", "No, es otra cosa"))
        [action] = r.pending_actions
        assert "indicaste que es otra incidencia" in action.description

        r = run(orchestrator.resume_agent("U001", "dup-1", "approve"))
        assert r.reply == "Listo, creé un ticket nuevo."
        assert _count(indexed) == before + 1
    finally:
        orchestrator.reset_agent()
