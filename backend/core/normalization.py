"""
SimAdapter for F1 Telemetry Analyzer
Normalizes simulator-specific coordinate systems and units into a 
canonical telemetry-grade format.
"""
import numpy as np
from typing import Dict, Any, Tuple

class SimAdapter:
    """
    Standardizes telemetry from different sims (F1, ACC, AC, iRacing).
    Canonical format:
    - Coordinates: (x, z) in meters (2D horizontal plane)
    - Heading: Unit vector (hx, hz)
    - Speed: m/s
    - Inputs: 0.0 to 1.0 (float)
    """
    
    def __init__(self, sim_type: str = "F1-25"):
        self.sim_type = sim_type
        
        # Axis mapping: (SimX, SimY, SimZ) -> (CanonicalX, CanonicalZ)
        # F1/ACC typically use Y as altitude.
        self.configs = {
            "F1-25": {
                "axes": ("x", "z"), # Sim X -> Canonical X, Sim Z -> Canonical Z
                "flip_z": True,
                "speed_unit": "kmh_to_ms",
                "heading_source": "quaternion" 
            },
            "ACC": {
                "axes": ("x", "z"),
                "flip_z": True,
                "speed_unit": "ms_to_ms",
                "heading_source": "euler"
            },
            "AC": {
                "axes": ("x", "z"),
                "flip_z": False,
                "speed_unit": "ms_to_ms",
                "heading_source": "vector"
            },
            "AC1": {
                "axes": ("x", "z"),
                "flip_z": True,
                "speed_unit": "ms_to_ms",
                "heading_source": "vector"
            }
        }
        self.config = self.configs.get(sim_type, self.configs["F1-25"])

    def get_heading_vector(self, yaw: float) -> Tuple[float, float]:
        """Converts yaw (radians) to a 2D unit vector (hx, hz)."""
        # AC Yaw: 0 = North (+Z), Pi/2 = East (+X)
        hx = np.sin(yaw)
        hz = np.cos(yaw)
        
        if self.config["flip_z"]:
            hz = -hz
            
        return (hx, hz)

    def normalize_pos(self, x: np.ndarray, y: np.ndarray, z: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Maps 3D sim coordinates to 2D canonical (x, z)."""
        # Default for F1/ACC: use X and Z
        cx = x
        cz = z
        
        if self.config["flip_z"]:
            cz = -cz
            
        return cx, cz

    def normalize_heading(self, hx: np.ndarray, hy: np.ndarray, hz: np.ndarray) -> np.ndarray:
        """Normalizes heading vectors to unit (hx, hz) vectors."""
        # We ignore vertical heading component (hy)
        mags = np.hypot(hx, hz) + 1e-10
        return np.column_stack([hx / mags, hz / mags])

    def normalize_speed(self, speed: np.ndarray) -> np.ndarray:
        """Converts speed to m/s."""
        if self.config["speed_unit"] == "kmh_to_ms":
            return speed / 3.6
        return speed

    def normalize_inputs(self, throttle: np.ndarray, brake: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Normalizes inputs to 0.0 - 1.0 range."""
        # Ensure they are floats and clipped
        t = np.asarray(throttle, dtype=float)
        b = np.asarray(brake, dtype=float)
        
        # F1 UDP can sometimes be 0-255 or 0.0-1.0 depending on packet version
        if t.max() > 1.1: t /= 255.0
        if b.max() > 1.1: b /= 255.0
        
        return np.clip(t, 0, 1), np.clip(b, 0, 1)

    @staticmethod
    def get_heading_from_quaternion(q: np.ndarray) -> np.ndarray:
        """
        Calculates 2D heading vector from quaternion (w, x, y, z).
        Common in F1 Motion packets.
        """
        # Assuming Z is forward in local frame
        # Direction vector d = R * [0, 0, 1]
        # dx = 2(xz + wy), dy = 2(yz - wx), dz = 1 - 2(xx + yy)
        # For 2D: (dx, dz)
        w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
        
        dx = 2.0 * (x * z + w * y)
        dz = 1.0 - 2.0 * (x * x + y * y)
        
        mags = np.hypot(dx, dz) + 1e-10
        return np.column_stack([dx / mags, dz / mags])
