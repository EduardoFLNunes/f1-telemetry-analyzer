"""Fase 2b: o estimador empirico preve o ganho numa janela de curva?

    python -m ml.scripts.validate_empirical

Deixa uma sessao inteira de fora por vez. Janelas, envelope, calibracao do E1,
regularizacao do E2, k do E3 e hiperparametros do E4 saem so das sessoes de
treino. Roda duas vezes: com todas as sessoes e sem as duas dominantes
(ADR 0006). Escreve em `data/ml/validation/empirical/`.

Regra de decisao, fixada antes da primeira execucao
---------------------------------------------------
* Um estimador e **aprovado** quando passa em todos os criterios do ADR 0006
  (`counterfactual.AcceptanceCriteria`, sem alteracao) nos pares-janela
  comparaveis e dentro da distribuicao, com a previsao pontual em todos eles
  (cobertura total, variante "todas as sessoes").
* Os mesmos criterios aplicados so aos casos em que o estimador responde
  (faixa de 95 % exclui zero) sao relatados como resultado **secundario**: dizem
  se a abstencao ajuda, mas nao aprovam sozinhos.
* E2-teto nunca e candidato (ADR 0005).
* Fora da distribuicao (alguma entrada fora de 2,5-97,5 % do treino naquela
  janela) e abstencao contada a parte, igual para todos os estimadores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
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
from ml.validation import empirical as em

DOMINANT = ("2026-08-09_19-20-59_vhe_interlagos", "2026-06-20_13-13-02_vhe_interlagos")
CANDIDATES = ("E1", "E2", "E3", "E4")
WITH_INTERVAL = ("E2", "E3", "E4", "E2_teto")
BRAKING_BINS = (("< 5 m", 0.0, 5.0), ("5-15 m", 5.0, 15.0), (">= 15 m", 15.0, np.inf))
APEX_BINS = (("< 0,5 m", 0.0, 0.5), ("0,5-1,5 m", 0.5, 1.5), (">= 1,5 m", 1.5, np.inf))


def run_variant(name, store, track, corners, profiles, laps_by_session, log) -> Dict[str, object]:
    sessions = sorted(laps_by_session)
    testable = [s for s in sessions if laps_by_session[s] >= 2]
    rows: List[pd.DataFrame] = []
    folds = []
    for session_id in testable:
        started = time.time()
        train_ids = [k for k, p in profiles.items() if p.session_id != session_id]
        windows = em.define_windows([store.lap(i)["brake"].to_numpy(dtype=float) for i in train_ids], track, corners)
        envelope = cf.envelope_from(store, train_ids)
        cf.simulate_profiles(track, envelope, list(profiles.values()))
        features = {k: em.lap_window_features(store.lap(k), windows, track) for k in profiles}

        train = em.build_pair_windows({k: p for k, p in profiles.items() if p.session_id != session_id}, windows, features, track)
        test = em.build_pair_windows({k: p for k, p in profiles.items() if p.session_id == session_id}, windows, features, track)

        tr = np.flatnonzero(np.array(train.reason) == "")
        te = np.flatnonzero(np.array(test.reason) == "")
        x_tr = em.design(train, tr, em.ACTIONABLE)
        x_te = em.design(test, te, em.ACTIONABLE)
        c_tr = em.design(train, tr, em.ACTIONABLE + em.CEILING_EXTRA)
        c_te = em.design(test, te, em.ACTIONABLE + em.CEILING_EXTRA)
        y_tr = np.array(train.observed_s)[tr]
        w_tr = np.array(train.window)[tr]
        w_te = np.array(test.window)[te]
        s_tr = np.array(train.session)[tr]

        ood = np.zeros(te.size, dtype=bool)
        for k in range(windows.count):
            mask = w_te == k
            ood[mask] = em.ood_mask(x_tr[w_tr == k], x_te[mask])

        physics_tr = np.array(train.physics_s)[tr]
        slopes = {k: cf.fit_slope(physics_tr[w_tr == k], y_tr[w_tr == k]) for k in range(windows.count)}
        e1 = np.array([slopes[k] for k in w_te]) * np.array(test.physics_s)[te]

        e2, e2_info = em.fit_ridge(x_tr, y_tr, w_tr, s_tr, x_te, w_te, windows.count)
        e3, e3_info = em.fit_knn(x_tr, y_tr, w_tr, s_tr, x_te, w_te, windows.count)
        e4, e4_info = em.fit_gp(x_tr, y_tr, w_tr, x_te, w_te, windows.count)
        teto, teto_info = em.fit_ridge(c_tr, y_tr, w_tr, s_tr, c_te, w_te, windows.count)

        labels = windows.labels()
        frame = pd.DataFrame(
            {
                "variant": name,
                "fold": session_id,
                "session_id": np.array(test.session)[te],
                "slow": np.array(test.slow)[te],
                "fast": np.array(test.fast)[te],
                "window": w_te,
                "window_label": [labels[k] for k in w_te],
                "pace_s": np.array(test.pace_s)[te],
                "observed_s": np.array(test.observed_s)[te],
                "ood": ood,
                "pred_E0": 0.0,
                "pred_E1": e1,
                **{f"x_{c}": c_te[:, i] for i, c in enumerate(em.ACTIONABLE + em.CEILING_EXTRA)},
            }
        )
        for label, prediction in (("E2", e2), ("E3", e3), ("E4", e4), ("E2_teto", teto)):
            frame[f"pred_{label}"] = prediction.point
            frame[f"low_{label}"] = prediction.low
            frame[f"high_{label}"] = prediction.high
        rows.append(frame)

        reasons = pd.Series(test.reason).replace("", "comparavel").value_counts().to_dict()
        folds.append(
            {
                "sessao_de_teste": session_id,
                "voltas_de_teste": int(laps_by_session[session_id]),
                "janelas": windows.describe(),
                "pares_janela_teste": int(len(test)),
                "motivos_teste": reasons,
                "comparaveis_teste": int(te.size),
                "fora_da_distribuicao_teste": int(ood.sum()),
                "comparaveis_treino": int(tr.size),
                "e1_inclinacao_por_janela": {labels[k]: v for k, v in slopes.items()},
                "e2": e2_info,
                "e3": e3_info,
                "e4": e4_info,
                "e2_teto": teto_info,
                "segundos": round(time.time() - started, 1),
            }
        )
        log(f"  [{name}] {session_id}: {te.size} comparaveis, {int(ood.sum())} fora da distribuicao ({folds[-1]['segundos']} s)")

    data = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return {"testaveis": testable, "dobras": folds, "data": data}


def evaluate(data: pd.DataFrame, bootstrap: int) -> Dict[str, object]:
    criteria = cf.AcceptanceCriteria()
    inside = data[~data["ood"]]
    observed = inside["observed_s"].to_numpy()
    estimators = ["E0", "E1", "E2", "E3", "E4", "E2_teto"]

    def block(subset: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        return {
            e: cf.error_metrics(subset[f"pred_{e}"].to_numpy(), subset["observed_s"].to_numpy())
            for e in estimators
        }

    out: Dict[str, object] = {
        "pares_janela_comparaveis": int(len(data)),
        "fora_da_distribuicao": int(data["ood"].sum()),
        "dentro_da_distribuicao": int(len(inside)),
        "cobertura_total": block(inside),
        "fora_da_distribuicao_se_respondesse": block(data[data["ood"]]),
        "por_ritmo": {},
        "por_janela": {k: block(g) for k, g in inside.groupby("window_label")},
        "por_sessao": {k: block(g) for k, g in inside.groupby("session_id")},
        "por_diferenca_de_frenagem": {},
        "por_diferenca_lateral_no_apice": {},
        "decisao": {},
        "seletivo": {},
        "risco_cobertura": {},
        "calibracao_faixa_95": {},
    }
    pace = pd.cut(inside["pace_s"], [b[1] for b in cf.PACE_BANDS] + [np.inf], labels=[b[0] for b in cf.PACE_BANDS], right=False)
    out["por_ritmo"] = {str(k): block(g) for k, g in inside.groupby(pace.astype(str))}
    for key, column, bins in (
        ("por_diferenca_de_frenagem", "x_braking_point_m", BRAKING_BINS),
        ("por_diferenca_lateral_no_apice", "x_lateral_apex_m", APEX_BINS),
    ):
        binned = pd.cut(inside[column].abs(), [b[1] for b in bins] + [np.inf], labels=[b[0] for b in bins], right=False)
        out[key] = {str(k): block(g) for k, g in inside.groupby(binned.astype(str))}

    for e in CANDIDATES + ("E2_teto",):
        predicted = inside[f"pred_{e}"].to_numpy()
        pooled = cf.error_metrics(predicted, observed)
        ci = cf.cluster_bootstrap_skill(predicted, observed, inside["session_id"].to_numpy(), repetitions=bootstrap)
        per_session = {
            s: cf.error_metrics(g[f"pred_{e}"].to_numpy(), g["observed_s"].to_numpy())
            for s, g in inside.groupby("session_id")
        }
        verdict = criteria.evaluate(pooled, ci[0], per_session)
        out["decisao"][e] = {
            "candidato": e != "E2_teto",
            "ic95_skill": ci,
            **verdict,
        }

    for e in WITH_INTERVAL:
        prediction = em.Prediction(
            inside[f"pred_{e}"].to_numpy(), inside[f"low_{e}"].to_numpy(), inside[f"high_{e}"].to_numpy()
        )
        responds = em.answered(prediction)
        chosen = inside[responds]
        pooled = cf.error_metrics(chosen[f"pred_{e}"].to_numpy(), chosen["observed_s"].to_numpy())
        ci = (
            cf.cluster_bootstrap_skill(
                chosen[f"pred_{e}"].to_numpy(), chosen["observed_s"].to_numpy(), chosen["session_id"].to_numpy(), repetitions=bootstrap
            )
            if len(chosen)
            else (float("nan"), float("nan"))
        )
        per_session = {
            s: cf.error_metrics(g[f"pred_{e}"].to_numpy(), g["observed_s"].to_numpy())
            for s, g in chosen.groupby("session_id")
        }
        out["seletivo"][e] = {
            "responde": int(responds.sum()),
            "nao_conclusivo": int((~responds).sum()),
            "cobertura": float(responds.mean()) if responds.size else float("nan"),
            "metricas_quando_responde": pooled,
            "ic95_skill_quando_responde": ci,
            "criterios_quando_responde_secundario": criteria.evaluate(pooled, ci[0], per_session) if len(chosen) else None,
        }
        out["risco_cobertura"][e] = em.risk_coverage(prediction, observed)
        out["calibracao_faixa_95"][e] = {
            "dentro_da_distribuicao": em.interval_coverage(prediction, observed),
            "fora_da_distribuicao": em.interval_coverage(
                em.Prediction(
                    data.loc[data["ood"], f"pred_{e}"].to_numpy(),
                    data.loc[data["ood"], f"low_{e}"].to_numpy(),
                    data.loc[data["ood"], f"high_{e}"].to_numpy(),
                ),
                data.loc[data["ood"], "observed_s"].to_numpy(),
            ),
        }
    return out


def file_record(path: Path) -> Dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return {"caminho": str(path.relative_to(config.repo_root())), "sha256": digest, "bytes": path.stat().st_size if path.exists() else None}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args(argv)
    started = time.time()

    track = load_geometry()
    corners = detect_corners(track)
    store = load_store(track=track)
    profiles = cf.lap_profiles(store, track, build_microsectors(track))
    counts = store.laps.groupby("session_id").size()
    print(f"geometria {track.geometry_id} | {len(profiles)} voltas | {counts.size} sessoes", flush=True)

    variants = {}
    data_frames = []
    for name, excluded in (("todas", ()), ("sem_dominantes", DOMINANT)):
        subset = {k: p for k, p in profiles.items() if p.session_id not in excluded}
        per_session = {s: int(n) for s, n in counts.items() if s not in excluded}
        run = run_variant(name, store, track, corners, subset, per_session, lambda m: print(m, flush=True))
        evaluation = evaluate(run["data"], args.bootstrap)
        variants[name] = {"sessoes_testaveis": run["testaveis"], "dobras": run["dobras"], **evaluation}
        data_frames.append(run["data"])

    # Informativo: o modelo da variante completa, avaliado so fora das dominantes.
    main_data = data_frames[0]
    variants["todas_avaliado_sem_dominantes"] = evaluate(
        main_data[~main_data["session_id"].isin(DOMINANT)], args.bootstrap
    )

    import sklearn

    root = config.repo_root()
    result = {
        "etapa": "fase2b",
        "commit_base": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "geometry_id": track.geometry_id,
        "dados": [
            file_record(config.artifacts_root() / "laps_grid.parquet"),
            file_record(config.artifacts_root() / "laps_grid_meta.json"),
            file_record(config.artifacts_root() / "lap_inventory.parquet"),
            file_record(config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE),
        ],
        "ambiente": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "comando": "cd backend && python -m ml.scripts.validate_empirical",
        "regra_de_decisao": __doc__.split("Regra de decisao")[1].strip(),
        "criterios_adr_0006": cf.AcceptanceCriteria().to_dict(),
        "parametros": {
            "janelas": {
                "limiar_freio": em.BRAKE_ONSET,
                "limiar_acelerador": em.THROTTLE_ONSET,
                "fracao_minima_de_voltas": em.MIN_LAP_SHARE,
                "juntar_zonas_a_menos_de_m": em.MERGE_ZONES_M,
                "margem_inicio_m": em.START_MARGIN_M,
                "quantil_inicio": em.START_QUANTILE,
            },
            "filtros": {
                "combustivel_l": cf.MAX_FUEL_DIFF_L,
                "desgaste_pneu": cf.MAX_TYRE_WEAR_DIFF,
                "velocidade_entrada_kmh": cf.MAX_ENTRY_SPEED_DIFF_KMH,
                "eficiencia_minima": cf.MIN_EFFICIENCY,
            },
            "entradas": list(em.ACTIONABLE),
            "entradas_teto": list(em.ACTIONABLE + em.CEILING_EXTRA),
            "ridge_alphas": list(em.RIDGE_ALPHAS),
            "knn_ks": list(em.KNN_KS),
            "gp_max_treino_por_janela": em.GP_MAX_TRAIN,
            "fora_da_distribuicao_percentis": [em.OOD_LOW, em.OOD_HIGH],
            "bootstrap": args.bootstrap,
        },
        "variantes": variants,
        "segundos": round(time.time() - started, 1),
    }

    out_dir = config.artifacts_root() / "validation" / "empirical"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "resultado.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=_jsonable), encoding="utf-8"
    )
    pd.concat(data_frames, ignore_index=True).to_parquet(out_dir / "pares_por_janela.parquet", index=False)
    for name in ("todas", "sem_dominantes"):
        print(f"\n[{name}]")
        for e, d in variants[name]["decisao"].items():
            m = variants[name]["cobertura_total"][e]
            print(f"  {e:8s} skill={m.get('skill', float('nan')):+.3f} IC={np.round(d['ic95_skill'], 3)} {'APROVADO' if d['aprovado'] else 'reprovado'}")
    print(f"\n-> {out_dir}  ({result['segundos']} s)")
    return 0


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
