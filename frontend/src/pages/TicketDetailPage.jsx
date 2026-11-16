import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  addComment,
  assignTicket,
  getHistory,
  getTicket,
  updatePriority,
  updateStatus,
} from "../api/tickets";
import { useAuth } from "../auth/AuthContext";
import { PriorityBadge, StatusBadge } from "../components/tickets/Badges";
import {
  allowedTransitions,
  canAssign,
  canChangePriority,
  canChangeStatus,
  describeEvent,
  formatDate,
  PRIORITIES,
} from "../tickets/constants";
import { useDirectory } from "../tickets/useDirectory";

export default function TicketDetailPage() {
  const { ticketId } = useParams();
  const { user } = useAuth();
  const { users, nameOf } = useDirectory();

  const [ticket, setTicket] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [comment, setComment] = useState("");
  const [priorityDraft, setPriorityDraft] = useState("");
  const [assigneeDraft, setAssigneeDraft] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, h] = await Promise.all([getTicket(ticketId), getHistory(ticketId)]);
      setTicket(t);
      setHistory(h);
      setPriorityDraft(t.priority);
      setAssigneeDraft(t.assignee_id ?? "");
      setError(null);
    } catch (exc) {
      setError(exc.message ?? "No se pudo cargar el ticket.");
    } finally {
      setLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action, onSuccess) {
    setBusy(true);
    setError(null);
    try {
      await action();
      if (onSuccess) onSuccess();
      await load();
    } catch (exc) {
      setError(exc.message ?? "No se pudo completar la acción.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="py-8 text-center text-sm text-gray-500">Cargando ticket…</p>;
  }

  if (!ticket) {
    return (
      <div className="space-y-4">
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error ?? "No se encontró el ticket."}
        </div>
        <Link to="/tickets" className="text-sm text-gray-600 hover:underline">
          ← Volver al listado
        </Link>
      </div>
    );
  }

  const role = user?.role;
  const transitions = allowedTransitions(ticket.status, role);

  return (
    <section className="space-y-4">
      <Link to="/tickets" className="text-sm text-gray-600 hover:underline">
        ← Volver al listado
      </Link>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-mono text-xs text-gray-500">{ticket.id}</p>
            <h2 className="mt-1 text-xl font-semibold text-gray-900">{ticket.title}</h2>
          </div>
          <div className="flex gap-2">
            <StatusBadge status={ticket.status} />
            <PriorityBadge priority={ticket.priority} />
          </div>
        </div>

        <dl className="mt-4 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
          <div className="flex gap-2">
            <dt className="text-gray-500">Categoría:</dt>
            <dd className="text-gray-800">{ticket.category}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-gray-500">Creado:</dt>
            <dd className="text-gray-800">{formatDate(ticket.created_at)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-gray-500">Solicitante:</dt>
            <dd className="text-gray-800">{nameOf(ticket.requester_id)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-gray-500">Asignado:</dt>
            <dd className="text-gray-800">{nameOf(ticket.assignee_id)}</dd>
          </div>
        </dl>

        <div className="mt-4 border-t border-gray-100 pt-4">
          <p className="whitespace-pre-wrap text-sm text-gray-700">{ticket.description}</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4 rounded-lg border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-800">Acciones</h3>

          {canChangeStatus(role) && (
            <div>
              <p className="mb-1 text-xs font-medium uppercase tracking-wide text-gray-400">
                Cambiar estado
              </p>
              {transitions.length === 0 ? (
                <p className="text-sm text-gray-500">No hay transiciones disponibles.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {transitions.map((next) => (
                    <button
                      key={next}
                      type="button"
                      disabled={busy}
                      onClick={() => run(() => updateStatus(ticket.id, next))}
                      className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
                    >
                      Pasar a «{next}»
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {canChangePriority(role) && (
            <div>
              <label htmlFor="prioridad" className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-400">
                Prioridad
              </label>
              <div className="flex gap-2">
                <select
                  id="prioridad"
                  value={priorityDraft}
                  onChange={(e) => setPriorityDraft(e.target.value)}
                  disabled={busy}
                  className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  {PRIORITIES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy || priorityDraft === ticket.priority}
                  onClick={() => run(() => updatePriority(ticket.id, priorityDraft))}
                  className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
                >
                  Aplicar
                </button>
              </div>
            </div>
          )}

          {canAssign(role) && (
            <div>
              <label htmlFor="asignado" className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-400">
                Asignar a
              </label>
              <div className="flex gap-2">
                <select
                  id="asignado"
                  value={assigneeDraft}
                  onChange={(e) => setAssigneeDraft(e.target.value)}
                  disabled={busy}
                  className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="">Sin asignar</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name} ({u.role})
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  disabled={busy || !assigneeDraft || assigneeDraft === ticket.assignee_id}
                  onClick={() => run(() => assignTicket(ticket.id, assigneeDraft))}
                  className="rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
                >
                  Asignar
                </button>
              </div>
            </div>
          )}

          <div>
            <label htmlFor="comentario" className="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-400">
              Agregar comentario
            </label>
            <textarea
              id="comentario"
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              disabled={busy}
              className="w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none"
            />
            <button
              type="button"
              disabled={busy || comment.trim().length === 0}
              onClick={() =>
                run(
                  () => addComment(ticket.id, comment.trim()),
                  () => setComment(""),
                )
              }
              className="mt-2 rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
            >
              Comentar
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-gray-200 bg-white p-5">
          <h3 className="text-sm font-semibold text-gray-800">Historial</h3>
          {history.length === 0 ? (
            <p className="mt-2 text-sm text-gray-500">Sin eventos.</p>
          ) : (
            <ol className="mt-3 space-y-3">
              {history.map((event) => (
                <li key={event.id} className="border-l-2 border-gray-200 pl-3">
                  <p className="text-sm text-gray-800">{describeEvent(event)}</p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {formatDate(event.timestamp)} · {nameOf(event.actor_id)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}
