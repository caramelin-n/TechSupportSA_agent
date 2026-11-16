import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatPage from "./ChatPage";
import { jsonResponse, mockFetch } from "../test/setup";

function reply(overrides = {}) {
  return jsonResponse({
    reply: "respuesta del agente",
    conversation_id: "c1",
    pending_actions: [],
    ...overrides,
  });
}

async function enviar(texto) {
  await userEvent.type(screen.getByLabelText("Mensaje"), texto);
  await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
}

describe("ChatPage", () => {
  it("envía un mensaje y muestra la respuesta del agente", async () => {
    mockFetch({
      "POST /chat": reply({ reply: "Contame desde cuándo pasa." }),
    });

    render(<ChatPage />);
    await enviar("La impresora no anda");

    expect(screen.getByText("La impresora no anda")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Contame desde cuándo pasa.")).toBeInTheDocument(),
    );
  });

  it("muestra las acciones pendientes y las aprueba", async () => {
    mockFetch({
      "POST /chat": reply({
        reply: "Antes de seguir necesito que confirmes:",
        pending_actions: [
          {
            tool: "crear_ticket",
            args: { title: "Impresora" },
            description: "Crear el ticket «Impresora» (categoría Hardware, prioridad Alta)",
          },
        ],
      }),
      "POST /chat/c1/decision": reply({ reply: "Ticket creado: TCK-1014" }),
    });

    render(<ChatPage />);
    await enviar("Creá el ticket");

    await waitFor(() =>
      expect(screen.getByText(/Crear el ticket «Impresora»/)).toBeInTheDocument(),
    );
    // Con una acción pendiente no se puede seguir escribiendo.
    expect(screen.getByLabelText("Mensaje")).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Aprobar" }));

    await waitFor(() =>
      expect(screen.getByText("Ticket creado: TCK-1014")).toBeInTheDocument(),
    );
    expect(screen.getByLabelText("Mensaje")).not.toBeDisabled();
  });

  it("permite rechazar con un motivo", async () => {
    const { calls } = mockFetch({
      "POST /chat": reply({
        reply: "Confirmá:",
        pending_actions: [
          { tool: "crear_ticket", args: {}, description: "Crear el ticket «X»" },
        ],
      }),
      "POST /chat/c1/decision": reply({ reply: "Entendido, no lo creo." }),
    });

    render(<ChatPage />);
    await enviar("Creá el ticket");
    await waitFor(() => expect(screen.getByRole("button", { name: "Rechazar" })).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Rechazar" }));
    await userEvent.type(screen.getByLabelText("Motivo del rechazo (opcional)"), "no era");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar rechazo" }));

    await waitFor(() => expect(screen.getByText("Entendido, no lo creo.")).toBeInTheDocument());
    const decisionCall = calls.find((c) => c.path === "/chat/c1/decision");
    expect(JSON.parse(decisionCall.options.body)).toEqual({
      decision: "reject",
      message: "no era",
    });
  });

  it("muestra el detalle de un 503 (cuota agotada)", async () => {
    mockFetch({
      "POST /chat": jsonResponse(
        { detail: "Cuota del modelo agotada. Cambiá LLM_MODEL en .env." },
        503,
      ),
    });

    render(<ChatPage />);
    await enviar("Hola");

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/cuota del modelo/i));
  });

  it("sube un adjunto y lo manda en upload_ids", async () => {
    const { calls } = mockFetch({
      "POST /chat/upload": jsonResponse(
        [{ id: 7, filename: "captura.png", kind: "imagen", size_bytes: 10 }],
        201,
      ),
      "POST /chat": reply({ reply: "Recibí la captura." }),
    });

    render(<ChatPage />);

    const file = new File(["contenido"], "captura.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText("Adjuntar archivos"), {
      target: { files: [file] },
    });

    await waitFor(() => expect(screen.getByText("captura.png")).toBeInTheDocument());

    await enviar("Mirá esta captura");
    await waitFor(() => expect(screen.getByText("Recibí la captura.")).toBeInTheDocument());

    const chatCall = calls.find((c) => c.path === "/chat");
    expect(JSON.parse(chatCall.options.body).upload_ids).toEqual([7]);
    // Tras enviar, los chips se limpian.
    expect(screen.queryByText("captura.png")).not.toBeInTheDocument();
  });

  it("rechaza más de 5 archivos sin llamar al backend", async () => {
    const { calls } = mockFetch({});
    render(<ChatPage />);

    const files = Array.from(
      { length: 6 },
      (_, i) => new File(["x"], `captura-${i}.png`, { type: "image/png" }),
    );
    fireEvent.change(screen.getByLabelText("Adjuntar archivos"), {
      target: { files },
    });

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/hasta 5 archivos/i),
    );
    expect(calls).toHaveLength(0);
  });

  it("rechaza un formato no admitido", async () => {
    mockFetch({});
    render(<ChatPage />);

    const file = new File(["x"], "script.exe", { type: "application/octet-stream" });
    fireEvent.change(screen.getByLabelText("Adjuntar archivos"), {
      target: { files: [file] },
    });

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/formato no admitido/i),
    );
  });
});
