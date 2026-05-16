"""
Driver Embedding System
Converts telemetry behavior into compact feature vectors for style analysis.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List

class DriverEmbedding:
    """
    Generates deterministic behavioral embeddings from lap telemetry.
    """
    def __init__(self):
        # Feature indices
        self.feature_names = [
            "braking_aggressiveness",
            "throttle_smoothness",
            "trail_braking_score",
            "traction_efficiency",
            "steering_stability",
            "consistency_s",
            "racing_line_offset_avg",
            "exit_speed_score"
        ]

    def generate_lap_embedding(self, lap_df: pd.DataFrame) -> Dict[str, float]:
        """
        Extracts style features from a full lap of telemetry.
        """
        # Ensure numeric types
        for col in ["speed", "throttle", "brake", "L", "s"]:
            if col in lap_df.columns:
                lap_df[col] = pd.to_numeric(lap_df[col], errors='coerce')
        
        lap_df = lap_df.dropna(subset=["speed", "throttle", "brake", "s"])
        
        # 1. Braking Aggressiveness (mean brake gradient when brake > 0.1)
        brake_diff = lap_df["brake"].diff().fillna(0)
        aggressiveness = brake_diff[lap_df["brake"] > 0.1].abs().mean()
        
        # 2. Throttle Smoothness (inverse of throttle variance during application)
        throttle_var = lap_df[lap_df["throttle"] > 0.1]["throttle"].var()
        smoothness = 1.0 / (throttle_var + 0.1)
        
        # 3. Trail Braking Score (correlation between brake and curvature during entry)
        # Simplified: brake pressure during high L change
        trail_score = (lap_df["brake"] * lap_df["L"].abs().diff().fillna(0).abs()).mean()
        
        # 4. Traction Efficiency (longitudinal accel vs speed)
        # accel = dv/dt
        accel = lap_df["speed"].diff().fillna(0)
        traction = (accel[lap_df["throttle"] > 0.8] / (lap_df["speed"] + 1)).mean()
        
        # 5. Steering Stability (inverse of L oscillation)
        steering_jitter = lap_df["L"].diff().diff().fillna(0).abs().mean()
        stability = 1.0 / (steering_jitter + 0.01)
        
        embedding = {
            "braking_aggressiveness": float(np.nan_to_num(aggressiveness)),
            "throttle_smoothness": float(np.nan_to_num(smoothness)),
            "trail_braking_score": float(np.nan_to_num(trail_score)),
            "traction_efficiency": float(np.nan_to_num(traction)),
            "steering_stability": float(np.nan_to_num(stability)),
            "racing_line_offset_avg": float(lap_df["L"].abs().mean())
        }
        
        return embedding

    def get_style_labels(self, embedding: Dict[str, float]) -> List[str]:
        """Converts numerical embedding into human-readable style labels."""
        labels = []
        if embedding["braking_aggressiveness"] > 0.05: labels.append("Aggressive Braker")
        if embedding["throttle_smoothness"] > 5.0: labels.append("Smooth Throttle")
        if embedding["trail_braking_score"] > 0.02: labels.append("Trail Braking Expert")
        if embedding["steering_stability"] > 50.0: labels.append("Laser Precision")
        return labels
