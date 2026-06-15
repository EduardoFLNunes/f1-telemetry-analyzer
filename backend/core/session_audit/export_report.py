import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


class SessionAuditExporter:
    def __init__(self, output_root: Path):
        self.output_root = Path(output_root)

    def export(self, report: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = str(report.get("sessionId") or "unknown_session")
        safe_session_id = "".join(
            character
            for character in session_id
            if character.isalnum() or character in "._-"
        ) or "unknown_session"
        self.output_root.mkdir(parents=True, exist_ok=True)
        json_path = self.output_root / f"session_audit_{safe_session_id}.json"
        markdown_path = self.output_root / f"session_audit_{safe_session_id}.md"
        json_path.write_text(
            json.dumps(dict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        markdown_path.write_text(self.to_markdown(report), encoding="utf-8")
        generated_at = datetime.now(timezone.utc).isoformat()
        return {
            "status": "success",
            "sessionId": session_id,
            "generatedAt": generated_at,
            "directory": str(self.output_root),
            "jsonPath": str(json_path),
            "markdownPath": str(markdown_path),
        }

    def latest(self) -> Optional[Dict[str, Any]]:
        if not self.output_root.exists():
            return None
        markdown_files = sorted(
            self.output_root.glob("session_audit_*.md"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        if not markdown_files:
            return None
        markdown_path = markdown_files[0]
        json_path = markdown_path.with_suffix(".json")
        session_id = markdown_path.stem.removeprefix("session_audit_")
        return {
            "status": "success",
            "sessionId": session_id,
            "generatedAt": datetime.fromtimestamp(
                markdown_path.stat().st_mtime,
                timezone.utc,
            ).isoformat(),
            "directory": str(self.output_root),
            "jsonPath": str(json_path) if json_path.exists() else None,
            "markdownPath": str(markdown_path),
        }

    @staticmethod
    def to_markdown(report: Mapping[str, Any]) -> str:
        player = report.get("playerCapture") or {}
        udp = report.get("udpOpponents") or {}
        laps = report.get("laps") or {}
        track = report.get("track") or {}
        recommendations = report.get("recommendations") or []
        limitations = report.get("limitations") or []

        def value(item: Any, suffix: str = "") -> str:
            return "--" if item is None else f"{item}{suffix}"

        lines = [
            "# Session Telemetry Audit",
            "",
            f"- Session: `{report.get('sessionId')}`",
            f"- Track: `{report.get('trackName') or 'unknown'}`",
            f"- Car: `{report.get('carName') or 'unavailable'}`",
            f"- Started: `{report.get('startedAt') or 'unavailable'}`",
            f"- Ended: `{report.get('endedAt') or 'unavailable'}`",
            f"- Overall status: **{report.get('overallStatus', 'UNKNOWN')}**",
            "",
            "## Player Capture",
            "",
            f"- Source: `{player.get('source', 'shared_memory')}`",
            f"- Average frequency: {value(player.get('avgHz'), ' Hz')}",
            f"- P95 frame gap: {value(player.get('p95FrameGapMs'), ' ms')}",
            f"- P99 frame gap: {value(player.get('p99FrameGapMs'), ' ms')}",
            f"- Estimated dropped samples: {value(player.get('estimatedDroppedSamples'))}",
            f"- Longest gap: {value(player.get('longestGapMs'), ' ms')}",
            f"- Quality: **{player.get('qualityStatus', 'UNKNOWN')}**",
            "",
            "## Laps",
            "",
            f"- Total: {laps.get('totalLaps', 0)}",
            f"- Valid: {laps.get('validLaps', 0)}",
            f"- Partial: {laps.get('partialLaps', 0)}",
            f"- Invalid: {laps.get('invalidLaps', 0)}",
            f"- Best valid lap: {value(laps.get('bestValidLapTime'), ' s')}",
            "",
            "## UDP Opponents",
            "",
            f"- Source: `{udp.get('source', 'udp')}`",
            f"- Received snapshots: {udp.get('totalPacketsReceived', 0)}",
            f"- Accepted snapshots: {udp.get('totalPacketsAccepted', 0)}",
            f"- Dropped/invalid/out-of-order: {udp.get('totalPacketsDropped', 0)}/{udp.get('totalPacketsInvalid', 0)}/{udp.get('totalPacketsOutOfOrder', 0)}",
            f"- Opponents seen: {udp.get('opponentsSeen', 0)}",
            f"- Quality: **{udp.get('qualityStatus', 'UNKNOWN')}**",
            "",
            "## Track",
            "",
            f"- Status: **{track.get('status', 'UNKNOWN')}**",
            f"- Calibration profile: `{track.get('calibrationProfile') or 'default'}`",
            f"- Centerline/bounds/sectors: {track.get('hasCenterline', False)}/{track.get('hasBounds', False)}/{track.get('hasSectors', False)}",
            "",
            "## Recommendations",
            "",
        ]
        lines.extend(f"- {item}" for item in recommendations or ["No recommendations."])
        lines.extend(["", "## Limitations", ""])
        lines.extend(f"- {item}" for item in limitations or ["No known limitations."])
        lines.append("")
        return "\n".join(lines)
