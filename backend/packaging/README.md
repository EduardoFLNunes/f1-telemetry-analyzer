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
- `AT_BACKEND_REPO_ROOT`, default resolved by the runner

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

`AT_BACKEND_REPO_ROOT` is used so a PyInstaller onefile executable does not
write recordings/cache under the temporary extraction directory.

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
```

## Phase 12.2 Result

- Python runner validated.
- PyInstaller `automobilista-backend.exe` generated.
- Packaged backend validated against `/api/health` and live endpoints.
- `AT_BACKEND_REPO_ROOT` keeps runtime data under the project/app root during
  the current desktop packaging prep.
- PyInstaller still emits hook warnings for optional test modules in pandas and
  pyarrow. The executable runs despite those warnings; Phase 12.3 should trim
  hook collection further.

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
- Backend executable missing: build with `backend\packaging\build_backend.ps1`
  or set `AT_BACKEND_EXE_PATH`.
- Health timeout: inspect `logs/desktop.log` and `logs/backend.log`.
- PyInstaller missing: run `.venv\Scripts\python.exe -m pip install pyinstaller`.
- Python dependency missing at runtime: rebuild after installing the dependency
  in `.venv`, then inspect `backend/build/automobilista-backend/warn-*.txt`.
