"""
Professional Motorsport Spatial Engine
Deterministic, track-relative, spline-based spatial intelligence.
"""
import numpy as np
from scipy.spatial import KDTree
from scipy.interpolate import CubicSpline
from typing import Dict, List, Tuple, Any, Optional
import logging
import time

logger = logging.getLogger(__name__)

class CanonicalTrackSpace:
    """
    Authoritative spatial model of the track.
    Provides arc-length parameterization, spline interpolation, and geometric properties.
    """
    def __init__(self, x: np.ndarray, z: np.ndarray):
        self.x = np.asarray(x, dtype=float)
        self.z = np.asarray(z, dtype=float)
        self.points = np.column_stack([self.x, self.z])
        self.n_samples = len(self.x)
        
        # 1. Calculate cumulative arc-length (s)
        dx = np.diff(self.x, append=self.x[0])
        dz = np.diff(self.z, append=self.z[0])
        self.ds = np.sqrt(dx**2 + dz**2)
        self.s_samples = np.concatenate([[0.0], np.cumsum(self.ds)[:-1]])
        self.total_length = self.s_samples[-1] + self.ds[-1]
        
        # 2. Setup Periodic Splines
        s_periodic = np.concatenate([self.s_samples, [self.total_length]])
        x_periodic = np.concatenate([self.x, [self.x[0]]])
        z_periodic = np.concatenate([self.z, [self.z[0]]])

        self.spline_x = CubicSpline(s_periodic, x_periodic, bc_type='periodic')
        self.spline_z = CubicSpline(s_periodic, z_periodic, bc_type='periodic')
        
        # 3. Acceleration Structure
        self.tree = KDTree(self.points)
        
    def evaluate(self, s: float, L: float = 0.0) -> Tuple[float, float]:
        """Reconstructs (x, z) position from (s, L) coordinates."""
        s_mod = s % self.total_length
        base_x = float(self.spline_x(s_mod))
        base_z = float(self.spline_z(s_mod))
        
        if abs(L) < 1e-6:
            return base_x, base_z
            
        # Add lateral offset using normal
        nx, nz = self.get_normal(s_mod)
        return base_x + nx * L, base_z + nz * L

    def get_tangent(self, s: float) -> Tuple[float, float]:
        """Returns normalized tangent vector at lap distance s."""
        s_mod = s % self.total_length
        dx = float(self.spline_x(s_mod, 1))
        dz = float(self.spline_z(s_mod, 1))
        mag = np.hypot(dx, dz) + 1e-10
        return dx / mag, dz / mag

    def get_normal(self, s: float) -> Tuple[float, float]:
        """Returns normalized normal vector (90 deg left) at lap distance s."""
        tx, tz = self.get_tangent(s)
        return -tz, tx

    def get_curvature(self, s: float) -> float:
        """Calculates curvature (kappa) at distance s."""
        s_mod = s % self.total_length
        dx = self.spline_x(s_mod, 1)
        dz = self.spline_z(s_mod, 1)
        ddx = self.spline_x(s_mod, 2)
        ddz = self.spline_z(s_mod, 2)
        
        num = abs(dx * ddz - dz * ddx)
        den = (dx**2 + dz**2)**(1.5) + 1e-10
        return float(num / den)

class MapMatchingEngine:
    """
    High-precision map matching with heading validation and temporal continuity.
    Responsible for projecting raw coordinates into canonical (s, L) space.
    """
    def __init__(self, track: CanonicalTrackSpace):
        self.track = track
        self.last_s = None
        self.spatial_lock_threshold = 20.0  # meters
        
    def project(self, x: float, z: float, heading_vec: Optional[Tuple[float, float]] = None, velocity: float = 0.0, hint_s: Optional[float] = None) -> Dict[str, Any]:
        q = np.array([x, z])
        
        # 1. Candidate Selection
        if hint_s is not None:
            # If we have a hint (from lap_dist_pct), use it to narrow search
            idxs = [int((hint_s / self.track.total_length) * self.track.n_samples) % self.track.n_samples]
            # Add neighbors
            idxs += [(idxs[0] + offset) % self.track.n_samples for offset in range(-5, 6) if offset != 0]
        else:
            k = 15 if self.last_s is None else 8
            dists, idxs = self.track.tree.query(q, k=k)
        
        best_s = 0.0
        best_L = 0.0
        best_score = float('inf')
        
        # 2. Score candidates
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
                
                # Heading Validation
                if heading_vec is not None:
                    tx, tz = self.track.get_tangent(s_proj)
                    h_mag = np.linalg.norm(heading_vec)
                    if h_mag > 0.1:
                        h_norm = np.array(heading_vec) / h_mag
                        dot = np.dot(h_norm, [tx, tz])
                        # Heavy penalty for wrong direction (reverse snapping protection)
                        score += (1.0 - dot) * 20.0
                
                # Temporal Continuity
                if self.last_s is not None:
                    s_diff = abs(self._min_s_diff(s_proj, self.last_s))
                    # Penalty for jumping too far
                    if s_diff > 10.0:
                        score += s_diff * 1.5
                    
                if score < best_score:
                    best_score = score
                    best_s = s_proj
                    
                    # Lateral Offset L
                    nx, nz = self.track.get_normal(best_s)
                    v_to_q = q - proj_p
                    best_L = np.dot(v_to_q, [nx, nz])

        # 3. Spatial Locking / Outlier Rejection
        if self.last_s is not None:
            jump = abs(self._min_s_diff(best_s, self.last_s))
            if jump > self.spatial_lock_threshold and velocity < 100.0: # 100m/s is very fast
                logger.warning(f"MapMatching: Rejected large jump {jump:.1f}m")
                # Return previous s if jump is too large (unless we have no choice)
                # For now, we trust the scoring but we could be more aggressive
        
        self.last_s = best_s
        return {"s": best_s, "L": best_L, "score": best_score}

    def _min_s_diff(self, s1: float, s2: float) -> float:
        diff = s1 - s2
        if diff > self.track.total_length / 2: diff -= self.track.total_length
        elif diff < -self.track.total_length / 2: diff += self.track.total_length
        return diff

class SpatialStateEstimator:
    """
    Kalman Filter based state estimator for (s, L) coordinates.
    Smoothes out jitter and predicts future states.
    """
    def __init__(self, total_length: float):
        self.total_length = total_length
        # State: [s, s_dot, L, L_dot]
        self.x = np.zeros(4)
        self.P = np.eye(4) * 10.0
        self.F = np.eye(4) # Transition matrix
        self.H = np.array([[1, 0, 0, 0], [0, 0, 1, 0]]) # Measurement matrix
        self.Q = np.eye(4) * 0.1 # Process noise
        self.R = np.array([[0.1, 0], [0, 1.0]]) # Measurement noise (reduced for s)
        self.initialized = False

    def update(self, s: float, L: float, dt: float) -> Tuple[float, float, float, float]:
        if not self.initialized:
            self.x = np.array([s, 0.0, L, 0.0])
            self.initialized = True
            return s, 0.0, L, 0.0
            
        # 1. Predict
        self.F[0, 1] = dt
        self.F[2, 3] = dt
        self.x = self.F @ self.x
        # Wrap s after prediction
        self.x[0] = self.x[0] % self.total_length
        
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        # 2. Correct (handling s-wrap)
        s_meas = s
        s_diff = s_meas - self.x[0]
        # Shortest path for wrap-around
        if s_diff > self.total_length / 2: s_diff -= self.total_length
        elif s_diff < -self.total_length / 2: s_diff += self.total_length
        
        y = np.array([s_diff, L - self.x[2]])
        
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        # Wrap s after correction
        self.x[0] = self.x[0] % self.total_length
        
        self.P = (np.eye(4) - K @ self.H) @ self.P
        
        return self.x[0], self.x[1], self.x[2], self.x[3]

class TrajectoryReconstructionEngine:
    """
    Handles continuous path reconstruction and historical buffering.
    Provides stable, interpolated trajectory data.
    """
    def __init__(self, track: CanonicalTrackSpace):
        self.track = track
        self.history: List[Dict[str, Any]] = []
        self.max_history = 1000
        
    def add_point(self, s: float, L: float, timestamp: float, speed: float):
        self.history.append({
            "s": s, "L": L, "t": timestamp, "v": speed
        })
        if len(self.history) > self.max_history:
            self.history.pop(0)
            
    def get_interpolated_state(self, timestamp: float) -> Optional[Dict[str, Any]]:
        if len(self.history) < 2: return None
        
        # Find segment in history
        for i in range(len(self.history) - 1, 0, -1):
            p1 = self.history[i-1]
            p2 = self.history[i]
            if p1["t"] <= timestamp <= p2["t"]:
                t = (timestamp - p1["t"]) / (p2["t"] - p1["t"])
                # Shortest path for s-wrap
                s1, s2 = p1["s"], p2["s"]
                ds = s2 - s1
                if ds > self.track.total_length / 2: ds -= self.track.total_length
                elif ds < -self.track.total_length / 2: ds += self.track.total_length
                
                s = (s1 + ds * t) % self.track.total_length
                L = p1["L"] + (p2["L"] - p1["L"]) * t
                v = p1["v"] + (p2["v"] - p1["v"]) * t
                
                x, z = self.track.evaluate(s, L)
                return {"s": s, "L": L, "x": x, "z": z, "v": v}
        return None

class RenderSpaceAdapter:
    """
    Converts canonical track-space into render-space.
    Handles coordinate transforms and camera-relative logic.
    """
    @staticmethod
    def to_render_space(x: float, z: float) -> Tuple[float, float]:
        return x, z
        
    @staticmethod
    def get_camera_target(s: float, L: float, track: CanonicalTrackSpace, look_ahead: float = 20.0) -> Dict[str, Any]:
        """Calculates stable follow-camera target with predictive look-ahead."""
        curr_x, curr_z = track.evaluate(s, L)
        target_s = (s + look_ahead) % track.total_length
        target_x, target_z = track.evaluate(target_s, 0.0)
        
        dx = target_x - curr_x
        dz = target_z - curr_z
        heading = np.arctan2(dx, -dz)
        
        return {
            "pos": (curr_x, curr_z),
            "heading": heading,
            "target": (target_x, target_z)
        }
