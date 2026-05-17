import mmap
import ctypes
import time
import threading

# Estruturas simplificadas do AC via ctypes para mapeamento perfeito de memória
class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", ctypes.c_wchar * 15),
        ("acVersion", ctypes.c_wchar * 15),
        ("numberOfSessions", ctypes.c_int),
        ("numCars", ctypes.c_int),
        ("carModel", ctypes.c_wchar * 33),
        ("track", ctypes.c_wchar * 33),
        ("playerName", ctypes.c_wchar * 33),
    ]

class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", ctypes.c_float * 3),
        ("accG", ctypes.c_float * 3),
        ("wheelSlip", ctypes.c_float * 4),
        ("wheelLoad", ctypes.c_float * 4),
        ("wheelsPressure", ctypes.c_float * 4),
        ("wheelAngularSpeed", ctypes.c_float * 4),
        ("tyreWear", ctypes.c_float * 4),
        ("tyreDirtyLevel", ctypes.c_float * 4),
        ("tyreCoreTemperature", ctypes.c_float * 4),
        ("camberRAD", ctypes.c_float * 4),
        ("suspensionTravel", ctypes.c_float * 4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
    ]

class SPageFileGraphics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("activeCars", ctypes.c_int),
        ("carCoordinates", ctypes.c_float * 3),
    ]

class AssettoCorsaTelemetryReader:
    def __init__(self, track_parser_callback=None):
        self.shm_static = None
        self.shm_physics = None
        self.shm_graphics = None
        self.running = False
        self.current_track = ""
        self.track_parser_callback = track_parser_callback
        self.telemetry_data = {"x": 0.0, "z": 0.0, "speed": 0.0, "heading": 0.0}

    def connect(self):
        try:
            self.shm_static = mmap.mmap(0, ctypes.sizeof(SPageFileStatic), "Local\\acpmf_static", mmap.ACCESS_READ)
            self.shm_physics = mmap.mmap(0, ctypes.sizeof(SPageFilePhysics), "Local\\acpmf_physics", mmap.ACCESS_READ)
            self.shm_graphics = mmap.mmap(0, ctypes.sizeof(SPageFileGraphics), "Local\\acpmf_graphics", mmap.ACCESS_READ)
            return True
        except Exception as e:
            return False

    def start(self):
        if self.connect():
            self.running = True
            threading.Thread(target=self._loop, daemon=True).start()
            return True
        return False

    def stop(self):
        self.running = False

    def _loop(self):
        while self.running:
            try:
                static_data = SPageFileStatic.from_buffer_copy(self.shm_static.read(ctypes.sizeof(SPageFileStatic)))
                self.shm_static.seek(0)
                
                track_name = static_data.track
                if track_name and track_name != self.current_track:
                    self.current_track = track_name
                    if self.track_parser_callback:
                        self.track_parser_callback(self.current_track)

                physics_data = SPageFilePhysics.from_buffer_copy(self.shm_physics.read(ctypes.sizeof(SPageFilePhysics)))
                self.shm_physics.seek(0)
                
                graphics_data = SPageFileGraphics.from_buffer_copy(self.shm_graphics.read(ctypes.sizeof(SPageFileGraphics)))
                self.shm_graphics.seek(0)

                self.telemetry_data = {
                    "speed": physics_data.speedKmh,
                    "heading": physics_data.heading,
                    "x": graphics_data.carCoordinates[0],
                    "z": graphics_data.carCoordinates[2]
                }
            except Exception:
                pass
                
            time.sleep(1/60) # 60Hz update rate

    def get_latest_data(self):
        return self.telemetry_data
