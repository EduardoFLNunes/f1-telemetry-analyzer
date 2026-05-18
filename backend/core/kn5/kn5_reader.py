import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .kn5_models import Kn5FileInventory, Kn5MeshInventory, empty_file_inventory


KN5_MAGIC = b"sc6969"
KN5_STATIC_VERTEX_STRIDE = 44
KN5_MESH_FOOTER_BYTES = 33


class Kn5ParseError(RuntimeError):
    pass


class _BinaryReader:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def remaining(self) -> int:
        return len(self.data) - self.offset

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int) -> None:
        if offset < 0 or offset > len(self.data):
            raise Kn5ParseError(f"Invalid KN5 seek offset: {offset}")
        self.offset = offset

    def read(self, size: int) -> bytes:
        if self.offset + size > len(self.data):
            raise Kn5ParseError(f"Unexpected EOF at offset {self.offset}; need {size} bytes")
        chunk = self.data[self.offset : self.offset + size]
        self.offset += size
        return chunk

    def u8(self) -> int:
        return self.read(1)[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.read(4))[0]

    def f32(self) -> float:
        return struct.unpack_from("<f", self.read(4))[0]

    def f32_tuple(self, count: int) -> Tuple[float, ...]:
        return struct.unpack_from(f"<{count}f", self.read(count * 4))

    def string(self) -> str:
        length = self.u32()
        if length > 1024 * 1024:
            raise Kn5ParseError(f"Unreasonable KN5 string length {length} at offset {self.offset - 4}")
        raw = self.read(length)
        return raw.decode("utf-8", errors="replace").rstrip("\x00")


def _normalize_surface_order(surface_keys: Sequence[str]) -> List[str]:
    preferred = ["ROAD", "CURB", "KERB"]
    upper = [str(key).upper() for key in surface_keys if key]
    ordered = [key for key in preferred if key in upper]
    ordered.extend(key for key in upper if key not in ordered)
    return ordered


def _match_surface(mesh_name: str, material_name: Optional[str], surface_keys: Sequence[str]) -> Optional[str]:
    haystack = f"{mesh_name or ''} {material_name or ''}".upper()
    for key in _normalize_surface_order(surface_keys):
        if key and key in haystack:
            return key
    return None


def _rotation_matrix_xyz(rotation_degrees: Sequence[float]) -> Tuple[Tuple[float, float, float], ...]:
    rx, ry, rz = [(float(value) if value is not None else 0.0) * math.pi / 180.0 for value in list(rotation_degrees)[:3]]
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    # Rz * Ry * Rx. Current AC models usually provide 0,0,0; this keeps the
    # inventory honest if a model entry has an offset or rotation.
    return (
        (cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx),
        (sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx),
        (-sy, cy * sx, cy * cx),
    )


def _transform_point(
    point: Tuple[float, float, float],
    position: Sequence[float],
    rotation_degrees: Sequence[float],
) -> Tuple[float, float, float]:
    px, py, pz = [float(value) if value is not None else 0.0 for value in list(position)[:3]]
    matrix = _rotation_matrix_xyz(rotation_degrees)
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + px,
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + py,
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + pz,
    )


class Kn5Reader:
    def __init__(
        self,
        path: Union[str, Path],
        *,
        role: str,
        geometry_surfaces: Sequence[str],
        model_position: Optional[Sequence[float]] = None,
        model_rotation: Optional[Sequence[float]] = None,
    ):
        self.path = Path(path)
        self.role = role
        self.geometry_surfaces = _normalize_surface_order(geometry_surfaces)
        self.model_position = list(model_position or [0.0, 0.0, 0.0])
        self.model_rotation = list(model_rotation or [0.0, 0.0, 0.0])
        self.reader: Optional[_BinaryReader] = None
        self.materials: List[str] = []
        self.nodes: List[str] = []
        self.meshes: List[Kn5MeshInventory] = []
        self.diagnostics: List[Dict[str, Any]] = []
        self.version: Optional[int] = None
        self.texture_count: Optional[int] = None
        self.material_count: Optional[int] = None

    def read_inventory(self) -> Kn5FileInventory:
        if not self.path.exists():
            return empty_file_inventory(self.role, str(self.path), "missing_kn5", "KN5 file does not exist")

        try:
            data = self.path.read_bytes()
            self.reader = _BinaryReader(data)
            self._parse_header()
            self._parse_materials()
            self._parse_node(parent_path="")
            if self.reader.remaining() != 0:
                self._diagnostic(
                    "kn5_trailing_bytes",
                    "Parser finished before EOF",
                    remainingBytes=self.reader.remaining(),
                    offset=self.reader.tell(),
                )
        except Exception as exc:
            self._diagnostic(
                "kn5_parse_failed",
                str(exc),
                recommendation=(
                    "Integrate a fuller KN5 parser before geometry extraction if this file uses an unsupported node/mesh variant."
                ),
            )

        return Kn5FileInventory(
            role=self.role,
            path=str(self.path),
            fileName=self.path.name,
            exists=True,
            fileSizeBytes=self.path.stat().st_size,
            version=self.version,
            textureCount=self.texture_count,
            materialCount=self.material_count,
            nodeCount=len(self.nodes),
            meshCount=len(self.meshes),
            materials=self.materials,
            nodes=self.nodes,
            meshes=self.meshes,
            diagnostics=self.diagnostics,
        )

    def _parse_header(self) -> None:
        reader = self._require_reader()
        magic = reader.read(len(KN5_MAGIC))
        if magic != KN5_MAGIC:
            raise Kn5ParseError(f"Invalid KN5 magic {magic!r}; expected {KN5_MAGIC!r}")
        self.version = reader.u32()
        self.texture_count = reader.u32()
        for _ in range(self.texture_count):
            _texture_type = reader.u32()
            _texture_name = reader.string()
            size = reader.u32()
            reader.read(size)

    def _parse_materials(self) -> None:
        reader = self._require_reader()
        self.material_count = reader.u32()
        self.materials = []
        for _ in range(self.material_count):
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
        self.nodes.append(node_path)

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

    def _parse_static_mesh(self, node_name: str, node_path: str) -> None:
        reader = self._require_reader()
        material_index = reader.u32()
        _mesh_flags = reader.u32()
        vertex_count = reader.u32()
        if vertex_count > 10_000_000:
            raise Kn5ParseError(f"Unreasonable vertex count {vertex_count} for mesh {node_path}")

        bbox_min = [float("inf"), float("inf"), float("inf")]
        bbox_max = [float("-inf"), float("-inf"), float("-inf")]
        for _ in range(vertex_count):
            x, y, z = struct.unpack_from("<3f", reader.data, reader.tell())
            wx, wy, wz = _transform_point((x, y, z), self.model_position, self.model_rotation)
            bbox_min[0] = min(bbox_min[0], wx)
            bbox_min[1] = min(bbox_min[1], wy)
            bbox_min[2] = min(bbox_min[2], wz)
            bbox_max[0] = max(bbox_max[0], wx)
            bbox_max[1] = max(bbox_max[1], wy)
            bbox_max[2] = max(bbox_max[2], wz)
            reader.seek(reader.tell() + KN5_STATIC_VERTEX_STRIDE)

        index_count = reader.u32()
        reader.read(index_count * 2)
        if reader.remaining() >= KN5_MESH_FOOTER_BYTES:
            reader.read(KN5_MESH_FOOTER_BYTES)
        else:
            self._diagnostic("kn5_mesh_footer_missing", "Mesh footer was shorter than expected", nodePath=node_path)

        material = self.materials[material_index] if 0 <= material_index < len(self.materials) else None
        matched_surface = _match_surface(node_name, material, self.geometry_surfaces)
        bbox = {
            "min": [round(value, 6) for value in bbox_min],
            "max": [round(value, 6) for value in bbox_max],
        }
        self.meshes.append(
            Kn5MeshInventory(
                name=node_name,
                nodeName=node_name,
                nodePath=node_path,
                material=material,
                materialIndex=material_index,
                vertices=vertex_count,
                triangles=index_count // 3,
                bbox=bbox,
                matchesGeometrySurface=matched_surface is not None,
                matchedSurface=matched_surface,
                role=self.role,
            )
        )

    def _require_reader(self) -> _BinaryReader:
        if not self.reader:
            raise Kn5ParseError("KN5 reader is not initialized")
        return self.reader

    def _diagnostic(self, code: str, message: str, **context: Any) -> None:
        self.diagnostics.append({"code": code, "message": message, **context})
