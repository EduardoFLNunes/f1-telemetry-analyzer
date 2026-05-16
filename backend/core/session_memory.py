"""
Persistent Session Memory
Tracks driver performance patterns and recurring errors across laps.
"""
from typing import Dict, List, Any, Optional
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

class SessionMemory:
    """
    Maintains a rolling memory of driver behavior to enable 
    context-aware coaching and pattern detection.
    """
    def __init__(self, history_len: int = 5):
        self.history_len = history_len
        # Keyed by corner_id: list of error types
        self.corner_errors = defaultdict(list)
        # Lap times history
        self.lap_history: List[float] = []
        # General style trends
        self.style_trends = defaultdict(list)

    def add_lap_error(self, corner_id: int, error_type: str):
        """Records an error at a specific corner."""
        self.corner_errors[corner_id].append(error_type)
        if len(self.corner_errors[corner_id]) > self.history_len * 2:
            self.corner_errors[corner_id].pop(0)

    def is_recurring_error(self, corner_id: int, error_type: str, threshold: int = 2) -> bool:
        """Checks if a specific error has occurred multiple times at a corner recently."""
        recent = self.corner_errors[corner_id][-self.history_len:]
        return recent.count(error_type) >= threshold

    def get_pattern_intensity(self, corner_id: int, error_type: str) -> float:
        """Returns 0-1 score representing how ingrained an error is."""
        recent = self.corner_errors[corner_id][-self.history_len:]
        if not recent: return 0.0
        return recent.count(error_type) / len(recent)

    def add_lap_time(self, time: float):
        self.lap_history.append(time)
        if len(self.lap_history) > 50:
            self.lap_history.pop(0)

    def clear(self):
        self.corner_errors.clear()
        self.lap_history.clear()
        self.style_trends.clear()
