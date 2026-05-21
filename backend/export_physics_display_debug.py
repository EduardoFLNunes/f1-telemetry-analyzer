import os
import json
import sys
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.track_file_resolver import TrackFileResolver
from core.geometry.track_geometry_provider import Kn5SurfaceTrackGeometryProvider, kn5_surface_cache_name, track_geometry_cleanup_enabled
from core.cache.track_cache import TrackCache
from core.geometry.physics_display import generate_physics_display_geometry, calculate_physics_display_metrics

def build_comparison_svg(raw_track, display_geo, title, output_path):
    import math
    
    raw_center = [[p.x, -p.z] for p in raw_track.get("centerline", [])]
    display_center = [[p["x"], p["y"]] for p in display_geo.get("centerline", [])]
    display_left = [[p["x"], p["y"]] for p in display_geo.get("leftEdge", [])]
    display_right = [[p["x"], p["y"]] for p in display_geo.get("rightEdge", [])]
    
    all_points = raw_center + display_center + display_left + display_right
    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)
    
    width = max_x - min_x
    height = max_y - min_y
    padding = max(width, height) * 0.05
    
    view_box = f"{min_x - padding} {min_y - padding} {width + 2*padding} {height + 2*padding}"
    
    def to_points_str(pts):
        return " ".join([f"{p[0]},{p[1]}" for p in pts])

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" width="1200" height="900" style="background:#0f172a">',
        f'<text x="{min_x}" y="{min_y - padding/2}" fill="white" font-family="sans-serif" font-size="20">{title}</text>',
        # Raw Physics (red dashed)
        f'<polyline points="{to_points_str(raw_center)}" fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="5,5" opacity="0.5" />',
        # Display Surface
        f'<polygon points="{to_points_str(display_left + display_right[::-1])}" fill="#1e293b" stroke="#334155" stroke-width="1" />',
        # Display Edges
        f'<polyline points="{to_points_str(display_left)}" fill="none" stroke="#f472b6" stroke-width="1.5" />',
        f'<polyline points="{to_points_str(display_right)}" fill="none" stroke="#fbbf24" stroke-width="1.5" />',
        # Display Centerline
        f'<polyline points="{to_points_str(display_center)}" fill="none" stroke="#38bdf8" stroke-width="1" opacity="0.8" />',
        '</svg>'
    ]
    
    output_path.write_text("\n".join(svg), encoding="utf-8")

def run_debug_export():
    track_name = "vhe_interlagos"
    track_config = "gp"
    debug_dir = REPO_ROOT / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Load authoritative track
    cache = TrackCache(str(REPO_ROOT / "data" / "cache" / "tracks"))
    # Ensure we use strict mode
    os.environ["TRACK_KN5_STRICT_MAIN_TRACK"] = "true"
    
    provider = Kn5SurfaceTrackGeometryProvider(cache)
    result = provider.load_or_build(track_name, track_config)
    if not result:
        print("Failed to load track")
        return
        
    track_data = result.track_data
    display_geo = track_data.get("physicsDisplayGeometry")
    
    if not display_geo:
        print("Physics Display Geometry missing in track data")
        return

    # 1. physics_display_geometry_preview.svg
    # (just the display geometry)
    build_comparison_svg(track_data, display_geo, f"Physics Display Geometry: {track_name}", debug_dir / "physics_display_geometry_preview.svg")
    
    # 2. physics_raw_vs_display.svg
    # (shows both for comparison)
    build_comparison_svg(track_data, display_geo, f"Physics Raw (Red) vs Display (Cyan): {track_name}", debug_dir / "physics_raw_vs_display.svg")
    
    # 3. physics_display_metrics.json
    metrics = track_data.get("physicsDisplayMetrics")
    (debug_dir / "physics_display_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    
    print(f"Debug files exported to {debug_dir}")

if __name__ == "__main__":
    run_debug_export()
