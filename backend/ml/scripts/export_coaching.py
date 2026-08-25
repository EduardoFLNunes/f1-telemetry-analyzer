"""Grava o tracado otimizado onde o coach ao vivo vai procurar por ele.

    python -m ml.scripts.export_coaching [--track vhe_interlagos] [--runtime-root DIR]

Este e o unico ponto em que o subsistema de ML escreve algo que o aplicativo le.
O que sai e um JSON de poucos KB -- sessenta tempos alvo e uma volta -- ao lado
do modelo de referencia do piloto, em `data/reference_models/`.

Depende de `ml.scripts.optimize_line` ter rodado antes: sem
`optimization/optimised_lateral.npy` nao ha tracado para exportar.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from ml import config
from ml.export.coaching import COACH_MICROSECTORS, build_targets
from ml.optimization.vehicle_model import load_envelope
from ml.track.geometry import load_geometry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Exporta o tracado otimizado para o coach")
    parser.add_argument("--track", default="vhe_interlagos", help="nome da pista no runtime")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=None,
        help="raiz do runtime do backend (padrao: raiz do repositorio)",
    )
    parser.add_argument("--microsectors", type=int, default=COACH_MICROSECTORS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="exporta mesmo que o tracado nao supere as voltas gravadas",
    )
    args = parser.parse_args(argv)

    root = config.artifacts_root()
    lateral_path = root / "optimization" / "optimised_lateral.npy"
    if not lateral_path.exists():
        print(f"tracado otimizado ausente em {lateral_path}")
        print("rode antes: python -m ml.scripts.optimize_line")
        return 1

    runtime_root = args.runtime_root or Path(__file__).resolve().parents[3]

    print("carregando pista e envelope...", flush=True)
    track = load_geometry()
    envelope = load_envelope()
    lateral = np.load(lateral_path)

    print("conferindo se o tracado supera as voltas gravadas...", flush=True)
    from ml.data.lap_store import load_store
    from ml.export.coaching import beats_recorded_laps

    verdict = beats_recorded_laps(track, lateral, envelope, load_store())
    print(
        f"  tracado {verdict['line_seconds']:.3f} s   "
        f"melhor volta gravada {verdict['quickest_recorded_seconds']:.3f} s   "
        f"(ambos no mesmo simulador)"
    )
    print(
        f"  voltas gravadas mais rapidas que o tracado: "
        f"{verdict['laps_quicker_than_line']}/{verdict['laps_compared']}"
    )
    if not verdict["is_an_improvement"] and not args.force:
        print(
            f"\nRECUSADO: o tracado e {-verdict['margin_seconds']:.3f} s mais lento que uma volta\n"
            "que o piloto ja fez, medida pelo mesmo simulador. Exportar isso faria o\n"
            "coach cobrar do piloto um alvo que ele ja supera.\n\n"
            "Rode a busca de novo, ou use --force se souber o que esta fazendo."
        )
        return 2

    print("simulando o tracado e repartindo por progresso...", flush=True)
    targets = build_targets(
        track,
        lateral,
        envelope,
        track_name=args.track,
        microsectors=args.microsectors,
        source=f"ml/{lateral_path.name}",
    )

    # Importado aqui, e nao no topo, porque este script vive no pacote `ml` e o
    # backend nao deve ser uma dependencia de import dele.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from core.assisted_analysis.optimal_line import optimal_line_path

    destination = optimal_line_path(runtime_root, args.track)
    targets.save(destination)

    total = sum(targets.seconds)
    print(f"\n  pista            {targets.track}")
    print(f"  microsetores     {targets.microsectors}")
    print(f"  volta simulada   {targets.lap_seconds:.3f} s")
    print(f"  soma das fatias  {total:.3f} s")
    print(f"  fatia mais curta {min(targets.seconds):.3f} s")
    print(f"  fatia mais longa {max(targets.seconds):.3f} s")
    print(f"\nartefato -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
