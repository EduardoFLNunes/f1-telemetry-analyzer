# Phase 12 - Desktop Software Packaging Preparation

Branch: `feature/phase-12-desktop-packaging`

Baseline before Phase 12 changes:

- Branch: `feature/phase-12-desktop-packaging`
- Last commit: `96e233d1 feat: add line overlay comparison`
- Frontend build: `npm.cmd run build` from `frontend/` completed successfully.
- Backend tests: `.venv\Scripts\python.exe -m unittest discover -s backend\tests` completed successfully, 13 tests OK.
- Pre-existing untracked files were present and intentionally left out of this phase.

## Current Architecture

The current application is a local web app split into two services:

- Python/FastAPI backend in `backend/`.
- React/Vite frontend in `frontend/`.
- Assetto Corsa shared-memory telemetry is read by the backend.
- Opponents telemetry is sent by the Assetto Corsa Python exporter over UDP.
- Browser clients connect to the backend through REST endpoints and `/ws`.

### Current Startup

Frontend development:

```bash
cd frontend
npm.cmd run dev
```

Current Vite dev port:

```text
5173
```

Backend development:

```bash
cd backend
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The legacy helper scripts `run-frontend.bat`, `run-backend.bat`,
`run-frontend.sh`, and `run-backend.sh` still exist and should continue to work.

Current backend port:

```text
8000
```

### Important Endpoints

- `GET /api/health`
- `GET /api/runtime/status`
- `GET /api/live/telemetry`
- `GET /api/live/opponents`
- `GET /api/live/racing-line`
- `GET /api/live/coach`

Existing compatibility health endpoint:

- `GET /health`

WebSocket endpoint:

- `WS /ws`

### Opponents UDP Pipeline

The Assetto Corsa opponents exporter lives in:

```text
tools/assetto_opponents_exporter/ac_opponents_exporter.py
```

It sends JSON snapshots to:

```text
127.0.0.1:8765
```

The backend `OpponentsRuntime` receives that stream and exposes current state via
`/api/live/opponents` and websocket messages.

### Configuration

Frontend runtime configuration is centralized in:

```text
frontend/src/config/runtime.js
```

Supported frontend variables:

- `VITE_API_BASE_URL`
- `VITE_API_URL` for backward compatibility
- `VITE_WS_URL`

Backend/source variables currently observed:

- `TELEMETRY_SOURCE`
- `ALLOW_REPLAY_FALLBACK`
- `TELEMETRY_DEBUG_REPLAY`
- `DEBUG_ALLOW_TRAJECTORY_TRACK`

Desktop shell variables:

- `AT_DESKTOP_FRONTEND_URL`
- `AT_DESKTOP_MODE`
- `AT_BACKEND_URL`
- `AT_BACKEND_WS_URL`
- `AT_BACKEND_HEALTH_URL`
- `AT_DESKTOP_START_BACKEND`
- `DESKTOP_AUTOSTART_BACKEND`
- `AT_BACKEND_COMMAND`
- `AT_BACKEND_ARGS`
- `AT_UDP_OPPONENTS_PORT`

## Target Architecture

Initial target:

```text
Automobilista Telemetria Desktop App
  ├─ Electron desktop shell
  ├─ React/Vite frontend build
  ├─ FastAPI backend started as a local process
  ├─ Backend health check
  ├─ Runtime status endpoint
  ├─ Port configuration
  ├─ Local logs
  └─ Future Windows installer
```

The backend remains Python/FastAPI. The frontend remains React/Vite. The
Assetto Corsa exporter remains a separate integration.

## Phase 12 Scope

Implemented in this preparation phase:

- Created minimal `desktop/` Electron shell.
- Added backend health endpoint `/api/health`.
- Added lightweight runtime endpoint `/api/runtime/status`.
- Centralized frontend API and websocket URL configuration.
- Documented desktop packaging architecture, risks, and migration steps.

Not implemented in Phase 12:

- PyInstaller backend bundle.
- Windows installer.
- Assetto Corsa exporter packaging/copy validation.
- Auto-update.
- Digital signing.
- Visual port configuration.

## Electron Shell

Desktop structure:

```text
desktop/
  package.json
  main.js
  preload.js
  scripts/start.js
  README.md
```

Development mode loads:

```text
http://127.0.0.1:5173
```

Production mode is prepared to load:

```text
frontend/dist/index.html
```

Backend autostart is disabled by default. `desktop/main.js` checks
`/api/health`, logs port/health failures, and only starts a configured backend
process when an explicit autostart flag is enabled.

## Phase 12.1 Status

Phase 12.1 extends the desktop preparation with static frontend validation,
runtime diagnostics, and backend packaging notes.

### Test Count Investigation

The canonical backend test command is:

```bash
.venv\Scripts\python.exe -m unittest discover -s backend\tests
```

The equivalent command from `backend/` is:

```bash
..\.venv\Scripts\python.exe -m unittest discover -s tests
```

Both commands discover the same 13 tests in:

```text
backend/tests/test_recording.py
backend/tests/test_opponents.py
backend/tests/test_ideal_line_overlay.py
```

Additional files found by a broad search are manual or legacy scripts outside
the canonical test suite:

```text
backend/stress_test.py
backend/test_ws_client.py
backend/test_api_comparison.py
backup/testes/testemain.py
backup/testes/teste.py
```

No import failure was observed during discovery. The current count is 13 because
only `backend/tests` contains unittest-discoverable automated tests. Earlier
counts of 34/49 likely came from a different phase, command, or suite layout.

### Frontend Static Runtime

The frontend runtime config now resolves API and websocket URLs in this order:

1. Vite env vars such as `VITE_API_BASE_URL`, `VITE_API_URL`, and `VITE_WS_URL`.
2. `window.desktopRuntime` from the Electron preload.
3. Local defaults on `127.0.0.1:8000`.

This keeps browser/Vite development working while allowing the static
`frontend/dist` bundle to run from Electron.

### Desktop Scripts

```bash
cd desktop
npm run desktop:dev
```

Loads the Vite dev server.

```bash
cd desktop
npm run desktop:prod
```

Sets `AT_DESKTOP_MODE=production` and loads `frontend/dist/index.html`.

### Runtime Diagnostics

The dashboard includes a compact runtime panel. It polls only
`/api/runtime/status` every 5 seconds and reports:

- Backend online/offline.
- API URL.
- Health OK/error.
- Telemetry waiting/receiving.
- Opponents waiting/receiving.
- Racing Line READY/INSUFFICIENT_DATA.
- Coach READY/INSUFFICIENT_DATA.
- Ports 8000, 5173, and UDP 8765.

### Backend Packaging Prep

Packaging notes live in:

```text
backend/packaging/README.md
```

PyInstaller has not been run in Phase 12.1. The next phase should create a
dedicated production runner with `reload=False`, then validate hidden imports,
native dependencies, logs, writable cache paths, and Electron autostart.

## Build Commands

Frontend production build:

```bash
cd frontend
npm.cmd run build
```

Backend tests:

```bash
.venv\Scripts\python.exe -m unittest discover -s backend\tests
```

Desktop development, after installing desktop dependencies:

```bash
cd desktop
npm install
npm run desktop:dev
```

Desktop static production smoke:

```bash
cd frontend
npm.cmd run build
```

```bash
cd desktop
npm run desktop:prod
```

## Logs Plan

Future desktop logs should be written to:

```text
logs/backend.log
logs/desktop.log
```

This directory is runtime output and should not be committed.

## Risks

- Backend subprocess packaging needs careful handling of Python dependencies,
  native libraries, and Assetto Corsa shared-memory access.
- Port conflicts on `8000`, `5173`, and UDP `8765` need a diagnostic screen or
  explicit recovery path.
- Loading frontend assets from `file://` may expose assumptions that only work
  behind Vite. Phase 12 keeps dev and production paths separate.
- The Assetto Corsa exporter still targets UDP `127.0.0.1:8765`; changing that
  later will require exporter-side configuration.
- Large runtime caches, recordings, and logs must stay outside packaged app
  resources.

## Rollback Plan

Phase 12 is incremental. To rollback:

1. Keep using the existing backend/frontend terminal flow.
2. Remove or ignore `desktop/`.
3. Revert the frontend runtime config import if needed.
4. Keep `/health`; ignore `/api/health` and `/api/runtime/status` if unused.

No telemetry, racing line, race coach, opponents, or recording logic is removed
by this phase.

## Migration Steps

1. Keep frontend/backend terminal startup as the source of truth.
2. Use the Electron shell only as a wrapper around the dev server.
3. Validate `frontend/dist` static loading in production mode.
4. Package backend with PyInstaller in a later phase.
5. Replace the backend command stub with the packaged executable path.
6. Add port conflict detection and a diagnostics view.
7. Add installer flow and Assetto Corsa exporter checks.

## Recommended Phase 12.2

- Create and validate a PyInstaller runner for the backend.
- Replace the command stub with the packaged executable path.
- Expand port probing and user-facing recovery for conflicts.
- Add installer planning without packaging the Assetto Corsa exporter yet.
- Define runtime config file location for user-selected ports and paths.
