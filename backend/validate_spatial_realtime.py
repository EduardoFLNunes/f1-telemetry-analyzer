"""
Automated Spatial Validation Script
Simulates 60 seconds of telemetry and validates the Canonical Track-Space Engine.
"""
import pandas as pd
import numpy as np
import time
import logging
from core.spatial_engine import (
    CanonicalTrackSpace, 
    MapMatchingEngine, 
    SpatialStateEstimator, 
    TrajectoryReconstructionEngine
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("SpatialValidation")

def run_validation():
    # 1. Load Track
    logger.info("Loading SaoPaulo.csv...")
    df_track = pd.read_csv("data/SaoPaulo.csv")
    df_track.columns = df_track.columns.str.strip()
    
    x_center = df_track['# x_m'].values
    z_center = df_track['y_m'].values
    
    track = CanonicalTrackSpace(x_center, z_center)
    map_matching = MapMatchingEngine(track)
    estimator = SpatialStateEstimator(track.total_length)
    reconstructor = TrajectoryReconstructionEngine(track)
    
    logger.info(f"Track loaded. Length: {track.total_length:.2f}m")
    
    # 2. Simulation Loop (60 seconds at 60Hz)
    duration = 60 # seconds
    hz = 60
    dt = 1.0 / hz
    total_frames = duration * hz
    
    # Driver state
    curr_s = 0.0
    speed = 50.0 # 180 km/h constant
    lateral_noise_amp = 0.01 # 1cm noise

    metrics = {
        "max_perp_dist": 0.0,
        "avg_confidence": 0.0,
        "total_jumps": 0,
        "max_s_diff": 0.0,
        "max_L_error": 0.0
    }

    confidences = []

    logger.info("Starting 60s simulation...")
    start_time = time.time()

    for frame in range(total_frames):
        # Move driver along the track with some lateral offset and noise
        curr_s = (curr_s + speed * dt) % track.total_length
        target_L = 1.0 * np.sin(curr_s / 50.0) # Swaying between -1.0 and 1.0m
        noisy_L = target_L + np.random.normal(0, lateral_noise_amp)        
        # Get ground truth world position
        raw_x, raw_z = track.evaluate(curr_s, noisy_L)
        
        # Simulate heading vector
        tx, tz = track.get_tangent(curr_s)
        # Add slight heading error
        heading_vec = (tx + np.random.normal(0, 0.05), tz + np.random.normal(0, 0.05))
        
        # A. Map Matching
        res = map_matching.project(raw_x, raw_z, heading_vec=heading_vec, velocity=speed)
        
        # B. Kalman Estimation
        est_s, s_dot, est_L, L_dot = estimator.update(res["s"], res["L"], dt)
        
        # C. Reconstruction
        final_x, final_z = track.evaluate(est_s, est_L)
        
        # D. Metrics
        perp_dist = np.sqrt((raw_x - final_x)**2 + (raw_z - final_z)**2)
        confidence = 1.0 - (res["score"] / 50.0)
        
        if perp_dist > 0.5: # Debugging large errors
            logger.debug(f"Frame {frame}: curr_s={curr_s:.2f}, est_s={est_s:.2f}, noisy_L={noisy_L:.2f}, est_L={est_L:.2f}")
            logger.debug(f"  Raw: ({raw_x:.2f}, {raw_z:.2f}), Final: ({final_x:.2f}, {final_z:.2f}), Perp Dist: {perp_dist:.3f}")

        metrics["max_perp_dist"] = max(metrics["max_perp_dist"], perp_dist)
        metrics["max_L_error"] = max(metrics["max_L_error"], abs(est_L - noisy_L))
        confidences.append(confidence)
        
        # Check for sector jumps/snapping
        s_diff = abs(curr_s - est_s)
        if s_diff > track.total_length / 2: s_diff = abs(s_diff - track.total_length)
        metrics["max_s_diff"] = max(metrics["max_s_diff"], s_diff)
        
        if s_diff > 5.0: # 5 meter jump is significant
             metrics["total_jumps"] += 1
        
        if frame % (hz * 10) == 0 and frame > 0:
            logger.info(f"Progress: {frame/total_frames*100:.0f}% | Avg Conf: {np.mean(confidences):.3f}")

    metrics["avg_confidence"] = np.mean(confidences)
    
    # 3. Final Report
    print("\n" + "="*40)
    print("SPATIAL ENGINE VALIDATION REPORT")
    print("="*40)
    print(f"Track State:         {'OK' if track.total_length > 0 else 'FAIL'}")
    print(f"Position Accuracy:   {'OK' if metrics['max_perp_dist'] < 0.5 else 'FAIL'} (Max Error: {metrics['max_perp_dist']:.3f}m)")
    print(f"Lateral Stability:   {'OK' if metrics['max_L_error'] < 0.5 else 'FAIL'} (Max L-Error: {metrics['max_L_error']:.3f}m)")
    print(f"Confidence Level:    {metrics['avg_confidence']:.3f}")
    print(f"Continuity Status:   {'OK' if metrics['total_jumps'] == 0 else 'FAIL'} (Jumps: {metrics['total_jumps']})")
    print(f"Spatial Precision:   {((1.0 - metrics['max_perp_dist']/5.0)*100):.1f}%")
    print("="*40)
    
    if metrics['max_perp_dist'] < 0.5 and metrics['total_jumps'] == 0:
        print("CONCLUSION: SYSTEM VALIDATED. SPATIAL INTEGRITY CONFIRMED.")
    else:
        print("CONCLUSION: VALIDATION FAILED. ISSUES DETECTED.")

if __name__ == "__main__":
    run_validation()
