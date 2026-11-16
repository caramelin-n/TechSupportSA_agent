import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { setToken } from "../auth/storage";
import { jsonResponse, mockFetch } from "./setup";

export const ADMIN = {
  id: "A001",
  name: "Raúl Giménez",
  email: "raul.gimenez@techsupport-demo.com",
  role: "admin",
  area: "Jefatura",
};

export const SOPORTE = {
  id: "S001",
  name: "Diego Salinas",
  email: "diego.salinas@techsupport-demo.com",
  role: "soporte",
  area: "Soporte N1",
};

export const USUARIO = {
  id: "U001",
  name: "Lucía Benítez",
  email: "lucia.benitez@cliente-demo.com",
  role: "usuario",
  area: "Facturación",
};

/**
 * Renderiza una página protegida con AuthProvider y un token válido.
 *
 * @param {{path: string, route: string, element: React.ReactElement,
 *          user?: object, mocks?: object, extraRoutes?: React.ReactElement[]}} options
 */
export function renderProtected({
  path,
  route,
  element,
  user = ADMIN,
  mocks = {},
  extraRoutes = [],
}) {
  setToken("jwt-de-prueba");

  const { calls } = mockFetch({
    "GET /auth/me": jsonResponse(user),
    ...mocks,
  });

  const utils = render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Routes>
          <Route path={path} element={element} />
          {extraRoutes}
          <Route path="*" element={<div>otra ruta</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );

  return { ...utils, calls };
}

/** Query params de una URL registrada por mockFetch. */
export function queryOf(path) {
  const index = path.indexOf("?");
  return new URLSearchParams(index === -1 ? "" : path.slice(index + 1));
}
