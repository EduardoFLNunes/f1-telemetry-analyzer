"""
Módulo de processamento de telemetria
Valida, limpa e processa dados de telemetria do jogador
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class TelemetryProcessor:
    """Processa telemetria do jogador"""
    
    def process_telemetry(self, df: pd.DataFrame, track_data: Dict, sim_type: str = "F1-25") -> Dict:
        """
        Processa telemetria bruta usando o pipeline profissional Fase 1.2.
        """
        try:
            if df is None or df.empty:
                raise ValueError("DataFrame de telemetria está vazio")

            # 1. Normalização (SimAdapter)
            from core.normalization import SimAdapter
            adapter = SimAdapter(sim_type=sim_type)
            
            # Normalizar nomes de colunas para facilitar extração
            df.columns = df.columns.str.strip().str.lower()
            
            # Extrair e normalizar canais básicos
            raw_x = df['pos_x'].values if 'pos_x' in df.columns else df['x'].values
            raw_y = df['pos_y'].values if 'pos_y' in df.columns else df['y'].values
            raw_z = df['pos_z'].values if 'pos_z' in df.columns else df['z'].values
            
            pos_x, pos_z = adapter.normalize_pos(raw_x, raw_y, raw_z)
            speed = adapter.normalize_speed(df['speed'].values)
            throttle, brake = adapter.normalize_inputs(df['throttle'].values, df['brake'].values)
            
            # Tentar obter heading (se disponível no CSV)
            headings = None
            if 'heading_x' in df.columns and 'heading_z' in df.columns:
                headings = adapter.normalize_heading(df['heading_x'].values, 0, df['heading_z'].values)
            
            # 2. Identificar Melhor Volta (usando dados normalizados)
            df_norm = pd.DataFrame({
                'session_time': df['session_time'].values,
                'lap': df['lap'].values,
                'pos_x': pos_x,
                'pos_z': pos_z,
                'speed': speed,
                'throttle': throttle,
                'brake': brake
            })
            best_lap_df = self._find_best_lap(df_norm)
            
            # 3. Projeção Espacial (TrackSpline)
            spatial_index = track_data.get("_spatial_index")
            if not spatial_index:
                raise ValueError("TrackSpline não encontrado nos dados da pista.")
            
            # Projeção de sequência com continuidade temporal
            # Se tivermos headings, usamos para disambiguação
            h_lap = headings[best_lap_df.index] if headings is not None else None
            projection = spatial_index.project_sequence(
                best_lap_df['pos_x'].values, 
                best_lap_df['pos_z'].values,
                headings=h_lap
            )
            
            best_lap_df['s'] = projection['s']
            best_lap_df['L'] = projection['L']
            
            # 4. Resampling (TelemetryResampler)
            from core.resampling import TelemetryResampler
            resampler = TelemetryResampler(n_points=2048)
            
            lap_channels = {
                "s": best_lap_df['s'].values,
                "L": best_lap_df['L'].values,
                "speed": best_lap_df['speed'].values,
                "throttle": best_lap_df['throttle'].values,
                "brake": best_lap_df['brake'].values,
                "session_time": best_lap_df['session_time'].values
            }
            
            resampled = resampler.resample_lap(lap_channels, spatial_index.total_length)
            
            # 5. Validação Espacial (TelemetryValidator)
            from core.validation import TelemetryValidator
            validator = TelemetryValidator()
            validation_report = validator.validate_lap(resampled)
            
            # 6. PRO MODE: Dinâmica e Física (Phase 1.3)
            from core.dynamics import TelemetryDynamics
            from core.physics_model import TrackPhysicsModel
            from core.physics_validator import TelemetryPhysicsValidator
            from core.features import FeatureVectorBuilder
            
            # Calcular Curvatura Real (kappa) a partir do Spline
            resampled["curvature"] = spatial_index._compute_kappa(resampled["s"])
            
            # Dinâmica Veicular (G-forces, Yaw, Jerk)
            dyn_engine = TelemetryDynamics(sample_rate=60.0) # Assumindo normalizado
            dynamics = dyn_engine.compute_dynamics(resampled)
            
            # Validação Física
            phys_validator = TelemetryPhysicsValidator()
            phys_report = phys_validator.validate_dynamics(dynamics)
            
            # Segmentação de Pista (Apexes e Fases)
            track_phys = TrackPhysicsModel(track_data)
            corners = track_phys.segment_corners()
            
            # Feature Engineering para ML (PyTorch Ready)
            feature_builder = FeatureVectorBuilder(n_points=2048)
            ml_tensor = feature_builder.build_lap_tensor({**resampled, **dynamics}, spatial_index.total_length)

            if not validation_report["valid"] or not phys_report["valid"]:
                logger.warning(f"Problemas de integridade detectados: {validation_report['issues']} {phys_report['issues']}")

            # Calcular métricas e estilo
            resampled_df = pd.DataFrame({**resampled, **dynamics})
            metrics = self._calculate_metrics(resampled_df)
            driving_style = self._analyze_driving_style(resampled_df)
            
            lap_time = float(best_lap_df['session_time'].iloc[-1] - best_lap_df['session_time'].iloc[0])
            
            return {
                "total_laps": len(df['lap'].unique()),
                "best_lap_number": int(best_lap_df['lap'].iloc[0]),
                "best_lap_time": lap_time,
                "best_lap_data": {
                    "x": spatial_index.get_position(resampled['s'])[:, 0].tolist(),
                    "z": spatial_index.get_position(resampled['s'])[:, 1].tolist(),
                    "speed": (resampled['speed'] * 3.6).tolist(), 
                    "throttle": (resampled['throttle'] * 100).tolist(),
                    "brake": (resampled['brake'] * 100).tolist(),
                    "distance": resampled['s'].tolist(),
                    "lateral_offset": resampled['L'].tolist(),
                    # Novos canais Phase 1.3
                    "accel_lat_g": dynamics["accel_lat_g"].tolist(),
                    "accel_long_g": dynamics["accel_long_g"].tolist(),
                    "yaw_rate": dynamics["yaw_rate_degs"].tolist(),
                    "curvature": dynamics["curvature"].tolist()
                },
                "validation": {**validation_report, **phys_report},
                "corners": corners,
                "metrics": metrics,
                "driving_style": driving_style,
                "ml_ready": True # Indica que o dado está pronto para treinamento
            }
        
        except Exception as e:
            logger.error(f"Erro no pipeline de telemetria: {str(e)}", exc_info=True)
            raise
        
        except Exception as e:
            logger.error(f"Erro ao processar telemetria: {str(e)}")
            raise
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza nomes de colunas (case insensitive, aliases)"""
        # Normalizar primeiro
        df.columns = df.columns.str.strip().str.lower()

        # Mapeamento de aliases base (sem os aliases de eixo vertical)
        col_map = {
            'time': 'session_time',
            't': 'session_time',
            'x': 'pos_x',
            'z': 'pos_z',
        }

        # Só mapear y/pos_y → pos_z se pos_z ainda não existir no CSV.
        # CSVs com pos_x, pos_y, pos_z (3D) já têm pos_z real; renomear
        # pos_y também geraria coluna duplicada e quebraria _calculate_distance.
        if 'pos_z' not in df.columns and 'z' not in df.columns:
            if 'pos_y' in df.columns:
                col_map['pos_y'] = 'pos_z'
            elif 'y' in df.columns:
                col_map['y'] = 'pos_z'

        df = df.rename(columns=col_map)

        return df
    
    def _find_best_lap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identifica e retorna dados da melhor volta"""
        laps = {}
        
        try:
            unique_laps = df['lap'].unique()
            logger.info(f"Analisando {len(unique_laps)} voltas")
            
            for lap_num in unique_laps:
                lap_data = df[df['lap'] == lap_num].copy()
                
                # Calcular tempo da volta
                if len(lap_data) < 10:  # Volta muito curta, ignorar
                    logger.warning(f"Volta {lap_num} ignorada: apenas {len(lap_data)} pontos")
                    continue
                
                lap_time = lap_data['session_time'].max() - lap_data['session_time'].min()
                
                # Validar tempo razoável (entre 30s e 300s)
                if lap_time < 30 or lap_time > 300:
                    logger.warning(f"Volta {lap_num} ignorada: tempo inválido {lap_time:.1f}s")
                    continue
                
                laps[lap_num] = (lap_time, lap_data)
                logger.info(f"Volta {lap_num}: {lap_time:.3f}s com {len(lap_data)} pontos")
            
            if not laps:
                raise ValueError("Nenhuma volta válida encontrada. Verifique se o CSV tem dados completos de pelo menos uma volta.")
            
            # Melhor volta = menor tempo
            best_lap_num = min(laps.keys(), key=lambda k: laps[k][0])
            best_lap_time = laps[best_lap_num][0]
            best_lap_df = laps[best_lap_num][1].copy()
            
            logger.info(f"Melhor volta: {best_lap_num} com tempo {best_lap_time:.3f}s")
            
            # Normalizar tempo para começar em 0
            t0 = best_lap_df['session_time'].min()
            best_lap_df['session_time'] = best_lap_df['session_time'] - t0
            
            return best_lap_df.reset_index(drop=True)
            
        except Exception as e:
            logger.error(f"Erro ao encontrar melhor volta: {str(e)}")
            raise
    
    def _calculate_distance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula distância percorrida ao longo da volta"""
        dx = df['pos_x'].diff().fillna(0)
        dz = df['pos_z'].diff().fillna(0)
        delta_dist = np.sqrt(dx**2 + dz**2)
        df['distance'] = delta_dist.cumsum()
        return df
    
    def _check_track_limits_pro(self, df: pd.DataFrame, track_data: Dict) -> Dict:
        """
        Verifica se o jogador saiu dos limites da pista usando o Lateral Offset.
        L > width_left ou L < -width_right (considerando sinal do offset)
        """
        violations = {
            "total": 0,
            "positions": []
        }
        
        if 'lateral_offset' not in df.columns:
            return violations

        # Converter larguras para arrays interpolados na distância do player
        from scipy.interpolate import interp1d
        
        s_track = np.array(track_data["centerline"]["x"]) # placeholder for track s
        # Wait, track_data should have s_centerline if generated by spatial engine
        spatial_index = track_data.get("_spatial_index")
        if not spatial_index:
            return violations
            
        s_centerline = spatial_index.s_centerline
        w_left = np.array(track_data["width_left"])
        w_right = np.array(track_data["width_right"])
        
        f_left = interp1d(s_centerline, w_left, bounds_error=False, fill_value="extrapolate")
        f_right = interp1d(s_centerline, w_right, bounds_error=False, fill_value="extrapolate")
        
        player_s = df['distance'].values
        player_L = df['lateral_offset'].values
        
        limit_left = f_left(player_s)
        limit_right = -f_right(player_s) # Offset right is negative in our spatial engine
        
        # Violação: player_L > limit_left ou player_L < limit_right
        # Adicionamos uma pequena margem de tolerância (0.2m)
        is_violation = (player_L > (limit_left + 0.2)) | (player_L < (limit_right - 0.2))
        
        violation_idxs = np.where(is_violation)[0]
        violations["total"] = len(violation_idxs)
        
        for idx in violation_idxs:
            violations["positions"].append({
                "distance": float(df['distance'].iloc[idx]),
                "time": float(df['session_time'].iloc[idx]),
                "offset": float(player_L[idx])
            })
            
        return violations
    
    def _calculate_metrics(self, df: pd.DataFrame) -> Dict:
        """Calcula métricas de performance"""
        return {
            "avg_speed": float(df['speed'].mean()),
            "max_speed": float(df['speed'].max()),
            "min_speed": float(df['speed'].min()),
            "avg_throttle": float(df['throttle'].mean() * 100),
            "avg_brake": float(df['brake'].mean() * 100),
            "brake_points": int((df['brake'] > 0.1).sum()),
            "full_throttle_pct": float((df['throttle'] > 0.95).sum() / len(df) * 100),
            "coasting_pct": float(((df['throttle'] < 0.1) & (df['brake'] < 0.1)).sum() / len(df) * 100)
        }
    
    def _analyze_driving_style(self, df: pd.DataFrame) -> Dict:
        """
        Analisa estilo de pilotagem
        - Agressivo: muito freio, throttle on/off
        - Suave: transições graduais
        - Conservador: velocidade média baixa
        """
        # Variação de throttle (transições bruscas vs suaves)
        throttle_changes = df['throttle'].diff().abs().mean()
        brake_changes = df['brake'].diff().abs().mean()
        
        # Classificação
        if throttle_changes > 0.15 or brake_changes > 0.15:
            style = "agressivo"
            desc = "Muitas transições bruscas de throttle/brake"
        elif df['speed'].mean() < df['speed'].max() * 0.65:
            style = "conservador"
            desc = "Velocidade média baixa, pode atacar mais"
        else:
            style = "suave"
            desc = "Transições graduais, bom controle"
        
        return {
            "classification": style,
            "description": desc,
            "throttle_smoothness": float(1 - throttle_changes),
            "brake_smoothness": float(1 - brake_changes)
        }
