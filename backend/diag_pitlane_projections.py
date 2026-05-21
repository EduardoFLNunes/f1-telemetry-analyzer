import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List
from core.kn5.pitlane_extraction import extract_pitlane_surface, parse_pit_lane_ai

def get_distance(p, surface_triangles):
    # Min distance to any segment in surface
    min_dist = float('inf')
    for tri in surface_triangles:
        segments = [(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])]
        for a, b in segments:
            # point-to-segment distance 2D
            ba = np.array(b) - np.array(a)
            pa = np.array(p) - np.array(a)
            h = np.clip(np.dot(pa, ba) / np.dot(ba, ba), 0, 1)
            dist = np.linalg.norm(pa - ba * h)
            min_dist = min(min_dist, dist)
    return min_dist

def test_projections(surface, ai_points):
    # Projections: (x, -z), (x, z), (z, -x), (-x, -z)
    # Actually, raw_points[0] is x, raw_points[1] is -z (from previous parsing)
    # Let's re-parse raw to test variations
    results = {}
    
    # Original AI points (parsed) are list of {"x": ..., "y": -z}
    # We need access to raw floats to test variants
    # For now, let's just apply transformations on the parsed points
    
    # Actually, simpler: define transformations on (x, z)
    # A: (x, -z) [Current]
    # B: (x, z)
    # C: (z, -x)
    # D: (-x, -z)
    
    # I need access to raw (x, z) data from AI parser
    # I will modify parse_pit_lane_ai to return (x, z) tuple
    pass

# Update implementation for diagnostics
def run_diagnostic():
    kn5_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\vhe_interlagos.kn5")
    ai_path = Path(r"D:\SteamLibrary\steamapps\common\assettocorsa\content\tracks\vhe_interlagos\gp\ai\pit_lane.ai")
    
    pit_surface = extract_pitlane_surface(kn5_path)
    
    # Raw AI points (x, z)
    raw_ai = []
    with open(ai_path, "rb") as f:
        f.read(8)
        import struct
        for _ in range(1361): # known count
            floats = struct.unpack('<18f', f.read(72))
            raw_ai.append((floats[0], floats[2])) # x, z
            
    projections = {
        "A (x, -z)": [(p[0], -p[1]) for p in raw_ai],
        "B (x, z)": [(p[0], p[1]) for p in raw_ai],
        "C (z, -x)": [(p[1], -p[0]) for p in raw_ai],
        "D (-x, -z)": [(-p[0], -p[1]) for p in raw_ai]
    }
    
    report = {}
    for name, points in projections.items():
        dists = [get_distance(p, pit_surface["triangles"]) for p in points]
        report[name] = {
            "nearestDistanceAvg": float(np.mean(dists)),
            "nearestDistanceP95": float(np.percentile(dists, 95)),
            "pointsInside": int(sum(1 for d in dists if d < 0.1))
        }
        
    (Path("data/debug/interlagos_pitlane_projection_candidates.json")).write_text(json.dumps(report, indent=2))
    print("Done")

if __name__ == "__main__":
    run_diagnostic()
