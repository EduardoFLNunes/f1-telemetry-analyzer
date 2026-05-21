import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.pitlane_extraction import extract_pitlane_surface, parse_pit_lane_ai, build_svg
from core.geometry.track_geometry_provider import Kn5SurfaceTrackGeometryProvider
from core.cache.track_cache import TrackCache

def run_extraction_debug():
    track_name = "vhe_interlagos"
    track_config = "gp"
    
    # Paths
    kn5_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\vhe_interlagos.kn5")
    ai_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\gp\ai\pit_lane.ai")
    debug_dir = REPO_ROOT / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load Main Track for Reference
    cache = TrackCache(str(REPO_ROOT / "data" / "cache" / "tracks"))
    provider = Kn5SurfaceTrackGeometryProvider(cache)
    result = provider.load_or_build(track_name, track_config)
    main_track = result.track_data
    
    # 2. Extract Pitlane Surface
    pit_surface = extract_pitlane_surface(kn5_path)
    print(f"Extracted {len(pit_surface['triangles'])} pitlane triangles.")
    
    # 3. Parse PitLane AI
    pit_centerline = parse_pit_lane_ai(ai_path)
    print(f"Parsed {len(pit_centerline)} pitlane centerline points.")
    
    # 4. Generate SVG
    build_svg(main_track, pit_surface, pit_centerline, debug_dir / "interlagos_pitlane_surface_and_centerline.svg")
    print(f"Exported debug SVG to {debug_dir / 'interlagos_pitlane_surface_and_centerline.svg'}")

if __name__ == "__main__":
    run_extraction_debug()
