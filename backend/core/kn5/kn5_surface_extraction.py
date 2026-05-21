import json
import math
import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .kn5_inventory import _model_transform
from .kn5_models import Kn5SurfaceCandidateMesh, Kn5SurfaceExtraction
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


DEFAULT_SURFACES = ["ROAD", "CURB", "KERB"]
OPTIONAL_SURFACES = ["PITLANE"]


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _empty_bounds() -> Tuple[List[float], List[float]]:
    return [float("inf"), float("inf"), float("inf")], [float("-inf"), float("-inf"), float("-inf")]


def _update_bounds(minimum: List[float], maximum: List[float], point: Sequence[float]) -> None:
    for axis in range(3):
        value = float(point[axis])
        minimum[axis] = min(minimum[axis], value)
        maximum[axis] = max(maximum[axis], value)


def _bounds_dict(minimum: Sequence[float], maximum: Sequence[float]) -> Dict[str, List[float]]:
    return {
        "min": [round(float(value), 6) for value in minimum],
        "max": [round(float(value), 6) for value in maximum],
    }


def _triangle_area2(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]


class Kn5SurfaceExtractor:
    def __init__(
        self,
        path: str,
        *,
        role: str,
        included_surface_keys: Sequence[str],
        optional_surface_keys: Sequence[str],
        include_pitlane: bool = False,
        model_position: Optional[Sequence[float]] = None,
        model_rotation: Optional[Sequence[float]] = None,
    ):
        self.path = Path(path)
        self.role = role
        self.included_surface_keys = _normalize_surface_order(included_surface_keys)
        self.optional_surface_keys = _normalize_surface_order(optional_surface_keys)
        self.match_surface_keys = _normalize_surface_order([*self.included_surface_keys, *self.optional_surface_keys])
        self.include_pitlane = include_pitlane
        self.model_position = list(model_position or [0.0, 0.0, 0.0])
        self.model_rotation = list(model_rotation or [0.0, 0.0, 0.0])
        self.reader: Optional[_BinaryReader] = None
        self.materials: List[str] = []
        self.candidates: List[Kn5SurfaceCandidateMesh] = []
        self.diagnostics: List[Dict[str, Any]] = []

    def extract(self) -> Tuple[List[Kn5SurfaceCandidateMesh], List[Dict[str, Any]]]:
        if not self.path.exists():
            return [], [{"code": "missing_kn5", "message": "Primary visual KN5 file does not exist", "path": str(self.path)}]
        try:
            self.reader = _BinaryReader(self.path.read_bytes())
            self._parse_header()
            self._parse_materials()
            self._parse_node("")
            if self.reader.remaining() != 0:
                self._diagnostic("kn5_trailing_bytes", "Surface extractor finished before EOF", remainingBytes=self.reader.remaining())
        except Exception as exc:
            self._diagnostic(
                "kn5_surface_extraction_failed",
                str(exc),
                recommendation="Keep this as debug-only until the unsupported KN5 variant is covered by parser tests.",
            )
        return self.candidates, self.diagnostics

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
        matched_surface = _match_surface(mesh_name, material, self.match_surface_keys)
        should_capture = matched_surface is not None

        vertices: List[List[float]] = []
        vertex_min, vertex_max = _empty_bounds()
        for _ in range(vertex_count):
            x, y, z = struct.unpack_from("<3f", reader.data, reader.tell())
            world = _transform_point((x, y, z), self.model_position, self.model_rotation)
            if should_capture:
                point = [round(float(world[0]), 6), round(float(world[1]), 6), round(float(world[2]), 6)]
                vertices.append(point)
                _update_bounds(vertex_min, vertex_max, point)
            reader.seek(reader.tell() + KN5_STATIC_VERTEX_STRIDE)

        index_count = reader.u32()
        index_bytes = reader.read(index_count * 2)
        indices = list(struct.unpack(f"<{index_count}H", index_bytes)) if should_capture and index_count else []
        if reader.remaining() >= KN5_MESH_FOOTER_BYTES:
            reader.read(KN5_MESH_FOOTER_BYTES)
        else:
            self._diagnostic("kn5_mesh_footer_missing", "Mesh footer was shorter than expected", nodePath=node_path)

        if not should_capture:
            return

        triangle_min, triangle_max = _empty_bounds()
        invalid_indices = 0
        degenerate_triangles = 0
        sample_triangles: List[List[int]] = []
        min_index: Optional[int] = None
        max_index: Optional[int] = None
        for tri_start in range(0, len(indices) - 2, 3):
            triangle = indices[tri_start : tri_start + 3]
            min_index = min(triangle) if min_index is None else min(min_index, *triangle)
            max_index = max(triangle) if max_index is None else max(max_index, *triangle)
            if any(index >= len(vertices) for index in triangle):
                invalid_indices += sum(1 for index in triangle if index >= len(vertices))
                continue
            points = [vertices[index] for index in triangle]
            for point in points:
                _update_bounds(triangle_min, triangle_max, point)
            if _triangle_area2(points[0], points[1], points[2]) < 1e-12:
                degenerate_triangles += 1
            if len(sample_triangles) < 5:
                sample_triangles.append([int(index) for index in triangle])

        is_pit = matched_surface == "PITLANE"
        included_road = matched_surface in self.included_surface_keys and not is_pit
        included_pit = is_pit and self.include_pitlane

        if included_road:
            name_lower = mesh_name.lower()
            
            # Strict mode: Only ^1road, ^1curb, ^1kerb
            if _env_bool("TRACK_KN5_STRICT_MAIN_TRACK", False):
                # Check if it starts with 1road, 1curb, or 1kerb
                if not (name_lower.startswith("1road") or name_lower.startswith("1curb") or name_lower.startswith("1kerb")):
                    included_road = False
            
            # Additional explicit exclusions
            if _env_bool("TRACK_KN5_EXCLUDE_AUX_ROADLINE", False) and "roadline" in name_lower:
                included_road = False
            if _env_bool("TRACK_KN5_EXCLUDE_ROADVERGE", False) and "roadverge" in name_lower:
                included_road = False
            
            # Pitlane is NEVER part of main track in strict mode or when explicitly excluded
            if not _env_bool("TRACK_KN5_INCLUDE_PITLANE_IN_MAIN", False) and "pitlane" in name_lower:
                included_road = False

        self.candidates.append(
            Kn5SurfaceCandidateMesh(
                sourceFile=self.path.name,
                sourcePath=str(self.path),
                role=self.role,
                meshName=mesh_name,
                nodePath=node_path,
                material=material,
                matchedSurface=matched_surface or "UNKNOWN",
                includedForRoadGeometry=included_road,
                includedForPitLaneGeometry=included_pit,
                vertices=vertex_count,
                triangles=index_count // 3,
                vertexBounds=_bounds_dict(vertex_min, vertex_max),
                triangleBounds=_bounds_dict(triangle_min, triangle_max),
                indexRange={"min": min_index, "max": max_index},
                invalidIndexCount=invalid_indices,
                degenerateTriangleCount=degenerate_triangles,
                sampleVertices=vertices[:5],
                sampleTriangles=sample_triangles,
            )
        )

    def _require_reader(self) -> _BinaryReader:
        if not self.reader:
            raise Kn5ParseError("KN5 reader is not initialized")
        return self.reader

    def _diagnostic(self, code: str, message: str, **context: Any) -> None:
        self.diagnostics.append({"code": code, "message": message, **context})


def build_kn5_surface_extraction_from_manifest(
    manifest: Dict[str, Any],
    *,
    include_pitlane: bool = False,
) -> Kn5SurfaceExtraction:
    candidate_files = manifest.get("candidateGeometryFiles") or {}
    primary_path = candidate_files.get("mainVisual")
    diagnostics: List[Dict[str, Any]] = []
    candidate_meshes: List[Kn5SurfaceCandidateMesh] = []
    if not primary_path:
        diagnostics.append(
            {
                "code": "missing_visual_kn5",
                "message": "TrackFileResolver did not resolve a main visual KN5 file",
            }
        )
    else:
        transform = _model_transform(manifest, primary_path)
        candidate_meshes, diagnostics = Kn5SurfaceExtractor(
            primary_path,
            role="visual",
            included_surface_keys=DEFAULT_SURFACES,
            optional_surface_keys=OPTIONAL_SURFACES,
            include_pitlane=include_pitlane,
            model_position=transform["position"],
            model_rotation=transform["rotation"],
        ).extract()

    vertex_bounds = _aggregate_bounds([mesh.vertexBounds for mesh in candidate_meshes if mesh.includedForRoadGeometry])
    triangle_bounds = _aggregate_bounds([mesh.triangleBounds for mesh in candidate_meshes if mesh.includedForRoadGeometry])
    return Kn5SurfaceExtraction(
        trackName=manifest.get("trackNameFromSharedMemory"),
        trackConfig=manifest.get("trackConfigFromSharedMemory"),
        primarySource=primary_path or "",
        primarySourceRole="visual",
        includedSurfaceKeys=DEFAULT_SURFACES,
        optionalSurfaceKeys=OPTIONAL_SURFACES,
        includePitlane=include_pitlane,
        candidateMeshes=candidate_meshes,
        globalVertexBounds=vertex_bounds,
        globalTriangleBounds=triangle_bounds,
        diagnostics=diagnostics,
    )


def _aggregate_bounds(bounds: Sequence[Dict[str, List[float]]]) -> Optional[Dict[str, List[float]]]:
    if not bounds:
        return None
    minimum, maximum = _empty_bounds()
    for item in bounds:
        _update_bounds(minimum, maximum, item["min"])
        _update_bounds(minimum, maximum, item["max"])
    return _bounds_dict(minimum, maximum)


def write_kn5_surface_extraction_json(extraction: Kn5SurfaceExtraction, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_track = "".join(char if char.isalnum() or char in "._-" else "_" for char in (extraction.trackName or "unknown"))
    output_path = output_dir / f"kn5_surface_candidates_{safe_track}.json"
    output_path.write_text(json.dumps(extraction.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
