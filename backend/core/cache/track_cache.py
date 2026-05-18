import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Dict, Any
from .cache_serializer import CacheSerializer

class TrackCache:
    def __init__(self, cache_dir: str = "data/cache/tracks"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, track_name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", track_name.strip())
        return cleaned or "reconstructed_track"

    def compute_source_hash(self, track_data: Dict[str, Any]) -> str:
        centerline = track_data.get("centerline", [])
        payload = {
            "length": round(float(track_data.get("trackLength", track_data.get("track_length", 0.0))), 3),
            "points": len(centerline),
            "bbox": self._bbox(track_data),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()

    def _bbox(self, track_data: Dict[str, Any]):
        pts = track_data.get("centerline", [])
        xs = []
        zs = []
        for p in pts:
            if hasattr(p, "x"):
                xs.append(float(p.x))
                zs.append(float(p.z))
            else:
                xs.append(float(p["x"]))
                zs.append(float(p.get("z", p.get("y", 0.0))))
        if not xs or not zs:
            return []
        return [round(min(xs), 2), round(min(zs), 2), round(max(xs), 2), round(max(zs), 2)]

    def save_track(self, track_name: str, track_data: Dict[str, Any]):
        file_path = self.cache_dir / f"{self._safe_name(track_name)}.json"
        source_hash = self.compute_source_hash(track_data)
        serialized = CacheSerializer.serialize_track(track_data, source_hash=source_hash)
        file_path.write_text(serialized, encoding="utf-8")
        return file_path

    def load_track(self, track_name: str) -> Optional[Dict[str, Any]]:
        file_path = self.cache_dir / f"{self._safe_name(track_name)}.json"
        if not file_path.exists():
            return None
        return CacheSerializer.deserialize_track(file_path.read_text(encoding="utf-8"))

    def is_valid(self, track_name: str, track_data: Dict[str, Any], tolerance_ratio: float = 0.03) -> bool:
        cached = self.load_track(track_name)
        if not cached:
            return False

        cached_len = float(cached.get("trackLength", 0.0))
        current_len = float(track_data.get("trackLength", track_data.get("track_length", 0.0)))
        if cached_len <= 0 or current_len <= 0:
            return False
        return abs(cached_len - current_len) / cached_len <= tolerance_ratio

    def list_cached_tracks(self) -> list:
        return [
            {
                "trackName": f.stem,
                "path": str(f),
                "bytes": f.stat().st_size,
                "modifiedAt": f.stat().st_mtime,
            }
            for f in self.cache_dir.glob("*.json")
        ]
