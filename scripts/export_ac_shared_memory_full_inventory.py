from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.debug.ac_shared_memory_full_inventory import write_ac_shared_memory_inventory_files


def main() -> None:
    output_dir = REPO_ROOT / "data" / "debug"
    paths = write_ac_shared_memory_inventory_files(output_dir)
    for kind, path in paths.items():
        print(f"{kind}: {path}")


if __name__ == "__main__":
    main()
