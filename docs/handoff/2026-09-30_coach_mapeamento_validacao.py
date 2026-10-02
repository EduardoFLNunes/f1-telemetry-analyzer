"""Validacao do mapeamento p -> s dos alvos do coach, antes e depois da correcao.

    cd backend
    python ../docs/handoff/2026-09-30_coach_mapeamento_validacao.py [--recordings DIR]

Le `data/ml/laps_grid.parquet` (voltas validas ja na grade `s` do ML, com a
posicao no mundo de cada ponto) e a geometria atual. Para cada amostra real, o
trecho do coach e o que o runtime daria hoje: `p` do `ProjectionEngine` sobre o
cache atual, a partir da posicao no mundo. Os alvos sao cortados na volta de
referencia do ML pelo mapeamento antigo (vetor `p` por indice + poligonal crua)
e pelo novo (`progress_to_distance(track=...)`).

Nada e gravado fora do JSON de saida; o `optimal.json` nao e tocado.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path.cwd()
sys.path.insert(0, str(BACKEND))

from ml import config  # noqa: E402
from ml.comparison.reference_frame import reference_lap_frame  # noqa: E402
from ml.export import coaching  # noqa: E402
from ml.optimization.vehicle_model import load_envelope  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from core.cache.cache_serializer import CacheSerializer  # noqa: E402
from core.projection.spatial_projection import ProjectionEngine  # noqa: E402

SLICES = coaching.COACH_MICROSECTORS
BRAKE_ON = 0.10
NATIVE_SESSIONS = ("2026-08-16_03-30-14_vhe_interlagos", "2026-08-16_03-58-36_vhe_interlagos")
OUTLIER_SESSION = "2026-06-20_13-13-02_vhe_interlagos"


def old_progress_to_distance(raw: dict, length: float):
    """O mapeamento de `handoff/fase1`, reconstruido: `p` por indice + poligonal crua."""
    centre = np.array([[p["x"], p["z"]] for p in raw["centerline"]], dtype=float)
    cumulative = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(centre, axis=0), axis=1))])
    progress = np.asarray(raw["p"], dtype=float)
    distance = cumulative / cumulative[-1] * length
    return lambda v: np.interp(np.asarray(v, dtype=float), progress, distance)


def edges_for(s_of_p, length: float) -> np.ndarray:
    edges = s_of_p(np.arange(SLICES + 1, dtype=float) / SLICES)
    edges[0], edges[-1] = 0.0, length
    return edges


def first_brake(s: np.ndarray, brake: np.ndarray):
    on = np.flatnonzero(brake >= BRAKE_ON)
    return float(s[on[0]]) if on.size else None


def target_slices(frame: pd.DataFrame, edges: np.ndarray) -> list:
    s = frame["s"].to_numpy(float)
    v = frame["speed_kmh"].to_numpy(float)
    b = frame["brake"].to_numpy(float)
    out = []
    for k in range(SLICES):
        sel = (s >= edges[k]) & (s < edges[k + 1])
        i = np.flatnonzero(sel)
        vmin_i = i[np.argmin(v[i])]
        out.append(
            {
                "s_start": round(float(edges[k]), 2),
                "s_end": round(float(edges[k + 1]), 2),
                "vmin_kmh": round(float(v[vmin_i]), 1),
                "vmin_s": round(float(s[vmin_i]), 1),
                "brake_s": first_brake(s[i], b[i]),
            }
        )
    return out


def real_slices(lap: pd.DataFrame) -> list:
    """Por trecho do runtime (p do ProjectionEngine), o que a volta real fez."""
    out = []
    for k in range(SLICES):
        part = lap[lap["slice"] == k]
        if part.empty:
            out.append(None)
            continue
        s = part["s"].to_numpy(float)
        v = part["speed_kmh"].to_numpy(float)
        i = int(np.argmin(v))
        out.append(
            {
                "vmin_kmh": float(v[i]),
                "vmin_s": float(s[i]),
                "brake_s": first_brake(s, part["brake"].to_numpy(float)),
                "s_start": float(s[0]),
            }
        )
    return out


def wrap(d, length):
    return (np.asarray(d, float) + length / 2.0) % length - length / 2.0


def compare(targets: list, laps: dict, length: float) -> dict:
    """Desvio alvo - real por trecho, mediana sobre as voltas."""
    per_slice = []
    for k in range(SLICES):
        t = targets[k]
        reals = [r[k] for r in laps.values() if r[k] is not None]
        edge = [wrap(t["s_start"] - r["s_start"], length) for r in reals] if k else []
        vpos = [wrap(t["vmin_s"] - r["vmin_s"], length) for r in reals]
        vval = [t["vmin_kmh"] - r["vmin_kmh"] for r in reals]
        both = [r for r in reals if r["brake_s"] is not None]
        brake = (
            [wrap(t["brake_s"] - r["brake_s"], length) for r in both] if t["brake_s"] is not None else []
        )
        real_brakes = len(both) / len(reals) if reals else None
        per_slice.append(
            {
                "slice": k,
                "laps": len(reals),
                "edge_offset_m": None if not edge else round(float(np.median(edge)), 2),
                "vmin_pos_offset_m": round(float(np.median(vpos)), 1),
                "vmin_value_offset_kmh": round(float(np.median(vval)), 1),
                "target_brakes": t["brake_s"] is not None,
                "share_of_real_laps_braking": None if real_brakes is None else round(real_brakes, 3),
                "brake_pos_offset_m": None if not brake else round(float(np.median(brake)), 1),
            }
        )

    def agg(key):
        values = np.abs([row[key] for row in per_slice if row[key] is not None])
        return {
            "median_abs": round(float(np.median(values)), 2),
            "p90_abs": round(float(np.percentile(values, 90)), 2),
            "max_abs": round(float(values.max()), 2),
            "slices": int(values.size),
        }

    brake_agree = [
        row["target_brakes"] == (row["share_of_real_laps_braking"] >= 0.5)
        for row in per_slice
        if row["share_of_real_laps_braking"] is not None
    ]
    return {
        "summary": {
            "edge_offset_m": agg("edge_offset_m"),
            "vmin_pos_offset_m": agg("vmin_pos_offset_m"),
            "vmin_value_offset_kmh": agg("vmin_value_offset_kmh"),
            "brake_pos_offset_m": agg("brake_pos_offset_m"),
            "slices_where_target_and_majority_agree_on_braking": int(sum(brake_agree)),
        },
        "per_slice": per_slice,
    }


def native_p_check(recordings: Path, engine, length: float) -> dict:
    """Nas sessoes nativas, o p reprojetado tem de ser o p gravado."""
    gaps = []
    for session in NATIVE_SESSIONS:
        with (recordings / session / "player.jsonl").open(encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i % 400:
                    continue
                s = json.loads(line).get("sample") or {}
                if s.get("world_x") is None or s.get("p") is None:
                    continue
                gap = abs(engine.project_car(s["world_x"], s["world_z"])["p"] - s["p"])
                gaps.append(min(gap, 1.0 - gap) * length)
    gaps = np.asarray(gaps)
    return {
        "samples": int(gaps.size),
        "median_m": round(float(np.median(gaps)), 4),
        "max_m": round(float(gaps.max()), 4),
    }


def investigate_outlier(recordings: Path, track, engine, length: float, s_of_p) -> dict:
    """A amostra de 15,9 m: onde fica e por que."""
    rows = []
    path = recordings / OUTLIER_SESSION / "player.jsonl"
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i % 10:
                continue
            s = json.loads(line).get("sample") or {}
            if s.get("world_x") is not None:
                rows.append((i, s["world_x"], s["world_z"], s.get("speedKmh"), s.get("lap_time")))
    xz = np.array([[r[1], r[2]] for r in rows])
    ml_s, ml_l = track.project_sequence(xz)
    projections = [engine.project_car(x, z) for x, z in xz]
    p = np.array([q["p"] for q in projections])
    gap = np.abs(wrap(s_of_p(p) - ml_s, length))
    on = np.abs(ml_l) < 10
    worst = np.argsort(np.where(on, gap, -1))[::-1][:8]
    details = []
    for j in worst:
        q = projections[j]
        neighbours = []
        for d in (-2, -1, 1, 2):
            if 0 <= j + d < len(p):
                neighbours.append(round(float(gap[j + d]), 2))
        details.append(
            {
                "line": int(rows[j][0]),
                "world": [round(float(xz[j, 0]), 2), round(float(xz[j, 1]), 2)],
                "speed_kmh": rows[j][3],
                "ml_s": round(float(ml_s[j]), 2),
                "ml_lateral": round(float(ml_l[j]), 2),
                "runtime_s": round(float(q["distanceAlongTrack"]), 2),
                "runtime_segment": int(q["nearest_segment_index"]),
                "runtime_distance_to_track": round(float(q["debug"]["distanceToTrack"]), 2),
                "mapped_minus_ml_m": round(float(gap[j]), 2),
                "neighbours_gap_m": neighbours,
            }
        )
    # Diagnostico: onde a centerline crua (a que o runtime projeta) se afasta da
    # centerline consertada do ML.
    centre = np.asarray(engine.points, dtype=float)
    distance = np.array(engine.distances, dtype=float)
    _, vertex_lateral = track.project(centre)
    far = np.flatnonzero(np.abs(vertex_lateral) > 2.0)
    regions = []
    if far.size:
        starts = far[np.r_[True, np.diff(far) > 1]]
        ends = far[np.r_[np.diff(far) > 1, True]]
        for a, b in zip(starts, ends):
            regions.append(
                {
                    "vertices": [int(a), int(b)],
                    "runtime_distance_m": [round(float(distance[a]), 1), round(float(distance[b]), 1)],
                    "max_lateral_offset_m": round(float(np.abs(vertex_lateral[a : b + 1]).max()), 2),
                }
            )
    return {
        "samples": int(on.sum()),
        "gap_over_2m": int((gap[on] > 2).sum()),
        "gap_over_5m": int((gap[on] > 5).sum()),
        "raw_centerline_regions_over_2m_from_ml_line": regions,
        "diagnosis": (
            "Nao e erro do mapeamento. A centerline crua do cache (a que o ProjectionEngine usa) "
            "esta deslocada ~10,8 m de lado nas regioes acima -- defeito de reconstrucao que "
            "load_geometry conserta e o runtime nao. Um carro na pista real em s_ML ~775-784 fica "
            "mais perto da diagonal dos segmentos 484-485 (que volta a linha certa) do que dos "
            "vertices deslocados, e o runtime o projeta ate ~30 m a frente por algumas amostras. "
            "O p do runtime salta; o mapeamento novo leva corretamente esse p ao s_ML do vertice."
        ),
        "worst": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recordings", type=Path, default=config.recordings_root())
    parser.add_argument(
        "--out", type=Path, default=BACKEND.parent / "docs" / "handoff" / "2026-09-30_coach_mapeamento_resultados.json"
    )
    args = parser.parse_args()

    cache = config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE
    text = cache.read_text(encoding="utf-8")
    raw = json.loads(text)
    track = load_geometry(cache)
    engine = ProjectionEngine(CacheSerializer.deserialize_track(text)["centerline"])
    length = float(track.length)

    lateral = np.load(config.artifacts_root() / "optimization" / "optimised_lateral.npy")
    frame = reference_lap_frame(track, lateral, load_envelope())

    mappings = {
        "antes": old_progress_to_distance(raw, length),
        "depois": coaching.progress_to_distance(cache, track=track),
    }
    targets = {name: target_slices(frame, edges_for(f, length)) for name, f in mappings.items()}

    grid = pd.read_parquet(config.artifacts_root() / "laps_grid.parquet")
    grid["s"] = track.s[grid["grid_index"].to_numpy(int)]
    ok = grid[["x", "z"]].notna().all(axis=1)
    grid = grid[ok].copy()
    grid["p"] = [engine.project_car(x, z)["p"] for x, z in grid[["x", "z"]].to_numpy()]
    grid["slice"] = np.minimum((grid["p"] * SLICES).astype(int), SLICES - 1)
    grid = grid.sort_values(["lap_id", "grid_index"])
    grid["session_id"] = grid["lap_id"].str.split("#").str[0]

    laps_all = {lap_id: real_slices(lap) for lap_id, lap in grid.groupby("lap_id")}
    native = {k: v for k, v in laps_all.items() if k.split("#")[0] in NATIVE_SESSIONS}

    result = {
        "description": (
            "Alvo - volta real por trecho do coach (60). Trecho real = p do ProjectionEngine atual "
            "sobre a posicao no mundo. Distancias em s da grade do ML. 'antes' = mapeamento de "
            "handoff/fase1; 'depois' = progress_to_distance(track=...). Offsets: mediana sobre as "
            "voltas; summary agrega |offset| sobre os trechos."
        ),
        "brake_threshold": BRAKE_ON,
        "geometry_id": track.geometry_id,
        "track_length_m": length,
        "reference_lap_s": float(frame["lap_time_s"].iloc[0]),
        "datasets": {
            "nativo": {
                "sessions": sorted({k.split("#")[0] for k in native}),
                "laps": len(native),
                "note": "gravadas com a geometria atual (total 4334,08 m)",
            },
            "reprojetado": {
                "sessions": sorted({k.split("#")[0] for k in laps_all}),
                "laps": len(laps_all),
                "note": "todas as voltas validas do lap store; p recalculado pelo ProjectionEngine atual",
            },
        },
        "targets": targets,
        "comparison": {},
    }
    for dataset, laps in (("nativo", native), ("reprojetado", laps_all)):
        result["comparison"][dataset] = {name: compare(t, laps, length) for name, t in targets.items()}

    result["native_p_check"] = native_p_check(args.recordings, engine, length)
    result["outlier_15_9m"] = investigate_outlier(args.recordings, track, engine, length, mappings["depois"])

    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for dataset in ("nativo", "reprojetado"):
        print(f"== {dataset}: {result['datasets'][dataset]['laps']} voltas")
        for name in ("antes", "depois"):
            print(f"  {name:6s}", json.dumps(result["comparison"][dataset][name]["summary"]))
    print(json.dumps(result["outlier_15_9m"], indent=1)[:3000])
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
