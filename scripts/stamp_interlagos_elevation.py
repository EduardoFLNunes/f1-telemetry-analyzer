"""Write the track elevation into the shipped Interlagos geometry.

The consolidated asset was built through a pipeline that projects to a flat map
at its first step, so every centreline sample carries y = 0. The height was
never derived, only dropped: fast_lane.ai has it, and for this track its point
count matches the centreline one for one.

Run once against an Assetto Corsa install; the result is committed, so the
packaged app needs no track files to draw the elevation.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from core.geometry import interlagos_track_only_fixed as fx  # noqa: E402
from core.kn5.track_edges_from_surface import parse_fast_lane_ai  # noqa: E402
from core.track_file_resolver import TrackFileResolver  # noqa: E402

TARGET = ROOT / "data" / "debug" / "interlagos_consolidated_geometry.json"


def main() -> int:
    track = fx.load_fixed_geometry(ROOT)
    if not track:
        print("geometria consolidada nao encontrada")
        return 1

    manifest = TrackFileResolver().build_track_file_manifest("vhe_interlagos", "gp").to_dict()
    ai_path = (manifest.get("aiFiles") or {}).get("fast_lane")
    ai = parse_fast_lane_ai(ai_path)
    if not ai["pointCount"]:
        print(f"fast_lane.ai indisponivel: {ai['diagnostics']}")
        return 1

    centerline = track["centerline"]
    ai_points = ai["points"]
    if len(ai_points) != len(centerline):
        print(f"contagem divergente: ai {len(ai_points)} vs centerline {len(centerline)}")
        return 1

    # The AI line is the longitudinal reference the geometry was built from, so
    # sample i of one is sample i of the other. Verified rather than assumed.
    ai_map = np.array([point["mapPosition"] for point in ai_points], dtype=float)
    center_map = np.array([[point.x, -point.z] for point in centerline], dtype=float)
    drift = np.sqrt(((ai_map - center_map) ** 2).sum(axis=1))
    print(f"desvio lateral entre a linha do AI e a centerline: mediana {np.median(drift):.2f} m | "
          f"p95 {np.percentile(drift, 95):.2f} m | max {drift.max():.2f} m")
    if np.median(drift) > 6.0:
        print("as duas nao estao alinhadas; abortando")
        return 1

    for point, ai_point in zip(centerline, ai_points):
        point.y = float(ai_point["worldPosition"][1])

    heights = np.array([point.y for point in centerline])
    print(f"altura gravada: min {heights.min():.2f} m | max {heights.max():.2f} m | "
          f"desnivel {heights.max() - heights.min():.2f} m")

    track.setdefault("metadata", {})["elevationSource"] = "fast_lane.ai worldPosition.y"
    TARGET.write_text(fx.serialize_consolidated_geometry(track), encoding="utf-8")
    print(f"gravado em {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
