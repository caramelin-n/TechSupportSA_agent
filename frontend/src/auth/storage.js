const TOKEN_KEY = "techsupport.token";

/** Lee el JWT guardado en localStorage. */
export function getToken() {
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/** Guarda el JWT. */
export function setToken(token) {
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* localStorage bloqueado (modo privado): la sesión no persiste. */
  }
}

/** Borra el JWT. */
export function clearToken() {
  try {
    window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nada que hacer */
  }
}
