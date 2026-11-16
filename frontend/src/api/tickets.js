import { api } from "./client";

/** Lista tickets con filtros y paginación. */
export function listTickets({
  status,
  category,
  priority,
  unresolved = false,
  limit = 20,
  offset = 0,
} = {}) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (category) params.set("category", category);
  if (priority) params.set("priority", priority);
  if (unresolved) params.set("unresolved", "true");
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return api.get(`/tickets?${params.toString()}`);
}

export function getTicket(ticketId) {
  return api.get(`/tickets/${ticketId}`);
}

export function getHistory(ticketId) {
  return api.get(`/tickets/${ticketId}/history`);
}

export function createTicket(body) {
  return api.post("/tickets", body);
}

export function updateStatus(ticketId, newStatus) {
  return api.patch(`/tickets/${ticketId}/status`, { new_status: newStatus });
}

export function updatePriority(ticketId, priority) {
  return api.patch(`/tickets/${ticketId}/priority`, { priority });
}

export function assignTicket(ticketId, assigneeId) {
  return api.patch(`/tickets/${ticketId}/assignee`, { assignee_id: assigneeId });
}

export function addComment(ticketId, text) {
  return api.post(`/tickets/${ticketId}/comments`, { text });
}

export function listUsers() {
  return api.get("/users");
}

export function getUser(userId) {
  return api.get(`/users/${userId}`);
}

export function listCategories() {
  return api.get("/catalog/categories");
}

export function listPriorities() {
  return api.get("/catalog/priorities");
}
