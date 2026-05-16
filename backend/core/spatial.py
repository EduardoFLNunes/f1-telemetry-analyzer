"""
Robust Spatial Engine for F1 Telemetry Analyzer
Provides Spline-based projection, arc-length parameterization, 
and heading-aware temporal continuity.
"""
import numpy as np
from scipy.spatial import KDTree
from scipy.interpolate import interp1d, CubicSpline
from typing import Dict, List, Tuple, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TrackSpline:
    """
    High-precision track representation using arc-length parameterization.
    Supports continuous segment projection and heading-aware validation.
    """
    
    def __init__(self, x: np.ndarray, z: np.ndarray):
        self.x = np.asarray(x, dtype=float)
        self.z = np.asarray(z, dtype=float)
        self.points = np.column_stack([self.x, self.z])
        self.n_samples = len(self.x)
        
        # 1. Calculate cumulative arc-length (s)
        # Using a closed loop (last point connects to first)
        dx = np.diff(self.x, append=self.x[0])
        dz = np.diff(self.z, append=self.z[0])
        self.ds = np.sqrt(dx**2 + dz**2)
        self.s_samples = np.concatenate([[0.0], np.cumsum(self.ds)[:-1]])
        self.total_length = self.s_samples[-1] + self.ds[-1]
        
        # 2. Setup Splines for smooth interpolation
        # Enforce periodicity: x[0] must equal x[-1] for bc_type='periodic'
        # We append a final point at total_length to close the loop perfectly
        s_periodic = np.concatenate([self.s_samples, [self.total_length]])
        x_periodic = np.concatenate([self.x, [self.x[0]]])
        z_periodic = np.concatenate([self.z, [self.z[0]]])

        self.spline_x = CubicSpline(s_periodic, x_periodic, bc_type='periodic')
        self.spline_z = CubicSpline(s_periodic, z_periodic, bc_type='periodic')
        
        # 3. Acceleration Structure
        self.tree = KDTree(self.points)
        
        # 4. Tangent and Normal cache (sampled)
        self.tangents = self.tangent(self.s_samples)
        self.normals = self.normal(self.s_samples)

    def tangent(self, s: np.ndarray) -> np.ndarray:
        """Returns normalized tangent vector at lap distance s."""
        s_mod = s % self.total_length
        dx = self.spline_x(s_mod, 1)
        dz = self.spline_z(s_mod, 1)
        mags = np.hypot(dx, dz) + 1e-10
        return np.column_stack([dx / mags, dz / mags])

    def normal(self, s: np.ndarray) -> np.ndarray:
        """Returns normalized normal vector (90 deg left) at lap distance s."""
        t = self.tangent(s)
        # Rotate (tx, tz) by 90 deg counter-clockwise: (-tz, tx)
        return np.column_stack([-t[:, 1], t[:, 0]])

    def heading_at(self, s: np.ndarray) -> np.ndarray:
        """Alias for tangent, representing the ideal heading at distance s."""
        return self.tangent(s)

    def project_point(
        self, 
        q_x: float, 
        q_z: float, 
        prev_s: Optional[float] = None,
        heading: Optional[Tuple[float, float]] = None
    ) -> Dict[str, Any]:
        """
        Projects a single point (q_x, q_z) onto the track centerline.
        Uses segment-based projection with heading-aware scoring.
        """
        q = np.array([q_x, q_z])
        
        # 1. Candidate Selection
        # Search radius or K-nearest samples
        k = 10 if prev_s is None else 5
        dists, idxs = self.tree.query(q, k=k)
        
        best_s = 0.0
        best_L = 0.0
        min_score = float('inf')
        
        # 2. Test adjacent segments for each candidate index
        # A segment is [i, i+1]
        for i in idxs:
            for seg_start_idx in [i - 1, i]:
                idx1 = seg_start_idx % self.n_samples
                idx2 = (seg_start_idx + 1) % self.n_samples
                
                p1 = self.points[idx1]
                p2 = self.points[idx2]
                
                # Segment vector
                u = p2 - p1
                u_mag_sq = np.sum(u**2)
                if u_mag_sq < 1e-8: continue
                
                # Projection parameter t
                v = q - p1
                t = np.dot(v, u) / u_mag_sq
                t_clamped = np.clip(t, 0, 1)
                
                # Projected point and distance to segment
                proj_p = p1 + t_clamped * u
                perp_dist = np.linalg.norm(q - proj_p)
                
                # Lap distance s
                s_base = self.s_samples[idx1]
                ds_seg = self.ds[idx1]
                s_proj = (s_base + t_clamped * ds_seg) % self.total_length
                
                # 3. Scoring
                score = perp_dist
                
                # Heading penalty
                if heading is not None:
                    track_t = self.tangent(np.array([s_proj]))[0]
                    h_vec = np.array(heading)
                    h_mag = np.linalg.norm(h_vec)
                    if h_mag > 0.01:
                        h_norm = h_vec / h_mag
                        dot = np.dot(h_norm, track_t)
                        # Penalty for misalignment
                        score += (1.0 - dot) * 10.0 
                
                # Continuity penalty (prevent jumps)
                if prev_s is not None:
                    diff = abs(self.min_s_diff(s_proj, prev_s))
                    # Apply steep penalty for jumps larger than expected
                    if diff > 15.0: 
                        score += diff * 2.0
                
                if score < min_score:
                    min_score = score
                    best_s = s_proj
                    
                    # Lateral offset L
                    n = self.normal(np.array([best_s]))[0]
                    v_to_q = q - proj_p
                    best_L = np.dot(v_to_q, n)

        return {
            "s": float(best_s),
            "L": float(best_L),
            "score": float(min_score),
            "x": float(self.spline_x(best_s)),
            "z": float(self.spline_z(best_s))
        }

    def project_sequence(
        self, 
        qx: np.ndarray, 
        qz: np.ndarray, 
        headings: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """
        Projects a sequence of points with temporal continuity enforcement.
        """
        n = len(qx)
        s_arr = np.zeros(n)
        L_arr = np.zeros(n)
        
        last_s = None
        for i in range(n):
            h = headings[i] if headings is not None else None
            res = self.project_point(qx[i], qz[i], prev_s=last_s, heading=h)
            s_arr[i] = res["s"]
            L_arr[i] = res["L"]
            last_s = res["s"]
            
        return {"s": s_arr, "L": L_arr}

    def min_s_diff(self, s1: float, s2: float) -> float:
        """Returns the shortest signed distance between s1 and s2 on the loop."""
        diff = s1 - s2
        if diff > self.total_length / 2:
            diff -= self.total_length
        elif diff < -self.total_length / 2:
            diff += self.total_length
        return diff

    def get_position(self, s: np.ndarray) -> np.ndarray:
        """Returns (x, z) coordinates for given lap distances s."""
        s_mod = s % self.total_length
        return np.column_stack([self.spline_x(s_mod), self.spline_z(s_mod)])

    def _compute_kappa(self, s: np.ndarray) -> np.ndarray:
        """Calculates curvature (kappa) at distance s."""
        s_mod = s % self.total_length
        dx = self.spline_x(s_mod, 1)
        dz = self.spline_z(s_mod, 1)
        ddx = self.spline_x(s_mod, 2)
        ddz = self.spline_z(s_mod, 2)
        
        # Curvature formula: κ = |x'z'' - z'x''| / (x'² + z'²)^(3/2)
        numerator = np.abs(dx * ddz - dz * ddx)
        denominator = (dx**2 + dz**2)**(3/2)
        denominator[denominator < 1e-10] = 1e-10
        return numerator / denominator
