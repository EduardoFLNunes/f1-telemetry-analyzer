"""Pedido 13: sessao rotulada, variacao do piloto e detector da IA.

    python -m ml.scripts.detector_ia calibrar [--saida data/ml/origem] [--json ARQUIVO]
    python -m ml.scripts.detector_ia variacao [--saida ...] [--json ARQUIVO]
    python -m ml.scripts.detector_ia aplicar  [--saida ...] [--json ARQUIVO]

Le o inventario e a grade de `ml.scripts.report_lap_origin` (que ja inclui as
sessoes de 2026-10-04). A ordem importa:

1. `calibrar` olha **so** a sessao rotulada: rotulos pelas anotacoes, conferidos
   com o indicador, e as distancias ate a linha da IA, para escolher os limites;
2. os limites vao para `ml/data/ai_detector.py` e `docs/detector_ia.md` num
   commit proprio;
3. `aplicar` recusa rodar sem os limites, e so entao olha as voltas antigas.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config  # noqa: E402
from ml.data import ai_detector as det  # noqa: E402
from ml.data import origin  # noqa: E402
from ml.data.inventory import inventory_path, save_inventory  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from ml.validation import controlled as ctl  # noqa: E402
from ml.validation import empirical as em  # noqa: E402

SESSION_DATE = "2026-10-04"
ANNOTATIONS = config.repo_root() / "docs" / "experimentos" / "2026-10-04_sessao_rotulada_anotacoes.csv"
BICO_DE_PATO_M = (2590.0, 3080.0)
# As datas que o piloto lembra de ter usado a IA (pedido 12/13) e as 4 sessoes
# que mais variam nos sinais do pedido 12.
AI_DATES_CITED = ("2026-06-14", "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19",
                  "2026-06-20", "2026-08-09")
VARIABLE_SESSIONS = ("2026-06-19_23-24-46", "2026-06-20_13-13-02", "2026-08-16_03-30-14", "2026-08-19_20-58-36")
EFFECTS_MS = (15, 30, 50)

# Escolhidos olhando so a sessao rotulada (docs/detector_ia.md):
# * 0,25 m: em 40 dos 60 microsetores toda volta da IA fica ate 0,25 m da
#   referencia sem ela; o piloto tem mediana de 1 a 2 m;
# * 0,30 m: abaixo disto e acima de 0,25 m o microsetor fica indefinido;
# * trechos: as voltas do piloto passam perto da IA em no maximo 2
#   microsetores seguidos, e a IA pilota trechos de 20 ou mais;
# * frenagem: a IA repete o inicio de frenagem com ate 4 m nas zonas
#   confiaveis; o piloto tem mediana de 44 a 117 m.
CALIBRATION = {
    "lateral_ai_m": 0.25,
    "lateral_human_m": 0.30,
    "ai_run": 3,
    "human_run": 2,
    "braking_ai_m": 4.0,
    "braking_human_m": 8.0,
}


# ------------------------------------------------------------- dados ---

def load(out_dir: Path):
    inventory = pd.read_parquet(inventory_path(out_dir))
    grids = {
        lap_id: frame.sort_values("grid_index").reset_index(drop=True)
        for lap_id, frame in pd.read_parquet(out_dir / "grade_voltas.parquet").groupby("lap_id")
    }
    return inventory, grids


def annotations() -> Dict[tuple, Dict[str, str]]:
    with ANNOTATIONS.open(encoding="utf-8") as handle:
        return {(int(r["parte"]), int(r["volta_jogo"])): r for r in csv.DictReader(handle)}


def labelled_session(inventory: pd.DataFrame) -> pd.DataFrame:
    """Voltas de 2026-10-04 com a parte (1 = antes do reinicio) e a anotacao.

    O jogo foi reiniciado no meio da primeira gravacao: o contador volta a 1 e
    as voltas seguintes sao da parte 2, assim como todas as gravacoes depois.
    """
    rows = inventory[inventory["session_id"].str.startswith(SESSION_DATE)].copy()
    rows = rows.sort_values(["session_id", "sequence"])
    first = sorted(rows["session_id"].unique())[0]
    number = rows["game_lap_number"].fillna(rows["lap_number"]).astype(float)
    rows["volta_jogo"] = number
    part = []
    seen_reset = False
    previous = None
    for session_id, value in zip(rows["session_id"], number):
        if session_id != first:
            part.append(2)
            continue
        if previous is not None and value < previous:
            seen_reset = True
        previous = value
        part.append(2 if seen_reset else 1)
    rows["parte"] = part
    notes = annotations()
    rows["origem_anotada"] = [notes.get((p, int(v)), {}).get("origem_anotada") for p, v in zip(rows["parte"], number)]
    rows["box_anotado"] = [notes.get((p, int(v)), {}).get("box") == "sim" for p, v in zip(rows["parte"], number)]
    return rows


def clean_mask(rows: pd.DataFrame, grids, sectors) -> pd.Series:
    """Valida, unica, relogio conferido e sem box (anotado ou medido)."""
    ok = origin.driver_mask(rows, origins=None, equipment=None) & rows["valid"].astype(bool)
    measured_box = [bool(lap in grids and det.pit_lap(grids[lap], sectors)) for lap in rows["lap_id"]]
    return ok & ~rows.get("box_anotado", pd.Series(False, index=rows.index)).astype(bool) & ~pd.Series(measured_box, index=rows.index)


# --------------------------------------------------------- calibrar ---

def candidate_limits(ai_ids: List[str], grids, track, sectors) -> det.DetectorLimits:
    """Os parametros que dependem das voltas da IA: microsetores e zonas em que ela se repete.

    Cada volta da IA e medida contra a referencia feita sem ela (deixa-uma-fora).
    """
    reference = det.build_reference({i: grids[i] for i in ai_ids}, track)
    lateral, zones = [], []
    for lap_id in ai_ids:
        loo = det.build_reference({i: grids[i] for i in ai_ids if i != lap_id}, track)
        lateral.append(det.microsector_distances(grids[lap_id], loo, track, sectors)["lateral_m"].to_numpy(dtype=float))
        zones.append(det.zone_distances(grids[lap_id], reference.braking_s, track))
    return det.DetectorLimits(
        lateral_ai_m=CALIBRATION["lateral_ai_m"],
        lateral_human_m=CALIBRATION["lateral_human_m"],
        ai_run=CALIBRATION["ai_run"],
        human_run=CALIBRATION["human_run"],
        braking_ai_m=CALIBRATION["braking_ai_m"],
        braking_human_m=CALIBRATION["braking_human_m"],
        informative_microsectors=det.informative_microsectors(lateral, CALIBRATION["lateral_ai_m"]),
        braking_zones_m=det.reliable_zones(np.vstack(zones), reference.braking_s, CALIBRATION["braking_ai_m"]),
    )


def evaluate(rows: pd.DataFrame, lap_ids: List[str], ai_ids: List[str], grids, track, sectors, limits) -> List[Dict[str, object]]:
    """O detector nas voltas rotuladas; as da IA contra a referencia sem elas."""
    reference = det.build_reference({i: grids[i] for i in ai_ids}, track)
    out = []
    for lap_id in lap_ids:
        r = rows.loc[rows["lap_id"] == lap_id].iloc[0]
        ref = det.build_reference({i: grids[i] for i in ai_ids if i != lap_id}, track) if lap_id in ai_ids else reference
        verdict = det.classify_lap(grids[lap_id], float(r["duration_s"]), ref, track, sectors, limits)
        out.append({"lap_id": lap_id, "parte": int(r["parte"]), "volta_jogo": int(r["volta_jogo"]),
                    "anotada": r["origem_anotada"], "tempo_s": float(r["duration_s"]), **verdict})
    return out


def accuracy(results: List[Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    table = {}
    for label in (origin.AI, origin.HUMAN, origin.MIXED):
        subset = [r for r in results if r["anotada"] == label]
        table[label] = {
            "voltas": len(subset),
            "acertos": sum(r["origem_detector"] == label for r in subset),
            "desconhecidas": sum(r["origem_detector"] == origin.UNKNOWN for r in subset),
            "erradas": sum(r["origem_detector"] not in (label, origin.UNKNOWN) for r in subset),
        }
    return table


def calibrate(out_dir: Path, track, json_path: Path) -> Dict[str, object]:
    inventory, grids = load(out_dir)
    sectors = build_microsectors(track)
    rows = labelled_session(inventory)
    rows["limpa"] = clean_mask(rows, grids, sectors)

    # Indicador contra anotacao, em todas as voltas da sessao.
    comparison = []
    for _, r in rows.iterrows():
        comparison.append({
            "lap_id": r["lap_id"], "parte": int(r["parte"]), "volta_jogo": int(r["volta_jogo"]),
            "anotada": r["origem_anotada"], "indicador": r["origem_indicador"],
            "concorda": r["origem_anotada"] == r["origem_indicador"],
            "valida": bool(r["valid"]), "limpa": bool(r["limpa"]), "tempo_s": float(r["duration_s"]),
        })

    clean = rows[rows["limpa"]]
    ai_ids = [i for i in clean.loc[clean["origem_anotada"] == origin.AI, "lap_id"] if i in grids]
    human_ids = [i for i in clean.loc[clean["origem_anotada"] == origin.HUMAN, "lap_id"] if i in grids]
    mixed_ids = [i for i in rows.loc[(rows["origem_anotada"] == origin.MIXED) & rows["valid"].astype(bool), "lap_id"]
                 if i in grids]
    labelled = ai_ids + human_ids + mixed_ids

    limits = candidate_limits(ai_ids, grids, track, sectors)
    results = evaluate(rows, labelled, ai_ids, grids, track, sectors, limits)

    # Fora da amostra: calibra com a parte 2, testa na parte 1.
    part = dict(zip(rows["lap_id"], rows["parte"]))
    ai_2 = [i for i in ai_ids if part[i] == 2]
    limits_2 = candidate_limits(ai_2, grids, track, sectors)
    results_1 = evaluate(rows, [i for i in labelled if part[i] == 1], ai_2, grids, track, sectors, limits_2)

    result = {
        "voltas_da_sessao": len(rows),
        "indicador_contra_anotacao": comparison,
        "voltas_limpas": {"ia": ai_ids, "humano": human_ids},
        "voltas_misturadas_validas": mixed_ids,
        "limites_candidatos": limits.__dict__,
        "acerto_na_sessao": accuracy(results),
        "por_volta": results,
        "fora_da_amostra_calibra_parte2_testa_parte1": {
            "limites": limits_2.__dict__, "acerto": accuracy(results_1), "por_volta": results_1,
        },
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return result


# --------------------------------------------------------- variacao ---

def section_time(grid: pd.DataFrame, track, span) -> float:
    a, b = np.interp(span, track.s, grid["elapsed_s"].to_numpy(dtype=float))
    return float(b - a)


def spread_stats(values: np.ndarray) -> Dict[str, float]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 3:
        return {"n": int(values.size)}
    successive = np.diff(values)
    return {
        "n": int(values.size),
        "media": float(values.mean()),
        "dp": float(values.std(ddof=1)),
        "dp_robusto": float(1.4826 * np.median(np.abs(values - np.median(values)))),
        # Sem a tendencia da sessao (aprendizado, pneu, combustivel): o que os
        # blocos do experimento enxergam.
        "dp_diferencas_sucessivas": float(np.std(successive, ddof=1) / np.sqrt(2)),
    }


def power(n: int, sigma: float, effect: float, contrast: str, sims: int = 2000, seed: int = 13) -> float:
    """Chance de o IC 95 % do contraste excluir zero, no desenho em blocos do plano."""
    rng = np.random.default_rng(seed)
    plan = ctl.make_plan(laps_per_condition=n, warmup=0, seed=seed)
    conditions = plan["condicao"].to_numpy()
    blocks = plan["bloco"].to_numpy()
    shift = np.zeros(len(conditions))
    for code, weight in ctl.CONTRASTS[contrast].items():
        # Efeito so na condicao "tratada" do contraste.
        if weight > 0:
            shift[conditions == code] = effect
    hits = 0
    for _ in range(sims):
        times = 30.0 + shift + rng.normal(0.0, sigma, len(conditions))
        low, high = ctl.estimate_effects(times, conditions, blocks)[contrast]["ic95_s"]
        hits += int(low > 0 or high < 0)
    return hits / sims


def laps_needed(sigma: float, effect: float, contrast: str, target: float = 0.8, max_n: int = 400) -> Optional[int]:
    """Menor numero de voltas por condicao com poder >= alvo (busca pela formula, conferida por simulacao)."""
    z = 1.96 + 0.8416
    scale = 1.0 if contrast in ("frenagem", "linha") else 2.0   # efeito principal: 2n contra 2n
    guess = max(2, int(np.ceil(scale * (z * sigma / effect) ** 2)))
    n = max(2, guess - 2)
    while n <= max_n:
        if power(n, sigma, effect, contrast) >= target:
            return n
        n += 1
    return None


def variation(out_dir: Path, track, json_path: Path) -> Dict[str, object]:
    inventory, grids = load(out_dir)
    sectors = build_microsectors(track)
    rows = labelled_session(inventory)
    rows["limpa"] = clean_mask(rows, grids, sectors)
    clean = rows[rows["limpa"]].sort_values("inicio_epoch_s")
    corners = detect_corners(track)
    all_clean = [i for i in clean["lap_id"] if i in grids]
    windows = em.define_windows([grids[i]["brake"].to_numpy(dtype=float) for i in all_clean], track, corners)

    out: Dict[str, object] = {"janelas": windows.describe()}
    for label in (origin.HUMAN, origin.AI):
        ids = [i for i in clean.loc[clean["origem_anotada"] == label, "lap_id"] if i in grids]
        bico = np.array([section_time(grids[i], track, BICO_DE_PATO_M) for i in ids])
        feats = [em.lap_window_features(grids[i], windows, track) for i in ids]
        brake_sd, apex_sd = [], []
        for k in range(windows.count):
            b = np.array([f[k]["braking_point_s"] for f in feats], dtype=float)
            a = np.array([f[k]["lateral_apex_m"] for f in feats], dtype=float)
            b, a = b[np.isfinite(b)], a[np.isfinite(a)]
            brake_sd.append(float(np.std(b, ddof=1)) if b.size >= 3 else float("nan"))
            apex_sd.append(float(np.std(a, ddof=1)) if a.size >= 3 else float("nan"))
        times = clean.set_index("lap_id").loc[ids, "duration_s"].to_numpy(dtype=float)
        best = clean.set_index("lap_id").loc[ids, "duration_s"].idxmin() if ids else None
        out[label] = {
            "voltas_limpas": ids,
            "bico_de_pato_s": spread_stats(bico),
            "frenagem_dp_m_por_janela": dict(zip(windows.labels(), brake_sd)),
            "frenagem_dp_m_mediana": float(np.nanmedian(brake_sd)) if brake_sd else None,
            "apice_dp_m_por_janela": dict(zip(windows.labels(), apex_sd)),
            "apice_dp_m_mediana": float(np.nanmedian(apex_sd)) if apex_sd else None,
            "tempo_volta_s": spread_stats(times),
            "melhor_volta": {"lap_id": best, "tempo_s": float(times.min()) if ids else None},
        }

    human = out[origin.HUMAN]["bico_de_pato_s"]
    sizes = {}
    for key in ("dp_diferencas_sucessivas", "dp"):
        sigma = human.get(key)
        if not sigma:
            continue
        sizes[key] = {
            f"{ms}_ms": {
                contrast: laps_needed(sigma, ms / 1000.0, contrast) for contrast in ("frenagem", "B_menos_A")
            }
            for ms in EFFECTS_MS
        }
    out["tamanho_do_experimento"] = {
        "sigma_bico_de_pato_s": {k: human.get(k) for k in ("dp_diferencas_sucessivas", "dp")},
        "voltas_por_condicao_para_80pct": sizes,
        "como": "simulacao do plano em blocos (make_plan) analisado por estimate_effects, 2000 sessoes por n",
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return out


# ----------------------------------------------------------- aplicar ---

def apply(out_dir: Path, track, json_path: Path) -> Dict[str, object]:
    limits = det.LIMITS
    if limits is None:
        raise SystemExit("PARADO: os limites do detector ainda nao foram registrados (ai_detector.LIMITS).")
    inventory, grids = load(out_dir)
    sectors = build_microsectors(track)
    rows = labelled_session(inventory)
    rows["limpa"] = clean_mask(rows, grids, sectors)
    ai_ids = [i for i in rows.loc[rows["limpa"] & (rows["origem_anotada"] == origin.AI), "lap_id"] if i in grids]
    reference = det.build_reference({i: grids[i] for i in ai_ids}, track)
    # Os microsetores e as zonas registrados tem de ser os que a sessao da hoje.
    recomputed = candidate_limits(ai_ids, grids, track, sectors)
    if (recomputed.informative_microsectors != limits.informative_microsectors
            or recomputed.braking_zones_m != limits.braking_zones_m):
        raise SystemExit("PARADO: os microsetores ou as zonas registrados nao batem com a sessao rotulada.")

    # 1. Quanto o detector acerta na sessao rotulada (IA deixa-uma-fora).
    human_ids = [i for i in rows.loc[rows["limpa"] & (rows["origem_anotada"] == origin.HUMAN), "lap_id"] if i in grids]
    mixed_ids = [i for i in rows.loc[(rows["origem_anotada"] == origin.MIXED) & rows["valid"].astype(bool), "lap_id"]
                 if i in grids]
    scored = evaluate(rows, ai_ids + human_ids + mixed_ids, ai_ids, grids, track, sectors, limits)
    hits = accuracy(scored)

    # 2. Rotulos finais no inventario.
    out_inv = inventory.copy()
    for column in ("origem_detector", "motivo_detector", "linha_detector"):
        out_inv[column] = None
    by_id = out_inv.set_index("lap_id")
    session_rows = rows.set_index("lap_id")
    for lap_id, r in session_rows.iterrows():
        note = r["origem_anotada"]
        if note is None:
            continue
        by_id.at[lap_id, "origem"] = note
        by_id.at[lap_id, "origem_fonte"] = (
            origin.SOURCE_INDICATOR if r["origem_indicador"] == note else origin.SOURCE_ANNOTATION
        )
    old = by_id[(by_id["equipamento"] == origin.PREVIOUS_EQUIPMENT) & by_id["valid"].astype(bool) & by_id["duplicada_de"].isna()]
    for lap_id, r in old.iterrows():
        if lap_id not in grids:
            continue
        verdict = det.classify_lap(grids[lap_id], float(r["duration_s"]), reference, track, sectors, limits)
        by_id.at[lap_id, "origem_detector"] = verdict["origem_detector"]
        by_id.at[lap_id, "motivo_detector"] = verdict["motivo"]
        by_id.at[lap_id, "linha_detector"] = verdict["linha"]
        if verdict["origem_detector"] != origin.UNKNOWN:
            by_id.at[lap_id, "origem"] = verdict["origem_detector"]
            by_id.at[lap_id, "origem_fonte"] = origin.SOURCE_DETECTOR
    out_inv = by_id.reset_index()
    save_inventory(out_inv, out_dir)

    # 3. Por sessao.
    applied = out_inv[out_inv["lap_id"].isin(old.index)]
    sessions = []
    for session_id, laps in applied.groupby("session_id"):
        counts = laps["origem_detector"].fillna(origin.UNKNOWN).value_counts().to_dict()
        reasons = laps["motivo_detector"].fillna("-").value_counts().to_dict()
        sessions.append({
            "sessao": session_id, "pasta": laps["pasta"].iloc[0], "voltas": int(len(laps)),
            "humano": int(counts.get(origin.HUMAN, 0)), "ia": int(counts.get(origin.AI, 0)),
            "misturada": int(counts.get(origin.MIXED, 0)), "desconhecida": int(counts.get(origin.UNKNOWN, 0)),
            "box": int(reasons.get("box", 0)),
            "data_citada_com_ia": session_id[:10] in AI_DATES_CITED,
            "sessao_variavel_pedido_12": session_id[:19] in VARIABLE_SESSIONS,
            "motivos": reasons,
        })
    totals = applied["origem_detector"].fillna(origin.UNKNOWN).value_counts().to_dict()
    result = {
        "limites": limits.__dict__,
        "referencia_ia": {"voltas": ai_ids, "zonas_de_frenagem_m": [round(float(z), 1) for z in reference.braking_s]},
        "sessao_rotulada": {"acerto": hits, "voltas": scored},
        "voltas_antigas": {"aplicadas": int(len(applied)), "totais": totals,
                           "motivos": applied["motivo_detector"].fillna("-").value_counts().to_dict()},
        "sessoes": sessions,
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=["calibrar", "variacao", "aplicar"])
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "origem")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)
    track = load_geometry()
    json_path = args.json or (args.saida / f"detector_{args.comando}.json")
    run = {"calibrar": calibrate, "variacao": variation, "aplicar": apply}[args.comando]
    result = run(args.saida, track, json_path)
    print(json.dumps({k: v for k, v in result.items() if k not in ("por_volta", "indicador_contra_anotacao",
                                                                     "microsetores_das_misturadas", "sessoes")},
                     indent=1, ensure_ascii=False, default=float)[:6000])
    print(f"\n-> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
