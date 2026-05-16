"""
Módulo de geração de TrackMap
REGRA CRÍTICA: O trackmap é SEMPRE gerado a partir do CSV da pista, NUNCA da raceline
"""
import pandas as pd
import numpy as np
import logging
import struct
import os
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class TrackMapGenerator:
    """Gera trackmap real a partir do CSV da pista"""
    
    def __init__(self):
        self.track_data = None
    
    def generate_from_csv(self, df: pd.DataFrame) -> Dict:
        """
        Gera trackmap completo a partir do CSV da pista
        
        Args:
            df: DataFrame com colunas [# x_m, y_m, w_tr_right_m, w_tr_left_m]
        
        Returns:
            Dict com trackmap completo (centerline, bordas, limites)
        """
        # Limpar nomes de colunas
        df.columns = df.columns.str.strip()
        
        # Extrair dados brutos
        x_center = df['# x_m'].values
        y_center = df['y_m'].values
        width_right = df['w_tr_right_m'].values
        width_left = df['w_tr_left_m'].values
        
        return self._generate_from_raw_arrays(x_center, y_center, width_left, width_right)

    def _generate_from_raw_arrays(
        self,
        x_center: np.ndarray,
        y_center: np.ndarray,
        width_left: np.ndarray,
        width_right: np.ndarray
    ) -> Dict:
        """
        Generates complete trackmap from raw numpy arrays of centerline
        coordinates and track widths.
        """
        # PRO MODE: Formal Spatial Registration
        from core.spatial_registration import registrar
        raw_points = np.column_stack([x_center, y_center])
        registrar.register_track(raw_points)
        
        # Transform centerline to Canonical Space
        center_canonical = np.array([registrar.transform_track(x, y) for x, y in raw_points])
        x_canonical = center_canonical[:, 0]
        y_canonical = center_canonical[:, 1]

        # Calcular bordas da pista usando geometria vetorial (no espaço canônico)
        left_edge, right_edge = self._calculate_track_edges(
            x_canonical, y_canonical, width_left, width_right
        )
        
        # Calcular curvaturas (para análise da IA)
        curvatures = self._calculate_curvature(x_canonical, y_canonical)
        
        # Identificar setores e corners
        sectors = self._identify_sectors(x_canonical, y_canonical, curvatures)
        corners = self._identify_corners(curvatures)
        
        # Calcular comprimento da pista
        track_length = self._calculate_track_length(x_canonical, y_canonical)
        
        # PRO MODE: Gerar Índice Espacial Profissional (CanonicalTrackSpace)
        from core.spatial_engine import CanonicalTrackSpace
        spatial_index = CanonicalTrackSpace(x_canonical, y_canonical)
        s_values = spatial_index.s_samples.tolist()
        
        # Calcular tangentes e normais para cada ponto da centerline
        tangents = []
        normals = []
        for s in spatial_index.s_samples:
            tx, tz = spatial_index.get_tangent(s)
            nx, nz = spatial_index.get_normal(s)
            tangents.append({"x": float(tx), "z": float(tz)})
            normals.append({"x": float(nx), "z": float(nz)})

        # Calcular bounds para visualização
        all_x = np.concatenate([x_canonical, left_edge[0], right_edge[0]])
        all_y = np.concatenate([y_canonical, left_edge[1], right_edge[1]])
        
        bounds = {
            "min_x": float(np.min(all_x)),
            "max_x": float(np.max(all_x)),
            "min_y": float(np.min(all_y)),
            "max_y": float(np.max(all_y))
        }

        logger.info(f"TrackMap generated and registered in Canonical Space: {len(x_canonical)} points. Bounds: {bounds}")

        # Montar estrutura de dados
        track_data = {
            "name": "Circuit",
            "centerline": {
                "x": x_canonical.tolist(),
                "y": y_canonical.tolist(),
                "s": s_values,
                "tangents": tangents,
                "normals": normals
            },
            "left_edge": {
                "x": left_edge[0].tolist(),
                "y": left_edge[1].tolist()
            },
            "right_edge": {
                "x": right_edge[0].tolist(),
                "y": right_edge[1].tolist()
            },
            "width_left": width_left.tolist(),
            "width_right": width_right.tolist(),
            "curvatures": curvatures.tolist(),
            "sectors": sectors,
            "corners": corners,
            "length_meters": track_length,
            "total_length": spatial_index.total_length,
            "bounds": bounds,
            "total_points": len(x_center),
            "_spatial_index": spatial_index
        }
        
        # REMOVE Non-serializable object before returning
        track_data.pop("_spatial_index", None)
        
        self.track_data = track_data
        return track_data
    
    def _calculate_track_edges(
        self, 
        x_center: np.ndarray, 
        y_center: np.ndarray, 
        width_left: np.ndarray, 
        width_right: np.ndarray
    ) -> Tuple[Tuple[np.ndarray, np.ndarray], Tuple[np.ndarray, np.ndarray]]:
        # Gradiente = tangente
        dx = np.gradient(x_center)
        dy = np.gradient(y_center)
        
        # Normalização
        norm = np.hypot(dx, dy)
        norm[norm == 0] = 1  # Evitar divisão por zero
        
        # Vetor normal (perpendicular)
        nx = -dy / norm
        ny = dx / norm
        
        # Bordas
        x_left = x_center + nx * width_left
        y_left = y_center + ny * width_left
        
        x_right = x_center - nx * width_right
        y_right = y_center - ny * width_right
        
        return (x_left, y_left), (x_right, y_right)
    
    def _calculate_curvature(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        dx = np.gradient(x)
        dy = np.gradient(y)
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        
        # Fórmula da curvatura: κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)
        numerator = np.abs(dx * ddy - dy * ddx)
        denominator = (dx**2 + dy**2)**(3/2)
        denominator[denominator == 0] = 1e-10
        
        curvature = numerator / denominator
        return curvature
    
    def _identify_sectors(
        self, 
        x: np.ndarray, 
        y: np.ndarray, 
        curvatures: np.ndarray
    ) -> List[Dict]:
        n_points = len(x)
        sector_size = n_points // 3
        
        sectors = [
            {
                "sector": 1,
                "start_idx": 0,
                "end_idx": sector_size,
                "avg_curvature": float(np.mean(curvatures[0:sector_size]))
            },
            {
                "sector": 2,
                "start_idx": sector_size,
                "end_idx": 2 * sector_size,
                "avg_curvature": float(np.mean(curvatures[sector_size:2*sector_size]))
            },
            {
                "sector": 3,
                "start_idx": 2 * sector_size,
                "end_idx": n_points,
                "avg_curvature": float(np.mean(curvatures[2*sector_size:]))
            }
        ]
        
        return sectors
    
    def _identify_corners(self, curvatures: np.ndarray) -> List[Dict]:
        threshold = np.percentile(curvatures, 70)
        
        corners = []
        in_corner = False
        corner_start = 0
        
        for i, curv in enumerate(curvatures):
            if curv > threshold and not in_corner:
                in_corner = True
                corner_start = i
            elif curv <= threshold and in_corner:
                in_corner = False
                corners.append({
                    "corner_id": len(corners) + 1,
                    "start_idx": corner_start,
                    "end_idx": i,
                    "apex_idx": corner_start + (i - corner_start) // 2,
                    "avg_curvature": float(np.mean(curvatures[corner_start:i])),
                    "type": "tight" if np.mean(curvatures[corner_start:i]) > threshold * 1.5 else "medium"
                })
        
        return corners
    
    def _calculate_track_length(self, x: np.ndarray, y: np.ndarray) -> float:
        dx = np.diff(x)
        dy = np.diff(y)
        distances = np.sqrt(dx**2 + dy**2)
        return float(np.sum(distances))

class AssettoCorsaTrackParser:
    def parse_track(self, track_directory: Path) -> Dict:
        """
        Parses the fast_lane.ai file and returns track data in the
        standard format.
        """
        fast_lane_path = track_directory / "ai" / "fast_lane.ai"
        if not fast_lane_path.exists():
            raise FileNotFoundError(f"fast_lane.ai not found at {fast_lane_path}")

        x_coords = []
        z_coords = []
        width_left = []
        width_right = []

        point_format = '<18f' # 18 floats as per original AC binary structure (72 bytes)
        point_size = struct.calcsize(point_format)

        try:
            with open(fast_lane_path, "rb") as f:
                header_data = f.read(8)
                if len(header_data) < 8:
                    raise ValueError("Empty or corrupt file.")
                version, points_count = struct.unpack('<II', header_data)

                for i in range(points_count):
                    chunk = f.read(point_size)
                    if len(chunk) < point_size:
                        break
                    
                    data = struct.unpack(point_format, chunk)
                    x_coords.append(data[0])
                    z_coords.append(data[2])
                    width_left.append(abs(data[10]))
                    width_right.append(abs(data[11]))

        except Exception as e:
            raise IOError(f"Error reading fast_lane.ai: {e}")

        if not x_coords:
            raise ValueError("No track points found in fast_lane.ai.")

        generator = TrackMapGenerator()
        track_data = generator._generate_from_raw_arrays(
            np.array(x_coords, dtype=np.float32), 
            np.array(z_coords, dtype=np.float32), 
            np.array(width_left, dtype=np.float32), 
            np.array(width_right, dtype=np.float32)
        )
        
        track_data["name"] = track_directory.name 
        return track_data
