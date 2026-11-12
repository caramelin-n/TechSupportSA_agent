import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./AuthContext";
import RequireAuth from "../components/RequireAuth";
import { getToken } from "./storage";
import { jsonResponse, mockFetch } from "../test/setup";

const USUARIO = {
  id: "U001",
  name: "Lucía Benítez",
  email: "lucia.benitez@cliente-demo.com",
  role: "usuario",
  area: "Facturación",
};

function renderConProvider(ui, { ruta = "/" } = {}) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>,
  );
}

/** Componente auxiliar que expone el estado de sesión en el DOM. */
function EstadoSesion() {
  const { status, user, login } = useAuth();
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="rol">{user?.role ?? "-"}</span>
      <button type="button" onClick={() => login("a@b.com", "x")}>
        entrar
      </button>
    </div>
  );
}

describe("AuthContext", () => {
  it("bootstrap valida el token guardado contra /auth/me y queda autenticado", async () => {
    window.localStorage.setItem("techsupport.token", "jwt-guardado");
    mockFetch({ "GET /auth/me": jsonResponse(USUARIO) });

    renderConProvider(<EstadoSesion />);

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("rol")).toHaveTextContent("usuario");
  });

  it("sin token queda anonymous", async () => {
    renderConProvider(<EstadoSesion />);

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
  });

  it("token expirado en bootstrap deja la sesión anonymous y borra el token", async () => {
    window.localStorage.setItem("techsupport.token", "jwt-vencido");
    mockFetch({ "GET /auth/me": jsonResponse({ detail: "expirado" }, 401) });

    renderConProvider(<EstadoSesion />);

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));
    expect(getToken()).toBeNull();
  });

  it("login guarda el token y trae el usuario con su rol", async () => {
    mockFetch({
      "POST /auth/login": jsonResponse({ access_token: "jwt-nuevo", token_type: "bearer" }),
      "GET /auth/me": jsonResponse({ ...USUARIO, role: "admin" }),
    });

    renderConProvider(<EstadoSesion />);
    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("anonymous"));

    await userEvent.click(screen.getByRole("button", { name: "entrar" }));

    await waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("authenticated"));
    expect(screen.getByTestId("rol")).toHaveTextContent("admin");
    expect(getToken()).toBe("jwt-nuevo");
  });
});

describe("RequireAuth", () => {
  const rutas = (
    <>
      <Route
        path="/"
        element={
          <RequireAuth>
            <div>zona protegida</div>
          </RequireAuth>
        }
      />
      <Route path="/login" element={<div>pantalla de login</div>} />
    </>
  );

  it("sin sesión redirige a /login", async () => {
    mockFetch({ "*": jsonResponse({ detail: "sin sesión" }, 401) });

    renderConProvider(<Routes>{rutas}</Routes>);

    await waitFor(() => expect(screen.getByText("pantalla de login")).toBeInTheDocument());
    expect(screen.queryByText("zona protegida")).not.toBeInTheDocument();
  });

  it("con sesión renderiza los children", async () => {
    window.localStorage.setItem("techsupport.token", "jwt-guardado");
    mockFetch({ "GET /auth/me": jsonResponse(USUARIO) });

    renderConProvider(<Routes>{rutas}</Routes>);

    await waitFor(() => expect(screen.getByText("zona protegida")).toBeInTheDocument());
  });
});
