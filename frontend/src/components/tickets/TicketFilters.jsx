import { PRIORITIES, STATUSES } from "../../tickets/constants";

const selectClass =
  "rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:border-gray-400 focus:outline-none";

/** Filtros del listado: estado, prioridad, categoría y "solo sin resolver". */
export default function TicketFilters({ filters, categories, onChange, onClear }) {
  function update(patch) {
    onChange({ ...filters, ...patch });
  }

  const hasFilters =
    Boolean(filters.status || filters.priority || filters.category) || filters.unresolved;

  return (
    <div className="flex flex-wrap items-end gap-3 rounded-lg border border-gray-200 bg-white p-4">
      <div>
        <label htmlFor="filtro-estado" className="block text-xs font-medium text-gray-500">
          Estado
        </label>
        <select
          id="filtro-estado"
          value={filters.status}
          onChange={(e) => update({ status: e.target.value })}
          className={`mt-1 ${selectClass}`}
        >
          <option value="">Todos</option>
          {STATUSES.map((status) => (
            <option key={status} value={status}>
              {status}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="filtro-prioridad" className="block text-xs font-medium text-gray-500">
          Prioridad
        </label>
        <select
          id="filtro-prioridad"
          value={filters.priority}
          onChange={(e) => update({ priority: e.target.value })}
          className={`mt-1 ${selectClass}`}
        >
          <option value="">Todas</option>
          {PRIORITIES.map((priority) => (
            <option key={priority} value={priority}>
              {priority}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="filtro-categoria" className="block text-xs font-medium text-gray-500">
          Categoría
        </label>
        <select
          id="filtro-categoria"
          value={filters.category}
          onChange={(e) => update({ category: e.target.value })}
          className={`mt-1 ${selectClass}`}
        >
          <option value="">Todas</option>
          {categories.map((category) => (
            <option key={category.name} value={category.name}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-2 text-sm text-gray-700">
        <input
          type="checkbox"
          checked={filters.unresolved}
          onChange={(e) => update({ unresolved: e.target.checked })}
          className="h-4 w-4 rounded border-gray-300"
        />
        Solo sin resolver
      </label>

      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="ml-auto text-sm text-gray-500 underline-offset-2 transition hover:text-gray-800 hover:underline"
        >
          Limpiar filtros
        </button>
      )}
    </div>
  );
}
