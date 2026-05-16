"""
Replay-Based AI Training Environment
Generates high-volume training batches from historical Parquet telemetry data.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from core.telemetry_store import TelemetryStore
from core.feature_store import FeatureStore
import logging

logger = logging.getLogger(__name__)

class TrainingEnvironment:
    """
    Automates the extraction and augmentation of telemetry for ML training.
    Uses the TelemetryStore to pull full laps and the FeatureStore to persist tensors.
    """
    def __init__(self):
        self.tel_store = TelemetryStore()
        self.feat_store = FeatureStore()

    def generate_training_data(self, driver_id: str, lap_numbers: List[int]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extracts features (X) and targets (y) for sequence learning.
        Target: predict L-offset for the next 10 frames.
        """
        X_batches = []
        y_batches = []
        
        for lap_num in lap_numbers:
            try:
                df = self.tel_store.load_lap_telemetry(driver_id, lap_num)
                # Normalize and build sequences
                # seq_len = 60 (1 second at 60Hz)
                X, y = self._prepare_sequences(df, seq_len=60, pred_len=10)
                X_batches.append(X)
                y_batches.append(y)
            except Exception as e:
                logger.error(f"Error loading lap {lap_num}: {e}")
                
        return np.concatenate(X_batches), np.concatenate(y_batches)

    def _prepare_sequences(self, df: pd.DataFrame, seq_len: int, pred_len: int):
        """Builds windowed sequences from dataframe."""
        # Features: [s, L, speed, throttle, brake, accel_g]
        cols = ["s", "L", "speed", "throttle", "brake", "accel_g"]
        data = df[cols].values
        
        X, y = [], []
        for i in range(len(data) - seq_len - pred_len):
            X.append(data[i:i+seq_len])
            y.append(data[i+seq_len:i+seq_len+pred_len, 1]) # predict L
            
        return np.array(X), np.array(y)

    def add_augmentation(self, X: np.ndarray):
        """Adds synthetic noise to input features to improve model robustness."""
        noise = np.random.normal(0, 0.01, X.shape)
        return X + noise
