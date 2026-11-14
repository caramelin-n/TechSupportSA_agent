"""Archivos subidos al chat: validación, almacenamiento y propiedad.

Formatos admitidos (F02): imágenes PNG, JPG y WEBP (fotos y capturas), y
texto plano TXT o LOG. El tipo de las imágenes se decide por su contenido
(bytes mágicos), no por la extensión que manda el cliente.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import filetype
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.models import Upload, User
from src.services.exceptions import NotFound, ValidationError

IMAGE_MIMES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
TEXT_EXTENSIONS = {".txt": "txt", ".log": "log"}
ADMITTED = "PNG, JPG, WEBP, TXT o LOG"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_name(filename: str | None) -> str:
    # Solo el nombre, sin rutas que mande el cliente ("../../etc/passwd").
    name = Path((filename or "").replace("\\", "/")).name.strip()
    return name[:255] or "archivo"


def _classify(name: str, data: bytes) -> tuple[str, str, str]:
    """Devuelve (kind, mime_type, extensión) o lanza ValidationError."""
    guess = filetype.guess(data)
    if guess is not None and guess.mime in IMAGE_MIMES:
        try:
            with Image.open(io.BytesIO(data)) as im:
                im.verify()
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise ValidationError(f"'{name}' parece una imagen pero está dañada.")
        return "imagen", guess.mime, IMAGE_MIMES[guess.mime]

    ext = Path(name).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        if guess is not None or b"\x00" in data[:8192]:
            raise ValidationError(
                f"'{name}' tiene extensión {ext} pero no es un archivo de texto."
            )
        return TEXT_EXTENSIONS[ext], "text/plain", ext

    raise ValidationError(f"Formato de '{name}' no admitido. Se aceptan {ADMITTED}.")


def save_upload(session: Session, actor: User, filename: str | None, data: bytes) -> Upload:
    name = _display_name(filename)
    if not data:
        raise ValidationError(f"'{name}' está vacío.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ValidationError(
            f"'{name}' supera el máximo de {settings.max_upload_mb} MB."
        )

    kind, mime, ext = _classify(name, data)

    # El nombre en disco lo genera el servidor; el del usuario queda en la DB.
    folder = Path(settings.upload_dir) / actor.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{uuid4().hex}{ext}"
    path.write_bytes(data)

    upload = Upload(
        user_id=actor.id,
        filename=name,
        path=str(path),
        kind=kind,
        mime_type=mime,
        size_bytes=len(data),
        created_at=_now(),
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def get_owned_uploads(session: Session, actor: User, ids: list[int]) -> list[Upload]:
    """Trae los uploads del usuario en el orden pedido.

    Uno ajeno se informa igual que uno inexistente, así no se puede averiguar
    qué ids existen.
    """
    if not ids:
        return []
    rows = session.execute(
        select(Upload).where(Upload.id.in_(ids), Upload.user_id == actor.id)
    ).scalars().all()
    by_id = {u.id: u for u in rows}
    missing = [i for i in ids if i not in by_id]
    if missing:
        listed = ", ".join(f"#{i}" for i in missing)
        raise NotFound(f"Adjunto(s) {listed} no encontrado(s)")
    return [by_id[i] for i in dict.fromkeys(ids)]


def read_text(upload: Upload) -> str:
    """Lee un TXT/LOG. Los logs de Windows suelen venir en latin-1."""
    raw = Path(upload.path).read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")
