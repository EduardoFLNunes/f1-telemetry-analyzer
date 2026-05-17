"""
Módulo de geração de TrackMap
REGRA CRÍTICA: O trackmap é SEMPRE gerado a partir do CSV da pista, NUNCA da raceline
"""
import pandas as pd
import numpy as np
import logging
import struct
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class TrackMapGenerator:
    """Gera trackmap real a partir do CSV da pista"""
    
    def __init__(self):
        self.track_data = None
    
    def generate_from_csv(self, df: pd.DataFrame) -> Dict:
        # Limpar nomes de colunas
        df.columns = df.columns.str.strip()
        
        # Extrair dados brutos
        x_center = df['# x_m'].values
        y_center = df['y_m'].values
        width_right = df['w_tr_right_m'].values
        width_left = df['w_tr_left_m'].values
        
        # PRO MODE: Formal Spatial Registration
        from core.spatial_registration import registrar
        raw_points = np.column_stack([x_center, y_center])
        registrar.register_track(raw_points)
        
        # Transform centerline to Canonical Space
        center_canonical = np.array([registrar.transform_track(x, y) for x, y in raw_points])
        
        return self._generate_final_structure(
            center_canonical[:, 0], center_canonical[:, 1], 
            width_left, width_right, "Circuit"
        )

    def _generate_final_structure(self, x_c, y_c, w_l, w_r, name) -> Dict:
        from core.spatial_engine import CanonicalTrackSpace
        spatial_index = CanonicalTrackSpace(x_c, y_c)
        
        l_e, r_e = self._calculate_track_edges(x_c, y_c, w_l, w_r)
        
        return {
            "name": name,
            "centerline": {"x": x_c.tolist(), "z": y_c.tolist()},
            "left_edge": {"x": l_e[0].tolist(), "z": l_e[1].tolist()},
            "right_edge": {"x": r_e[0].tolist(), "z": r_e[1].tolist()},
            "width_left": w_l.tolist(),
            "width_right": w_r.tolist(),
            "length_meters": self._calculate_track_length(x_c, y_c),
            "total_points": len(x_c),
            "_spatial_index": spatial_index
        }

    def _calculate_track_edges(self, x, y, wl, wr):
        dx, dy = np.gradient(x), np.gradient(y)
        norm = np.hypot(dx, dy)
        norm[norm == 0] = 1
        nx, ny = -dy / norm, dx / norm
        return (x + nx * wl, y + ny * wl), (x - nx * wr, y - ny * wr)

    def _calculate_track_length(self, x, y):
        return float(np.sum(np.sqrt(np.diff(x)**2 + np.diff(y)**2)))

class AssettoCorsaTrackParser:
    def parse_track(self, track_directory: Path) -> Dict:
        """Parses fast_lane.ai into Raw World Space data."""
        fast_lane_path = track_directory / "ai" / "fast_lane.ai"
        if not fast_lane_path.exists():
            raise FileNotFoundError(f"fast_lane.ai not found at {fast_lane_path}")

        x_coords, z_coords = [], []
        left_edge_x, left_edge_z = [], []
        right_edge_x, right_edge_z = [], []
        wl, wr = [], []

        point_format = '<18f'
        point_size = struct.calcsize(point_format)

        with open(fast_lane_path, "rb") as f:
            header = f.read(8)
            _, points_count = struct.unpack('<II', header)
            for _ in range(points_count):
                d = struct.unpack(point_format, f.read(point_size))
                pos_x, pos_z, nx, nz = d[0], d[2], d[7], d[9]
                lw, rw = abs(d[10]), abs(d[11])

                x_coords.append(pos_x)
                z_coords.append(pos_z)
                wl.append(lw)
                wr.append(rw)
                left_edge_x.append(pos_x + (nx * lw))
                left_edge_z.append(pos_z + (nz * lw))
                right_edge_x.append(pos_x - (nx * rw))
                right_edge_z.append(pos_z - (nz * rw))

        return {
            "name": track_directory.name,
            "centerline": {"x": x_coords, "z": z_coords},
            "left_edge": {"x": left_edge_x, "z": left_edge_z},
            "right_edge": {"x": right_edge_x, "z": right_edge_z},
            "is_raw_world_space": True
        }
