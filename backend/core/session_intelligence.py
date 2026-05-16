"""
Session Intelligence Layer
Aggregates telemetry insights over multiple laps and sessions.
"""
from typing import Dict, List, Any, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SessionIntelligence:
    """
    Tracks driver consistency, fatigue, and adaptation over time.
    """
    def __init__(self):
        self.lap_times: List[float] = []
        self.consistency_history: List[float] = []
        self.style_drift: List[float] = []
        
    def add_lap_summary(self, summary: Dict[str, Any]):
        """
        Incorporates a completed lap into the session-wide intelligence.
        """
        self.lap_times.append(summary["lap_time"])
        
        # Calculate consistency (Standard deviation of last 5 laps)
        if len(self.lap_times) >= 2:
            consistency = np.std(self.lap_times[-5:])
            self.consistency_history.append(float(consistency))
            
        # TODO: Detect fatigue by looking for drift in brake points or steering jitter
        
    def get_session_insights(self) -> Dict[str, Any]:
        """Returns aggregated insights for the current session."""
        if not self.lap_times:
            return {}
            
        return {
            "avg_lap_time": float(np.mean(self.lap_times)),
            "best_lap_time": float(np.min(self.lap_times)),
            "consistency_score": float(self.consistency_history[-1]) if self.consistency_history else 0.0,
            "improvement_rate": float(self.lap_times[0] - self.lap_times[-1]) if len(self.lap_times) > 1 else 0.0,
            "lap_count": len(self.lap_times)
        }
