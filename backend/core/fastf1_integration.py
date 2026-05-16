"""
Módulo de Integração FastF1
Busca telemetria real de pilotos de F1, alinha coordenadas com o trackmap
e prepara os dados para alimentar o modelo de aprendizagem.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d, splprep, splev
from scipy.optimize import minimize_scalar

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_GP_CONFIG = {
    "Brazil":     {"year": 2024, "session": "Q"},
    "Bahrain":    {"year": 2024, "session": "Q"},
    "Monaco":     {"year": 2024, "session": "Q"},
    "Monza":      {"year": 2024, "session": "Q"},
    "Silverstone":{"year": 2024, "session": "Q"},
}


class FastF1Integration:
    """
    Integração com a biblioteca FastF1 para obter telemetria real de F1.

    Fluxo:
        1. get_fastest_lap()  → dict com telemetria bruta
        2. align_coordinates() → dict com coordenadas alinhadas ao trackmap
        3. upsample_to_resolution() → mesmo nº de pontos que o trackmap
        4. prepare_reference_for_model() → formato dict compatível com TrajectoryAI
    """

    def __init__(self, cache_dir: str = "data/fastf1_cache"):
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        self._enable_cache()

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------
    def _enable_cache(self) -> None:
        try:
            import fastf1
            fastf1.Cache.enable_cache(self.cache_dir)
            logger.info(f"[FastF1] Cache habilitado em: {self.cache_dir}")
        except Exception as exc:
            logger.warning(f"[FastF1] Não foi possível habilitar cache: {exc}")

    # ------------------------------------------------------------------
    # Busca de volta
    # ------------------------------------------------------------------
    def get_fastest_lap(
        self,
        year: int = 2023,
        gp: str = "Brazil",
        session_type: str = "Q",
    ) -> Dict[str, Any]:
        """
        Busca e retorna a volta mais rápida de uma sessão real de F1.

        Args:
            year: Temporada (ex: 2024)
            gp: Nome do GP (ex: "Brazil", "Monaco")
            session_type: 'Q' (Qualifying), 'R' (Race), 'FP1/2/3'

        Returns:
            Dict com metadados do piloto e telemetria bruta
        """
        import fastf1  # import tardio para não quebrar se não instalado

        logger.info(f"[FastF1] Buscando {year} {gp} {session_type} ...")
        session = fastf1.get_session(year, gp, session_type)
        
        # 1. Camada de Segurança e Pedido Explícito
        try:
            # laps=True garante que os dados da volta são processados
            session.load(laps=True, telemetry=True, weather=False, messages=False)
        except Exception as exc:
            raise ValueError(f"Falha ao carregar dados do FastF1. Verifique a internet ou os servidores da FIA. Erro: {exc}")

        # 2. Verificação de segurança para evitar o erro "has not been loaded yet"
        if getattr(session, '_laps', None) is None or len(session.laps) == 0:
            raise ValueError(f"A sessão foi carregada, mas não contém voltas válidas para {year} {gp} {session_type}.")

        fastest_lap = session.laps.pick_fastest()
        if fastest_lap is None or (hasattr(fastest_lap, "empty") and fastest_lap.empty):
            raise ValueError(f"Nenhuma volta mais rápida encontrada para {year} {gp} {session_type}")

        telemetry = fastest_lap.get_telemetry().add_distance()

        # --- Coordenadas ---
        x = self._safe_float(telemetry, "X")
        y = self._safe_float(telemetry, "Y")

        # --- Canais dinâmicos ---
        speed    = self._safe_float(telemetry, "Speed")
        throttle = self._safe_float(telemetry, "Throttle")
        brake_raw = telemetry["Brake"].values if "Brake" in telemetry.columns else np.zeros(len(x))
        brake = (brake_raw.astype(float) * 100.0) if brake_raw.dtype == bool or brake_raw.max() <= 1.5 else brake_raw.astype(float)
        distance = self._safe_float(telemetry, "Distance")

        # --- Tempo normalizado ---
        time_s = telemetry["Time"].dt.total_seconds().values.astype(float)
        time_s -= time_s[0]

        # --- Metadados ---
        try:
            lap_time = float(fastest_lap["LapTime"].total_seconds())
        except Exception:
            lap_time = float(time_s[-1])

        driver = str(fastest_lap.get("Driver", "Unknown"))
        team   = str(fastest_lap.get("Team",   "Unknown"))

        logger.info(
            f"[FastF1] Volta mais rápida: {driver} ({team}) "
            f"- {lap_time:.3f}s - {len(x)} pontos"
        )

        return {
            "driver":       driver,
            "team":         team,
            "lap_time":     lap_time,
            "year":         year,
            "gp":           gp,
            "session_type": session_type,
            "n_points":     int(len(x)),
            "telemetry": {
                "x":        x.tolist(),
                "y":        y.tolist(),
                "speed":    speed.tolist(),
                "throttle": throttle.tolist(),
                "brake":    brake.tolist(),
                "distance": distance.tolist(),
                "time":     time_s.tolist(),
            },
        }
    # ------------------------------------------------------------------
    # Alinhamento de coordenadas
    # ------------------------------------------------------------------
    def align_coordinates(
        self,
        fastf1_data: Dict[str, Any],
        track_data:  Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Alinha o sistema de coordenadas do FastF1 ao trackmap usando o Spatial Engine.
        """
        spatial_index = track_data.get("_spatial_index")
        
        if spatial_index:
            logger.info("[FastF1] Usando Spatial Engine para alinhamento profissional")
            f1_x = np.asarray(fastf1_data["telemetry"]["x"], float)
            f1_y = np.asarray(fastf1_data["telemetry"]["y"], float)
            
            # O FastF1 pode estar em escala/rotação diferente. 
            # Primeiro, aplicamos uma pré-sincronização baseada no comprimento total.
            f1_len = float(np.sum(np.hypot(np.diff(f1_x), np.diff(f1_y))))
            scale = spatial_index.total_length / max(f1_len, 1.0)
            
            # Se a escala for muito diferente (ex: metros vs km), corrigimos.
            # FastF1 costuma estar em metros, mas o centro pode estar longe.
            
            # Usamos o buscador de rotação original para achar a orientação inicial
            # (já que o KD-Tree é sensível a translação/rotação bruta)
            f1_xc, f1_yc = f1_x - f1_x.mean(), f1_y - f1_y.mean()
            best_angle = self._find_best_rotation(
                f1_xc * scale, f1_yc * scale,
                spatial_index.cx - spatial_index.cx.mean(),
                spatial_index.cz - spatial_index.cz.mean()
            )
            
            ca, sa = np.cos(best_angle), np.sin(best_angle)
            temp_x = (f1_xc * scale * ca - f1_yc * scale * sa) + spatial_index.cx.mean()
            temp_y = (f1_xc * scale * sa + f1_yc * scale * ca) + spatial_index.cz.mean()
            
            # Agora projetamos com precisão no KD-Tree
            s, L = spatial_index.project(temp_x, temp_y)
            
            # Reconstruímos (x, y) alinhados perfeitamente à geometria da pista
            cx, cz = spatial_index.get_interpolated_centerline(s)
            tx = np.gradient(cx)
            tz = np.gradient(cz)
            norm = np.hypot(tx, tz) + 1e-9
            nx, nz = -tz / norm, tx / norm
            
            aligned_x = cx + nx * L
            aligned_y = cz + nz * L
            
            result = {k: v for k, v in fastf1_data.items() if k != "telemetry"}
            result["telemetry"]  = {k: v for k, v in fastf1_data["telemetry"].items()}
            result["telemetry"]["x"] = aligned_x.tolist()
            result["telemetry"]["y"] = aligned_y.tolist()
            result["telemetry"]["distance"] = s.tolist() # Sincronizado!
            result["aligned"] = True
            result["alignment"] = {
                "scale":     float(scale),
                "angle_deg": float(np.degrees(best_angle)),
                "method": "spatial_engine"
            }
            return result
        
        # Fallback para o método legado
        logger.warning("[FastF1] Spatial Index não encontrado. Usando alinhamento legado.")
        f1_x = np.asarray(fastf1_data["telemetry"]["x"], float)
        f1_y = np.asarray(fastf1_data["telemetry"]["y"], float)

        track_x = np.asarray(track_data["centerline"]["x"], float)
        track_y = np.asarray(track_data["centerline"]["y"], float)

        # Centros
        f1_cx, f1_cy       = f1_x.mean(),    f1_y.mean()
        track_cx, track_cy = track_x.mean(), track_y.mean()

        # Centralizar FastF1
        f1_xc = f1_x - f1_cx
        f1_yc = f1_y - f1_cy

        # Escala pelo comprimento de arco
        f1_len    = float(np.sum(np.hypot(np.diff(f1_x),    np.diff(f1_y))))
        track_len = float(np.sum(np.hypot(np.diff(track_x), np.diff(track_y))))
        scale = track_len / max(f1_len, 1.0)

        f1_xs = f1_xc * scale
        f1_ys = f1_yc * scale

        # Melhor rotação
        best_angle = self._find_best_rotation(
            f1_xs, f1_ys,
            track_x - track_cx,
            track_y - track_cy,
        )

        ca, sa = np.cos(best_angle), np.sin(best_angle)
        aligned_x = f1_xs * ca - f1_ys * sa + track_cx
        aligned_y = f1_xs * sa + f1_ys * ca + track_cy

        logger.info(
            f"[FastF1] Alinhamento: escala={scale:.4f}, "
            f"ângulo={np.degrees(best_angle):.1f}°"
        )

        result = {k: v for k, v in fastf1_data.items() if k != "telemetry"}
        result["telemetry"]  = {k: v for k, v in fastf1_data["telemetry"].items()}
        result["telemetry"]["x"] = aligned_x.tolist()
        result["telemetry"]["y"] = aligned_y.tolist()
        result["aligned"] = True
        result["alignment"] = {
            "scale":     float(scale),
            "angle_deg": float(np.degrees(best_angle)),
        }
        return result

    def _find_best_rotation(
        self,
        src_x: np.ndarray,
        src_y: np.ndarray,
        ref_x: np.ndarray,
        ref_y: np.ndarray,
        n_coarse: int = 72,
    ) -> float:
        """Busca grossa (72 ângulos) + refinamento local (Brent)."""
        ref_pts = np.column_stack([ref_x, ref_y])
        step    = max(1, len(src_x) // 150)
        sx, sy  = src_x[::step], src_y[::step]

        def cost(angle: float) -> float:
            ca, sa = np.cos(angle), np.sin(angle)
            rx, ry = sx * ca - sy * sa, sx * sa + sy * ca
            pts = np.column_stack([rx, ry])
            dists = [float(np.min(np.sum((ref_pts - p) ** 2, axis=1))) for p in pts[::4]]
            return float(np.mean(dists))

        angles = np.linspace(0.0, 2 * np.pi, n_coarse, endpoint=False)
        costs  = [cost(a) for a in angles]
        best   = angles[int(np.argmin(costs))]

        res = minimize_scalar(cost, bounds=(best - 0.25, best + 0.25), method="bounded")
        return float(res.x)

    # ------------------------------------------------------------------
    # Upsampling / interpolação temporal
    # ------------------------------------------------------------------
    def upsample_to_resolution(
        self,
        telemetry: Dict[str, Any],
        n_points:  int,
        keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Interpola todos os canais para exatamente n_points amostras
        uniformemente espaçadas em distância, garantindo que a volta
        percorra TODO o traçado sem lacunas.

        Args:
            telemetry: dict com chaves "x", "y", e outros canais
            n_points:  número alvo de pontos (tipicamente = len(centerline))
            keys:      lista de canais a interpolar (default: x, y, speed, throttle, brake)

        Returns:
            dict com os mesmos canais, todos com comprimento n_points
        """
        if keys is None:
            keys = ["x", "y", "speed", "throttle", "brake"]

        x = np.asarray(telemetry["x"], float)
        y = np.asarray(telemetry["y"], float)

        # Parâmetro = distância acumulada normalizada
        ds   = np.hypot(np.diff(x), np.diff(y))
        s    = np.concatenate([[0.0], np.cumsum(ds)])
        s_n  = s / (s[-1] + 1e-10)

        # Remover duplicatas de parâmetro (necessário para interp1d)
        _, uid = np.unique(s_n, return_index=True)
        s_u   = s_n[uid]
        s_new = np.linspace(0.0, 1.0, n_points)

        result: Dict[str, Any] = {}

        for key in keys:
            if key not in telemetry:
                continue
            arr = np.asarray(telemetry[key], float)[uid]
            if len(arr) < 4:
                result[key] = np.interp(s_new, s_u, arr).tolist()
                continue

            f = interp1d(
                s_u, arr, kind="cubic",
                bounds_error=False,
                fill_value=(float(arr[0]), float(arr[-1])),
            )
            out = f(s_new)

            # Clips por canal
            if key == "speed":
                out = np.clip(out, 0.0, 420.0)
            elif key in ("throttle", "brake"):
                out = np.clip(out, 0.0, 100.0)

            result[key] = out.tolist()

        # Distância total real
        if "distance" in telemetry:
            total = float(np.asarray(telemetry["distance"])[-1])
            result["distance"] = np.linspace(0.0, total, n_points).tolist()

        # Tempo linear aproximado (para exibição)
        if "time" in telemetry:
            total_t = float(np.asarray(telemetry["time"])[-1])
            result["time"] = np.linspace(0.0, total_t, n_points).tolist()

        return result

    # ------------------------------------------------------------------
    # Preparo para o modelo TrajectoryAI
    # ------------------------------------------------------------------
    def prepare_reference_for_model(
        self,
        fastf1_data: Dict[str, Any],
        track_data:  Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Converte dados FastF1 (após align_coordinates) para o formato
        esperado pelo TrajectoryAI.fit().

        FastF1 usa Y para o eixo horizontal (plano de pista),
        enquanto nosso pipeline usa Z. Esta função faz o mapeamento
        Y → Z.
        """
        n_track = len(track_data["centerline"]["x"])
        tel = self.upsample_to_resolution(
            fastf1_data["telemetry"], n_track,
            keys=["x", "y", "speed", "throttle", "brake"],
        )

        return {
            "best_lap_data": {
                "x":        tel["x"],
                "z":        tel["y"],     # FastF1 Y → nosso eixo Z
                "speed":    tel["speed"],
                "throttle": tel["throttle"],
                "brake":    tel["brake"],
                "distance": tel.get("distance", []),
            },
            "metadata": {
                "driver":      fastf1_data.get("driver",  "F1 Reference"),
                "team":        fastf1_data.get("team",    "Unknown"),
                "lap_time":    fastf1_data.get("lap_time", 0.0),
                "year":        fastf1_data.get("year",    2023),
                "gp":          fastf1_data.get("gp",      "Brazil"),
                "session":     fastf1_data.get("session_type", "Q"),
                "source":      "fastf1",
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_float(df: "pd.DataFrame", col: str) -> np.ndarray:
        """Extrai coluna como float64, preenchendo NaN com forward-fill."""
        series = df[col] if col in df.columns else pd.Series(np.zeros(len(df)))
        return series.ffill().bfill().values.astype(float)
