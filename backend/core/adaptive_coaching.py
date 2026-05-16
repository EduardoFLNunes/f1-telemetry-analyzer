"""
Adaptive Coaching Engine
Personalizes coaching based on driver state, session phase, and engineer personality.
"""
from typing import Dict, Any, List, Optional
import time
import logging

logger = logging.getLogger(__name__)

class AdaptiveCoachingEngine:
    """
    Orchestrates the delivery of coaching events.
    Handles anti-spam, prioritization, and personality-based filtering.
    """
    def __init__(self):
        self.personality = "analyst" # analyst, calm, aggressive, minimal
        self.feedback_history: List[Dict[str, Any]] = []
        self.cooldowns: Dict[str, float] = {}
        
        self.personality_profiles = {
            "calm": {"verbosity": 0.3, "severity_threshold": 0.7, "cooldown": 10.0},
            "analyst": {"verbosity": 0.8, "severity_threshold": 0.5, "cooldown": 5.0},
            "aggressive": {"verbosity": 1.0, "severity_threshold": 0.4, "cooldown": 3.0},
            "minimal": {"verbosity": 0.1, "severity_threshold": 0.9, "cooldown": 30.0}
        }

    def set_personality(self, personality: str):
        if personality in self.personality_profiles:
            self.personality = personality
            logger.info(f"AI Engineer personality set to: {personality}")

    def should_emit(self, event: Dict[str, Any], driver_state: str) -> bool:
        """
        Determines if a coaching event should be escalated to the driver.
        """
        profile = self.personality_profiles[self.personality]
        event_type = event.get("event")
        severity = event.get("severity", 0.0)
        now = time.time()
        
        # 1. Personality Threshold
        if severity < profile["severity_threshold"]:
            return False
            
        # 2. Global Cooldown
        last_time = self.cooldowns.get("global", 0)
        if now - last_time < profile["cooldown"]:
            return False
            
        # 3. Driver State Filtering
        # If overdriving, be more aggressive/urgent
        if driver_state == "overdriving" and self.personality != "aggressive":
             # Temporarily boost severity of safety events
             if "unstable" in event_type or "too_fast" in event_type:
                 pass # Allow through
             else:
                 return False # Don't overwhelm an already stressed driver
                 
        # 4. Anti-Spam (Don't repeat the same type too often)
        last_type_time = self.cooldowns.get(event_type, 0)
        if now - last_type_time < 30.0: # 30s per type
            return False
            
        return True

    def log_emission(self, event: Dict[str, Any]):
        self.cooldowns["global"] = time.time()
        self.cooldowns[event.get("event")] = time.time()
        self.feedback_history.append(event)
