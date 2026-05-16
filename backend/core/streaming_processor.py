"""
Real-Time Telemetry Processor
Orchestrates the streaming pipeline: Normalization -> Projection -> Physics -> Delta -> Broadcast.
"""
import asyncio
import time
import logging
import numpy as np
from typing import Dict, Any, Optional, List

from core.telemetry_events import event_bus
from core.normalization import SimAdapter
from core.spatial import TrackSpline, CalibrationEngine
from core.dynamics import TelemetryDynamics
from core.realtime_delta import RealTimeDelta
from core.vehicle_physics import VehiclePhysicsAdapter

# Phase 3 Imports
from core.coaching_engine import CoachingEngine
from core.corner_classifier import CornerClassifier
from core.delta_intelligence import DeltaIntelligence

# Phase 4 Imports
from core.racing_line_model import RacingLinePredictor
from core.corner_ai import CornerAI
from core.delta_predictor import DeltaPredictor

# Phase 8: Professional Spatial Engine
from core.spatial_engine import (
    CanonicalTrackSpace, 
    MapMatchingEngine, 
    SpatialStateEstimator, 
    TrajectoryReconstructionEngine,
    RenderSpaceAdapter
)

logger = logging.getLogger(__name__)

class RealTimeProcessor:
    """
    Main orchestrator for real-time telemetry processing.
    Now enriched with Phase 4 AI Predictive Intelligence and 
    professional-grade Spatial Engine.
    """
    def __init__(self, track_spline: TrackSpline, reference_lap: Optional[Dict] = None, sim_type: str = "F1-25"):
        # Canonical Track Space Engine
        self.track = CanonicalTrackSpace(track_spline.x, track_spline.z)
        self.map_matching = MapMatchingEngine(self.track)
        self.estimator = SpatialStateEstimator(self.track.total_length)
        self.reconstructor = TrajectoryReconstructionEngine(self.track)
        
        self.adapter = SimAdapter(sim_type=sim_type)
        self.dynamics = TelemetryDynamics(sample_rate=60.0)
        self.delta_engine = RealTimeDelta(reference_lap)
        self.physics = VehiclePhysicsAdapter()

        # Spatial Calibration System
        self.calibration = CalibrationEngine()
        self.calibration_points = []
        self.is_calibrated = False

        # Intelligence Layers
        self.classifier = CornerClassifier(track_spline)
        self.classifier.classify_track()
        
        self.coaching = CoachingEngine(reference_lap)
        self.delta_intel = DeltaIntelligence(track_length=self.track.total_length)
        
        # Phase 4: AI Predictors
        self.racing_line_ai = RacingLinePredictor()
        self.corner_ai = CornerAI()
        self.delta_predictor = DeltaPredictor(reference_time=reference_lap.get("lap_time", 90.0) if reference_lap else 90.0)
        
        # Rolling window for sequence-based AI (last 60 frames)
        self.sequence_window: List[Dict[str, Any]] = []
        
        # Current state buffer
        self.current_state = {
            "x": 0.0, "y": 0.0, "z": 0.0,
            "speed": 0.0, "throttle": 0.0, "brake": 0.0,
            "lap_number": 0, "lap_time": 0.0,
            "prev_speed": 0.0, "prev_t": time.perf_counter(),
            "initialized": False
        }
        
        event_bus.subscribe("raw_packet", self.on_raw_packet)

    def stop(self):
        """Cleanup and unsubscribe from event bus."""
        event_bus.unsubscribe("raw_packet", self.on_raw_packet)
        logger.info("RealTimeProcessor stopped and unsubscribed")

    async def update_reference(self, reference_lap: Dict[str, Any]):
        """Updates the reference lap for all deterministic and AI layers."""
        self.delta_engine.update_reference(reference_lap)
        self.coaching.update_reference(reference_lap)
        if "lap_time" in reference_lap:
            self.delta_predictor.reference_time = reference_lap["lap_time"]

    async def on_raw_packet(self, packet: Dict[str, Any]):
        if packet.get("is_pre_parsed"):
            new_x, new_z = packet["x"], packet["z"]
            
            # IMPROVED: Ignore (0,0) during initialization as sims often send it initially
            if not self.current_state["initialized"]:
                if abs(new_x) < 0.001 and abs(new_z) < 0.001:
                    return # Still waiting for valid position
                    
                logger.info(f"Spatial origin initialized: {new_x},{new_z}")
                self.current_state["x"] = new_x
                self.current_state["z"] = new_z
                self.current_state["initialized"] = True
            else:
                # Continuity validation
                dist_sq = (new_x - self.current_state["x"])**2 + (new_z - self.current_state["z"])**2
                if dist_sq > 2500.0:
                    # RECOVERY: If we just initialized at 0,0 or similar, and this is a huge jump,
                    # re-initialize once. This handles "bad origin" cases.
                    if abs(self.current_state["x"]) < 1.0 and abs(self.current_state["z"]) < 1.0:
                         logger.info(f"Spatial origin reset to: {new_x},{new_z}")
                         self.current_state["x"] = new_x
                         self.current_state["z"] = new_z
                         return
                         
                    logger.warning(f"Rejected impossible spatial jump: {new_x},{new_z} (Dist: {dist_sq**0.5:.1f}m)")
                    return
                self.current_state["x"] = new_x
                self.current_state["z"] = new_z
            
            self.current_state["y"] = packet.get("y", 0.0)
            self.current_state["speed"] = packet["speed"]
            self.current_state["throttle"] = packet["throttle"]
            self.current_state["brake"] = packet["brake"]
            self.current_state["steering"] = packet.get("steer", 0.0)
            self.current_state["heading"] = packet.get("heading", 0.0)
            self.current_state["lap_number"] = packet["lap_number"]
            self.current_state["lap_time"] = packet["lap_time"]
            self.current_state["lap_dist_pct"] = packet.get("lap_dist_pct", 0.0)
            await self.process_frame()
            return

        p_type = packet.get("type")
        if p_type == "motion":
            self.current_state["x"] = packet["x"]
            self.current_state["y"] = packet["y"]
            self.current_state["z"] = packet["z"]
            await self.process_frame()
        elif p_type == "telemetry":
            self.current_state["speed"] = packet["speed"]
            self.current_state["throttle"] = packet["throttle"]
            self.current_state["brake"] = packet["brake"]
        elif p_type == "lap":
            self.current_state["lap_number"] = packet["lap_number"]
            self.current_state["lap_time"] = packet["lap_time"]

    async def process_frame(self):
        """Hot-path processing with deterministic analysis and AI forecasting."""
        start_t = time.perf_counter()
        now = time.time()
        
        # 1. Normalization
        raw_x, raw_z = self.adapter.normalize_pos(self.current_state["x"], 0, self.current_state["z"])
        speed_ms = self.adapter.normalize_speed(self.current_state["speed"])
        throttle, brake = self.adapter.normalize_inputs(self.current_state["throttle"], self.current_state["brake"])
        
        # 2. Spatial Calibration
        if not self.is_calibrated:
            self.calibration_points.append([raw_x, raw_z])
            if len(self.calibration_points) == 100:
                self.calibration.calibrate(self.track.points, np.array(self.calibration_points))
                self.is_calibrated = self.calibration.transform["is_calibrated"]
        
        cal_x, cal_z = self.calibration.apply(raw_x, raw_z)
        
        # 3. SPATIAL PIPELINE (Phase 8: PROFESSIONAL MOTORSPORT GRADE)
        
        # A. Heading Validation
        heading_rad = self.current_state.get("heading", 0.0)
        raw_h_vec = self.adapter.get_heading_vector(heading_rad)
        cal_h_vec = self.calibration.apply_vector(raw_h_vec[0], raw_h_vec[1])
        
        # B. Map Matching (Deterministic Projection)
        hint_s = self.current_state["lap_dist_pct"] * self.track.total_length if self.current_state.get("lap_dist_pct", 0) > 0 else None
        projection = self.map_matching.project(cal_x, cal_z, heading_vec=cal_h_vec, velocity=speed_ms, hint_s=hint_s)
        raw_s, raw_L = projection["s"], projection["L"]

        # C. Spatial State Estimation (Kalman Filter)
        dt = max(start_t - self.current_state["prev_t"], 0.001)
        est_s, s_dot, est_L, L_dot = self.estimator.update(raw_s, raw_L, dt)
        
        # D. Trajectory Reconstruction (Motion Continuity)
        self.reconstructor.add_point(est_s, est_L, now, speed_ms)
        
        # E. Final Spatial Reconstruction (Authoritative)
        final_x, final_z = self.track.evaluate(est_s, est_L)
        
        # Corrected Heading Angle (for frontend rotation)
        corrected_heading = np.arctan2(cal_h_vec[0], -cal_h_vec[1])

        # 4. Geometry Intelligence
        corner = self.classifier.get_corner_at(est_s)
        
        # 5. Incremental Delta & Physics
        delta = self.delta_engine.calculate_delta(est_s, speed_ms, self.current_state["lap_time"])
        dv = speed_ms - self.current_state["prev_speed"]
        accel_g = (dv / dt) / 9.81
        
        physics_metrics = self.physics.calculate_metrics({
            "x": final_x, "z": final_z, "speed": speed_ms,
            "heading": corrected_heading,
            "steering_angle": self.current_state.get("steering", 0.0)
        }, now)

        # 6. Build Processed Frame
        processed_frame = {
            "driver_id": "player_1",
            "lap_number": self.current_state["lap_number"],
            "lap_time": self.current_state["lap_time"],
            "s": est_s, "L": est_L, "speed": speed_ms,
            "throttle": throttle, "brake": brake, "accel_g": accel_g,
            "delta": delta, 
            "x": final_x, "z": final_z, 
            "raw_x": raw_x, "raw_z": raw_z,
            "timestamp": now,
            "corner_id": corner.corner_id if corner else None,
            "corner_type": corner.archetype if corner else "straight",
            "slip_angle": physics_metrics["slip_angle"],
            "heading": float(corrected_heading),
            # Debug Instrumentation
            "reconstruction_confidence": float(1.0 - (projection["score"] / 50.0)),
            "s_dot": float(s_dot),
            "L_dot": float(L_dot)
        }
        
        # Update sequence window for AI
        self.sequence_window.append(processed_frame)
        if len(self.sequence_window) > 60: self.sequence_window.pop(0)
        
        # 5. AI PREDICTIVE INTELLIGENCE
        # A. Racing Line AI
        if len(self.sequence_window) >= 10:
            input_tensor = self.racing_line_ai.prepare_input_tensor(self.sequence_window)
            ai_path = self.racing_line_ai.predict_optimal_path(input_tensor)
            processed_frame["predicted_optimal_L"] = float(ai_path["predicted_L"][0, -1])
            processed_frame["ai_confidence"] = float(ai_path["confidence"][0, 0])
            
        # B. Corner Execution AI
        corner_eval = self.corner_ai.analyze_execution(processed_frame, processed_frame["corner_type"])
        processed_frame["execution_score"] = corner_eval["execution_score"]
        
        # C. Predictive Delta
        forecast = self.delta_predictor.forecast_lap_time(processed_frame)
        processed_frame["predicted_lap_time"] = forecast["projected_time"]
        
        # 6. Deterministic Coaching
        coaching_events = self.coaching.process_frame(processed_frame, corner)
        
        # 7. Broadcast Events
        await event_bus.emit("processed_frame", processed_frame)
        await event_bus.emit("normalized_frame", processed_frame)
        
        for event in coaching_events:
            event.update({"driver_id": "player_1", "lap_number": self.current_state["lap_number"], "s": est_s})
            if corner and "evidence" in event:
                event["evidence"]["corner_id"] = corner.corner_id
            await event_bus.emit("coaching_event", event)
            
        # 8. AI-Specific Alerting
        if corner_eval["is_unstable"]:
            await event_bus.emit("coaching_event", {
                "type": "coaching_event", "event": "ai_instability_alert",
                "severity": 0.8, "evidence": {"patterns": corner_eval["detected_patterns"]},
                "s": est_s, "driver_id": "player_1", "lap_number": self.current_state["lap_number"]
            })
            
        # Update prev state
        self.current_state["prev_speed"] = speed_ms
        self.current_state["prev_t"] = start_t
        processed_frame["processing_time_ms"] = (time.perf_counter() - start_t) * 1000
