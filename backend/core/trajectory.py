# backend/core/trajectory.py
"""
TrajectoryAI — IA de Trajetória com suporte a referência FastF1.

Melhorias nesta versão:
  • fit() aceita reference_data (volta FastF1) para calcular perda REAL
    comparando o jogador ao piloto profissional segmento a segmento.
  • _build_raceline_from_scores() guia a linha gerada em direção à referência
    nos trechos com maior perda (blend adaptativo).
  • recommend() retorna a trajetória com Upsampling explícito para n_points
    (igual ao comprimento da centerline), garantindo que percorra a pista inteira.
  • Novo método upsample_trajectory() reutilizável externamente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import interp1d, splprep, splev
from scipy.ndimage import gaussian_filter1d


# ---------------------------------------------------------------------------
@dataclass
class TrajectoryResult:
    trajectory_x: List[float]
    trajectory_z: List[float]
    target_speed: List[float]
    segment_loss: List[float]
    estimated_gain_seconds: float
    notes: List[str]


# ---------------------------------------------------------------------------
class TrajectoryAI:
    """
    IA leve para geração de raceline ideal.

    Uso básico (sem FastF1):
        ai = TrajectoryAI(track_data)
        ai.fit(player_telemetry)
        result = ai.recommend()

    Uso com FastF1:
        ai = TrajectoryAI(track_data)
        ai.fit(player_telemetry, reference_data=f1_reference)
        result = ai.recommend()          # raceline mistura geometria + referência
    """

    def __init__(self, track_data: Dict[str, Any], n_segments: int = 40):
        self.track_data  = track_data
        self.n_segments  = n_segments
        self._n_track    = len(track_data["centerline"]["x"])

        self.cx = np.asarray(track_data["centerline"]["x"], float)
        self.cz = np.asarray(track_data["centerline"]["y"], float)
        self.lx = np.asarray(track_data["left_edge"]["x"],  float)
        self.lz = np.asarray(track_data["left_edge"]["y"],  float)
        self.rx = np.asarray(track_data["right_edge"]["x"], float)
        self.rz = np.asarray(track_data["right_edge"]["y"], float)

        self.curv = np.asarray(track_data["curvatures"],  float)
        self.wl   = np.asarray(track_data["width_left"],  float)
        self.wr   = np.asarray(track_data["width_right"], float)

        # Resultados do treino
        self.coef_: Optional[np.ndarray] = None
        self._ref_speed_per_seg: Optional[np.ndarray] = None  # velocidade F1 por segmento
        self._ref_traj_x: Optional[np.ndarray] = None         # trajetória F1 alinhada
        self._ref_traj_z: Optional[np.ndarray] = None

    # -----------------------------------------------------------------------
    # TREINO
    # -----------------------------------------------------------------------
    def fit(
        self,
        telemetry_data:  Dict[str, Any],
        reference_data:  Optional[Dict[str, Any]] = None,
    ) -> "TrajectoryAI":
        """
        Treina o modelo de perda por segmento.

        Args:
            telemetry_data: dict com chave 'best_lap_data' (pipeline padrão)
            reference_data: (opcional) dict no formato retornado por
                            FastF1Integration.prepare_reference_for_model()
                            Se fornecido, a perda é calculada como desvio
                            REAL em relação ao piloto profissional.
        """
        lap = telemetry_data["best_lap_data"]

        lap_x      = np.asarray(lap["x"],        float)
        lap_z      = np.asarray(lap["z"],        float)
        lap_speed  = np.asarray(lap["speed"],    float)
        lap_thr    = np.asarray(lap["throttle"], float) / 100.0
        lap_brk    = np.asarray(lap["brake"],    float) / 100.0

        track_idx = self._map_points_to_track_indices(lap_x, lap_z)
        seg_ids   = self._indices_to_segments(track_idx)

        # --- Processar referência FastF1 (se fornecida) ---
        has_ref = False
        if reference_data is not None:
            try:
                ref_lap   = reference_data["best_lap_data"]
                ref_x     = np.asarray(ref_lap["x"],     float)
                ref_z     = np.asarray(ref_lap["z"],     float)
                ref_speed = np.asarray(ref_lap["speed"], float)

                ref_track_idx  = self._map_points_to_track_indices(ref_x, ref_z)
                ref_seg_ids    = self._indices_to_segments(ref_track_idx)

                # Velocidade média da referência por segmento
                self._ref_speed_per_seg = np.zeros(self.n_segments)
                for seg in range(self.n_segments):
                    mask = ref_seg_ids == seg
                    self._ref_speed_per_seg[seg] = (
                        float(np.mean(ref_speed[mask])) if mask.sum() > 0 else 0.0
                    )

                # Guardar trajetória de referência para blending posterior
                self._ref_traj_x = ref_x
                self._ref_traj_z = ref_z
                has_ref = True
                logger.info("[TrajectoryAI] Referência FastF1 carregada com sucesso.")
            except Exception as exc:
                logger.warning(f"[TrajectoryAI] Falha ao processar referência: {exc}. Usando modo padrão.")

        # --- Construir features e labels por segmento ---
        X_list: List[List[float]] = []
        y_list: List[float]       = []

        for seg in range(self.n_segments):
            mask = seg_ids == seg
            if mask.sum() < 3:
                continue

            speed_mean   = float(np.mean(lap_speed[mask]))
            thr_mean     = float(np.mean(lap_thr[mask]))
            brk_mean     = float(np.mean(lap_brk[mask]))
            track_pts    = track_idx[mask]
            curv_mean    = float(np.mean(self.curv[track_pts]))
            width_mean   = float(np.mean(self.wl[track_pts] + self.wr[track_pts]))
            max_speed    = float(np.max(lap_speed)) if np.max(lap_speed) > 0 else 1.0

            if has_ref and self._ref_speed_per_seg is not None:
                ref_spd = self._ref_speed_per_seg[seg]
                if ref_spd > 0:
                    # Perda real = quanto o jogador está mais lento que o F1 neste trecho
                    speed_ratio = speed_mean / max(ref_spd, 1.0)
                    loss = (
                        2.5 * (1.0 - speed_ratio)          # desvio de velocidade real
                        + 1.5 * curv_mean                   # complexidade geométrica
                        + 1.2 * brk_mean                    # frenagens excessivas
                        + 0.3 * (1.0 - thr_mean)            # falta de aceleração
                    )
                else:
                    loss = self._proxy_loss(curv_mean, brk_mean, speed_mean, max_speed, thr_mean)
            else:
                loss = self._proxy_loss(curv_mean, brk_mean, speed_mean, max_speed, thr_mean)

            X_list.append([
                1.0,
                curv_mean,
                curv_mean ** 2,
                speed_mean / max_speed,
                brk_mean,
                thr_mean,
                width_mean,
            ])
            y_list.append(loss)

        if len(X_list) < 4:
            raise ValueError("Dados insuficientes para treinar a TrajectoryAI (< 4 segmentos válidos).")

        X = np.asarray(X_list, float)
        y = np.asarray(y_list, float)

        # Ridge via equação normal
        lam = 1e-3
        I   = np.eye(X.shape[1])
        self.coef_ = np.linalg.solve(X.T @ X + lam * I, X.T @ y)

        logger.info(f"[TrajectoryAI] Treinamento concluído — {len(X_list)} segmentos válidos, ref={has_ref}")
        return self

    @staticmethod
    def _proxy_loss(
        curv: float, brk: float, spd: float,
        max_spd: float, thr: float,
    ) -> float:
        return (
            1.8 * curv
            + 1.2 * brk
            - 0.8 * spd / max(max_spd, 1.0)
            + 0.2 * (1.0 - thr)
        )

    # -----------------------------------------------------------------------
    # RECOMENDAÇÃO
    # -----------------------------------------------------------------------
    def recommend(self, target_fps: int = 60) -> TrajectoryResult:
        # 1. Gera traçado e velocidades base
        # CORREÇÃO: Usando o método correto que já avalia a geometria e a referência da FastF1!
        scores = self._segment_scores_from_track()
        
        tx, tz = self._build_raceline_from_scores(scores)
        speeds = self._build_target_speed(scores)

        # 2. CALCULAR O TEMPO ACUMULADO (Time-based distance)
        # Distância entre cada ponto gerado
        dx = np.diff(tx, append=tx[0])
        dz = np.diff(tz, append=tz[0])
        ds = np.sqrt(dx**2 + dz**2)
        
        # v = d/t -> dt = d/v
        speeds_ms = np.clip(speeds / 3.6, 1.0, None)
        dt = ds / speeds_ms
        time_stamps = np.cumsum(dt)
        time_stamps = np.insert(time_stamps, 0, 0.0)[:-1]
        
        total_lap_time = time_stamps[-1]

        # 3. UPSAMPLING PARA 60 FPS (Sincronização com o Play)
        n_points_sync = int(total_lap_time * target_fps)
        t_uniform = np.linspace(0, total_lap_time, n_points_sync)

        # Interpolação de tudo contra o TEMPO, não contra o índice
        fx = interp1d(time_stamps, tx, kind='linear', fill_value="extrapolate")
        fz = interp1d(time_stamps, tz, kind='linear', fill_value="extrapolate")
        fs = interp1d(time_stamps, speeds, kind='linear', fill_value="extrapolate")

        return TrajectoryResult(
            trajectory_x=fx(t_uniform).tolist(),
            trajectory_z=fz(t_uniform).tolist(),
            target_speed=fs(t_uniform).tolist(),
            segment_loss=scores.tolist(),
            estimated_gain_seconds=0.0,
            notes=self._build_notes(scores)
        )

    # -----------------------------------------------------------------------
    # UPSAMPLING (público, reutilizável)
    # -----------------------------------------------------------------------
    @staticmethod
    def upsample_trajectory(
        x: np.ndarray,
        z: np.ndarray,
        n_points: int,
        smooth: float = 2.0,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Interpola (x, z) para n_points pontos uniformes em distância.

        1. Calcula distância acumulada normalizada como parâmetro.
        2. Encaixa um B-spline periódico (pista fechada).
        3. Reamostra em n_points amostras equidistantes.
        4. Aplica suavização gaussiana leve.

        Args:
            x, z:     arrays da trajetória bruta
            n_points: número de amostras desejadas
            smooth:   fator de suavização do spline (0 = interpolação exata)

        Returns:
            (x_up, z_up): arrays com comprimento n_points
        """
        x = np.asarray(x, float)
        z = np.asarray(z, float)

        if len(x) < 4:
            t = np.linspace(0, 1, n_points)
            t_src = np.linspace(0, 1, len(x))
            return (
                np.interp(t, t_src, x),
                np.interp(t, t_src, z),
            )

        # Remover pontos duplicados consecutivos
        diffs = np.hypot(np.diff(x), np.diff(z))
        keep  = np.concatenate([[True], diffs > 1e-8])
        x, z  = x[keep], z[keep]

        try:
            tck, _ = splprep([x, z], s=smooth, per=True, quiet=True)
        except Exception:
            tck, _ = splprep([x, z], s=smooth * 3, per=True, quiet=True)

        u_new      = np.linspace(0.0, 1.0, n_points)
        x_up, z_up = splev(u_new, tck)

        # Suavização gaussiana leve
        x_up = gaussian_filter1d(x_up, sigma=1.5)
        z_up = gaussian_filter1d(z_up, sigma=1.5)

        return np.asarray(x_up, float), np.asarray(z_up, float)

    # -----------------------------------------------------------------------
    # INTERNOS
    # -----------------------------------------------------------------------
    def _map_points_to_track_indices(
        self, px: np.ndarray, pz: np.ndarray
    ) -> np.ndarray:
        track = np.column_stack([self.cx, self.cz])
        idxs  = []
        for p in np.column_stack([px, pz]):
            d = np.sum((track - p) ** 2, axis=1)
            idxs.append(int(np.argmin(d)))
        return np.asarray(idxs, int)

    def _indices_to_segments(self, track_idx: np.ndarray) -> np.ndarray:
        n       = len(self.cx)
        seg_sz  = max(1, n // self.n_segments)
        return np.clip(track_idx // seg_sz, 0, self.n_segments - 1)

    def _segment_scores_from_track(self) -> np.ndarray:
        n      = len(self.cx)
        seg_sz = max(1, n // self.n_segments)
        scores = np.zeros(self.n_segments, float)

        for seg in range(self.n_segments):
            start = seg * seg_sz
            end   = n if seg == self.n_segments - 1 else (seg + 1) * seg_sz

            curv_mean  = float(np.mean(self.curv[start:end]))
            width_mean = float(np.mean(self.wl[start:end] + self.wr[start:end]))

            # Incorpora velocidade de referência FastF1 se disponível
            if self._ref_speed_per_seg is not None:
                ref_spd = self._ref_speed_per_seg[seg]
                ref_bonus = 0.5 / max(ref_spd / 100.0, 0.1)  # mais lento = score maior
            else:
                ref_bonus = 0.0

            scores[seg] = 1.5 * curv_mean + 0.15 / max(width_mean, 1.0) + ref_bonus

        mn, mx = scores.min(), scores.max()
        return (scores - mn) / (mx - mn + 1e-9)

    def _build_raceline_from_scores(
        self, scores: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Gera a raceline por deslocamento lateral.

        Se houver referência FastF1, nos segmentos críticos a linha é
        puxada em direção ao traçado do piloto profissional (blend adaptativo).
        """
        n      = len(self.cx)
        seg_sz = max(1, n // self.n_segments)

        # Normal da centerline
        dx   = np.gradient(self.cx)
        dz   = np.gradient(self.cz)
        norm = np.hypot(dx, dz) + 1e-9
        nx   = -dz / norm
        nz   =  dx / norm

        offsets = np.zeros(n, float)

        for seg in range(self.n_segments):
            start = seg * seg_sz
            end   = n if seg == self.n_segments - 1 else (seg + 1) * seg_sz

            width_mean = float(np.mean(self.wl[start:end] + self.wr[start:end]))
            score      = float(scores[seg])

            base   = 0.10 * width_mean
            extra  = 0.22 * width_mean * score
            offset = float(np.clip(base + extra, 0.0, 0.42 * width_mean))

            sign            = np.sign(np.mean(self.curv[start:end]))
            offsets[start:end] = -sign * offset

        x_new = self.cx + nx * offsets
        z_new = self.cz + nz * offsets

        # Blend com trajetória FastF1 nos trechos de maior perda
        if self._ref_traj_x is not None and self._ref_traj_z is not None:
            x_new, z_new = self._blend_with_reference(x_new, z_new, scores, seg_sz)

        return x_new, z_new

    def _blend_with_reference(
        self,
        x_gen: np.ndarray,
        z_gen: np.ndarray,
        scores: np.ndarray,
        seg_sz: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Blend suave entre a raceline gerada e a trajetória FastF1.
        Alpha por ponto = score_do_segmento * 0.55
        (máximo 55 % de peso na referência, para não copiar cegamente).
        """
        n = len(self.cx)

        # Interpolar a referência para n pontos (pode ter resolução diferente)
        ref_x, ref_z = TrajectoryAI.upsample_trajectory(
            np.asarray(self._ref_traj_x),
            np.asarray(self._ref_traj_z),
            n, smooth=3.0,
        )

        # Alpha point-wise
        alpha = np.zeros(n, float)
        for seg in range(self.n_segments):
            start = seg * seg_sz
            end   = n if seg == self.n_segments - 1 else (seg + 1) * seg_sz
            alpha[start:end] = float(scores[seg]) * 0.55

        alpha = gaussian_filter1d(alpha, sigma=seg_sz // 2 + 1)
        alpha = np.clip(alpha, 0.0, 0.55)

        x_blend = (1.0 - alpha) * x_gen + alpha * ref_x
        z_blend = (1.0 - alpha) * z_gen + alpha * ref_z

        return x_blend, z_blend

    def _build_target_speed(self, scores: np.ndarray) -> np.ndarray:
        n = len(self.cx)
        seg_size = max(1, n // self.n_segments)
        speeds = np.zeros(n, dtype=float)

        for seg in range(self.n_segments):
            start = seg * seg_size
            end = n if seg == self.n_segments - 1 else (seg + 1) * seg_size
            
            # 1. Suavizar a curvatura média para ignorar "trepidações" na reta
            curv_mean = float(np.mean(np.abs(self.curv[start:end])))
            
            # Se a curva for quase inexistente (reta), mantém velocidade máxima
            if curv_mean < 0.0005: # Threshold para retas como a subida dos boxes
                v = 310.0 
            else:
                # Física: v = sqrt(R * g * mu)
                radius = 1.0 / curv_mean
                v = np.sqrt(max(0.0, radius * 9.81 * 1.5)) * 3.6
                v = np.clip(v, 60.0, 310.0)

            speeds[start:end] = v

        # 2. SUAVIZAÇÃO CRUCIAL: Impede freadas bruscas de 1 frame
        from scipy.ndimage import gaussian_filter1d
        speeds = gaussian_filter1d(speeds, sigma=5)
        
        return speeds

    def _build_notes(self, scores: np.ndarray) -> List[str]:
        top   = np.argsort(scores)[-5:][::-1]
        notes = []
        has_ref = self._ref_speed_per_seg is not None

        for rank, seg in enumerate(top, start=1):
            seg_n  = int(seg) + 1
            sc     = float(scores[seg])
            prefix = f"Trecho {seg_n}"

            if has_ref and self._ref_speed_per_seg is not None:
                ref_spd = self._ref_speed_per_seg[seg]
                if ref_spd > 0:
                    notes.append(
                        f"{prefix}: alta perda de tempo. "
                        f"Referência F1 passa a ~{ref_spd:.0f} km/h aqui — "
                        f"ajuste seu ponto de frenagem e traçado."
                    )
                    continue

            notes.append(
                f"{prefix}: alta chance de ganho de tempo "
                f"(score={sc:.2f}). Revise frenagem e apex."
            )

        return notes


# ---------------------------------------------------------------------------
# Logger local (evita import circular)
# ---------------------------------------------------------------------------
import logging
logger = logging.getLogger(__name__)
