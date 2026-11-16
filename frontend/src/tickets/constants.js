/** Constantes y reglas de presentación de tickets. */

export const STATUSES = [
  "Abierto",
  "En revisión",
  "En progreso",
  "Pendiente",
  "Resuelto",
  "Cerrado",
];

/** Transiciones válidas (espejo de `ticket_service.TRANSITIONS`). */
export const TRANSITIONS = {
  Abierto: ["En revisión"],
  "En revisión": ["En progreso", "Pendiente"],
  "En progreso": ["Resuelto", "Pendiente"],
  Pendiente: ["En progreso"],
  Resuelto: ["Cerrado"],
  Cerrado: [],
};

export const PRIORITIES = ["Baja", "Media", "Alta", "Crítica"];

const STATUS_STYLES = {
  Abierto: "bg-blue-50 text-blue-700",
  "En revisión": "bg-amber-50 text-amber-700",
  "En progreso": "bg-indigo-50 text-indigo-700",
  Pendiente: "bg-orange-50 text-orange-700",
  Resuelto: "bg-emerald-50 text-emerald-700",
  Cerrado: "bg-gray-100 text-gray-600",
};

const PRIORITY_STYLES = {
  Baja: "bg-gray-100 text-gray-600",
  Media: "bg-blue-50 text-blue-700",
  Alta: "bg-amber-50 text-amber-700",
  Crítica: "bg-red-50 text-red-700",
};

export function statusClass(status) {
  return STATUS_STYLES[status] ?? "bg-gray-100 text-gray-600";
}

export function priorityClass(priority) {
  return PRIORITY_STYLES[priority] ?? "bg-gray-100 text-gray-600";
}

/** Transiciones que el rol puede ejecutar. `Cerrado` es solo de admin. */
export function allowedTransitions(status, role) {
  const base = TRANSITIONS[status] ?? [];
  if (role === "admin") return base;
  return base.filter((next) => next !== "Cerrado");
}

export const canChangeStatus = (role) => role === "soporte" || role === "admin";
export const canChangePriority = (role) => role === "soporte" || role === "admin";
export const canAssign = (role) => role === "soporte" || role === "admin";
export const canCreate = () => true;

export const ROLE_LABEL = {
  usuario: "Usuario",
  soporte: "Soporte",
  admin: "Admin",
};

/** Formatea un timestamp ISO (o lo devuelve tal cual si no es parseable). */
export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
}

/** Texto legible del historial. */
export function describeEvent(event) {
  switch (event.event_type) {
    case "CREATED":
      return `Creado en estado «${event.new_value}»`;
    case "STATUS_CHANGED":
      return `Estado: «${event.old_value}» → «${event.new_value}»`;
    case "PRIORITY_CHANGED":
      return `Prioridad: «${event.old_value}» → «${event.new_value}»`;
    case "COMMENT_ADDED":
      return `Comentario: ${event.new_value}`;
    case "FILE_ATTACHED":
      return `Adjunto: ${event.new_value}`;
    case "ASSIGNED":
      return `Asignado a ${event.new_value}`;
    default:
      return event.event_type;
  }
}
