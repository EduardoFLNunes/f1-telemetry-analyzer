"""
Racing Line Prediction Model
Implements trajectory forecasting using sequence learning.
"""
import numpy as np
from typing import Dict, Any, Optional, List
from core.ai_runtime import ai_runtime
import logging

logger = logging.getLogger(__name__)

class RacingLinePredictor:
    """
    Predicts the optimal racing line (L-offset) and target speed.
    Consumes temporal telemetry sequences.
    """
    def __init__(self, model_id: str = "racing_line_v1"):
        self.model_id = model_id
        self.is_loaded = False
        
        # Canonical Feature Mapping
        self.feature_cols = ["s", "L", "speed", "throttle", "brake", "accel_g", "kappa"]
        
    def load(self, filename: str = "racing_line.onnx"):
        self.is_loaded = ai_runtime.load_model(self.model_id, filename)
        return self.is_loaded

    def predict_optimal_path(self, sequence: np.ndarray) -> Optional[Dict[str, np.ndarray]]:
        """
        Inputs: sequence of shape (batch, seq_len, num_features)
        Outputs: predicted L-offset and speed for future points.
        """
        if not self.is_loaded:
            # Fallback to deterministic heuristic if model not available
            return self._heuristic_fallback(sequence)
            
        inputs = {"telemetry_seq": sequence.astype(np.float32)}
        prediction = ai_runtime.predict(self.model_id, inputs)
        
        return prediction

    def _heuristic_fallback(self, sequence: np.ndarray) -> Dict[str, np.ndarray]:
        """Simple geometric fallback when AI model is offline."""
        # For a sequence, just return a slightly smoothed version or centerline
        # This prevents the UI from breaking
        batch_size = sequence.shape[0]
        seq_len = sequence.shape[1]
        
        return {
            "predicted_L": np.zeros((batch_size, seq_len)),
            "predicted_speed": sequence[:, :, 2], # return current speed as target
            "confidence": np.full((batch_size, 1), 0.5)
        }

    def prepare_input_tensor(self, frames: List[Dict[str, Any]]) -> np.ndarray:
        """Converts raw frame list into standardized (1, N, C) tensor."""
        data = []
        for f in frames:
            row = [
                f.get("s", 0.0),
                f.get("L", 0.0),
                f.get("speed", 0.0),
                f.get("throttle", 0.0),
                f.get("brake", 0.0),
                f.get("accel_g", 0.0),
                f.get("kappa", 0.0) # Curvature from classifier/spline
            ]
            data.append(row)
        
        tensor = np.array(data).reshape(1, len(data), -1)
        return tensor
