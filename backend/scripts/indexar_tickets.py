"""Genera los embeddings de los tickets que no los tienen (por ejemplo, los del seed).

Uso (dentro del contenedor del backend):
    python scripts/indexar_tickets.py              # solo los que faltan
    python scripts/indexar_tickets.py --todos      # regenera todos
    python scripts/indexar_tickets.py --calibrar   # muestra distancias entre tickets

Requiere GOOGLE_API_KEY. Hace una llamada a la API cada 50 tickets.

`--calibrar` sirve para elegir DUPLICATE_MAX_DISTANCE: lista, para cada
ticket, su vecino más cercano. Los pares que son la misma incidencia tienen
que quedar por debajo del umbral, y los que no, por encima.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, text  # noqa: E402

from src.core.config import settings  # noqa: E402
from src.db import SessionLocal  # noqa: E402
from src.models import Ticket  # noqa: E402
from src.services import similarity_service  # noqa: E402

CALIBRATION_SQL = text(
    """
    SELECT DISTINCT ON (a.ticket_id)
           a.ticket_id, ta.title, b.ticket_id AS vecino, tb.title AS titulo_vecino,
           a.embedding <=> b.embedding AS distancia
    FROM ticket_embeddings a
    JOIN ticket_embeddings b ON a.ticket_id <> b.ticket_id
    JOIN tickets ta ON ta.id = a.ticket_id
    JOIN tickets tb ON tb.id = b.ticket_id
    ORDER BY a.ticket_id, distancia
    """
)


def indexar(todos: bool) -> None:
    embedder = similarity_service.get_embedder()
    if embedder is None:
        sys.exit("Falta GOOGLE_API_KEY en el .env: no se pueden generar embeddings.")
    with SessionLocal() as session:
        if todos:
            tickets = list(session.execute(select(Ticket).order_by(Ticket.id)).scalars())
        else:
            tickets = similarity_service.tickets_without_embedding(session)
        if not tickets:
            print("Todos los tickets ya tienen embedding.")
            return
        n = similarity_service.index_tickets(session, tickets, embedder)
        print(f"Indexados {n} tickets con {embedder.model}.")


def calibrar() -> None:
    umbral = settings.duplicate_max_distance
    with SessionLocal() as session:
        rows = session.execute(CALIBRATION_SQL).all()
    if not rows:
        sys.exit("No hay embeddings: corré primero el script sin --calibrar.")
    print(f"Umbral actual (DUPLICATE_MAX_DISTANCE): {umbral:.2f}\n")
    for r in sorted(rows, key=lambda r: r.distancia):
        marca = "DUPLICADO?" if r.distancia <= umbral else ""
        print(
            f"{r.distancia:.3f}  {r.ticket_id} «{r.title[:38]}» "
            f"↔ {r.vecino} «{r.titulo_vecino[:38]}»  {marca}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--todos", action="store_true", help="regenerar todos los embeddings")
    parser.add_argument("--calibrar", action="store_true", help="mostrar distancias entre tickets")
    args = parser.parse_args()
    if args.calibrar:
        calibrar()
    else:
        indexar(args.todos)


if __name__ == "__main__":
    main()
