# UDP Opponents Integration Plan

## Architecture Decision

The current `main` is the source of truth:

```text
Assetto Corsa Shared Memory
  -> ACSharedMemoryReader
  -> TelemetrySample (player only)
  -> TelemetryBuffer
  -> /api/live/telemetry and WebSocket

Assetto Corsa Python exporter
  -> UTF-8 JSON over UDP
  -> OpponentsTelemetryReceiver
  -> OpponentsStateBuffer
  -> /api/live/opponents and WebSocket
```

The UDP transport is a lateral opponents pipeline. It is not a fallback or
replacement for player Shared Memory.

## UDP Inventory

- Exporter: `tools/assetto_opponents_exporter/ac_opponents_exporter.py`
- Receiver: `backend/core/opponents/opponents_receiver.py`
- Runtime/config: `backend/core/opponents/opponents_runtime.py`
- Models: `backend/core/opponents/opponent_models.py`
- Bounded buffer: `backend/core/opponents/opponents_buffer.py`
- REST endpoint: `GET /api/live/opponents`
- WebSocket event: `type=opponents` on `/ws`
- Default destination: `127.0.0.1:8765`
- Packet format: compact UTF-8 JSON
- Packet type: `opponents_snapshot`
- Default exporter rate: 20 Hz

Configuration:

```text
AT_UDP_OPPONENTS_ENABLED=true
AT_UDP_OPPONENTS_HOST=127.0.0.1
AT_UDP_OPPONENTS_PORT=8765
```

## Packet Contract

Top-level fields:

```json
{
  "type": "opponents_snapshot",
  "timestamp": 1710000000.0,
  "sessionTime": null,
  "playerCarId": 0,
  "track": "ks_interlagos",
  "isMultiplayer": false,
  "cars": []
}
```

Accepted opponent fields:

| Field | Classification | Notes |
| --- | --- | --- |
| `carId` | real | Required identity key |
| `driverName` | real when present | Assetto Python API |
| `carModel` | real when present | Assetto Python API |
| `isAI` | real when present | `null` if the API cannot identify it |
| `isMultiplayer` | real session signal | Derived from an exposed server address |
| `worldPosition` | real | X/Y/Z from Assetto |
| `speedKmh` | real | Assetto car state |
| `yaw` | real when present | Assetto heading |
| `splinePosition` | real | Normalized track progress |
| `lap`, `lapTime` | real when present | Assetto car state |
| `racePosition` | real when present | Not synthesized |
| `status` | real/observed | Connected, pit, pitlane or on-track |
| `inferredState` | inferred | Speed-delta classification |
| `dataCompleteness` | calculated metadata | Ratio of available safe fields |

The backend does not expose opponent throttle, brake, tyre temperature,
suspension, fuel, setup or other full player physics. Missing data stays
`null`; it is never fabricated.

## Player Filtering

The exporter excludes the detected local `playerCarId`. The backend applies a
second defensive filter and rejects:

- `carId == 0`;
- any car with `isPlayer == true`;
- any car matching the packet's `playerCarId`.

This protects sessions where the local player ID is not zero.

## Buffer and Failure Handling

- Receiver runs on a daemon thread and uses a socket timeout.
- Invalid JSON and invalid contracts are discarded.
- Repeated invalid packet logs are rate limited.
- History is bounded per car.
- Stale cars are pruned.
- Track and session resets clear old opponent state.
- Snapshots older than the last accepted timestamp are discarded.
- UDP loss does not block or stop player telemetry.
- WebSocket output coalesces stale frames when a client is slow.

## Accepted From UDP Work

- Opponents-only Assetto Python exporter.
- UDP receiver, JSON parser and configurable runtime.
- Opponent model, bounded history and stale pruning.
- AI/multiplayer nullable identity fields.
- `carId` player filtering.
- Opponent REST/WebSocket delivery.
- Transport diagnostics and out-of-order counters.
- Isolated WebSocket backpressure improvement.

## Deliberately Discarded

- `backend/core/telemetry/assetto_udp.py` player receiver on port `9996`.
- `ACUDPReader` and `AssettoHybridReader`.
- UDP-first or UDP-fallback player telemetry.
- Player packets emitted by the Assetto exporter.
- UDP-specific LiveMap, map renderer or coordinate system.
- UDP dashboard/session layout replacements.
- Changes to `frontend/src/components/map/TrackRenderer.jsx`.
- Changes to Racing Line, Race Coach, Comparison layout or PerformanceMode.
- UDP opponent fields that imply unavailable full physics.

## Main Visual Pipeline

The existing main map remains authoritative. Opponents are projected and drawn
by the existing `TrackRenderer.jsx` overlay using the main coordinate rules.
No UDP component reconstructs or replaces TrackGeometry. Racing Line and all
main overlays continue to use the main track pipeline.

## Risks and Limitations

- UDP is lossy by design; a missing snapshot is tolerated but cannot be
  recovered.
- Assetto Python APIs do not always identify AI versus multiplayer per car.
  Unknown values remain `null`.
- `yaw`, race position and lap timing depend on simulator/API availability.
- Exporter destination is static inside the Assetto Python app; changing host
  or port requires matching exporter configuration/code.
- An empty opponents list can mean no opponents, a disabled plugin or no UDP
  packets. Runtime timestamps and counters distinguish these cases.

## Merge Plan

1. Keep player source selection on `ACSharedMemoryReader`.
2. Configure and start only the opponents UDP runtime.
3. Normalize opponent data without promoting it to player physics.
4. Preserve existing main endpoints and add explicit source diagnostics.
5. Add only diagnostic source labels to existing Runtime/Assetto panels.
6. Keep `TrackRenderer.jsx` byte-for-byte unchanged from `main`.
7. Validate unit tests, frontend build, Node syntax, endpoints and desktop
   packaging.
