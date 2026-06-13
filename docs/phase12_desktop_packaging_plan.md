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
- `AT_DESKTOP_AUTOSTART_BACKEND`
- `AT_DESKTOP_START_BACKEND`
- `DESKTOP_AUTOSTART_BACKEND`
- `AT_BACKEND_EXE_PATH`
- `AT_BACKEND_USE_PYTHON_RUNNER`
- `AT_BACKEND_RUNNER`
- `AT_BACKEND_PYTHON`
- `AT_BACKEND_RUNNER_PATH`
- `AT_BACKEND_RESOURCE_ROOT`
- `AT_BACKEND_RUNTIME_ROOT`
- `AT_BACKEND_REPO_ROOT`
- `AT_DESKTOP_DISABLE_BACKEND_AUTOSTART`
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

Still outside the completed Phase 12.3 scope:

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

## Phase 12.2 Status

Phase 12.2 adds a real packaged backend runner and controlled Electron
autostart.

### Backend Runner

Created:

```text
backend/desktop_backend_runner.py
```

The runner imports the existing FastAPI app and starts Uvicorn
programmatically. It supports:

- `AT_BACKEND_HOST`, default `127.0.0.1`.
- `AT_BACKEND_PORT`, default `8000`.
- `AT_BACKEND_LOG_LEVEL`, default `info`.
- `AT_BACKEND_REPO_ROOT`, used for cache, recordings, and data paths.

`backend/main.py` now resolves `REPO_ROOT` from `AT_BACKEND_REPO_ROOT` when
present. This prevents PyInstaller onefile runs from writing runtime data under
the temporary extraction directory.

### PyInstaller Build

Created:

```text
backend/packaging/build_backend.ps1
```

Build command:

```bash
powershell -ExecutionPolicy Bypass -File backend\packaging\build_backend.ps1
```

Generated executable:

```text
backend/dist/automobilista-backend.exe
```

The executable was validated against:

- `GET /api/health`
- `GET /api/runtime/status`
- `GET /api/live/telemetry`
- `GET /api/live/opponents`
- `GET /api/live/racing-line`
- `GET /api/live/coach`

PyInstaller currently emits warnings about optional test modules from pandas
and pyarrow hooks. The executable still runs; Phase 12.3 should trim hook
collection and package size.

### Controlled Autostart

Added:

```bash
cd desktop
npm run desktop:prod:autostart
```

Behavior:

1. Electron checks `/api/health`.
2. If backend is already online, Electron records `already-running`, does not
   start another backend, and does not stop the existing backend on close.
3. If backend is offline and autostart is enabled, Electron locates:

```text
backend/dist/automobilista-backend.exe
```

or a path from `AT_BACKEND_EXE_PATH`, starts it, captures stdout/stderr, waits
for health, and stops only the process tree it started.

Python runner autostart is available for development by setting:

```text
AT_BACKEND_RUNNER=python
```

or:

```text
AT_BACKEND_USE_PYTHON_RUNNER=true
```

### Runtime Diagnostics

The dashboard runtime panel now also reports:

- Backend source: `already-running`, `packaged-exe`, `python-runner`,
  `custom-command`, or `unavailable`.
- Autostart enabled/disabled.
- Whether the backend was started by Electron.
- Backend executable/runner path when available.
- Last backend error when present.

## Phase 12.3 Status

Phase 12.3 adds Electron Builder packaging and proves that the unpacked app can
run from copied resources instead of the repository structure.

### Electron Builder

Added desktop scripts:

```bash
cd desktop
npm run pack
npm run dist:win
```

`npm run pack` creates:

```text
desktop/dist/win-unpacked/
```

`npm run dist:win` creates:

```text
desktop/dist/Automobilista Telemetria Setup 0.1.0-phase-12.exe
```

The build copies:

- `backend/dist/automobilista-backend.exe` to
  `resources/backend/automobilista-backend.exe`.
- `frontend/dist` to `resources/frontend`.
- Fixture CSV files to `resources/data`.

### Packaged Runtime Paths

When `app.isPackaged` is true, Electron starts the bundled backend by default
unless `AT_DESKTOP_DISABLE_BACKEND_AUTOSTART=true` is set.

Backend executable lookup order:

1. `AT_BACKEND_EXE_PATH`.
2. `process.resourcesPath\backend\automobilista-backend.exe`.
3. Repository fallback for development.

Frontend static lookup order:

1. `process.resourcesPath\frontend\index.html`.
2. Repository fallback `frontend\dist\index.html`.

Electron passes:

```text
AT_BACKEND_RESOURCE_ROOT=<process.resourcesPath>
AT_BACKEND_RUNTIME_ROOT=<app.getPath("userData")>
```

The backend reads fixtures from `RESOURCE_ROOT` and writes cache/recordings to
`RUNTIME_ROOT`.

Packaged logs are written under:

```text
%APPDATA%\Automobilista Telemetria\logs\
```

### Validation Result

Baseline validation:

- `npm.cmd run build` from `frontend/`: passed.
- `.venv\Scripts\python.exe -m unittest discover -s backend\tests`: 13 tests OK.
- `backend\packaging\build_backend.ps1`: regenerated the backend executable.

Packaged resource validation:

- `npm run pack`: passed.
- `npm run dist:win`: passed.
- Repository `backend/dist/automobilista-backend.exe` was temporarily hidden.
- Repository `frontend/dist` was temporarily hidden.
- `desktop/dist/win-unpacked/Automobilista Telemetria.exe` still started the
  backend and returned OK from `/api/health`.
- `/api/runtime/status` reported `backend.resourceRoot` as
  `desktop/dist/win-unpacked/resources`.
- `/api/runtime/status` reported `backend.runtimeRoot` under
  `%APPDATA%\Automobilista Telemetria`.
- Desktop log confirmed the frontend loaded from
  `desktop/dist/win-unpacked/resources/frontend/index.html`.

## Phase 12.4 Status

Phase 12.4 validates the NSIS installer as real installed software and improves
runtime recovery when the backend, port, health check, or packaged executable is
not healthy.

### Installer Validation

Installer path:

```text
desktop/dist/Automobilista Telemetria Setup 0.1.0-phase-12.exe
```

Silent install command used for validation:

```bash
desktop\dist\Automobilista Telemetria Setup 0.1.0-phase-12.exe /S
```

Installed app path:

```text
%LOCALAPPDATA%\Programs\Automobilista Telemetria\Automobilista Telemetria.exe
```

The installed app was opened with repository `frontend/dist` and `backend/dist`
temporarily renamed. It still loaded and reported:

```text
resourceRoot=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources
runtimeRoot=%APPDATA%\Automobilista Telemetria
frontend=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources\frontend\index.html
backend source=packaged-resource
logs=%APPDATA%\Automobilista Telemetria\logs
```

Validated installed endpoints:

- `GET /api/health`
- `GET /api/runtime/status`
- `GET /api/live/telemetry`
- `GET /api/live/opponents`
- `GET /api/live/racing-line`
- `GET /api/live/coach`

### Runtime Recovery

`desktop/main.js` now tracks:

```text
backendStatus=online|offline|starting|already-running|port-conflict|health-timeout|executable-not-found|crashed
```

Recovery behavior validated:

- Valid backend already running: Electron marks `already-running`, does not
  start another backend, and does not stop the external backend on close.
- Unknown process on backend port: Electron marks `port-conflict`, logs the
  conflict, and does not start the packaged backend.
- Packaged backend exe missing: Electron marks `executable-not-found`, logs the
  searched paths, and does not enter a restart loop.
- Backend startup can take longer in PyInstaller onefile mode, so health wait
  was increased to 60 seconds before reporting `health-timeout`.
- Normal app close stops the PyInstaller backend process tree started by
  Electron, including child processes.

### Runtime Panel

The dashboard runtime panel now shows:

- backend status;
- backend source;
- autostart enabled/disabled;
- started-by-Electron;
- API URL and backend port;
- health status;
- runtime root;
- resource root;
- logs directory;
- backend executable path;
- last backend error and port conflict message.

It polls lightweight runtime/health endpoints every 4 seconds and exposes a
safe `openLogsDir()` IPC bridge through the preload to open the logs directory.

### Uninstall/Reinstall

Silent uninstall and reinstall were validated:

```text
%LOCALAPPDATA%\Programs\Automobilista Telemetria\Uninstall Automobilista Telemetria.exe /S
desktop\dist\Automobilista Telemetria Setup 0.1.0-phase-12.exe /S
```

After reinstall, the app opened, backend health returned OK, and normal window
close left no backend process orphan.

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

Desktop production with controlled backend autostart:

```bash
cd desktop
npm run desktop:prod:autostart
```

Unpacked desktop package:

```bash
cd desktop
npm run pack
```

Windows installer:

```bash
cd desktop
npm run dist:win
```

Silent installer validation:

```bash
desktop\dist\Automobilista Telemetria Setup 0.1.0-phase-12.exe /S
```

## Logs Plan

Development desktop logs are written to:

```text
logs/backend.log
logs/desktop.log
```

This directory is runtime output and should not be committed.

Packaged desktop logs are written to:

```text
%APPDATA%\Automobilista Telemetria\logs\
```

## Risks

- Backend subprocess packaging needs careful handling of Python dependencies,
  native libraries, and Assetto Corsa shared-memory access.
- Port conflicts on `8000`, `5173`, and UDP `8765` need a diagnostic screen or
  explicit recovery path. Phase 12.4 covers backend HTTP port diagnostics, but
  not a full visual port configuration screen.
- Loading frontend assets from `file://` can expose assumptions that only work
  behind Vite. Phase 12.3 sets Vite `base: './'` and validates packaged
  `resources/frontend/index.html`.
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
4. Package backend with PyInstaller.
5. Package Electron with backend/frontend copied into `resources`.
6. Add port conflict detection and a diagnostics view.
7. Validate the Windows installer as installed software.
8. Add Assetto Corsa exporter/plugin setup checks.

## Recommended Phase 12.5

- Trim PyInstaller hook collection and reduce executable size.
- Add Assetto Corsa plugin/exporter setup wizard.
- Detect the Assetto Corsa install folder automatically where possible.
- Add application icon and polished installer metadata.
- Define runtime config file location for user-selected ports and paths.
- Keep auto-update, public signing, and crash reporting out of scope until the
  local installer flow is stable.
