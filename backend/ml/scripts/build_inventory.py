"""Varre as gravacoes e escreve o inventario de voltas.

    python -m ml.scripts.build_inventory [--limit N] [--sessions PREFIXO ...]
        [--pastas repositorio app_instalado] [--saida DIRETORIO]

Roda de dentro de `backend/`, que e a raiz de import do projeto.

Desde o ADR 0014 le as duas pastas de gravacoes (a do repositorio e a do app
instalado) e grava, ao lado do inventario, `relogio_microsetores.parquet`: o
tempo pelo relogio e o tempo pela velocidade em cada microsetor de cada volta
valida, de onde sai `relogio_suspeito`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from ml import config
from ml.data.inventory import save_inventory, scan_sessions, summarise
from ml.data.recordings import list_all_sessions
from ml.track.geometry import load_geometry

CLOCK_TABLE = "relogio_microsetores.parquet"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Inventario de voltas gravadas")
    parser.add_argument("--limit", type=int, default=None, help="processa so as N primeiras sessoes")
    parser.add_argument("--sessions", nargs="*", default=None, help="prefixos de sessao a incluir")
    parser.add_argument("--pastas", nargs="*", default=None, choices=list(config.RECORDING_FOLDERS),
                        help="pastas de gravacoes (padrao: todas as que existem)")
    parser.add_argument("--saida", type=Path, default=None,
                        help=f"diretorio do inventario (padrao: {config.artifacts_root()})")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    started = time.time()
    roots = config.recordings_roots()
    if args.pastas:
        roots = {label: path for label, path in roots.items() if label in args.pastas}
    for label, path in roots.items():
        print(f"pasta {label}: {path}")
    sessions = list_all_sessions(list(roots.values()))
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

    clock_rows = []

    def keep_clock(lap, aligned, grid, check, row):
        block = check.copy()
        block.insert(0, "lap_id", lap.lap_id)
        clock_rows.append(block)

    inventory = scan_sessions(
        sessions,
        track=track,
        progress=None if args.quiet else lambda text: print(text, flush=True),
        lap_hook=keep_clock,
    )
    path = save_inventory(inventory, args.saida)
    if clock_rows:
        pd.concat(clock_rows, ignore_index=True).to_parquet(path.parent / CLOCK_TABLE, index=False)
    summary = summarise(inventory)

    print(f"\ninventario -> {path}  ({time.time() - started:.0f}s)")
    print(json.dumps(summary, indent=2, ensure_ascii=False)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
