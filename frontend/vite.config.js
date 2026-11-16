import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // Dentro de Docker el backend se llama "backend"; "localhost" sería el propio
  // contenedor frontend. Para `npm run dev` en el host: VITE_PROXY_TARGET=localhost
  const target = env.VITE_PROXY_TARGET || "backend";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      // El backend no sirve bajo /api: hay que cortar el prefijo, igual que
      // hace nginx.conf con `proxy_pass http://backend:8000/`.
      proxy: {
        "/api": {
          target: `http://${target}:8000`,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },
      },
    },
  };
});
