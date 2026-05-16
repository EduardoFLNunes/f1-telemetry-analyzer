"""
Módulo de geração de TrackMap
REGRA CRÍTICA: O trackmap é SEMPRE gerado a partir do CSV da pista, NUNCA da raceline
"""
import pandas as pd
import numpy as np
import logging
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
        
        # Calcular bordas da pista usando geometria vetorial
        left_edge, right_edge = self._calculate_track_edges(
            x_center, y_center, width_left, width_right
        )
        
        # Calcular curvaturas (para análise da IA)
        curvatures = self._calculate_curvature(x_center, y_center)
        
        # Identificar setores e corners
        sectors = self._identify_sectors(x_center, y_center, curvatures)
        corners = self._identify_corners(curvatures)
        
        # Calcular comprimento da pista
        track_length = self._calculate_track_length(x_center, y_center)
        
        # PRO MODE: Gerar Índice Espacial Profissional (CanonicalTrackSpace)
        from core.spatial_engine import CanonicalTrackSpace
        spatial_index = CanonicalTrackSpace(x_center, y_center)
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
        all_x = np.concatenate([x_center, left_edge[0], right_edge[0]])
        all_y = np.concatenate([y_center, left_edge[1], right_edge[1]])
        
        bounds = {
            "min_x": float(np.min(all_x)),
            "max_x": float(np.max(all_x)),
            "min_y": float(np.min(all_y)),
            "max_y": float(np.max(all_y))
        }

        logger.info(f"TrackMap generated: {len(x_center)} points. Bounds: {bounds}")

        # Montar estrutura de dados
        track_data = {
            "name": "Circuit",
            "centerline": {
                "x": x_center.tolist(),
                "y": y_center.tolist(),
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
        """
        Calcula as bordas da pista usando vetores perpendiculares
        
        Geometria:
        1. Calcular tangente em cada ponto (dx, dy)
        2. Calcular normal (perpendicular à tangente)
        3. Aplicar largura para obter bordas
        """
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
        """
        Calcula curvatura em cada ponto da pista
        Curvatura = 1/raio da curva
        """
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
        """
        Identifica setores da pista (dividir em 3 setores como F1 real)
        """
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
        """
        Identifica curvas principais da pista
        Curva = região com curvatura acima de threshold
        """
        # Threshold para identificar curvas (ajustar conforme pista)
        threshold = np.percentile(curvatures, 70)
        
        corners = []
        in_corner = False
        corner_start = 0
        
        for i, curv in enumerate(curvatures):
            if curv > threshold and not in_corner:
                # Início de uma curva
                in_corner = True
                corner_start = i
            elif curv <= threshold and in_corner:
                # Fim de uma curva
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
        """Calcula comprimento total da pista em metros"""
        dx = np.diff(x)
        dy = np.diff(y)
        distances = np.sqrt(dx**2 + dy**2)
        return float(np.sum(distances))
