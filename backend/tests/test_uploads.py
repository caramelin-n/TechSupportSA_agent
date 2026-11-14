"""Adjuntos (F02): subida, validación, preparación para el modelo y tickets.

Sin red ni API key: el agente se reemplaza por un runner falso que registra
el contenido que recibe.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from src.agent import multimodal
from src.agent.tools import _adjuntar_archivo_impl, _crear_ticket_impl
from src.core.config import settings
from src.models import Attachment, HistoryEvent, Ticket, User
from src.services import upload_service
from src.services.exceptions import NotFound

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"
LUCIA = "lucia.benitez@cliente-demo.com"
MARTIN = "martin.ojeda@cliente-demo.com"


@pytest.fixture(autouse=True)
def tmp_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def _png(size=(200, 100), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "white").save(buf, fmt)
    return buf.getvalue()


def _auth(client, email=LUCIA):
    r = client.post("/auth/login", json={"email": email, "password": "techsupport123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client, files, email=LUCIA):
    return client.post(
        "/chat/upload",
        files=[("files", (name, data, "application/octet-stream")) for name, data in files],
        headers=_auth(client, email),
    )


# --------------------------------------------------------------------------
# Validación al subir
# --------------------------------------------------------------------------


def test_sube_captura_y_log(client, tmp_upload_dir):
    r = _upload(client, [
        ("captura_navegador.png", (SAMPLES / "captura_navegador.png").read_bytes()),
        ("app_facturacion.log", (SAMPLES / "app_facturacion.log").read_bytes()),
    ])
    assert r.status_code == 201
    img, log = r.json()
    assert (img["kind"], log["kind"]) == ("imagen", "log")
    assert img["filename"] == "captura_navegador.png"
    # Guardado con nombre del servidor, en la carpeta del usuario.
    stored = list((tmp_upload_dir / "U001").iterdir())
    assert len(stored) == 2
    assert all(p.name != "captura_navegador.png" for p in stored)


def test_el_tipo_de_imagen_sale_del_contenido(client):
    # Un JPEG con extensión .png se acepta como JPEG.
    r = _upload(client, [("foto.png", _png(fmt="JPEG"))])
    assert r.status_code == 201
    assert r.json()[0]["kind"] == "imagen"


@pytest.mark.parametrize(
    "name,data,msg",
    [
        ("programa.exe", b"MZ\x90\x00" + b"\x00" * 100, "no admitido"),
        ("captura.png", b"esto no es una imagen", "no admitido"),
        ("datos.log", b"linea\x00binaria", "no es un archivo de texto"),
        ("informe.log", b"%PDF-1.7\n%\xe2\xe3\n1 0 obj", "no es un archivo de texto"),
        ("vacio.txt", b"", "vacío"),
        ("rota.png", _png()[:60], "dañada"),
    ],
)
def test_rechaza_archivos_invalidos(client, name, data, msg):
    r = _upload(client, [(name, data)])
    assert r.status_code == 422
    assert msg in r.json()["detail"]


def test_rechaza_archivos_grandes(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    r = _upload(client, [("grande.log", b"x" * (1024 * 1024 + 10))])
    assert r.status_code == 422
    assert "1 MB" in r.json()["detail"]


def test_rechaza_mas_de_cinco_archivos(client):
    r = _upload(client, [(f"a{i}.txt", b"hola") for i in range(6)])
    assert r.status_code == 422


def test_nombre_sin_rutas(client):
    r = _upload(client, [("../../etc/passwd.txt", b"root")])
    assert r.status_code == 201
    assert r.json()[0]["filename"] == "passwd.txt"


def test_upload_requiere_token(client):
    r = client.post("/chat/upload", files=[("files", ("a.txt", b"x", "text/plain"))])
    assert r.status_code == 401


# --------------------------------------------------------------------------
# Envío al agente
# --------------------------------------------------------------------------


def _fake_runner(app):
    from src.api.routes_chat import get_run_agent

    received = []

    async def fake(user_id, conversation_id, content):
        received.append(content)
        return "ok"

    app.dependency_overrides[get_run_agent] = lambda: fake
    return received


def test_chat_manda_mensaje_y_adjuntos_al_agente(client):
    from src.main import app

    ids = [u["id"] for u in _upload(client, [
        ("captura_acceso_denegado.png", (SAMPLES / "captura_acceso_denegado.png").read_bytes()),
        ("reporte_impresora.txt", (SAMPLES / "reporte_impresora.txt").read_bytes()),
    ]).json()]
    received = _fake_runner(app)

    r = client.post(
        "/chat",
        json={"message": "No puedo entrar", "upload_ids": ids},
        headers=_auth(client),
    )
    assert r.status_code == 200
    [content] = received
    assert content[0] == {"type": "text", "text": "No puedo entrar"}
    assert content[1]["text"].startswith(f"[Adjunto #{ids[0]}: captura_acceso_denegado.png (imagen)")
    assert content[2]["type"] == "image" and content[2]["mime_type"] == "image/png"
    assert base64.b64decode(content[2]["base64"])[:8] == b"\x89PNG\r\n\x1a\n"
    assert content[3]["text"].startswith(f"[Adjunto #{ids[1]}: reporte_impresora.txt (txt)")


def test_chat_sin_adjuntos_manda_texto_plano(client):
    from src.main import app

    received = _fake_runner(app)
    client.post("/chat", json={"message": "hola"}, headers=_auth(client))
    assert received == ["hola"]


def test_no_se_pueden_usar_adjuntos_ajenos(client):
    from src.main import app

    [ajeno] = _upload(client, [("a.txt", b"privado")], email=MARTIN).json()
    received = _fake_runner(app)
    r = client.post(
        "/chat", json={"message": "mirá", "upload_ids": [ajeno["id"]]}, headers=_auth(client)
    )
    assert r.status_code == 404
    assert received == []


def test_adjunto_borrado_del_disco_devuelve_410(client, tmp_upload_dir):
    from src.main import app

    [u] = _upload(client, [("a.txt", b"hola")]).json()
    for p in (tmp_upload_dir / "U001").iterdir():
        p.unlink()
    _fake_runner(app)
    r = client.post("/chat", json={"message": "x", "upload_ids": [u["id"]]}, headers=_auth(client))
    assert r.status_code == 410


# --------------------------------------------------------------------------
# Preparación de logs e imágenes
# --------------------------------------------------------------------------


def test_log_largo_se_recorta_a_lo_relevante():
    text = (SAMPLES / "app_facturacion.log").read_text(encoding="utf-8")
    content, note = multimodal.extract_text(text)
    lines = content.splitlines()
    assert "extracto de" in note and "de 311 líneas" in note
    assert len(lines) < 311
    assert any("ERROR" in l or "FATAL" in l for l in lines)
    assert "[...]" in lines  # bloques no contiguos separados


def test_log_sin_errores_avisa_y_muestra_inicio_y_fin():
    lines = [f"2026-10-21 14:00:{i:02d} INFO todo ok {i}" for i in range(400)]
    content, note = multimodal.extract_text("\n".join(lines))
    assert "sin líneas de ERROR" in note
    assert lines[0] in content and lines[-1] in content
    assert lines[200] not in content


def test_texto_corto_va_completo():
    text = (SAMPLES / "reporte_impresora.txt").read_text(encoding="utf-8")
    content, note = multimodal.extract_text(text)
    assert content == text
    assert note.startswith("completo")


def test_log_en_latin1_se_lee(db_session):
    lucia = db_session.get(User, "U001")
    u = upload_service.save_upload(db_session, lucia, "win.log", "Conexión rechazada".encode("latin-1"))
    assert upload_service.read_text(u) == "Conexión rechazada"


def test_imagen_grande_se_achica(db_session):
    lucia = db_session.get(User, "U001")
    u = upload_service.save_upload(db_session, lucia, "foto.jpg", _png((4000, 3000), "JPEG"))
    block = multimodal.image_block(u)
    with Image.open(io.BytesIO(base64.b64decode(block["base64"]))) as im:
        assert max(im.size) == multimodal.MAX_IMAGE_SIDE
    assert block["mime_type"] == "image/jpeg"


# --------------------------------------------------------------------------
# Adjuntos en tickets (herramientas del agente)
# --------------------------------------------------------------------------


def _save(db_session, user_id, name, data):
    return upload_service.save_upload(db_session, db_session.get(User, user_id), name, data)


def test_crear_ticket_con_adjuntos(db_session):
    up = _save(db_session, "U001", "captura.png", _png())
    out = _crear_ticket_impl(
        "U001",
        title="No puedo abrir el sistema de facturación",
        description="Al iniciar sesión aparece el error 0x80070005.",
        category="Accesos y permisos",
        priority="Alta",
        adjuntos=[{"upload_id": up.id, "resumen": "Error 0x80070005: acceso denegado"}],
        session=db_session,
    )
    assert "1 adjunto(s)" in out
    ticket_id = out.split()[2]
    [att] = db_session.execute(select(Attachment).where(Attachment.ticket_id == ticket_id)).scalars()
    assert (att.filename, att.kind, att.path) == ("captura.png", "imagen", up.path)
    assert att.analysis_summary == "Error 0x80070005: acceso denegado"
    events = db_session.execute(
        select(HistoryEvent.event_type).where(HistoryEvent.ticket_id == ticket_id)
    ).scalars().all()
    assert events == ["CREATED", "FILE_ATTACHED"]


def test_crear_ticket_con_adjunto_ajeno_no_crea_nada(db_session):
    ajeno = _save(db_session, "U002", "a.txt", b"hola")
    before = db_session.query(Ticket).count()
    out = _crear_ticket_impl(
        "U001",
        title="Algo",
        description="Descripción suficiente",
        category="Otros",
        priority="Baja",
        adjuntos=[{"upload_id": ajeno.id, "resumen": "x"}],
        session=db_session,
    )
    assert out.startswith("Error:") and f"#{ajeno.id}" in out
    assert db_session.query(Ticket).count() == before


def _ticket_de(db_session, user_id, propio=True):
    q = select(Ticket.id).where(
        Ticket.requester_id == user_id if propio else Ticket.requester_id != user_id
    )
    return db_session.execute(q.limit(1)).scalar_one()


def test_adjuntar_a_ticket_existente(db_session):
    ticket_id = _ticket_de(db_session, "U001")
    up = _save(db_session, "U001", "error.log", b"ERROR timeout")
    out = _adjuntar_archivo_impl("U001", ticket_id, up.id, "Timeout contra la base", session=db_session)
    assert out == f"Archivo 'error.log' adjuntado a {ticket_id}."
    last = db_session.execute(
        select(HistoryEvent).where(HistoryEvent.ticket_id == ticket_id).order_by(HistoryEvent.id.desc())
    ).scalars().first()
    assert (last.event_type, last.new_value, last.actor_id) == ("FILE_ATTACHED", "error.log", "U001")


def test_no_se_adjunta_a_ticket_ajeno(db_session):
    ticket_id = _ticket_de(db_session, "U001", propio=False)
    up = _save(db_session, "U001", "a.txt", b"hola")
    out = _adjuntar_archivo_impl("U001", ticket_id, up.id, "x", session=db_session)
    assert out.startswith("Error:") and "permiso" in out


def test_soporte_puede_adjuntar_a_cualquier_ticket(db_session):
    ticket_id = _ticket_de(db_session, "U001")
    up = _save(db_session, "S001", "diag.txt", b"diagnostico")
    out = _adjuntar_archivo_impl("S001", ticket_id, up.id, "Diagnóstico", session=db_session)
    assert out.startswith("Archivo")


def test_get_owned_uploads_respeta_el_orden_y_duplicados(db_session):
    lucia = db_session.get(User, "U001")
    a = _save(db_session, "U001", "a.txt", b"a")
    b = _save(db_session, "U001", "b.txt", b"b")
    got = upload_service.get_owned_uploads(db_session, lucia, [b.id, a.id, b.id])
    assert [u.id for u in got] == [b.id, a.id]
    with pytest.raises(NotFound):
        upload_service.get_owned_uploads(db_session, lucia, [999999])
