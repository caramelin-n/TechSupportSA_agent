import { useState } from "react";

/**
 * Acciones que el agente quiere ejecutar y esperan confirmación.
 *
 * Mientras existan, el backend rechaza mensajes nuevos (409), por eso el
 * composer queda bloqueado hasta resolverlas.
 */
export default function PendingActions({ actions, disabled, onApprove, onReject }) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  function confirmReject() {
    onReject(reason.trim() || undefined);
    setRejecting(false);
    setReason("");
  }

  return (
    <div
      role="region"
      aria-label="Acciones pendientes de confirmación"
      className="mx-4 mb-3 rounded-lg border border-amber-300 bg-amber-50 p-4"
    >
      <p className="text-sm font-medium text-amber-900">
        Antes de seguir necesito que confirmes:
      </p>

      <ul className="mt-2 space-y-2">
        {actions.map((action, i) => (
          <li key={`${action.tool}-${i}`} className="rounded-md bg-white/70 px-3 py-2">
            <p className="text-sm text-gray-800">{action.description}</p>
            <p className="mt-1 text-xs text-gray-500">Herramienta: {action.tool}</p>
          </li>
        ))}
      </ul>

      {!rejecting ? (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => onApprove()}
            disabled={disabled}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
          >
            Aprobar
          </button>
          <button
            type="button"
            onClick={() => setRejecting(true)}
            disabled={disabled}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
          >
            Rechazar
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-2">
          <label htmlFor="reject-reason" className="block text-sm text-gray-700">
            Motivo del rechazo (opcional)
          </label>
          <textarea
            id="reject-reason"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={disabled}
            className="w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none disabled:bg-gray-50"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={confirmReject}
              disabled={disabled}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-50"
            >
              Confirmar rechazo
            </button>
            <button
              type="button"
              onClick={() => {
                setRejecting(false);
                setReason("");
              }}
              disabled={disabled}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
