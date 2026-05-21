import json
import math
import struct
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from collections import defaultdict

# Setup paths to include backend
REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.kn5.kn5_reader import _BinaryReader, _transform_point, _normalize_surface_order, KN5_MAGIC, KN5_MESH_FOOTER_BYTES, KN5_STATIC_VERTEX_STRIDE, Kn5ParseError, _match_surface
from core.kn5.kn5_inventory import _model_transform
from core.track_file_resolver import TrackFileResolver
from core.ac_track_loader import ACTrackLoader
from core.geometry.track_geometry_cleanup import audit_geometry, stats

def _map_point(world: Sequence[float]) -> List[float]:
    return [round(float(world[0]), 6), round(float(-world[2]), 6)]

class DiagnosticPolygonBuilder:
    def __init__(self, kn5_path: Path, transform: Dict[str, Any]):
        self.path = kn5_path
        self.model_position = transform["position"]
        self.model_rotation = transform["rotation"]
        self.reader = _BinaryReader(self.path.read_bytes())
        self.materials: List[str] = []
        self.triangles: List[Dict[str, Any]] = []
        self.meshes: List[Dict[str, Any]] = []

    def run(self):
        self._parse_header()
        self._parse_materials()
        self._parse_node("")

    def _parse_header(self) -> None:
        reader = self.reader
        magic = reader.read(len(KN5_MAGIC))
        if magic != KN5_MAGIC:
            raise Kn5ParseError(f"Invalid KN5 magic {magic!r}")
        _version = reader.u32()
        texture_count = reader.u32()
        for _ in range(texture_count):
            _texture_type = reader.u32()
            _texture_name = reader.string()
            size = reader.u32()
            reader.read(size)

    def _parse_materials(self) -> None:
        reader = self.reader
        material_count = reader.u32()
        for _ in range(material_count):
            name = reader.string()
            _shader = reader.string()
            reader.read(6)
            var_count = reader.u32()
            for _ in range(var_count):
                _var_name = reader.string()
                reader.read(40)
            texture_mapping_count = reader.u32()
            for _ in range(texture_mapping_count):
                _slot = reader.string()
                reader.read(4)
                _texture_name = reader.string()
            self.materials.append(name)

    def _parse_node(self, parent_path: str) -> None:
        reader = self.reader
        node_type = reader.u32()
        node_name = reader.string()
        node_path = f"{parent_path}/{node_name}" if parent_path else node_name

        if node_type == 1:
            child_count = reader.u32()
            _active = reader.u8()
            _transform = reader.f32_tuple(16)
            for _ in range(child_count):
                self._parse_node(node_path)
            return

        if node_type == 2:
            self._parse_static_mesh(node_name, node_path)
            return

    def _parse_static_mesh(self, mesh_name: str, node_path: str) -> None:
        reader = self.reader
        material_index = reader.u32()
        _mesh_flags = reader.u32()
        vertex_count = reader.u32()
        material = self.materials[material_index] if 0 <= material_index < len(self.materials) else None
        
        vertices: List[List[float]] = []
        for _ in range(vertex_count):
            x, y, z = struct.unpack_from("<3f", reader.data, reader.tell())
            world = _transform_point((x, y, z), self.model_position, self.model_rotation)
            vertices.append(_map_point(world))
            reader.seek(reader.tell() + KN5_STATIC_VERTEX_STRIDE)

        index_count = reader.u32()
        raw_indices = reader.read(index_count * 2)
        indices = list(struct.unpack(f"<{index_count}H", raw_indices)) if index_count else []
        if reader.remaining() >= KN5_MESH_FOOTER_BYTES:
            reader.read(KN5_MESH_FOOTER_BYTES)

        for tri_start in range(0, len(indices) - 2, 3):
            tri_indices = indices[tri_start : tri_start + 3]
            if any(index >= len(vertices) for index in tri_indices):
                continue
            points = [vertices[index] for index in tri_indices]
            self.triangles.append({
                "mesh": mesh_name,
                "material": material,
                "vertices": points,
            })
        
        self.meshes.append({
            "meshName": mesh_name,
            "material": material,
            "triangleCount": index_count // 3
        })

def is_strict_main_track(mesh_name: str) -> bool:
    name = mesh_name.lower()
    # include: ^1road, ^1curb, ^1kerb
    if not (name.startswith("1road") or name.startswith("1curb") or name.startswith("1kerb")):
        return False
    # exclude: roadline*, roadlineout, roadverge, pitlane*, auxiliary
    if any(token in name for token in ["roadline", "roadverge", "pitlane"]):
        return False
    return True

def is_current_filter(mesh_name: str, material_name: Optional[str]) -> bool:
    haystack = f"{mesh_name or ''} {material_name or ''}".upper()
    return any(key in haystack for key in ["ROAD", "CURB", "KERB"])

def get_mesh_type(mesh_name: str, material_name: Optional[str]) -> str:
    name = mesh_name.lower()
    if "roadline" in name: return "roadline"
    if "roadverge" in name: return "roadverge"
    if is_strict_main_track(mesh_name): return "strict"
    if is_current_filter(mesh_name, material_name): return "current_other"
    return "other"

def build_svg(
    triangles: List[Dict[str, Any]], 
    fast_lane: Optional[Dict[str, Any]], 
    pit_lane: Optional[Dict[str, Any]],
    title: str,
    output_path: Path
):
    all_points = []
    for tri in triangles:
        all_points.extend(tri["vertices"])
    if fast_lane:
        all_points.extend(zip(fast_lane["x"], [-z for z in fast_lane["z"]]))
    if pit_lane:
        all_points.extend(zip(pit_lane["x"], [-z for z in pit_lane["z"]]))

    if not all_points:
        return

    min_x = min(p[0] for p in all_points)
    max_x = max(p[0] for p in all_points)
    min_y = min(p[1] for p in all_points)
    max_y = max(p[1] for p in all_points)

    margin = 40
    width, height = 1200, 1000
    scale = min((width - margin * 2) / max(max_x - min_x, 1.0), (height - margin * 2) / max(max_y - min_y, 1.0))

    def sx(p: Sequence[float]) -> Tuple[float, float]:
        x = margin + (p[0] - min_x) * scale
        y = height - margin - (p[1] - min_y) * scale
        return x, y

    colors = {
        "roadline": "#ffff00",  # Yellow
        "roadverge": "#ffa500", # Orange
        "strict": "#00ff00",    # Green (pista principal strict)
        "current_other": "#808080", # Gray (geometria atual que não é strict)
        "other": "#333333"
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
        f'<text x="24" y="32" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="20">{title}</text>'
    ]

    # Draw triangles
    for tri in triangles:
        m_type = get_mesh_type(tri["mesh"], tri["material"])
        fill = colors.get(m_type, "#333333")
        opacity = "0.7" if m_type in ["strict", "roadline", "roadverge"] else "0.3"
        points = [sx(p) for p in tri["vertices"]]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(f'<polygon points="{point_text}" fill="{fill}" fill-opacity="{opacity}" stroke="none"/>')

    # Draw AI splines
    if fast_lane:
        pts = [sx((x, -z)) for x, z in zip(fast_lane["x"], fast_lane["z"])]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        parts.append(f'<polyline points="{point_text}" fill="none" stroke="#27d8ff" stroke-width="1.5" stroke-opacity="0.9" stroke-dasharray="5,5"/>')
        parts.append(f'<text x="24" y="60" fill="#27d8ff" font-size="12">Fast Lane (AI)</text>')

    if pit_lane:
        pts = [sx((x, -z)) for x, z in zip(pit_lane["x"], pit_lane["z"])]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
        parts.append(f'<polyline points="{point_text}" fill="none" stroke="#ff4aa3" stroke-width="1.5" stroke-opacity="0.9"/>')
        parts.append(f'<text x="24" y="80" fill="#ff4aa3" font-size="12">Pit Lane (AI)</text>')

    # Legend
    parts.append('<g transform="translate(1000, 50)">')
    y_off = 0
    for label, color in [("Strict Main", "#00ff00"), ("Roadline", "#ffff00"), ("Roadverge", "#ffa500"), ("Current Other", "#808080")]:
        parts.append(f'<rect x="0" y="{y_off}" width="20" height="10" fill="{color}"/>')
        parts.append(f'<text x="30" y="{y_off+10}" fill="#d9e6f2" font-size="12">{label}</text>')
        y_off += 20
    parts.append('</g>')

    parts.append("</svg>")
    output_path.write_text("\n".join(parts), encoding="utf-8")

def run_diagnosis():
    track_name = "vhe_interlagos"
    track_config = "gp"
    resolver = TrackFileResolver()
    manifest = resolver.build_track_file_manifest(track_name, track_config)
    main_visual = manifest.candidateGeometryFiles.get("mainVisual")
    
    if not main_visual:
        print("Error: Main visual KN5 not found")
        return

    transform = _model_transform(manifest.to_dict(), main_visual)
    print(f"Loading KN5: {main_visual}")
    builder = DiagnosticPolygonBuilder(Path(main_visual), transform)
    builder.run()

    # AI files
    loader = ACTrackLoader()
    try:
        track_data = loader.load_track(track_name, track_config)
        fast_lane = track_data.get("centerline")
        pit_lane = track_data.get("pit_lane")
    except Exception as e:
        print(f"Warning: Could not load AI files: {e}")
        fast_lane = None
        pit_lane = None

    # Filtering
    all_triangles = builder.triangles
    strict_triangles = [t for t in all_triangles if is_strict_main_track(t["mesh"])]
    current_triangles = [t for t in all_triangles if is_current_filter(t["mesh"], t["material"])]
    
    # Metrics comparison
    def get_metrics(triangles):
        if not triangles:
            return {}
        # Simple boundary loop count (edges with only one triangle)
        edge_counts = defaultdict(int)
        for tri in triangles:
            pts = tri["vertices"]
            for i in range(3):
                p1, p2 = pts[i], pts[(i+1)%3]
                # Quantize for robustness
                edge = tuple(sorted((round(p1[0], 3), round(p1[1], 3), round(p2[0], 3), round(p2[1], 3))))
                edge_counts[edge] += 1
        
        boundary_edges = [e for e, c in edge_counts.items() if c == 1]
        
        return {
            "triangleCount": len(triangles),
            "meshCount": len(set(t["mesh"] for t in triangles)),
            "boundaryEdgeCount": len(boundary_edges)
        }

    comparison = {
        "track": track_name,
        "config": track_config,
        "current": get_metrics(current_triangles),
        "strict": get_metrics(strict_triangles),
        "keptMeshes": sorted(list(set(t["mesh"] for t in strict_triangles))),
        "removedMeshes": sorted(list(set(t["mesh"] for t in current_triangles) - set(t["mesh"] for t in strict_triangles)))
    }

    # Generate Reports
    debug_dir = REPO_ROOT / "data" / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = debug_dir / "main_track_mesh_filter_comparison.json"
    json_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    
    # Runtime debug names as requested
    svg_path = debug_dir / "main_track_current_vs_strict_runtime.svg"
    build_svg(current_triangles, fast_lane, pit_lane, "Current vs Strict Filter Comparison (Runtime)", svg_path)
    
    artifact_svg_path = debug_dir / "pit_entry_exit_artifact_candidates.svg"
    # Filter triangles near pit lane or marked as roadline/roadverge
    artifact_triangles = [t for t in current_triangles if get_mesh_type(t["mesh"], t["material"]) in ["roadline", "roadverge", "current_other"]]
    build_svg(artifact_triangles, fast_lane, pit_lane, "Pit Entry/Exit Artifact Candidates", artifact_svg_path)

    # Also save the original name for compatibility if needed
    (debug_dir / "main_track_current_vs_strict.svg").write_text(svg_path.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"Reports generated in {debug_dir}")
    print(f"- {json_path.name}")
    print(f"- {svg_path.name}")
    print(f"- {artifact_svg_path.name}")

if __name__ == "__main__":
    run_diagnosis()
