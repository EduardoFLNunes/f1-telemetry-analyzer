from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.assisted_analysis.validation_fixture_factory import (  # noqa: E402
    write_phase14_1_validation_recording,
)


def main() -> int:
    fixture = write_phase14_1_validation_recording(REPO_ROOT)
    payload = {
        "status": "seeded",
        "sessionId": fixture.session_id,
        "sessionDir": str(fixture.session_dir),
        "track": fixture.track_name,
        "referenceLapId": fixture.reference_lap_id,
        "targetLapId": fixture.target_lap_id,
        "invalidLapId": fixture.invalid_lap_id,
        "validations": fixture.validations,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
