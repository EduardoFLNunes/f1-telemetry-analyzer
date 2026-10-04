"""Origem e confiabilidade das voltas (pedido 12, ADR 0014).

    python -m ml.scripts.report_lap_origin [--saida data/ml/origem] [--json ARQUIVO]
    python -m ml.scripts.report_lap_origin --remarcar [--saida ...] [--json ...]

A primeira forma varre as duas pastas de gravacoes (so leitura) e grava em
`--saida`, sem tocar no inventario nem no store em uso:

* `lap_inventory.parquet`: o inventario com `origem`, `pasta`, `relogio_*` e
  `duplicada_de`;
* `relogio_microsetores.parquet`: relogio x velocidade por microsetor;
* `sinais_voltas.parquet`: os sinais candidatos IA x piloto de cada volta;
* `grade_voltas.parquet`: freio, acelerador, lateral, velocidade e tempo na
  grade, para as dispersoes entre voltas.

`--remarcar` refaz so a marca do relogio (com `origin.CLOCK_LIMIT_S`) e o
relatorio a partir desses arquivos, sem varrer de novo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml import config  # noqa: E402
from ml.data import origin  # noqa: E402
from ml.data.inventory import inventory_path, save_inventory, scan_sessions, summarise  # noqa: E402
from ml.data.origin_signals import lap_signals  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from ml.validation import empirical as em  # noqa: E402

CLOCK_TABLE = "relogio_microsetores.parquet"
SIGNALS_TABLE = "sinais_voltas.parquet"
GRID_TABLE = "grade_voltas.parquet"
GRID_COLUMNS = ("brake", "throttle", "lateral", "speed_kmh", "elapsed_s")

# Bico de Pato, como na Fase 2b (janela J6).
BICO_DE_PATO_M = (2590.0, 3080.0)

# As tres voltas "impossiveis" do pedido 11 (identidade do coach).
PEDIDO_11_LAPS = (
    "rec__2026-08-08_13-18-00_vhe_interlagos__67",
    "rec__2026-08-19_20-58-36_vhe_interlagos__9",
    "rec__2026-08-16_03-30-14_vhe_interlagos__5",
)

# Datas em que o piloto disse que a IA pilotou parte das sessoes (pedido 12).
# Nao e rotulo: as sessoes alternam IA e piloto, e a lista e de memoria.
AI_DATES_CITED = (
    "2026-06-14", "2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19",
    "2026-06-20", "2026-08-09",
)

SIGNAL_COLUMNS = (
    "volante_taxa_p95",
    "volante_reversoes_km",
    "acelerador_parcial",
    "freio_parcial",
    "freio_pico_mediano",
    "freio_subida_s",
    "troca_rpm_mediana",
    "troca_rpm_dp",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def scan(out_dir: Path, track) -> None:
    sessions = list_all_sessions()
    print(f"sessoes de Interlagos nas duas pastas: {len(sessions)}", flush=True)
    clocks: List[pd.DataFrame] = []
    signals: List[Dict[str, float]] = []
    grids: List[pd.DataFrame] = []

    def hook(lap, aligned, grid, check, row):
        block = check.copy()
        block.insert(0, "lap_id", lap.lap_id)
        clocks.append(block)
        signals.append({"lap_id": lap.lap_id, **lap_signals(aligned, track.length)})
        g = grid.reindex(columns=list(GRID_COLUMNS)).astype("float32")
        g.insert(0, "grid_index", np.arange(len(g), dtype=np.int32))
        g.insert(0, "lap_id", lap.lap_id)
        grids.append(g)

    inventory = scan_sessions(sessions, track=track, progress=lambda t: print(t, flush=True), lap_hook=hook)
    save_inventory(inventory, out_dir)
    pd.concat(clocks, ignore_index=True).to_parquet(out_dir / CLOCK_TABLE, index=False)
    pd.DataFrame(signals).to_parquet(out_dir / SIGNALS_TABLE, index=False)
    pd.concat(grids, ignore_index=True).to_parquet(out_dir / GRID_TABLE, index=False)


def percentiles(values: np.ndarray) -> Dict[str, float]:
    values = values[np.isfinite(values)]
    qs = (0, 1, 5, 25, 50, 75, 95, 99, 99.9, 100)
    return {f"p{q:g}": round(float(np.percentile(values, q)), 4) for q in qs} | {"n": int(values.size)}


def clock_distribution(inventory: pd.DataFrame, clock: pd.DataFrame) -> Dict[str, object]:
    usable = inventory[inventory["valid"] & inventory["duplicada_de"].isna()]
    rows = clock[clock["lap_id"].isin(usable["lap_id"])]
    difference = rows["diferenca_s"].to_numpy(dtype=float)
    worst = usable["relogio_pior_s"].abs().to_numpy(dtype=float)
    by_sector = rows.groupby("microsetor")["diferenca_s"]
    return {
        "voltas": int(len(usable)),
        "microsetores": int(len(rows)),
        "diferenca_s": percentiles(difference),
        "diferenca_abs_s": percentiles(np.abs(difference)),
        "pior_por_volta_abs_s": percentiles(worst),
        "voltas_com_pior_acima_de_s": {
            str(t): int((worst > t).sum()) for t in (0.02, 0.03, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)
        },
        "por_microsetor": [
            {
                "microsetor": int(k),
                "mediana_s": round(float(v.median()), 4),
                "p1_s": round(float(v.quantile(0.01)), 4),
                "p99_s": round(float(v.quantile(0.99)), 4),
            }
            for k, v in by_sector
        ],
    }


def window_dispersion(rows: List[List[Dict[str, float]]], count: int) -> Dict[str, float]:
    """Dispersao (dp entre voltas) do ponto de frenagem e da lateral no apice."""
    if len(rows) < 3:
        return {"frenagem_dp_m": float("nan"), "apice_dp_m": float("nan"), "voltas_janela": len(rows)}
    brake_sd, apex_sd = [], []
    for k in range(count):
        points = np.array([r[k]["braking_point_s"] for r in rows], dtype=float)
        points = points[np.isfinite(points)]
        if points.size >= 3:
            brake_sd.append(float(np.std(points, ddof=1)))
        apex = np.array([r[k]["lateral_apex_m"] for r in rows], dtype=float)
        apex = apex[np.isfinite(apex)]
        if apex.size >= 3:
            apex_sd.append(float(np.std(apex, ddof=1)))
    return {
        "frenagem_dp_m": float(np.median(brake_sd)) if brake_sd else float("nan"),
        "apice_dp_m": float(np.median(apex_sd)) if apex_sd else float("nan"),
        "voltas_janela": len(rows),
    }


def lap_deviation(features: List[Dict[str, float]], medians: Dict[str, np.ndarray]) -> Dict[str, float]:
    """Quanto uma volta se afasta da mediana da pista: frenagem e apice, mediana entre janelas.

    E um sinal por volta, e nao por sessao: numa sessao que alterna IA e
    piloto, as voltas de cada um podem cair em grupos diferentes.
    """
    out = {}
    for key, name in (("braking_point_s", "frenagem_desvio_m"), ("lateral_apex_m", "apice_desvio_m")):
        values = np.array([f[key] for f in features], dtype=float)
        deviation = np.abs(values - medians[key])
        deviation = deviation[np.isfinite(deviation)]
        out[name] = float(np.median(deviation)) if deviation.size else float("nan")
    return out


def spread(values: np.ndarray) -> Dict[str, float]:
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"p10": float("nan"), "p50": float("nan"), "p90": float("nan")}
    return {f"p{q}": float(np.percentile(values, q)) for q in (10, 50, 90)}


def section_time(frame: pd.DataFrame, track, span) -> float:
    elapsed = frame.sort_values("grid_index")["elapsed_s"].to_numpy(dtype=float)
    a, b = np.interp(span, track.s, elapsed)
    return float(b - a)


def robust_sd(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size < 3:
        return float("nan")
    return float(1.4826 * np.median(np.abs(values - np.median(values))))


def report(out_dir: Path, track, json_path: Path) -> Dict[str, object]:
    inventory = pd.read_parquet(inventory_path(out_dir))
    inventory = origin.mark_clock(inventory)
    save_inventory(inventory, out_dir)
    clock = pd.read_parquet(out_dir / CLOCK_TABLE)
    signals = pd.read_parquet(out_dir / SIGNALS_TABLE)
    grids = {
        lap_id: frame.sort_values("grid_index").reset_index(drop=True)
        for lap_id, frame in pd.read_parquet(out_dir / GRID_TABLE).groupby("lap_id")
    }

    distribution = clock_distribution(inventory, clock)

    # As 3 voltas do pedido 11, na identidade do ml.
    p11 = []
    for replay in PEDIDO_11_LAPS:
        mapped = inventory[inventory.get("replay_lap_id") == replay]
        for _, row in mapped.iterrows():
            rows = clock[clock["lap_id"] == row["lap_id"]]
            worst = rows.reindex(rows["diferenca_s"].abs().sort_values(ascending=False).index).head(3)
            p11.append(
                {
                    "volta_coach": replay,
                    "volta_ml": row["lap_id"],
                    "pasta": row.get("pasta"),
                    "valida": bool(row["valid"]),
                    "motivos": row.get("reasons"),
                    "duplicada_de": row.get("duplicada_de"),
                    "relogio_verificado": bool(row.get("relogio_verificado", False)),
                    "relogio_pior_s": None if pd.isna(row.get("relogio_pior_s")) else round(float(row["relogio_pior_s"]), 4),
                    "relogio_pior_microsetor": (
                        None if pd.isna(row.get("relogio_pior_microsetor")) else int(row["relogio_pior_microsetor"])
                    ),
                    "relogio_suspeito": None if "relogio_suspeito" not in row else bool(row["relogio_suspeito"]),
                    "piores_microsetores": [
                        {k: (round(float(v), 4) if isinstance(v, float) else int(v)) for k, v in r.items() if k != "lap_id"}
                        for r in worst.to_dict(orient="records")
                    ],
                }
            )

    # Os sinais saem das voltas validas, unicas e com o relogio conferido: uma
    # passagem pelo box ou uma parada mudaria o tempo e a frenagem por motivos
    # que nao tem nada a ver com quem pilotou.
    usable = inventory[inventory["valid"] & inventory["duplicada_de"].isna()]
    clean_laps = origin.select_laps(usable, origins=None)
    complete = [i for i in clean_laps["lap_id"] if i in grids and len(grids[i]) == track.size]
    # Zonas de frenagem e janelas da Fase 2b, sobre essas voltas.
    corners = detect_corners(track)
    windows = em.define_windows([grids[i]["brake"].to_numpy(dtype=float) for i in complete], track, corners)
    features = {i: em.lap_window_features(grids[i], windows, track) for i in complete}
    medians = {
        key: np.array(
            [np.nanmedian(np.array([features[i][k][key] for i in complete], dtype=float)) for k in range(windows.count)],
            dtype=float,
        )
        for key in ("braking_point_s", "lateral_apex_m")
    }
    deviations = pd.DataFrame([{"lap_id": i, **lap_deviation(features[i], medians)} for i in complete])
    deviations.to_parquet(out_dir / "desvios_voltas.parquet", index=False)

    merged = clean_laps.merge(signals, on="lap_id", how="left").merge(deviations, on="lap_id", how="left")
    sessions = []
    for session_id, laps in inventory.groupby("session_id"):
        unique_valid = usable[usable["session_id"] == session_id]
        clean = merged[merged["session_id"] == session_id]
        times = clean["duration_s"].to_numpy(dtype=float)
        bico = [section_time(grids[i], track, BICO_DE_PATO_M) for i in clean["lap_id"] if i in grids]
        with_field = int(laps["ia_amostras_com_campo"].sum())
        raw = int(laps["raw_samples"].sum())
        ai_samples = float((laps["ia_fracao"].fillna(0) * laps["ia_amostras_com_campo"]).sum())
        row = {
            "sessao": session_id,
            "pasta": laps["pasta"].iloc[0],
            "data": session_id[:10],
            "data_citada_com_ia": session_id[:10] in AI_DATES_CITED,
            "amostras_nas_voltas": raw,
            "campo_ia_existe": with_field > 0,
            "amostras_com_campo_ia": with_field,
            "fracao_amostras_ia": (ai_samples / with_field) if with_field else None,
            "voltas": int(len(laps)),
            "voltas_validas": int(laps["valid"].sum()),
            "voltas_duplicadas": int(laps["duplicada_de"].notna().sum()),
            "voltas_validas_unicas": int(len(unique_valid)),
            "voltas_limpas": int(len(clean)),
            "origem": laps["origem"].value_counts().to_dict(),
            "relogio_suspeito_validas": (
                int(unique_valid["relogio_suspeito"].fillna(False).astype(bool).sum())
                if "relogio_suspeito" in unique_valid
                else None
            ),
            "hz_mediana": float(np.nanmedian(clean["sample_hz"])) if len(clean) else None,
            "melhor_volta_s": float(np.nanmin(times)) if times.size else None,
            "tempo_volta_mediana_s": float(np.nanmedian(times)) if times.size else None,
            "tempo_volta_dp_robusto_s": robust_sd(times),
            "bico_de_pato_dp_robusto_s": robust_sd(np.asarray(bico, dtype=float)),
        }
        for column in SIGNAL_COLUMNS:
            values = clean[column].to_numpy(dtype=float) if column in clean else np.array([])
            row[column] = float(np.nanmedian(values)) if np.isfinite(values).any() else None
        row.update(window_dispersion([features[i] for i in clean["lap_id"] if i in features], windows.count))
        for column in ("frenagem_desvio_m", "apice_desvio_m"):
            values = clean[column].to_numpy(dtype=float) if column in clean else np.array([])
            row[column] = spread(values)
        sessions.append(row)

    def clean(value):
        if isinstance(value, float) and not np.isfinite(value):
            return None
        if isinstance(value, (np.floating,)):
            return clean(float(value))
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        if isinstance(value, dict):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    files = {
        name: out_dir / name
        for name in (inventory_path(out_dir).name, CLOCK_TABLE, SIGNALS_TABLE, GRID_TABLE, "desvios_voltas.parquet")
    }
    result = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pastas": {label: str(path) for label, path in config.recordings_roots().items()},
        "limite_relogio_s": origin.CLOCK_LIMIT_S,
        "inventario": summarise(inventory),
        "relogio": distribution,
        "voltas_pedido_11": p11,
        "janelas_fase2b": windows.describe(),
        "voltas_usadas_nos_sinais": len(complete),
        "sinais_por_volta_distribuicao": {
            column: spread(merged[column].to_numpy(dtype=float))
            for column in SIGNAL_COLUMNS + ("frenagem_desvio_m", "apice_desvio_m")
            if column in merged
        },
        "sessoes": sessions,
        "arquivos": {name: {"caminho": str(path), "sha256": sha256(path)} for name, path in files.items()},
    }
    result = clean(result)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "origem")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--remarcar", action="store_true", help="nao varre: refaz a marca e o relatorio")
    args = parser.parse_args(argv)

    started = time.time()
    track = load_geometry()
    args.saida.mkdir(parents=True, exist_ok=True)
    if not args.remarcar:
        scan(args.saida, track)
    result = report(args.saida, track, args.json or (args.saida / "relatorio_origem.json"))

    d = result["relogio"]
    print(f"\nlimite do relogio: {result['limite_relogio_s']}")
    print(f"voltas validas e unicas: {d['voltas']}  microsetores: {d['microsetores']}")
    print("diferenca relogio - velocidade (s):", d["diferenca_s"])
    print("|diferenca| (s):", d["diferenca_abs_s"])
    print("pior |diferenca| por volta (s):", d["pior_por_volta_abs_s"])
    print("voltas com pior acima de:", d["voltas_com_pior_acima_de_s"])
    print("\nvoltas do pedido 11:")
    for row in result["voltas_pedido_11"]:
        print("  ", json.dumps(row, ensure_ascii=False))
    print(f"\n({time.time() - started:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
