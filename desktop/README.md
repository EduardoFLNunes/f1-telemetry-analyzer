# Automobilista Telemetria Desktop Shell

Phase 12.6 validates the Windows installer after the desktop packaging merge to
`main` and adds a project-owned provisional icon. Packaged builds start the
bundled backend from Electron `resources/`, write runtime data to AppData,
expose clearer backend recovery states, and provide a safe action to open the
logs directory.

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

## Electron Builder Packaging

Build prerequisites:

```bash
cd frontend
npm.cmd run build
```

```bash
powershell -ExecutionPolicy Bypass -File backend\packaging\build_backend.ps1
```

Create an unpacked Windows app:

```bash
cd desktop
npm run pack
```

Create the NSIS installer:

```bash
cd desktop
npm run dist:win
```

Install silently for validation:

```bash
desktop\dist\Automobilista-Telemetria-Setup-0.1.0-phase-12.exe /S
```

Default per-user install path:

```text
%LOCALAPPDATA%\Programs\Automobilista Telemetria\
```

The packaged app expects these resources:

```text
desktop/dist/win-unpacked/resources/backend/automobilista-backend.exe
desktop/dist/win-unpacked/resources/frontend/index.html
desktop/dist/win-unpacked/resources/data/example_telemetry.csv
```

When packaged, Electron resolves the backend in this order:

1. `AT_BACKEND_EXE_PATH`
2. `process.resourcesPath\backend\automobilista-backend.exe`
3. Development fallbacks under the repository.

The frontend static build resolves from:

1. `process.resourcesPath\frontend\index.html`
2. Development fallback `frontend\dist\index.html`.

## Installed App Validation

Phase 12.6 revalidated the installed app from the merge commit on `main`. It was
installed with the generated NSIS setup, opened without Vite or a manual
backend, and then opened again while repository `frontend/dist` and
`backend/dist` were temporarily renamed.

Observed installed app path:

```text
%LOCALAPPDATA%\Programs\Automobilista Telemetria\Automobilista Telemetria.exe
```

The installed app reported:

```text
resourceRoot=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources
runtimeRoot=%APPDATA%\Automobilista Telemetria
frontend=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources\frontend\index.html
backend source=packaged-resource
logs=%APPDATA%\Automobilista Telemetria\logs
```

Validated endpoints:

```http
GET /api/health
GET /api/runtime/status
GET /api/live/telemetry
GET /api/live/opponents
GET /api/live/racing-line
GET /api/live/coach
GET /api/live/comparison
GET /api/live/player-physics
```

The app was also uninstalled and reinstalled silently. After reinstall, it
opened, `/api/health` returned OK, logs were present in AppData, and normal
window close stopped the backend process tree started by Electron. User data in
`%APPDATA%\Automobilista Telemetria` was intentionally preserved.

## Visual Identity

Phase 12.6 adds provisional local icon assets:

```text
desktop/assets/icon.ico
desktop/assets/icon.png
```

The icon is a simple project-owned placeholder inspired by telemetry, a track
trace, and speed bars. It does not use external images or protected motorsport,
game, storefront, or sponsor marks.

Electron Builder uses `assets/icon.ico` for the Windows executable, installer,
uninstaller, and shortcuts. The Electron window also resolves the icon from the
packaged `assets` directory when possible. Replace these provisional assets
later with a polished final identity without changing the package layout.

## Runtime Config

The preload exposes `window.desktopRuntime` with:

- `apiBaseUrl`
- `wsUrl`
- `backendPort`
- `frontendDevPort`
- `udpOpponentsPort`
- `mode`
- `autostartEnabled`

The preload also exposes `window.automobilistaDesktop` with:

- `runtimeStatus()`
- `backendHealth()`
- `openLogsDir()`

`runtimeStatus()` includes `backendStatus`:

```text
online
offline
starting
already-running
port-conflict
health-timeout
executable-not-found
crashed
```

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
- `AT_BACKEND_RESOURCE_ROOT`: read-only root for packaged fixtures/resources.
- `AT_BACKEND_RUNTIME_ROOT`: writable root for cache and recordings.
- `AT_BACKEND_REPO_ROOT`: legacy fallback root for local development.
- `AT_DESKTOP_DISABLE_BACKEND_AUTOSTART=true`: disable packaged autostart.
- `AT_BACKEND_COMMAND`: backend command for future local process startup.
- `AT_BACKEND_ARGS`: backend command arguments. JSON arrays are supported.
- `AT_UDP_OPPONENTS_PORT`: UDP opponents port shown in diagnostics.
- `ASSETTO_CORSA_ROOT` / `AT_ASSETTO_CORSA_ROOT`: optional Assetto Corsa root
  used by the setup diagnostics before Steam/default path detection.

Backend autostart is enabled by default only when `app.isPackaged` is true.

## Assetto Corsa Setup Diagnostics

Phase 12.5 adds an `Assetto` tab inside the runtime panel. The tab is
diagnostic-first and does not install the plugin automatically.

It reports:

- Assetto Corsa detected or not found.
- Detected game path.
- Opponents exporter installed, not installed, or unknown.
- Bundled exporter source availability.
- Backend, player telemetry, and opponents status.
- API/UDP ports.

Safe actions exposed through the preload bridge:

- Find Assetto Corsa folder.
- Open detected folder.
- Copy manual plugin installation instructions.
- Validate plugin status.

The installed app bundles the exporter source under:

```text
resources\assetto_plugin\ac_opponents_exporter\
```

Expected manual destination:

```text
<Assetto Corsa>\apps\python\ac_opponents_exporter\
```

## Health Validation

```http
GET /api/health
GET /api/runtime/status
GET /api/live/telemetry
GET /api/live/opponents
GET /api/live/racing-line
GET /api/live/coach
GET /api/live/comparison
GET /api/live/player-physics
```

## Logs

The shell writes development logs to:

```text
logs/desktop.log
logs/backend.log
```

Packaged logs are written under:

```text
%APPDATA%\Automobilista Telemetria\logs\
```

The `logs/` directory is runtime output and should not be committed.

## Troubleshooting

- Port 8000 occupied: Electron reports `already-running` and avoids duplicate
  backend startup if `/api/health` is OK.
- Port 8000 occupied by an unknown service: Electron reports `port-conflict`
  and does not start the packaged backend.
- Backend exe missing: build it with `backend\packaging\build_backend.ps1` or set
  `AT_BACKEND_EXE_PATH`. Packaged apps report `executable-not-found` if the exe
  is missing from `resources/backend`.
- Health timeout: inspect the development logs or the packaged app logs under
  `%APPDATA%\Automobilista Telemetria\logs\`.
- Backend crash: Electron reports `crashed` and avoids aggressive restart loops.
- Static frontend missing: run `npm.cmd run build` from `frontend/`.
- Need Python runner for development: set `AT_BACKEND_RUNNER=python` or
  `AT_BACKEND_USE_PYTHON_RUNNER=true`.

## Still Planned

- Confirmed-copy plugin install flow with explicit user approval.
- Polished final icon and signed visual identity assets.
- Test on another clean Windows machine with only the installer copied.
- Digital signing.
- Auto-update.
