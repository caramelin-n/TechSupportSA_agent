import { useAuth } from "../auth/AuthContext";

/** Etiqueta legible del rol del usuario. */
const ROLES = {
  usuario: "Usuario",
  soporte: "Soporte",
  admin: "Admin",
};

export default function AppLayout({ children }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-gray-900">TechSupport S.A.</span>
            {user && (
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                {ROLES[user.role] ?? user.role}
              </span>
            )}
          </div>

          {user && (
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {user.name}
                <span className="text-gray-400"> · {user.area}</span>
              </span>
              <button
                type="button"
                onClick={logout}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-100"
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
