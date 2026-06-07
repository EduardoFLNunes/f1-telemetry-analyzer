# Backend Packaging Prep

Phase 12.1 maps the backend packaging path without producing a final executable.
The FastAPI backend continues to run from source during this phase.

## Current Entrypoint

Development command from `backend/`:

```bash
..\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
```

The app object lives in:

```text
backend/main.py
```

The `if __name__ == "__main__"` block in `backend/main.py` is useful for local
debugging, but a packaged executable should use a small production runner with
`reload=False` in a later phase.

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

## Dependency Risks

Packaging must be validated carefully because the backend imports libraries that
may need native binaries or hidden imports:

- FastAPI, Starlette, Uvicorn, websockets
- pandas, numpy, scipy
- pyarrow, duckdb, parquet/recording helpers
- torch, onnxruntime, model files if enabled by future phases
- Assetto Corsa shared-memory readers
- filesystem helpers for KN5/track cache discovery

## Preliminary PyInstaller Shape

This command is intentionally a starting point, not a final deliverable:

```bash
pyinstaller --name automobilista-backend --onefile --paths backend --collect-all uvicorn --collect-all pandas --collect-all numpy backend\packaging\run_backend.py
```

Before using that command in Phase 12.2, create and validate
`backend/packaging/run_backend.py` as a dedicated runner that imports
`main:app` and starts Uvicorn on `127.0.0.1:8000` with `reload=False`.

## Validation Checklist For Phase 12.2

- Packaged backend starts with no source tree on `PYTHONPATH`.
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
