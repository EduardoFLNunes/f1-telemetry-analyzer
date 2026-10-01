"""Valida a previsao da diferenca de tempo entre duas trajetorias.

    python -m ml.scripts.validate_counterfactual

Deixa uma sessao de fora por vez: o envelope do carro, a janela de eficiencia e
a inclinacao calibrada sao ajustados nas outras sessoes; a sessao de fora so
fornece os pares de teste. Escreve tudo em `data/ml/validation/counterfactual/`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config
from ml.data.lap_store import load_store
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors
from ml.validation import counterfactual as cf

PRIMARY_MIN_LINE_DIFF_M = 0.5
EXECUTION_SIMILAR_PEDAL = 0.05


def surrogate_sector_times(track, corners, sectors, profiles, allowed_sessions) -> Dict[str, np.ndarray]:
    """Tempo por microsetor pela LSTM substituta, so nas sessoes que ela nao viu."""
    from ml.models.sequences import SURROGATE_TASK, drop_warmup, with_warmup
    from ml.models.training import load_model
    from ml.optimization.surrogate import SurrogateFeatures

    model = load_model(config.artifacts_root() / "models" / "surrogate")
    features = SurrogateFeatures(track, corners, trained=model)
    out: Dict[str, np.ndarray] = {}
    wanted = [p for p in profiles.values() if p.session_id in allowed_sessions]
    pad = SURROGATE_TASK.window
    for start in range(0, len(wanted), 16):
        batch = wanted[start : start + 16]
        inputs = with_warmup(features(np.vstack([p.lateral for p in batch])), pad)
        per_step = drop_warmup(model.predict(inputs), pad)[..., 0]
        for profile, steps in zip(batch, per_step):
            out[profile.lap_id] = np.bincount(sectors.index, weights=steps, minlength=sectors.count)
    return out


def similar_execution(pairs, profiles, sectors) -> np.ndarray:
    """(pares, setores): os dois carros usaram os pedais do mesmo jeito ali.

    Diagnostico, nao criterio: usa os pedais da volta B, que numa recomendacao
    real nao existiriam. Serve para ver se o estimador acerta quando a
    diferenca de tempo tem de vir da linha.
    """
    counts = np.bincount(sectors.index, minlength=sectors.count)
    out = np.zeros((len(pairs), sectors.count), dtype=bool)
    for index, (a_id, b_id) in enumerate(zip(pairs.slow, pairs.fast)):
        a, b = profiles[a_id], profiles[b_id]
        brake = np.bincount(sectors.index, weights=np.abs(a.brake - b.brake), minlength=sectors.count) / counts
        throttle = np.bincount(sectors.index, weights=np.abs(a.throttle - b.throttle), minlength=sectors.count) / counts
        out[index] = (brake < EXECUTION_SIMILAR_PEDAL) & (throttle < EXECUTION_SIMILAR_PEDAL)
    return out


def tune(pairs, profiles, sectors) -> Dict[str, float]:
    """Janela de eficiencia e inclinacao, so com pares das sessoes de treino."""
    usable = pairs.sector_reason == ""
    observed = pairs.observed[usable]
    best_window, best_mae, maes = None, np.inf, {}
    for window in cf.EFFICIENCY_WINDOWS:
        predicted = cf.predict(pairs, profiles, sectors, window, 1.0)["efficiency"][usable]
        mae = float(np.mean(np.abs(predicted - observed)))
        maes[str(window)] = mae
        if mae < best_mae:
            best_window, best_mae = window, mae
    physics = cf.predict(pairs, profiles, sectors, 0, 1.0)["physics"][usable]
    return {"window": best_window, "slope": cf.fit_slope(physics, observed), "train_mae_by_window": maes}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-surrogate", action="store_true")
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args(argv)
    started = time.time()

    track = load_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    store = load_store(track=track)
    profiles = cf.lap_profiles(store, track, sectors)
    print(f"geometria {track.geometry_id} | {len(profiles)} voltas | {store.laps['session_id'].nunique()} sessoes")

    laps_per_session = store.laps.groupby("session_id").size()
    testable = sorted(laps_per_session[laps_per_session >= 2].index)
    total_pairs = len(profiles) * (len(profiles) - 1) // 2
    within = int(sum(n * (n - 1) // 2 for n in laps_per_session))

    surrogate_sector: Optional[Dict[str, np.ndarray]] = None
    surrogate_note = ""
    if not args.no_surrogate:
        metrics_path = config.artifacts_root() / "models" / "metrics.json"
        seen = json.loads(metrics_path.read_text(encoding="utf-8"))["split"]["sessions"]
        unseen = {s for s in laps_per_session.index if seen.get(s) not in ("train", "validation")}
        try:
            surrogate_sector = surrogate_sector_times(track, corners, sectors, profiles, unseen)
            surrogate_note = f"avaliada so em {sorted(unseen)}"
        except Exception as exc:  # pragma: no cover - depende do ambiente
            surrogate_note = f"nao avaliada: {exc}"
    print(f"substituta: {surrogate_note}")

    rows: List[pd.DataFrame] = []
    folds = []
    for session_id in testable:
        train_ids = [p.lap_id for p in profiles.values() if p.session_id != session_id]
        envelope = cf.envelope_from(store, train_ids)
        cf.simulate_profiles(track, envelope, list(profiles.values()))

        train_profiles = {k: v for k, v in profiles.items() if v.session_id != session_id}
        test_profiles = {k: v for k, v in profiles.items() if v.session_id == session_id}
        tuned = tune(cf.build_pairs(train_profiles, sectors), profiles, sectors)

        pairs = cf.build_pairs(test_profiles, sectors)
        predicted = cf.predict(pairs, profiles, sectors, tuned["window"], tuned["slope"], surrogate_sector)
        parts = cf.decompose(pairs, profiles, sectors)
        similar = similar_execution(pairs, profiles, sectors)

        count, sector_count = len(pairs), sectors.count
        frame = pd.DataFrame(
            {
                "session_id": np.repeat(pairs.session, sector_count),
                "slow": np.repeat(pairs.slow, sector_count),
                "fast": np.repeat(pairs.fast, sector_count),
                "pace_s": np.repeat(pairs.pace_s, sector_count),
                "lap_reason": np.repeat(pairs.lap_reason, sector_count),
                "sector": np.tile(np.arange(sector_count), count),
                "sector_reason": pairs.sector_reason.ravel(),
                "line_diff_m": pairs.line_diff_m.ravel(),
                "similar_execution": similar.ravel(),
                "observed_s": pairs.observed.ravel(),
                **{f"pred_{name}": values.ravel() for name, values in predicted.items()},
                **{f"part_{name}": values.ravel() for name, values in parts.items()},
            }
        )
        rows.append(frame)
        folds.append(
            {
                "session_id": session_id,
                "test_laps": len(test_profiles),
                "train_laps": len(train_ids),
                "pairs": count,
                "window_points": tuned["window"],
                "slope": tuned["slope"],
                "train_mae_by_window": tuned["train_mae_by_window"],
                "envelope_top_speed_kmh": envelope.top_speed_mps * 3.6,
            }
        )
        print(
            f"  {session_id}: {len(test_profiles)} voltas, {count} pares | "
            f"janela={tuned['window']} k={tuned['slope']:.3f}",
            flush=True,
        )

    data = pd.concat(rows, ignore_index=True)
    data["compatible"] = data["sector_reason"] == ""
    data["pace_band"] = pd.cut(
        data["pace_s"],
        [b[1] for b in cf.PACE_BANDS] + [np.inf],
        labels=[b[0] for b in cf.PACE_BANDS],
        right=False,
    ).astype(str)
    data["line_bin"] = pd.cut(
        data["line_diff_m"],
        [b[1] for b in cf.LINE_BINS] + [np.inf],
        labels=[b[0] for b in cf.LINE_BINS],
        right=False,
    ).astype(str)

    estimators = [c[len("pred_"):] for c in data.columns if c.startswith("pred_")]

    def metrics(subset: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        return {
            name: cf.error_metrics(subset[f"pred_{name}"].to_numpy(), subset["observed_s"].to_numpy())
            for name in estimators
        }

    primary = data[data["compatible"] & (data["line_diff_m"] >= PRIMARY_MIN_LINE_DIFF_M)]
    compatible = data[data["compatible"]]

    # Volta inteira: soma dos 60 microsetores, nos pares comparaveis como volta.
    lap_level = (
        data[data["lap_reason"] == ""]
        .groupby(["session_id", "slow", "fast", "pace_s"], as_index=False)[
            ["observed_s"] + [f"pred_{n}" for n in estimators]
        ]
        .sum(min_count=1)
    )

    criteria = cf.AcceptanceCriteria()
    decisions = {}
    for name in estimators:
        if name == "zero":
            continue
        pooled = cf.error_metrics(primary[f"pred_{name}"].to_numpy(), primary["observed_s"].to_numpy())
        ci = cf.cluster_bootstrap_skill(
            primary[f"pred_{name}"].to_numpy(),
            primary["observed_s"].to_numpy(),
            primary["session_id"].to_numpy(),
            repetitions=args.bootstrap,
        )
        per_session = {
            s: cf.error_metrics(g[f"pred_{name}"].to_numpy(), g["observed_s"].to_numpy())
            for s, g in primary.groupby("session_id")
        }
        decisions[name] = {"ic95_pericia": ci, **criteria.evaluate(pooled, ci[0], per_session)}

    sector_exclusions = data["sector_reason"].replace("", "comparavel").value_counts().to_dict()
    lap_pairs = data.drop_duplicates(["slow", "fast"])
    lap_exclusions = lap_pairs["lap_reason"].replace("", "comparavel").value_counts().to_dict()
    lap_exclusions["sessoes diferentes (par nao formado)"] = total_pairs - within

    # Decomposicao, nos microsetores comparaveis.
    parts = compatible
    interaction_share = np.abs(parts["part_interaction"]) / np.maximum(
        np.abs(parts["part_line"]) + np.abs(parts["part_execution"]), 1e-9
    )
    decomposition = {
        "setores": int(len(parts)),
        "identidade_total_menos_observado_max_s": float(np.max(np.abs(parts["part_total"] - parts["observed_s"]))),
        "media_abs_linha_s": float(np.mean(np.abs(parts["part_line"]))),
        "media_abs_execucao_s": float(np.mean(np.abs(parts["part_execution"]))),
        "media_abs_interacao_s": float(np.mean(np.abs(parts["part_interaction"]))),
        "mediana_interacao_relativa": float(np.median(interaction_share)),
        "p90_interacao_relativa": float(np.percentile(interaction_share, 90)),
        "fracao_interacao_acima_de_25pct": float(np.mean(interaction_share > 0.25)),
        "correlacao_linha_execucao": float(np.corrcoef(parts["part_line"], parts["part_execution"])[0, 1]),
        "volta_inteira": {
            "media_abs_linha_s": float(lap_level_parts(data, "part_line").abs().mean()),
            "media_abs_execucao_s": float(lap_level_parts(data, "part_execution").abs().mean()),
            "media_abs_interacao_s": float(lap_level_parts(data, "part_interaction").abs().mean()),
            "media_abs_total_s": float(lap_level_parts(data, "part_total").abs().mean()),
        },
    }

    result = {
        "geometry_id": track.geometry_id,
        "store": {
            "voltas": int(len(profiles)),
            "sessoes": int(laps_per_session.size),
            "voltas_por_sessao": {k: int(v) for k, v in laps_per_session.items()},
            "sessoes_testaveis": testable,
        },
        "pares": {
            "total_possivel": total_pairs,
            "dentro_da_sessao": within,
            "exclusoes_de_par": lap_exclusions,
            "exclusoes_de_microsetor": sector_exclusions,
            "microsetores_comparaveis": int(len(compatible)),
            "microsetores_primarios": int(len(primary)),
        },
        "comparabilidade": {
            "max_fuel_diff_l": cf.MAX_FUEL_DIFF_L,
            "max_tyre_wear_diff": cf.MAX_TYRE_WEAR_DIFF,
            "max_entry_speed_diff_kmh": cf.MAX_ENTRY_SPEED_DIFF_KMH,
            "min_efficiency": cf.MIN_EFFICIENCY,
            "primario_min_diferenca_de_linha_m": PRIMARY_MIN_LINE_DIFF_M,
        },
        "substituta": surrogate_note,
        "dobras": folds,
        "metricas": {
            "primario": metrics(primary),
            "todos_comparaveis": metrics(compatible),
            "por_diferenca_de_linha": {k: metrics(g) for k, g in compatible.groupby("line_bin")},
            "por_ritmo": {k: metrics(g) for k, g in primary.groupby("pace_band")},
            "por_sessao": {k: metrics(g) for k, g in primary.groupby("session_id")},
            "execucao_semelhante_diagnostico": metrics(primary[primary["similar_execution"]]),
            "volta_inteira": {
                "pares": int(len(lap_level)),
                **{
                    name: cf.error_metrics(lap_level[f"pred_{name}"].to_numpy(), lap_level["observed_s"].to_numpy())
                    for name in estimators
                },
                "por_ritmo": {
                    band: {
                        name: cf.error_metrics(g[f"pred_{name}"].to_numpy(), g["observed_s"].to_numpy())
                        for name in estimators
                    }
                    for band, g in lap_level.assign(
                        band=pd.cut(
                            lap_level["pace_s"],
                            [b[1] for b in cf.PACE_BANDS] + [np.inf],
                            labels=[b[0] for b in cf.PACE_BANDS],
                            right=False,
                        ).astype(str)
                    ).groupby("band")
                },
            },
        },
        "criterios": criteria.to_dict(),
        "decisao": decisions,
        "decomposicao": decomposition,
        "segundos": round(time.time() - started, 1),
    }

    out_dir = config.artifacts_root() / "validation" / "counterfactual"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=_jsonable), encoding="utf-8"
    )
    data.to_parquet(out_dir / "pares_por_microsetor.parquet", index=False)
    lap_level.to_csv(out_dir / "pares_por_volta.csv", index=False)
    print(json.dumps({k: result[k] for k in ("store", "pares", "decisao")}, indent=1, ensure_ascii=False, default=_jsonable))
    print(f"\n-> {out_dir}  ({result['segundos']} s)")
    return 0


def lap_level_parts(data: pd.DataFrame, column: str) -> pd.Series:
    subset = data[data["lap_reason"] == ""]
    return subset.groupby(["slow", "fast"])[column].sum()


def _jsonable(value):
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
