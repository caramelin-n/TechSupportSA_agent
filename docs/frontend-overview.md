# Frontend — TechSupport S.A.

> Documento de **explicación** (Diátaxis): describe cómo está armado el frontend, por qué se tomaron ciertas decisiones y qué queda pendiente. La referencia de la API está en `/docs` de FastAPI.

## 1. Visión general

El frontend es una **SPA React** que consume la API REST del backend. Hoy cubre el **ciclo de autenticación completo**:

- Login con email y contraseña contra `POST /auth/login`.
- Persistencia de la sesión (JWT en `localStorage`).
- Validación de la sesión al cargar la app (`GET /auth/me`).
- Rutas protegidas.
- Layout con identidad del usuario y su rol.
- Cierre de sesión.

**Pendiente:** UI de tickets (listado, detalle, filtros, creación), subida de adjuntos y el chat con el agente. El endpoint `/chat` ya existe en el backend (con confirmaciones y adjuntos); falta la pantalla.

## 2. Stack

| Pieza | Elección | Motivo |
|---|---|---|
| Framework | React 19 | Es lo que ya estaba; sin motivo para cambiar. |
| Bundler | Vite 7 | Dev server rápido con proxy a la API. |
| Estilos | Tailwind 4 | Ya configurado vía `@tailwindcss/vite`. |
| Rutas | `react-router-dom` 7 | Rutas reales, botón atrás y links compartibles. |
| Tests | Vitest 5 + Testing Library + jsdom | Se integra con Vite sin configuración extra. |
| Build | `vite build` → `dist/` | Servido por nginx en la imagen de Docker. |

Sin gestor de estado global: `Context` + hooks de React alcanzan para la sesión. Si la UI de tickets necesita estado compartido más rico, se puede sumar Zustand, pero hoy sería sobre-ingeniería.

## 3. Estructura

```
frontend/src/
├── api/
│   ├── client.js      # wrapper de fetch: Bearer automático, errores normalizados
│   ├── auth.js        # login() y me()
│   └── config.js      # API_BASE (VITE_API_BASE)
├── auth/
│   ├── AuthContext.jsx # estado de sesión + bootstrap
│   └── storage.js      # getToken/setToken/clearToken (localStorage)
├── components/
│   ├── AppLayout.jsx   # navbar con usuario, rol y logout
│   └── RequireAuth.jsx # guarda de rutas privadas
├── pages/
│   ├── LoginPage.jsx
│   ├── DashboardPage.jsx  # placeholder
│   └── NotFoundPage.jsx
└── test/setup.js      # mocks de fetch y helpers
```

## 4. Flujo de autenticación

1. `LoginPage` hace `POST /auth/login` con `{email, password}`.
2. La respuesta es `{access_token, token_type}`: **no incluye el usuario**.
3. `AuthContext.login()` guarda el token y llama a `GET /auth/me` para obtener
   `{id, name, email, role, area}`.
4. `RequireAuth` habilita las rutas privadas; si no hay sesión, redirige a
   `/login` guardando la ruta origen en `state.from` para volver a ella.
5. Al cargar la app, `bootstrap()` lee el token de `localStorage` y lo valida
   contra `/auth/me`:
   - `200` → `authenticated`.
   - `401` → borra el token y queda `anonymous`.

**El backend no tiene refresh token** (`ACCESS_TOKEN_EXPIRE_MINUTES=60` por
defecto). Un `401` implica re-loguear, no refrescar. El cliente HTTP tiene un
handler global `onUnauthorized` que limpia la sesión ante cualquier `401`, así
que la expiración se maneja sin lógica duplicada en cada pantalla.

## 5. Cliente HTTP

`src/api/client.js` centraliza todo el acceso a la API:

- Header `Authorization: Bearer <token>` automático (opt-out con `auth: false`).
- Errores de FastAPI normalizados a un mensaje en español:
  `401` credenciales/sesión · `403` permisos · `404` no encontrado ·
  `409` conflicto · `422` validación (aplana el `detail` array por campo) ·
  `5xx` error del servidor.
- `ApiError` con `status` y `message`, listo para pintar.
- `onUnauthorized` global para limpiar la sesión.

## 6. Proxy y despliegue

| Entorno | Cómo llega `/api/...` al backend |
|---|---|
| Dev (`npm run dev`) | Proxy de Vite con `rewrite` que corta el prefijo `/api`. |
| Docker | `nginx.conf` con `proxy_pass http://backend:8000/` (la barra final corta el prefijo). |

**Por qué importa:** el backend **no** sirve bajo `/api`. Sin el `rewrite` del
proxy, `/api/health` llegaba al backend como `/api/health` y respondía `404` en
modo dev, mientras que en Docker funcionaba. Ambos caminos deben comportarse
igual; por eso el `rewrite` explícito.

**Nunca** hacer `fetch` directo a `http://localhost:8000` desde el browser: el
backend no tiene CORS y el prefijo `/api` es lo que enruta al servicio
correcto.

## 7. Tests

```bash
cd frontend
npm test          # vitest run
npm run test:watch
```

16 tests, todos sin red: `fetch` está mockeado con `vi.stubGlobal`.

| Archivo | Qué cubre |
|---|---|
| `src/api/client.test.js` | Header Bearer, errores 401/403/422, `onUnauthorized`, error de red. |
| `src/auth/AuthContext.test.jsx` | Bootstrap con token válido/inválido, login, `RequireAuth`. |
| `src/pages/LoginPage.test.jsx` | Login exitoso, 401, acceso rápido de la demo. |

Helpers en `src/test/setup.js`: `jsonResponse(data, status)` y
`mockFetch(routes)`, que enrutan por `"MÉTODO /ruta"`.

## 8. Gotchas

- **`npm ci` en el Dockerfile**: si se agrega una dependencia hay que commitear
  `package-lock.json` actualizado, si no la imagen falla el build.
- **`vite.config.js` y `vitest.config.js` son separados**: Vitest no lee el
  `test` del config de Vite. Si se unifican, cuidado con la config del proxy.
- **`node:22-alpine`** en la imagen: Vitest 5 pide Node `^22.12 || ^24 || >=26`.
- **Los tests del backend borran la base**: `backend/tests/conftest.py` tiene un
  fixture `autouse` que corre el seed en cada sesión. Después de correrlos hay
  que volver a ejecutar `docker compose exec backend python seed.py`.
- **La sesión vive en `localStorage`**: un XSS podría leer el token. Para
  producción, la alternativa es cookie `httpOnly` (implica cambiar el backend a
  cookies y agregar manejo de CSRF).
- **El rol viene de `/auth/me`**, nunca del login. Si el backend cambiara el
  contrato, el punto a tocar es `src/api/auth.js`.

## 9. Próximos pasos

1. **UI de tickets**: listado con filtros por estado/categoría/prioridad,
   detalle con historial y comentarios, alta de ticket con adjuntos.
2. **Chat con el agente**: el endpoint `/chat` ya está en el backend (con
   confirmación de acciones y adjuntos); falta la pantalla que lo consuma.
3. **Subida de adjuntos**: `nginx.conf` ya permite `client_max_body_size 20m`.
4. **E2E**: Playwright para cubrir el flujo completo contra el backend real.
