import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createTicket, listCategories } from "../api/tickets";
import { PRIORITIES } from "../tickets/constants";

export default function NewTicketPage() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({
    title: "",
    description: "",
    category: "",
    priority: "Media",
  });
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => {
        /* sin catálogo no se puede elegir categoría */
      });
  }, []);

  const canSubmit =
    !saving &&
    form.title.trim().length >= 3 &&
    form.description.trim().length >= 10 &&
    Boolean(form.category);

  function update(patch) {
    setForm((prev) => ({ ...prev, ...patch }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;

    setSaving(true);
    setError(null);
    try {
      const created = await createTicket({
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category,
        priority: form.priority,
      });
      navigate(`/tickets/${created.id}`);
    } catch (exc) {
      setError(exc.message ?? "No se pudo crear el ticket.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="space-y-4">
      <Link to="/tickets" className="text-sm text-gray-600 hover:underline">
        ← Volver al listado
      </Link>

      <div className="max-w-2xl rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="text-xl font-semibold text-gray-900">Nuevo ticket</h2>
        <p className="mt-1 text-sm text-gray-500">
          Para incidencias informadas por chat, el agente ya crea el ticket. Este
          formulario es para alta directa del personal.
        </p>

        <form onSubmit={onSubmit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="titulo" className="block text-sm font-medium text-gray-700">
              Título
            </label>
            <input
              id="titulo"
              value={form.title}
              onChange={(e) => update({ title: e.target.value })}
              maxLength={150}
              required
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">Mínimo 3 caracteres.</p>
          </div>

          <div>
            <label htmlFor="descripcion" className="block text-sm font-medium text-gray-700">
              Descripción
            </label>
            <textarea
              id="descripcion"
              rows={4}
              value={form.description}
              onChange={(e) => update({ description: e.target.value })}
              required
              className="mt-1 w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-400">Mínimo 10 caracteres.</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="categoria" className="block text-sm font-medium text-gray-700">
                Categoría
              </label>
              <select
                id="categoria"
                value={form.category}
                onChange={(e) => update({ category: e.target.value })}
                required
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="">Elegí una categoría</option>
                {categories.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="prioridad" className="block text-sm font-medium text-gray-700">
                Prioridad
              </label>
              <select
                id="prioridad"
                value={form.priority}
                onChange={(e) => update({ priority: e.target.value })}
                className="mt-1 w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                {PRIORITIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {error && (
            <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
            >
              {saving ? "Creando…" : "Crear ticket"}
            </button>
            <Link
              to="/tickets"
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-100"
            >
              Cancelar
            </Link>
          </div>
        </form>
      </div>
    </section>
  );
}
