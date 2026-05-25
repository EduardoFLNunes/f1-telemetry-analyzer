from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.geometry.interlagos_track_only_fixed import build_fixed_geometry_from_cache  # noqa: E402


def main() -> None:
    base_cache = REPO_ROOT / "data" / "cache" / "tracks" / "vhe_interlagos_gp_kn5_surface_interval_geometry.json"
    output_dir = REPO_ROOT / "data" / "debug"
    result = build_fixed_geometry_from_cache(base_cache, output_dir)
    report = result["report"]
    print(
        {
            "geometry": str(output_dir / "interlagos_track_only_fixed_geometry.json"),
            "svg": str(output_dir / "interlagos_track_only_fixed_geometry.svg"),
            "beforeAfter": str(output_dir / "interlagos_track_only_fixed_before_after.svg"),
            "report": str(output_dir / "interlagos_track_only_fixed_report.json"),
            "validation": report.get("validation"),
            "metrics": report.get("metrics"),
        }
    )


if __name__ == "__main__":
    main()
