"""
AI Race Engineer Agent
Central reasoning agent for real-time driver coaching and session analysis.
"""
import logging
from typing import Dict, Any, List, Optional
import time
import numpy as np
from core.telemetry_events import event_bus, COACHING_EVENT, PROCESSED_FRAME
from core.session_memory import SessionMemory
from core.driver_cognitive_model import DriverCognitiveModel
from core.driver_state_estimator import DriverStateEstimator
from core.predictive_mistake_engine import PredictiveMistakeEngine
from core.adaptive_coaching import AdaptiveCoachingEngine

# Phase 8 Imports
from core.foundation_model import MotorsportFoundationModel
from core.line_prediction_model import LinePredictionModel
from core.knowledge_graph import MotorsportKnowledgeGraph

logger = logging.getLogger(__name__)

class RaceEngineerAgent:
    """
    Cognitive AI Race Engineer with Phase 8 Foundation Model capabilities.
    Uses learned racing representations and trajectory forecasting.
    """
    def __init__(self):
        self.memory = SessionMemory()
        self.cognitive_model = DriverCognitiveModel()
        self.state_estimator = DriverStateEstimator()
        self.predictive_engine = PredictiveMistakeEngine()
        self.coach = AdaptiveCoachingEngine()
        
        # Phase 8 Intelligence
        self.foundation_model = MotorsportFoundationModel()
        self.line_ai = LinePredictionModel()
        self.knowledge_graph = MotorsportKnowledgeGraph()
        
        self.current_lap_errors: List[Dict[str, Any]] = []
        self.sequence_window: List[np.ndarray] = [] # Rolling window of frames
        
        # Subscribe to telemetry for real-time cognitive modeling
        event_bus.subscribe(PROCESSED_FRAME, self.on_frame)
        event_bus.subscribe(COACHING_EVENT, self.on_coaching_event)

    async def on_frame(self, frame: Dict[str, Any]):
        """
        Hot-path for learned representation and trajectory prediction.
        """
        # 1. Base Cognitive Modeling
        cog_metrics = self.cognitive_model.update(frame)
        driver_state = self.state_estimator.estimate_state(cog_metrics, 0)
        
        # 2. Phase 8: Learned Trajectory Prediction
        # Convert frame to standard feature vector
        features = np.array([
            frame["s"], frame["L"], frame["speed"], 
            frame["throttle"], frame["brake"], frame.get("accel_g", 0),
            frame.get("steer", 0), frame.get("rpm", 0), 
            frame.get("gear", 0), frame.get("kappa", 0)
        ])
        self.sequence_window.append(features)
        if len(self.sequence_window) > 60: self.sequence_window.pop(0)
        
        if len(self.sequence_window) >= 30:
            seq = np.array(self.sequence_window).reshape(1, len(self.sequence_window), -1)
            # A. Latent Style Encoding
            style_vec = self.foundation_model.encode_driver_style(seq)
            # B. Future Trajectory Forecasting
            future_L = self.line_ai.predict_future_trajectory(seq)
            
            # Inject into frame for UI
            frame["style_latent"] = style_vec.flatten().tolist()
            frame["predicted_future_L"] = future_L.flatten().tolist()
        
        # 3. Emit Intelligence State
        await event_bus.emit("driver_cognitive_state", {
            "metrics": cog_metrics,
            "state": driver_state,
            "timestamp": frame["timestamp"]
        })

    async def on_coaching_event(self, event: Dict[str, Any]):
        """
        Evaluates coaching events and updates the knowledge graph.
        """
        event_type = event.get("event")
        severity = event.get("severity", 0.0)
        evidence = event.get("evidence", {})
        corner_id = evidence.get("corner_id")
        
        # 1. Update Persistent Knowledge Graph
        if corner_id:
            self.knowledge_graph.link_mistake_to_corner(
                "player_1", f"track_T{corner_id}", event_type
            )
        
        # 2. Adaptive Reasoning
        driver_state = self.state_estimator.current_state
        if self.coach.should_emit(event, driver_state):
            await self.generate_feedback(event)
            self.coach.log_emission(event)

    async def generate_feedback(self, event: Dict[str, Any]):
        """Converts a telemetry event into natural language coaching."""
        personality = self.coach.personality
        event_type = event.get("event")
        evidence = event.get("evidence", {})
        
        # In Phase 8, we can query the Knowledge Graph for context
        weaknesses = self.knowledge_graph.query_driver_weaknesses("player_1")
        is_chronic = any(w["mistake"] == event_type for w in weaknesses)
        
        prefix = "Chronic issue detected: " if is_chronic else ""
        message = ""
        
        if event_type == "late_brake":
            message = f"{prefix}Braking too deep. The model suggests {evidence.get('delta_m', 0):.1f}m earlier."
        elif event_type == "early_brake":
            message = f"{prefix}Good entry speed, but you can push the braking point further."
        elif event_type == "poor_apex":
            message = f"{prefix}Missing the apex target. Look for the predicted line."

        if message:
            await event_bus.emit("engineer_speech", {
                "message": message,
                "priority": "high" if is_chronic else "normal",
                "personality": personality,
                "timestamp": time.time()
            })
            logger.info(f"AI Engineer ({personality}): {message}")
