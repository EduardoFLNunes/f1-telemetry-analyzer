from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .external_reference_models import ExternalReferenceError, ExternalReferenceLap
from .external_reference_normalizer import ExternalReferenceNormalizer
from .external_reference_repository import ExternalReferenceRepository


class FastF1ReferenceProvider:
    def __init__(
        self,
        repo_root: Path,
        repository: Optional[ExternalReferenceRepository] = None,
        *,
        cache_dir: Optional[Path] = None,
        normalizer: Optional[ExternalReferenceNormalizer] = None,
        fastf1_module: Any = None,
    ):
        self.repo_root = Path(repo_root)
        self.repository = repository or ExternalReferenceRepository(repo_root)
        self.cache_dir = Path(cache_dir) if cache_dir else self.repo_root / "data" / "fastf1_cache"
        self.normalizer = normalizer or ExternalReferenceNormalizer()
        self._fastf1_module = fastf1_module

    def import_reference(
        self,
        *,
        year: int = 2024,
        event: str = "Brazil",
        session: str = "Q",
        driver: Optional[str] = None,
        force: bool = False,
    ) -> ExternalReferenceLap:
        self._validate_selector(year, event, session)
        if not force:
            existing = self.repository.find_existing_fastf1(year=year, event=event, session=session, driver=driver)
            if existing:
                return existing

        fastf1 = self._load_fastf1()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            fastf1.Cache.enable_cache(str(self.cache_dir))
        except Exception as exc:
            raise ExternalReferenceError(f"FastF1 cache could not be enabled at {self.cache_dir}: {exc}") from exc

        try:
            session_obj = fastf1.get_session(int(year), event, session)
            session_obj.load(laps=True, telemetry=True, weather=False, messages=False)
            laps = session_obj.laps
            selected_laps = laps.pick_driver(driver) if driver else laps
            fastest_lap = selected_laps.pick_fastest()
            if fastest_lap is None or getattr(fastest_lap, "empty", False):
                raise ValueError("no fastest lap found")
            telemetry = fastest_lap.get_telemetry().add_distance()
        except Exception as exc:
            raise ExternalReferenceError(
                f"FastF1 reference unavailable for {year} {event} {session}: {exc}"
            ) from exc

        reference = self.normalizer.normalize_fastf1_telemetry(
            telemetry,
            year=int(year),
            event=event,
            session=session,
            driver=str(fastest_lap.get("Driver", driver or "FASTEST")),
            team=str(fastest_lap.get("Team", "")) or None,
            lap_number=self._int_or_none(fastest_lap.get("LapNumber")),
            lap_time=self._lap_time_seconds(fastest_lap.get("LapTime")),
            track="Interlagos" if _is_interlagos_event(event) else event,
        )
        return self.repository.save(reference)

    def _load_fastf1(self):
        if self._fastf1_module is not None:
            return self._fastf1_module
        try:
            import fastf1
        except Exception as exc:
            raise ExternalReferenceError(f"FastF1 is not available: {exc}") from exc
        return fastf1

    @staticmethod
    def _validate_selector(year: int, event: str, session: str) -> None:
        if int(year) < 2018:
            raise ExternalReferenceError("FastF1 telemetry references require year >= 2018")
        if not str(event or "").strip():
            raise ExternalReferenceError("FastF1 event is required")
        if not str(session or "").strip():
            raise ExternalReferenceError("FastF1 session is required")

    @staticmethod
    def _lap_time_seconds(value: Any) -> Optional[float]:
        if value is None:
            return None
        total_seconds = getattr(value, "total_seconds", None)
        if callable(total_seconds):
            try:
                return float(total_seconds())
            except Exception:
                return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _int_or_none(value: Any) -> Optional[int]:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _is_interlagos_event(event: str) -> bool:
    key = str(event or "").strip().lower()
    return any(token in key for token in ("brazil", "sao paulo", "são paulo", "interlagos"))
