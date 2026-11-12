import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { login as apiLogin, me as apiMe } from "../api/auth";
import { setUnauthorizedHandler } from "../api/client";
import { clearToken, getToken, setToken } from "./storage";

const AuthContext = createContext(null);

/**
 * Estado de sesión.
 *
 * status: "loading" (validando token guardado) | "authenticated" | "anonymous"
 */
export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(null);
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setUser(null);
    setStatus("anonymous");
  }, []);

  // Un 401 en cualquier request deja la sesión sin sesión.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearToken();
      setTokenState(null);
      setUser(null);
      setStatus("anonymous");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // Bootstrap: si hay token guardado, se valida contra /auth/me.
  useEffect(() => {
    let cancelado = false;

    async function bootstrap() {
      const guardado = getToken();
      if (!guardado) {
        setStatus("anonymous");
        return;
      }
      try {
        const usuario = await apiMe();
        if (cancelado) return;
        setTokenState(guardado);
        setUser(usuario);
        setStatus("authenticated");
      } catch {
        if (cancelado) return;
        // Token expirado o inválido: no hay refresh token, hay que re-loguear.
        clearToken();
        setStatus("anonymous");
      }
    }

    bootstrap();
    return () => {
      cancelado = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await apiLogin(email, password);
    setToken(data.access_token);
    setTokenState(data.access_token);
    // El login no devuelve el usuario: el rol viene de /auth/me.
    const usuario = await apiMe();
    setUser(usuario);
    setStatus("authenticated");
    return usuario;
  }, []);

  const hasRole = useCallback(
    (...roles) => Boolean(user && roles.includes(user.role)),
    [user],
  );

  const value = useMemo(
    () => ({ token, user, status, login, logout, hasRole }),
    [token, user, status, login, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
