"""Carga idempotente de los datos ficticios (instructions.md §13.6).

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

from src.db import connect, init_db  # noqa: E402

SEED = ROOT / "data" / "seed"


def _load(name: str):
    return json.loads((SEED / name).read_text(encoding="utf-8"))


def main() -> None:
    init_db()
    conn = connect()
    try:
        with conn:
            conn.execute("DELETE FROM history")
            conn.execute("DELETE FROM comments")
            conn.execute("DELETE FROM attachments")
            conn.execute("DELETE FROM tickets")
            conn.execute("DELETE FROM users")

            users = _load("users.json")
            conn.executemany(
                "INSERT INTO users(id, name, email, role, area) VALUES (?, ?, ?, ?, ?)",
                [(u["id"], u["name"], u["email"], u["role"], u["area"]) for u in users],
            )

            tickets = _load("tickets_historicos.json")
            for t in tickets:
                conn.execute(
                    "INSERT INTO tickets(id, created_at, requester_id, title, description,"
                    " category, priority, status, assignee_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (t["id"], t["created_at"], t["requester_id"], t["title"], t["description"],
                     t["category"], t["priority"], t["status"], t.get("assignee_id")),
                )
                for a in t.get("attachments") or []:
                    conn.execute(
                        "INSERT INTO attachments(ticket_id, filename, path, kind,"
                        " analysis_summary, added_at, added_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (t["id"], a["filename"], a["path"], a["kind"],
                         a.get("analysis_summary"), t["created_at"], t["requester_id"]),
                    )
                for c in t.get("comments") or []:
                    conn.execute(
                        "INSERT INTO comments(ticket_id, author_id, text, created_at)"
                        " VALUES (?, ?, ?, ?)",
                        (t["id"], c["author_id"], c["text"], c["created_at"]),
                    )
                for h in t.get("history") or []:
                    conn.execute(
                        "INSERT INTO history(ticket_id, event_type, old_value, new_value,"
                        " actor_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                        (t["id"], h["event_type"], h.get("old_value"), h.get("new_value"),
                         h["actor_id"], h["timestamp"]),
                    )
        n_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        n_tickets = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        n_history = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        n_attach = conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0]
        n_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        print(f"Cargados: {n_users} usuarios, {n_tickets} tickets, "
              f"{n_attach} adjuntos, {n_comments} comentarios, {n_history} eventos de historial.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
