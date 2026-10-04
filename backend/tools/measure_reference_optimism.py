"""Quanto o "melhor de todos por microsetor" do coach e otimista (ADR 0012).

    python tools/measure_reference_optimism.py [--min-laps 20]

So dados ja gravados. Para cada sessao com pelo menos `--min-laps` voltas
validas (as do store do `ml`, todas com associacao `exact` ao replay):

* as voltas sao divididas em duas metades, na ordem em que foram feitas;
* o modelo do coach (`build_reference_model`, o mesmo codigo do app) e
  ajustado so com a primeira metade -- o "melhor de todos" de cada microsetor;
* na segunda metade mede-se em que fracao das voltas cada microsetor atinge esse
  melhor, quanto do "ganho na mesa" da primeira metade aparece na melhor volta
  da segunda, e a volta ideal da primeira contra a melhor volta real da segunda.

As voltas sao lidas como o coach as le (`LapDataLoader._load_recorded_lap`):
amostras com o mesmo numero de volta do jogo, sem os quadros de atraso do
contador, normalizadas por `normalize_lap_dataframe`. Aqui isso e feito numa
passada so pelo arquivo, em vez de uma por volta.

Escreve `data/ml/validation/reference_optimism/resultado.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.assisted_analysis.reference_model import build_reference_model, microsector_splits  # noqa: E402
from core.assisted_analysis.utils import finite_float, finite_int, normalize_lap_dataframe  # noqa: E402
from core.recording.session_repository import is_assetto_lap_counter_lag_frame  # noqa: E402
from ml import config  # noqa: E402
from ml.data.lap_store import load_store  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402


def coach_frames(player: Path, wanted: Dict[int, str]) -> Dict[str, pd.DataFrame]:
    """`{lap_id: df}` das voltas pedidas (numero do jogo -> lap_id), numa passada."""
    rows: Dict[int, List[dict]] = {number: [] for number in wanted}
    previous: Dict[int, Optional[float]] = {number: None for number in wanted}
    with player.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            sample = payload.get("sample", payload)
            number = finite_int(sample.get("lap_number", sample.get("lap")), 0)
            if number not in rows:
                continue
            if is_assetto_lap_counter_lag_frame(sample, previous[number]):
                continue
            row = dict(sample)
            row.setdefault("timestamp", payload.get("timestamp"))
            row.setdefault("sessionTime", payload.get("sessionTime"))
            row.setdefault("track", payload.get("track"))
            rows[number].append(row)
            elapsed = finite_float(sample.get("lap_time", sample.get("lapTime", sample.get("currentLapTime"))))
            if elapsed is not None:
                if elapsed > 10_000.0:
                    elapsed /= 1000.0
                previous[number] = max(previous[number] or elapsed, elapsed)
    return {wanted[n]: normalize_lap_dataframe(pd.DataFrame(r)) for n, r in rows.items() if r}


def measure_session(session_id: str, laps: pd.DataFrame, frames: Dict[str, pd.DataFrame]) -> Dict[str, object]:
    laps = laps.sort_values("sequence").reset_index(drop=True)
    half = len(laps) // 2
    first, second = laps.iloc[:half], laps.iloc[half:]

    def entries(part):
        return [
            (r.lap_id, float(r.lap_time_s), int(len(frames[r.lap_id])), frames[r.lap_id])
            for r in part.itertuples()
            if r.lap_id in frames
        ]

    model = build_reference_model(entries(first), track=session_id)
    best = {t.index: t.best_seconds for t in model.targets}

    second_entries = entries(second)
    splits = {lap_id: microsector_splits(df, model.microsectors) for lap_id, _, _, df in second_entries}
    reach = {}
    for index, target in best.items():
        values = [s[index] for s in splits.values() if s[index] is not None]
        reach[index] = float(np.mean([v <= target for v in values])) if values else float("nan")
    reach_values = np.array([v for v in reach.values() if np.isfinite(v)])

    best_first = float(first["lap_time_s"].min())
    best_second = float(second["lap_time_s"].min())
    on_table = best_first - float(model.ideal_lap_seconds) if model.ideal_lap_seconds else float("nan")
    realised = best_first - best_second
    return {
        "voltas_validas": int(len(laps)),
        "primeira_metade": {"voltas": int(len(first)), "voltas_no_modelo": model.lap_count, "descartadas": model.rejected_reasons},
        "segunda_metade": {"voltas": int(len(second)), "voltas_medidas": len(splits)},
        "microsetores_com_alvo": len(best),
        "fracao_das_voltas_que_atinge_o_melhor": {
            "media": float(reach_values.mean()) if reach_values.size else float("nan"),
            "mediana": float(np.median(reach_values)) if reach_values.size else float("nan"),
            "microsetores_nunca_atingidos": int((reach_values == 0).sum()),
            "microsetores_atingidos_em_mais_de_25pct": int((reach_values > 0.25).sum()),
            "por_microsetor": {str(k): v for k, v in sorted(reach.items())},
        },
        "melhor_volta_primeira_metade_s": best_first,
        "volta_ideal_primeira_metade_s": model.ideal_lap_seconds,
        "ganho_na_mesa_primeira_metade_s": on_table,
        "melhor_volta_segunda_metade_s": best_second,
        "ganho_realizado_na_segunda_metade_s": realised,
        "fracao_do_ganho_na_mesa_realizada": realised / on_table if on_table and on_table > 0 else float("nan"),
        "ideal_primeira_menos_melhor_real_segunda_s": float(model.ideal_lap_seconds) - best_second
        if model.ideal_lap_seconds
        else float("nan"),
    }


def measure_grid(session_laps: pd.DataFrame, store, track) -> Dict[str, object]:
    """A mesma medicao na grade do `ml`: 60 microsetores de mesma distancia.

    Serve onde a regua do coach nao existe -- as gravacoes de 2026-08-09 nao tem
    progresso (`p`), e o coach nao consegue recortar essas voltas -- e como
    segunda regua para as outras.
    """
    from ml.track.microsectors import build_microsectors, split_times, theoretical_best

    sectors = build_microsectors(track)
    laps = session_laps.sort_values("sequence").reset_index(drop=True)
    half = len(laps) // 2
    first, second = laps.iloc[:half], laps.iloc[half:]

    def splits(lap):
        frame = store.lap(lap.lap_id)
        return split_times(frame["elapsed_s"].to_numpy(dtype=float), sectors, track, total=float(lap.lap_time_s))

    first_splits = [splits(r) for r in first.itertuples()]
    second_splits = np.vstack([splits(r) for r in second.itertuples()])
    best = theoretical_best(first_splits)
    reach = (second_splits <= best[None, :]).mean(axis=0)
    ideal = float(best.sum())
    best_first = float(first["lap_time_s"].min())
    best_second = float(second["lap_time_s"].min())
    on_table = best_first - ideal
    realised = best_first - best_second
    return {
        "voltas_validas": int(len(laps)),
        "primeira_metade": int(len(first)),
        "segunda_metade": int(len(second)),
        "fracao_das_voltas_que_atinge_o_melhor": {
            "media": float(reach.mean()),
            "mediana": float(np.median(reach)),
            "microsetores_nunca_atingidos": int((reach == 0).sum()),
            "microsetores_atingidos_em_mais_de_25pct": int((reach > 0.25).sum()),
        },
        "melhor_volta_primeira_metade_s": best_first,
        "volta_ideal_primeira_metade_s": ideal,
        "ganho_na_mesa_primeira_metade_s": on_table,
        "melhor_volta_segunda_metade_s": best_second,
        "ganho_realizado_na_segunda_metade_s": realised,
        "fracao_do_ganho_na_mesa_realizada": realised / on_table if on_table > 0 else float("nan"),
        "ideal_primeira_menos_melhor_real_segunda_s": ideal - best_second,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--min-laps", type=int, default=20)
    args = parser.parse_args(argv)

    track = load_geometry()
    store = load_store(track=track)
    laps = store.laps
    counts = laps.groupby("session_id").size()
    sessions = sorted(counts[counts >= args.min_laps].index)
    print(f"sessoes com >= {args.min_laps} voltas validas: {sessions}", flush=True)

    out: Dict[str, object] = {"min_voltas": args.min_laps, "regua_do_coach": {}, "grade_do_ml": {}}
    for session_id in sessions:
        part = laps[laps["session_id"] == session_id]
        exact = part[part["replay_match"] == "exact"]
        if len(exact) != len(part):
            print(f"  {session_id}: {len(part) - len(exact)} voltas sem associacao exata ao replay; ficam de fora")
        wanted = {int(n): lap_id for n, lap_id in zip(exact["game_lap_number"], exact["lap_id"])}
        frames = coach_frames(config.recordings_root() / session_id / "player.jsonl", wanted)
        with_progress = {k: f for k, f in frames.items() if f["p"].nunique() > 10}
        if with_progress:
            out["regua_do_coach"][session_id] = measure_session(session_id, exact, with_progress)
        else:
            out["regua_do_coach"][session_id] = {
                "indisponivel": "a gravacao nao tem progresso (p): o coach nao recorta estas voltas em microsetores"
            }
        out["grade_do_ml"][session_id] = measure_grid(exact, store, track)
        for ruler in ("regua_do_coach", "grade_do_ml"):
            result = out[ruler][session_id]
            if "indisponivel" in result:
                print(f"  {session_id} [{ruler}]: {result['indisponivel']}", flush=True)
                continue
            reach = result["fracao_das_voltas_que_atinge_o_melhor"]
            print(
                f"  {session_id} [{ruler}]: ideal(1a) {result['volta_ideal_primeira_metade_s']:.3f} | melhor(1a) "
                f"{result['melhor_volta_primeira_metade_s']:.3f} | na mesa {result['ganho_na_mesa_primeira_metade_s']:.3f} | "
                f"melhor(2a) {result['melhor_volta_segunda_metade_s']:.3f} | realizado "
                f"{result['ganho_realizado_na_segunda_metade_s']:+.3f} | atinge o melhor: media {reach['media']:.1%}",
                flush=True,
            )

    path = config.artifacts_root() / "validation" / "reference_optimism" / "resultado.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
