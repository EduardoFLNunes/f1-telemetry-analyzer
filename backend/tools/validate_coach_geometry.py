"""Validacao do coach na geometria oficial (ADR 0013), criterios a-d do pedido 11.

    python tools/validate_coach_geometry.py --geometria-arquivo G.json --modelo M.json --saida DIR

Criterios fixados antes da primeira execucao (constantes abaixo):

a  Fidelidade: projecao do coach contra `TrackGeometry.project_sequence`, nas
   mesmas amostras das voltas validas, em uma sessao de cada origem
   (MergeFix, cache atual, sem cache). Cada sessao precisa passar sozinha:
   p99 |ds| <= 0,5 m e p99 |dd| <= 0,2 m. O maximo e relatado.
   O coach projeta a sessao inteira, amostra por amostra e na ordem gravada,
   com um projetor so (como ao vivo); o `ml` projeta volta a volta.
b  Tempo de projecao por amostra, nas mesmas amostras de a: p99 <= 1 ms.
c  Tempos por microsetor do coach (volta lida pelo carregador do app,
   reprojetada) contra os do store, nas mesmas fronteiras, na volta valida
   mais rapida de 5 sessoes diferentes: diferenca maxima <= 0,02 s por
   microsetor e soma dos microsetores = tempo da volta do store +- 0,02 s.
d  Ensaio: o coach novo, com o modelo dado, roda amostra por amostra na ordem
   gravada sobre duas sessoes inteiras (20/06 e 09/08). Todas as frases sao
   salvas; nenhuma pode conter "ganh", "ideal" ou "otimo". O intervalo minimo
   entre falas e zerado, como no replay (`coach_recorded_lap`): o de 3 s usa o
   relogio da maquina e, numa reproducao rapida, calaria quase tudo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.assisted_analysis.lap_loader import LapDataLoader  # noqa: E402
from core.assisted_analysis.official_geometry import OfficialGeometry, project_lap  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel, microsector_splits  # noqa: E402
from core.live.driving_coach import LiveDrivingCoach  # noqa: E402
from core.live.runtime_state import RuntimeState  # noqa: E402
from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402
from ml import config  # noqa: E402
from ml.data.lap_store import load_store  # noqa: E402
from ml.data.recordings import iter_laps, list_sessions  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors, split_times  # noqa: E402

A_P99_DS_M = 0.5
A_P99_DD_M = 0.2
B_P99_MS = 1.0
C_MAX_SECTOR_S = 0.02
C_SUM_S = 0.02
D_FORBIDDEN = ("ganh", "ideal", "otimo")

A_SESSIONS = {
    "MergeFix": "2026-06-20_13-13-02_vhe_interlagos",
    "cache atual": "2026-08-16_03-30-14_vhe_interlagos",
    "sem cache": "2026-08-09_19-20-59_vhe_interlagos",
}
D_SESSIONS = ("2026-06-20_13-13-02_vhe_interlagos", "2026-08-09_19-20-59_vhe_interlagos")


def stats(values: np.ndarray) -> Dict[str, float]:
    values = np.abs(values[np.isfinite(values)])
    return {
        "n": int(values.size),
        "p50": float(np.percentile(values, 50)),
        "p99": float(np.percentile(values, 99)),
        "max": float(values.max()),
    }


def criterion_a_b(geometry, track, store, sessions) -> Dict[str, object]:
    valid = set(store.lap_ids)
    out: Dict[str, object] = {"sessoes": {}}
    timings: List[float] = []
    for origin, session_id in A_SESSIONS.items():
        projector = geometry.projector()
        ds_all, dd_all = [], []
        laps_compared = 0
        for lap in iter_laps(sessions[session_id], min_samples=1):
            frame = lap.frame.dropna(subset=["x", "z"])
            points = frame[["x", "z"]].to_numpy(dtype=float)
            coach = np.empty((points.shape[0], 2))
            for index, (x, z) in enumerate(points):
                started = time.perf_counter()
                coach[index] = projector.project(x, z)
                timings.append(time.perf_counter() - started)
            if lap.lap_id not in valid or points.shape[0] < 10:
                continue
            s_ml, d_ml = track.project_sequence(points)
            ds = np.mod(coach[:, 0] - s_ml + track.length / 2, track.length) - track.length / 2
            ds_all.append(ds)
            dd_all.append(coach[:, 1] - d_ml)
            laps_compared += 1
        ds_stats = stats(np.concatenate(ds_all))
        dd_stats = stats(np.concatenate(dd_all))
        out["sessoes"][origin] = {
            "sessao": session_id,
            "voltas_validas_comparadas": laps_compared,
            "abs_ds_m": ds_stats,
            "abs_dd_m": dd_stats,
            "passou": ds_stats["p99"] <= A_P99_DS_M and dd_stats["p99"] <= A_P99_DD_M,
        }
    out["passou"] = all(v["passou"] for v in out["sessoes"].values())
    ms = np.array(timings) * 1000.0
    b = {
        "amostras": int(ms.size),
        "p50_ms": float(np.percentile(ms, 50)),
        "p99_ms": float(np.percentile(ms, 99)),
        "max_ms": float(ms.max()),
        "passou": float(np.percentile(ms, 99)) <= B_P99_MS,
    }
    return {"a": out, "b": b}


def criterion_c(geometry, track, store, loader) -> Dict[str, object]:
    sectors = build_microsectors(track)
    laps = store.laps.sort_values("lap_time_s")
    chosen = laps.drop_duplicates("session_id").head(5)
    loaded = loader.load_recorded_laps(chosen["replay_lap_id"].tolist())
    rows = []
    for lap in chosen.itertuples():
        _, df = loaded[lap.replay_lap_id]
        coach = microsector_splits(project_lap(df, geometry), geometry.microsectors)
        frame = store.lap(lap.lap_id)
        ml = split_times(frame["elapsed_s"].to_numpy(dtype=float), sectors, track, total=float(lap.lap_time_s))
        coach_arr = np.array([np.nan if v is None else v for v in coach], dtype=float)
        diff = coach_arr - ml
        rows.append(
            {
                "lap_id": lap.lap_id,
                "replay_lap_id": lap.replay_lap_id,
                "tempo_volta_store_s": float(lap.lap_time_s),
                "microsetores_sem_tempo_no_coach": int(np.isnan(coach_arr).sum()),
                "diferenca_max_por_microsetor_s": float(np.nanmax(np.abs(diff))),
                "soma_coach_s": float(np.nansum(coach_arr)),
                "soma_menos_tempo_volta_s": float(np.nansum(coach_arr) - lap.lap_time_s),
            }
        )
    passed = all(
        r["microsetores_sem_tempo_no_coach"] == 0
        and r["diferenca_max_por_microsetor_s"] <= C_MAX_SECTOR_S
        and abs(r["soma_menos_tempo_volta_s"]) <= C_SUM_S
        for r in rows
    )
    return {"voltas": rows, "passou": passed}


class CollectingBus:
    def __init__(self):
        self.events: List[dict] = []
        self.speech: List[dict] = []

    def schedule(self, topic, payload, loop_ref=None):
        (self.events if topic == COACHING_EVENT else self.speech if topic == ENGINEER_SPEECH else []).append(payload)


def criterion_d(geometry, model) -> Dict[str, object]:
    out: Dict[str, object] = {"sessoes": {}}
    all_phrases: List[str] = []
    for session_id in D_SESSIONS:
        bus = CollectingBus()
        coach = LiveDrivingCoach(bus, lambda _t: model, geometry_provider=lambda _t: geometry, min_gap_seconds=0.0)
        path = config.recordings_root() / session_id / "player.jsonl"
        frames = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sample = dict(payload.get("sample", payload))
                sample.setdefault("track", payload.get("track"))
                coach.on_frame(sample)
                frames += 1
        per_lap: Dict[int, int] = {}
        for event in bus.events:
            per_lap[event["lap_number"]] = per_lap.get(event["lap_number"], 0) + 1
        phrases = [{"tipo": "trecho", "volta": e["lap_number"], "texto": e["event"]} for e in bus.events]
        phrases += [{"tipo": "fim de volta", "texto": s["message"]} for s in bus.speech]
        all_phrases.extend(p["texto"] for p in phrases)
        counts = np.array(list(per_lap.values())) if per_lap else np.array([0])
        out["sessoes"][session_id] = {
            "frames": frames,
            "frases_de_trecho": len(bus.events),
            "frases_de_fim_de_volta": len(bus.speech),
            "voltas_com_frase": len(per_lap),
            "frases_por_volta": {"media": float(counts.mean()), "mediana": float(np.median(counts)), "max": int(counts.max())},
            "frases": phrases,
        }
    forbidden = [text for text in all_phrases if any(word in text.lower() for word in D_FORBIDDEN)]
    out["frases_proibidas"] = forbidden
    out["total_de_frases"] = len(all_phrases)
    out["passou"] = bool(all_phrases) and not forbidden
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geometria-arquivo", type=Path, required=True)
    parser.add_argument("--modelo", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--so", default="abcd", help="quais criterios rodar (padrao: abcd)")
    args = parser.parse_args(argv)

    geometry = OfficialGeometry.load(args.geometria_arquivo)
    model = DriverReferenceModel.load(args.modelo)
    if geometry is None or model is None:
        print("PARADO: geometria ou modelo ilegivel")
        return 2
    track = load_geometry()
    if track.geometry_id != geometry.geometry_id or model.geometry_id != geometry.geometry_id:
        print(f"PARADO: geometria {geometry.geometry_id}, ml {track.geometry_id}, modelo {model.geometry_id}")
        return 2
    store = load_store(track=track)
    sessions = {s.session_id: s for s in list_sessions()}
    loader = LapDataLoader(
        repo_root=BACKEND.parent,
        buffer_provider=lambda: TelemetryBuffer(max_size=1),
        runtime_state_provider=RuntimeState,
        recordings_roots=[config.recordings_root()],
    )

    result: Dict[str, object] = {
        "geometry_id": geometry.geometry_id,
        "modelo": {"arquivo": str(args.modelo), "referencia": model.reference_lap_id, "voltas": model.lap_count},
        "criterios": {
            "a": {"p99_ds_m": A_P99_DS_M, "p99_dd_m": A_P99_DD_M},
            "b": {"p99_ms": B_P99_MS},
            "c": {"max_por_microsetor_s": C_MAX_SECTOR_S, "soma_s": C_SUM_S},
            "d": {"proibido": list(D_FORBIDDEN)},
        },
    }
    if "a" in args.so or "b" in args.so:
        print("a/b: projetando tres sessoes...", flush=True)
        result.update(criterion_a_b(geometry, track, store, sessions))
        print(f"  a: {result['a']['passou']}  b: {result['b']['passou']}", flush=True)
    if "c" in args.so:
        print("c: microsetores do coach contra o store...", flush=True)
        result["c"] = criterion_c(geometry, track, store, loader)
        print(f"  c: {result['c']['passou']}", flush=True)
    if "d" in args.so:
        print("d: ensaio do coach em duas sessoes inteiras...", flush=True)
        result["d"] = criterion_d(geometry, model)
        print(f"  d: {result['d']['passou']}", flush=True)

    args.saida.mkdir(parents=True, exist_ok=True)
    (args.saida / "validacao.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"-> {args.saida / 'validacao.json'}")
    return 0 if all(result.get(k, {}).get("passou", True) for k in "abcd") else 1


if __name__ == "__main__":
    raise SystemExit(main())
