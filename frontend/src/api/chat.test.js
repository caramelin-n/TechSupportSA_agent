import { beforeEach, describe, expect, it } from "vitest";
import { decide, sendMessage, uploadFiles } from "./chat";
import { setToken } from "../auth/storage";
import { jsonResponse, mockFetch } from "../test/setup";

beforeEach(() => {
  setToken("jwt-de-prueba");
});

describe("api/chat", () => {
  it("sendMessage manda mensaje, conversación y adjuntos", async () => {
    const { calls } = mockFetch({
      "POST /chat": jsonResponse({
        reply: "ok",
        conversation_id: "c1",
        pending_actions: [],
      }),
    });

    const data = await sendMessage({
      message: "hola",
      conversationId: "c1",
      uploadIds: [1, 2],
    });

    expect(data.reply).toBe("ok");
    expect(calls).toHaveLength(1);
    expect(calls[0].path).toBe("/chat");
    expect(JSON.parse(calls[0].options.body)).toEqual({
      message: "hola",
      conversation_id: "c1",
      upload_ids: [1, 2],
    });
    expect(calls[0].options.headers.Authorization).toBe("Bearer jwt-de-prueba");
  });

  it("sendMessage sin conversación manda conversation_id null", async () => {
    const { calls } = mockFetch({
      "POST /chat": jsonResponse({ reply: "ok", conversation_id: "nueva", pending_actions: [] }),
    });

    await sendMessage({ message: "primer mensaje" });

    expect(JSON.parse(calls[0].options.body)).toEqual({
      message: "primer mensaje",
      conversation_id: null,
      upload_ids: [],
    });
  });

  it("uploadFiles usa multipart y no fuerza Content-Type", async () => {
    const { calls } = mockFetch({
      "POST /chat/upload": jsonResponse(
        [{ id: 7, filename: "captura.png", kind: "imagen", size_bytes: 10 }],
        201,
      ),
    });

    const file = new File(["contenido"], "captura.png", { type: "image/png" });
    const data = await uploadFiles([file]);

    expect(data).toHaveLength(1);
    expect(calls[0].options.body).toBeInstanceOf(FormData);
    expect(calls[0].options.body.get("files")).toBe(file);
    expect(calls[0].options.headers["Content-Type"]).toBeUndefined();
    expect(calls[0].options.headers.Authorization).toBe("Bearer jwt-de-prueba");
  });

  it("decide manda la decisión y el motivo del rechazo", async () => {
    const { calls } = mockFetch({
      "POST /chat/c1/decision": jsonResponse({
        reply: "ok",
        conversation_id: "c1",
        pending_actions: [],
      }),
    });

    await decide("c1", "reject", "no era la misma incidencia");

    expect(calls[0].path).toBe("/chat/c1/decision");
    expect(JSON.parse(calls[0].options.body)).toEqual({
      decision: "reject",
      message: "no era la misma incidencia",
    });
  });

  it("expone el detail del 409 como mensaje", async () => {
    mockFetch({
      "POST /chat": jsonResponse(
        { detail: "Hay una acción esperando confirmación en esta conversación." },
        409,
      ),
    });

    await expect(sendMessage({ message: "otra cosa" })).rejects.toMatchObject({
      status: 409,
      message: "Hay una acción esperando confirmación en esta conversación.",
    });
  });
});
