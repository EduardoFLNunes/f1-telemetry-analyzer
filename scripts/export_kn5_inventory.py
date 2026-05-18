from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.kn5_inventory import build_kn5_inventory_from_manifest, write_kn5_inventory_json
from core.track_file_resolver import TrackFileResolver


def main() -> None:
    track_name = sys.argv[1] if len(sys.argv) > 1 else "vhe_interlagos"
    track_config = sys.argv[2] if len(sys.argv) > 2 else "gp"
    manifest = TrackFileResolver().build_track_file_manifest(
        track_name,
        track_config,
        source="assetto_corsa",
        game_code="assetto_corsa",
    )
    inventory = build_kn5_inventory_from_manifest(manifest.to_dict())
    output = write_kn5_inventory_json(inventory, REPO_ROOT / "data" / "debug")
    print(output)


if __name__ == "__main__":
    main()
