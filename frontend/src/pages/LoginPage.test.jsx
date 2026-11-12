import { describe, expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import LoginPage from "./LoginPage";
import { jsonResponse, mockFetch } from "../test/setup";

const USUARIO = {
  id: "U001",
  name: "Lucía Benítez",
  email: "lucia.benitez@cliente-demo.com",
  role: "usuario",
  area: "Facturación",
};

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>panel de tickets</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  it("con credenciales válidas navega al panel", async () => {
    mockFetch({
      "POST /auth/login": jsonResponse({ access_token: "jwt-nuevo", token_type: "bearer" }),
      "GET /auth/me": jsonResponse(USUARIO),
    });

    renderLogin();

    await userEvent.type(screen.getByLabelText("Email"), "lucia.benitez@cliente-demo.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "techsupport123");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() => expect(screen.getByText("panel de tickets")).toBeInTheDocument());
  });

  it("con 401 muestra el mensaje de credenciales inválidas y no navega", async () => {
    mockFetch({
      "POST /auth/login": jsonResponse({ detail: "Credenciales inválidas" }, 401),
    });

    renderLogin();

    await userEvent.type(screen.getByLabelText("Email"), "lucia.benitez@cliente-demo.com");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Iniciar sesión" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/credenciales inválidas/i),
    );
    expect(screen.queryByText("panel de tickets")).not.toBeInTheDocument();
  });

  it("el acceso rápido de la demo inicia sesión con el usuario elegido", async () => {
    mockFetch({
      "POST /auth/login": jsonResponse({ access_token: "jwt-nuevo", token_type: "bearer" }),
      "GET /auth/me": jsonResponse({ ...USUARIO, role: "admin" }),
    });

    renderLogin();

    await userEvent.click(screen.getByRole("button", { name: /Raúl Giménez/ }));

    await waitFor(() => expect(screen.getByText("panel de tickets")).toBeInTheDocument());
  });
});
