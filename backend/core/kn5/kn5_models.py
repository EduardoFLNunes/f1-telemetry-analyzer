from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Kn5MeshInventory:
    name: str
    nodeName: str
    nodePath: str
    material: Optional[str]
    materialIndex: Optional[int]
    vertices: int
    triangles: int
    bbox: Dict[str, List[float]]
    matchesGeometrySurface: bool
    matchedSurface: Optional[str]
    role: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "nodeName": self.nodeName,
            "nodePath": self.nodePath,
            "material": self.material,
            "materialIndex": self.materialIndex,
            "vertices": self.vertices,
            "triangles": self.triangles,
            "bbox": self.bbox,
            "matchesGeometrySurface": self.matchesGeometrySurface,
            "matchedSurface": self.matchedSurface,
            "role": self.role,
        }


@dataclass
class Kn5FileInventory:
    role: str
    path: str
    fileName: str
    exists: bool
    fileSizeBytes: Optional[int] = None
    version: Optional[int] = None
    textureCount: Optional[int] = None
    materialCount: Optional[int] = None
    nodeCount: int = 0
    meshCount: int = 0
    materials: List[str] = field(default_factory=list)
    nodes: List[str] = field(default_factory=list)
    meshes: List[Kn5MeshInventory] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "path": self.path,
            "fileName": self.fileName,
            "exists": self.exists,
            "fileSizeBytes": self.fileSizeBytes,
            "version": self.version,
            "textureCount": self.textureCount,
            "materialCount": self.materialCount,
            "nodeCount": self.nodeCount,
            "meshCount": self.meshCount,
            "materials": self.materials,
            "nodes": self.nodes,
            "meshes": [mesh.to_dict() for mesh in self.meshes],
            "diagnostics": self.diagnostics,
        }


@dataclass
class Kn5TrackInventory:
    trackName: Optional[str]
    trackConfig: Optional[str]
    geometrySurfaces: List[str]
    sourceManifest: Dict[str, Any]
    files: List[Kn5FileInventory]
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trackName": self.trackName,
            "trackConfig": self.trackConfig,
            "geometrySurfaces": self.geometrySurfaces,
            "sourceManifest": self.sourceManifest,
            "files": [file.to_dict() for file in self.files],
            "diagnostics": self.diagnostics,
        }


def empty_file_inventory(role: str, path: Optional[str], code: str, message: str) -> Kn5FileInventory:
    display_path = path or ""
    return Kn5FileInventory(
        role=role,
        path=display_path,
        fileName=Path(display_path).name if display_path else "",
        exists=bool(path and Path(path).exists()),
        diagnostics=[{"code": code, "message": message}],
    )


@dataclass
class Kn5SurfaceCandidateMesh:
    sourceFile: str
    sourcePath: str
    role: str
    meshName: str
    nodePath: str
    material: Optional[str]
    matchedSurface: str
    includedForRoadGeometry: bool
    includedForPitLaneGeometry: bool
    vertices: int
    triangles: int
    vertexBounds: Dict[str, List[float]]
    triangleBounds: Dict[str, List[float]]
    indexRange: Dict[str, Optional[int]]
    invalidIndexCount: int
    degenerateTriangleCount: int
    sampleVertices: List[List[float]]
    sampleTriangles: List[List[int]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sourceFile": self.sourceFile,
            "sourcePath": self.sourcePath,
            "role": self.role,
            "meshName": self.meshName,
            "nodePath": self.nodePath,
            "material": self.material,
            "matchedSurface": self.matchedSurface,
            "includedForRoadGeometry": self.includedForRoadGeometry,
            "includedForPitLaneGeometry": self.includedForPitLaneGeometry,
            "vertices": self.vertices,
            "triangles": self.triangles,
            "vertexBounds": self.vertexBounds,
            "triangleBounds": self.triangleBounds,
            "indexRange": self.indexRange,
            "invalidIndexCount": self.invalidIndexCount,
            "degenerateTriangleCount": self.degenerateTriangleCount,
            "sampleVertices": self.sampleVertices,
            "sampleTriangles": self.sampleTriangles,
        }


@dataclass
class Kn5SurfaceExtraction:
    trackName: Optional[str]
    trackConfig: Optional[str]
    primarySource: str
    primarySourceRole: str
    includedSurfaceKeys: List[str]
    optionalSurfaceKeys: List[str]
    includePitlane: bool
    candidateMeshes: List[Kn5SurfaceCandidateMesh]
    globalVertexBounds: Optional[Dict[str, List[float]]]
    globalTriangleBounds: Optional[Dict[str, List[float]]]
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trackName": self.trackName,
            "trackConfig": self.trackConfig,
            "primarySource": self.primarySource,
            "primarySourceRole": self.primarySourceRole,
            "includedSurfaceKeys": self.includedSurfaceKeys,
            "optionalSurfaceKeys": self.optionalSurfaceKeys,
            "includePitlane": self.includePitlane,
            "candidateMeshes": [mesh.to_dict() for mesh in self.candidateMeshes],
            "globalVertexBounds": self.globalVertexBounds,
            "globalTriangleBounds": self.globalTriangleBounds,
            "diagnostics": self.diagnostics,
        }
