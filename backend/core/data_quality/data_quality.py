import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence


logger = logging.getLogger(__name__)


def _iso_from_epoch(value: Any) -> Optional[str]:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat()
    except (OSError, OverflowError, TypeError, ValueError):
        return None


class DataQualityReporter:
    def __init__(self, log_throttle_seconds: float = 60.0):
        self.log_throttle_seconds = float(log_throttle_seconds)
        self._last_log_at: Dict[str, float] = {}

    def build(
        self,
        *,
        player: Mapping[str, Any],
        opponents: Mapping[str, Any],
        sessions: Sequence[Mapping[str, Any]],
        track: Mapping[str, Any],
        comparison: Optional[Mapping[str, Any]] = None,
        current_lap_valid: Optional[bool] = None,
    ) -> Dict[str, Any]:
        lap_payload = self._laps(sessions, current_lap_valid)
        comparison_payload = self._comparison(comparison, lap_payload)
        player_payload = dict(player)
        player_payload["source"] = "shared_memory"
        player_payload["lastSampleAt"] = _iso_from_epoch(player_payload.pop("lastSampleAtEpoch", None))
        opponents_payload = dict(opponents)
        opponents_payload["source"] = "udp"
        opponents_payload.pop("lastPacketAtEpoch", None)

        report = {
            "status": self._overall_status(
                player_payload,
                opponents_payload,
                lap_payload,
                track,
                comparison_payload,
            ),
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "player": player_payload,
            "opponents": opponents_payload,
            "laps": lap_payload,
            "track": dict(track),
            "comparison": comparison_payload,
        }
        self._log_diagnostics(report)
        return report

    @staticmethod
    def _laps(
        sessions: Sequence[Mapping[str, Any]],
        current_lap_valid: Optional[bool],
    ) -> Dict[str, Any]:
        all_laps = [
            {**lap, "sessionId": session.get("sessionId")}
            for session in sessions
            for lap in (session.get("laps") or [])
            if isinstance(lap, Mapping)
        ]
        completed = [lap for lap in all_laps if lap.get("completed")]
        valid = [lap for lap in completed if lap.get("validationStatus") == "VALID" or lap.get("valid")]
        invalid = [lap for lap in completed if lap.get("validationStatus") == "INVALID"]
        partial = [
            lap
            for lap in all_laps
            if lap.get("validationStatus") == "PARTIAL"
            or (lap.get("completed") and not lap.get("valid") and not lap.get("validationStatus"))
        ]
        issues = []
        for lap in invalid + partial:
            lap_id = lap.get("lapId") or f"{lap.get('sessionId')}:{lap.get('lapNumber')}"
            for issue in lap.get("issues") or ["lap did not pass validation"]:
                issues.append(f"{lap_id}: {issue}")
                if len(issues) >= 12:
                    break
            if len(issues) >= 12:
                break
        last_completed = next(
            (
                lap
                for session in sessions
                for lap in reversed(session.get("laps") or [])
                if isinstance(lap, Mapping) and lap.get("completed")
            ),
            None,
        )
        return {
            "sessionCount": len(sessions),
            "completedLapCount": len(completed),
            "validLapCount": len(valid),
            "invalidLapCount": len(invalid),
            "partialLapCount": len(partial),
            "currentLapValid": current_lap_valid,
            "lastCompletedLapNumber": last_completed.get("lapNumber") if last_completed else None,
            "lastCompletedLapTime": (
                last_completed.get("durationSeconds", last_completed.get("duration"))
                if last_completed
                else None
            ),
            "issues": issues,
        }

    @staticmethod
    def _comparison(
        comparison: Optional[Mapping[str, Any]],
        laps: Mapping[str, Any],
    ) -> Dict[str, Any]:
        data = dict(comparison or {})
        issues = list(data.get("issues") or [])
        ready = bool(data.get("status") == "READY")
        if not ready and int(laps.get("validLapCount") or 0) > 0:
            ready = True
        if not ready:
            issues.append("at least one valid reference lap is required")
        return {
            "status": "READY" if ready else "INSUFFICIENT_DATA",
            "selectedReferenceLapId": data.get("selectedReferenceLapId"),
            "selectedComparisonLapId": data.get("selectedComparisonLapId"),
            "issues": issues,
        }

    @staticmethod
    def _overall_status(
        player: Mapping[str, Any],
        opponents: Mapping[str, Any],
        laps: Mapping[str, Any],
        track: Mapping[str, Any],
        comparison: Mapping[str, Any],
    ) -> str:
        if player.get("status") == "waiting" and not player.get("sampleCount"):
            return "UNKNOWN"
        if (
            player.get("frequencyStatus") == "ERROR"
            or int(player.get("invalidSampleCount") or 0) > 0
            or track.get("status") == "TRACK_MISSING"
        ):
            return "ERROR"
        if (
            player.get("frequencyStatus") in {"WARNING", "UNKNOWN"}
            or player.get("status") == "stale"
            or opponents.get("status") == "stale"
            or int(opponents.get("packetsInvalid") or 0) > 0
            or int(laps.get("invalidLapCount") or 0) > 0
            or int(laps.get("partialLapCount") or 0) > 0
            or track.get("status") != "TRACK_READY"
            or comparison.get("status") != "READY"
        ):
            return "WARNING"
        return "OK"

    def _log_diagnostics(self, report: Mapping[str, Any]):
        diagnostics = []
        if report["track"].get("status") == "TRACK_MISSING":
            diagnostics.append(("track_missing", "Track validation reports missing geometry"))
        if int(report["laps"].get("invalidLapCount") or 0) > 0:
            diagnostics.append(
                (
                    "invalid_lap",
                    f"Lap validation found {report['laps']['invalidLapCount']} invalid lap(s)",
                )
            )
        for key, message in diagnostics:
            now = time.monotonic()
            if now - self._last_log_at.get(key, 0.0) < self.log_throttle_seconds:
                continue
            self._last_log_at[key] = now
            logger.warning(message)
