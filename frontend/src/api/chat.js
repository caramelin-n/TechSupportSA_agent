import { api, requestForm } from "./client";

/**
 * Envía un mensaje al agente.
 *
 * @param {{message: string, conversationId?: string|null, uploadIds?: number[]}} params
 */
export function sendMessage({ message, conversationId = null, uploadIds = [] }) {
  return api.post("/chat", {
    message,
    conversation_id: conversationId,
    upload_ids: uploadIds,
  });
}

/**
 * Sube adjuntos (PNG/JPG/WEBP/TXT/LOG). Devuelve los ids para `sendMessage`.
 *
 * @param {File[]} files
 */
export function uploadFiles(files) {
  const form = new FormData();
  for (const file of files) form.append("files", file);
  return requestForm("/chat/upload", form);
}

/**
 * Resuelve las acciones pendientes de una conversación.
 *
 * @param {string} conversationId
 * @param {"approve"|"reject"} decision
 * @param {string} [message] motivo del rechazo (opcional)
 */
export function decide(conversationId, decision, message) {
  const body = { decision };
  if (message) body.message = message;
  return api.post(`/chat/${conversationId}/decision`, body);
}
