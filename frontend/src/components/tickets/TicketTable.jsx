import { Link } from "react-router-dom";
import { PriorityBadge, StatusBadge } from "./Badges";

/** Tabla de tickets. Cada fila linkea al detalle. */
export default function TicketTable({ tickets, nameOf }) {
  if (tickets.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-10 text-center text-sm text-gray-500">
        No se encontraron tickets con esos filtros.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr className="text-left text-xs uppercase tracking-wide text-gray-500">
            <th scope="col" className="px-4 py-3">Ticket</th>
            <th scope="col" className="px-4 py-3">Título</th>
            <th scope="col" className="px-4 py-3">Estado</th>
            <th scope="col" className="px-4 py-3">Prioridad</th>
            <th scope="col" className="px-4 py-3">Categoría</th>
            <th scope="col" className="px-4 py-3">Solicitante</th>
            <th scope="col" className="px-4 py-3">Asignado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {tickets.map((ticket) => (
            <tr key={ticket.id} className="transition hover:bg-gray-50">
              <td className="whitespace-nowrap px-4 py-3 font-mono text-xs">
                <Link to={`/tickets/${ticket.id}`} className="text-gray-700 hover:underline">
                  {ticket.id}
                </Link>
              </td>
              <td className="max-w-xs px-4 py-3">
                <Link
                  to={`/tickets/${ticket.id}`}
                  className="line-clamp-1 text-gray-800 hover:underline"
                  title={ticket.title}
                >
                  {ticket.title}
                </Link>
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <StatusBadge status={ticket.status} />
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                <PriorityBadge priority={ticket.priority} />
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-600">{ticket.category}</td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                {nameOf(ticket.requester_id)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-gray-600">
                {nameOf(ticket.assignee_id)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
