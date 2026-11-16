# Frontend — TechSupport S.A.

> Documento de **explicación** (Diátaxis): describe cómo está armado el frontend, por qué se tomaron ciertas decisiones y qué queda pendiente. La referencia de la API está en `/docs` de FastAPI.

## 1. Visión general

El frontend es una **SPA React** que consume la API REST del backend. Cubre el
**ciclo de autenticación completo** y la **pantalla de chat con el agente**:

- Login con email y contraseña contra `POST /auth/login`.
- Persistencia de la sesión (JWT en `localStorage`).
- Validación de la sesión al cargar la app (`GET /auth/me`).
- Rutas protegidas.
- Layout con identidad del usuario y su rol.
- Cierre de sesión.
- **Chat con el agente**: texto, adjuntos (PNG/JPG/WEBP/TXT/LOG) y confirmación
  de acciones (aprobar/rechazar).

**Pendiente:** UI de tickets (listado, detalle, filtros, creación) y E2E con Playwright.

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
│   ├── client.js      # wrapper de fetch: Bearer automático, JSON y multipart
│   ├── auth.js        # login() y me()
│   ├── chat.js        # sendMessage(), uploadFiles(), decide()
│   └── config.js      # API_BASE (VITE_API_BASE)
├── auth/
│   ├── AuthContext.jsx # estado de sesión + bootstrap
│   └── storage.js      # getToken/setToken/clearToken (localStorage)
├── chat/
│   ├── useChat.js      # mensajes, conversación, pendientes, adjuntos
│   └── constants.js    # límites, tipos aceptados, sugerencias
├── components/
│   ├── AppLayout.jsx   # navbar con usuario, rol y logout
│   ├── RequireAuth.jsx # guarda de rutas privadas
│   ├── MessageList.jsx / MessageBubble.jsx
│   ├── Composer.jsx    # texto + adjuntos + enviar
│   ├── AttachmentChips.jsx
│   └── PendingActions.jsx
├── pages/
│   ├── LoginPage.jsx
│   ├── ChatPage.jsx    # pantalla principal
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

## 5.1 Chat con el agente

`ChatPage` monta el hook `useChat`, que concentra todo el estado:

- `messages`: historial en memoria (el backend no expone el historial de la
  conversación, solo el de cada ticket).
- `conversationId`: se guarda en `sessionStorage`
  (`techsupport.conversation`) y se limpia en `logout()`. Si falta, el backend
  genera uno y lo devuelve.
- `pending`: acciones que el agente quiere ejecutar y esperan confirmación.
- `attachments`: adjuntos ya subidos (`upload_ids`) que se mandan con el
  próximo mensaje.

**Flujo de un mensaje:** `POST /chat` con `{message, conversation_id, upload_ids}`.
La respuesta trae `{reply, conversation_id, pending_actions}`. Si
`pending_actions` no está vacío, la acción **no se ejecutó**: la UI muestra la
tarjeta con **Aprobar / Rechazar** y bloquea el composer, porque el backend
responde **409** a cualquier mensaje nuevo mientras haya una pendiente. La
decisión va a `POST /chat/{conversation_id}/decision`.

**Adjuntos (F02):** se suben al seleccionarlos con `POST /chat/upload`
(multipart, campo `files`, hasta 5 archivos de 5 MB). La UI valida extensión y
tamaño antes de llamar y muestra chips con el `kind` que detectó el backend
(`imagen`, `txt`, `log`). Un adjunto subido que no se envía queda huérfano hasta
el próximo `seed.py`; no hay endpoint de borrado.

**Errores:** el banner muestra el `detail` del backend. Los 503 de cuota o
modelo se muestran tal cual (son accionables); un 409 no debería ocurrir porque
el composer está bloqueado, pero se maneja igual.

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

28 tests, todos sin red: `fetch` está mockeado con `vi.stubGlobal`.

| Archivo | Qué cubre |
|---|---|
| `src/api/client.test.js` | Header Bearer, errores 401/403/422, `onUnauthorized`, error de red. |
| `src/api/chat.test.js` | `sendMessage`, `uploadFiles` (multipart sin `Content-Type`), `decide`, 409. |
| `src/auth/AuthContext.test.jsx` | Bootstrap con token válido/inválido, login, `RequireAuth`. |
| `src/pages/LoginPage.test.jsx` | Login exitoso, 401, acceso rápido de la demo. |
| `src/pages/ChatPage.test.jsx` | Enviar mensaje, confirmar/rechazar, 503, adjuntos, límites de archivos. |

Helpers en `src/test/setup.js`: `jsonResponse(data, status)` y
`mockFetch(routes)`, que enrutan por `"MÉTODO /ruta"`.

## 8. Gotchas

- **`npm ci` en el Dockerfile**: si se agrega una dependencia hay que commitear
  `package-lock.json` actualizado, si no la imagen falla el build.
- **Multipart sin `Content-Type`**: `requestForm` no lo setea a propósito; el
  navegador agrega el boundary. Forzar `application/json` rompe `/chat/upload`.
- **Con acción pendiente no se puede escribir**: el backend responde 409, por eso
  el composer se deshabilita mientras `pending_actions` no esté vacío.
- **`conversation_id` en `sessionStorage`**: sin reusarlo, el agente pierde el
  hilo entre mensajes. Se limpia en `logout()`.
- **`vite.config.js` y `vitest.config.js` son separados**: Vitest no lee el
  `test` del config de Vite. Si se unifican, cuidado con la config del proxy.
- **`node:22-alpine`** en la imagen: Vitest 5 pide Node `^22.12 || ^24 || >=26`.
- **Los tests del backend corren el seed al inicio**: borran los datos creados a
  mano (el índice de `ticket_embeddings` sí se preserva). Si necesitás datos
  canónicos, `docker compose exec backend python seed.py`.
- **La sesión vive en `localStorage`**: un XSS podría leer el token. Para
  producción, la alternativa es cookie `httpOnly` (implica cambiar el backend a
  cookies y agregar manejo de CSRF).
- **El rol viene de `/auth/me`**, nunca del login. Si el backend cambiara el
  contrato, el punto a tocar es `src/api/auth.js`.

## 9. Próximos pasos

1. **UI de tickets**: listado con filtros por estado/categoría/prioridad,
   detalle con historial y comentarios, alta de ticket con adjuntos.
2. **E2E**: Playwright para cubrir login + chat + confirmación contra el backend
   real.
3. **Streaming** de la respuesta del agente (hoy se espera la respuesta completa).
