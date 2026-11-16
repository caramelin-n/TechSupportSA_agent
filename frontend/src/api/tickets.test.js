import { beforeEach, describe, expect, it } from "vitest";
import {
  addComment,
  assignTicket,
  createTicket,
  getTicket,
  listTickets,
  updatePriority,
  updateStatus,
} from "./tickets";
import { setToken } from "../auth/storage";
import { jsonResponse, mockFetch } from "../test/setup";
import { queryOf } from "../test/helpers";

beforeEach(() => setToken("jwt-de-prueba"));

describe("api/tickets", () => {
  it("listTickets arma los filtros y la paginación", async () => {
    const { calls } = mockFetch({ "GET /tickets": jsonResponse([]) });

    await listTickets({
      status: "En revisión",
      priority: "Alta",
      category: "Hardware",
      unresolved: true,
      limit: 21,
      offset: 20,
    });

    const query = queryOf(calls[0].path);
    expect(query.get("status")).toBe("En revisión");
    expect(query.get("priority")).toBe("Alta");
    expect(query.get("category")).toBe("Hardware");
    expect(query.get("unresolved")).toBe("true");
    expect(query.get("limit")).toBe("21");
    expect(query.get("offset")).toBe("20");
    expect(calls[0].options.headers.Authorization).toBe("Bearer jwt-de-prueba");
  });

  it("listTickets omite los filtros vacíos", async () => {
    const { calls } = mockFetch({ "GET /tickets": jsonResponse([]) });

    await listTickets({ status: "", priority: "", category: "", unresolved: false });

    const query = queryOf(calls[0].path);
    expect(query.has("status")).toBe(false);
    expect(query.has("priority")).toBe(false);
    expect(query.has("category")).toBe(false);
    expect(query.has("unresolved")).toBe(false);
  });

  it("getTicket y createTicket", async () => {
    const { calls } = mockFetch({
      "GET /tickets/TCK-1001": jsonResponse({ id: "TCK-1001" }),
      "POST /tickets": jsonResponse({ id: "TCK-2000" }, 201),
    });

    expect((await getTicket("TCK-1001")).id).toBe("TCK-1001");
    const created = await createTicket({
      title: "Prueba",
      description: "Descripción suficiente",
      category: "Hardware",
      priority: "Media",
    });
    expect(created.id).toBe("TCK-2000");
    expect(JSON.parse(calls[1].options.body).category).toBe("Hardware");
  });

  it("las acciones usan los nombres de campo del backend", async () => {
    const { calls } = mockFetch({
      "PATCH /tickets/TCK-1001/status": jsonResponse({ id: "TCK-1001" }),
      "PATCH /tickets/TCK-1001/priority": jsonResponse({ id: "TCK-1001" }),
      "PATCH /tickets/TCK-1001/assignee": jsonResponse({ id: "TCK-1001" }),
      "POST /tickets/TCK-1001/comments": jsonResponse({ id: 1 }, 201),
    });

    await updateStatus("TCK-1001", "En revisión");
    await updatePriority("TCK-1001", "Alta");
    await assignTicket("TCK-1001", "S001");
    await addComment("TCK-1001", "Probé reiniciar");

    expect(JSON.parse(calls[0].options.body)).toEqual({ new_status: "En revisión" });
    expect(JSON.parse(calls[1].options.body)).toEqual({ priority: "Alta" });
    expect(JSON.parse(calls[2].options.body)).toEqual({ assignee_id: "S001" });
    expect(JSON.parse(calls[3].options.body)).toEqual({ text: "Probé reiniciar" });
  });
});
