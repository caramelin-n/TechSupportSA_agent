import { api } from "./client";

/** Inicia sesión. Devuelve solo el token; el usuario se obtiene con me(). */
export function login(email, password) {
  return api.post("/auth/login", { email, password }, { auth: false });
}

/** Usuario autenticado. Única fuente del rol (el login no lo devuelve). */
export function me() {
  return api.get("/auth/me");
}
