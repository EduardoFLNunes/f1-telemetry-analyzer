# Automobilista Telemetria Desktop Shell

Phase 12.1 prepares the Electron shell for both development and static frontend
loading. It does not create the final Windows installer and does not enable
backend autostart by default.

## Current Terminal Flow

Backend:

```bash
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm.cmd run dev
```

## Electron Development

Development mode loads the Vite dev server at `http://127.0.0.1:5173`.

```bash
cd desktop
npm install
npm run desktop:dev
```

## Electron Static Production Smoke

Build the frontend first:

```bash
cd frontend
npm.cmd run build
```

Then run Electron against `frontend/dist/index.html`:

```bash
cd desktop
npm run desktop:prod
```

The static frontend still talks to the local backend through the runtime config
exposed by the preload script.

## Runtime Config

The preload exposes `window.desktopRuntime` with:

- `apiBaseUrl`
- `wsUrl`
- `backendPort`
- `frontendDevPort`
- `udpOpponentsPort`
- `mode`

The frontend also continues to support:

- `VITE_API_BASE_URL`
- `VITE_API_URL`
- `VITE_WS_URL`

## Environment

- `AT_DESKTOP_FRONTEND_URL`: frontend URL loaded by Electron in development.
- `AT_DESKTOP_MODE=production`: load `frontend/dist/index.html` when present.
- `AT_BACKEND_URL`: backend base URL for health checks and frontend runtime.
- `AT_BACKEND_WS_URL`: explicit websocket URL for desktop runtime.
- `AT_BACKEND_HEALTH_URL`: explicit backend health URL.
- `AT_DESKTOP_START_BACKEND=1`: enable guarded backend subprocess startup.
- `DESKTOP_AUTOSTART_BACKEND=true`: alternate guarded autostart flag.
- `AT_BACKEND_COMMAND`: backend command for future local process startup.
- `AT_BACKEND_ARGS`: backend command arguments. JSON arrays are supported.
- `AT_UDP_OPPONENTS_PORT`: UDP opponents port shown in diagnostics.

Backend autostart is intentionally disabled by default. If enabled explicitly,
the shell checks `/api/health`, starts the configured command only when needed,
waits for health, writes logs, and stops the child process on app quit.

## Health Validation

```http
GET /api/health
GET /api/runtime/status
```

## Logs

The shell writes runtime logs to:

```text
logs/desktop.log
logs/backend.log
```

The `logs/` directory is runtime output and should not be committed.

## Still Planned

- Real PyInstaller backend executable.
- Backend autostart using the packaged executable.
- Windows installer.
- Assetto Corsa plugin packaging/checks.
- Digital signing.
- Auto-update.
