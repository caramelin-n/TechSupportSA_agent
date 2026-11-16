"""Escenarios de prueba del agente (criterio 12) contra el backend y el modelo real.

Cada escenario es una conversación: mensajes del usuario (con archivos si
corresponde), las decisiones ante las confirmaciones y chequeos sobre el
resultado (qué respondió el agente y qué quedó en la base). Al final escribe
un informe en Markdown con las conversaciones completas, útil para la entrega.

Uso (dentro del contenedor del backend):
    python scripts/escenarios.py --preparar      # seed + embeddings y corre todo
    python scripts/escenarios.py                 # corre todo sobre la base actual
    python scripts/escenarios.py --solo E03,E06  # algunos
    python scripts/escenarios.py --pausa 5       # espera entre llamadas al modelo

--preparar BORRA la base y la vuelve a cargar con el seed: los escenarios
asumen los tickets del seed (por ejemplo, que TCK-1002 está Abierto).

Cada escenario hace entre 2 y 8 llamadas al modelo. Si aparece "Cuota del
modelo agotada", usá --pausa o corré por partes con --solo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
PASSWORD = "techsupport123"
ADMIN = "raul.gimenez@techsupport-demo.com"
USUARIOS = {
    "Lucía (usuario)": "lucia.benitez@cliente-demo.com",
    "Martín (usuario)": "martin.ojeda@cliente-demo.com",
    "Carla (usuario)": "carla.duarte@cliente-demo.com",
    "Diego (soporte)": "diego.salinas@techsupport-demo.com",
    "Raúl (admin)": ADMIN,
}
MAX_DECISIONES = 4


# --------------------------------------------------------------------------
# Modelo de los escenarios
# --------------------------------------------------------------------------


@dataclass
class Paso:
    mensaje: str
    archivos: tuple[str, ...] = ()
    decision: Literal["approve", "reject"] = "approve"
    motivo: str | None = None
    # Paso de respaldo: se manda solo si el agente todavía no propuso esta
    # herramienta (por ejemplo, si pidió más datos antes de crear el ticket).
    si_no_propuso: str | None = None


@dataclass
class Turno:
    rol: Literal["usuario", "agente", "decision", "error"]
    texto: str
    archivos: tuple[str, ...] = ()
    acciones: list[dict] = field(default_factory=list)


@dataclass
class Contexto:
    api: "Api"
    turnos: list[Turno] = field(default_factory=list)
    creados: list[dict] = field(default_factory=list)

    def acciones(self) -> list[dict]:
        return [a for t in self.turnos for a in t.acciones]

    def propuso(self, tool: str) -> bool:
        return any(a["tool"] == tool for a in self.acciones())

    def textos_agente(self) -> list[str]:
        return [t.texto for t in self.turnos if t.rol == "agente"]


@dataclass
class Chequeo:
    descripcion: str
    fn: Callable[[Contexto], tuple[bool, str]]


@dataclass
class Escenario:
    id: str
    titulo: str
    criterios: str
    objetivo: str
    usuario: str
    pasos: list[Paso]
    chequeos: list[Chequeo]


@dataclass
class Resultado:
    escenario: Escenario
    ctx: Contexto
    chequeos: list[tuple[str, bool, str]]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and all(ok for _, ok, _ in self.chequeos)


# --------------------------------------------------------------------------
# Chequeos
# --------------------------------------------------------------------------


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c))


def menciona(*palabras: str, todas: bool = False) -> Chequeo:
    modo = "todas" if todas else "alguna"
    lista = ", ".join(f"«{p}»" for p in palabras)

    def fn(ctx: Contexto) -> tuple[bool, str]:
        pajar = _plano(
            "\n".join(ctx.textos_agente())
            + json.dumps(ctx.acciones(), ensure_ascii=False)
        )
        vistas = [p for p in palabras if _plano(p) in pajar]
        ok = len(vistas) == len(palabras) if todas else bool(vistas)
        return ok, f"encontradas: {', '.join(vistas) or 'ninguna'}"

    return Chequeo(f"El agente menciona {modo} de: {lista}", fn)


def pregunta() -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        ok = any("?" in t for t in ctx.textos_agente())
        return ok, "hizo al menos una pregunta" if ok else "no hizo preguntas"

    return Chequeo("Pide información adicional", fn)


def propuso(tool: str) -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        vistas = sorted({a["tool"] for a in ctx.acciones()})
        return ctx.propuso(tool), f"acciones propuestas: {', '.join(vistas) or 'ninguna'}"

    return Chequeo(f"Pide confirmación para `{tool}`", fn)


def no_propuso(tool: str) -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        return not ctx.propuso(tool), "no la propuso" if not ctx.propuso(tool) else "la propuso"

    return Chequeo(f"No intenta `{tool}`", fn)


def crea_tickets(
    n: int = 1,
    categorias: tuple[str, ...] | None = None,
    prioridades: tuple[str, ...] | None = None,
    con_adjunto: bool = False,
) -> Chequeo:
    partes = [f"Se crea {n} ticket" + ("s" if n != 1 else "")]
    if categorias:
        partes.append(f"con categoría {' o '.join(categorias)}")
    if prioridades:
        partes.append(f"prioridad {' o '.join(prioridades)}")
    if con_adjunto:
        partes.append("y archivo adjunto")

    def fn(ctx: Contexto) -> tuple[bool, str]:
        nuevos = ctx.creados
        detalle = "; ".join(
            f"{t['id']} «{t['title']}» ({t['category']}, {t['priority']})" for t in nuevos
        ) or "ninguno"
        if len(nuevos) != n:
            return False, f"se crearon {len(nuevos)}: {detalle}"
        for t in nuevos:
            if categorias and t["category"] not in categorias:
                return False, detalle
            if prioridades and t["priority"] not in prioridades:
                return False, detalle
            if con_adjunto:
                eventos = [e["event_type"] for e in ctx.api.historial(t["id"])]
                if "FILE_ATTACHED" not in eventos:
                    return False, f"{detalle}; sin FILE_ATTACHED en el historial"
        return True, detalle

    return Chequeo(" ".join(partes), fn)


def no_crea_tickets() -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        ids = ", ".join(t["id"] for t in ctx.creados)
        return not ctx.creados, f"se crearon: {ids}" if ids else "no se creó ninguno"

    return Chequeo("No se crea ningún ticket", fn)


def campo(ticket_id: str, nombre: str, esperado: str | None, etiqueta: str) -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        valor = ctx.api.ticket(ticket_id)[nombre]
        return valor == esperado, f"{nombre} = {valor}"

    return Chequeo(f"{ticket_id} queda con {etiqueta} «{esperado}»", fn)


def estado(ticket_id: str, esperado: str) -> Chequeo:
    return campo(ticket_id, "status", esperado, "estado")


def prioridad(ticket_id: str, esperado: str) -> Chequeo:
    return campo(ticket_id, "priority", esperado, "prioridad")


def asignado(ticket_id: str, user_id: str) -> Chequeo:
    return campo(ticket_id, "assignee_id", user_id, "responsable")


def historial(ticket_id: str, *eventos: str) -> Chequeo:
    def fn(ctx: Contexto) -> tuple[bool, str]:
        vistos = [e["event_type"] for e in ctx.api.historial(ticket_id)]
        faltan = [e for e in eventos if e not in vistos]
        return not faltan, f"faltan: {', '.join(faltan)}" if faltan else "todos registrados"

    return Chequeo(f"El historial de {ticket_id} registra {', '.join(eventos)}", fn)


# --------------------------------------------------------------------------
# Escenarios
# --------------------------------------------------------------------------

ESCENARIOS: list[Escenario] = [
    Escenario(
        "E01", "Solicitud en texto claro", "F01, F03, F05, F06, F07, F10",
        "Con un mensaje informal pero completo, el agente clasifica, propone "
        "prioridad y crea el ticket después de la confirmación.",
        "Martín (usuario)",
        [
            Paso("Desde las 9 la impresora HP LaserJet del 3er piso no imprime para "
                 "nadie de Compras. Los trabajos quedan en cola y no sale nada, y hoy "
                 "tenemos que imprimir las órdenes de compra."),
            Paso("No muestra ningún error, los trabajos quedan en cola. Afecta a todo "
                 "el área de Compras.", si_no_propuso="crear_ticket"),
            Paso("No probé nada más. Registralo, por favor.", si_no_propuso="crear_ticket"),
        ],
        [
            propuso("crear_ticket"),
            crea_tickets(1, categorias=("Hardware",), prioridades=("Media", "Alta", "Crítica")),
        ],
    ),
    Escenario(
        "E02", "Captura de pantalla legible", "F02, F03, F07",
        "El agente lee el código de error de la captura y lo usa en el ticket, "
        "que queda con la captura adjunta.",
        "Martín (usuario)",
        [
            Paso("No puedo abrir la carpeta de Contabilidad, me sale esto.",
                 archivos=("captura_acceso_denegado.png",)),
            Paso("Es la carpeta compartida de Contabilidad en el servidor de archivos. "
                 "Hasta ayer entraba sin problema y la necesito para cerrar el mes.",
                 si_no_propuso="crear_ticket"),
            Paso("Sí, registralo así.", si_no_propuso="crear_ticket"),
        ],
        [
            menciona("0x80070005"),
            crea_tickets(1, categorias=("Accesos y permisos",), con_adjunto=True),
        ],
    ),
    Escenario(
        "E03", "Captura borrosa", "F02, F04",
        "Si la imagen no se puede leer, el agente lo dice y pregunta; no inventa "
        "un error ni crea el ticket.",
        "Lucía (usuario)",
        [Paso("No me anda esto.", archivos=("captura_borrosa.png",))],
        [pregunta(), no_propuso("crear_ticket"), no_crea_tickets()],
    ),
    Escenario(
        "E04", "Log técnico largo", "F02, F03, F07",
        "De un log de cientos de líneas, el agente identifica el error principal "
        "(timeout contra la base) y crea el ticket con el log adjunto.",
        "Carla (usuario)",
        [
            Paso("La app de facturación se me cierra sola. Te paso el log.",
                 archivos=("app_facturacion.log",)),
            Paso("Me pasa cada vez que la abro, desde esta mañana, en la PC de "
                 "Administración. No puedo facturar.", si_no_propuso="crear_ticket"),
            Paso("Sí, registralo.", si_no_propuso="crear_ticket"),
        ],
        [menciona("timeout"), crea_tickets(1, con_adjunto=True)],
    ),
    Escenario(
        "E05", "Log ambiguo", "F02, F04",
        "Un log sin errores claros no alcanza para crear un ticket: el agente "
        "explica qué ve y pide más datos.",
        "Martín (usuario)",
        [Paso("Te paso este log, revisalo.", archivos=("log_ambiguo.log",))],
        [pregunta(), no_propuso("crear_ticket"), no_crea_tickets()],
    ),
    Escenario(
        "E06", "Ticket duplicado", "Criterio 10",
        "Lucía ya tiene abierto TCK-1001 por facturación. El agente lo encuentra "
        "con otras palabras y pregunta antes de crear otro.",
        "Lucía (usuario)",
        [Paso("No me abre el sistema de facturación, queda la pantalla en blanco.")],
        [menciona("TCK-1001", "TCK-1007"), no_crea_tickets()],
    ),
    Escenario(
        "E07", "Consultas de un usuario", "F09",
        "Consultas en lenguaje natural, incluso con el ID sin prefijo.",
        "Lucía (usuario)",
        [
            Paso("¿Cuál es el estado del ticket 1001?"),
            Paso("Mostrame los tickets que tengo abiertos."),
        ],
        [menciona("En progreso"), menciona("TCK-1007"), no_crea_tickets()],
    ),
    Escenario(
        "E08", "Consulta de soporte", "F09",
        "Soporte consulta las incidencias críticas sin resolver (TCK-1002 y TCK-1006).",
        "Diego (soporte)",
        [Paso("¿Qué incidencias críticas siguen pendientes?")],
        [menciona("TCK-1002", "TCK-1006", todas=True)],
    ),
    Escenario(
        "E09", "Permisos insuficientes", "F10, criterio 11",
        "Un usuario no puede cerrar tickets: aunque lo pida (y apruebe), el "
        "estado no cambia.",
        "Lucía (usuario)",
        [Paso("Cerrá el ticket TCK-1004, ya no lo necesito.")],
        [estado("TCK-1004", "Pendiente")],
    ),
    Escenario(
        "E10", "Transición de estado inválida", "F08, criterio 8",
        "TCK-1002 está Abierto y no puede pasar directo a Resuelto: el estado no cambia.",
        "Diego (soporte)",
        [Paso("Pasá el TCK-1002 a Resuelto, ya quedó.")],
        [estado("TCK-1002", "Abierto")],
    ),
    Escenario(
        "E11", "Gestión de un ticket e historial", "F08, F10, F11, criterio 9",
        "Soporte toma un ticket: cambia el estado, se lo asigna y comenta. Todo "
        "queda en el historial con fecha y responsable.",
        "Diego (soporte)",
        [
            Paso("Tomo el TCK-1002: pasalo a En revisión, asignámelo a mí (S001) y "
                 "agregá el comentario «Revisando el switch de Ventas»."),
            Paso("Mostrame el historial del TCK-1002."),
        ],
        [
            estado("TCK-1002", "En revisión"),
            asignado("TCK-1002", "S001"),
            historial("TCK-1002", "STATUS_CHANGED", "ASSIGNED", "COMMENT_ADDED"),
        ],
    ),
    Escenario(
        "E12", "Confirmación rechazada", "F06, F10",
        "Si el usuario rechaza la confirmación, el cambio no se aplica.",
        "Diego (soporte)",
        [Paso("Subile la prioridad del TCK-1008 a Crítica.",
              decision="reject", motivo="No, mejor dejala como está.")],
        [propuso("actualizar_prioridad"), prioridad("TCK-1008", "Alta")],
    ),
    Escenario(
        "E13", "Resumen de incidencias", "F12",
        "El administrador pide un resumen agrupado por estado, categoría y prioridad.",
        "Raúl (admin)",
        [Paso("Haceme un resumen de las incidencias por estado, categoría y prioridad.")],
        [menciona("En progreso", "Hardware", "Crítica", todas=True)],
    ),
]


# --------------------------------------------------------------------------
# Cliente HTTP
# --------------------------------------------------------------------------


class Api:
    def __init__(self, client: httpx.Client, pausa: float = 0.0) -> None:
        self.client = client
        self.pausa = pausa
        self._tokens: dict[str, str] = {}

    def _headers(self, email: str) -> dict[str, str]:
        if email not in self._tokens:
            r = self.client.post("/auth/login", json={"email": email, "password": PASSWORD})
            r.raise_for_status()
            self._tokens[email] = r.json()["access_token"]
        return {"Authorization": f"Bearer {self._tokens[email]}"}

    def _check(self, r: httpx.Response) -> dict | list:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            raise RuntimeError(f"HTTP {r.status_code}: {detail}")
        return r.json()

    def subir(self, email: str, archivos: tuple[str, ...]) -> list[int]:
        files = [("files", (n, (SAMPLES / n).read_bytes(), "application/octet-stream")) for n in archivos]
        r = self.client.post("/chat/upload", files=files, headers=self._headers(email))
        return [u["id"] for u in self._check(r)]

    def chat(self, email: str, conv: str, mensaje: str, upload_ids: list[int]) -> dict:
        self._esperar()
        r = self.client.post(
            "/chat",
            json={"message": mensaje, "conversation_id": conv, "upload_ids": upload_ids},
            headers=self._headers(email),
        )
        return self._check(r)

    def decidir(self, email: str, conv: str, decision: str, motivo: str | None) -> dict:
        self._esperar()
        r = self.client.post(
            f"/chat/{conv}/decision",
            json={"decision": decision, "message": motivo},
            headers=self._headers(email),
        )
        return self._check(r)

    def tickets(self) -> list[dict]:
        r = self.client.get("/tickets", params={"limit": 200}, headers=self._headers(ADMIN))
        return self._check(r)

    def ticket(self, ticket_id: str) -> dict:
        return self._check(self.client.get(f"/tickets/{ticket_id}", headers=self._headers(ADMIN)))

    def historial(self, ticket_id: str) -> list[dict]:
        r = self.client.get(f"/tickets/{ticket_id}/history", headers=self._headers(ADMIN))
        return self._check(r)

    def _esperar(self) -> None:
        if self.pausa:
            time.sleep(self.pausa)


# --------------------------------------------------------------------------
# Ejecución
# --------------------------------------------------------------------------


def _registrar_respuesta(ctx: Contexto, resp: dict) -> None:
    ctx.turnos.append(Turno("agente", resp["reply"], acciones=resp.get("pending_actions", [])))


def correr(esc: Escenario, api: Api) -> Resultado:
    email = USUARIOS[esc.usuario]
    ctx = Contexto(api)
    conv = f"{esc.id.lower()}-{uuid4().hex[:8]}"
    error = None
    antes = {t["id"] for t in api.tickets()}
    try:
        for paso in esc.pasos:
            if paso.si_no_propuso and ctx.propuso(paso.si_no_propuso):
                continue
            ids = api.subir(email, paso.archivos) if paso.archivos else []
            ctx.turnos.append(Turno("usuario", paso.mensaje, archivos=paso.archivos))
            resp = api.chat(email, conv, paso.mensaje, ids)
            _registrar_respuesta(ctx, resp)
            for _ in range(MAX_DECISIONES):
                if not resp.get("pending_actions"):
                    break
                texto = "Aprueba" if paso.decision == "approve" else "Rechaza"
                if paso.motivo:
                    texto += f": «{paso.motivo}»"
                ctx.turnos.append(Turno("decision", texto))
                resp = api.decidir(email, conv, paso.decision, paso.motivo)
                _registrar_respuesta(ctx, resp)
    except Exception as exc:  # cuota, red, 5xx: se informa y se sigue
        error = str(exc)
        ctx.turnos.append(Turno("error", error))

    ctx.creados = [t for t in api.tickets() if t["id"] not in antes]
    chequeos = []
    for c in esc.chequeos:
        try:
            ok, detalle = c.fn(ctx)
        except Exception as exc:
            ok, detalle = False, f"no se pudo verificar: {exc}"
        chequeos.append((c.descripcion, ok, detalle))
    return Resultado(esc, ctx, chequeos, error)


# --------------------------------------------------------------------------
# Informe
# --------------------------------------------------------------------------


def _cita(texto: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in texto.splitlines())


def informe(resultados: list[Resultado], modelo: str, base_url: str) -> str:
    ok = sum(r.ok for r in resultados)
    lineas = [
        "# Escenarios de prueba del agente — TechSupport S.A.",
        "",
        f"- Fecha: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Modelo: `{modelo}`",
        f"- Backend: {base_url}",
        f"- Resultado: **{ok} de {len(resultados)} escenarios OK**",
        "",
        "| ID | Escenario | Requisitos | Resultado |",
        "|---|---|---|---|",
    ]
    for r in resultados:
        marca = "✅" if r.ok else ("⚠️ error" if r.error else "❌")
        lineas.append(f"| {r.escenario.id} | {r.escenario.titulo} | {r.escenario.criterios} | {marca} |")

    for r in resultados:
        e = r.escenario
        lineas += ["", f"## {e.id}. {e.titulo}", "", f"**Requisitos:** {e.criterios}  ",
                   f"**Usuario:** {e.usuario}  ", f"**Qué se espera:** {e.objetivo}", "",
                   "### Conversación", ""]
        for t in r.ctx.turnos:
            if t.rol == "usuario":
                adj = f" _(adjunta: {', '.join(t.archivos)})_" if t.archivos else ""
                lineas += [f"**Usuario:** {t.texto}{adj}", ""]
            elif t.rol == "agente":
                lineas += ["**Agente:**", "", _cita(t.texto or "(sin texto)"), ""]
                for a in t.acciones:
                    lineas += [f"🔒 _Acción pendiente de confirmación:_ {a['description']}", ""]
            elif t.rol == "decision":
                lineas += [f"**Decisión del usuario:** {t.texto}", ""]
            else:
                lineas += [f"**Error:** `{t.texto}`", ""]
        lineas += ["### Verificaciones", ""]
        for desc, ok_c, detalle in r.chequeos:
            lineas.append(f"- {'✅' if ok_c else '❌'} {desc} — _{detalle}_")
    return "\n".join(lineas) + "\n"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def preparar() -> None:
    import seed
    from src.db import SessionLocal
    from src.services import similarity_service

    print("Recargando la base con el seed (se borran los datos actuales)...")
    seed.main()
    embedder = similarity_service.get_embedder()
    if embedder is None:
        sys.exit("Falta GOOGLE_API_KEY: los escenarios necesitan el modelo real.")
    with SessionLocal() as s:
        n = similarity_service.index_tickets(s, similarity_service.tickets_without_embedding(s), embedder)
    print(f"Indexados {n} tickets.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--preparar", action="store_true", help="recargar el seed e indexar antes")
    parser.add_argument("--solo", help="IDs separados por coma, por ejemplo E03,E06")
    parser.add_argument("--pausa", type=float, default=0, help="segundos entre llamadas al modelo")
    parser.add_argument("--url", default=os.environ.get("ESCENARIOS_URL", "http://localhost:8000"))
    parser.add_argument("--salida", help="archivo del informe (por defecto informes/escenarios-FECHA.md)")
    args = parser.parse_args()

    elegidos = ESCENARIOS
    if args.solo:
        ids = {i.strip().upper() for i in args.solo.split(",")}
        elegidos = [e for e in ESCENARIOS if e.id in ids]
        if not elegidos:
            sys.exit(f"Ningún escenario con ID {args.solo}. Disponibles: "
                     + ", ".join(e.id for e in ESCENARIOS))
    if args.preparar:
        preparar()

    from src.core.config import settings

    resultados = []
    # El agente puede tardar: varias llamadas al modelo por mensaje.
    with httpx.Client(base_url=args.url, timeout=120) as client:
        api = Api(client, pausa=args.pausa)
        for esc in elegidos:
            print(f"{esc.id} {esc.titulo}... ", end="", flush=True)
            r = correr(esc, api)
            resultados.append(r)
            print("OK" if r.ok else ("ERROR" if r.error else "FALLA"))
            for desc, ok, detalle in r.chequeos:
                if not ok:
                    print(f"    ✗ {desc} — {detalle}")
            if r.error:
                print(f"    ! {r.error}")

    salida = Path(args.salida) if args.salida else ROOT / "informes" / f"escenarios-{datetime.now():%Y%m%d-%H%M}.md"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(informe(resultados, settings.llm_model, args.url), encoding="utf-8")
    ok = sum(r.ok for r in resultados)
    print(f"\n{ok} de {len(resultados)} escenarios OK. Informe: {salida}")
    sys.exit(0 if ok == len(resultados) else 1)


if __name__ == "__main__":
    main()
