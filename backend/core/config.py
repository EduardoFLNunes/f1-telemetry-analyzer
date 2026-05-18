"""
Configurações do F1 Telemetry Analyzer v2.0
"""

import os

AUTO_LOAD_EXAMPLE_DATA = os.getenv("TELEMETRY_SOURCE", "auto").lower() == "replay"

EXAMPLE_TRACK_CSV = "data/SaoPaulo.csv"
EXAMPLE_TELEMETRY_CSV = "data/example_telemetry.csv"

UDP_CAPTURE_DIR = "data/telemetry_sessions"
FASTF1_CACHE_DIR = "data/fastf1_cache"

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "*"
]

LOG_LEVEL = "INFO"

GRIP_FACTOR = 1.8
MAX_SPEED_KMH = 340
MIN_SPEED_KMH = 60
MAX_ACCEL_G = 1.5
MAX_BRAKE_G = 4.5
APEX_OFFSET_FACTOR = 0.3

MIN_POINTS_PER_LAP = 10
MIN_LAP_TIME = 30
MAX_LAP_TIME = 300
