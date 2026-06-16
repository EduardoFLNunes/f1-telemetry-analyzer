from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .external_reference_models import ExternalReferenceLap, SOURCE_FASTF1


class ExternalReferenceRepository:
    def __init__(self, repo_root: Path, *, data_dir: Optional[Path] = None):
        self.repo_root = Path(repo_root)
        self.data_dir = Path(data_dir) if data_dir else self.repo_root / "data" / "external_references"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save(self, reference: ExternalReferenceLap) -> ExternalReferenceLap:
        path = self._path(reference.metadata.reference_id)
        reference.metadata.cache_path = str(path)
        path.write_text(json.dumps(reference.to_api(include_samples=True), ensure_ascii=False, indent=2), encoding="utf-8")
        return reference

    def get(self, reference_id: str) -> Optional[ExternalReferenceLap]:
        path = self._path(reference_id)
        if not path.exists():
            return None
        try:
            return ExternalReferenceLap.from_api(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None

    def list_references(self, *, include_samples: bool = False) -> List[Dict]:
        items = []
        for path in sorted(self.data_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                reference = ExternalReferenceLap.from_api(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            payload = reference.to_api(include_samples=include_samples)
            payload["metadata"]["cachePath"] = str(path)
            items.append(payload)
        return items

    def find_existing_fastf1(
        self,
        *,
        year: int,
        event: str,
        session: str,
        driver: Optional[str],
    ) -> Optional[ExternalReferenceLap]:
        event_key = _norm(event)
        session_key = _norm(session)
        driver_key = _norm(driver or "FASTEST")
        for item in self.list_references(include_samples=False):
            metadata = item.get("metadata", {})
            if metadata.get("source") != SOURCE_FASTF1:
                continue
            if int(metadata.get("year") or 0) != int(year):
                continue
            if _norm(metadata.get("event")) != event_key:
                continue
            if _norm(metadata.get("session")) != session_key:
                continue
            if driver and _norm(metadata.get("driver")) != driver_key:
                continue
            reference = self.get(metadata.get("referenceId"))
            if reference:
                return reference
        return None

    def select_best_for_track(self, track: Optional[str] = None) -> Optional[ExternalReferenceLap]:
        references = self.list_references(include_samples=False)
        if not references:
            return None
        track_key = _norm(track or "")
        interlagos_track = "interlagos" in track_key or "sao_paulo" in track_key or "sao" in track_key
        preferred = []
        for item in references:
            metadata = item.get("metadata", {})
            ref_track = _norm(metadata.get("track") or metadata.get("event") or "")
            is_interlagos_ref = any(token in ref_track for token in ("interlagos", "brazil", "sao_paulo", "sao"))
            if not track_key or (interlagos_track and is_interlagos_ref) or (track_key and track_key in ref_track):
                preferred.append(item)
        selected = preferred[0] if preferred else references[0]
        return self.get(selected.get("metadata", {}).get("referenceId"))

    def _path(self, reference_id: str) -> Path:
        safe = "".join(char if char.isalnum() or char in "._-" else "_" for char in str(reference_id))
        return self.data_dir / f"{safe}.json"


def _norm(value: Optional[str]) -> str:
    return str(value or "").strip().lower().replace(" ", "_")
