"""As medicoes de integridade dos dados citadas no relatorio da Fase 1.

    python -m ml.scripts.measure_integrity [--backup DIR]

Cada numero de `docs/fase1_validacao_contrafactual.md` que nao sai de
`validate_counterfactual` sai daqui, para poder ser refeito:

* onde cada sessao guarda os pedais, e se os dois lugares concordam;
* o sinal do offset gravado contra o `lateral` do `ml`, por geracao de formato;
* o perfil da diferenca entre o `s` gravado e o recalculado ao longo da volta;
* se o store atual difere do anterior (`--backup`) nas voltas em comum;
* a associacao com o replay e a concordancia da projecao, pelo inventario;
* o simulador contra o cronometro dentro das duas maiores sessoes.

Escreve `data/ml/validation/integrity/resultado.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.telemetry.channels import INPUT_CHANNELS, input_schema
from ml import config
from ml.data.inventory import load_inventory
from ml.data.lap_store import load_store
from ml.data.recordings import iter_laps, list_sessions
from ml.optimization.lap_time_model import simulate_batch
from ml.preprocessing.alignment import align_lap
from ml.preprocessing.cleaning import clean_lap
from ml.track.geometry import load_geometry
from ml.validation.counterfactual import envelope_from

# Uma sessao por geracao de formato, as mesmas das fixtures de teste.
SCHEMA_SESSIONS = {
    "2026-05-26_19-06-59_vhe_interlagos": "maio, so topo",
    "2026-05-29_20-22-25_vhe_interlagos": "maio, ambos",
    "2026-06-14_12-23-46_vhe_interlagos": "junho, so topo",
    "2026-06-18_20-06-03_vhe_interlagos": "junho, ambos",
    "2026-06-20_13-13-02_vhe_interlagos": "junho, ambos",
    "2026-08-09_19-20-59_vhe_interlagos": "agosto, so aninhado",
    "2026-08-16_03-30-14_vhe_interlagos": "agosto, ambos",
}
MAX_LINES = 30_000
S_PROFILE_AT = (0, 500, 1000, 2000, 3000, 4000, 4300)
S_PROFILE_WINDOW_M = 50.0


def control_agreement(path: Path) -> Dict[str, object]:
    """Formato das amostras e diferenca maxima entre topo e `carPhysics.controls`."""
    schemas: Dict[str, int] = {}
    max_diff = {name: 0.0 for name in INPUT_CHANNELS}
    both = {name: 0 for name in INPUT_CHANNELS}
    read = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if read >= MAX_LINES:
                break
            try:
                sample = json.loads(line).get("sample", {})
            except json.JSONDecodeError:
                continue
            read += 1
            schemas[input_schema(sample)] = schemas.get(input_schema(sample), 0) + 1
            controls = (sample.get("carPhysics") or {}).get("controls") or {}
            for name, (nested, top) in INPUT_CHANNELS.items():
                a, b = sample.get(top), controls.get(nested)
                if a is not None and b is not None:
                    both[name] += 1
                    max_diff[name] = max(max_diff[name], abs(float(a) - float(b)))
    return {"amostras_lidas": read, "formatos": schemas, "amostras_com_os_dois": both, "diferenca_maxima": max_diff}


def first_full_lap(session, track):
    for lap in iter_laps(session):
        if lap.sample_count < 2000:
            continue
        cleaned, _ = clean_lap(lap.frame)
        aligned, _ = align_lap(cleaned, track)
        return lap.lap_id, aligned
    return None, None


def sign_and_s(aligned: pd.DataFrame, track) -> Dict[str, object]:
    out: Dict[str, object] = {}
    recorded = aligned["lateral_recorded"].to_numpy(dtype=float)
    lateral = aligned["lateral"].to_numpy(dtype=float)
    usable = np.isfinite(recorded) & np.isfinite(lateral)
    if usable.sum() < 100:
        return {"sem_projecao_gravada": True}
    # `lateral_recorded` ja vem convertido; o bruto gravado e o oposto dele.
    raw = -recorded[usable]
    out["amostras"] = int(usable.sum())
    out["correlacao_gravado_bruto_x_ml"] = float(np.corrcoef(raw, lateral[usable])[0, 1])
    out["p95_abs_ml_mais_gravado_bruto_m"] = float(np.percentile(np.abs(lateral[usable] + raw), 95))
    s_rec = aligned["s_recorded"].to_numpy(dtype=float)
    s = aligned["s"].to_numpy(dtype=float)
    diff = np.mod(s_rec - s + track.length / 2.0, track.length) - track.length / 2.0
    profile = {}
    for start in S_PROFILE_AT:
        window = (s > start) & (s < start + S_PROFILE_WINDOW_M) & np.isfinite(diff)
        profile[str(start)] = float(np.median(diff[window])) if window.any() else None
    out["s_gravado_menos_s_ml_mediana_por_trecho_m"] = profile
    return out


def store_versus_backup(current, backup_dir: Optional[Path]) -> Dict[str, object]:
    if backup_dir is None or not (backup_dir / "laps_grid.parquet").exists():
        return {"backup": None}
    old = pd.read_parquet(backup_dir / "laps_grid.parquet")
    new = current.frame
    common = sorted(set(old["lap_id"]) & set(new["lap_id"]))
    out: Dict[str, object] = {
        "backup": str(backup_dir),
        "voltas_comuns": len(common),
        "voltas_novas": sorted(set(new["lap_id"]) - set(old["lap_id"])),
        "voltas_removidas": sorted(set(old["lap_id"]) - set(new["lap_id"])),
    }
    a = old[old["lap_id"].isin(common)].sort_values(["lap_id", "grid_index"])
    b = new[new["lap_id"].isin(common)].sort_values(["lap_id", "grid_index"])
    for column in ("lateral", "elapsed_s", "speed_kmh", "throttle", "brake"):
        out[f"max_abs_diff_{column}"] = float(np.nanmax(np.abs(a[column].to_numpy() - b[column].to_numpy())))
    return out


def simulator_within_session(store, track, session_id: str) -> Dict[str, object]:
    ids = store.laps[store.laps["session_id"] == session_id]["lap_id"].tolist()
    envelope = envelope_from(store, [lap for lap in store.lap_ids if lap not in ids])
    laterals = np.vstack([store.lap(lap)["lateral"].to_numpy(dtype=float) for lap in ids])
    real = store.laps.set_index("lap_id").loc[ids, "lap_time_s"].to_numpy(dtype=float)
    simulated, _, _ = simulate_batch(track, laterals, envelope)
    under = real < 88.0
    return {
        "voltas_abaixo_de_88s": int(under.sum()),
        "dp_real_s": float(real[under].std()),
        "dp_simulado_s": float(simulated[under].std()),
        "correlacao": float(np.corrcoef(real[under], simulated[under])[0, 1]),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, default=config.artifacts_root() / "_backup_pre_fase1")
    args = parser.parse_args(argv)

    track = load_geometry()
    store = load_store(track=track)
    inventory = load_inventory()
    sessions = {s.session_id: s for s in list_sessions()}

    per_schema = {}
    for session_id, label in SCHEMA_SESSIONS.items():
        session = sessions.get(session_id)
        if session is None:
            per_schema[session_id] = {"rotulo": label, "ausente": True}
            continue
        lap_id, aligned = first_full_lap(session, track)
        per_schema[session_id] = {
            "rotulo": label,
            "controles": control_agreement(session.player_stream),
            "volta_usada": lap_id,
            "projecao": sign_and_s(aligned, track) if aligned is not None else None,
        }
        print(f"  {session_id}: {label}", flush=True)

    valid = inventory[inventory["valid"]]
    agreement_columns = ["recorded_s_p95_m", "recorded_lateral_p95_m", "recorded_lateral_correlation"]
    result = {
        "geometry_id": track.geometry_id,
        "source_hash": track.source_hash,
        "inventario": {
            "voltas": int(len(inventory)),
            "validas": int(valid.shape[0]),
            "sessoes_com_validas": int(valid["session_id"].nunique()),
            "validas_por_sessao": {k: int(v) for k, v in valid.groupby("session_id").size().items()},
            "associacao_replay": {
                f"{'valida' if ok else 'rejeitada'}:{match}": int(n)
                for (ok, match), n in inventory.groupby(["valid", "replay_match"]).size().items()
            },
            "concordancia_projecao_validas": {
                "voltas_com_projecao_gravada": int(valid[agreement_columns[0]].notna().sum()),
                **{
                    column: {
                        "media": float(valid[column].mean()),
                        "min": float(valid[column].min()),
                        "max": float(valid[column].max()),
                    }
                    for column in agreement_columns
                },
                "mediana_por_sessao": {
                    session: {c: (None if pd.isna(v) else float(v)) for c, v in row.items()}
                    for session, row in valid.groupby("session_id")[agreement_columns].median().iterrows()
                },
            },
        },
        "formatos_e_sinal": per_schema,
        "store_contra_backup": store_versus_backup(store, args.backup),
        "simulador_dentro_da_sessao": {
            session_id: simulator_within_session(store, track, session_id)
            for session_id in ("2026-08-09_19-20-59_vhe_interlagos", "2026-06-20_13-13-02_vhe_interlagos")
        },
    }

    out_dir = config.artifacts_root() / "validation" / "integrity"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "resultado.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"-> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
