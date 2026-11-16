"""El corredor de escenarios (scripts/escenarios.py), con un agente falso.

Los escenarios reales necesitan Gemini; acá se prueba la mecánica: pasos de
respaldo, decisiones, detección de tickets creados, chequeos e informe.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import escenarios as esc  # noqa: E402
from src.agent.orchestrator import AgentReply, PendingAction  # noqa: E402
from src.agent.tools import _crear_ticket_impl  # noqa: E402

IMPRESORA = dict(
    title="Impresora de Compras no imprime",
    description="La HP LaserJet del 3er piso deja los trabajos en cola.",
    category="Hardware",
    priority="Alta",
)


def test_escenarios_bien_formados():
    ids = [e.id for e in esc.ESCENARIOS]
    assert len(ids) == len(set(ids))
    for e in esc.ESCENARIOS:
        assert e.usuario in esc.USUARIOS, e.id
        assert e.pasos and e.chequeos, e.id
        for p in e.pasos:
            for archivo in p.archivos:
                assert (esc.SAMPLES / archivo).is_file(), (e.id, archivo)


@pytest.fixture()
def fake_agent(client, db_session, monkeypatch):
    """Primero pregunta; con el segundo mensaje propone crear; al aprobar crea."""
    from src.agent import tools
    from src.api.routes_chat import get_resume_agent, get_run_agent
    from src.main import app

    monkeypatch.setattr(tools, "SessionLocal", lambda: db_session)
    pending: dict[str, dict] = {}
    received = []

    async def run(user_id, conversation_id, content):
        received.append(content)
        if len(received) == 1:
            return AgentReply(reply="¿Qué impresora es y qué error muestra?")
        pending[conversation_id] = IMPRESORA
        return AgentReply(
            reply="",
            pending_actions=[PendingAction("crear_ticket", IMPRESORA, "Crear el ticket «Impresora»")],
        )

    async def resume(user_id, conversation_id, decision, message):
        args = pending.pop(conversation_id)
        if decision == "reject":
            return AgentReply(reply="No lo creo.")
        out = _crear_ticket_impl(user_id, **args, session=db_session)
        return AgentReply(reply=out)

    app.dependency_overrides[get_run_agent] = lambda: run
    app.dependency_overrides[get_resume_agent] = lambda: resume
    return received


def _escenario(**kw):
    base = dict(
        id="T01", titulo="Prueba", criterios="F01", objetivo="-", usuario="Martín (usuario)",
        pasos=[
            esc.Paso("La impresora no anda.", archivos=("reporte_impresora.txt",)),
            esc.Paso("Es la HP del 3er piso.", si_no_propuso="crear_ticket"),
            esc.Paso("No hace falta, ya la propuso.", si_no_propuso="crear_ticket"),
        ],
        chequeos=[
            esc.pregunta(),
            esc.propuso("crear_ticket"),
            esc.crea_tickets(1, categorias=("Hardware",), prioridades=("Alta",)),
            esc.menciona("Ticket creado"),
            esc.estado("TCK-1004", "Pendiente"),
        ],
    )
    base.update(kw)
    return esc.Escenario(**base)


def test_corre_un_escenario_completo(client, fake_agent):
    r = esc.correr(_escenario(), esc.Api(client))

    assert r.error is None
    assert [ok for _, ok, _ in r.chequeos] == [True] * 5, r.chequeos
    assert r.ok
    # El tercer paso no se mandó: el agente ya había propuesto crear.
    assert len(fake_agent) == 2
    roles = [t.rol for t in r.ctx.turnos]
    assert roles == ["usuario", "agente", "usuario", "agente", "decision", "agente"]
    assert r.ctx.turnos[0].archivos == ("reporte_impresora.txt",)
    # El adjunto llegó al agente como bloques multimodales.
    assert isinstance(fake_agent[0], list)
    [nuevo] = r.ctx.creados
    assert nuevo["requester_id"] == "U002"


def test_rechazo_y_chequeos_que_fallan(client, fake_agent):
    e = _escenario(
        pasos=[
            esc.Paso("La impresora no anda."),
            esc.Paso("Es la HP.", decision="reject", motivo="Mejor no."),
        ],
        chequeos=[esc.no_crea_tickets(), esc.crea_tickets(1), esc.menciona("TCK-9999")],
    )
    r = esc.correr(e, esc.Api(client))

    assert [ok for _, ok, _ in r.chequeos] == [True, False, False]
    assert not r.ok
    assert r.ctx.turnos[-2].texto == "Rechaza: «Mejor no.»"


def test_error_http_se_informa_y_no_corta(client):
    from src.api.routes_chat import get_run_agent
    from src.main import app

    async def boom(user_id, conversation_id, content):
        raise RuntimeError("GOOGLE_API_KEY no configurada")

    app.dependency_overrides[get_run_agent] = lambda: boom
    r = esc.correr(_escenario(chequeos=[esc.no_crea_tickets()]), esc.Api(client))
    assert r.error and "503" in r.error
    assert r.ctx.turnos[-1].rol == "error"
    assert r.chequeos[0][1] is True  # los chequeos igual se evalúan
    assert not r.ok


def test_informe_markdown(client, fake_agent):
    r = esc.correr(_escenario(), esc.Api(client))
    md = esc.informe([r], "modelo-x", "http://testserver")
    assert "**1 de 1 escenarios OK**" in md
    assert "| T01 | Prueba | F01 | ✅ |" in md
    assert "> ¿Qué impresora es y qué error muestra?" in md
    assert "🔒 _Acción pendiente de confirmación:_ Crear el ticket «Impresora»" in md
    assert "_(adjunta: reporte_impresora.txt)_" in md
    assert "**Decisión del usuario:** Aprueba" in md
