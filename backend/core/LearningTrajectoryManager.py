import numpy as np
from scipy.interpolate import splprep, splev
from typing import Dict, List, Any

class LearningTrajectoryManager:
    """
    IA de Aprendizado por Segmentos para Otimização de Trajetória.
    Combina análise de telemetria com geometria de pista.
    """
    
    def __init__(self, track_data: Dict[str, Any], n_segments: int = 50):
        self.track_data = track_data
        self.n_segments = n_segments
        
        # Dados base da pista
        self.cx = np.array(track_data["centerline"]["x"])
        self.cz = np.array(track_data["centerline"]["y"])
        self.curvatures = np.array(track_data["curvatures"])
        
        # Larguras (usadas para limitar o deslocamento da IA)
        self.width_left = np.array(track_data.get("width_left", np.ones_like(self.cx) * 5))
        self.width_right = np.array(track_data.get("width_right", np.ones_like(self.cx) * 5))

    def analyze_and_optimize(self, telemetry_lap: Dict[str, Any]) -> Dict[str, Any]:
        """
        Função principal: 
        1. Avalia o piloto 
        2. Gera scores 
        3. Cria nova raceline
        """
        # 1. Mapear telemetria para os segmentos da pista
        seg_indices = self._get_segment_indices()
        scores = self._calculate_segment_scores(telemetry_lap, seg_indices)
        
        # 2. Gerar a nova trajetória baseada nos scores de perda
        optimized_traj = self._generate_optimized_line(scores, seg_indices)
        
        # 3. Gerar insights baseados nos piores segmentos
        insights = self._generate_insights(scores)
        
        return {
            "optimized_trajectory": optimized_traj,
            "segment_scores": scores.tolist(),
            "insights": insights
        }

    def _get_segment_indices(self) -> List[np.ndarray]:
        """Divide os índices da pista em N blocos."""
        n_points = len(self.cx)
        return np.array_split(np.arange(n_points), self.n_segments)

    def _calculate_segment_scores(self, lap: Dict, seg_indices: List[np.ndarray]) -> np.ndarray:
        """
        Calcula onde o piloto perde tempo. 
        0.0 = Perfeito | 1.0 = Grande oportunidade de melhora.
        """
        scores = np.zeros(self.n_segments)
        
        # Dados do piloto (simplificado para o exemplo)
        lap_speed = np.array(lap["speed"])
        
        for i, idxs in enumerate(seg_indices):
            # Média de curvatura do trecho
            avg_curv = np.mean(np.abs(self.curvatures[idxs]))
            # Velocidade média do piloto no trecho
            avg_speed = np.mean(lap_speed[idxs]) if i < len(lap_speed) else 50
            
            # Lógica: Se a curvatura é alta e a velocidade é baixa, o score de 'perda' sobe
            # Usamos uma normalização simples
            loss_potential = avg_curv * (1.0 / (avg_speed + 1e-5))
            scores[i] = loss_potential
            
        # Normalizar entre 0 e 1
        if scores.max() > 0:
            scores = (scores - scores.min()) / (scores.max() - scores.min())
            
        return scores

    def _generate_optimized_line(self, scores: np.ndarray, seg_indices: List[np.ndarray]) -> Dict:
        """
        Cria a raceline movendo os pontos para o lado interno (apex) 
        baseado no score de perda.
        """
        n_points = len(self.cx)
        new_x = self.cx.copy()
        new_z = self.cz.copy()
        
        # Cálculo de vetores normais (direção lateral da pista)
        dx = np.gradient(self.cx)
        dz = np.gradient(self.cz)
        nx = -dz / (np.sqrt(dx**2 + dz**2) + 1e-8)
        nz = dx / (np.sqrt(dx**2 + dz**2) + 1e-8)

        for i, idxs in enumerate(seg_indices):
            score = scores[i]
            # Quanto maior o score, mais tentamos 'cortar' a curva (levar ao limite interno)
            # Deslocamento máximo de 80% da largura da pista
            offset_magnitude = score * (self.width_left[idxs] * 0.8)
            
            # Direção do deslocamento baseada na curvatura (para dentro da curva)
            side = np.sign(self.curvatures[idxs])
            
            new_x[idxs] += nx[idxs] * offset_magnitude * side
            new_z[idxs] += nz[idxs] * offset_magnitude * side

        # Suavização com Spline para a linha não ficar "quebrada"
        tck, u = splprep([new_x, new_z], s=5.0, per=True)
        u_fine = np.linspace(0, 1, n_points)
        x_smooth, z_smooth = splev(u_fine, tck)
        
        return {"x": x_smooth.tolist(), "z": z_smooth.tolist()}

    def _generate_insights(self, scores: np.ndarray) -> List[str]:
        """Identifica os 3 piores trechos para dar feedback ao usuário."""
        worst_segments = np.argsort(scores)[-3:][::-1]
        messages = []
        for seg_id in worst_segments:
            messages.append(f"Trecho {seg_id + 1}: Você está perdendo muito tempo aqui. Tente usar mais a largura da pista na entrada.")
        return messages