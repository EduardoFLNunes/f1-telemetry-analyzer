"""
Módulo de Track Limits - Validação de Limites da Pista
REGRA CRÍTICA: Se os 4 pneus saem da pista, a volta é INVALIDADA
"""
import numpy as np
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)


class TrackLimitsValidator:
    """
    Valida se pontos estão dentro dos limites da pista
    
    REGRA DO AUTOMOBILISMO:
    - Se os 4 pneus saem da pista = VOLTA INVALIDADA
    - Não há exceções
    - A pista é a única área segura (fora = lava)
    """
    
    def __init__(self, track_data: dict):
        """
        Args:
            track_data: Dados do trackmap com bordas (left_edge, right_edge)
        """
        self.track_data = track_data
        
        # Extrair bordas da pista
        self.left_x = np.array(track_data["left_edge"]["x"])
        self.left_y = np.array(track_data["left_edge"]["y"])
        self.right_x = np.array(track_data["right_edge"]["x"])
        self.right_y = np.array(track_data["right_edge"]["y"])
        
        # Criar polígono da pista (área válida)
        # Borda esquerda + borda direita invertida + fechar
        self.track_polygon_x = np.concatenate([
            self.left_x,
            self.right_x[::-1],
            [self.left_x[0]]
        ])
        
        self.track_polygon_y = np.concatenate([
            self.left_y,
            self.right_y[::-1],
            [self.left_y[0]]
        ])
        
        logger.info(f"Track Limits Validator inicializado: {len(self.left_x)} pontos de referência")
    
    def is_point_inside_track(self, x: float, y: float) -> bool:
        """
        Verifica se um ponto (x,y) está DENTRO da pista
        
        Algoritmo: Point-in-Polygon usando Ray Casting
        
        Args:
            x: Coordenada X
            y: Coordenada Y
        
        Returns:
            True se DENTRO da pista, False se FORA
        """
        return self._point_in_polygon(x, y, self.track_polygon_x, self.track_polygon_y)
    
    def _point_in_polygon(self, x: float, y: float, poly_x: np.ndarray, poly_y: np.ndarray) -> bool:
        """
        Algoritmo Ray Casting para Point-in-Polygon
        
        Traça um raio horizontal da direita do ponto até o infinito.
        Se cruzar número ímpar de bordas = DENTRO
        Se cruzar número par de bordas = FORA
        """
        n = len(poly_x)
        inside = False
        
        p1x, p1y = poly_x[0], poly_y[0]
        
        for i in range(1, n + 1):
            p2x, p2y = poly_x[i % n], poly_y[i % n]
            
            # Verificar se o ponto está entre as coordenadas Y das bordas
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        # Calcular interseção
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            
            p1x, p1y = p2x, p2y
        
        return inside
    
    def validate_lap(self, lap_x: np.ndarray, lap_y: np.ndarray) -> dict:
        """
        Valida uma volta completa
        
        REGRA: Se QUALQUER ponto sair da pista = VOLTA INVALIDADA
        
        Args:
            lap_x: Array de coordenadas X da volta
            lap_y: Array de coordenadas Y da volta (ou Z dependendo do sistema)
        
        Returns:
            dict com:
                - valid: bool (True se válida, False se inválida)
                - violations: int (número de pontos fora)
                - violation_points: list de índices onde saiu
                - reason: str (motivo da invalidação)
        """
        violations = []
        
        logger.info(f"Validando volta com {len(lap_x)} pontos...")
        
        for i, (x, y) in enumerate(zip(lap_x, lap_y)):
            if not self.is_point_inside_track(x, y):
                violations.append(i)
        
        is_valid = len(violations) == 0
        
        if not is_valid:
            logger.warning(f"❌ VOLTA INVALIDADA: {len(violations)} pontos fora da pista")
            logger.warning(f"   Pontos fora: {violations[:10]}{'...' if len(violations) > 10 else ''}")
            reason = f"Carro saiu da pista em {len(violations)} ponto(s). VOLTA INVALIDADA pela regra de track limits."
        else:
            logger.info(f"✅ Volta VÁLIDA: todos os {len(lap_x)} pontos dentro da pista")
            reason = "Volta válida"
        
        return {
            "valid": is_valid,
            "violations": len(violations),
            "violation_points": violations,
            "violation_percentage": (len(violations) / len(lap_x)) * 100,
            "reason": reason
        }
    
    def get_safe_racing_line_bounds(self, safety_margin_meters: float = 0.5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Retorna limites da pista com margem de segurança
        
        Para a IA: usar limites ligeiramente internos para garantir
        que NUNCA chegue perto das bordas
        
        Args:
            safety_margin_meters: Margem de segurança em metros
        
        Returns:
            (safe_left_x, safe_left_y), (safe_right_x, safe_right_y)
        """
        # Calcular vetores normais às bordas
        # Mover bordas para dentro em `safety_margin_meters`
        
        center_x = self.track_data["centerline"]["x"]
        center_y = self.track_data["centerline"]["y"]
        
        # Vetor da centerline para bordas
        dx_left = self.left_x - np.array(center_x)
        dy_left = self.left_y - np.array(center_y)
        dist_left = np.sqrt(dx_left**2 + dy_left**2)
        
        dx_right = self.right_x - np.array(center_x)
        dy_right = self.right_y - np.array(center_y)
        dist_right = np.sqrt(dx_right**2 + dy_right**2)
        
        # Normalizar e aplicar margem
        dist_left[dist_left == 0] = 1
        dist_right[dist_right == 0] = 1
        
        safe_left_x = self.left_x - (dx_left / dist_left) * safety_margin_meters
        safe_left_y = self.left_y - (dy_left / dist_left) * safety_margin_meters
        
        safe_right_x = self.right_x - (dx_right / dist_right) * safety_margin_meters
        safe_right_y = self.right_y - (dy_right / dist_right) * safety_margin_meters
        
        logger.info(f"Limites de segurança calculados com margem de {safety_margin_meters}m")
        
        return (safe_left_x, safe_left_y), (safe_right_x, safe_right_y)
    
    def constrain_point_to_track(self, x: float, y: float) -> Tuple[float, float]:
        """
        Se um ponto estiver FORA da pista, move para o ponto mais próximo DENTRO
        
        Args:
            x, y: Coordenadas do ponto
        
        Returns:
            (x_constrained, y_constrained): Ponto ajustado para dentro da pista
        """
        if self.is_point_inside_track(x, y):
            return x, y
        
        # Ponto está FORA - encontrar ponto mais próximo na borda
        # Calcular distância para todas as bordas
        
        # Distâncias para borda esquerda
        dist_left = np.sqrt((self.left_x - x)**2 + (self.left_y - y)**2)
        idx_left = np.argmin(dist_left)
        
        # Distâncias para borda direita
        dist_right = np.sqrt((self.right_x - x)**2 + (self.right_y - y)**2)
        idx_right = np.argmin(dist_right)
        
        # Usar a borda mais próxima
        if dist_left[idx_left] < dist_right[idx_right]:
            return float(self.left_x[idx_left]), float(self.left_y[idx_left])
        else:
            return float(self.right_x[idx_right]), float(self.right_y[idx_right])
    
    def get_track_width_at_position(self, x: float, y: float) -> float:
        """
        Calcula largura da pista na posição mais próxima
        
        Útil para validação de posicionamento
        """
        # Encontrar ponto mais próximo na centerline
        center_x = np.array(self.track_data["centerline"]["x"])
        center_y = np.array(self.track_data["centerline"]["y"])
        
        distances = np.sqrt((center_x - x)**2 + (center_y - y)**2)
        closest_idx = np.argmin(distances)
        
        # Calcular largura neste ponto
        left_point = np.array([self.left_x[closest_idx], self.left_y[closest_idx]])
        right_point = np.array([self.right_x[closest_idx], self.right_y[closest_idx]])
        
        width = np.linalg.norm(left_point - right_point)
        
        return float(width)


def validate_lap_track_limits(lap_data: dict, track_data: dict) -> dict:
    """
    Função auxiliar para validar uma volta
    
    Args:
        lap_data: Dados da volta com 'x' e 'z' (ou 'y')
        track_data: Dados do trackmap
    
    Returns:
        Resultado da validação
    """
    validator = TrackLimitsValidator(track_data)
    
    lap_x = np.array(lap_data.get('x', lap_data.get('pos_x', [])))
    lap_z = np.array(lap_data.get('z', lap_data.get('pos_z', [])))
    
    return validator.validate_lap(lap_x, lap_z)