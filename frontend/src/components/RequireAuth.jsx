import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/**
 * Ruta protegida. Sin sesión válida redirige a /login guardando la ruta
 * de origen para volver a ella después del login.
 */
export default function RequireAuth({ children }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Cargando sesión…</p>
      </div>
    );
  }

  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}
