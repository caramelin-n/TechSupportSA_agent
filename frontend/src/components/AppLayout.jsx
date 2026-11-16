import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ROLE_LABEL } from "../tickets/constants";

function navClass({ isActive }) {
  const base = "rounded-md px-3 py-1.5 text-sm transition";
  return isActive
    ? `${base} bg-gray-100 font-medium text-gray-900`
    : `${base} text-gray-600 hover:bg-gray-50 hover:text-gray-900`;
}

export default function AppLayout({ children }) {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-3 px-6 py-4">
          <span className="text-lg font-semibold text-gray-900">TechSupport S.A.</span>

          {user && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
              {ROLE_LABEL[user.role] ?? user.role}
            </span>
          )}

          <nav className="flex items-center gap-1 sm:ml-4">
            <NavLink to="/" end className={navClass}>
              Chat
            </NavLink>
            <NavLink to="/tickets" className={navClass}>
              Tickets
            </NavLink>
          </nav>

          {user && (
            <div className="ml-auto flex items-center gap-4">
              <span className="hidden text-sm text-gray-600 sm:inline">
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
