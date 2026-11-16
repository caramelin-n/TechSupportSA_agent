import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TicketDetailPage from "./TicketDetailPage";
import { jsonResponse } from "../test/setup";
import { renderProtected, USUARIO } from "../test/helpers";

const TICKET = {
  id: "TCK-1001",
  created_at: "2026-10-28T10:00:00+00:00",
  requester_id: "U001",
  title: "Sistema de facturación no abre",
  description: "Cuando intento abrir el sistema queda la pantalla en blanco.",
  category: "Sistemas y aplicaciones",
  priority: "Alta",
  status: "Abierto",
  assignee_id: null,
};

const HISTORY = [
  {
    id: 1,
    ticket_id: "TCK-1001",
    event_type: "CREATED",
    old_value: null,
    new_value: "Abierto",
    actor_id: "U001",
    timestamp: "2026-10-28T10:00:00+00:00",
  },
];

function renderDetail({ user = USUARIO, ticket = TICKET, extraMocks = {} } = {}) {
  return renderProtected({
    path: "/tickets/:ticketId",
    route: `/tickets/${ticket.id}`,
    element: <TicketDetailPage />,
    user,
    mocks: {
      "GET /users": jsonResponse([]),
      [`GET /tickets/${ticket.id}`]: jsonResponse(ticket),
      [`GET /tickets/${ticket.id}/history`]: jsonResponse(HISTORY),
      ...extraMocks,
    },
  });
}

describe("TicketDetailPage", () => {
  it("muestra los datos y el historial", async () => {
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Sistema de facturación no abre")).toBeInTheDocument(),
    );
    expect(screen.getByText("Sistemas y aplicaciones")).toBeInTheDocument();
    expect(screen.getByText("Alta")).toBeInTheDocument();
    expect(screen.getByText(/Creado en estado «Abierto»/)).toBeInTheDocument();
  });

  it("un usuario no ve acciones de estado ni prioridad", async () => {
    renderDetail();

    await waitFor(() =>
      expect(screen.getByText("Sistema de facturación no abre")).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Cambiar estado/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Prioridad$/)).not.toBeInTheDocument();
  });

  it("un admin puede cambiar el estado", async () => {
    const { calls } = renderDetail({
      user: { ...USUARIO, id: "A001", role: "admin", name: "Raúl" },
      extraMocks: {
        "PATCH /tickets/TCK-1001/status": jsonResponse({ ...TICKET, status: "En revisión" }),
      },
    });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Pasar a «En revisión»/ })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /Pasar a «En revisión»/ }));

    await waitFor(() => {
      const call = calls.find((c) => c.path === "/tickets/TCK-1001/status");
      expect(JSON.parse(call.options.body)).toEqual({ new_status: "En revisión" });
    });
  });

  it("permite comentar y limpia el campo", async () => {
    const { calls } = renderDetail({
      extraMocks: {
        "POST /tickets/TCK-1001/comments": jsonResponse({ id: 9 }, 201),
      },
    });

    await waitFor(() =>
      expect(screen.getByLabelText("Agregar comentario")).toBeInTheDocument(),
    );

    await userEvent.type(screen.getByLabelText("Agregar comentario"), "Probé reiniciar");
    await userEvent.click(screen.getByRole("button", { name: "Comentar" }));

    await waitFor(() => {
      const call = calls.find((c) => c.path === "/tickets/TCK-1001/comments");
      expect(JSON.parse(call.options.body)).toEqual({ text: "Probé reiniciar" });
    });
    await waitFor(() => expect(screen.getByLabelText("Agregar comentario")).toHaveValue(""));
  });

  it("muestra el error del backend al fallar una acción", async () => {
    renderDetail({
      user: { ...USUARIO, id: "A001", role: "admin", name: "Raúl" },
      extraMocks: {
        "PATCH /tickets/TCK-1001/status": jsonResponse(
          { detail: "Transición inválida: Abierto -> Cerrado" },
          409,
        ),
      },
    });

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Pasar a «En revisión»/ })).toBeInTheDocument(),
    );
    await userEvent.click(screen.getByRole("button", { name: /Pasar a «En revisión»/ }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/transición inválida/i),
    );
  });
});
