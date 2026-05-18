"""
Assetto Corsa Shared Memory Adapter
Reads high-frequency telemetry directly from AC1 Shared Memory.
"""
import mmap
import ctypes
from ctypes import c_int, c_float, c_wchar, Structure
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- AC Shared Memory Structures ---

class SPageFilePhysics(Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int),
        ("gas", c_float),
        ("brake", c_float),
        ("fuel", c_float),
        ("gear", c_int),
        ("rpms", c_int),
        ("steerAngle", c_float),
        ("speedKmh", c_float),
        ("velocity", c_float * 3),
        ("accG", c_float * 3),
        ("wheelSlip", c_float * 4),
        ("wheelLoad", c_float * 4),
        ("wheelsPressure", c_float * 4),
        ("wheelAngularSpeed", c_float * 4),
        ("tyreWear", c_float * 4),
        ("tyreDirtyLevel", c_float * 4),
        ("tyreCoreTemp", c_float * 4),
        ("camberRAD", c_float * 4),
        ("suspensionTravel", c_float * 4),
        ("drs", c_float),
        ("tc", c_float),
        ("heading", c_float),
        ("pitch", c_float),
        ("roll", c_float),
        ("cgHeight", c_float),
        ("carDamage", c_float * 5),
        ("numberOfTyresOut", c_int),
        ("pitLimiterOn", c_int),
        ("abs", c_float),
        ("kersCharge", c_float),
        ("kersInput", c_float),
        ("autoShifterOn", c_int),
        ("rideHeight", c_float * 2),
        ("turboBoost", c_float),
        ("ballast", c_float),
        ("airDensity", c_float),
        ("airTemp", c_float),
        ("roadTemp", c_float),
        ("localAngularVel", c_float * 3),
        ("finalFF", c_float),
        ("performanceMeter", c_float),
        ("engineBrake", c_int),
        ("ersRecoveryLevel", c_int),
        ("ersPowerLevel", c_int),
        ("ersHeatCharging", c_int),
        ("ersIsBatteryCharging", c_int),
        ("kersCurrentVK", c_float),
        ("visualTyreDamage", c_float * 4),
        ("elecSystemsOverlap", c_int),
        ("ersFuelDiff", c_float),
        ("diffPa", c_int),
        ("tyreTempI", c_float * 4),
        ("tyreTempM", c_float * 4),
        ("tyreTempO", c_float * 4),
        ("isAIControlled", c_int),
        ("tyreContactPoint", c_float * 4 * 3),
        ("tyreContactNormal", c_float * 4 * 3),
        ("tyreContactHeading", c_float * 4 * 3),
        ("brakeTemp", c_float * 4),
        ("clutch", c_float),
        ("tyreTempI2", c_float * 4),
        ("tyreTempM2", c_float * 4),
        ("tyreTempO2", c_float * 4),
        ("isShadowTrack", c_int),
        ("iDiffPriority", c_int),
        ("tyreWorkTemp", c_float * 4),
        ("flag", c_int),
        ("iCurrentMaxGear", c_int),
        ("iCurrentTyreSet", c_int),
        ("iMguKMaxTorque", c_float),
        ("iMguHMaxTorque", c_float),
        ("gearRatio", c_float * 7),
        ("iDiffIn", c_float),
        ("iDiffOut", c_float),
    ]

class SPageFileGraphics(Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", c_int),
        ("status", c_int),
        ("session", c_int),
        ("currentTime", c_wchar * 15),
        ("lastTime", c_wchar * 15),
        ("bestTime", c_wchar * 15),
        ("split", c_wchar * 15),
        ("completedLaps", c_int),
        ("position", c_int),
        ("iCurrentTime", c_int),
        ("iLastTime", c_int),
        ("iBestTime", c_int),
        ("sessionTimeLeft", c_float),
        ("distanceTraveled", c_float),
        ("isInPit", c_int),
        ("currentSectorIndex", c_int),
        ("lastSectorTime", c_int),
        ("numberOfLaps", c_int),
        ("tyreCompound", c_wchar * 33),
        ("replayTimeMultiplier", c_float),
        ("normalizedCarPosition", c_float),
        ("carCoordinates", c_float * 3),
        ("penaltyTime", c_float),
        ("flag", c_int),
        ("idealLineOn", c_int),
        ("isInPitLane", c_int),
        ("surfaceGrip", c_float),
        ("mandatoryPitDone", c_int),
        ("windSpeed", c_float),
        ("windDirection", c_float),
        ("isSetupMenuVisible", c_int),
        ("mainDisplayIndex", c_int),
        ("secondaryDisplayIndex", c_int),
        ("tc", c_int),
        ("tcCut", c_int),
        ("engineMap", c_int),
        ("abs", c_int),
        ("fuelUsedLaps", c_float),
        ("rainIntensity", c_int),
        ("rainIntensityIn10min", c_int),
        ("rainIntensityIn30min", c_int),
        ("currentTyreSet", c_int),
        ("strategyTyreSet", c_int),
        ("gapAhead", c_int),
        ("gapBehind", c_int),
    ]

class SPageFileStatic(Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", c_wchar * 15),
        ("acVersion", c_wchar * 15),
        ("numberOfSessions", c_int),
        ("numCars", c_int),
        ("carModel", c_wchar * 33),
        ("track", c_wchar * 33),
        ("playerName", c_wchar * 33),
        ("playerSurname", c_wchar * 33),
        ("playerNick", c_wchar * 33),
        ("sectorCount", c_int),
        ("maxTorque", c_float),
        ("maxPower", c_float),
        ("maxRpm", c_int),
        ("maxFuel", c_float),
        ("suspensionMaxTravel", c_float * 4),
        ("tyreRadius", c_float * 4),
        ("maxTurboBoost", c_float),
        ("deprecated_1", c_float),
        ("deprecated_2", c_float),
        ("isPenaltyEnabled", c_int),
        ("aidFuelRate", c_float),
        ("aidTireRate", c_float),
        ("aidMechanicalDamage", c_float),
        ("aidAllowTyreBlankets", c_int),
        ("aidStability", c_float),
        ("aidAutoClutch", c_int),
        ("aidAutoBlip", c_int),
        ("hasDRS", c_int),
        ("hasERS", c_int),
        ("hasKERS", c_int),
        ("kersMaxJ", c_float),
        ("engineBrakeSettingsCount", c_int),
        ("ersPowerControllerCount", c_int),
        ("trackSplineLength", c_float),
        ("trackConfiguration", c_wchar * 33),
        ("ersMaxJ", c_float),
        ("isTimedRace", c_int),
        ("hasExtraLap", c_int),
        ("carSkin", c_wchar * 33),
        ("reversedGridPositions", c_int),
        ("PitWindowStart", c_int),
        ("PitWindowEnd", c_int),
        ("isOnline", c_int),
    ]

class AssettoAdapter:
    """
    Adapter for Assetto Corsa Shared Memory.
    """
    def __init__(self):
        self._mmap_physics = None
        self._mmap_graphics = None
        self._mmap_static = None
        
        self.physics = SPageFilePhysics()
        self.graphics = SPageFileGraphics()
        self.static = SPageFileStatic()
        
        self.is_connected = False

    def connect(self) -> bool:
        """Connects to the AC shared memory pages."""
        try:
            # AC shared memory uses naming convention: acpmf_physics, acpmf_graphics, acpmf_static
            self._mmap_physics = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), tagname="acpmf_physics", access=mmap.ACCESS_READ)
            self._mmap_graphics = mmap.mmap(-1, ctypes.sizeof(SPageFileGraphics), tagname="acpmf_graphics", access=mmap.ACCESS_READ)
            self._mmap_static = mmap.mmap(-1, ctypes.sizeof(SPageFileStatic), tagname="acpmf_static", access=mmap.ACCESS_READ)
            
            self.is_connected = True
            logger.info("Connected to Assetto Corsa Shared Memory")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to AC Shared Memory: {e}")
            self.is_connected = False
            return False

    def poll(self) -> Optional[Dict[str, Any]]:
        """Polls current state and returns a normalized frame."""
        if not self.is_connected:
            if not self.connect(): return None

        try:
            # Read directly into structures
            self._mmap_physics.seek(0)
            self.physics = SPageFilePhysics.from_buffer_copy(self._mmap_physics[:ctypes.sizeof(SPageFilePhysics)])
            
            self._mmap_graphics.seek(0)
            self.graphics = SPageFileGraphics.from_buffer_copy(self._mmap_graphics[:ctypes.sizeof(SPageFileGraphics)])
            
            self._mmap_static.seek(0)
            self.static = SPageFileStatic.from_buffer_copy(self._mmap_static[:ctypes.sizeof(SPageFileStatic)])
            
            # Heartbeat logging
            logger.debug(f"AC Telemetry Active | Speed: {self.physics.speedKmh:.1f} | RPM: {self.physics.rpms} | Pos: {list(self.graphics.carCoordinates)}")
            
            # Map to canonical frame
            return self._normalize()
        except Exception as e:
            logger.error(f"Error polling AC Shared Memory: {e}")
            self.is_connected = False
            return None

    def _normalize(self) -> Dict[str, Any]:
        """Converts raw AC data into the platform's standardized format."""
        return {
            "type": "ac_frame",
            "sim_type": "AC1",
            "status": self.graphics.status,
            "session_type": self.graphics.session,
            "x": self.graphics.carCoordinates[0],
            "y": self.graphics.carCoordinates[1],
            "z": self.graphics.carCoordinates[2],
            "speed": self.physics.speedKmh / 3.6, # Convert to m/s
            "throttle": self.physics.gas,
            "brake": self.physics.brake,
            "steer": self.physics.steerAngle,
            "gear": self.physics.gear - 1, # AC gear: 0=R, 1=N, 2=1... -> Platform: -1=R, 0=N, 1=1...
            "rpm": self.physics.rpms,
            "lap_number": self.graphics.completedLaps + 1,
            "lap_time": self.graphics.iCurrentTime / 1000.0,
            "lap_dist_pct": self.graphics.normalizedCarPosition,
            "heading": self.physics.heading,
            "accel_g": self.physics.accG[2], # Z is longitudinal in AC physics? Need to verify
            "lat_g": self.physics.accG[0],
            "wheel_slip": list(self.physics.wheelSlip),
            "timestamp": time.time(),
            "car_model": self.static.carModel,
            "track_name": self.static.track,
            "track_config": self.static.trackConfiguration,
            "track_length": self.static.trackSplineLength,
            "game_code": "assetto_corsa",
            "ac_install_path": None,
        }

    def close(self):
        """Closes memory mappings."""
        if self._mmap_physics: self._mmap_physics.close()
        if self._mmap_graphics: self._mmap_graphics.close()
        if self._mmap_static: self._mmap_static.close()
        self.is_connected = False
