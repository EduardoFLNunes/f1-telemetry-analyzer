from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_edges_from_surface import (  # noqa: E402
    build_track_edges_interval_raycast_from_manifest,
    build_track_edges_svg,
)
from core.track_file_resolver import TrackFileResolver  # noqa: E402


def main() -> None:
    track_name = sys.argv[1] if len(sys.argv) > 1 else "vhe_interlagos"
    track_config = sys.argv[2] if len(sys.argv) > 2 else "gp"
    manifest = TrackFileResolver().build_track_file_manifest(
        track_name,
        track_config,
        source="assetto_corsa",
        game_code="assetto_corsa",
    )
    result = build_track_edges_interval_raycast_from_manifest(manifest.to_dict())
    output_dir = REPO_ROOT / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"track_edges_interval_raycast_{track_name}.json"
    svg_path = output_dir / f"track_edges_interval_raycast_preview_{track_name}.svg"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    svg_path.write_text(build_track_edges_svg(result), encoding="utf-8")
    print({"json": str(json_path), "svg": str(svg_path), "metrics": result.get("metrics")})


if __name__ == "__main__":
    main()
