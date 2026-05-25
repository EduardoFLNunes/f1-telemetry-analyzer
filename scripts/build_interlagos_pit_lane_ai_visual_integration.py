from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.geometry.interlagos_pit_lane_ai_visual import build_pit_lane_ai_visual_integration  # noqa: E402


def main() -> None:
    output_dir = REPO_ROOT / "data" / "debug"
    result = build_pit_lane_ai_visual_integration(REPO_ROOT, output_dir)
    print(
        {
            "alignment": str(output_dir / "interlagos_pit_lane_ai_alignment.json"),
            "alignmentSvg": str(output_dir / "interlagos_pit_lane_ai_alignment.svg"),
            "connectionPoints": str(output_dir / "interlagos_pit_lane_ai_connection_points.json"),
            "connectionPointsSvg": str(output_dir / "interlagos_pit_lane_ai_connection_points.svg"),
            "pitAccess": str(output_dir / "interlagos_pit_access_from_pit_lane_ai.json"),
            "pitAccessSvg": str(output_dir / "interlagos_pit_access_from_pit_lane_ai.svg"),
            "report": str(output_dir / "interlagos_pit_lane_ai_visual_integration_report.json"),
            "validation": result["report"]["validation"],
            "metrics": result["report"]["metrics"],
        }
    )


if __name__ == "__main__":
    main()
