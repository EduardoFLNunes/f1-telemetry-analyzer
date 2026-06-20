# Phase 15 runtime sampling diagnostics

## Sampling stages

`/api/runtime/performance` reports each stage independently:

- `readAttemptHz`: shared-memory read loop attempts.
- `rawReadHz`: new packets returned by the reader after duplicate filtering.
- `acceptedSampleHz`: samples accepted by reliability validation.
- `lapCollectorSampleHz`: samples delivered to the live lap collector.
- `recorderReceivedHz`: processed frames received by the session recorder.
- `recorderSampleHz`: player frames accepted into the recorder queue.
- `persistedSampleHz`: player rows physically written to JSONL. This rate can pulse with writer batches.
- `liveWebSocketEmitHz`: lightweight live telemetry broadcasts.
- `telemetryDetailEmitHz`: low-frequency detailed physics broadcasts.

The recorder consumes the internal `processed_frame` event. It does not consume the WebSocket stream and is not limited by `TELEMETRY_WS_HZ` or `TELEMETRY_DETAIL_WS_HZ`.

## Recorder policy

`TELEMETRY_RECORDING_PLAYER_HZ` defaults to 60 Hz and `TELEMETRY_SOURCE_TARGET_HZ` defaults to 60 Hz.

- When the recording rate is equal to or higher than the source target, every accepted processed frame is queued. No callback-time gate is applied.
- When the recording rate is lower than the source target, downsampling is intentional and uses the source telemetry timestamp. Metadata records `playerDownsamplingEnabled` and `playerRecordPolicy=source_timestamp_cap`.

`recorderDownsampleRatio` is the retained ratio (`recorderSampleHz / recorderReceivedHz`). A value of `1.0` means no recorder downsampling. Queue or write failures are reported separately as `recorderDroppedSamples`.

## WebSocket backpressure

Normal closed-client errors are counted as disconnects, not send failures. `backpressureDetected` considers only send failures from the latest five-second window, so an old auxiliary-client failure cannot leave the runtime permanently in `websocket_backpressure`.

## Opponent payloads

Opponent snapshots remain independent from the lightweight player frame. Detailed state remains available through `/api/live/opponents`; the 10 Hz WebSocket frame contains only identity, position, heading, speed, lap and track progress required by the live map. Synthetic validation with 19 cars reduced the average frame from approximately 13.0 KB to 6.5 KB. Payload size still grows with car count, so binary/delta encoding remains a possible later optimization.
