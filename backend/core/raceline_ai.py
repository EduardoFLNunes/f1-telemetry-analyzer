import numpy as np
from typing import Dict, List
from scipy.interpolate import splprep, splev
from scipy.ndimage import gaussian_filter1d

# Importamos a sua IA de Trajetória para gerar o traçado dinâmico!
from core.trajectory import TrajectoryAI

class RacelineAI:
    def __init__(self, track_data: Dict):
        self.track_data = track_data
        self.corners = track_data["corners"]
        self.centerline_x = np.array(track_data["centerline"]["x"])
        self.centerline_y = np.array(track_data["centerline"]["y"])
        self.left_edge_x = np.array(track_data["left_edge"]["x"])
        self.left_edge_y = np.array(track_data["left_edge"]["y"])
        self.right_edge_x = np.array(track_data["right_edge"]["x"])
        self.right_edge_y = np.array(track_data["right_edge"]["y"])
        self.curvatures = np.array(track_data["curvatures"])

    # ==========================
    # 🔥 FUNÇÃO PRINCIPAL
    # ==========================
    def generate_optimal_raceline(self, player_data: Dict) -> Dict:
        # 1. OBTER O TRAÇADO DA NOVA IA (Resolve o problema do traçado antigo)
        try:
            traj_ai = TrajectoryAI(self.track_data, n_segments=40)
            traj_ai.fit(player_data)
            recommendation = traj_ai.recommend()
            
            x_ai = np.array(recommendation["trajectory"]["x"])
            z_ai = np.array(recommendation["trajectory"]["z"])
            ideal_trajectory = np.column_stack([x_ai, z_ai])
            insights = recommendation.get("notes", ["Traçado otimizado gerado com sucesso."])
        except Exception as e:
            # Fallback de segurança
            ideal_trajectory = np.column_stack([self.centerline_x, self.centerline_y])
            insights = [f"Erro ao usar IA de aprendizado, usando centerline: {str(e)}"]

        # 2. Garantir track limits
        ideal_trajectory = self._enforce_track_limits(ideal_trajectory, margin=1.0)
        
        # 3. Aplicar a Nova Física de Corrida
        distances = self._calculate_distances(ideal_trajectory)
        ideal_speeds = self._calculate_ideal_speeds(ideal_trajectory)
        ideal_inputs = self._calculate_ideal_inputs(ideal_speeds, distances)
        estimated_time = self._estimate_lap_time(ideal_trajectory, ideal_speeds)
        
        # 4. Extrair Apexes
        ideal_apexes = self._calculate_ideal_apexes()

        result = {
            "trajectory": {
                "x": ideal_trajectory[:, 0],
                "z": ideal_trajectory[:, 1],
                "distance": distances
            },
            "speed": ideal_speeds,
            "throttle": ideal_inputs["throttle"],
            "brake": ideal_inputs["brake"],
            "estimated_time": estimated_time,
            "apexes": ideal_apexes,
            "insights": insights,
            "improvements": []
        }

        # Sanitização para o FastAPI não quebrar
        return self._sanitize(result)

    # ==========================
    # 🚀 FÍSICA E VELOCIDADE
    # ==========================
    def _calculate_ideal_speeds(self, trajectory: np.ndarray) -> np.ndarray:
        """Calcula velocidades com física corrigida baseada na distância real"""
        mu = 1.6          # Grip lateral
        g = 9.81
        max_speed = 340 / 3.6  # m/s (Permite chegar até 340 km/h)
        accel = 8.5       # m/s² 
        brake = 15.0      # m/s² 

        # Curvatura corrigida (baseada em ds, não no índice)
        dx = np.gradient(trajectory[:, 0])
        dy = np.gradient(trajectory[:, 1])
        ds = np.hypot(dx, dy)
        ds[ds == 0] = 1e-6

        tx = dx / ds
        ty = dy / ds
        dtx = np.gradient(tx)
        dty = np.gradient(ty)
        
        # Filtrar o ruído da pista para a velocidade não ficar caindo do nada
        curvatures = np.hypot(dtx, dty) / ds
        curvatures = gaussian_filter1d(curvatures, sigma=3)

        speeds = np.zeros(len(trajectory))

        # 1. Limite Lateral nas curvas
        for i, c in enumerate(curvatures):
            if c < 1e-5:
                speeds[i] = max_speed
            else:
                r = 1.0 / c
                v = np.sqrt(mu * g * r)
                speeds[i] = min(v, max_speed)

        # Distância entre cada ponto (para calcular aceleração/frenagem)
        step_dists = np.linalg.norm(np.diff(trajectory, axis=0), axis=1)
        step_dists = np.append(step_dists, step_dists[-1])

        # 2. Forward pass (Aceleração nas retas)
        for i in range(1, len(speeds)):
            v_prev = speeds[i - 1]
            v_max = np.sqrt(v_prev**2 + 2 * accel * step_dists[i - 1])
            speeds[i] = min(speeds[i], v_max)

        # 3. Backward pass (Frenagem nas chegadas de curva)
        for i in range(len(speeds) - 2, -1, -1):
            v_next = speeds[i + 1]
            v_max = np.sqrt(v_next**2 + 2 * brake * step_dists[i])
            speeds[i] = min(speeds[i], v_max)

        return speeds * 3.6 # Retorna em km/h

    # ==========================
    # 🎮 INPUTS (ACELERADOR E FREIO)
    # ==========================
    def _calculate_ideal_inputs(self, speeds_kmh, distances):
        """Usa Torricelli para gerar inputs de 0 a 100% que imitam um piloto"""
        speeds_ms = speeds_kmh / 3.6
        n = len(speeds_ms)
        throttle = np.zeros(n)
        brake = np.zeros(n)

        for i in range(n - 1):
            v1 = speeds_ms[i]
            v2 = speeds_ms[i + 1]
            ds = distances[i + 1] - distances[i]

            if ds <= 0: continue

            # Física: a = (v2^2 - v1^2) / 2*ds
            a = (v2**2 - v1**2) / (2 * ds)

            if a > 1.0: # Acelerando
                t = (a / 8.5) * 100
                throttle[i] = t
            elif a < -1.0: # Freando
                b = (abs(a) / 15.0) * 100
                brake[i] = b
            else:
                # Mantendo velocidade
                throttle[i] = 15

        # Suavizar as transições de pedal
        throttle = gaussian_filter1d(throttle, sigma=2)
        brake = gaussian_filter1d(brake, sigma=2)

        # TRAVAS RÍGIDAS DE SEGURANÇA (0% a 100%)
        throttle = np.clip(throttle, 0, 100)
        brake = np.clip(brake, 0, 100)

        # Copiar penúltimo para último
        throttle[-1] = throttle[-2]
        brake[-1] = brake[-2]

        return {"throttle": throttle, "brake": brake}

    # ==========================
    # 📏 OUTRAS UTILIDADES
    # ==========================
    def _calculate_distances(self, traj):
        dist = np.linalg.norm(np.diff(traj, axis=0), axis=1)
        return np.concatenate([[0], np.cumsum(dist)])

    def _estimate_lap_time(self, traj, speeds_kmh):
        dist = np.linalg.norm(np.diff(traj, axis=0), axis=1)
        speeds_ms = speeds_kmh[:-1] / 3.6
        speeds_ms[speeds_ms == 0] = 1 # Evitar dividir por zero
        return float(np.sum(dist / speeds_ms))

    def _calculate_ideal_apexes(self) -> List[Dict]:
        apexes = []
        for corner in self.corners:
            start = int(corner["start_idx"])
            end = int(corner["end_idx"])
            if start >= len(self.curvatures) or end > len(self.curvatures):
                continue
                
            segment = self.curvatures[start:end]
            if len(segment) == 0: continue
            
            apex_local = int(np.argmax(segment))
            apex_global = int(start + apex_local)

            apexes.append({
                "corner_id": int(corner["corner_id"]),
                "apex_idx": int(apex_global),
                "apex_x": float(self.centerline_x[apex_global]),
                "apex_y": float(self.centerline_y[apex_global]),
                "curvature": float(segment[apex_local])
            })
        return apexes

    def _enforce_track_limits(self, trajectory: np.ndarray, margin: float = 1.0) -> np.ndarray:
        clamped_trajectory = np.zeros_like(trajectory)

        for i, point in enumerate(trajectory):
            px, py = point[0], point[1]
            distances = np.sqrt((self.centerline_x - px)**2 + (self.centerline_y - py)**2)
            idx = np.argmin(distances)
            
            lx, ly = self.left_edge_x[idx], self.left_edge_y[idx]
            rx, ry = self.right_edge_x[idx], self.right_edge_y[idx]
            
            track_vec = np.array([rx - lx, ry - ly])
            track_width = np.linalg.norm(track_vec)
            
            if track_width < 0.1:
                clamped_trajectory[i] = point
                continue
                
            track_dir = track_vec / track_width
            point_vec = np.array([px - lx, py - ly])
            projection = np.dot(point_vec, track_dir)
            clamped_projection = np.clip(projection, margin, track_width - margin)
            
            new_x = lx + track_dir[0] * clamped_projection
            new_y = ly + track_dir[1] * clamped_projection
            
            clamped_trajectory[i] = [new_x, new_y]
            
        return clamped_trajectory

    def _sanitize(self, obj):
        if isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(v) for v in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        return obj