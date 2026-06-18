from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.external_references import (  # noqa: E402
    ExternalReferenceError,
    ExternalReferenceRepository,
    FastF1ReferenceProvider,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import an Interlagos FastF1 reference lap for assisted analysis.")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--event", default="Brazil")
    parser.add_argument("--session", default="Q")
    parser.add_argument("--driver", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repository = ExternalReferenceRepository(REPO_ROOT)
    provider = FastF1ReferenceProvider(REPO_ROOT, repository)
    try:
        reference = provider.import_reference(
            year=args.year,
            event=args.event,
            session=args.session,
            driver=args.driver,
            force=args.force,
        )
    except ExternalReferenceError as exc:
        print(json.dumps({"status": "error", "detail": str(exc)}, indent=2))
        return 1

    print(json.dumps({"status": "success", "reference": reference.to_api(include_samples=False)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
