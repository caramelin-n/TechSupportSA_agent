import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Dentro de Docker el backend se llama "backend"; "localhost" seria el
    // propio contenedor frontend. Para correr Vite fuera de Docker:
    // VITE_PROXY_TARGET=localhost npm run dev
    proxy: {
      "/api": `http://${process.env.VITE_PROXY_TARGET ?? "backend"}:8000`,
    },
  },
});
