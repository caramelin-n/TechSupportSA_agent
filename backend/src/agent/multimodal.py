"""Prepara los adjuntos para el modelo, sin usar el LLM (testeable entero).

- Imágenes: se achican si son grandes y van como bloque `image` en base64.
- TXT/LOG cortos: van completos.
- LOG largos: solo las líneas relevantes (ERROR, WARN, FATAL, excepciones)
  con un poco de contexto. Ahorra tokens y mejora la precisión.

Cada adjunto va precedido de un encabezado `[Adjunto #id: nombre (tipo)]`,
para que el modelo pueda referenciarlo al crear el ticket.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageOps

from src.models import Upload
from src.services.upload_service import read_text

MAX_IMAGE_SIDE = 1568
FULL_TEXT_MAX_LINES = 250
FULL_TEXT_MAX_CHARS = 15_000
CONTEXT_LINES = 2
MAX_EXTRACT_LINES = 200
HEAD_TAIL_LINES = 40

ERRORS = re.compile(
    r"\b(ERROR|ERR|FATAL|CRITICAL|SEVERE|PANIC)\b|Exception|Traceback|Caused by",
    re.IGNORECASE,
)
WARNINGS = re.compile(r"\bWARN(ING)?\b", re.IGNORECASE)

RELEVANT = re.compile(
    r"\b(ERROR|ERR|WARN(ING)?|FATAL|CRITICAL|SEVERE|PANIC)\b"
    r"|Exception|Traceback|\bat [\w.$]+\(|Caused by",
    re.IGNORECASE,
)


def _header(upload: Upload, note: str = "") -> str:
    extra = f" — {note}" if note else ""
    return f"[Adjunto #{upload.id}: {upload.filename} ({upload.kind}){extra}]"


def image_block(upload: Upload) -> dict:
    with Image.open(upload.path) as original:
        rotated = original.getexif().get(0x0112, 1) != 1  # fotos de celular
        im = ImageOps.exif_transpose(original)
        if max(im.size) <= MAX_IMAGE_SIDE and not rotated:
            data = Path(upload.path).read_bytes()
            mime = upload.mime_type
        else:
            im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            buf = io.BytesIO()
            # PNG conserva la nitidez del texto en capturas; JPEG pesa menos
            # en fotos.
            if upload.mime_type == "image/jpeg":
                im.convert("RGB").save(buf, "JPEG", quality=90)
                mime = "image/jpeg"
            else:
                im.save(buf, "PNG", optimize=True)
                mime = "image/png"
            data = buf.getvalue()
    return {
        "type": "image",
        "base64": base64.b64encode(data).decode("ascii"),
        "mime_type": mime,
    }


def severity_note(lines: list[str]) -> str:
    """Cuántos errores y advertencias tiene un log, para que el modelo no
    convierta una advertencia aislada en una incidencia."""
    errors = sum(1 for line in lines if ERRORS.search(line))
    warnings = sum(1 for line in lines if WARNINGS.search(line))
    if not errors and not warnings:
        return "sin errores ni advertencias"
    if not errors:
        return f"sin errores; {warnings} advertencia(s) WARN"
    return f"{errors} línea(s) de error, {warnings} advertencia(s) WARN"


def extract_text(text: str, kind: str = "log") -> tuple[str, str]:
    """Devuelve (contenido, nota) a enviar al modelo para un TXT/LOG."""
    lines = text.splitlines()
    total = len(lines)
    if total <= FULL_TEXT_MAX_LINES and len(text) <= FULL_TEXT_MAX_CHARS:
        note = f"completo, {total} líneas"
        if kind == "log":
            note += f"; {severity_note(lines)}"
        return text, note

    hits = [i for i, line in enumerate(lines) if RELEVANT.search(line)]
    if not hits:
        head = lines[:HEAD_TAIL_LINES]
        tail = lines[-HEAD_TAIL_LINES:]
        body = "\n".join(head + ["[...]"] + tail)
        return body, (
            f"sin líneas de ERROR/WARN/FATAL ni excepciones; se muestran las "
            f"primeras y últimas {HEAD_TAIL_LINES} de {total} líneas"
        )

    keep: set[int] = set()
    for i in hits:
        keep.update(range(max(0, i - CONTEXT_LINES), min(total, i + CONTEXT_LINES + 1)))
    selected = sorted(keep)
    truncated = len(selected) > MAX_EXTRACT_LINES
    selected = selected[:MAX_EXTRACT_LINES]

    out: list[str] = []
    prev = None
    for i in selected:
        if prev is not None and i != prev + 1:
            out.append("[...]")
        out.append(lines[i])
        prev = i
    note = (
        f"extracto de {len(selected)} de {total} líneas: {len(hits)} con "
        f"ERROR/WARN/FATAL o excepciones, más contexto"
    )
    if truncated:
        note += f"; recortado a las primeras {MAX_EXTRACT_LINES}"
    return "\n".join(out), note


def upload_blocks(upload: Upload) -> list[dict]:
    if upload.kind == "imagen":
        return [{"type": "text", "text": _header(upload)}, image_block(upload)]
    content, note = extract_text(read_text(upload), upload.kind)
    return [{"type": "text", "text": f"{_header(upload, note)}\n{content}"}]


def build_content(message: str, uploads: list[Upload]) -> str | list[dict]:
    """Mensaje del usuario + adjuntos, en el formato que acepta `HumanMessage`."""
    if not uploads:
        return message
    blocks: list[dict] = [{"type": "text", "text": message}]
    for upload in uploads:
        blocks.extend(upload_blocks(upload))
    return blocks
