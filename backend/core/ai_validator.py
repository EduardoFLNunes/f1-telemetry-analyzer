"""
AI Validation & Benchmarking Framework
Monitors inference accuracy, physical plausibility, and latency.
"""
import numpy as np
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AIValidator:
    """
    Benchmarks AI predictions against deterministic ground truth.
    Tracks prediction drift and latency metrics.
    """
    def __init__(self):
        self.latency_history: List[float] = []
        self.error_history: Dict[str, List[float]] = {
            "trajectory_mse": [],
            "delta_mae": []
        }

    def log_inference(self, latency_ms: float):
        self.latency_history.append(latency_ms)
        if len(self.latency_history) > 100:
            self.latency_history.pop(0)

    def validate_plausibility(self, prediction: Dict[str, Any]) -> bool:
        """Checks if AI predictions stay within physical bounds."""
        # Example: Predicted L-offset shouldn't exceed track width (approx 15m)
        if abs(prediction.get("predicted_L", 0)) > 20.0:
            logger.warning("AI Prediction Violation: Extreme lateral offset")
            return False
            
        # Example: Predicted speed shouldn't exceed 400 km/h
        if prediction.get("predicted_speed", 0) > 111.1: # 400 / 3.6
            logger.warning("AI Prediction Violation: Impossible speed")
            return False
            
        return True

    def get_benchmarks(self) -> Dict[str, Any]:
        """Returns aggregated performance metrics."""
        return {
            "avg_latency_ms": float(np.mean(self.latency_history)) if self.latency_history else 0.0,
            "max_latency_ms": float(np.max(self.latency_history)) if self.latency_history else 0.0,
            "p99_latency_ms": float(np.percentile(self.latency_history, 99)) if self.latency_history else 0.0
        }
