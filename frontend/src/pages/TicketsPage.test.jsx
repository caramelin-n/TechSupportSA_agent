import { describe, expect, it } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TicketsPage from "./TicketsPage";
import { jsonResponse } from "../test/setup";
import { queryOf, renderProtected, USUARIO } from "../test/helpers";

const TICKETS = [
  {
    id: "TCK-1001",
    created_at: "2026-10-28T10:00:00+00:00",
    requester_id: "U001",
    title: "Sistema de facturación no abre",
    description: "desc",
    category: "Sistemas y aplicaciones",
    priority: "Alta",
    status: "Abierto",
    assignee_id: null,
  },
  {
    id: "TCK-1004",
    created_at: "2026-10-29T10:00:00+00:00",
    requester_id: "U001",
    title: "Impresora del 2do piso no responde",
    description: "desc",
    category: "Hardware",
    priority: "Media",
    status: "Pendiente",
    assignee_id: "S001",
  },
];

function renderPage({ tickets = TICKETS, user = USUARIO } = {}) {
  return renderProtected({
    path: "/tickets",
    route: "/tickets",
    element: <TicketsPage />,
    user,
    mocks: {
      "GET /catalog/categories": jsonResponse([
        { name: "Hardware", description: null, examples: null },
        { name: "Sistemas y aplicaciones", description: null, examples: null },
      ]),
      "GET /tickets": jsonResponse(tickets),
      "GET /users": jsonResponse([]),
    },
  });
}

describe("TicketsPage", () => {
  it("lista los tickets con estado y prioridad", async () => {
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Sistema de facturación no abre")).toBeInTheDocument(),
    );
    expect(screen.getByText("Impresora del 2do piso no responde")).toBeInTheDocument();
    expect(screen.getByText("TCK-1001")).toBeInTheDocument();

    const fila = screen.getByText("TCK-1004").closest("tr");
    expect(within(fila).getByText("Pendiente")).toBeInTheDocument();
    expect(within(fila).getByText("Media")).toBeInTheDocument();
  });

  it("muestra el estado vacío", async () => {
    renderPage({ tickets: [] });

    await waitFor(() =>
      expect(screen.getByText(/no se encontraron tickets/i)).toBeInTheDocument(),
    );
  });

  it("al cambiar el filtro de estado vuelve a consultar desde la primera página", async () => {
    const { calls } = renderPage();

    await waitFor(() => expect(screen.getByText("TCK-1001")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText("Estado"), "En revisión");

    await waitFor(() => {
      const ultima = calls.filter((c) => c.path.startsWith("/tickets?")).at(-1);
      const query = queryOf(ultima.path);
      expect(query.get("status")).toBe("En revisión");
      expect(query.get("offset")).toBe("0");
    });
  });

  it("habilita Siguiente cuando hay más resultados", async () => {
    const muchos = Array.from({ length: 21 }, (_, i) => ({
      ...TICKETS[0],
      id: `TCK-${2000 + i}`,
      title: `Ticket ${i}`,
    }));

    renderPage({ tickets: muchos });

    await waitFor(() => expect(screen.getByText("Ticket 0")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
  });

  it("limpiar filtros restablece la consulta", async () => {
    const { calls } = renderPage();
    await waitFor(() => expect(screen.getByText("TCK-1001")).toBeInTheDocument());

    await userEvent.selectOptions(screen.getByLabelText("Prioridad"), "Alta");
    await waitFor(() => expect(screen.getByText("Limpiar filtros")).toBeInTheDocument());

    await userEvent.click(screen.getByText("Limpiar filtros"));

    await waitFor(() => {
      const ultima = calls.filter((c) => c.path.startsWith("/tickets?")).at(-1);
      expect(queryOf(ultima.path).has("priority")).toBe(false);
    });
  });
});
