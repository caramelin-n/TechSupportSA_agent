import { useEffect, useMemo, useState } from "react";
import { listUsers } from "../api/tickets";
import { useAuth } from "../auth/AuthContext";

/**
 * Directorio de usuarios para mostrar nombres en lugar de ids.
 *
 * `GET /users` es solo para soporte/admin; para un `usuario` se muestran los ids
 * (sus tickets solo lo tienen a él como solicitante).
 */
export function useDirectory() {
  const { user, hasRole } = useAuth();
  const canList = hasRole("soporte", "admin");
  const [users, setUsers] = useState([]);

  useEffect(() => {
    if (!canList) return undefined;
    let cancelado = false;
    listUsers()
      .then((data) => {
        if (!cancelado) setUsers(data);
      })
      .catch(() => {
        /* sin directorio: se muestran los ids */
      });
    return () => {
      cancelado = true;
    };
  }, [canList]);

  const byId = useMemo(
    () => Object.fromEntries(users.map((u) => [u.id, u])),
    [users],
  );

  function nameOf(id) {
    if (!id) return "—";
    if (user?.id === id) return user.name;
    return byId[id]?.name ?? id;
  }

  return { users, nameOf };
}
