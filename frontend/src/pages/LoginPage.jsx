import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

/**
 * Usuarios de la demo: el selector de usuario simulado es lo que más luce
 * en la demo (instructions.md §21). Todos comparten la misma contraseña.
 */
const USUARIOS_DEMO = [
  { email: "lucia.benitez@cliente-demo.com", nombre: "Lucía Benítez", rol: "usuario" },
  { email: "diego.salinas@techsupport-demo.com", nombre: "Diego Salinas", rol: "soporte" },
  { email: "raul.gimenez@techsupport-demo.com", nombre: "Raúl Giménez", rol: "admin" },
];

const PASSWORD_DEMO = "techsupport123";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  async function intentarLogin(credenciales) {
    setError(null);
    setEnviando(true);
    try {
      await login(credenciales.email, credenciales.password);
      navigate(location.state?.from?.pathname ?? "/", { replace: true });
    } catch (exc) {
      setError(exc.message ?? "No se pudo iniciar sesión.");
    } finally {
      setEnviando(false);
    }
  }

  function onSubmit(event) {
    event.preventDefault();
    intentarLogin({ email, password });
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-semibold text-gray-900">TechSupport S.A.</h1>
          <p className="mt-1 text-sm text-gray-500">Ingresá a tu cuenta de soporte</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-400 focus:outline-none"
              />
            </div>

            {error && (
              <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="w-full rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:opacity-60"
            >
              {enviando ? "Ingresando…" : "Iniciar sesión"}
            </button>
          </form>
        </div>

        <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            Acceso rápido (demo)
          </p>
          <div className="mt-3 space-y-2">
            {USUARIOS_DEMO.map((u) => (
              <button
                key={u.email}
                type="button"
                disabled={enviando}
                onClick={() => {
                  setEmail(u.email);
                  setPassword(PASSWORD_DEMO);
                  intentarLogin({ email: u.email, password: PASSWORD_DEMO });
                }}
                className="flex w-full items-center justify-between rounded-md border border-gray-200 px-3 py-2 text-left text-sm transition hover:bg-gray-50 disabled:opacity-60"
              >
                <span className="text-gray-800">{u.nombre}</span>
                <span className="text-xs text-gray-400">{u.rol}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
