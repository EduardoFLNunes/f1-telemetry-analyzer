import json
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.kn5.kn5_reader import Kn5Reader

def extract_pitlane_surface(kn5_path: Path, pit_mesh_names: List[str] = ["1pitlane001", "1pitlane002", "1pitlane003"]) -> Dict[str, Any]:
    reader = Kn5Reader(kn5_path, role="pitlane", geometry_surfaces=["PITLANE"])
    inventory = reader.read_inventory()
    return _parse_mesh_geometry_full(kn5_path, pit_mesh_names)

def _parse_mesh_geometry_full(kn5_path: Path, pit_mesh_names: List[str]) -> Dict[str, Any]:
    from core.kn5.kn5_reader import _BinaryReader
    with open(kn5_path, "rb") as f: data = f.read()
    reader = _BinaryReader(data)
    
    def _parse_node():
        node_type = reader.u32()
        node_name = reader.string()
        if node_type == 1:
            child_count = reader.u32()
            reader.read(1 + 64) 
            for _ in range(child_count): _parse_node()
        elif node_type == 2:
            material_idx = reader.u32()
            flags = reader.u32()
            vert_count = reader.u32()
            if any(name in node_name for name in pit_mesh_names):
                vs = []
                for _ in range(vert_count):
                    v = reader.f32_tuple(3)
                    vs.append([v[0], -v[2]])
                    reader.seek(reader.tell() + 32)
                idx_count = reader.u32()
                idx_data = reader.read(idx_count * 2)
                import struct
                indices = struct.unpack(f'<{idx_count}H', idx_data)
                for i in range(0, len(indices), 3):
                    tri = [vs[indices[i]], vs[indices[i+1]], vs[indices[i+2]]]
                    extracted_triangles.append(tri)
                    for pt in tri:
                        bounds["minX"] = min(bounds["minX"], pt[0])
                        bounds["maxX"] = max(bounds["maxX"], pt[0])
                        bounds["minY"] = min(bounds["minY"], pt[1])
                        bounds["maxY"] = max(bounds["maxY"], pt[1])
            else:
                reader.seek(reader.tell() + vert_count * 44)
                idx_count = reader.u32()
                reader.read(idx_count * 2)
            if reader.remaining() >= 33: reader.read(33)

    reader.read(len(b"sc6969") + 4)
    tex_count = reader.u32()
    for _ in range(tex_count): reader.u32(); reader.string(); size = reader.u32(); reader.read(size)
    mat_count = reader.u32()
    for _ in range(mat_count):
        reader.string(); reader.string(); reader.read(6); v_count = reader.u32()
        for _ in range(v_count): reader.string(); reader.read(40)
        t_count = reader.u32()
        for _ in range(t_count): reader.string(); reader.read(4); reader.string()
        
    extracted_triangles = []
    bounds = {"minX": float('inf'), "maxX": float('-inf'), "minY": float('inf'), "maxY": float('-inf')}
    _parse_node()
    return {"triangles": extracted_triangles, "bounds": bounds, "meshNames": pit_mesh_names}

def parse_pit_lane_ai(ai_file_path: Path) -> List[Dict[str, float]]:
    points = []
    with open(ai_file_path, "rb") as f:
        f.read(8)
        import struct
        while True:
            data = f.read(72)
            if len(data) < 72: break
            floats = struct.unpack('<18f', data)
            # AC AI: x, y, z -> map space: x, -z
            points.append({"x": floats[0], "y": -floats[2]})
    return points

def build_svg(main_track, pit_surface, pit_centerline, output_path):
    min_x = min(pit_surface["bounds"]["minX"], -2000)
    max_x = max(pit_surface["bounds"]["maxX"], 2000)
    min_y = min(pit_surface["bounds"]["minY"], -2000)
    max_y = max(pit_surface["bounds"]["maxY"], 2000)
    
    padding = 50
    view_box = f"{min_x-padding} {min_y-padding} {max_x-min_x+2*padding} {max_y-min_y+2*padding}"
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_box}" width="1200" height="900" style="background:#0f172a">']
    
    if "left_edge" in main_track:
        left_pts = " ".join([f"{p['x']},{p['y']}" for p in main_track['left_edge']])
        right_pts = " ".join([f"{p['x']},{p['y']}" for p in main_track['right_edge']])
        svg.append(f'<polyline points="{left_pts}" fill="none" stroke="#475569" stroke-width="1" />')
        svg.append(f'<polyline points="{right_pts}" fill="none" stroke="#475569" stroke-width="1" />')
        
    for tri in pit_surface["triangles"]:
        pts = " ".join([f"{p[0]},{p[1]}" for p in tri])
        svg.append(f'<polygon points="{pts}" fill="#eab308" fill-opacity="0.3" stroke="none" />')
        
    if pit_centerline:
        cl_pts = " ".join([f"{p['x']},{p['y']}" for p in pit_centerline])
        svg.append(f'<polyline points="{cl_pts}" fill="none" stroke="#eab308" stroke-dasharray="4,4" stroke-width="1" />')
        svg.append(f'<circle cx="{pit_centerline[0]["x"]}" cy="{pit_centerline[0]["y"]}" r="5" fill="#f97316" />')
        svg.append(f'<circle cx="{pit_centerline[-1]["x"]}" cy="{pit_centerline[-1]["y"]}" r="5" fill="#38bdf8" />')
    svg.append("</svg>")
    output_path.write_text("\n".join(svg), encoding="utf-8")

def raycast_pitlane(centerline: List[Dict[str, float]], surface_triangles: List[List[List[float]]]) -> Dict[str, Any]:
    valid_left = []
    valid_right = []
    widths = []
    edges = []
    for tri in surface_triangles:
        edges.extend([(tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])])

    def intersect(p, direction):
        best_dist = float('inf')
        for a, b in edges:
            dx, dy = b[0] - a[0], b[1] - a[1]
            det = direction[0] * (-dy) - direction[1] * dx
            if abs(det) < 1e-9: continue
            t = ((a[0] - p[0]) * (-dy) - (a[1] - p[1]) * (-dx)) / det
            u = (direction[0] * (a[1] - p[1]) - direction[1] * (a[0] - p[0])) / det
            if t > 0 and 0 <= u <= 1:
                if t < best_dist: best_dist = t
        return best_dist if best_dist != float('inf') else None

    for i in range(len(centerline)):
        p = [centerline[i]["x"], centerline[i]["y"]]
        prev_p = [centerline[(i-1)%len(centerline)]["x"], centerline[(i-1)%len(centerline)]["y"]]
        next_p = [centerline[(i+1)%len(centerline)]["x"], centerline[(i+1)%len(centerline)]["y"]]
        tx, ty = next_p[0] - prev_p[0], next_p[1] - prev_p[1]
        length = np.hypot(tx, ty)
        tx, ty = tx/(length + 1e-9), ty/(length + 1e-9)
        nx, ny = -ty, tx
        
        left_dist = intersect(p, (-nx, -ny))
        right_dist = intersect(p, (nx, ny))
        
        if left_dist and right_dist:
            valid_left.append({"x": p[0] - nx * left_dist, "y": p[1] - ny * left_dist})
            valid_right.append({"x": p[0] + nx * right_dist, "y": p[1] + ny * right_dist})
            widths.append(left_dist + right_dist)
        else:
            valid_left.append(None)
            valid_right.append(None)
            widths.append(None)
    return {"left": valid_left, "right": valid_right, "widths": widths}
