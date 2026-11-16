import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

/** Construye una Response JSON con el status dado. */
export function jsonResponse(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => (data === undefined ? "" : JSON.stringify(data)),
  };
}

/** Instala un fetch stub que responde por ruta y método. */
export function mockFetch(routes) {
  const calls = [];
  const fetchMock = vi.fn(async (url, options = {}) => {
    const path = String(url).replace(/^\/api/, "");
    const method = (options.method ?? "GET").toUpperCase();
    calls.push({ url, path, method, options });

    const key = `${method} ${path}`;
    const pathSinQuery = path.split("?")[0];
    const keySinQuery = `${method} ${pathSinQuery}`;
    const handler =
      routes[key] ??
      routes[path] ??
      routes[keySinQuery] ??
      routes[pathSinQuery] ??
      routes["*"];
    if (!handler) {
      return jsonResponse({ detail: `Sin mock para ${key}` }, 404);
    }
    return typeof handler === "function" ? handler({ path, method, options }) : handler;
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, calls };
}
