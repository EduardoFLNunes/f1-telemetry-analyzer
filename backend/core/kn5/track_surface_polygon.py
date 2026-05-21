import json
import math
import os
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kn5_inventory import _model_transform
from .kn5_reader import (
    KN5_MAGIC,
    KN5_MESH_FOOTER_BYTES,
    KN5_STATIC_VERTEX_STRIDE,
    Kn5ParseError,
    _BinaryReader,
    _match_surface,
    _normalize_surface_order,
    _transform_point,
)


INCLUDED_SURFACES = ["ROAD", "CURB", "KERB"]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _map_point(world: Sequence[float]) -> List[float]:
    return [round(float(world[0]), 6), round(float(-world[2]), 6)]


def _bounds2() -> Tuple[List[float], List[float]]:
    return [float("inf"), float("inf")], [float("-inf"), float("-inf")]


def _update_bounds2(minimum: List[float], maximum: List[float], point: Sequence[float]) -> None:
    minimum[0] = min(minimum[0], float(point[0]))
    minimum[1] = min(minimum[1], float(point[1]))
    maximum[0] = max(maximum[0], float(point[0]))
    maximum[1] = max(maximum[1], float(point[1]))


def _bounds_payload(minimum: Sequence[float], maximum: Sequence[float]) -> Dict[str, float]:
    min_x, min_y = float(minimum[0]), float(minimum[1])
    max_x, max_y = float(maximum[0]), float(maximum[1])
    return {
        "minX": round(min_x, 6),
        "maxX": round(max_x, 6),
        "minY": round(min_y, 6),
        "maxY": round(max_y, 6),
        "width": round(max_x - min_x, 6),
        "height": round(max_y - min_y, 6),
    }


def _triangle_area2d(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5


def _quantized(point: Sequence[float], precision: int = 3) -> Tuple[int, int]:
    scale = 10**precision
    return int(round(float(point[0]) * scale)), int(round(float(point[1]) * scale))


class Kn5TrackSurfacePolygonBuilder:
    def __init__(
        self,
        path: str,
        *,
        included_surfaces: Sequence[str],
        model_position: Optional[Sequence[float]] = None,
        model_rotation: Optional[Sequence[float]] = None,
    ):
        self.path = Path(path)
        self.included_surfaces = _normalize_surface_order(included_surfaces)
        self.model_position = list(model_position or [0.0, 0.0, 0.0])
        self.model_rotation = list(model_rotation or [0.0, 0.0, 0.0])
        self.reader: Optional[_BinaryReader] = None
        self.materials: List[str] = []
        self.meshes: List[Dict[str, Any]] = []
        self.triangles: List[Dict[str, Any]] = []
        self.diagnostics: List[Dict[str, Any]] = []
        self.bounds_min, self.bounds_max = _bounds2()

    def build(self, track_name: Optional[str], track_config: Optional[str]) -> Dict[str, Any]:
        if not self.path.exists():
            return self._payload(track_name, track_config, outline=[], diagnostics=[{"code": "missing_kn5", "message": "Visual KN5 file missing", "path": str(self.path)}])
        try:
            self.reader = _BinaryReader(self.path.read_bytes())
            self._parse_header()
            self._parse_materials()
            self._parse_node("")
        except Exception as exc:
            self._diagnostic("track_surface_polygon_failed", str(exc))

        outline_segments = self._boundary_segments()
        return self._payload(track_name, track_config, outline_segments, self.diagnostics)

    def _payload(
        self,
        track_name: Optional[str],
        track_config: Optional[str],
        outline: List[Dict[str, List[float]]],
        diagnostics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        bounds = None if not self.triangles else _bounds_payload(self.bounds_min, self.bounds_max)
        return {
            "trackName": track_name,
            "trackConfig": track_config,
            "source": str(self.path),
            "projection": "mapX = worldX, mapY = -worldZ",
            "includedSurfaceKeys": self.included_surfaces,
            "meshCount": len(self.meshes),
            "triangleCount": len(self.triangles),
            "bounds": bounds,
            "meshes": self.meshes,
            "triangles": self.triangles,
            "outline": {
                "segmentCount": len(outline),
                "segments": outline,
            },
            "diagnostics": diagnostics,
        }

    def _parse_header(self) -> None:
        reader = self._require_reader()
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
        reader = self._require_reader()
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
        reader = self._require_reader()
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

        raise Kn5ParseError(f"Unsupported KN5 node type {node_type} for node {node_path}")

    def _parse_static_mesh(self, mesh_name: str, node_path: str) -> None:
        reader = self._require_reader()
        material_index = reader.u32()
        _mesh_flags = reader.u32()
        vertex_count = reader.u32()
        material = self.materials[material_index] if 0 <= material_index < len(self.materials) else None
        matched_surface = _match_surface(mesh_name, material, self.included_surfaces)
        should_capture = matched_surface is not None

        if should_capture and matched_surface in ["ROAD", "CURB", "KERB"]:
            name_lower = mesh_name.lower()
            
            # Strict mode: Only ^1road, ^1curb, ^1kerb
            if _env_bool("TRACK_KN5_STRICT_MAIN_TRACK", False):
                # Check if it starts with 1road, 1curb, or 1kerb
                if not (name_lower.startswith("1road") or name_lower.startswith("1curb") or name_lower.startswith("1kerb")):
                    should_capture = False
            
            # Additional explicit exclusions
            if should_capture:
                if _env_bool("TRACK_KN5_EXCLUDE_AUX_ROADLINE", False) and "roadline" in name_lower:
                    should_capture = False
                if _env_bool("TRACK_KN5_EXCLUDE_ROADVERGE", False) and "roadverge" in name_lower:
                    should_capture = False
                
                # Pitlane is NEVER part of main track in strict mode or when explicitly excluded
                if not _env_bool("TRACK_KN5_INCLUDE_PITLANE_IN_MAIN", False) and "pitlane" in name_lower:
                    should_capture = False

        vertices: List[List[float]] = []
        for _ in range(vertex_count):
            x, y, z = struct.unpack_from("<3f", reader.data, reader.tell())
            world = _transform_point((x, y, z), self.model_position, self.model_rotation)
            if should_capture:
                vertices.append(_map_point(world))
            reader.seek(reader.tell() + KN5_STATIC_VERTEX_STRIDE)

        index_count = reader.u32()
        raw_indices = reader.read(index_count * 2)
        indices = list(struct.unpack(f"<{index_count}H", raw_indices)) if should_capture and index_count else []
        if reader.remaining() >= KN5_MESH_FOOTER_BYTES:
            reader.read(KN5_MESH_FOOTER_BYTES)
        else:
            self._diagnostic("kn5_mesh_footer_missing", "Mesh footer was shorter than expected", nodePath=node_path)

        if not should_capture:
            return

        mesh_triangle_start = len(self.triangles)
        mesh_bounds_min, mesh_bounds_max = _bounds2()
        invalid_indices = 0
        degenerate = 0
        for tri_start in range(0, len(indices) - 2, 3):
            tri_indices = indices[tri_start : tri_start + 3]
            if any(index >= len(vertices) for index in tri_indices):
                invalid_indices += sum(1 for index in tri_indices if index >= len(vertices))
                continue
            points = [vertices[index] for index in tri_indices]
            area = _triangle_area2d(points[0], points[1], points[2])
            if area <= 1e-9:
                degenerate += 1
                continue
            for point in points:
                _update_bounds2(self.bounds_min, self.bounds_max, point)
                _update_bounds2(mesh_bounds_min, mesh_bounds_max, point)
            self.triangles.append(
                {
                    "mesh": mesh_name,
                    "surface": matched_surface,
                    "vertices": points,
                    "area": round(area, 6),
                }
            )

        mesh_triangle_count = len(self.triangles) - mesh_triangle_start
        self.meshes.append(
            {
                "meshName": mesh_name,
                "nodePath": node_path,
                "material": material,
                "matchedSurface": matched_surface,
                "vertices": vertex_count,
                "sourceTriangles": index_count // 3,
                "capturedTriangles": mesh_triangle_count,
                "bounds": _bounds_payload(mesh_bounds_min, mesh_bounds_max) if mesh_triangle_count else None,
                "invalidIndexCount": invalid_indices,
                "degenerateTriangleCount": degenerate,
            }
        )

    def _boundary_segments(self) -> List[Dict[str, List[float]]]:
        edge_counts: Dict[Tuple[Tuple[int, int], Tuple[int, int]], int] = defaultdict(int)
        edge_points: Dict[Tuple[Tuple[int, int], Tuple[int, int]], Tuple[List[float], List[float]]] = {}
        for triangle in self.triangles:
            points = triangle["vertices"]
            for start, end in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
                qa, qb = _quantized(start), _quantized(end)
                key = tuple(sorted((qa, qb)))
                edge_counts[key] += 1
                edge_points[key] = (start, end)
        boundary = [
            {"from": edge_points[key][0], "to": edge_points[key][1]}
            for key, count in edge_counts.items()
            if count == 1
        ]
        return boundary

    def _require_reader(self) -> _BinaryReader:
        if not self.reader:
            raise Kn5ParseError("KN5 reader is not initialized")
        return self.reader

    def _diagnostic(self, code: str, message: str, **context: Any) -> None:
        self.diagnostics.append({"code": code, "message": message, **context})


def build_track_surface_polygon_from_manifest(
    manifest: Dict[str, Any],
    *,
    included_surfaces: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    surfaces = _normalize_surface_order(included_surfaces or INCLUDED_SURFACES)
    source = (manifest.get("candidateGeometryFiles") or {}).get("mainVisual")
    if not source:
        return {
            "trackName": manifest.get("trackNameFromSharedMemory"),
            "trackConfig": manifest.get("trackConfigFromSharedMemory"),
            "source": None,
            "projection": "mapX = worldX, mapY = -worldZ",
            "includedSurfaceKeys": surfaces,
            "meshCount": 0,
            "triangleCount": 0,
            "bounds": None,
            "meshes": [],
            "triangles": [],
            "outline": {"segmentCount": 0, "segments": []},
            "diagnostics": [{"code": "missing_visual_kn5", "message": "TrackFileResolver did not resolve mainVisual"}],
        }
    transform = _model_transform(manifest, source)
    return Kn5TrackSurfacePolygonBuilder(
        source,
        included_surfaces=surfaces,
        model_position=transform["position"],
        model_rotation=transform["rotation"],
    ).build(manifest.get("trackNameFromSharedMemory"), manifest.get("trackConfigFromSharedMemory"))


def write_track_surface_debug_files(surface: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    track = surface.get("trackName") or "unknown"
    safe_track = "".join(char if char.isalnum() or char in "._-" else "_" for char in track)
    triangles_path = output_dir / f"track_surface_triangles_{safe_track}.json"
    bounds_path = output_dir / f"track_surface_bounds_{safe_track}.json"
    svg_path = output_dir / f"track_surface_preview_{safe_track}.svg"

    triangles_payload = {
        key: surface[key]
        for key in (
            "trackName",
            "trackConfig",
            "source",
            "projection",
            "includedSurfaceKeys",
            "meshCount",
            "triangleCount",
            "bounds",
            "meshes",
            "triangles",
            "outline",
            "diagnostics",
        )
    }
    bounds_payload = {
        "trackName": surface.get("trackName"),
        "trackConfig": surface.get("trackConfig"),
        "projection": surface.get("projection"),
        "bounds": surface.get("bounds"),
        "meshBounds": [
            {
                "meshName": mesh.get("meshName"),
                "matchedSurface": mesh.get("matchedSurface"),
                "bounds": mesh.get("bounds"),
                "capturedTriangles": mesh.get("capturedTriangles"),
            }
            for mesh in surface.get("meshes", [])
        ],
        "diagnostics": surface.get("diagnostics", []),
    }
    triangles_path.write_text(json.dumps(triangles_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    bounds_path.write_text(json.dumps(bounds_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    svg_path.write_text(build_surface_svg(surface), encoding="utf-8")
    return {"triangles": str(triangles_path), "bounds": str(bounds_path), "svg": str(svg_path)}


def build_surface_svg(surface: Dict[str, Any]) -> str:
    bounds = surface.get("bounds")
    if not bounds:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><text x="20" y="40">No surface triangles</text></svg>'
    margin = 24
    width, height = 1100, 900
    min_x, max_x = bounds["minX"], bounds["maxX"]
    min_y, max_y = bounds["minY"], bounds["maxY"]
    scale = min((width - margin * 2) / max(max_x - min_x, 1.0), (height - margin * 2) / max(max_y - min_y, 1.0))

    def sx(point: Sequence[float]) -> Tuple[float, float]:
        x = margin + (point[0] - min_x) * scale
        y = height - margin - (point[1] - min_y) * scale
        return x, y

    color = {"ROAD": "#3f4652", "CURB": "#d6dce6", "KERB": "#f34f4f"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#080b10"/>',
    ]
    for triangle in surface.get("triangles", []):
        points = [sx(point) for point in triangle["vertices"]]
        point_text = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        fill = color.get(triangle.get("surface"), "#5aa8ff")
        parts.append(f'<polygon points="{point_text}" fill="{fill}" fill-opacity="0.62" stroke="none"/>')
    for segment in surface.get("outline", {}).get("segments", []):
        ax, ay = sx(segment["from"])
        bx, by = sx(segment["to"])
        parts.append(f'<line x1="{ax:.2f}" y1="{ay:.2f}" x2="{bx:.2f}" y2="{by:.2f}" stroke="#27d8ff" stroke-width="0.8" stroke-opacity="0.55"/>')
    parts.append(f'<text x="24" y="32" fill="#d9e6f2" font-family="Segoe UI, Arial" font-size="16">KN5 ROAD/CURB/KERB surface debug - {surface.get("trackName")}</text>')
    parts.append("</svg>")
    return "\n".join(parts)
