"""Analisa uma sessao controlada (Fase 2c) contra o plano sorteado.

    python -m ml.scripts.analyze_controlled_session --sessao <id> --plano docs/experimentos/<data>_plano.csv
        [--invalidas 7,19]  [--data AAAA-MM-DD]

`--invalidas` sao os numeros de volta **do jogo** que o piloto anotou como
invalidos durante a sessao.

Passos:
1. le a sessao pelo pipeline existente (`scan_sessions` + `build_store`: leitor,
   gates e alinhamento na grade de 2 m);
2. casa as voltas aproveitaveis com o plano, em ordem -- e para com a lista de
   voltas se a contagem nao bater;
3. usa a janela de curva da Fase 2b (zonas de frenagem das outras sessoes);
4. confere a execucao: frenagem e linha reais de cada condicao contra A;
5. mede os efeitos do 2 x 2 com IC 95 % (modelo linear com efeito de bloco);
6. compara com E1 a E4 da Fase 2b, treinados com todas as outras sessoes.

Escreve `docs/experimentos/<data>_resultado.json` e `<data>_resultado.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config
from ml.data.inventory import scan_sessions
from ml.data.lap_store import build_store, load_store
from ml.data.recordings import list_sessions
from ml.optimization.lap_time_model import step_times
from ml.track.corners import detect_corners
from ml.track.geometry import load_geometry
from ml.track.microsectors import build_microsectors
from ml.validation import controlled as ct
from ml.validation import counterfactual as cf
from ml.validation import empirical as em


def _sha256(path: Path) -> Dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return {"caminho": str(path.relative_to(config.repo_root())), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def lap_measures(store, windows, k, track) -> pd.DataFrame:
    """Medidas da janela-alvo em cada volta do store da sessao."""
    profiles = cf.lap_profiles(store, track, build_microsectors(track))
    rows = []
    for lap_id in store.lap_ids:
        features = em.lap_window_features(store.lap(lap_id), windows, track)[k]
        rows.append(
            {
                "lap_id": lap_id,
                "tempo_janela_s": float(em.window_sum(profiles[lap_id].observed_step_s, windows)[k]),
                **{m: features[m] for m in ct.MEASURES},
            }
        )
    return pd.DataFrame(rows)


def estimator_predictions(store, track, corners, windows, k, session_id, controlled_store, matched):
    """E1 a E4 da Fase 2b, treinados sem a sessao controlada, para as diferencas medidas."""
    microsectors = build_microsectors(track)
    profiles = cf.lap_profiles(store, track, microsectors)
    train = {key: p for key, p in profiles.items() if p.session_id != session_id}
    controlled = cf.lap_profiles(controlled_store, track, microsectors)

    envelope = cf.envelope_from(store, list(train))
    cf.simulate_profiles(track, envelope, list(train.values()) + list(controlled.values()))
    features = {key: em.lap_window_features(store.lap(key), windows, track) for key in train}
    pairs = em.build_pair_windows(train, windows, features, track)
    rows = np.flatnonzero(np.array(pairs.reason) == "")
    x_tr = em.design(pairs, rows, em.ACTIONABLE)
    y_tr = np.array(pairs.observed_s)[rows]
    w_tr = np.array(pairs.window)[rows]
    s_tr = np.array(pairs.session)[rows]

    differences = ct.condition_differences(matched)
    codes = ("B", "C", "D")
    x_te = np.vstack([differences[c] for c in codes])
    w_te = np.full(len(codes), k)
    ood = em.ood_mask(x_tr[w_tr == k], x_te)

    predictions: Dict[str, Dict[str, tuple]] = {}
    physics = np.array(pairs.physics_s)[rows]
    slope = cf.fit_slope(physics[w_tr == k], y_tr[w_tr == k])
    sim = {
        lap_id: float(
            em.window_sum(step_times(p.sim_speed_mps[None, :], p.step_length_m[None, :])[0], windows)[k]
        )
        for lap_id, p in controlled.items()
    }
    measured = matched[matched["condicao"] != ct.WARMUP]
    sim_mean = {c: float(np.mean([sim[i] for i in measured.loc[measured["condicao"] == c, "lap_id"]])) for c in "ABCD"}
    predictions["E1"] = {c: (slope * (sim_mean[c] - sim_mean["A"]), np.nan, np.nan) for c in codes}

    for name, fit in (
        ("E2", lambda: em.fit_ridge(x_tr, y_tr, w_tr, s_tr, x_te, w_te, windows.count)),
        ("E3", lambda: em.fit_knn(x_tr, y_tr, w_tr, s_tr, x_te, w_te, windows.count)),
        ("E4", lambda: em.fit_gp(x_tr, y_tr, w_tr, x_te, w_te, windows.count)),
    ):
        prediction, _ = fit()
        predictions[name] = {
            c: (float(prediction.point[i]), float(prediction.low[i]), float(prediction.high[i]))
            for i, c in enumerate(codes)
        }
    inputs = {c: dict(zip(em.ACTIONABLE, map(float, differences[c]))) for c in codes}
    training_range = {
        name: [float(np.percentile(x_tr[w_tr == k][:, j], em.OOD_LOW)), float(np.percentile(x_tr[w_tr == k][:, j], em.OOD_HIGH))]
        for j, name in enumerate(em.ACTIONABLE)
    }
    return predictions, {c: bool(ood[i]) for i, c in enumerate(codes)}, inputs, training_range, int(rows.size), slope


def write_markdown(path: Path, result: Dict[str, object]) -> None:
    ex = result["conferencia_da_execucao"]
    ef = result["efeitos"]
    lines = [
        f"# Sessao controlada {result['sessao']} - {result['curva']}",
        "",
        "Gerado por `python -m ml.scripts.analyze_controlled_session`. Numeros em segundos na janela de curva.",
        "",
        "## 1. Voce executou as condicoes?",
        "",
        "| condicao | voltas | frenagem vs A (pedido) | para dentro na entrada vs A (pedido) | longe do pedido? |",
        "|---|---:|---|---|---|",
    ]
    for code in sorted(ex):
        e = ex[code]
        lines.append(
            f"| {code} | {e['voltas']} | {e['frenagem_vs_A_m']:+.1f} m ({e['pedido']['frenagem_m']:+.0f}) | "
            f"{e['para_dentro_vs_A_m']['entry']:+.2f} m ({e['pedido']['para_dentro_m']:+.1f}) | "
            f"{'SIM: ' + '; '.join(e['observacoes']) if e['longe_do_pedido'] else 'nao'} |"
        )
    lines += [
        "",
        "## 2. Efeitos medidos (IC 95 %, modelo linear com efeito de bloco)",
        "",
        "| efeito | estimativa | IC 95 % |",
        "|---|---:|---|",
    ]
    for name in ("frenagem", "linha", "interacao", "B_menos_A", "C_menos_A", "D_menos_A"):
        e = ef[name]
        lines.append(f"| {name} | {e['estimativa_s'] * 1000:+.0f} ms | [{e['ic95_s'][0] * 1000:+.0f}; {e['ic95_s'][1] * 1000:+.0f}] ms |")
    lines += ["", "## 3. Os estimadores da Fase 2b acertam?", ""]
    for estimator, rows in result["comparacao_com_estimadores"].items():
        lines.append(f"**{estimator}**")
        for name, row in rows.items():
            if "medido_dentro_da_faixa" in row:
                inside = row["medido_dentro_da_faixa"]
                check = (
                    f", medido dentro da faixa de 95 % do estimador: {'sim' if inside else 'nao'}"
                    if inside is not None
                    else ", estimador sem faixa"
                )
            else:
                check = f", previsto dentro do IC 95 % medido: {'sim' if row['previsto_dentro_do_ic_medido'] else 'nao'}"
            lines.append(
                f"- {name}: medido {row['medido_s'] * 1000:+.0f} ms, previsto {row['previsto_s'] * 1000:+.0f} ms, "
                f"erro {row['erro_s'] * 1000:+.0f} ms"
                + check
                + (" (entrada fora da distribuicao de treino)" if row.get("fora_da_distribuicao") else "")
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sessao", required=True)
    parser.add_argument("--plano", type=Path, required=True)
    parser.add_argument("--invalidas", default="")
    parser.add_argument("--data", default=None, help="padrao: a data no inicio do id da sessao")
    parser.add_argument("--saida", type=Path, default=config.repo_root() / "docs" / "experimentos")
    args = parser.parse_args(argv)

    invalid = [int(v) for v in args.invalidas.split(",") if v.strip()]
    plan = pd.read_csv(args.plano)
    missing = [c for c in ct.PLAN_COLUMNS if c not in plan.columns]
    if missing:
        print(f"PARADO: o plano nao tem as colunas {missing}")
        return 2
    curve = str(plan["curva"].iloc[0])

    sessions = {s.session_id: s for s in list_sessions()}
    session = sessions.get(args.sessao)
    if session is None:
        print(f"PARADO: sessao {args.sessao} nao encontrada em {config.recordings_root()}")
        return 2

    track = load_geometry()
    corners = detect_corners(track)
    print(f"lendo {session.session_id}...", flush=True)
    inventory = scan_sessions([session], track)
    try:
        matched = ct.match_laps(inventory, plan, invalid)
    except ct.PlanMismatchError as error:
        print(f"PARADO: {error}")
        return 2

    store = load_store(track=track)
    train_ids = [i for i in store.lap_ids if not i.startswith(session.session_id + "#")]
    windows = em.define_windows([store.lap(i)["brake"].to_numpy(dtype=float) for i in train_ids], track, corners)
    label = ct.CORNER_NAMES[curve]
    targets = [k for k, c in enumerate(windows.corner) if c.label == label]
    if not targets:
        print(f"PARADO: nenhuma janela da Fase 2b comeca na curva {curve} ({label}); janelas: {windows.labels()}")
        return 2
    k = targets[0]
    direction = int(windows.corner[k].direction)

    controlled_store = build_store(inventory=inventory, track=track, sessions=[session])
    measures = lap_measures(controlled_store, windows, k, track)
    matched = matched.merge(measures, on="lap_id", how="left")
    undetected = matched[(matched["condicao"] != ct.WARMUP) & matched[list(ct.MEASURES)].isna().any(axis=1)]
    if len(undetected):
        print(
            "PARADO: frenagem ou retomada nao detectada na janela em "
            + ", ".join(f"ordem {r.ordem} ({r.lap_id})" for r in undetected.itertuples())
        )
        return 2

    measured = matched[matched["condicao"] != ct.WARMUP]
    execution = ct.execution_check(matched, direction)
    effects = ct.estimate_effects(
        measured["tempo_janela_s"].to_numpy(), measured["condicao"].to_numpy(), measured["bloco"].to_numpy()
    )
    predictions, ood, inputs, training_range, training_rows, slope = estimator_predictions(
        store, track, corners, windows, k, session.session_id, controlled_store, matched
    )
    comparison = ct.compare_with_estimators(effects, predictions, ood)

    import sklearn

    date = args.data or session.session_id[:10]
    result = {
        "sessao": session.session_id,
        "curva": curve,
        "janela": windows.describe()[k],
        "geometry_id": track.geometry_id,
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=config.repo_root(), text=True).strip(),
        "ambiente": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
        "plano": {"arquivo": str(args.plano), "semente": int(plan["semente"].iloc[0]), "voltas": int(len(plan))},
        "invalidas_anotadas": invalid,
        "dados": [
            _sha256(session.player_stream),
            _sha256(config.artifacts_root() / "laps_grid.parquet"),
            _sha256(config.artifacts_root() / "laps_grid_meta.json"),
        ],
        "voltas": matched.drop(columns=["status"], errors="ignore").to_dict(orient="records"),
        "conferencia_da_execucao": execution,
        "efeitos": effects,
        "entradas_para_os_estimadores": inputs,
        "faixa_de_treino_2_5_a_97_5": training_range,
        "pares_janela_de_treino": training_rows,
        "e1_inclinacao": slope,
        "comparacao_com_estimadores": comparison,
    }
    args.saida.mkdir(parents=True, exist_ok=True)
    json_path = args.saida / f"{date}_resultado.json"
    md_path = args.saida / f"{date}_resultado.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    write_markdown(md_path, result)
    print(md_path.read_text(encoding="utf-8"))
    print(f"-> {json_path}\n-> {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
