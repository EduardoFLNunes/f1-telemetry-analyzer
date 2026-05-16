"""
Driver State Estimator
Infers high-level driver states like overdriving, hesitation, or confident push.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class DriverStateEstimator:
    """
    Classifies the driver's current state based on cognitive metrics and physics metadata.
    """
    def __init__(self):
        self.current_state = "observing"
        self.state_history: List[str] = []

    def estimate_state(self, cog_metrics: Dict[str, float], physics_anomalies: int) -> str:
        """
        Determines the driver's state using cognitive indices.
        """
        confidence = cog_metrics["confidence"]
        aggression = cog_metrics["aggression"]
        smoothness = cog_metrics["smoothness"]
        
        new_state = "steady"
        
        if aggression > 0.8 and smoothness < 0.4:
            new_state = "overdriving"
        elif confidence < 0.4 and aggression < 0.4:
            new_state = "hesitating"
        elif confidence > 0.8 and aggression > 0.6 and smoothness > 0.6:
            new_state = "confident_push"
        elif physics_anomalies > 5:
            new_state = "unstable"
            
        if new_state != self.current_state:
            logger.info(f"Driver state transition: {self.current_state} -> {new_state}")
            self.current_state = new_state
            self.state_history.append(new_state)
            
        return self.current_state

    def get_state_report(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state,
            "recent_transitions": self.state_history[-5:]
        }
