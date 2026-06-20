# Phase 15 real-time stutter diagnostics

Use the same track, grid and frontend performance mode for every run. Capture at least 20 seconds after rates stabilize.

## Backend probe

```powershell
python tools\runtime_performance_probe.py --label assetto-closed --duration 20 --output C:\tmp\assetto-closed.json
```

The probe reads `/api/runtime/performance` without touching the live pipeline.

## Scenarios

1. Assetto closed: expect `waiting` or `stale`, low adaptive poll rate, zero pending-task growth and no recent backpressure.
2. Player only: open Assetto on track, select `PLAYER ONLY` on the map, and capture player/recorder rates.
3. Opponents enabled: select `OPPONENTS ON`, keep the same session, and capture backend plus `window.__telemetryPerf.trackRenderer` from Electron DevTools.
4. Render isolation: select `PLAYER ONLY` while UDP opponents remain active. Backend opponent rates must remain unchanged. A frontend improvement here isolates renderer/store cost.
5. Frequency sweep: restart the backend with `OPPONENTS_WS_HZ` set to `10`, `5`, then `2`, capturing each run. Do not change recorder settings.

For a reproducible backend-only load without Assetto:

```powershell
python tools\send_fake_opponents_udp.py --cars 19 --hz 20
```

## Frontend metrics

Open Electron DevTools and inspect:

```javascript
window.__telemetryPerf.trackRenderer
window.__telemetryPerf.wsPayloadByType
window.__telemetryPerf.wsParseByType
window.__renderMetrics
```

Compare frame p95/p99, static track, player, opponent transform/draw, store update time, React renders and payload sizes with the overlay on and off.

## Synthetic baseline

With 19 opponents at a requested 20 Hz input rate and one real WebSocket client:

- Full opponent frame at 10 Hz: approximately 12.99 KB average, serialization p95 approximately 0.79 ms.
- Lightweight opponent frame at 10 Hz: approximately 6.54 KB average, serialization p95 approximately 0.52 ms.
- Event bus pending tasks remained between 2 and 3 during active input and returned to zero afterward.
- WebSocket pending tasks remained zero and recent backpressure remained false.
- 5 Hz and 2 Hz trials also stayed queue-free, but reduce motion cadence. The default remains 10 Hz with canvas interpolation.

These measurements exclude Electron canvas timings. A final in-track run must capture `window.__telemetryPerf.trackRenderer` before commit approval.

## Real player validation

With Assetto running and a temporary corrected backend reading Shared Memory:

- adaptive mode: `active`, target 60 Hz;
- read attempts: 60.2 Hz;
- raw/accepted/collector: 58.6 Hz;
- recorder/persisted: 58.6 Hz;
- recorder retained ratio: 1.0, queue 0, drops 0;
- lightweight player WebSocket: 30.48 Hz;
- telemetry detail: 1.96 Hz;
- runtime loop p95: 2.84 ms;
- player serialization p95: 0.22 ms;
- event bus and WebSocket pending tasks: 0;
- recent WebSocket backpressure: false.

No lap transition occurred during this capture, so `lastPersistedLapEffectiveHz` was not finalized. Instantaneous recorder and disk rates were coherent.
