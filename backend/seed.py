"""Carga idempotente de los datos ficticios en PostgreSQL.

Uso: python seed.py
Vacía las tablas y recarga desde data/seed/*.json, así la demo siempre
arranca del mismo punto (sin duplicados).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.core.config import settings  # noqa: E402
from src.core.security import hash_password  # noqa: E402
from src.db import SessionLocal  # noqa: E402
from src.services import ticket_service  # noqa: E402
from src.models import (  # noqa: E402
    Attachment,
    Category,
    Comment,
    HistoryEvent,
    Priority,
    Ticket,
    TicketEmbedding,
    Upload,
    User,
)

SEED = ROOT / "data" / "seed"


def _load(name: str):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def _delete_upload_files(paths: list[Path]) -> int:
    """Borra los archivos de los uploads, sin salir de `upload_dir`.

    Se llama después del commit: si la transacción falla, las filas siguen
    existiendo y los archivos también.
    """
    root = Path(settings.upload_dir).resolve()
    removed = 0
    for path in paths:
        try:
            resolved = path.resolve()
            if root == resolved or root in resolved.parents:
                resolved.unlink(missing_ok=True)
                removed += 1
            else:
                print(f"Omitido (fuera de upload_dir): {resolved}")
        except OSError as exc:
            print(f"No se pudo borrar {path}: {exc}")
    return removed


def main() -> None:
    session = SessionLocal()
    try:
        # Snapshot antes de borrar: el borrado de tickets arrastra los
        # embeddings por FK (ON DELETE CASCADE), pero los tickets del seed
        # vuelven a existir con el mismo id, así que se restauran.
        preserved_embeddings = [
            (e.ticket_id, e.embedding, e.model, e.updated_at)
            for e in session.query(TicketEmbedding).all()
        ]
        upload_files = [Path(u.path) for u in session.query(Upload).all()]

        # Borrado en orden seguro por FKs.
        session.query(HistoryEvent).delete()
        session.query(Comment).delete()
        session.query(Attachment).delete()
        session.query(Ticket).delete()
        session.query(Upload).delete()  # FK a users
        session.query(User).delete()
        session.query(Category).delete()
        session.query(Priority).delete()
        session.commit()

        for c in _load("categories.json"):
            session.add(Category(name=c["name"], description=c.get("description"), examples=c.get("examples")))
        for p in _load("priorities.json"):
            session.add(Priority(name=p["name"], definition=p.get("definition")))
        session.flush()

        for u in _load("users.json"):
            session.add(User(
                id=u["id"],
                name=u["name"],
                email=u["email"],
                password_hash=hash_password("techsupport123"),
                role=u["role"],
                area=u["area"],
            ))
        session.flush()

        tickets = _load("tickets_historicos.json")
        for t in tickets:
            session.add(Ticket(
                id=t["id"],
                created_at=t["created_at"],
                requester_id=t["requester_id"],
                title=t["title"],
                description=t["description"],
                category=t["category"],
                priority=t["priority"],
                status=t["status"],
                assignee_id=t.get("assignee_id"),
            ))
        session.flush()  # asegura que existan los tickets antes de los hijos

        for t in tickets:
            for a in t.get("attachments") or []:
                session.add(Attachment(
                    ticket_id=t["id"],
                    filename=a["filename"],
                    path=a["path"],
                    kind=a["kind"],
                    analysis_summary=a.get("analysis_summary"),
                    added_at=t["created_at"],
                    added_by=t["requester_id"],
                ))
            for c in t.get("comments") or []:
                session.add(Comment(
                    ticket_id=t["id"],
                    author_id=c["author_id"],
                    text=c["text"],
                    created_at=c["created_at"],
                ))
            for h in t.get("history") or []:
                session.add(HistoryEvent(
                    ticket_id=t["id"],
                    event_type=h["event_type"],
                    old_value=h.get("old_value"),
                    new_value=h.get("new_value"),
                    actor_id=h["actor_id"],
                    timestamp=h["timestamp"],
                ))
        session.flush()
        # Restaura los embeddings de los tickets que siguen existiendo (los del
        # seed). Los de tickets ajenos quedan descartados a propósito.
        restored = 0
        for ticket_id, vector, model, updated_at in preserved_embeddings:
            if session.get(Ticket, ticket_id) is not None:
                session.add(TicketEmbedding(
                    ticket_id=ticket_id,
                    embedding=vector,
                    model=model,
                    updated_at=updated_at,
                ))
                restored += 1
        session.flush()
        # Los tickets nuevos siguen numerando desde el más alto del seed.
        ticket_service.sync_ticket_number_seq(session)
        session.commit()

        # Los archivos se borran recién después del commit: si algo falla antes,
        # las filas y los archivos siguen coincidiendo.
        removed_files = _delete_upload_files(upload_files)

        n_users = session.query(User).count()
        n_tickets = session.query(Ticket).count()
        n_history = session.query(HistoryEvent).count()
        n_attach = session.query(Attachment).count()
        n_comments = session.query(Comment).count()
        n_cats = session.query(Category).count()
        n_prios = session.query(Priority).count()
        print(f"Cargados: {n_users} usuarios, {n_tickets} tickets, "
              f"{n_cats} categorias, {n_prios} prioridades, "
              f"{n_attach} adjuntos, {n_comments} comentarios, {n_history} eventos de historial.")
        print(f"Embeddings preservados: {restored}. Archivos de uploads borrados: {removed_files}.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
