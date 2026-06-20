import argparse
import json
import statistics
import time
from pathlib import Path
from urllib.request import urlopen


FIELDS = (
    "readAttemptHz",
    "sharedMemoryReadHz",
    "acceptedSampleHz",
    "collectorSampleHz",
    "recorderSampleHz",
    "persistedSampleHz",
    "liveWebSocketEmitHz",
    "telemetryDetailEmitHz",
    "opponentsUdpReceiveHz",
    "opponentsAcceptedHz",
    "opponentsWebSocketEmitHz",
    "opponentsSnapshotBytesAvg",
    "opponentsSnapshotBytesP95",
    "eventBusPendingTasks",
    "websocketPendingTasks",
    "recorderDroppedSamples",
    "droppedOpponentFrames",
    "droppedPlayerFrames",
)


def read_snapshot(url):
    with urlopen(url, timeout=3.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    sampling = payload.get("sampling") or {}
    row = {field: sampling.get(field) for field in FIELDS}
    row.update(
        {
            "capturedAt": time.time(),
            "playerStatus": (payload.get("telemetry") or {}).get("playerStatus"),
            "adaptivePollMode": (payload.get("telemetry") or {}).get("adaptivePollMode"),
            "backpressureRecent": sampling.get("websocketBackpressureRecent"),
            "loopTickP95Ms": (sampling.get("loopTickDurationMs") or {}).get("p95"),
            "playerSerializationP95Ms": (
                (sampling.get("serializationTimeMs") or {}).get("player") or {}
            ).get("p95"),
            "opponentsSerializationP95Ms": (
                (sampling.get("serializationTimeMs") or {}).get("opponents") or {}
            ).get("p95"),
        }
    )
    return row


def numeric_summary(rows):
    summary = {}
    for field in FIELDS + (
        "loopTickP95Ms",
        "playerSerializationP95Ms",
        "opponentsSerializationP95Ms",
    ):
        values = [float(row[field]) for row in rows if isinstance(row.get(field), (int, float))]
        if values:
            summary[field] = {
                "avg": round(statistics.fmean(values), 3),
                "max": round(max(values), 3),
            }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Sample runtime pipeline metrics for a controlled scenario.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/api/runtime/performance")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--label", default="unnamed")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = []
    deadline = time.monotonic() + max(args.duration, 1.0)
    while time.monotonic() < deadline:
        try:
            row = read_snapshot(args.url)
            rows.append(row)
            print(json.dumps(row, separators=(",", ":")))
        except Exception as exc:
            print(json.dumps({"error": str(exc), "capturedAt": time.time()}))
        time.sleep(max(args.interval, 0.2))

    result = {"label": args.label, "samples": len(rows), "summary": numeric_summary(rows), "rows": rows}
    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"outputError": str(exc), "path": str(args.output)}))
    print(json.dumps({"label": args.label, "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
