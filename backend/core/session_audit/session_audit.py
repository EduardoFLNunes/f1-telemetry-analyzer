import json
import threading
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..recording.session_repository import SessionRepository
from .export_report import SessionAuditExporter
from .lap_audit import LapStreamAggregator, audit_laps
from .sample_loss_report import analyze_sample_timestamps, timestamp_seconds
from .track_calibration import calibration_for_track


class SessionAuditService:
    def __init__(
        self,
        repository: SessionRepository,
        reports_root: Path,
    ):
        self.repository = repository
        self.exporter = SessionAuditExporter(reports_root)
        self._cache: Dict[str, tuple] = {}
        self._lock = threading.RLock()

    def latest_session_id(self) -> Optional[str]:
        fallback = None
        for session_id in self.repository.list_session_ids():
            fallback = fallback or session_id
            directory = self.repository.session_directory(session_id)
            if any(
                (directory / filename).exists()
                and (directory / filename).stat().st_size > 0
                for filename in ("player.jsonl", "opponents.jsonl")
            ):
                return session_id
        return fallback

    def audit_latest(
        self,
        track_validation: Optional[Mapping[str, Any]] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        session_id = self.latest_session_id()
        if not session_id:
            return None
        return self.audit_session(session_id, track_validation=track_validation, force=force)

    def audit_session(
        self,
        session_id: str,
        *,
        track_validation: Optional[Mapping[str, Any]] = None,
        force: bool = False,
    ) -> Optional[Dict[str, Any]]:
        signature = (
            self.repository.session_signature(session_id),
            json.dumps(dict(track_validation or {}), sort_keys=True, default=str),
        )
        with self._lock:
            cached = self._cache.get(session_id)
            if not force and cached and cached[0] == signature:
                return dict(cached[1])

        summary = self.repository.session_summary(session_id, allow_large_scan=True)
        if not summary:
            return None
        metadata = self.repository.session_metadata(session_id)
        nested_metadata = metadata.get("metadata") or {}
        track_name = summary.get("track") or metadata.get("track")
        profile = calibration_for_track(track_name)

        player_capture, car_name, streamed_laps = self._audit_player(
            session_id,
            float(metadata.get("playerRecordHz") or 60.0),
            recording_ended=bool(metadata.get("endedAt")),
        )
        udp_opponents = self._audit_udp(
            session_id,
            float(metadata.get("opponentsRecordHz") or 20.0),
        )
        laps = audit_laps(session_id, streamed_laps, profile)
        track = self._audit_track(
            track_name,
            nested_metadata,
            track_validation,
            profile.profileId,
        )
        recommendations = self._recommendations(player_capture, udp_opponents, laps, track)
        overall_status = self._overall_status(player_capture, udp_opponents, laps, track)
        report = {
            "sessionId": session_id,
            "trackName": track_name,
            "carName": car_name,
            "startedAt": metadata.get("startedAt"),
            "endedAt": metadata.get("endedAt"),
            "durationSeconds": summary.get("duration"),
            "overallStatus": overall_status,
            "playerCapture": player_capture,
            "udpOpponents": udp_opponents,
            "laps": laps,
            "track": track,
            "recommendations": recommendations,
            "limitations": [
                "Historical UDP invalid packets that were rejected before persistence cannot be reconstructed.",
                "Track sector availability depends on metadata captured with the session.",
                "Interlagos thresholds are intentionally broad pending more real-session calibration.",
            ],
            "samplesIncluded": False,
        }
        with self._lock:
            self._cache[session_id] = (signature, dict(report))
        return report

    def export_latest(
        self,
        track_validation: Optional[Mapping[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        report = self.audit_latest(track_validation=track_validation)
        return self.exporter.export(report) if report else None

    def _audit_player(
        self,
        session_id: str,
        target_hz: float,
        *,
        recording_ended: bool,
    ):
        timestamps = []
        car_name = None
        lap_aggregator = LapStreamAggregator(session_id)
        for row in self.repository.iter_stream_rows(session_id, "player"):
            sample = row.get("sample") if isinstance(row.get("sample"), dict) else {}
            timestamps.append(row.get("timestamp", sample.get("timestamp")))
            lap_aggregator.observe(row)
            if car_name is None:
                for key in ("carName", "carModel", "car_name", "car_model"):
                    value = sample.get(key)
                    if isinstance(value, str) and value.strip():
                        car_name = value.strip()
                        break
        report = analyze_sample_timestamps(timestamps, target_hz=target_hz)
        return (
            {"source": "shared_memory", **report},
            car_name,
            lap_aggregator.finish(recording_ended),
        )

    def _audit_udp(self, session_id: str, target_hz: float) -> Dict[str, Any]:
        directory = self.repository.session_directory(session_id)
        path = directory / "opponents.jsonl"
        received = 0
        accepted = 0
        invalid = 0
        out_of_order = 0
        player_filtered = 0
        timestamps = []
        opponents_seen = set()
        previous_timestamp = None
        if path.exists():
            with path.open("rb") as handle:
                for line in handle:
                    received += 1
                    try:
                        row = json.loads(line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        invalid += 1
                        continue
                    if not isinstance(row, dict) or not isinstance(row.get("cars"), list):
                        invalid += 1
                        continue
                    timestamp = timestamp_seconds(row.get("timestamp"))
                    if timestamp is not None:
                        timestamps.append(timestamp)
                        if previous_timestamp is not None and timestamp < previous_timestamp - 1e-6:
                            out_of_order += 1
                        previous_timestamp = timestamp
                    accepted += 1
                    for car in row["cars"]:
                        if not isinstance(car, dict):
                            continue
                        car_id = car.get("carId")
                        if car.get("isPlayer") is True or car_id == 0:
                            player_filtered += 1
                            continue
                        if car_id is not None:
                            opponents_seen.add(str(car_id))

        frequency = analyze_sample_timestamps(timestamps, target_hz=target_hz)
        dropped = invalid + out_of_order
        if received == 0:
            quality = "UNKNOWN"
        elif invalid / max(received, 1) >= 0.2 or out_of_order > 0:
            quality = "ERROR"
        elif frequency["qualityStatus"] in {"ERROR", "WARNING"} or dropped > 0:
            quality = "WARNING"
        else:
            quality = "OK"
        return {
            "source": "udp",
            "totalPacketsReceived": received,
            "totalPacketsAccepted": accepted,
            "totalPacketsDropped": dropped,
            "totalPacketsInvalid": invalid,
            "totalPacketsOutOfOrder": out_of_order,
            "playerFilteredCount": player_filtered,
            "avgHz": frequency["avgHz"],
            "opponentsSeen": len(opponents_seen),
            "qualityStatus": quality,
        }

    @staticmethod
    def _audit_track(
        track_name: Optional[str],
        metadata: Mapping[str, Any],
        current_validation: Optional[Mapping[str, Any]],
        profile_id: str,
    ) -> Dict[str, Any]:
        current = dict(current_validation or {})
        current_name = str(current.get("trackName") or "").lower()
        track_matches = bool(
            current
            and track_name
            and (
                str(track_name).lower() in current_name
                or current_name in str(track_name).lower()
                or ("interlagos" in str(track_name).lower() and "interlagos" in current_name)
            )
        )
        if track_matches:
            return {
                "status": current.get("status", "UNKNOWN"),
                "hasCenterline": bool(current.get("hasCenterline")),
                "hasBounds": bool(current.get("hasBounds")),
                "hasSectors": bool(current.get("hasSectors")),
                "calibrationProfile": profile_id,
                "issues": list(current.get("issues") or []),
            }

        state = metadata.get("trackState") or "UNKNOWN"
        ready = state == "TRACK_READY"
        status = state if state in {"TRACK_READY", "TRACK_PARTIAL", "TRACK_MISSING"} else "UNKNOWN"
        issues = []
        if status == "UNKNOWN":
            issues.append("historical session has no track validation snapshot")
        if not metadata.get("hasSectors"):
            issues.append("sector metadata is unavailable")
        return {
            "status": status,
            "hasCenterline": bool(metadata.get("hasCenterline", ready)),
            "hasBounds": bool(metadata.get("hasBounds", ready)),
            "hasSectors": bool(metadata.get("hasSectors", False)),
            "calibrationProfile": profile_id,
            "issues": issues,
        }

    @staticmethod
    def _recommendations(player, udp, laps, track):
        items = []
        if player["qualityStatus"] in {"WARNING", "ERROR"}:
            items.append(
                "Review capture cadence and background load; player frequency is below the reliability target."
            )
        if (player.get("estimatedDroppedSamples") or 0) > 0:
            items.append("Compare estimated sample loss with the recorder target before using microsector deltas.")
        if laps["validLaps"] == 0:
            items.append("Complete at least one validated lap before selecting a comparison reference.")
        if laps["invalidLaps"] or laps["partialLaps"]:
            items.append("Inspect lap issues before using the session in comparative analysis.")
        if udp["qualityStatus"] in {"WARNING", "ERROR"}:
            items.append("Verify the opponents exporter cadence and UDP packet ordering.")
        if track["status"] != "TRACK_READY":
            items.append("Confirm track geometry readiness before spatial analysis.")
        if not items:
            items.append("Session is suitable for lap comparison and technical reporting.")
        return items

    @staticmethod
    def _overall_status(player, udp, laps, track):
        if player["qualityStatus"] == "UNKNOWN" and laps["totalLaps"] == 0:
            return "UNKNOWN"
        if (
            player["qualityStatus"] == "ERROR"
            or udp["qualityStatus"] == "ERROR"
            or track["status"] == "TRACK_MISSING"
        ):
            return "ERROR"
        if (
            player["qualityStatus"] == "WARNING"
            or udp["qualityStatus"] in {"WARNING", "UNKNOWN"}
            or laps["invalidLaps"] > 0
            or laps["partialLaps"] > 0
            or track["status"] != "TRACK_READY"
        ):
            return "WARNING"
        return "OK"
