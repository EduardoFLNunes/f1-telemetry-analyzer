import sys
from pathlib import Path
import json
import math

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.pitlane_extraction import extract_pitlane_surface, parse_pit_lane_ai, build_svg, raycast_pitlane
from core.geometry.track_geometry_provider import Kn5SurfaceTrackGeometryProvider
from core.cache.track_cache import TrackCache

def run_extraction_full():
    track_name = "vhe_interlagos"
    track_config = "gp"
    kn5_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\vhe_interlagos.kn5")
    ai_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\gp\ai\pit_lane.ai")
    debug_dir = REPO_ROOT / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load Main Track for Reference
    cache = TrackCache(str(REPO_ROOT / "data" / "cache" / "tracks"))
    provider = Kn5SurfaceTrackGeometryProvider(cache)
    result = provider.load_or_build(track_name, track_config)
    main_track = result.track_data
    
    # 2. Extract Data
    pit_surface = extract_pitlane_surface(kn5_path)
    pit_centerline = parse_pit_lane_ai(ai_path)
    
    # 3. Raycast Edges
    raycast = raycast_pitlane(pit_centerline, pit_surface["triangles"])
    
    # 4. Metrics & Validation
    valid_widths = [w for w in raycast["widths"] if w is not None]
    
    # Simple candidates: start/end of AI
    report = {
        "pitLaneAiFound": True,
        "pitLaneAiPointCount": len(pit_centerline),
        "pitMeshesFound": True,
        "pitMeshNames": pit_surface["meshNames"],
        "pitSurfaceTriangleCount": len(pit_surface["triangles"]),
        "pitSurfaceBounds": pit_surface["bounds"],
        "pitLaneStartPoint": pit_centerline[0],
        "pitLaneEndPoint": pit_centerline[-1],
        "raycastValidCount": len(valid_widths),
        "raycastFailedCount": len(raycast["widths"]) - len(valid_widths),
        "pitWidthMin": min(valid_widths) if valid_widths else 0,
        "pitWidthAvg": sum(valid_widths)/len(valid_widths) if valid_widths else 0,
        "pitWidthMax": max(valid_widths) if valid_widths else 0,
        "pitEntryCandidate": pit_centerline[0],
        "pitExitCandidate": pit_centerline[-1],
    }
    
    # 5. Export
    (debug_dir / "interlagos_pitlane_extraction_report.json").write_text(json.dumps(report, indent=2))
    
    # 6. Final SVG
    # (Reusing build_svg, adding edges)
    # ...
    print(f"Extraction complete. Report at {debug_dir / 'interlagos_pitlane_extraction_report.json'}")

if __name__ == "__main__":
    run_extraction_full()
