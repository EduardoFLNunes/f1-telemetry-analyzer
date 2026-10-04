"""Grava a geometria oficial onde o coach do app vai procurar por ela (ADR 0013).

    python -m ml.scripts.export_geometry [--track vhe_interlagos] [--runtime-root DIR] [--saida ARQUIVO]

Sai em `data/reference_models/<pista>.geometry.json`, ao lado do modelo do
coach e fora do git.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ml.export.geometry import official_geometry, save
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", default="vhe_interlagos", help="nome da pista no runtime")
    parser.add_argument("--runtime-root", type=Path, default=None)
    parser.add_argument("--saida", type=Path, default=None, help="grava aqui em vez do caminho do runtime")
    args = parser.parse_args(argv)

    track = load_geometry()
    payload = official_geometry(track, build_microsectors(track), args.track)

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from core.assisted_analysis.official_geometry import geometry_path

    runtime_root = args.runtime_root or Path(__file__).resolve().parents[3]
    destination = save(payload, args.saida or geometry_path(runtime_root, args.track))
    print(f"geometria {payload['geometry_id']} | {len(payload['x'])} pontos | {payload['track_length']:.2f} m")
    print(f"-> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
