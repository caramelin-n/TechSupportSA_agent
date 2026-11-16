import { describe, expect, it } from "vitest";
import { Route } from "react-router-dom";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import NewTicketPage from "./NewTicketPage";
import { jsonResponse } from "../test/setup";
import { renderProtected, USUARIO } from "../test/helpers";

function renderNew(extraMocks = {}) {
  return renderProtected({
    path: "/tickets/new",
    route: "/tickets/new",
    element: <NewTicketPage />,
    user: USUARIO,
    mocks: {
      "GET /catalog/categories": jsonResponse([
        { name: "Hardware", description: null, examples: null },
        { name: "Software", description: null, examples: null },
      ]),
      "POST /tickets": jsonResponse({ id: "TCK-2000" }, 201),
      ...extraMocks,
    },
    extraRoutes: [
      <Route key="detalle" path="/tickets/:ticketId" element={<div>detalle del ticket</div>} />,
    ],
  });
}

async function completar() {
  await waitFor(() => expect(screen.getByLabelText("Categoría")).toBeInTheDocument());
  await userEvent.type(screen.getByLabelText("Título"), "Impresora sin tóner");
  await userEvent.type(
    screen.getByLabelText("Descripción"),
    "La impresora del 3er piso no imprime por falta de tóner.",
  );
  await userEvent.selectOptions(screen.getByLabelText("Categoría"), "Hardware");
}

describe("NewTicketPage", () => {
  it("crea el ticket y navega al detalle", async () => {
    const { calls } = renderNew();

    await completar();
    await userEvent.click(screen.getByRole("button", { name: "Crear ticket" }));

    await waitFor(() => expect(screen.getByText("detalle del ticket")).toBeInTheDocument());

    const call = calls.find((c) => c.path === "/tickets" && c.method === "POST");
    expect(JSON.parse(call.options.body)).toMatchObject({
      title: "Impresora sin tóner",
      category: "Hardware",
      priority: "Media",
    });
  });

  it("no permite enviar sin categoría", async () => {
    renderNew();

    await waitFor(() => expect(screen.getByLabelText("Título")).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText("Título"), "Algo");
    await userEvent.type(screen.getByLabelText("Descripción"), "Descripción suficientemente larga");

    expect(screen.getByRole("button", { name: "Crear ticket" })).toBeDisabled();
  });

  it("muestra el error de validación del backend", async () => {
    renderNew({
      "POST /tickets": jsonResponse(
        { detail: [{ loc: ["body", "title"], msg: "String should have at least 3 characters" }] },
        422,
      ),
    });

    await completar();
    await userEvent.click(screen.getByRole("button", { name: "Crear ticket" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/at least 3 characters/i));
  });
});
