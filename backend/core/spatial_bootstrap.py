"""
Initial Spatial Bootstrap Module
Resolves the 'Where am I?' problem on session startup or reset.
Uses physical world position instead of logical lap progress.
"""
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class InitialTrackRegistration:
    """
    Handles the first-time spatial anchoring of a vehicle to the track geometry.
    Ensures that spawning in pits or mid-track doesn't default to s=0.
    """
    def __init__(self, track):
        # track is expected to be a CanonicalTrackSpace instance
        self.track = track
        
    def infer_initial_state(self, x: float, z: float, heading_vec: Tuple[float, float]) -> Dict[str, Any]:
        """
        Global search for the nearest track segment to bootstrap the spatial anchor.
        Uses world coordinates and heading validation.
        """
        q = np.array([x, z])
        
        # 1. Global Candidate Selection (Search the entire track tree)
        # We take a large number of candidates to ensure we find the right segment even in pits
        dists, idxs = self.track.tree.query(q, k=40)
        
        best_s = 0.0
        best_L = 0.0
        best_score = float('inf')
        best_idx = 0
        
        # 2. Exhaustive segment scoring
        for i in idxs:
            # Check segments [i-1, i] and [i, i+1]
            for seg_start_idx in [i - 1, i]:
                idx1 = seg_start_idx % self.track.n_samples
                idx2 = (seg_start_idx + 1) % self.track.n_samples
                
                p1 = self.track.points[idx1]
                p2 = self.track.points[idx2]
                
                u = p2 - p1
                u_mag_sq = np.sum(u**2)
                if u_mag_sq < 1e-8: continue
                
                v = q - p1
                t = np.clip(np.dot(v, u) / u_mag_sq, 0, 1)
                
                proj_p = p1 + t * u
                perp_dist = np.linalg.norm(q - proj_p)
                
                s_proj = (self.track.s_samples[idx1] + t * self.track.ds[idx1]) % self.track.total_length
                
                # Scoring Function
                score = perp_dist
                
                # Heading Validation (Crucial for bootstrap)
                tx, tz = self.track.get_tangent(s_proj)
                h_mag = np.hypot(heading_vec[0], heading_vec[1])
                if h_mag > 0.1:
                    h_norm = np.array(heading_vec) / h_mag
                    dot = np.dot(h_norm, [tx, tz])
                    # Heavy penalty for wrong direction (prevents snapping to opposite side of track)
                    score += (1.0 - dot) * 30.0
                
                if score < best_score:
                    best_score = score
                    best_s = s_proj
                    best_idx = i
                    # Lateral Offset L
                    nx, nz = self.track.get_normal(best_s)
                    v_to_q = q - proj_p
                    best_L = np.dot(v_to_q, [nx, nz])

        # 3. Pitlane Detection (Heuristic)
        # Usually pits are significantly offset from the centerline (> 7m)
        is_pitlane = abs(best_L) > 7.0
        
        # 4. Confidence calculation
        # A good match in a well-defined track should have low best_score
        confidence = max(0.0, 1.0 - (best_score / 25.0))
        
        logger.info(f"Spatial Bootstrap: s={best_s:.1f}, L={best_L:.1f}, Pit={is_pitlane}, Conf={confidence:.2f}")
        
        return {
            "initial_s": float(best_s),
            "initial_L": float(best_L),
            "is_pitlane": is_pitlane,
            "confidence": confidence,
            "nearest_idx": int(best_idx),
            "source": "world_bootstrap"
        }
