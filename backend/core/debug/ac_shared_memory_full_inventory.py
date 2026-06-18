"""Read-only Assetto Corsa shared memory inventory helpers.

This module documents the raw ctypes structures implemented in the backend and
optionally captures a current mmap snapshot. It does not mutate telemetry state.
"""

from __future__ import annotations

import csv
import ctypes
import json
import mmap
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import reduce
from operator import mul
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..assetto_adapter import (
    SPageFileGraphics as AdapterGraphics,
    SPageFilePhysics as AdapterPhysics,
    SPageFileStatic as AdapterStatic,
)
from ..assetto_shared_memory_gate import shared_memory_gate_status

try:
    from .. import ac_shared_memory as legacy_shared_memory
except Exception:  # pragma: no cover - optional legacy module
    legacy_shared_memory = None


@dataclass(frozen=True)
class StructureSource:
    structure: str
    ctypes_class: type
    module: str
    mmap_name: str
    primary: bool


PRIMARY_SOURCES: Tuple[StructureSource, ...] = (
    StructureSource("Physics", AdapterPhysics, "backend/core/assetto_adapter.py", "acpmf_physics", True),
    StructureSource("Graphics", AdapterGraphics, "backend/core/assetto_adapter.py", "acpmf_graphics", True),
    StructureSource("Static", AdapterStatic, "backend/core/assetto_adapter.py", "acpmf_static", True),
)


def _legacy_sources() -> Tuple[StructureSource, ...]:
    if not legacy_shared_memory:
        return ()
    sources: List[StructureSource] = []
    for structure, class_name, mmap_name in (
        ("Physics", "SPageFilePhysics", "acpmf_physics"),
        ("Graphics", "SPageFileGraphics", "acpmf_graphics"),
        ("Static", "SPageFileStatic", "acpmf_static"),
    ):
        cls = getattr(legacy_shared_memory, class_name, None)
        if cls is not None and hasattr(cls, "_fields_"):
            sources.append(
                StructureSource(structure, cls, "backend/core/ac_shared_memory.py", mmap_name, False)
            )
    return tuple(sources)


NORMALIZED_SOURCES: Dict[Tuple[str, str], List[str]] = {
    ("Graphics", "status"): ["status"],
    ("Graphics", "session"): ["session_type"],
    ("Graphics", "carCoordinates"): ["x", "y", "z", "mapPosition"],
    ("Physics", "speedKmh"): ["speed"],
    ("Physics", "gas"): ["throttle"],
    ("Physics", "brake"): ["brake"],
    ("Physics", "steerAngle"): ["steer", "steering"],
    ("Physics", "gear"): ["gear"],
    ("Physics", "rpms"): ["rpm"],
    ("Graphics", "completedLaps"): ["lap_number", "lap"],
    ("Graphics", "iCurrentTime"): ["lap_time", "sessionTime"],
    ("Graphics", "normalizedCarPosition"): ["lap_dist_pct", "normalizedSplinePosition"],
    ("Physics", "heading"): ["heading"],
    ("Physics", "accG"): ["accel_g", "lat_g"],
    ("Physics", "wheelSlip"): ["wheel_slip"],
    ("Static", "carModel"): ["car_model"],
    ("Static", "track"): ["track_name"],
    ("Static", "trackSplineLength"): ["track_length"],
}

USED_BY_BACKEND_FIELDS = set(NORMALIZED_SOURCES)
EXPOSED_BY_API_FIELDS = set(NORMALIZED_SOURCES)

WHEEL_NOTE = "Wheel arrays are usually ordered LF, RF, LR, RR in AC shared memory."

DESCRIPTIONS: Dict[str, str] = {
    "packetId": "Incrementing packet counter for the shared memory page.",
    "gas": "Throttle input.",
    "brake": "Brake input.",
    "fuel": "Current fuel amount.",
    "gear": "Raw AC gear value: 0=reverse, 1=neutral, 2=first gear.",
    "rpms": "Engine speed.",
    "steerAngle": "Steering input/angle reported by AC.",
    "speedKmh": "Current car speed in km/h.",
    "velocity": "Car velocity vector.",
    "accG": "Acceleration vector in G.",
    "wheelSlip": f"Wheel slip per wheel. {WHEEL_NOTE}",
    "wheelLoad": f"Wheel load per wheel. {WHEEL_NOTE}",
    "wheelsPressure": f"Tyre pressure per wheel. {WHEEL_NOTE}",
    "wheelAngularSpeed": f"Wheel angular speed per wheel. {WHEEL_NOTE}",
    "tyreWear": f"Tyre wear per wheel. {WHEEL_NOTE}",
    "tyreDirtyLevel": f"Tyre dirt level per wheel. {WHEEL_NOTE}",
    "tyreCoreTemp": f"Tyre core temperature per wheel. {WHEEL_NOTE}",
    "tyreCoreTemperature": f"Legacy tyre core temperature field per wheel. {WHEEL_NOTE}",
    "camberRAD": f"Camber angle in radians per wheel. {WHEEL_NOTE}",
    "suspensionTravel": f"Suspension travel per wheel. {WHEEL_NOTE}",
    "drs": "DRS status/input.",
    "tc": "Traction control value.",
    "heading": "Car yaw/heading angle.",
    "pitch": "Car pitch angle.",
    "roll": "Car roll angle.",
    "cgHeight": "Center-of-gravity height.",
    "carDamage": "Car damage values by component.",
    "numberOfTyresOut": "Number of tyres outside track limits.",
    "pitLimiterOn": "Pit limiter enabled state.",
    "abs": "ABS value or setting.",
    "kersCharge": "KERS charge level.",
    "kersInput": "KERS deployment input.",
    "autoShifterOn": "Automatic shifting enabled state.",
    "rideHeight": "Front/rear ride height.",
    "turboBoost": "Turbo boost pressure/level.",
    "ballast": "Ballast setting.",
    "airDensity": "Air density.",
    "airTemp": "Ambient air temperature.",
    "roadTemp": "Track surface temperature.",
    "localAngularVel": "Local angular velocity vector.",
    "finalFF": "Final force feedback signal.",
    "performanceMeter": "AC performance meter value.",
    "engineBrake": "Engine brake setting.",
    "ersRecoveryLevel": "ERS recovery level.",
    "ersPowerLevel": "ERS power level.",
    "ersHeatCharging": "ERS heat charging state.",
    "ersIsBatteryCharging": "ERS battery charging state.",
    "kersCurrentVK": "Current KERS voltage/energy related value.",
    "visualTyreDamage": f"Visual tyre damage per wheel. {WHEEL_NOTE}",
    "elecSystemsOverlap": "Electrical systems overlap value.",
    "ersFuelDiff": "ERS fuel delta/difference value.",
    "diffPa": "Differential preload/setting.",
    "tyreTempI": f"Inner tyre temperature per wheel. {WHEEL_NOTE}",
    "tyreTempM": f"Middle tyre temperature per wheel. {WHEEL_NOTE}",
    "tyreTempO": f"Outer tyre temperature per wheel. {WHEEL_NOTE}",
    "isAIControlled": "Whether the car is AI controlled.",
    "tyreContactPoint": f"Tyre contact point vector per wheel. {WHEEL_NOTE}",
    "tyreContactNormal": f"Tyre contact normal vector per wheel. {WHEEL_NOTE}",
    "tyreContactHeading": f"Tyre contact heading vector per wheel. {WHEEL_NOTE}",
    "brakeTemp": f"Brake temperature per wheel. {WHEEL_NOTE}",
    "clutch": "Clutch input.",
    "tyreTempI2": f"Secondary inner tyre temperature per wheel. {WHEEL_NOTE}",
    "tyreTempM2": f"Secondary middle tyre temperature per wheel. {WHEEL_NOTE}",
    "tyreTempO2": f"Secondary outer tyre temperature per wheel. {WHEEL_NOTE}",
    "isShadowTrack": "Shadow track state.",
    "iDiffPriority": "Differential priority setting.",
    "tyreWorkTemp": f"Tyre working temperature per wheel. {WHEEL_NOTE}",
    "flag": "Current flag/status value.",
    "iCurrentMaxGear": "Current maximum gear.",
    "iCurrentTyreSet": "Current tyre set index.",
    "iMguKMaxTorque": "MGU-K maximum torque.",
    "iMguHMaxTorque": "MGU-H maximum torque.",
    "gearRatio": "Gear ratio table.",
    "iDiffIn": "Differential input setting.",
    "iDiffOut": "Differential output setting.",
    "status": "Simulation status.",
    "session": "Session type.",
    "currentTime": "Current lap time as text.",
    "lastTime": "Last lap time as text.",
    "bestTime": "Best lap time as text.",
    "split": "Current split delta/time as text.",
    "completedLaps": "Completed lap count.",
    "position": "Race/session position.",
    "iCurrentTime": "Current lap time in milliseconds.",
    "iLastTime": "Last lap time in milliseconds.",
    "iBestTime": "Best lap time in milliseconds.",
    "sessionTimeLeft": "Session time remaining.",
    "distanceTraveled": "Distance traveled in session.",
    "isInPit": "Whether the car is in pit.",
    "currentSectorIndex": "Current sector index.",
    "lastSectorTime": "Last sector time.",
    "numberOfLaps": "Configured session lap count.",
    "tyreCompound": "Current tyre compound name.",
    "replayTimeMultiplier": "Replay playback speed multiplier.",
    "normalizedCarPosition": "Normalized car position along AC track spline.",
    "activeCars": "Legacy implemented active car count field.",
    "carCoordinates": "Current car world coordinates.",
    "penaltyTime": "Penalty time.",
    "idealLineOn": "Ideal line enabled state.",
    "isInPitLane": "Whether the car is in pit lane.",
    "surfaceGrip": "Current surface grip multiplier/value.",
    "mandatoryPitDone": "Mandatory pit stop completed state.",
    "windSpeed": "Wind speed.",
    "windDirection": "Wind direction.",
    "isSetupMenuVisible": "Setup menu visibility state.",
    "mainDisplayIndex": "Main display/MFD page index.",
    "secondaryDisplayIndex": "Secondary display/MFD page index.",
    "tcCut": "Traction control cut setting.",
    "engineMap": "Engine map setting.",
    "fuelUsedLaps": "Fuel usage measured in laps.",
    "rainIntensity": "Current rain intensity.",
    "rainIntensityIn10min": "Predicted rain intensity in 10 minutes.",
    "rainIntensityIn30min": "Predicted rain intensity in 30 minutes.",
    "currentTyreSet": "Current tyre set index.",
    "strategyTyreSet": "Strategy tyre set index.",
    "gapAhead": "Gap to car ahead.",
    "gapBehind": "Gap to car behind.",
    "smVersion": "Shared memory version.",
    "acVersion": "Assetto Corsa version.",
    "numberOfSessions": "Number of sessions in event.",
    "numCars": "Number of cars in session.",
    "carModel": "Loaded car model.",
    "track": "Loaded track name.",
    "playerName": "Player first name.",
    "playerSurname": "Player surname.",
    "playerNick": "Player nickname.",
    "sectorCount": "Number of track sectors.",
    "maxTorque": "Car maximum torque.",
    "maxPower": "Car maximum power.",
    "maxRpm": "Car maximum RPM.",
    "maxFuel": "Maximum fuel capacity.",
    "suspensionMaxTravel": f"Maximum suspension travel per wheel. {WHEEL_NOTE}",
    "tyreRadius": f"Tyre radius per wheel. {WHEEL_NOTE}",
    "maxTurboBoost": "Maximum turbo boost.",
    "isPenaltyEnabled": "Penalty system enabled state.",
    "aidFuelRate": "Fuel consumption assist/rate.",
    "aidTireRate": "Tyre wear assist/rate.",
    "aidMechanicalDamage": "Mechanical damage assist/rate.",
    "aidAllowTyreBlankets": "Tyre blankets allowed aid flag.",
    "aidStability": "Stability assist level.",
    "aidAutoClutch": "Auto clutch assist flag.",
    "aidAutoBlip": "Auto blip assist flag.",
    "hasDRS": "Whether the car supports DRS.",
    "hasERS": "Whether the car supports ERS.",
    "hasKERS": "Whether the car supports KERS.",
    "kersMaxJ": "Maximum KERS energy.",
    "engineBrakeSettingsCount": "Number of engine-brake settings.",
    "ersPowerControllerCount": "Number of ERS power controller settings.",
    "trackSplineLength": "Track spline length reported by AC.",
    "trackConfiguration": "Track layout/configuration.",
    "ersMaxJ": "Maximum ERS energy.",
    "isTimedRace": "Whether race is timed.",
    "hasExtraLap": "Whether session has extra lap.",
    "carSkin": "Loaded car skin.",
    "reversedGridPositions": "Reversed grid positions setting.",
    "PitWindowStart": "Pit window start lap/time.",
    "PitWindowEnd": "Pit window end lap/time.",
    "isOnline": "Online session flag.",
}


def _array_shape(ctype: Any) -> Tuple[int, ...]:
    shape: List[int] = []
    base = ctype
    while isinstance(base, type) and issubclass(base, ctypes.Array):
        shape.append(int(base._length_))
        base = base._type_
    return tuple(shape)


def _base_type(ctype: Any) -> Any:
    base = ctype
    while isinstance(base, type) and issubclass(base, ctypes.Array):
        base = base._type_
    return base


def _type_name(ctype: Any) -> str:
    return getattr(ctype, "__name__", str(ctype))


def _shape_text(shape: Iterable[int]) -> str:
    shape = tuple(shape)
    if not shape:
        return "1"
    return " x ".join(str(item) for item in shape)


def _plain_value(value: Any) -> Any:
    if isinstance(value, ctypes.Array):
        if getattr(value, "_type_", None) is ctypes.c_wchar:
            return str(value).rstrip("\x00")
        return [_plain_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").rstrip("\x00")
    if isinstance(value, str):
        return value.rstrip("\x00")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _unit_for(structure: str, field_name: str, base_type_name: str) -> str:
    name = field_name.lower()
    if base_type_name in {"c_wchar", "c_wchar_p"}:
        return "text"
    if name in {"gas", "brake", "clutch"}:
        return "0-1"
    if "wheelload" in name:
        return "N"
    if "angularspeed" in name:
        return "rad/s"
    if "slip" in name:
        return "ratio"
    if "speedkmh" in name:
        return "km/h"
    if name == "velocity":
        return "m/s"
    if name in {"accg"}:
        return "g"
    if "rpm" in name:
        return "rpm"
    if "time" in name and not name.endswith("multiplier"):
        return "ms/text" if name.startswith("i") or "sector" in name else "s/text"
    if "normalized" in name:
        return "0-1"
    if any(token in name for token in ("coordinate", "distance", "height", "travel", "radius", "point", "length")):
        return "m"
    if "temp" in name:
        return "deg C"
    if "pressure" in name:
        return "psi"
    if any(token in name for token in ("heading", "pitch", "roll", "camber", "angle")):
        return "rad"
    if any(token in name for token in ("grip", "wear", "dirty", "damage", "tc", "abs", "drs")):
        return "level/ratio"
    if "fuel" in name:
        return "L/laps"
    if "winddirection" in name:
        return "rad/deg"
    if "windspeed" in name:
        return "m/s"
    if "torque" in name:
        return "Nm"
    if "power" in name:
        return "W"
    if any(token in name for token in ("ers", "kers")) and any(token in name for token in ("j", "charge")):
        return "J/level"
    if base_type_name in {"c_int", "c_long"}:
        return "integer/enum"
    return "unknown"


def _category_for(structure: str, field_name: str) -> str:
    name = field_name.lower()
    if name in {"carcoordinates", "normalizedcarposition"}:
        return "car_position"
    if any(token in name for token in ("heading", "pitch", "roll")):
        return "car_orientation"
    if any(token in name for token in ("tyre", "tire", "wheel", "camber")):
        return "tyres"
    if any(token in name for token in ("speed", "velocity", "accg", "angularvel", "performancemeter")):
        return "car_speed"
    if name in {"drs", "tc", "abs"}:
        return "assist_systems"
    if any(token in name for token in ("gas", "steer", "clutch", "autoshifter", "mainDisplay".lower(), "secondaryDisplay".lower())):
        return "car_controls"
    if any(token in name for token in ("rpm", "turbo", "enginemap", "enginebrake", "maxtorque", "maxpower", "maxrpm", "airdensity")):
        return "engine"
    if any(token in name for token in ("gear", "diff", "ratio", "mgu")):
        return "drivetrain"
    if any(token in name for token in ("suspension", "rideheight", "cgheight")):
        return "suspension"
    if "brake" in name or name == "abs":
        return "brakes"
    if "damage" in name:
        return "damage"
    if "fuel" in name:
        return "fuel"
    if any(token in name for token in ("time", "lap", "split", "sector", "distancetraveled")):
        return "lap_timing"
    if any(token in name for token in ("session", "status", "numberoflaps", "completedlaps")):
        return "session"
    if any(token in name for token in ("track", "surfacegrip")):
        return "track"
    if any(token in name for token in ("airtemp", "roadtemp", "wind", "rain")):
        return "weather"
    if "flag" in name:
        return "flags"
    if any(token in name for token in ("numcars", "activecars", "gapahead", "gapbehind", "isonline", "player", "position")):
        return "multiplayer"
    if any(token in name for token in ("pit", "pitwindow", "mandatorypit")):
        return "pit"
    if any(token in name for token in ("aid", "hasdrs", "hasers", "haskers", "tc", "isai", "idealline", "setupmenu")):
        return "assist_systems"
    if structure == "Static":
        return "session"
    return "unknown"


def _update_frequency(structure: str) -> str:
    if structure == "Physics":
        return "high_frequency_physics_tick"
    if structure == "Graphics":
        return "per_frame_or_session_update"
    if structure == "Static":
        return "session_load_or_car_track_change"
    return "unknown"


def _source_value(struct_source: StructureSource) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    try:
        with mmap.mmap(
            -1,
            ctypes.sizeof(struct_source.ctypes_class),
            tagname=struct_source.mmap_name,
            access=mmap.ACCESS_READ,
        ) as mapping:
            mapping.seek(0)
            data = struct_source.ctypes_class.from_buffer_copy(
                mapping[: ctypes.sizeof(struct_source.ctypes_class)]
            )
            return True, {field: _plain_value(getattr(data, field)) for field, _ in data._fields_}, None
    except Exception as exc:
        return False, None, str(exc)


def _collect_current_values(sources: Iterable[StructureSource]) -> Dict[str, Any]:
    by_source: Dict[str, Dict[str, Any]] = {}
    connection: Dict[str, Dict[str, Any]] = {}
    for source in sources:
        source_key = source.module
        connected, values, error = _source_value(source)
        by_source.setdefault(source_key, {})[source.structure] = values or {}
        connection[f"{source.structure}:{source.module}"] = {
            "connected": connected,
            "error": error,
            "size_bytes": ctypes.sizeof(source.ctypes_class),
            "primary": source.primary,
        }
    return {"by_source": by_source, "connection": connection}


def _blocked_current_values(sources: Iterable[StructureSource], gate_status: Dict[str, Any]) -> Dict[str, Any]:
    connection: Dict[str, Dict[str, Any]] = {}
    reason = gate_status.get("reason") or "shared_memory_gate_blocked"
    for source in sources:
        connection[f"{source.structure}:{source.module}"] = {
            "connected": False,
            "error": reason,
            "size_bytes": ctypes.sizeof(source.ctypes_class),
            "primary": source.primary,
        }
    return {"by_source": {}, "connection": connection}


def _field_descriptor(source: StructureSource, index: int, field_name: str, field_type: Any) -> Dict[str, Any]:
    shape = _array_shape(field_type)
    base_type = _base_type(field_type)
    descriptor = getattr(source.ctypes_class, field_name)
    base_type_name = _type_name(base_type)
    return {
        "structure": source.structure,
        "field_name": field_name,
        "field_index": index,
        "data_type": base_type_name,
        "array_length": _shape_text(shape),
        "element_count": int(reduce(mul, shape, 1)),
        "offset_bytes": int(descriptor.offset),
        "size_bytes": int(descriptor.size),
        "unit": _unit_for(source.structure, field_name, base_type_name),
        "category": _category_for(source.structure, field_name),
        "description": DESCRIPTIONS.get(field_name, "needs investigation"),
        "update_frequency": _update_frequency(source.structure),
        "used_by_backend": (source.structure, field_name) in USED_BY_BACKEND_FIELDS,
        "exposed_by_api": (source.structure, field_name) in EXPOSED_BY_API_FIELDS,
        "api_fields": NORMALIZED_SOURCES.get((source.structure, field_name), []),
        "implemented_in": [source.module],
        "primary_source": source.module if source.primary else None,
        "notes": "primary ctypes struct" if source.primary else "additional implemented ctypes struct",
    }


def _merge_field(existing: Dict[str, Any], source: StructureSource, field_type: Any) -> None:
    existing["implemented_in"].append(source.module)
    base_type_name = _type_name(_base_type(field_type))
    shape = _shape_text(_array_shape(field_type))
    if existing["data_type"] != base_type_name or existing["array_length"] != shape:
        existing["notes"] = (
            f"{existing['notes']}; also implemented in {source.module} as {base_type_name}[{shape}]"
        )
    else:
        existing["notes"] = f"{existing['notes']}; also implemented in {source.module}"


def _all_field_metadata(sources: Iterable[StructureSource], current_values: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields: Dict[Tuple[str, str], Dict[str, Any]] = {}
    primary_fields_by_structure: Dict[str, List[Dict[str, Any]]] = {}
    for source in sources:
        for index, (field_name, field_type) in enumerate(source.ctypes_class._fields_, start=1):
            key = (source.structure, field_name)
            if key not in fields or source.primary:
                fields[key] = _field_descriptor(source, index, field_name, field_type)
            else:
                _merge_field(fields[key], source, field_type)
            if source.primary:
                primary_fields_by_structure.setdefault(source.structure, []).append(fields[key])

    for field in fields.values():
        overlapping_primary = [
            primary
            for primary in primary_fields_by_structure.get(field["structure"], [])
            if primary["field_name"] != field["field_name"]
            and field["offset_bytes"] < primary["offset_bytes"] + primary["size_bytes"]
            and field["offset_bytes"] + field["size_bytes"] > primary["offset_bytes"]
        ]
        conflicting_layout = False
        if field["primary_source"] is None and overlapping_primary:
            exact_alias = next(
                (
                    primary
                    for primary in overlapping_primary
                    if primary["offset_bytes"] == field["offset_bytes"]
                    and primary["size_bytes"] == field["size_bytes"]
                    and primary["data_type"] == field["data_type"]
                    and primary["array_length"] == field["array_length"]
                ),
                None,
            )
            if exact_alias:
                field["notes"] = (
                    f"{field['notes']}; shares the same offset/layout as primary field "
                    f"{exact_alias['field_name']}"
                )
            else:
                conflicting_layout = True
                overlaps = ", ".join(primary["field_name"] for primary in overlapping_primary)
                field["notes"] = (
                    f"{field['notes']}; legacy-only field overlaps primary layout field(s) "
                    f"{overlaps}; current value marked unknown to avoid reporting a misaligned read"
                )

        current_value = None
        if not conflicting_layout:
            for module in field["implemented_in"]:
                value = current_values.get("by_source", {}).get(module, {}).get(field["structure"], {}).get(
                    field["field_name"]
                )
                if value is not None:
                    current_value = value
                    break
        field["current_value"] = current_value
        field["implemented_in"] = sorted(set(field["implemented_in"]))

    return sorted(fields.values(), key=lambda item: (("Physics", "Graphics", "Static").index(item["structure"]), item["field_index"], item["field_name"]))


def _raw_primary_values(current_values: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    primary: Dict[str, Dict[str, Any]] = {}
    primary_module = "backend/core/assetto_adapter.py"
    source_values = current_values.get("by_source", {}).get(primary_module, {})
    for structure in ("Physics", "Graphics", "Static"):
        primary[structure] = source_values.get(structure, {})
    return primary


def _snapshot_summary(raw: Dict[str, Dict[str, Any]], generated_at: str, connection: Dict[str, Any]) -> Dict[str, Any]:
    physics = raw.get("Physics", {})
    graphics = raw.get("Graphics", {})
    static = raw.get("Static", {})
    world_position = graphics.get("carCoordinates")
    map_position = None
    if isinstance(world_position, list) and len(world_position) >= 3:
        map_position = {"x": world_position[0], "y": -world_position[2]}
    return {
        "timestamp": generated_at,
        "connection_status": all(item.get("connected") for item in connection.values() if item.get("primary")),
        "connection": connection,
        "track_name": static.get("track"),
        "car_name": static.get("carModel"),
        "session_current": graphics.get("session"),
        "session_status": graphics.get("status"),
        "current_lap": graphics.get("completedLaps"),
        "current_sector": graphics.get("currentSectorIndex"),
        "current_position": world_position,
        "map_position": map_position,
        "speed_kmh": physics.get("speedKmh"),
        "gear": physics.get("gear"),
        "rpm": physics.get("rpms"),
        "tyres": {
            key: physics.get(key)
            for key in (
                "wheelSlip",
                "wheelLoad",
                "wheelsPressure",
                "wheelAngularSpeed",
                "tyreWear",
                "tyreDirtyLevel",
                "tyreCoreTemp",
                "tyreTempI",
                "tyreTempM",
                "tyreTempO",
                "brakeTemp",
            )
            if key in physics
        },
        "fuel": {
            "fuel": physics.get("fuel"),
            "fuelUsedLaps": graphics.get("fuelUsedLaps"),
            "maxFuel": static.get("maxFuel"),
        },
        "damage": {
            "carDamage": physics.get("carDamage"),
            "visualTyreDamage": physics.get("visualTyreDamage"),
        },
        "weather": {
            "airTemp": physics.get("airTemp"),
            "roadTemp": physics.get("roadTemp"),
            "airDensity": physics.get("airDensity"),
            "windSpeed": graphics.get("windSpeed"),
            "windDirection": graphics.get("windDirection"),
            "rainIntensity": graphics.get("rainIntensity"),
            "rainIntensityIn10min": graphics.get("rainIntensityIn10min"),
            "rainIntensityIn30min": graphics.get("rainIntensityIn30min"),
        },
        "flags": {
            "physics_flag": physics.get("flag"),
            "graphics_flag": graphics.get("flag"),
            "isInPit": graphics.get("isInPit"),
            "isInPitLane": graphics.get("isInPitLane"),
            "pitLimiterOn": physics.get("pitLimiterOn"),
        },
        "all_values": raw,
    }


def build_ac_shared_memory_full_inventory() -> Dict[str, Any]:
    """Return a complete read-only inventory of implemented AC shared memory fields."""
    generated_at = datetime.now(timezone.utc).isoformat()
    sources = PRIMARY_SOURCES + _legacy_sources()
    gate_status = shared_memory_gate_status()
    current_values = (
        _collect_current_values(sources)
        if gate_status.get("allowed", True)
        else _blocked_current_values(sources, gate_status)
    )
    fields = _all_field_metadata(sources, current_values)
    raw = _raw_primary_values(current_values)
    categories: Dict[str, Dict[str, Any]] = {}
    for field in fields:
        category = field["category"]
        bucket = categories.setdefault(category, {"field_count": 0, "fields": []})
        bucket["field_count"] += 1
        bucket["fields"].append(f"{field['structure']}.{field['field_name']}")

    structures = {}
    for structure in ("Physics", "Graphics", "Static"):
        structure_fields = [field for field in fields if field["structure"] == structure]
        structures[structure] = {
            "field_count": len(structure_fields),
            "primary_module": "backend/core/assetto_adapter.py",
            "implemented_modules": sorted(
                {module for field in structure_fields for module in field["implemented_in"]}
            ),
        }

    return {
        "generated_at": generated_at,
        "source": "assetto_corsa_shared_memory",
        "mode": "read_only_debug_inventory",
        "shared_memory_gate": gate_status,
        "structures": structures,
        "fields": fields,
        "field_categories": dict(sorted(categories.items())),
        "not_yet_used_by_backend": [
            field for field in fields if not field["used_by_backend"]
        ],
        "current_snapshot": _snapshot_summary(raw, generated_at, current_values["connection"]),
    }


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def write_ac_shared_memory_inventory_files(output_dir: Path) -> Dict[str, str]:
    """Write JSON and CSV debug exports. The XLSX export is built separately."""
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory = build_ac_shared_memory_full_inventory()
    json_path = output_dir / "ac_shared_memory_full_inventory.json"
    csv_path = output_dir / "ac_shared_memory_full_inventory.csv"

    json_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_columns = [
        "structure",
        "field_name",
        "data_type",
        "array_length",
        "current_value",
        "unit",
        "category",
        "description",
        "update_frequency",
        "used_by_backend",
        "exposed_by_api",
        "notes",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_columns)
        writer.writeheader()
        for field in inventory["fields"]:
            writer.writerow({column: _json_cell(field.get(column)) for column in csv_columns})

    return {"json": str(json_path), "csv": str(csv_path)}
