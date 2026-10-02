"""Gera o plano sorteado da sessao controlada (Fase 2c).

    python -m ml.scripts.plan_controlled_session --semente 2026 [--curva "Bico de Pato"]
        [--condicoes A,B,C,D] [--voltas-por-condicao 8] [--aquecimento 5] [--data AAAA-MM-DD]

Grava `docs/experimentos/<data>_plano.csv` (com a semente em cada linha, para o
plano poder ser refeito igual) e `<data>_plano.txt`, para imprimir ou deixar na
tela durante a sessao.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config
from ml.validation.controlled import make_plan, plan_text


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--curva", default="Bico de Pato")
    parser.add_argument("--condicoes", default="A,B,C,D")
    parser.add_argument("--voltas-por-condicao", type=int, default=8)
    parser.add_argument("--aquecimento", type=int, default=5)
    parser.add_argument("--semente", type=int, required=True)
    parser.add_argument("--data", default=dt.date.today().isoformat())
    parser.add_argument("--saida", type=Path, default=config.repo_root() / "docs" / "experimentos")
    args = parser.parse_args(argv)

    plan = make_plan(
        curve=args.curva,
        conditions=[c.strip() for c in args.condicoes.split(",") if c.strip()],
        laps_per_condition=args.voltas_por_condicao,
        warmup=args.aquecimento,
        seed=args.semente,
    )
    args.saida.mkdir(parents=True, exist_ok=True)
    csv_path = args.saida / f"{args.data}_plano.csv"
    txt_path = args.saida / f"{args.data}_plano.txt"
    plan.to_csv(csv_path, index=False, encoding="utf-8")
    txt_path.write_text(plan_text(plan), encoding="utf-8")
    print(plan_text(plan))
    print(f"-> {csv_path}\n-> {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
