"""Confirmaciones de punta a punta: grafo real + herramientas reales + DB.

El único reemplazo es el LLM: un modelo falso que devuelve llamadas a
herramientas guionadas. Así se prueba que la pausa la impone el código y que
nada se escribe en la base antes de aprobar.
"""
from __future__ import annotations

import asyncio
from itertools import count

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import func, select

from src.agent import orchestrator, tools
from src.models import HistoryEvent, Ticket

USUARIO = "U001"  # Lucía Benítez, rol usuario
_ids = count(1)


class ScriptedModel(GenericFakeChatModel):
    """Modelo falso que ignora las herramientas que le bindean."""

    def bind_tools(self, tools, **kwargs):
        return self


def _tool_call(name: str, **args) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": f"call_{next(_ids)}"}]
    )


CREAR = dict(
    title="Impresora del 2do piso no imprime",
    description="La impresora HP del segundo piso no responde desde esta mañana.",
    category="Hardware",
    priority="Media",
)


@pytest.fixture()
def agent_factory(db_session, monkeypatch):
    """Arma el agente con un guion de respuestas y la sesión de test."""
    # Las herramientas abren su propia sesión: la redirigimos a la del test
    # para que todo se deshaga con el rollback.
    monkeypatch.setattr(tools, "SessionLocal", lambda: db_session)

    def make(*responses: AIMessage, checkpointer=None):
        llm = ScriptedModel(messages=iter(responses))
        agent = orchestrator.build_agent(llm, checkpointer or InMemorySaver())
        monkeypatch.setattr(orchestrator, "_agent", agent)
        return agent

    yield make
    orchestrator.reset_agent()


def _count_tickets(db_session) -> int:
    return db_session.execute(select(func.count()).select_from(Ticket)).scalar_one()


def _run(coro):
    return asyncio.run(coro)


def test_crear_ticket_queda_pendiente_y_no_escribe(agent_factory, db_session):
    agent_factory(_tool_call("crear_ticket", **CREAR))
    before = _count_tickets(db_session)

    reply = _run(orchestrator.run_agent(USUARIO, "c1", "La impresora no imprime"))

    [action] = reply.pending_actions
    assert action.tool == "crear_ticket"
    assert action.args["category"] == "Hardware"
    assert "Impresora del 2do piso" in action.description
    assert "confirmes" in reply.reply
    assert _count_tickets(db_session) == before  # nada se creó todavía


def test_aprobar_ejecuta_la_herramienta(agent_factory, db_session):
    agent_factory(
        _tool_call("crear_ticket", **CREAR),
        AIMessage(content="Listo, registré el ticket."),
    )
    before = _count_tickets(db_session)

    _run(orchestrator.run_agent(USUARIO, "c2", "La impresora no imprime"))
    reply = _run(orchestrator.resume_agent(USUARIO, "c2", "approve"))

    assert reply.pending_actions == []
    assert reply.reply == "Listo, registré el ticket."
    assert _count_tickets(db_session) == before + 1
    t = db_session.execute(
        select(Ticket).where(Ticket.title == CREAR["title"])
    ).scalar_one()
    assert t.requester_id == USUARIO  # el solicitante sale del contexto, no del LLM
    created = db_session.execute(
        select(HistoryEvent).where(HistoryEvent.ticket_id == t.id)
    ).scalars().all()
    assert [e.event_type for e in created] == ["CREATED"]


def test_rechazar_no_ejecuta_y_el_modelo_recibe_el_motivo(agent_factory, db_session):
    agent = agent_factory(
        _tool_call("crear_ticket", **CREAR),
        AIMessage(content="Entendido, no lo creo."),
    )
    before = _count_tickets(db_session)

    _run(orchestrator.run_agent(USUARIO, "c3", "La impresora no imprime"))
    reply = _run(
        orchestrator.resume_agent(USUARIO, "c3", "reject", "es la del 3er piso")
    )

    assert reply.reply == "Entendido, no lo creo."
    assert _count_tickets(db_session) == before
    config = {"configurable": {"thread_id": orchestrator.thread_id(USUARIO, "c3")}}
    messages = _run(agent.aget_state(config)).values["messages"]
    assert any("es la del 3er piso" in str(m.content) for m in messages)


def test_mensaje_nuevo_con_pendiente_lanza_error(agent_factory):
    agent_factory(_tool_call("crear_ticket", **CREAR))
    _run(orchestrator.run_agent(USUARIO, "c4", "La impresora no imprime"))

    with pytest.raises(orchestrator.PendingActionExists):
        _run(orchestrator.run_agent(USUARIO, "c4", "y además el mouse"))


def test_decision_sin_pendientes_lanza_error(agent_factory):
    agent_factory(AIMessage(content="Hola, ¿en qué te ayudo?"))
    reply = _run(orchestrator.run_agent(USUARIO, "c5", "hola"))
    assert reply.pending_actions == []

    with pytest.raises(orchestrator.NoPendingAction):
        _run(orchestrator.resume_agent(USUARIO, "c5", "approve"))


def test_otro_usuario_no_puede_aprobar(agent_factory):
    agent_factory(_tool_call("crear_ticket", **CREAR))
    _run(orchestrator.run_agent(USUARIO, "c6", "La impresora no imprime"))

    # Mismo conversation_id, otro usuario: es otro hilo, no hay nada pendiente.
    with pytest.raises(orchestrator.NoPendingAction):
        _run(orchestrator.resume_agent("S001", "c6", "approve"))


def test_consultas_no_piden_confirmacion(agent_factory):
    agent_factory(
        _tool_call("buscar_tickets", status="Abierto"),
        AIMessage(content="Tenés estos tickets abiertos."),
    )
    reply = _run(orchestrator.run_agent(USUARIO, "c7", "mis tickets abiertos"))

    assert reply.pending_actions == []
    assert reply.reply == "Tenés estos tickets abiertos."


def test_permisos_siguen_vigentes_despues_de_aprobar(agent_factory, db_session):
    """Aprobar no saltea los permisos: un usuario no puede cambiar estados."""
    agent_factory(
        _tool_call("actualizar_estado", ticket_id="TCK-1001", nuevo_estado="En revisión"),
        AIMessage(content="No tenés permiso para eso."),
    )
    before = db_session.get(Ticket, "TCK-1001").status

    _run(orchestrator.run_agent(USUARIO, "c8", "pasá el 1001 a revisión"))
    reply = _run(orchestrator.resume_agent(USUARIO, "c8", "approve"))

    assert reply.reply == "No tenés permiso para eso."
    assert db_session.get(Ticket, "TCK-1001").status == before


def test_pendiente_sobrevive_a_un_reinicio_con_postgres(agent_factory, db_session):
    """Con el checkpointer de Postgres, la acción pendiente sigue ahí aunque el
    proceso se reinicie (acá: dos agentes distintos sobre la misma base)."""
    from src.agent.checkpointer import open_checkpointer

    conv = f"restart-{next(_ids)}"
    before = _count_tickets(db_session)

    async def scenario():
        async with open_checkpointer() as cp:
            agent_factory(_tool_call("crear_ticket", **CREAR), checkpointer=cp)
            first = await orchestrator.run_agent(USUARIO, conv, "La impresora no imprime")
        # "Reinicio": pool nuevo y agente nuevo.
        async with open_checkpointer() as cp:
            agent_factory(AIMessage(content="Creado."), checkpointer=cp)
            second = await orchestrator.resume_agent(USUARIO, conv, "approve")
        return first, second

    first, second = _run(scenario())
    assert first.pending_actions
    assert second.reply == "Creado."
    assert _count_tickets(db_session) == before + 1


def test_ticket_con_adjunto_de_punta_a_punta(agent_factory, db_session, tmp_path, monkeypatch):
    """Mensaje con imagen → crear_ticket con adjuntos → confirmar → Attachment."""
    from pathlib import Path

    from src.agent.multimodal import build_content
    from src.core.config import settings
    from src.models import Attachment, User
    from src.services import upload_service

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    sample = Path(__file__).resolve().parents[1] / "data" / "samples" / "captura_acceso_denegado.png"
    up = upload_service.save_upload(
        db_session, db_session.get(User, USUARIO), sample.name, sample.read_bytes()
    )
    content = build_content("No puedo entrar al sistema", [up])
    up_id, up_path = up.id, up.path  # la herramienta cierra la sesión compartida
    agent_factory(
        _tool_call(
            "crear_ticket",
            title="Acceso denegado al sistema de facturación",
            description="Al abrir el sistema aparece el error 0x80070005.",
            category="Accesos y permisos",
            priority="Alta",
            adjuntos=[{"upload_id": up_id, "resumen": "Error 0x80070005: acceso denegado"}],
        ),
        AIMessage(content="Registré el ticket con la captura."),
    )

    first = _run(orchestrator.run_agent(USUARIO, "adj-1", content))
    [action] = first.pending_actions
    assert "1 adjunto(s)" in action.description

    second = _run(orchestrator.resume_agent(USUARIO, "adj-1", "approve"))
    assert second.reply == "Registré el ticket con la captura."
    att = db_session.execute(
        select(Attachment).where(Attachment.filename == sample.name)
        .order_by(Attachment.id.desc())
    ).scalars().first()
    assert att.analysis_summary == "Error 0x80070005: acceso denegado"
    assert att.path == up_path
