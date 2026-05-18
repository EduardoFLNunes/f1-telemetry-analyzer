import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from .kn5_models import Kn5FileInventory, Kn5TrackInventory, empty_file_inventory
from .kn5_reader import Kn5Reader


def _safe_name(value: Optional[str]) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (value or "unknown").strip())
    return cleaned.strip("_") or "unknown"


def _geometry_surface_order(surface_keys: List[str]) -> List[str]:
    upper = [str(key).upper() for key in surface_keys if key]
    ordered = [key for key in ("ROAD", "CURB", "KERB") if key in upper]
    ordered.extend(key for key in upper if key not in ordered)
    return ordered


def _model_transform(manifest: Dict[str, Any], target_path: Optional[str]) -> Dict[str, List[float]]:
    if not target_path:
        return {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}
    normalized_target = str(Path(target_path)).lower()
    for model in manifest.get("staticModels", []):
        absolute = model.get("absolutePath")
        if absolute and str(Path(absolute)).lower() == normalized_target:
            return {
                "position": list(model.get("position") or [0.0, 0.0, 0.0]),
                "rotation": list(model.get("rotation") or [0.0, 0.0, 0.0]),
            }
    return {"position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0]}


def _files_to_inspect(manifest: Dict[str, Any]) -> List[Dict[str, Optional[str]]]:
    candidates = manifest.get("candidateGeometryFiles", {}) or {}
    ordered = [
        {"role": "collider", "path": candidates.get("collider")},
        {"role": "visual", "path": candidates.get("mainVisual")},
        {"role": "groove", "path": candidates.get("groove")},
    ]
    seen = set()
    result = []
    for item in ordered:
        path = item.get("path")
        key = str(path).lower() if path else f"missing:{item['role']}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def build_kn5_inventory_from_manifest(manifest: Dict[str, Any]) -> Kn5TrackInventory:
    geometry_surfaces = _geometry_surface_order(manifest.get("geometrySurfaces") or ["ROAD", "CURB", "KERB"])
    files: List[Kn5FileInventory] = []
    diagnostics: List[Dict[str, Any]] = []

    for item in _files_to_inspect(manifest):
        role = item["role"] or "unknown"
        path = item.get("path")
        if not path:
            files.append(
                empty_file_inventory(
                    role,
                    None,
                    "missing_kn5",
                    f"No {role} KN5 was resolved by TrackFileResolver",
                )
            )
            continue
        transform = _model_transform(manifest, path)
        file_inventory = Kn5Reader(
            path,
            role=role,
            geometry_surfaces=geometry_surfaces,
            model_position=transform["position"],
            model_rotation=transform["rotation"],
        ).read_inventory()
        files.append(file_inventory)
        diagnostics.extend(
            {"file": file_inventory.path, "role": role, **diagnostic}
            for diagnostic in file_inventory.diagnostics
        )

    return Kn5TrackInventory(
        trackName=manifest.get("trackNameFromSharedMemory"),
        trackConfig=manifest.get("trackConfigFromSharedMemory"),
        geometrySurfaces=geometry_surfaces,
        sourceManifest={
            "acRoot": manifest.get("acRoot"),
            "trackFolder": manifest.get("trackFolder"),
            "modelsIni": manifest.get("modelsIni"),
            "surfacesIni": manifest.get("surfacesIni"),
            "candidateGeometryFiles": manifest.get("candidateGeometryFiles"),
        },
        files=files,
        diagnostics=diagnostics,
    )


def write_kn5_inventory_json(inventory: Kn5TrackInventory, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"kn5_inventory_{_safe_name(inventory.trackName)}.json"
    output_path.write_text(json.dumps(inventory.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
