from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.track_surface_polygon import (  # noqa: E402
    build_track_surface_polygon_from_manifest,
    write_track_surface_debug_files,
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
    surface = build_track_surface_polygon_from_manifest(manifest.to_dict())
    output = write_track_surface_debug_files(surface, REPO_ROOT / "data" / "debug")
    print(output)


if __name__ == "__main__":
    main()
