import { API_BASE } from "./config";
import { getToken } from "../auth/storage";

/** Error de API con status HTTP y mensaje listo para pintar en español. */
export class ApiError extends Error {
  constructor(status, message, detail = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** Callback invocado cuando el backend responde 401 en cualquier request. */
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler ?? (() => {});
}

/** Aplana el `detail` de FastAPI (422) a un texto legible por campo. */
function formatValidationDetail(detail) {
  if (!Array.isArray(detail)) return "Datos inválidos.";
  return detail
    .map((item) => {
      const campo = (item.loc ?? []).filter((p) => p !== "body").join(".");
      const texto = item.msg ?? "valor inválido";
      return campo ? `${campo}: ${texto}` : texto;
    })
    .join(" | ");
}

function mensajePorStatus(status, detail) {
  switch (status) {
    case 400:
      return "La solicitud no es válida.";
    case 401:
      return "Credenciales inválidas o sesión expirada.";
    case 403:
      return "No tenés permisos para realizar esa acción.";
    case 404:
      return "No se encontró el recurso solicitado.";
    case 409:
      return typeof detail === "string" ? detail : "Hay una acción pendiente de confirmación.";
    case 410:
      return typeof detail === "string" ? detail : "El recurso ya no está disponible.";
    case 422:
      return formatValidationDetail(detail);
    default:
      if (status >= 500) {
        // 503 trae un detalle útil (cuota, modelo, API key): mostrarlo tal cual.
        if (typeof detail === "string" && detail) return detail;
        return "Error del servidor. Intentá de nuevo en un momento.";
      }
      return "No se pudo completar la operación.";
  }
}

/** Convierte una Response en datos o lanza `ApiError`. */
async function parseResponse(response) {
  if (response.status === 204) return null;

  const texto = await response.text();
  let datos = null;
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      datos = null;
    }
  }

  if (!response.ok) {
    const detail = datos?.detail ?? null;
    if (response.status === 401) onUnauthorized();
    throw new ApiError(response.status, mensajePorStatus(response.status, detail), detail);
  }

  return datos;
}

/** Encabezados comunes; el Bearer es opcional. */
function authHeaders(withAuth) {
  const headers = { Accept: "application/json" };
  if (withAuth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Wrapper de fetch con token Bearer automático y errores normalizados.
 *
 * @param {string} path ruta relativa al backend, sin el prefijo /api
 * @param {{method?: string, body?: unknown, auth?: boolean, signal?: AbortSignal}} options
 */
export async function request(path, options = {}) {
  const { method = "GET", body, auth = true, signal } = options;

  const headers = authHeaders(auth);
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor.");
  }

  return parseResponse(response);
}

/**
 * POST multipart (FormData). No setea Content-Type: lo agrega el navegador con
 * el boundary; forzarlo rompe la subida.
 */
export async function requestForm(path, formData, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: authHeaders(true),
      body: formData,
      signal: options.signal,
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor.");
  }

  return parseResponse(response);
}

export const api = {
  get: (path, options) => request(path, { ...options, method: "GET" }),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};
