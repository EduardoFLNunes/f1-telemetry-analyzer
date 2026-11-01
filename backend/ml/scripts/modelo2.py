"""Modelo 2: o erro, as tecnicas e o estilo, nas voltas da IA e do piloto (pedido 38).

    python -m ml.scripts.modelo2 todos [--handoff PREFIXO]
    python -m ml.scripts.modelo2 rotulos --rotulos ARQUIVO.csv

As regras estao em `docs/modelo2_tecnica_e_estilo.md`, secao 1, registradas
antes de rodar. As saidas ficam em `data/ml/modelo2/` (fora do git) e, com
`--handoff`, uma copia dos JSON vai para `docs/handoff/`.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.assisted_analysis.reference_model import REFERENCE_AI, DriverReferenceModel, model_path  # noqa: E402
from ml import config  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.modelo2 import conferencias as conf  # noqa: E402
from ml.modelo2 import estilo, rotulagem, supervisionado  # noqa: E402
from ml.modelo2.dados import FORA_DO_STORE, ai_levels, carregar, raiz, sha256  # noqa: E402
from ml.modelo2.detectores import (APLICA, CATALOG, NAO_APLICA, NC, PER_CORNER, PRIMARY, Lap,  # noqa: E402
                                   assign_states, consistency_states, envelope_from, lap_measures, lap_states,
                                   measure_passage, phase_time)
from ml.modelo2.fases import build_phases, check_partition, window  # noqa: E402
from ml.modelo2.perda import loss_table, session_ranking  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

TRACK = "vhe_interlagos"


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else round(float(value), 5)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_clean(data), indent=1, ensure_ascii=False), encoding="utf-8")
    return path


CHANNELS = {"guinada": ("yaw_rate",), "velocidades_no_carro": ("velocity_long", "velocity_lat"),
            "cargas": ("wheel_load_fl",), "escorregamento": ("wheel_slip_fl",),
            "temperatura_pneus": ("tyre_core_temp_fl",), "temperatura_freios": ("brake_temp_fl",),
            "volante": ("steer_angle",), "pedais": ("brake", "throttle"), "marcha": ("gear",)}


def channels_of(lap: Lap) -> Dict[str, bool]:
    g = lap.volta.grid
    def has(c):
        return c in g and np.isfinite(g[c].to_numpy(dtype=float)).any() and np.nanmax(np.abs(g[c].to_numpy(dtype=float))) > 0
    return {name: all(has(c) for c in cols) for name, cols in CHANNELS.items()}


def fractions(states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (curva, det, who), g in states.assign(quem=np.where(states["origem"] == "ia", "ia", "piloto")).groupby(
            ["curva", "detector", "quem"]):
        n = len(g)
        conclusive = g[g["estado"] != NC]
        rows.append({"curva": curva, "detector": det, "quem": who, "passagens": n,
                     "conclusivas": len(conclusive),
                     "fracao_aplica": None if conclusive.empty else round(float((conclusive["estado"] == APLICA).mean()), 3),
                     "fracao_nao_conclusivo": round(float((g["estado"] == NC).mean()), 3)})
    return pd.DataFrame(rows)


def run(handoff_prefix: str = None) -> Dict[str, object]:
    started = time.time()
    timings = {}
    track = load_geometry()
    corners = detect_corners(track)
    if len(corners) != 14:
        raise SystemExit(f"PARADO: {len(corners)} curvas, o radio e o relatorio usam 14.")
    data = carregar(track)
    timings["leitura_s"] = round(time.time() - started, 1)
    laps = {k: Lap.build(v) for k, v in data.voltas.items()}

    model_file = model_path(BACKEND.parent, TRACK)
    model = DriverReferenceModel.load(model_file)
    ref_id = (model.references or {}).get(REFERENCE_AI, {}).get("lap_id")
    if ref_id not in laps:
        raise SystemExit(f"PARADO: a volta da IA do coach ({ref_id}) nao esta nas voltas rotuladas.")
    ref = laps[ref_id]
    humans = [l for l in laps.values() if l.volta.origem != "ia"]
    ais = [l for l in laps.values() if l.volta.origem == "ia"]
    best = min(humans, key=lambda l: l.total)

    # --- fases: primeiro sem frenagem, para medir os pontos de frenagem; depois as definitivas
    speed = ref.a("speed_kmh")
    ai_min = [float(np.nanmin(speed[window(track, c.start_s, c.end_s)])) for c in corners]
    empty = [[] for _ in corners]
    provisional = build_phases(track, corners, ai_min, empty, empty)
    env = envelope_from(list(laps.values()))
    ai_on, drv_on = [[] for _ in corners], [[] for _ in corners]
    for lap in laps.values():
        for cp in provisional:
            r = measure_passage(lap, track, cp, provisional[cp.k - 1], env)
            s = None if r["s_b_rel"] is None else float(np.mod(cp.a + r["s_b_rel"], track.length))
            (ai_on if lap.volta.origem == "ia" else drv_on)[cp.k].append(s)
    phases = build_phases(track, corners, ai_min, ai_on, drv_on)
    covered = check_partition(track, phases)

    # --- passagens e estados
    rows = []
    for lap in laps.values():
        for cp in phases:
            r = measure_passage(lap, track, cp, phases[cp.k - 1], env)
            r["tipo"] = cp.tipo
            r["tempo_trecho_s"] = phase_time(lap, track, *cp.trecho)
            rows.append(r)
    states, refs = assign_states(rows)
    passages = pd.DataFrame([{k: v for k, v in r.items() if k != "_ausente"} for r in rows])
    lap_rows = [lap_measures(l) for l in laps.values()]
    lstates = lap_states(lap_rows)
    seg_times = passages[["origem", "sessao", "curva", "lap_id", "tempo_trecho_s"]].copy()
    seg_times["origem"] = np.where(seg_times["origem"] == "ia", "ia", "humano")
    v5 = consistency_states(seg_times)
    timings["detectores_s"] = round(time.time() - started, 1)

    # --- Parte B: canais por volta e conferencias
    per_lap = [{"lap_id": l.volta.lap_id, "origem": l.volta.origem, "sessao": l.volta.sessao,
                "fora_do_store": l.volta.fora_do_store, "tempo_s": round(l.total, 3), **channels_of(l)}
               for l in sorted(laps.values(), key=lambda l: l.volta.lap_id)]
    sessions = {s.session_id: s for s in list_all_sessions()}
    checks = {
        "volante_em_reta": conf.steer_offset(list(laps.values())),
        "sinais_por_curva": conf.signs([l for l in laps.values() if l.a("yaw_rate") is not None], track, phases),
        "volante_por_curvatura": conf.steer_per_curvature(list(laps.values())),
        "unidade_e_entre_eixos": {
            "m1_pedido_37": "nao identificados: a regra registrada deu L negativo ou < 1,1 m; na opcao (a), L foi ao limite de 3,8 m e k_delta = 0,30 rad",
            "retrato_pedido_39": {"L_m": 2.955, "k_delta_rad": 0.267, "L_sobre_k": round(2.955 / 0.267, 2)},
            "reportagem_m": 2.943,
            "usado_no_e2": "retrato do pedido 39, como medida substituta (secao 1.2)"},
        "escorregamento": conf.slip_nature(list(laps.values())),
        "abs_ciclos": conf.abs_cycles(list(laps.values())),
        "abs_ajuste": [conf.abs_setting(sessions[s]) for s in ("2026-10-22_09-46-01_vhe_interlagos",
                                                               "2026-10-21_20-30-54_vhe_interlagos",
                                                               "2026-10-24_13-43-32_vhe_interlagos") if s in sessions],
    }

    # --- Parte D
    losses = loss_table(humans, ref, best, track, phases)
    ai_passages = passages[passages["origem"] == "ia"]
    rankings = []
    by_session: Dict[str, List[Lap]] = {}
    for l in humans:
        by_session.setdefault(l.volta.sessao, []).append(l)
    for session, items in sorted(by_session.items()):
        rankings.append(session_ranking(session, items, losses, passages, states, phases, best.volta.lap_id, ai_passages))
    phase_sum = losses.groupby("lap_id")["perda_s"].sum()
    lap_diff = pd.Series({l.volta.lap_id: l.total - ref.total for l in humans})
    closure = float((phase_sum - lap_diff.reindex(phase_sum.index)).abs().max())

    # --- Parte E
    all_states = pd.concat([states, lstates.assign(curva="volta")], ignore_index=True)
    frac = fractions(states)
    lists = []
    for (curva, det), g in frac.groupby(["curva", "detector"]):
        ia = g[g["quem"] == "ia"]
        me = g[g["quem"] == "piloto"]
        if ia.empty or me.empty:
            continue
        ia, me = ia.iloc[0], me.iloc[0]
        if ia["conclusivas"] >= 3 and me["conclusivas"] >= 3 and ia["fracao_aplica"] is not None and me["fracao_aplica"] is not None:
            if ia["fracao_aplica"] >= 0.6 and me["fracao_aplica"] <= 0.3:
                lists.append({"lista": "ia_aplica_piloto_nao", "curva": curva, "detector": det,
                              "ia": ia["fracao_aplica"], "piloto": me["fracao_aplica"]})
            elif me["fracao_aplica"] >= 0.6 and ia["fracao_aplica"] <= 0.3:
                lists.append({"lista": "piloto_aplica_ia_nao", "curva": curva, "detector": det,
                              "ia": ia["fracao_aplica"], "piloto": me["fracao_aplica"]})
    mine = states[states["origem"] != "ia"]
    evolution = []
    for (sess, det), g in mine.groupby(["sessao", "detector"]):
        c = g[g["estado"] != NC]
        evolution.append({"sessao": sess, "detector": det, "passagens": len(g), "conclusivas": len(c),
                          "fracao_aplica": None if c.empty else round(float((c["estado"] == APLICA).mean()), 3)})
    # verificacoes proprias da IA
    def pedal_share(group):
        out = {}
        for pedal in ("brake", "throttle"):
            vals = np.concatenate([l.a(pedal) for l in group if l.a(pedal) is not None])
            out[pedal] = round(float(((vals > 0.05) & (vals < 0.95)).mean()), 4)
        return out
    ai_disp = []
    for curva, g in ai_passages.groupby("curva"):
        ai_disp.append({"curva": curva, **{f"desvio_{m}": None if g[m].notna().sum() < 3 else round(float(np.std(g[m].dropna(), ddof=1)), 3)
                                           for m in ("s_b_rel", "v_min", "retomada_s")},
                        "sobreposicao_freio_volante_s_mediana": None if g["sobreposicao_s"].dropna().empty else round(float(g["sobreposicao_s"].median()), 3)})
    hum_disp = []
    for curva, g in passages[passages["origem"] != "ia"].groupby("curva"):
        hum_disp.append({"curva": curva, **{f"desvio_{m}": None if g[m].notna().sum() < 3 else round(float(np.std(g[m].dropna(), ddof=1)), 3)
                                            for m in ("s_b_rel", "v_min", "retomada_s")}})
    ai_states = states[states["origem"] == "ia"]
    changes = []
    for det, g in ai_states.groupby("detector"):
        per_corner = g[g["estado"] != NC].groupby("curva")["estado"].agg(lambda s: s.value_counts().idxmax())
        if per_corner.nunique() > 1:
            changes.append({"detector": det, "aplica_em": sorted(per_corner[per_corner == APLICA].index.tolist()),
                            "nao_aplica_em": sorted(per_corner[per_corner == NAO_APLICA].index.tolist())})
    levels = ai_levels()
    ai_checks = {
        "fracao_de_pedal_intermediario": {"ia": pedal_share(ais), "piloto": pedal_share(humans),
                                          "nota": "na grade de 2 m; valores entre 0,05 e 0,95"},
        "trail_hint": "nao legivel: o ai.ini do carro so existe dentro do data.acd, que nao foi aberto",
        "dispersao_volta_a_volta_ia": ai_disp,
        "dispersao_volta_a_volta_piloto": hum_disp,
        "ia_muda_a_tecnica_entre_curvas": changes,
        "niveis_de_forca": ("nao conclusivo: ainda nao ha sessao da IA em niveis de forca "
                            "(docs/experimentos/ia_niveis.csv nao existe)") if levels.empty else levels.to_dict("records"),
    }

    # --- Parte F
    styled = estilo.with_relative_peak(passages.assign(quem=np.where(passages["origem"] == "ia", "ia", "piloto")))
    signature = {"total": estilo.signatures(styled, ["quem"]),
                 "piloto_por_sessao": estilo.signatures(styled[styled["quem"] == "piloto"], ["sessao"])}

    # --- Parte G
    features = [PRIMARY[d] for d in PER_CORNER]
    models = []
    human_passages = passages[passages["origem"] != "ia"].reset_index(drop=True)
    for cp in phases:
        g = human_passages[human_passages["curva"] == cp.curva].reset_index(drop=True)
        models.append({"curva": cp.curva, "tipo": cp.tipo, **supervisionado.fit_corner(g, features)})
    timings["modelos_s"] = round(time.time() - started, 1)

    # --- Parte H
    root = raiz()
    kit_dir = root / "rotulagem"
    kit_dir.mkdir(parents=True, exist_ok=True)
    stem = handoff_prefix or "kit"
    kit_html = kit_dir / f"{Path(stem).name}_kit_rotulagem.html"
    kit_csv = kit_dir / f"{Path(stem).name}_rotulagem.csv"
    key = root / "rotulagem_gabarito.json"
    kit = rotulagem.build_kit(states, laps, track, phases, kit_html, kit_csv, key)

    # --- saidas
    outputs = {
        "fases": {"curvas": [cp.to_dict() for cp in phases], "metros_cobertos": covered, "comprimento_da_volta": track.length,
                  "envelope": env.table},
        "canais_e_conferencias": {"voltas": per_lap, "fora_do_store": data.fora_relatorio, "conferencias": checks},
        "erros_por_sessao": {"referencia": {"volta_ia": ref_id, "tempo_s": ref.total, "melhor_volta": best.volta.lap_id,
                                            "melhor_tempo_s": best.total},
                             "fechamento_soma_das_fases_s": closure, "sessoes": rankings},
        "tecnicas": {"fracoes": frac.to_dict("records"), "listas": lists, "evolucao_piloto": evolution,
                     "por_volta": lstates.to_dict("records"), "consistencia_v5": v5.to_dict("records"),
                     "verificacoes_da_ia": ai_checks,
                     "estados": all_states[["lap_id", "curva", "detector", "estado", "motivo", "valor_regra", "indicador",
                                            "origem", "sessao"]].to_dict("records")},
        "estilo": signature,
        "modelo_leve": models,
    }
    paths = {}
    for name, payload in outputs.items():
        paths[name] = write(root / f"{name}.json", payload)
    passages.to_parquet(root / "passagens.parquet")
    timings["total_s"] = round(time.time() - started, 1)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(BACKEND.parent), capture_output=True, text=True).stdout.strip()
    read_files = [dict(e, sha256=sha256(Path(e["arquivo"]))) for e in data.lidos]
    read_files.append({"arquivo": str(model_file), "bytes": model_file.stat().st_size, "sha256": sha256(model_file)})
    results = {
        "pedido": "docs/prompts/2026-10-24_38_modelo2-erro-tecnica-e-estilo.md",
        "commit": commit, "geometry_id": track.geometry_id, "geometria_source_hash": track.source_hash,
        "store_v2": {"commit": data.store_meta.get("commit"), "construido_em": data.store_meta.get("construido_em")},
        "ambiente": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "comandos": ["python -m ml.scripts.modelo2 todos --handoff docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo"],
        "voltas": {"total": len(laps), "piloto": len(humans), "ia": len(ais),
                   "fora_do_store": sum(l.volta.fora_do_store for l in laps.values())},
        "lidos": read_files,
        "escritos": [{"arquivo": str(p), "sha256": sha256(p)} for p in list(paths.values()) + [kit_html, kit_csv, key]],
        "kit": kit, "tempos": timings,
    }
    write(root / "resultados.json", results)
    if handoff_prefix:
        base = BACKEND.parent / handoff_prefix
        for name, p in paths.items():
            payload = outputs[name]
            if name == "tecnicas":
                # Os estados de cada passagem (~13 MB) ficam so em data/ml/modelo2/tecnicas.json.
                payload = {k: v for k, v in payload.items() if k != "estados"}
            write(base.parent / f"{base.name}_{name}.json", payload)
        for p in (kit_html, kit_csv):
            target = base.parent / p.name.replace("kit_kit", "kit").replace(Path(stem).name, base.name)
            target.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        (base.parent / f"{base.name}_resultados.json").write_text((root / "resultados.json").read_text(encoding="utf-8"), encoding="utf-8")
    return {"saidas": outputs, "resultados": results}


def labels(path: Path) -> int:
    out = rotulagem.precision_recall(path, raiz() / "rotulagem_gabarito.json")
    write(raiz() / "precisao_revocacao.json", out)
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=["todos", "rotulos"])
    parser.add_argument("--handoff", default=None)
    parser.add_argument("--rotulos", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.comando == "rotulos":
        return labels(args.rotulos)
    try:
        result = run(args.handoff)
    except SystemExit as stop:
        print(stop)
        return 2
    r = result["resultados"]
    print(json.dumps({"voltas": r["voltas"], "tempos": r["tempos"], "kit": r["kit"]}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
