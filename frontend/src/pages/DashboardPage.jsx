import { useAuth } from "../auth/AuthContext";

/** Placeholder: la UI de tickets es el siguiente slice. */
export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <section className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">Panel</h2>
        <p className="mt-1 text-sm text-gray-500">
          Sesión iniciada como <span className="font-medium">{user?.name}</span> (
          {user?.role}).
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center">
        <p className="text-sm text-gray-500">
          Acá va la lista de tickets. En el próximo slice se agrega la UI de
          tickets (filtros por estado, categoría y prioridad).
        </p>
      </div>
    </section>
  );
}
