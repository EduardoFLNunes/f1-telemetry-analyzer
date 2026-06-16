from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..cache.track_cache import TrackCache
from ..data_quality.lap_validation import validate_lap
from ..external_references import ExternalReferenceRepository, InterlagosReferenceMapper
from ..live.runtime_state import RuntimeState
from ..telemetry.telemetry_buffer import TelemetryBuffer
from .driver_error_classifier import DrivingErrorClassifier
from .driving_knowledge_base import DrivingKnowledgeBase
from .feedback_generator import FeedbackGenerator
from .lap_loader import LapDataLoader
from .reference_lap_comparator import ReferenceComparator
from .corner_metrics import CornerMetricsCalculator
from .models import CornerComparison, CornerMetrics, DrivingError, LapDescriptor
from .corner_segmentation import CornerSegmenter
from .utils import finite_float
from .vehicle_dynamics_analyzer import VehicleDynamicsAnalyzer


ANALYSIS_VERSION = "phase14.post_lap_assisted_analysis.v1"


class AssistedAnalysisService:
    def __init__(
        self,
        repo_root: Path,
        telemetry_buffer: TelemetryBuffer,
        runtime_state: RuntimeState,
        track_cache: TrackCache,
        external_reference_repository: Optional[ExternalReferenceRepository] = None,
    ):
        self.repo_root = Path(repo_root)
        self.telemetry_buffer = telemetry_buffer
        self.runtime_state = runtime_state
        self.track_cache = track_cache
        self.analysis_dir = self.repo_root / "data" / "assisted_analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        self.loader = LapDataLoader(
            repo_root=self.repo_root,
            buffer_provider=lambda: self.telemetry_buffer,
            runtime_state_provider=lambda: self.runtime_state,
        )
        self.segmenter = CornerSegmenter()
        self.metrics = CornerMetricsCalculator()
        self.comparator = ReferenceComparator()
        self.knowledge_base = DrivingKnowledgeBase()
        self.classifier = DrivingErrorClassifier(self.knowledge_base)
        self.dynamics = VehicleDynamicsAnalyzer()
        self.feedback = FeedbackGenerator()
        self.external_references = external_reference_repository or ExternalReferenceRepository(self.repo_root)
        self.external_mapper = InterlagosReferenceMapper()
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def list_laps(self) -> Dict[str, Any]:
        laps = [lap.to_api() for lap in self.loader.list_laps(include_buffer=False)]
        return {"status": "success", "laps": laps}

    def get_cached_analysis(
        self,
        lap_id: str,
        reference_lap_id: Optional[str] = None,
        *,
        include_external_reference: bool = False,
        external_reference_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key(lap_id, reference_lap_id, self._external_cache_key(include_external_reference, external_reference_id))
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        path = self._cache_path(cache_key)
        if not path.exists() and reference_lap_id is None:
            candidates = sorted(self.analysis_dir.glob(f"{self._hash(lap_id)}__*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
            path = candidates[0] if candidates else path
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._memory_cache[cache_key] = payload
            return payload
        except Exception:
            return None

    def analyze_lap(
        self,
        lap_id: str,
        reference_lap_id: Optional[str] = None,
        include_external_reference: bool = False,
        external_reference_id: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        if not force:
            cached = self.get_cached_analysis(
                lap_id,
                reference_lap_id,
                include_external_reference=include_external_reference,
                external_reference_id=external_reference_id,
            )
            if cached:
                return cached

        target, target_df = self.loader.load_lap(lap_id)
        reference, reference_df, reference_mode = self._load_reference(target, reference_lap_id)
        track_data = self._track_data(target, reference)
        track_length = self._track_length(track_data, target_df, reference_df)
        target_validation = self._validate_loaded_lap(target, target_df)
        reference_validation = self._validate_loaded_lap(reference, reference_df)

        warnings: List[str] = []
        if len(target_df) < 40:
            warnings.append("target_lap_has_low_sample_count")
        if len(reference_df) < 40:
            warnings.append("reference_lap_has_low_sample_count")
        if reference.lap_id == target.lap_id:
            warnings.append("self_baseline_reference")
        if not track_data:
            warnings.append("active_track_geometry_unavailable")

        segments = self.segmenter.segment(track_data, target_df)
        if not segments:
            warnings.append("corner_segmentation_unavailable")

        player_metrics = self.metrics.compute(target_df, segments, track_length)
        reference_metrics = self.metrics.compute(reference_df, segments, track_length)
        comparisons = self.comparator.compare(player_metrics, reference_metrics, track_length)
        target_dynamics_df = self.dynamics.prepare(target_df)
        reference_dynamics_df = self.dynamics.prepare(reference_df)

        corner_payloads = []
        all_errors: List[DrivingError] = []
        for segment in segments:
            player = player_metrics.get(segment.corner_id)
            ref = reference_metrics.get(segment.corner_id)
            comparison = comparisons.get(segment.corner_id)
            if not player or not ref or not comparison:
                continue
            dynamics_profile = self.dynamics.analyze_corner(target_dynamics_df, reference_dynamics_df, segment, track_length)
            reference_dynamics_profile = self.dynamics.analyze_corner(reference_dynamics_df, target_dynamics_df, segment, track_length)
            errors = self.classifier.classify(player, ref, comparison, dynamics_profile, reference_dynamics_profile)
            all_errors.extend(errors)
            loss = comparison.estimated_gain()
            name = segment.name or f"T{segment.corner_id}"
            primary = errors[0] if errors else None
            corner_payloads.append(
                {
                    **segment.to_api(),
                    "lossS": loss,
                    "estimatedGainS": sum(error.estimated_gain_s for error in errors) or loss,
                    "primaryError": primary.label if primary else None,
                    "primaryPhase": primary.phase if primary else None,
                    "technicalConcept": primary.concept if primary else None,
                    "drivingTechnique": primary.technique if primary else None,
                    "physicalBehavior": primary.physical_behavior if primary else None,
                    "evidenceTelemetry": primary.evidence if primary else {},
                    "metrics": player.to_api(),
                    "referenceMetrics": ref.to_api(),
                    "comparison": comparison.to_api(),
                    "vehicleDynamics": dynamics_profile.to_api(),
                    "referenceVehicleDynamics": reference_dynamics_profile.to_api(),
                    "errors": [error.to_api() for error in errors],
                    "feedback": self.feedback.corner_feedback(name, errors, loss),
                }
            )

        top_losses = self._top_losses(corner_payloads)
        total_gain = sum(float(item.get("estimatedGainS") or 0.0) for item in corner_payloads)
        optional_channels = self._optional_channels(player_metrics)
        data_quality = self.feedback.data_quality(len(target_df), len(reference_df), optional_channels, warnings)
        summary = {
            "totalEstimatedGainS": total_gain,
            "cornerCount": len(corner_payloads),
            "errorCount": len(all_errors),
            "confidence": data_quality["confidence"],
            "headline": self.feedback.headline(top_losses, total_gain),
            "dataQuality": data_quality,
        }
        external_reference_context = (
            self._external_reference_context(target.track, track_length, corner_payloads, external_reference_id)
            if include_external_reference
            else None
        )

        analysis = self._json_safe({
            "status": "success",
            "analysis": {
                "status": "ANALYZED",
                "version": ANALYSIS_VERSION,
                "createdAt": datetime.utcnow().isoformat() + "Z",
                "pipeline": "post_lap_only",
                "lapId": target.lap_id,
                "driverId": target.driver_id,
                "lapNumber": target.lap_number,
                "lapTime": target.lap_time,
                "track": target.track,
                "source": target.source,
                "validation": target_validation,
                "reference": {
                    "lapId": reference.lap_id,
                    "driverId": reference.driver_id,
                    "lapNumber": reference.lap_number,
                    "lapTime": reference.lap_time,
                    "track": reference.track,
                    "source": reference.source,
                    "mode": reference_mode,
                    "validation": reference_validation,
                },
                "trackLength": track_length,
                "summary": summary,
                "knowledgeBase": [concept.to_api() for concept in self.knowledge_base.all()],
                "externalReference": external_reference_context,
                "topLosses": top_losses,
                "corners": corner_payloads,
            },
        })
        cache_key = self._cache_key(lap_id, reference_lap_id, self._external_cache_key(include_external_reference, external_reference_id))
        self._memory_cache[cache_key] = analysis
        self._cache_path(cache_key).write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        return analysis

    def _load_reference(
        self,
        target: LapDescriptor,
        reference_lap_id: Optional[str],
    ) -> Tuple[LapDescriptor, pd.DataFrame, str]:
        if reference_lap_id:
            descriptor, df = self.loader.load_lap(reference_lap_id)
            return descriptor, df, "provided"

        candidates = [
            lap for lap in self.loader.list_laps(include_buffer=False)
            if lap.lap_id != target.lap_id and lap.sample_count >= 40
        ]
        same_track = [lap for lap in candidates if self._same_track(lap.track, target.track)]
        candidates = same_track or candidates

        previous = [
            lap for lap in candidates
            if lap.session_id == target.session_id and lap.lap_number == target.lap_number - 1
        ]
        if previous:
            descriptor, df = self.loader.load_lap(previous[0].lap_id)
            return descriptor, df, "previous_lap"

        timed = [lap for lap in candidates if lap.lap_time is not None and lap.lap_time > 20.0]
        if timed:
            best = min(timed, key=lambda lap: float(lap.lap_time or 9999.0))
            descriptor, df = self.loader.load_lap(best.lap_id)
            return descriptor, df, "best_available"

        if candidates:
            best = max(candidates, key=lambda lap: lap.sample_count)
            descriptor, df = self.loader.load_lap(best.lap_id)
            return descriptor, df, "largest_available"

        descriptor, df = self.loader.load_lap(target.lap_id)
        return descriptor, df, "self_baseline"

    def _track_data(self, target: LapDescriptor, reference: LapDescriptor) -> Optional[Dict[str, Any]]:
        active = self.runtime_state.track_data
        if active:
            return active

        track_cache_names = [
            (target.metadata.get("sessionMetadata") or {}).get("trackCache"),
            (reference.metadata.get("sessionMetadata") or {}).get("trackCache"),
            target.track,
            reference.track,
        ]
        for name in track_cache_names:
            if not name:
                continue
            cached = self.track_cache.load_track(name)
            if cached:
                return cached
        return None

    @staticmethod
    def _same_track(left: Optional[str], right: Optional[str]) -> bool:
        if not left or not right:
            return False
        return left.strip().lower() == right.strip().lower()

    @staticmethod
    def _track_length(track_data: Optional[Dict[str, Any]], target_df: pd.DataFrame, reference_df: pd.DataFrame) -> float:
        if track_data:
            length = finite_float(track_data.get("trackLength", track_data.get("track_length")))
            if length and length > 0:
                return length
        for df in (target_df, reference_df):
            if not df.empty and "track_length" in df:
                length = finite_float(df["track_length"].dropna().max())
                if length and length > 0:
                    return length
        return float(max(target_df["s"].max() if "s" in target_df else 1.0, reference_df["s"].max() if "s" in reference_df else 1.0, 1.0))

    @staticmethod
    def _validate_loaded_lap(descriptor: LapDescriptor, df: pd.DataFrame) -> Dict[str, Any]:
        if df.empty:
            raise ValueError(f"Lap {descriptor.lap_id} has no telemetry samples")
        progress = df["p"] if "p" in df else pd.Series(dtype=float)
        duration = descriptor.lap_time
        if duration is None and "elapsed_s" in df:
            duration = float(df["elapsed_s"].max() - df["elapsed_s"].min())
        validation = validate_lap(
            {
                "lapId": descriptor.lap_id,
                "lapNumber": descriptor.lap_number,
                "sampleCount": len(df),
                "durationSeconds": duration,
                "progressStart": float(progress.iloc[0]) if len(progress) else None,
                "progressEnd": float(progress.iloc[-1]) if len(progress) else None,
                "progressMin": float(progress.min()) if len(progress) else None,
                "progressMax": float(progress.max()) if len(progress) else None,
                "completed": True,
            }
        )
        if validation.status != "VALID":
            raise ValueError(f"Lap {descriptor.lap_id} is not valid for assisted analysis: {', '.join(validation.issues)}")
        return validation.to_api()

    @staticmethod
    def _optional_channels(metrics: Dict[int, CornerMetrics]) -> Dict[str, bool]:
        channels: Dict[str, bool] = {
            "steering": False,
            "gear": False,
            "rpm": False,
            "lateralG": False,
            "longitudinalG": False,
            "yaw": False,
            "yawRate": False,
        }
        for item in metrics.values():
            for key, value in item.optional_channels.items():
                channels[key] = channels.get(key, False) or bool(value)
        return channels

    @staticmethod
    def _top_losses(corners: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked = sorted(corners, key=lambda item: float(item.get("estimatedGainS") or item.get("lossS") or 0.0), reverse=True)
        return [
            {
                "cornerId": item["cornerId"],
                "name": item["name"],
                "lossS": item.get("lossS"),
                "estimatedGainS": item.get("estimatedGainS"),
                "primaryError": item.get("primaryError"),
                "phase": item.get("primaryPhase"),
                "concept": item.get("technicalConcept"),
                "physicalBehavior": item.get("physicalBehavior"),
                "feedback": item.get("feedback"),
            }
            for item in ranked[:5]
            if float(item.get("estimatedGainS") or item.get("lossS") or 0.0) > 0.0 or item.get("primaryError")
        ]

    def _external_reference_context(
        self,
        track: Optional[str],
        track_length: float,
        corners: List[Dict[str, Any]],
        external_reference_id: Optional[str],
    ) -> Dict[str, Any]:
        reference = (
            self.external_references.get(external_reference_id)
            if external_reference_id
            else self.external_references.select_best_for_track(track)
        )
        if not reference:
            return {
                "available": False,
                "reason": "no_external_reference_available",
                "comparisonMode": "internal_reference_only",
            }
        return self.external_mapper.build_context(reference, corners=corners, track_length=track_length)

    @staticmethod
    def _external_cache_key(include_external_reference: bool, external_reference_id: Optional[str]) -> str:
        if not include_external_reference:
            return "internal_only"
        return external_reference_id or "external_auto"

    def _cache_key(self, lap_id: str, reference_lap_id: Optional[str], external_key: str = "internal_only") -> str:
        return f"{self._hash(lap_id)}__{self._hash(reference_lap_id or 'default')}__{self._hash(external_key)}"

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]

    def _cache_path(self, cache_key: str) -> Path:
        return self.analysis_dir / f"{cache_key}.json"

    @classmethod
    def _json_safe(cls, value):
        item = getattr(value, "item", None)
        if callable(item):
            try:
                return item()
            except Exception:
                pass
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [cls._json_safe(item) for item in value]
        return value
