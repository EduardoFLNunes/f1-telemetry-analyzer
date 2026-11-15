"""
Fit the coach's reference model for the learning phase (ADR 0016).

    python tools/train_reference_model.py [--track vhe_interlagos]
        [--inventario data/ml/origem/lap_inventory.parquet]
        [--geometria-arquivo <pista>.geometry.json] [--saida ARQUIVO]
        [--carro CARRO] [--dry-run]

The model carries two references, both real, complete laps (ADR 0032, pedido 51):

* ``volta_do_modelo`` (the default, "Volta de referência"): the model's lap,
  read from `data/reference_models/<track>.volta_do_modelo.json`
  (`ml.scripts.volta_do_modelo`). Without that file the model has no
  `volta_do_modelo` and the app offers only "Sua melhor volta";
* ``minha_melhor``: the driver's best clean lap, `humano` with the current
  equipment (ADR 0015).

The game's AI laps are no longer a reference of the app (ADR 0032, item 1).

The driver's spread through each microsector -- the speaking threshold -- comes
only from his own laps (`humano`, current equipment). Which laps are which comes
from the `ml` inventory with the labels of pedidos 12 and 13; a lap is clean
when it is valid, unique, its clock checked and not suspect, and it did not go
through the pits. Laps are read by their `ml` identity (`<session>#<order>`):
the game's lap counter repeats after a session restart, and the replay identity
(`rec__<session>__<n>`) would glue an AI lap and a driver's lap together.

Every lap is projected on the official geometry (ADR 0013). By default the model
is written to the repository's `data/reference_models/`, the one the
development app reads; the installed app's model is written only when asked
for with `--saida`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core.assisted_analysis.official_geometry import OfficialGeometry, find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import (  # noqa: E402
    DEFAULT_REFERENCE,
    REFERENCE_MODEL_LAP,
    REFERENCE_OWN_BEST,
    build_reference_model,
    model_path,
    reference_from_laps,
)
from ml import config  # noqa: E402
from ml.data.ai_detector import pit_lap  # noqa: E402
from core.assisted_analysis import volta_do_modelo  # noqa: E402
from ml.data.coach_references import driver_laps, most_common_car  # noqa: E402
from ml.data.recordings import iter_laps, list_all_sessions  # noqa: E402
from ml.data.session_annotations import cars_with_annotations  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

LapTuple = Tuple[str, Optional[float], Optional[int], pd.DataFrame]


def coach_frame(lap) -> pd.DataFrame:
    """An `ml` lap in the shape the coach's model fitting reads."""
    frame = lap.frame
    lap_time = pd.to_numeric(frame["lap_time_s"], errors="coerce")
    return pd.DataFrame({
        "x": pd.to_numeric(frame["x"], errors="coerce"),
        "z": pd.to_numeric(frame["z"], errors="coerce"),
        "elapsed_s": lap_time - lap_time.min(),
        "speed_kmh": pd.to_numeric(frame["speed_kmh"], errors="coerce"),
        "brake": pd.to_numeric(frame["brake"], errors="coerce"),
        "throttle": pd.to_numeric(frame["throttle"], errors="coerce"),
        "lap_number": lap.lap_number,
    }).dropna(subset=["x", "z", "elapsed_s"]).reset_index(drop=True)


def load_laps(rows: pd.DataFrame, sessions) -> List[LapTuple]:
    """Read the chosen laps by their `ml` identity, one pass per session."""
    wanted: Dict[str, Dict[int, pd.Series]] = {}
    for _, row in rows.iterrows():
        wanted.setdefault(row["session_id"], {})[int(row["sequence"])] = row
    laps: List[LapTuple] = []
    for session_id, by_sequence in sorted(wanted.items()):
        for lap in iter_laps(sessions[session_id]):
            row = by_sequence.get(lap.sequence)
            if row is not None:
                laps.append((lap.lap_id, float(row["duration_s"]), int(row["raw_samples"]), coach_frame(lap)))
    return laps


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Modelo do coach na fase de aprendizado (ADR 0016)")
    parser.add_argument("--track", default="vhe_interlagos")
    parser.add_argument("--inventario", type=Path, default=config.artifacts_root() / "origem" / "lap_inventory.parquet",
                        help="inventario do ml com origem e equipamento (pedidos 12 e 13)")
    parser.add_argument("--geometria-arquivo", type=Path, default=None,
                        help="geometria oficial exportada (padrao: data/reference_models/<pista>.geometry.json)")
    parser.add_argument("--saida", type=Path, default=None,
                        help="onde gravar (padrao: data/reference_models do repositorio, lido pelo app de desenvolvimento)")
    parser.add_argument("--carro", default=None, help="carModel (padrao: o das voltas do piloto)")
    parser.add_argument("--dry-run", action="store_true", help="nao grava o modelo")
    args = parser.parse_args(argv)

    repo = BACKEND_DIR.parent
    geometry = (
        OfficialGeometry.load(args.geometria_arquivo)
        if args.geometria_arquivo
        else find_official_geometry([repo], args.track)
    )
    if geometry is None:
        print("PARADO: geometria oficial nao encontrada. Rode antes: python -m ml.scripts.export_geometry")
        return 2
    print(f"geometria oficial : {geometry.geometry_id}  ({geometry.length:.2f} m, {geometry.microsectors} microsetores)")

    if not args.inventario.exists():
        print(f"PARADO: inventario nao encontrado em {args.inventario}. Rode: python -m ml.scripts.report_lap_origin")
        return 2
    inventory = pd.read_parquet(args.inventario)
    missing = {"origem", "equipamento", "relogio_suspeito"} - set(inventory.columns)
    if missing:
        print(f"PARADO: o inventario {args.inventario} nao tem {sorted(missing)} (pedidos 12 e 13).")
        return 2
    inventory = inventory[inventory["track"].fillna("").str.startswith(args.track)]

    sessions = {s.session_id: s for s in list_all_sessions()}
    cars = {sid: ((s.metadata().get("metadata") or {}).get("carModel")) for sid, s in sessions.items()}
    # O app instalado nao grava o carModel: vale o anotado (anotacoes_de_sessao.csv, 05/10).
    cars = cars_with_annotations(cars)
    grids_path = config.artifacts_root() / "origem" / "grade_voltas.parquet"
    track = load_geometry()
    sectors = build_microsectors(track)
    pits = set()
    if grids_path.exists():
        for lap_id, grid in pd.read_parquet(grids_path).groupby("lap_id"):
            if pit_lap(grid.sort_values("grid_index"), sectors):
                pits.add(lap_id)

    mine = driver_laps(inventory, pits)
    car = args.carro or most_common_car(mine, cars)
    mine = driver_laps(inventory, pits, cars=cars, car=car)
    print(f"carro             : {car}")
    print(f"voltas do piloto  : {len(mine)} (humano, equipamento atual, limpas)")
    if mine.empty:
        print("PARADO: nenhuma volta limpa do piloto com o equipamento atual. Modelo nao gravado.")
        return 2

    my_laps = load_laps(mine, sessions)
    model = build_reference_model(
        my_laps, track=args.track, built_at=datetime.now(timezone.utc).isoformat(), geometry=geometry,
    )
    reference, candidates = reference_from_laps(my_laps, geometry=geometry, kind=REFERENCE_OWN_BEST) if my_laps else (None, [])
    print(f"\nreferencia {REFERENCE_OWN_BEST}:")
    for candidate in candidates:
        print(f"  {candidate['lap_seconds']:.3f}s  {candidate['lap_id']}  -> {candidate['motivo']}")
    if reference is None:
        print("  (nenhuma volta valida e completa)")
    else:
        reference["carro"] = car
        model.references[REFERENCE_OWN_BEST] = reference

    # ADR 0032: a volta do modelo vem do arquivo derivado, no mesmo carro e na mesma geometria.
    print(f"\nreferencia {REFERENCE_MODEL_LAP}:")
    dados = volta_do_modelo.encontrar([repo], args.track)
    if dados is None:
        print(f"  ({volta_do_modelo.SEM_VOLTA_DO_MODELO}: {volta_do_modelo.caminho(repo, args.track)})")
    elif dados.get("geometry_id") != geometry.geometry_id:
        print(f"  fora: o arquivo e da geometria {dados.get('geometry_id')}, a oficial e {geometry.geometry_id}")
    elif car is not None and dados.get("carro") not in (None, car):
        print(f"  fora: o arquivo e do carro {dados.get('carro')}, as voltas do piloto sao do {car}")
    else:
        volta_do_modelo.anexar(model, dados)
        ref = model.references[REFERENCE_MODEL_LAP]
        print(f"  {ref['lap_seconds']:.3f}s  {ref['lap_id']}  -> {dados.get('marca')} ({dados.get('_arquivo')})")
    active = model.use_reference(DEFAULT_REFERENCE) or model.use_reference(REFERENCE_OWN_BEST)

    spreads = [t.median_seconds - t.best_seconds for t in model.targets]
    print()
    print("=" * 58)
    print(f"voltas do piloto no modelo : {model.lap_count}  (recusadas {model.rejected_count} {model.rejected_reasons})")
    print(f"referencia ativa           : {model.reference_kind} {model.reference_lap_id} {model.reference_lap_seconds}s"
          if active else "referencia ativa           : nenhuma")
    if spreads:
        print(f"oscilacao (mediana - melhor) por microsetor: mediana {np.median(spreads):.3f}s, "
              f"p90 {np.percentile(spreads, 90):.3f}s")
    print(f"geometria                  : {model.geometry_id}")
    print("=" * 58)

    if args.dry_run:
        print("\n--dry-run: modelo nao gravado")
        return 0
    path = model.save(args.saida or model_path(repo, args.track))
    print(f"\nmodelo gravado em: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
