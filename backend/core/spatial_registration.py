"""
Formal Spatial Registration Layer
Unifies different coordinate systems (CSV, Shared Memory, GPS) into a single Canonical Space.
Deterministic, non-snapping, and verifiable.
"""
import numpy as np
from typing import Dict, Tuple, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class SpatialTransform:
    """
    Represents a formal 2D transformation: Scale, Rotation, Offset, and Axis Remapping.
    """
    def __init__(self, name: str = "default"):
        self.name = name
        self.scale = 1.0
        self.rotation = 0.0  # Radians
        self.offset_x = 0.0
        self.offset_z = 0.0
        self.flip_x = False
        self.flip_z = False
        self.swap_axes = False
        self.is_initialized = False

    def apply(self, x: float, z: float) -> Tuple[float, float]:
        """Applies the formal transform to a raw coordinate."""
        # 1. Axis Swap
        tx, tz = (z, x) if self.swap_axes else (x, z)
        
        # 2. Flips
        if self.flip_x: tx *= -1
        if self.flip_z: tz *= -1
        
        # 3. Scale
        tx *= self.scale
        tz *= self.scale
        
        # 4. Rotation
        if abs(self.rotation) > 1e-6:
            c, s = np.cos(self.rotation), np.sin(self.rotation)
            rx = tx * c - tz * s
            rz = tx * s + tz * c
            tx, tz = rx, rz
            
        # 5. Offset
        tx += self.offset_x
        tz += self.offset_z
        
        return tx, tz

    def apply_vector(self, vx: float, vz: float) -> Tuple[float, float]:
        """Applies ONLY rotation/flip/swap (no offset or translation)."""
        tx, tz = (vz, vx) if self.swap_axes else (vx, vz)
        if self.flip_x: tx *= -1
        if self.flip_z: tz *= -1
        
        if abs(self.rotation) > 1e-6:
            c, s = np.cos(self.rotation), np.sin(self.rotation)
            rx = tx * c - tz * s
            rz = tx * s + tz * c
            tx, tz = rx, rz
            
        return tx, tz

    def configure(self, config: Dict[str, Any]):
        self.scale = config.get("scale", 1.0)
        self.rotation = config.get("rotation", 0.0)
        self.offset_x = config.get("offset_x", 0.0)
        self.offset_z = config.get("offset_z", 0.0)
        self.flip_x = config.get("flip_x", False)
        self.flip_z = config.get("flip_z", False)
        self.swap_axes = config.get("swap_axes", False)
        self.is_initialized = True
        logger.info(f"SpatialTransform '{self.name}' configured: {config}")

class SpatialRegistrar:
    """
    Master Registrar for the application.
    Ensures Track and Sim live in the same Canonical Space.
    """
    def __init__(self):
        # Transform for Track CSV -> Canonical
        self.track_to_canonical = SpatialTransform("track_to_canonical")
        # Transform for Sim Shared Memory -> Canonical
        self.sim_to_canonical = SpatialTransform("sim_to_canonical")
        
        self.canonical_origin = (0.0, 0.0)
        
    def register_track(self, points: np.ndarray):
        """
        Initializes the track transform. 
        Usually, the track defines the Canonical Space origin.
        """
        # For now, we center the track as our Canonical Space
        center = np.mean(points, axis=0)
        self.track_to_canonical.configure({
            "offset_x": -float(center[0]),
            "offset_z": -float(center[1]),
            "scale": 1.0,
            "rotation": 0.0
        })
        logger.info(f"Track registered. Canonical origin set to track mean: {center}")

    def align_sim(self, sim_points: np.ndarray, anchor_points: np.ndarray):
        """
        Formal Global Origin Alignment.
        Uses paired points (sim vs theoretical track) to calculate 
        a deterministic global offset, scale, and rotation.
        """
        if len(sim_points) < 20 or len(sim_points) != len(anchor_points):
            logger.warning("Alignment failed: point count mismatch or insufficient data.")
            return
        
        # 1. Zero-center both samples for scale/rotation search
        # Note: This is ONLY for identifying the rotation/flip/scale.
        # The final offset will be calculated globally.
        s_mean = np.mean(sim_points, axis=0)
        a_mean = np.mean(anchor_points, axis=0)
        
        s_norm = sim_points - s_mean
        a_norm = anchor_points - a_mean
        
        # 2. Estimate Scale (robustly)
        s_mags = np.linalg.norm(s_norm, axis=1)
        a_mags = np.linalg.norm(a_norm, axis=1)
        # Use median of ratios to reject outliers (pitting, bumps)
        scale_ratios = a_mags / (s_mags + 1e-6)
        scale = float(np.median(scale_ratios))
        if scale < 0.1 or scale > 10.0: scale = 1.0 # Safety clamp
        
        # 3. Exhaustive Axis/Flip Search (8 combinations)
        from scipy.spatial import KDTree
        tree = KDTree(a_norm)
        
        best_score = float('inf')
        best_config = (False, False, False)
        
        for swap in [False, True]:
            for flip_x in [False, True]:
                for flip_z in [False, True]:
                    test = s_norm.copy()
                    if swap: test = test[:, [1, 0]]
                    if flip_x: test[:, 0] *= -1
                    if flip_z: test[:, 1] *= -1
                    
                    dists, _ = tree.query(test * scale, k=1)
                    score = np.mean(dists)
                    if score < best_score:
                        best_score = score
                        best_config = (swap, flip_x, flip_z)

        # 4. FORMAL GLOBAL OFFSET CALCULATION
        # Transform the raw sim mean using the best rotation/flip/scale
        tx, tz = s_mean[0], s_mean[1]
        if best_config[0]: tx, tz = tz, tx
        if best_config[1]: tx *= -1
        if best_config[2]: tz *= -1
        
        # Global offset is what brings the transformed sim mean to the anchor mean
        # anchor_mean = (sim_mean_transformed * scale) + offset
        # offset = anchor_mean - (sim_mean_transformed * scale)
        off_x = a_mean[0] - (tx * scale)
        off_z = a_mean[1] - (tz * scale)
        
        self.sim_to_canonical.configure({
            "swap_axes": best_config[0],
            "flip_x": best_config[1],
            "flip_z": best_config[2],
            "scale": scale,
            "offset_x": off_x,
            "offset_z": off_z
        })
        
        # 5. DIAGNOSTICS
        # Calculate residual errors after alignment
        residuals = []
        for i in range(len(sim_points)):
            tx, tz = self.transform_sim(sim_points[i][0], sim_points[i][1])
            dx = anchor_points[i][0] - tx
            dz = anchor_points[i][1] - tz
            residuals.append(np.hypot(dx, dz))
        
        avg_err = np.mean(residuals)
        logger.info(f"Global Alignment Success. Error: {avg_err:.3f}m | Offset: [{off_x:.1f}, {off_z:.1f}]")

    def get_diagnostics(self, sim_x: float, sim_z: float, anchor_x: float, anchor_z: float) -> Dict[str, float]:
        """Calculates real-time alignment drift diagnostics."""
        tx, tz = self.transform_sim(sim_x, sim_z)
        dx = anchor_x - tx
        dz = anchor_z - tz
        return {
            "dx": float(dx),
            "dz": float(dz),
            "drift": float(np.hypot(dx, dz))
        }

    def transform_track(self, x: float, z: float) -> Tuple[float, float]:
        return self.track_to_canonical.apply(x, z)

    def transform_sim(self, x: float, z: float) -> Tuple[float, float]:
        return self.sim_to_canonical.apply(x, z)
        
    def transform_sim_vector(self, vx: float, vz: float) -> Tuple[float, float]:
        return self.sim_to_canonical.apply_vector(vx, vz)

# Global Instance
registrar = SpatialRegistrar()
