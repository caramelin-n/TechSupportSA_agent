import { describe, expect, it } from "vitest";
import { api, ApiError, request, setUnauthorizedHandler } from "./client";
import { clearToken, setToken } from "../auth/storage";
import { jsonResponse, mockFetch } from "../test/setup";

describe("cliente HTTP", () => {
  it("adjunta el header Authorization Bearer cuando hay token", async () => {
    setToken("jwt-de-prueba");
    const { calls } = mockFetch({ "GET /auth/me": jsonResponse({ id: "U001" }) });

    await api.get("/auth/me");

    expect(calls[0].options.headers.Authorization).toBe("Bearer jwt-de-prueba");
  });

  it("no adjunta Authorization cuando la request es pública", async () => {
    const { calls } = mockFetch({ "POST /auth/login": jsonResponse({ access_token: "x" }) });

    await api.post("/auth/login", { email: "a@b.com", password: "x" }, { auth: false });

    expect(calls[0].options.headers.Authorization).toBeUndefined();
  });

  it("lanza ApiError con mensaje en español ante 403", async () => {
    mockFetch({ "GET /tickets": jsonResponse({ detail: "Permisos insuficientes" }, 403) });

    await expect(api.get("/tickets")).rejects.toBeInstanceOf(ApiError);
    await expect(api.get("/tickets")).rejects.toThrow(/permisos/i);
  });

  it("aplana el detail 422 de FastAPI a un texto legible", async () => {
    mockFetch({
      "POST /auth/login": jsonResponse(
        { detail: [{ loc: ["body", "email"], msg: "value is not a valid email address" }] },
        422,
      ),
    });

    await expect(api.post("/auth/login", {}, { auth: false })).rejects.toThrow(/email/);
  });

  it("dispara onUnauthorized ante un 401", async () => {
    let disparado = false;
    setUnauthorizedHandler(() => {
      disparado = true;
    });
    mockFetch({ "GET /auth/me": jsonResponse({ detail: "Token inválido o expirado" }, 401) });

    await expect(api.get("/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(disparado).toBe(true);
  });

  it("no propaga el error de red como ApiError 0 sincrónico", async () => {
    mockFetch({ "*": () => Promise.reject(new TypeError("Failed to fetch")) });

    await expect(request("/health")).rejects.toMatchObject({ status: 0 });
  });

  it("limpia el token cuando la respuesta es 401 y dispara el handler", async () => {
    setToken("jwt-vencido");
    let disparado = false;
    setUnauthorizedHandler(() => {
      disparado = true;
    });
    mockFetch({ "GET /auth/me": jsonResponse({ detail: "expirado" }, 401) });

    await expect(api.get("/auth/me")).rejects.toThrow();
    expect(disparado).toBe(true);

    clearToken();
  });
});
