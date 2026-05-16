import numpy as np
from typing import Dict, Any

class VehiclePhysicsAdapter:
    """
    Computes professional spatial metrics from raw telemetry.
    Calculates slip angle, heading, and accurate lateral positioning.
    """
    def __init__(self):
        self.prev_x = 0.0
        self.prev_z = 0.0
        self.last_update = 0.0

    def calculate_metrics(self, packet: Dict[str, Any], current_time: float) -> Dict[str, Any]:
        """
        Derives high-fidelity spatial metrics.
        Packet expected keys: x, z, heading (rad), speed (m/s), steering_angle (rad)
        """
        x, z = packet['x'], packet['z']
        speed = packet.get('speed', 0.0)
        heading = packet.get('heading', 0.0)
        steering = packet.get('steering_angle', 0.0)
        
        # 1. Velocity Vector
        dt = max(current_time - self.last_update, 0.001)
        dx = x - self.prev_x
        dz = z - self.prev_z
        vel_heading = np.arctan2(dx, dz)
        
        # 2. Slip Angle (Beta)
        # Difference between where the car is pointed and where it's going
        slip_angle = heading - vel_heading
        
        # 3. Lateral Acceleration (Simple estimate for instability detection)
        lateral_accel = (heading - self.last_heading) / dt * speed if hasattr(self, 'last_heading') else 0.0
        
        # 4. Steering vs Heading
        # Difference between intention (steering) and result (heading)
        steering_error = steering - slip_angle
        
        # Cache
        self.prev_x, self.prev_z = x, z
        self.last_update = current_time
        self.last_heading = heading
        
        return {
            "slip_angle": float(slip_angle),
            "heading_error": float(steering_error),
            "lateral_accel": float(lateral_accel),
            "velocity_heading": float(vel_heading)
        }
