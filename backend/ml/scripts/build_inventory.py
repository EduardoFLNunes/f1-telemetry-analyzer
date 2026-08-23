"""Varre as gravacoes e escreve o inventario de voltas.

    python -m ml.scripts.build_inventory [--limit N] [--sessions PREFIXO ...]

Roda de dentro de `backend/`, que e a raiz de import do projeto.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ml import config
from ml.data.inventory import save_inventory, scan_sessions, summarise
from ml.data.recordings import list_sessions
from ml.track.geometry import load_geometry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inventario de voltas gravadas")
    parser.add_argument("--limit", type=int, default=None, help="processa so as N primeiras sessoes")
    parser.add_argument("--sessions", nargs="*", default=None, help="prefixos de sessao a incluir")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    started = time.time()
    sessions = list_sessions()
    if args.sessions:
        sessions = [s for s in sessions if any(s.session_id.startswith(p) for p in args.sessions)]
    if args.limit:
        sessions = sessions[: args.limit]

    if not sessions:
        print("nenhuma sessao encontrada", file=sys.stderr)
        return 1

    track = load_geometry()
    print(f"pista: {track.name} — {track.length:.1f} m, grade de {track.step:.1f} m")
    print(f"sessoes: {len(sessions)}")

    inventory = scan_sessions(
        sessions, track=track, progress=None if args.quiet else lambda text: print(text, flush=True)
    )
    path = save_inventory(inventory)
    summary = summarise(inventory)

    print(f"\ninventario -> {path}  ({time.time() - started:.0f}s)")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
