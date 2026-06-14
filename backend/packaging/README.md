# Backend Packaging

## Current Entrypoint

Development command from `backend/`:

```bash
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The app object lives in:

```text
backend/main.py
```

Desktop packaging uses:

```text
backend/desktop_backend_runner.py
```

The runner imports the existing FastAPI app and starts Uvicorn programmatically
with `reload=False`. It accepts:

- `AT_BACKEND_HOST`, default `127.0.0.1`
- `AT_BACKEND_PORT`, default `8000`
- `AT_BACKEND_LOG_LEVEL`, default `info`
- `AT_BACKEND_RESOURCE_ROOT`, read-only root for packaged fixtures/resources
- `AT_BACKEND_RUNTIME_ROOT`, writable root for cache and recordings
- `AT_BACKEND_REPO_ROOT`, legacy fallback used by local development

No FastAPI logic is duplicated in the runner.

## Runtime Ports

- HTTP API: `127.0.0.1:8000`
- WebSocket: `ws://127.0.0.1:8000/ws`
- Opponents UDP receiver: `127.0.0.1:8765`
- Vite dev server, frontend only: `127.0.0.1:5173`

## Runtime Data Paths

These paths must remain writable outside a read-only packaged app directory:

- `data/cache/tracks/`
- `data/recordings/`
- `logs/`
- any user-selected Assetto Corsa install path

Do not bake machine-specific absolute paths into the executable.

`AT_BACKEND_RESOURCE_ROOT` and `AT_BACKEND_RUNTIME_ROOT` keep PyInstaller
onefile runs from reading or writing under the temporary extraction directory.
In the Electron package, resources come from `process.resourcesPath` while
cache and recordings go to Electron `userData`.

## Dependency Risks

Packaging must be validated carefully because the backend imports libraries that
may need native binaries or hidden imports:

- FastAPI, Starlette, Uvicorn, websockets
- pandas, numpy, scipy
- pyarrow, duckdb, parquet/recording helpers
- torch, onnxruntime, model files if enabled by future phases
- Assetto Corsa shared-memory readers
- filesystem helpers for KN5/track cache discovery

## Build Backend Executable

Install PyInstaller when needed:

```bash
.venv\Scripts\python.exe -m pip install pyinstaller
```

Build:

```bash
powershell -ExecutionPolicy Bypass -File backend\packaging\build_backend.ps1
```

The executable is generated at:

```text
backend/dist/automobilista-backend.exe
```

`backend/build/`, `backend/dist/`, and generated PyInstaller `.spec` files are
build artifacts. Do not commit machine-specific generated specs.

## Electron Resource Packaging

Electron Builder copies the backend executable into:

```text
desktop/dist/win-unpacked/resources/backend/automobilista-backend.exe
```

At runtime, Electron passes:

```text
AT_BACKEND_RESOURCE_ROOT=<process.resourcesPath>
AT_BACKEND_RUNTIME_ROOT=<app.getPath("userData")>
```

This lets the packaged backend read bundled fixture data from `resources/data`
and write cache/recordings under `%APPDATA%\Automobilista Telemetria\`.

Installed apps use:

```text
resourceRoot=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources
runtimeRoot=%APPDATA%\Automobilista Telemetria
logs=%APPDATA%\Automobilista Telemetria\logs
```

## Test Runner

From `backend/`:

```bash
..\.venv\Scripts\python.exe desktop_backend_runner.py
```

Then validate:

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

## Phase 12.2 Result

- Python runner validated.
- PyInstaller `automobilista-backend.exe` generated.
- Packaged backend validated against `/api/health` and live endpoints.
- Phase 12.2 used `AT_BACKEND_REPO_ROOT` to keep runtime data under the
  project/app root during early packaging prep.
- PyInstaller still emits hook warnings for optional test modules in pandas and
  pyarrow. The executable runs despite those warnings; Phase 12.3 should trim
  hook collection further.

## Phase 12.3 Result

- Electron Builder `pack` creates `desktop/dist/win-unpacked`.
- Electron Builder `dist:win` creates the NSIS installer in `desktop/dist`.
- Packaged backend lookup was validated with repository `backend/dist` hidden.
- Packaged frontend lookup was validated with repository `frontend/dist` hidden.
- Runtime status reported `backend.resourceRoot` as
  `desktop/dist/win-unpacked/resources`.
- Runtime status reported `backend.runtimeRoot` under
  `%APPDATA%\Automobilista Telemetria`.

## Phase 12.4 Result

- NSIS installer was installed silently with `/S`.
- Installed app opened without repository `frontend/dist` or `backend/dist`.
- Installed backend started from
  `%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources\backend`.
- Installed frontend loaded from
  `%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources\frontend`.
- Logs were created under `%APPDATA%\Automobilista Telemetria\logs`.
- `/api/health`, `/api/runtime/status`, telemetry, opponents, Racing Line, and
  Coach endpoints returned.
- Unknown service on the backend port was detected as `port-conflict`.
- Missing packaged backend exe was detected as `executable-not-found`.
- Valid backend already running was treated as `already-running`; Electron did
  not start another backend and did not stop that external backend.
- Normal app close stopped the PyInstaller backend process tree started by
  Electron, including child processes.
- Silent uninstall/reinstall was validated without deleting user data.

## Phase 12.5 Runtime Status Additions

`GET /api/runtime/status` now includes lightweight stream diagnostics for the
desktop setup panel:

```text
telemetry.playerStatus
telemetry.lastPlayerSampleAt
telemetry.secondsSinceLastPlayerSample
opponents.status
opponents.lastOpponentSampleAt
opponents.secondsSinceLastOpponentSample
racingLine.status
coach.status
```

These fields use existing runtime timestamps and buffers. They do not trigger
Racing Line recalculation, Coach analysis, or any heavy reconstruction work.

## Phase 12.6 Installer Validation

Phase 12.6 revalidates the installer after the desktop packaging branch was
merged into `main`.

Baseline validation:

- Frontend build from `frontend/`: passed, 1501 modules transformed.
- Backend tests: passed, 36 tests OK.
- `node --check desktop/main.js`: passed.
- `node --check desktop/preload.js`: passed.

Packaging validation:

- `backend\packaging\build_backend.ps1`: passed and generated
  `backend/dist/automobilista-backend.exe`.
- `npm.cmd run pack` from `desktop/`: passed and generated
  `desktop/dist/win-unpacked`.
- `npm.cmd run dist:win` from `desktop/`: passed and generated
  `desktop/dist/Automobilista-Telemetria-Setup-0.1.1-phase-12.exe`.

Installed validation:

```text
app=%LOCALAPPDATA%\Programs\Automobilista Telemetria\Automobilista Telemetria.exe
resourceRoot=%LOCALAPPDATA%\Programs\Automobilista Telemetria\resources
runtimeRoot=%APPDATA%\Automobilista Telemetria
logs=%APPDATA%\Automobilista Telemetria\logs
```

The installed app opened without Vite, without a manual backend, and with the
repository `frontend/dist` and `backend/dist` temporarily hidden. The backend
started from packaged resources and the frontend loaded from packaged
resources.

Validated installed endpoints:

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

Silent uninstall/reinstall was validated. The uninstall removed the installed
program directory, left no `automobilista-backend.exe` process orphaned, and did
not remove user data under `%APPDATA%\Automobilista Telemetria`.

PyInstaller still emits known warnings about optional pandas/pyarrow test
modules and a rapidfuzz hook entry point. The executable is generated and runs
despite those warnings.

The packaged backend resolves fixed track geometry from
`AT_BACKEND_RESOURCE_ROOT`. Electron Builder includes only the validated JSON
assets required for the final Interlagos map, preventing an old AppData cache
or a raw KN5 rebuild from replacing the visual geometry used by `main`.

## Validation Checklist For Phase 12.2

- Packaged backend starts from `backend/dist/automobilista-backend.exe`.
- `GET /api/health` returns OK.
- `GET /api/runtime/status` returns OK.
- WebSocket `/ws` accepts a client.
- Opponents UDP receiver starts and exposes `/api/live/opponents`.
- Racing Line endpoint still returns a reference or explicit insufficient-data
  state.
- Logs are written to a user-writable directory.
- Track cache and recordings are written outside packaged resources.
- Electron can start and stop the packaged backend only when autostart is
  explicitly enabled.

## Troubleshooting

- Port 8000 occupied: Electron will treat the existing healthy backend as
  `already-running` and will not start another process.
- Port 8000 occupied by another service: Electron reports `port-conflict` and
  leaves the unknown process alone.
- Backend executable missing: build with `backend\packaging\build_backend.ps1`
  or set `AT_BACKEND_EXE_PATH`. Installed apps report
  `executable-not-found` if `resources/backend/automobilista-backend.exe` is
  missing.
- Health timeout: inspect development logs or installed logs under
  `%APPDATA%\Automobilista Telemetria\logs`.
- PyInstaller missing: run `.venv\Scripts\python.exe -m pip install pyinstaller`.
- Python dependency missing at runtime: rebuild after installing the dependency
  in `.venv`, then inspect `backend/build/automobilista-backend/warn-*.txt`.
