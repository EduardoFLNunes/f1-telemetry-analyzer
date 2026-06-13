# Phase 12 Distribution Checklist

Use this checklist before handing a build to another Windows machine.

## Build

- [ ] Build frontend with `npm.cmd run build` from `frontend`.
- [ ] Build backend EXE with `powershell -ExecutionPolicy Bypass -File backend\packaging\build_backend.ps1`.
- [ ] Run backend unit tests with `.venv\Scripts\python.exe -m unittest discover -s backend\tests`.
- [ ] Run `node --check desktop/main.js`.
- [ ] Run `node --check desktop/preload.js`.
- [ ] Run `npm.cmd run pack` from `desktop`.
- [ ] Run `npm.cmd run dist:win` from `desktop`.
- [ ] Confirm `desktop/dist`, `backend/dist`, logs, caches, and installers are ignored by Git.

## Install

- [ ] Install `desktop\dist\Automobilista-Telemetria-Setup-<version>.exe`.
- [ ] Open the installed app from Start Menu or Desktop shortcut.
- [ ] Confirm the app opens without Vite.
- [ ] Confirm the app opens without a manual backend.
- [ ] Confirm the app does not depend on repo `frontend/dist`.
- [ ] Confirm the app does not depend on repo `backend/dist`.
- [ ] Confirm `resources\frontend\index.html` is used.
- [ ] Confirm `resources\backend\automobilista-backend.exe` is used.
- [ ] Confirm `resources\assetto_plugin\ac_opponents_exporter` exists.

## Runtime

- [ ] `GET /api/health` returns OK.
- [ ] `GET /api/runtime/status` returns OK.
- [ ] `GET /api/live/telemetry` returns a valid payload.
- [ ] `GET /api/live/opponents` returns a valid payload.
- [ ] `GET /api/live/racing-line` returns a valid payload.
- [ ] `GET /api/live/coach` returns a valid payload.
- [ ] Runtime panel shows backend status.
- [ ] Runtime panel opens logs.
- [ ] Logs are written under `%APPDATA%\Automobilista Telemetria\logs`.

## Assetto Corsa

- [ ] Assetto setup panel appears.
- [ ] Assetto Corsa detection returns a clear result.
- [ ] Manual folder picker works.
- [ ] Detected folder can be opened.
- [ ] Plugin status is `installed`, `not-installed`, or `unknown`.
- [ ] Setup instructions can be copied.
- [ ] Backend status is visible in the setup panel.
- [ ] Player telemetry status is visible.
- [ ] Opponents status is visible.
- [ ] Ports show API `8000` and UDP `8765`.

## Game Session

- [ ] Start Assetto Corsa or Content Manager.
- [ ] Enable `ac_opponents_exporter` / `Opponents Exporter`.
- [ ] Start a driving session.
- [ ] Confirm player telemetry changes from `waiting` to `receiving`.
- [ ] Confirm opponents status changes when AI or multiplayer cars are present.
- [ ] Complete a valid lap.
- [ ] Confirm Racing Line can become ready after sufficient data.
- [ ] Confirm Coach can report after sufficient data/events.

## Recovery

- [ ] Close the app and confirm the backend started by Electron is stopped.
- [ ] Run a valid backend manually and open the app; it should report `already-running`.
- [ ] Occupy port `8000` with an unknown service; the app should report `port-conflict`.
- [ ] Temporarily hide packaged backend EXE; the app should report `executable-not-found`.
- [ ] Uninstall and reinstall.
- [ ] Confirm the app opens after reinstall.

## Other Machine

- [ ] Install on a Windows machine without the repository.
- [ ] Confirm backend starts from packaged resources.
- [ ] Confirm frontend loads from packaged resources.
- [ ] Confirm logs are created under AppData.
- [ ] Confirm Assetto Corsa detection succeeds or fails clearly.
- [ ] Confirm no unhandled crash occurs when Assetto Corsa is missing.
