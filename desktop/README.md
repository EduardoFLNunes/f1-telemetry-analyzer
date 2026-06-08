# Automobilista Telemetria Desktop Shell

Phase 12.2 prepares the Electron shell to run with a packaged backend runner and
controlled autostart. It does not create the final Windows installer and does
not enable backend autostart by default.

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

## Electron Static With Controlled Autostart

Build the backend executable first:

```bash
powershell -ExecutionPolicy Bypass -File backend\packaging\build_backend.ps1
```

Then run:

```bash
cd desktop
npm run desktop:prod:autostart
```

This sets an explicit autostart flag. Electron checks `/api/health` first. If a
healthy backend is already online, it uses that backend and does not start or
stop another process. If the backend is offline, it searches for
`automobilista-backend.exe`, starts it, waits for health, captures logs, and
stops only the backend process tree it started.

## Runtime Config

The preload exposes `window.desktopRuntime` with:

- `apiBaseUrl`
- `wsUrl`
- `backendPort`
- `frontendDevPort`
- `udpOpponentsPort`
- `mode`
- `autostartEnabled`

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
- `AT_DESKTOP_AUTOSTART_BACKEND=true`: enable packaged backend autostart.
- `AT_DESKTOP_START_BACKEND=1`: enable guarded backend subprocess startup.
- `DESKTOP_AUTOSTART_BACKEND=true`: alternate guarded autostart flag.
- `AT_BACKEND_EXE_PATH`: explicit path to `automobilista-backend.exe`.
- `AT_BACKEND_USE_PYTHON_RUNNER=true`: use the Python runner instead of the exe.
- `AT_BACKEND_RUNNER=python`: alternate Python-runner selector.
- `AT_BACKEND_PYTHON`: Python executable used by the Python runner mode.
- `AT_BACKEND_RUNNER_PATH`: explicit path to `desktop_backend_runner.py`.
- `AT_BACKEND_REPO_ROOT`: runtime root for cache, recordings, and data files.
- `AT_BACKEND_COMMAND`: backend command for future local process startup.
- `AT_BACKEND_ARGS`: backend command arguments. JSON arrays are supported.
- `AT_UDP_OPPONENTS_PORT`: UDP opponents port shown in diagnostics.

Backend autostart is intentionally disabled by default.

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

## Troubleshooting

- Port 8000 occupied: Electron reports `already-running` and avoids duplicate
  backend startup if `/api/health` is OK.
- Backend exe missing: build it with `backend\packaging\build_backend.ps1` or set
  `AT_BACKEND_EXE_PATH`.
- Health timeout: inspect `logs/desktop.log` and `logs/backend.log`.
- Static frontend missing: run `npm.cmd run build` from `frontend/`.
- Need Python runner for development: set `AT_BACKEND_RUNNER=python` or
  `AT_BACKEND_USE_PYTHON_RUNNER=true`.

## Still Planned

- Windows installer.
- Assetto Corsa plugin packaging/checks.
- Digital signing.
- Auto-update.
