"""Where a recorded sample keeps the driver's inputs, across recorder versions.

Three schemas are on disk, and a reader that knows only one of them returns
zeros for the others without raising:

* up to mid-June 2026: inputs at the top of the sample (`sample.throttle`,
  `sample.brake`, `sample.steering`, `sample.gear`, `sample.rpm`), no
  `carPhysics` block -- e.g. `2026-06-14_12-23-46`;
* from late May on: both places, with identical values (measured: maximum
  difference 0.0 over 120 000 samples in four sessions);
* `2026-08-09_*`: only `carPhysics.controls` (`steerAngle` instead of
  `steering`), nothing at the top.

The nested block wins when it carries a value because it is the newer schema;
the top level fills in when it does not. Both callers -- the runtime's assisted
analysis and the offline `ml` pipeline -- read through `driver_inputs`, so the
rule lives in one place.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional

# Canonical name -> (key in `carPhysics.controls`, key at the top of the sample).
INPUT_CHANNELS: Dict[str, tuple] = {
    "throttle": ("throttle", "throttle"),
    "brake": ("brake", "brake"),
    "clutch": ("clutch", "clutch"),
    "steering": ("steerAngle", "steering"),
    "gear": ("gear", "gear"),
    "rpm": ("rpm", "rpm"),
}


def _finite(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _controls(sample: Mapping[str, Any]) -> Mapping[str, Any]:
    physics = sample.get("carPhysics")
    if not isinstance(physics, Mapping):
        return {}
    controls = physics.get("controls")
    return controls if isinstance(controls, Mapping) else {}


def driver_inputs(sample: Mapping[str, Any]) -> Dict[str, Optional[float]]:
    """Throttle, brake, clutch, steering, gear and rpm of one sample.

    `sample` is the inner `sample` object of a `player.jsonl` line (an envelope
    is unwrapped too). A channel no schema carries comes back as None, never
    0.0: "not recorded" and "pedal released" are different facts.
    """
    if isinstance(sample.get("sample"), Mapping):
        sample = sample["sample"]
    controls = _controls(sample)
    out: Dict[str, Optional[float]] = {}
    for name, (nested_key, top_key) in INPUT_CHANNELS.items():
        value = _finite(controls.get(nested_key))
        if value is None:
            value = _finite(sample.get(top_key))
        out[name] = value
    return out


def input_schema(sample: Mapping[str, Any]) -> str:
    """Which schema a sample uses: `nested`, `top_level`, `both` or `none`."""
    if isinstance(sample.get("sample"), Mapping):
        sample = sample["sample"]
    nested = _finite(_controls(sample).get("throttle")) is not None
    top = _finite(sample.get("throttle")) is not None
    if nested and top:
        return "both"
    if nested:
        return "nested"
    if top:
        return "top_level"
    return "none"
