"""
Racing Intelligence Memory Graph
Structured memory system for long-term driver behavioral tracking.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class MemoryGraph:
    """
    Persists driver performance history, adaptation trends, and problematic corners.
    Enables the AI engineer to reference data from previous sessions.
    """
    def __init__(self, storage_dir: str = "data/memory"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.memory_file = self.storage_dir / "driver_memory.json"
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memory graph: {e}")
        return {
            "corners": {}, # corner_id -> {errors: [], avg_time_loss: 0}
            "style_history": [], # List of cognitive snapshots
            "sessions": [] # List of session summaries
        }

    def save(self):
        try:
            with open(self.memory_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory graph: {e}")

    def update_corner_knowledge(self, corner_id: int, error_type: str, time_loss: float):
        corner_id_str = str(corner_id)
        if corner_id_str not in self.data["corners"]:
            self.data["corners"][corner_id_str] = {"errors": {}, "total_loss": 0.0, "count": 0}
            
        c_data = self.data["corners"][corner_id_str]
        c_data["errors"][error_type] = c_data["errors"].get(error_type, 0) + 1
        c_data["total_loss"] += time_loss
        c_data["count"] += 1
        
        self.save()

    def add_session_summary(self, summary: Dict[str, Any]):
        self.data["sessions"].append(summary)
        # Keep only last 20 sessions for compactness
        if len(self.data["sessions"]) > 20:
            self.data["sessions"].pop(0)
        self.save()

    def get_driver_profile(self) -> Dict[str, Any]:
        """Returns high-level traits based on memory."""
        # Simple heuristic: find top 3 problematic corners
        sorted_corners = sorted(
            self.data["corners"].items(), 
            key=lambda x: x[1]["total_loss"], 
            reverse=True
        )
        
        return {
            "problem_corners": [int(cid) for cid, _ in sorted_corners[:3]],
            "session_count": len(self.data["sessions"])
        }
