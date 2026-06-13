# Phase 12.5 - Assetto Corsa Plugin Setup

This document maps the current Assetto Corsa integration and the assisted
setup plan for the installed desktop app.

## Current Integration

Player telemetry is read by the backend through Assetto Corsa shared memory.
It does not require an Assetto Python app.

Opponents telemetry uses a custom Assetto Corsa Python app:

```text
tools/assetto_opponents_exporter/
  ac_opponents_exporter.py
  icon.png
  README.md
  install_ac_opponents_exporter.ps1
```

The exporter sends UDP snapshots to:

```text
127.0.0.1:8765
```

The backend receives those snapshots through `OpponentsRuntime` and exposes
them through:

```text
GET /api/live/opponents
WS /ws
```

The desktop app/backend ports used by this phase are:

```text
Backend API: 127.0.0.1:8000
WebSocket:   ws://127.0.0.1:8000/ws
Opponents:   UDP 127.0.0.1:8765
```

## Expected Assetto Corsa Destination

The exporter destination inside Assetto Corsa is:

```text
<Assetto Corsa>\apps\python\ac_opponents_exporter\
  ac_opponents_exporter.py
  icon.png
  stdlib\_ctypes.pyd      optional, copied from SimHub if available
  stdlib64\_ctypes.pyd    optional, copied from SimHub if available
```

Only `ac_opponents_exporter.py` is required for the plugin status to be
considered installed. The `_ctypes.pyd` files are optional compatibility
helpers for Assetto Python environments where the standard `socket` module is
unavailable.

## Detection Plan

Electron detects candidate Assetto Corsa folders without modifying them.
Candidates are sourced from:

```text
ASSETTO_CORSA_ROOT / AT_ASSETTO_CORSA_ROOT
Saved manual selection under Electron userData
Steam registry InstallPath
Steam libraryfolders.vdf
Common Steam default paths
```

Each candidate reports:

```ts
{
  path: string;
  exists: boolean;
  hasAssettoExecutable: boolean;
  hasAppsPythonFolder: boolean;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  source: "steam-default" | "steam-library" | "manual" | "unknown";
}
```

`HIGH` means the folder exists, has `acs.exe`, and has `apps/python`.
`MEDIUM` means the folder exists and has either the executable or the Python app
folder. `LOW` means it is only a suggestion.

## Assisted Setup Plan

Phase 12.5 is diagnostic-first. It does not copy files into the user's Assetto
Corsa folder automatically.

The desktop UI now supports:

```text
Find Assetto Corsa folder
Open detected folder
Validate plugin status
Copy manual installation instructions
Show backend/player/opponents status
Show bundled exporter source availability
```

The installer includes the exporter as an app resource:

```text
resources\assetto_plugin\ac_opponents_exporter\
```

That makes the installed app ready for a later confirmed-copy flow, while this
phase remains read-only for the simulator folder.

## Validation Signals

The setup panel should make these signals visible:

```text
Assetto Corsa: detected / not found
Plugin: installed / not-installed / unknown
Backend: online / offline
Telemetry: receiving / waiting / stale / unknown
Opponents: receiving / waiting / stale / unknown
Last player sample age
Last opponents sample age
API/UDP ports
```

Backend `/api/runtime/status` now returns lightweight stream status fields:

```ts
telemetry.playerStatus
telemetry.lastPlayerSampleAt
telemetry.secondsSinceLastPlayerSample
opponents.status
opponents.lastOpponentSampleAt
opponents.secondsSinceLastOpponentSample
racingLine.status
coach.status
```

## Risks

- Assetto Corsa can be installed in any Steam library, including custom paths.
- Content Manager users may manage Python apps differently from vanilla
  Assetto Corsa.
- The exporter can be installed but disabled inside the game.
- A session with no AI/multiplayer cars can produce player telemetry while
  opponents remain empty.
- Assetto Python environments vary; the exporter has a WinSock fallback, but
  `socket`/`ctypes` availability can still differ by install.

## Rollback Plan

If a future confirmed install copies the exporter, rollback is simple:

```text
1. Close Assetto Corsa.
2. Remove <Assetto Corsa>\apps\python\ac_opponents_exporter.
3. Restart Assetto Corsa or Content Manager.
4. Confirm the app/module no longer appears.
```

No Phase 12.5 operation deletes or overwrites Assetto Corsa files.
