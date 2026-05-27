import os
import platform
import sys
import time

try:
    import ac
    import acsys
except Exception:
    ac = None
    acsys = None


APP_NAME = "Opponents Exporter"
UDP_HOST = "127.0.0.1"
UDP_PORT = 8765
DEFAULT_PLAYER_CAR_ID = 0
DEFAULT_SEND_HZ = 20.0
DEBUG_LOG_INTERVAL_SECONDS = 2.0
ERROR_LOG_INTERVAL_SECONDS = 5.0

_app_window = None
_labels = {}
_socket = None
_socket_module_unavailable = False
_winsock_socket = None
_winsock_addr = None
_winsock_sender_ready = False
_ctypes_path_logged = False
_elapsed = 0.0
_last_error_log = 0.0
_last_debug_log = 0.0
_last_player_log = 0.0
_last_udp_error_log = 0.0
_last_udp_error = None
_last_sent_timestamp = None
_udp_ok = False
_read_error_log = {}
_snapshot_debug = {
    "cars_detected": 0,
    "player_car_id": DEFAULT_PLAYER_CAR_ID,
    "iterated_ids": [],
    "sent_ids": [],
    "fields_ok": {},
    "fields_failed": {},
}


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default


def _env_bool(name, default):
    try:
        value = os.environ.get(name)
        if value is None:
            return default
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return default


SEND_HZ = _env_float("AC_OPPONENTS_SEND_HZ", DEFAULT_SEND_HZ)
DEBUG_ENABLED = _env_bool("AC_OPPONENTS_DEBUG", True)


def _log(message):
    text = "[%s] %s" % (APP_NAME, message)
    try:
        ac.console(text)
    except Exception:
        pass
    try:
        ac.log(text)
    except Exception:
        pass


def _safe_call(fn, *args, **kwargs):
    error_context = kwargs.pop("error_context", None)
    try:
        return fn(*args)
    except Exception as exc:
        if error_context:
            _log_read_error(error_context[0], error_context[1], exc)
        return None


def _app_base_dir():
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _ctypes_candidate_dirs():
    base_dir = _app_base_dir()
    arch_dir = "stdlib64" if platform.architecture()[0] == "64bit" else "stdlib"
    return [
        os.path.join(base_dir, arch_dir),
        os.path.join(base_dir, "stdlib64"),
        os.path.join(base_dir, "stdlib"),
        os.path.join(os.path.dirname(base_dir), "SimHub", arch_dir),
        os.path.join(os.path.dirname(base_dir), "SimHub", "stdlib64"),
        os.path.join(os.path.dirname(base_dir), "SimHub", "stdlib"),
    ]


def _prepare_ctypes_path():
    global _ctypes_path_logged

    candidate_dirs = _ctypes_candidate_dirs()
    added = []
    for candidate in candidate_dirs:
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
            os.environ["PATH"] = os.environ.get("PATH", "") + ";" + candidate
            added.append(candidate)

    if DEBUG_ENABLED and not _ctypes_path_logged:
        _ctypes_path_logged = True
        status = []
        for candidate in candidate_dirs:
            status.append("%s=%s" % (candidate, "yes" if os.path.isdir(candidate) else "no"))
        _log("ctypes search dirs: %s" % " | ".join(status))
        if added:
            _log("ctypes path added: %s" % " | ".join(added))


def _ctypes_candidate_files():
    files = []
    for candidate in _ctypes_candidate_dirs():
        files.append(os.path.join(candidate, "_ctypes.pyd"))
    return files


def _import_ctypes():
    _prepare_ctypes_path()
    try:
        import ctypes

        return ctypes
    except Exception as first_exc:
        first_error = first_exc

    try:
        if "_ctypes" in sys.modules:
            del sys.modules["_ctypes"]
    except Exception:
        pass

    try:
        import imp

        for candidate in _ctypes_candidate_files():
            if not os.path.isfile(candidate):
                continue
            try:
                imp.load_dynamic("_ctypes", candidate)
                _log("loaded _ctypes directly from %s" % candidate)
                break
            except Exception as exc:
                _log("direct _ctypes load failed from %s: %s" % (candidate, exc))

        import ctypes

        return ctypes
    except Exception as second_exc:
        raise ImportError(
            "ctypes unavailable; first=%s; second=%s" % (first_error, second_exc)
        )


def _socket_instance():
    global _socket, _socket_module_unavailable
    if _socket is None:
        try:
            import socket

            _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception:
            _socket_module_unavailable = True
            raise
    return _socket


def _winsock_error(ws2):
    try:
        return int(ws2.WSAGetLastError())
    except Exception:
        return -1


def _winsock_socket_instance():
    global _winsock_socket, _winsock_addr, _winsock_sender_ready

    ctypes = _import_ctypes()

    ws2 = ctypes.WinDLL("Ws2_32.dll")
    socket_type = ctypes.c_uint64 if platform.architecture()[0] == "64bit" else ctypes.c_uint32

    class WSAData(ctypes.Structure):
        _fields_ = [
            ("wVersion", ctypes.c_ushort),
            ("wHighVersion", ctypes.c_ushort),
            ("szDescription", ctypes.c_char * 257),
            ("szSystemStatus", ctypes.c_char * 129),
            ("iMaxSockets", ctypes.c_ushort),
            ("iMaxUdpDg", ctypes.c_ushort),
            ("lpVendorInfo", ctypes.c_char_p),
        ]

    class SockaddrIn(ctypes.Structure):
        _fields_ = [
            ("sin_family", ctypes.c_ushort),
            ("sin_port", ctypes.c_ushort),
            ("sin_addr", ctypes.c_uint32),
            ("sin_zero", ctypes.c_char * 8),
        ]

    if not _winsock_sender_ready:
        data = WSAData()
        if ws2.WSAStartup(0x0202, ctypes.byref(data)) != 0:
            raise RuntimeError("WSAStartup failed: %s" % _winsock_error(ws2))
        _winsock_sender_ready = True

    if _winsock_socket is None:
        ws2.socket.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        ws2.socket.restype = socket_type
        raw_socket = ws2.socket(2, 2, 17)
        if raw_socket == socket_type(-1).value:
            raise RuntimeError("WinSock socket failed: %s" % _winsock_error(ws2))
        _winsock_socket = raw_socket

    if _winsock_addr is None:
        ws2.htons.argtypes = [ctypes.c_ushort]
        ws2.htons.restype = ctypes.c_ushort
        ws2.inet_addr.argtypes = [ctypes.c_char_p]
        ws2.inet_addr.restype = ctypes.c_uint32

        addr = SockaddrIn()
        addr.sin_family = 2
        addr.sin_port = ws2.htons(UDP_PORT)
        addr.sin_addr = ws2.inet_addr(UDP_HOST.encode("ascii"))
        addr.sin_zero = b"\0" * 8
        _winsock_addr = addr

    return ws2, socket_type, SockaddrIn, _winsock_socket, _winsock_addr


def _winsock_sendto(data):
    ws2, socket_type, sockaddr_type, sock, addr = _winsock_socket_instance()
    ctypes = _import_ctypes()
    ws2.sendto.argtypes = [
        socket_type,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_int,
    ]
    ws2.sendto.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(data)
    sent = ws2.sendto(
        sock,
        ctypes.cast(buffer, ctypes.c_void_p),
        len(data),
        0,
        ctypes.cast(ctypes.pointer(addr), ctypes.c_void_p),
        ctypes.sizeof(addr),
    )
    if sent < 0:
        raise RuntimeError("WinSock sendto failed: %s" % _winsock_error(ws2))
    return sent


def _send_udp_bytes(data):
    global _socket_module_unavailable

    if not _socket_module_unavailable:
        try:
            _socket_instance().sendto(data, (UDP_HOST, UDP_PORT))
            return "socket"
        except Exception as exc:
            _socket_module_unavailable = True
            _set_udp_error("python socket unavailable, trying WinSock: %s" % exc)

    _winsock_sendto(data)
    return "winsock"


def _send_interval_seconds():
    try:
        hz = float(SEND_HZ)
    except Exception:
        hz = DEFAULT_SEND_HZ
    if hz <= 0.0:
        hz = DEFAULT_SEND_HZ
    return 1.0 / hz


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _safe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _append_unique(mapping, car_id, field_name):
    try:
        if not isinstance(car_id, int):
            return
    except Exception:
        return
    values = mapping.setdefault(car_id, [])
    if field_name not in values:
        values.append(field_name)


def _record_field(car_id, field_name, ok):
    if ok:
        _append_unique(_snapshot_debug["fields_ok"], car_id, field_name)
    else:
        _append_unique(_snapshot_debug["fields_failed"], car_id, field_name)


def _reset_snapshot_debug(cars_detected, player_car_id):
    _snapshot_debug["cars_detected"] = cars_detected
    _snapshot_debug["player_car_id"] = player_car_id
    _snapshot_debug["iterated_ids"] = []
    _snapshot_debug["sent_ids"] = []
    _snapshot_debug["fields_ok"] = {}
    _snapshot_debug["fields_failed"] = {}


def _log_read_error(car_id, field_name, exc):
    now = time.time()
    key = "%s:%s" % (car_id, field_name)
    previous = _read_error_log.get(key, 0.0)
    if now - previous >= ERROR_LOG_INTERVAL_SECONDS:
        _read_error_log[key] = now
        _log("read error carId=%s field=%s: %s" % (car_id, field_name, exc))


def _set_udp_error(message):
    global _last_udp_error, _udp_ok, _last_udp_error_log
    _last_udp_error = str(message)
    _udp_ok = False
    now = time.time()
    if now - _last_udp_error_log >= ERROR_LOG_INTERVAL_SECONDS:
        _last_udp_error_log = now
        _log("UDP error: %s" % _last_udp_error)


def _set_udp_ok():
    global _last_udp_error, _udp_ok
    _last_udp_error = None
    _udp_ok = True


def _car_state(car_id, state_name, record=True):
    if ac is None or acsys is None:
        if record:
            _record_field(car_id, state_name, False)
        return None

    state_id = getattr(acsys.CS, state_name, None)
    if state_id is None:
        if record:
            _record_field(car_id, state_name, False)
        _log_read_error(car_id, state_name, "acsys.CS field unavailable")
        return None

    value = _safe_call(ac.getCarState, car_id, state_id, error_context=(car_id, state_name))
    if record:
        _record_field(car_id, state_name, value is not None)
    return value


def _player_car_id():
    global _last_player_log

    for getter_name in ("getPlayerCarId", "getPlayerCarID", "getLocalCarId", "getLocalCarID"):
        getter = getattr(ac, getter_name, None)
        if getter is None:
            continue
        value = _safe_call(getter, error_context=("player", getter_name))
        player_id = _safe_int(value)
        if player_id is not None:
            return player_id

    now = time.time()
    if now - _last_player_log >= ERROR_LOG_INTERVAL_SECONDS:
        _last_player_log = now
        _log("local player carId API unavailable; using Assetto Corsa fallback carId=%s" % DEFAULT_PLAYER_CAR_ID)
    return DEFAULT_PLAYER_CAR_ID


def _driver_name(car_id):
    value = _safe_call(ac.getDriverName, car_id, error_context=(car_id, "DriverName"))
    _record_field(car_id, "DriverName", value is not None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _car_model(car_id):
    value = _safe_call(ac.getCarName, car_id, error_context=(car_id, "CarName"))
    _record_field(car_id, "CarName", value is not None)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _track_name(player_car_id):
    getter = getattr(ac, "getTrackName", None)
    if getter is None:
        return None
    value = _safe_call(getter, player_car_id, error_context=(player_car_id, "TrackName"))
    if value is None:
        value = _safe_call(getter, error_context=("session", "TrackName"))
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _is_connected(car_id):
    getter = getattr(ac, "isConnected", None)
    if getter is None:
        _record_field(car_id, "Connected", False)
        return None
    value = _safe_call(getter, car_id, error_context=(car_id, "Connected"))
    _record_field(car_id, "Connected", value is not None)
    return value


def _status(car_id):
    connected = _is_connected(car_id)
    if connected is False:
        return "disconnected"

    in_pit_fn = getattr(ac, "isCarInPit", None)
    if in_pit_fn is not None:
        in_pit = _safe_call(in_pit_fn, car_id, error_context=(car_id, "InPit"))
        _record_field(car_id, "InPit", in_pit is not None)
        if in_pit:
            return "pit"

    in_pitline_fn = getattr(ac, "isCarInPitline", None)
    if in_pitline_fn is not None:
        in_pitline = _safe_call(in_pitline_fn, car_id, error_context=(car_id, "InPitline"))
        _record_field(car_id, "InPitline", in_pitline is not None)
        if in_pitline:
            return "pitlane"

    return "on_track"


def _world_position(car_id):
    position = _car_state(car_id, "WorldPosition", record=False)
    if position is None:
        _record_field(car_id, "WorldPosition", False)
        return None

    try:
        world = {
            "x": _safe_float(position[0]),
            "y": _safe_float(position[1]),
            "z": _safe_float(position[2]),
        }
    except Exception as exc:
        _record_field(car_id, "WorldPosition", False)
        _log_read_error(car_id, "WorldPosition", exc)
        return None

    valid = world["x"] is not None and world["y"] is not None and world["z"] is not None
    _record_field(car_id, "WorldPosition", valid)
    return world if valid else None


def _lap_time_seconds(car_id):
    value = _safe_float(_car_state(car_id, "LapTime"))
    if value is None:
        return None
    if value > 10000.0:
        return value / 1000.0
    return value


def _build_car(car_id):
    world_position = _world_position(car_id)
    status = _status(car_id)
    if world_position is None:
        _log_read_error(car_id, "WorldPosition", "invalid or missing; car skipped")
        return None

    return {
        "carId": car_id,
        "driverName": _driver_name(car_id),
        "carModel": _car_model(car_id),
        "isPlayer": False,
        "isAI": None,
        "worldPosition": world_position,
        "speedKmh": _safe_float(_car_state(car_id, "SpeedKMH")),
        "yaw": _safe_float(_car_state(car_id, "Heading")),
        "splinePosition": _safe_float(_car_state(car_id, "NormalizedSplinePosition")),
        "lap": _safe_int(_car_state(car_id, "LapCount")),
        "lapTime": _lap_time_seconds(car_id),
        "racePosition": _safe_int(_car_state(car_id, "RacePosition")),
        "status": status,
        "gear": _safe_int(_car_state(car_id, "Gear")),
        "rpm": _safe_int(_car_state(car_id, "RPM")),
        "gas": _safe_float(_car_state(car_id, "Gas")),
        "brake": _safe_float(_car_state(car_id, "Brake")),
        "steer": _safe_float(_car_state(car_id, "Steer")),
    }


def _cars_count():
    getter = getattr(ac, "getCarsCount", None)
    if getter is None:
        return 0
    count = _safe_call(getter, error_context=("session", "CarsCount"))
    try:
        return int(count)
    except Exception:
        return 0


def _send_snapshot():
    global _last_sent_timestamp

    cars = []
    count = _cars_count()
    player_car_id = _player_car_id()
    _reset_snapshot_debug(count, player_car_id)

    for car_id in range(count):
        _snapshot_debug["iterated_ids"].append(car_id)
        if car_id == player_car_id:
            continue
        try:
            car_payload = _build_car(car_id)
            if car_payload is None:
                continue
            cars.append(car_payload)
            _snapshot_debug["sent_ids"].append(car_id)
        except Exception as exc:
            _record_field(car_id, "car_snapshot", False)
            _log_read_error(car_id, "car_snapshot", exc)
            continue

    sent_timestamp = time.time()
    payload = {
        "type": "opponents_snapshot",
        "timestamp": sent_timestamp,
        "sessionTime": None,
        "playerCarId": player_car_id,
        "track": _track_name(player_car_id),
        "cars": cars,
    }
    try:
        import json

        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        _send_udp_bytes(data)
        _last_sent_timestamp = sent_timestamp
        _set_udp_ok()
    except Exception as exc:
        _set_udp_error("socket send: %s" % exc)
        raise
    return count, cars


def _create_label(key, text, y):
    try:
        label = ac.addLabel(_app_window, text)
        ac.setPosition(label, 8, y)
        _labels[key] = label
    except Exception:
        pass


def _set_label(key, text):
    label = _labels.get(key)
    if label is None:
        return
    try:
        ac.setText(label, text)
    except Exception:
        pass


def _last_sent_age_text():
    if _last_sent_timestamp is None:
        return "never"
    return "%d ms ago" % int(max(0.0, time.time() - _last_sent_timestamp) * 1000.0)


def _short_text(text, limit):
    if text is None:
        return ""
    text = str(text).replace("\r", " ").replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _update_labels():
    if not _labels:
        return
    sent_count = len(_snapshot_debug.get("sent_ids", []))
    udp_text = "OK" if _udp_ok else "ERROR"
    if _last_udp_error:
        udp_text = "ERROR"

    _set_label("status", "Opponents Exporter: ON")
    _set_label("cars", "Cars detected: %s" % _snapshot_debug.get("cars_detected", 0))
    _set_label("sending", "Sending: %s cars" % sent_count)
    _set_label("last", "Last sent: %s" % _last_sent_age_text())
    _set_label("udp", "UDP: %s" % udp_text)
    _set_label("error", "Err: %s" % _short_text(_last_udp_error or "-", 54))


def _ids_text(ids):
    if not ids:
        return "none"
    return ",".join([str(car_id) for car_id in ids])


def _log_debug_snapshot():
    if not DEBUG_ENABLED:
        return

    _log(
        "debug detected=%s playerCarId=%s iterated=%s sent=%s udp=%s lastSentTimestamp=%s lastUdpError=%s"
        % (
            _snapshot_debug.get("cars_detected", 0),
            _snapshot_debug.get("player_car_id", DEFAULT_PLAYER_CAR_ID),
            _ids_text(_snapshot_debug.get("iterated_ids", [])),
            _ids_text(_snapshot_debug.get("sent_ids", [])),
            "OK" if _udp_ok else "ERROR",
            _last_sent_timestamp,
            _last_udp_error,
        )
    )

    iterated_ids = _snapshot_debug.get("iterated_ids", [])
    for car_id in iterated_ids:
        if car_id == _snapshot_debug.get("player_car_id"):
            continue
        ok = _snapshot_debug.get("fields_ok", {}).get(car_id, [])
        failed = _snapshot_debug.get("fields_failed", {}).get(car_id, [])
        _log("debug carId=%s fields_ok=%s fields_failed=%s" % (car_id, _ids_text(ok), _ids_text(failed)))


def acMain(ac_version):
    global _app_window
    _app_window = ac.newApp(APP_NAME)
    try:
        ac.setSize(_app_window, 420, 136)
    except Exception:
        pass

    _create_label("status", "Opponents Exporter: ON", 8)
    _create_label("cars", "Cars detected: 0", 26)
    _create_label("sending", "Sending: 0 cars", 44)
    _create_label("last", "Last sent: never", 62)
    _create_label("udp", "UDP: INIT", 80)
    _create_label("error", "Err: -", 98)
    _update_labels()

    _log("started, sending UDP to %s:%s at %.1f Hz" % (UDP_HOST, UDP_PORT, SEND_HZ))
    _log("debug=%s, field diagnostics enabled" % ("ON" if DEBUG_ENABLED else "OFF"))
    _log("player carId detection initialized; fallback is carId=%s" % DEFAULT_PLAYER_CAR_ID)
    return APP_NAME


def acUpdate(delta_t):
    global _elapsed, _last_error_log, _last_debug_log

    _elapsed += delta_t
    _update_labels()
    if _elapsed < _send_interval_seconds():
        return
    _elapsed = 0.0

    try:
        _send_snapshot()
        _update_labels()
        now = time.time()
        if now - _last_debug_log >= DEBUG_LOG_INTERVAL_SECONDS:
            _last_debug_log = now
            _log_debug_snapshot()
    except Exception as exc:
        now = time.time()
        if now - _last_error_log > ERROR_LOG_INTERVAL_SECONDS:
            _last_error_log = now
            _log("send error: %s" % exc)
        _update_labels()


def acShutdown():
    global _socket, _winsock_socket
    if _socket is not None:
        try:
            _socket.close()
        except Exception:
            pass
        _socket = None
    if _winsock_socket is not None:
        try:
            ctypes = _import_ctypes()

            ws2 = ctypes.WinDLL("Ws2_32.dll")
            socket_type = ctypes.c_uint64 if platform.architecture()[0] == "64bit" else ctypes.c_uint32
            ws2.closesocket.argtypes = [socket_type]
            ws2.closesocket(_winsock_socket)
        except Exception:
            pass
        _winsock_socket = None
    _log("stopped")
