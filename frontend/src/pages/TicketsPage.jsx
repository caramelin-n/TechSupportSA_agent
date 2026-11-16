import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listCategories, listTickets } from "../api/tickets";
import TicketFilters from "../components/tickets/TicketFilters";
import TicketTable from "../components/tickets/TicketTable";
import { useDirectory } from "../tickets/useDirectory";

const PAGE_SIZE = 20;
const EMPTY_FILTERS = { status: "", priority: "", category: "", unresolved: false };

export default function TicketsPage() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [page, setPage] = useState(0);
  const [tickets, setTickets] = useState([]);
  const [hasNext, setHasNext] = useState(false);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { nameOf } = useDirectory();

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => {
        /* sin categorías el filtro queda vacío */
      });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Pide uno de más para saber si hay página siguiente.
      const data = await listTickets({
        ...filters,
        limit: PAGE_SIZE + 1,
        offset: page * PAGE_SIZE,
      });
      setTickets(data.slice(0, PAGE_SIZE));
      setHasNext(data.length > PAGE_SIZE);
    } catch (exc) {
      setError(exc.message ?? "No se pudieron cargar los tickets.");
      setTickets([]);
      setHasNext(false);
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  function changeFilters(next) {
    setPage(0);
    setFilters(next);
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">Tickets</h2>
          <p className="mt-1 text-sm text-gray-500">
            Listado de incidencias. Entrá al detalle para comentar o cambiar el
            estado.
          </p>
        </div>
        <Link
          to="/tickets/new"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-700"
        >
          Nuevo ticket
        </Link>
      </div>

      <TicketFilters
        filters={filters}
        categories={categories}
        onChange={changeFilters}
        onClear={() => changeFilters(EMPTY_FILTERS)}
      />

      {error && (
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <p className="py-8 text-center text-sm text-gray-500">Cargando tickets…</p>
      ) : (
        <TicketTable tickets={tickets} nameOf={nameOf} />
      )}

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setPage((p) => Math.max(0, p - 1))}
          disabled={page === 0 || loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
        >
          Anterior
        </button>
        <span className="text-sm text-gray-500">Página {page + 1}</span>
        <button
          type="button"
          onClick={() => setPage((p) => p + 1)}
          disabled={!hasNext || loading}
          className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
        >
          Siguiente
        </button>
      </div>
    </section>
  );
}
