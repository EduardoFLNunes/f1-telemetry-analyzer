"""Modelo 2: o erro, as tecnicas e o estilo, nas voltas da IA e do piloto (pedido 38).

    python -m ml.scripts.modelo2 todos --saida PASTA [--rodada 1|2] [--handoff PREFIXO]
    python -m ml.scripts.modelo2 rotulos --rotulos ARQUIVO.csv

As regras estao em `docs/modelo2_tecnica_e_estilo.md`, secao 1 (rodada 1) e
secao 4 (rodada 2), registradas antes de rodar. Desde o pedido 42, cada rodada
grava numa pasta propria dentro de `data/ml/modelo2/` (por exemplo,
`rodada1_refeita`), so com os 144 `lap_id` da rodada 1; os arquivos da rodada 1
em `data/ml/modelo2/` so sao lidos. Com `--handoff`, uma copia dos JSON vai
para `docs/handoff/`.
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

from core.assisted_analysis.reference_model import LEGACY_AI_KIND, DriverReferenceModel, model_path  # noqa: E402
from ml.pista_teste.condicoes import VOLTA_IA as VOLTA_0013  # noqa: E402
from ml import config  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.modelo2 import conferencias as conf  # noqa: E402
from ml.modelo2 import comparacao, estilo, rotulagem, saidas, supervisionado  # noqa: E402
from ml.data.store_v2 import store_v2_meta  # noqa: E402
from ml.modelo2.dados import (FORA_DO_STORE, ai_levels, carregar, geometria_medida, pasta_da_rodada,  # noqa: E402
                              raiz, sha256, volta_do_modelo, voltas_da_rodada1)
from ml.modelo2.detectores import (APLICA, CATALOG, GEOMETRIA_SUBSTITUTA, NAO_APLICA, NC, PER_CORNER,  # noqa: E402
                                   PRIMARY, Lap, assign_states, consistency_states, envelope_from, lap_measures,
                                   lap_states, measure_passage, phase_time)
from ml.modelo2.fases import build_phases, check_partition, window  # noqa: E402
from ml.modelo2.perda import loss_table, session_ranking  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

TRACK = "vhe_interlagos"
KIT_DATE = "2026-10-25"       # as sessoes depois do kit de 24/10 (pedido 42, Parte D.3)


def voltas_depois_do_kit(meta: Dict[str, object]) -> List[str]:
    """As voltas do piloto na pista original, de gravacoes depois de 24/10 (pelo meta do store)."""
    return sorted(l["lap_id"] for l in meta.get("laps", [])
                  if l.get("origem") == "humano" and l.get("track") == TRACK and str(l["session_id"])[:10] >= KIT_DATE)


def best_for(last: List[str], ordered_best: List[str]) -> str:
    """A "Sua melhor volta" de uma comparacao: a segunda melhor quando a melhor esta entre as voltas comparadas."""
    for lap_id in ordered_best:
        if lap_id not in last:
            return lap_id
    return ordered_best[0]


def rankings_for(laps: List[Lap], losses: pd.DataFrame, passages: pd.DataFrame, states: pd.DataFrame,
                 phases, ordered_best: List[str], ai_passages: pd.DataFrame, rodada: int,
                 ref_points: pd.DataFrame = None, ref_label: str = "volta da IA do coach") -> List[Dict[str, object]]:
    by_session: Dict[str, List[Lap]] = {}
    for l in laps:
        by_session.setdefault(l.volta.sessao, []).append(l)
    out = []
    for session, items in sorted(by_session.items()):
        ordered = sorted(items, key=lambda l: (l.volta.gravacao, int(l.volta.lap_id.split("#")[1])))
        last = [l.volta.lap_id for l in ordered][-3:]
        best_id = best_for(last, ordered_best) if rodada >= 2 else ordered_best[0]
        r = session_ranking(session, items, losses, passages, states, phases, best_id, ai_passages,
                            rodada=rodada, ref_points=ref_points, ref_label=ref_label)
        r["melhor_volta_usada"] = best_id
        out.append(r)
    return out


def closure_of(losses: pd.DataFrame, laps: List[Lap], ref: Lap) -> float:
    phase_sum = losses.groupby("lap_id")["perda_s"].sum()
    lap_diff = pd.Series({l.volta.lap_id: l.total - ref.total for l in laps})
    return float((phase_sum - lap_diff.reindex(phase_sum.index)).abs().max())


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


def run(saida: str, handoff_prefix: str = None, rodada: int = 1) -> Dict[str, object]:
    """Uma rodada do Modelo 2 (rodada 1: secoes 1 e 2; rodada 2: secao 4), gravada em data/ml/modelo2/<saida>/."""
    started = time.time()
    timings = {}
    out_dir = pasta_da_rodada(saida)
    wanted = voltas_da_rodada1()
    track = load_geometry()
    corners = detect_corners(track)
    if len(corners) != 14:
        raise SystemExit(f"PARADO: {len(corners)} curvas, o radio e o relatorio usam 14.")
    extra_wanted = voltas_depois_do_kit(store_v2_meta()) if rodada >= 2 else []
    data = carregar(track, saida=out_dir, so_ids=wanted, mais_ids=extra_wanted)
    timings["leitura_s"] = round(time.time() - started, 1)
    all_laps = {k: Lap.build(v) for k, v in data.voltas.items()}
    laps = {k: v for k, v in all_laps.items() if k in set(wanted)}
    extras = {k: v for k, v in all_laps.items() if k not in set(wanted)}
    geometria = geometria_medida() if rodada >= 2 else GEOMETRIA_SUBSTITUTA

    model_file = model_path(BACKEND.parent, TRACK)
    model = DriverReferenceModel.load(model_file)
    # ADR 0032, item 6: a volta da IA saiu do modelo do coach; o Modelo 2 (que nao muda) segue na `#0013`.
    ref_id = ((model.references or {}).get(LEGACY_AI_KIND) or {}).get("lap_id") or VOLTA_0013
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
            r = measure_passage(lap, track, cp, provisional[cp.k - 1], env, rodada=rodada, geometria=geometria)
            s = None if r["s_b_rel"] is None else float(np.mod(cp.a + r["s_b_rel"], track.length))
            (ai_on if lap.volta.origem == "ia" else drv_on)[cp.k].append(s)
    phases = build_phases(track, corners, ai_min, ai_on, drv_on)
    covered = check_partition(track, phases)

    # --- passagens e estados
    rows = []
    for lap in laps.values():
        for cp in phases:
            r = measure_passage(lap, track, cp, phases[cp.k - 1], env, rodada=rodada, geometria=geometria)
            r["tipo"] = cp.tipo
            r["tempo_trecho_s"] = phase_time(lap, track, *cp.trecho)
            r["sessao_com_margem"] = lap.volta.com_margem
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
            "usado_no_e2": ("retrato do pedido 39, como medida substituta (secao 1.2)" if rodada < 2 else
                            {"fonte": "docs/handoff/2026-10-25_39_m1-geometria-medida_geometria.json, chave usados",
                             "L_m": geometria[0], "k_delta_rad": geometria[1]})},
        "escorregamento": conf.slip_nature(list(laps.values())),
        "abs_ciclos": conf.abs_cycles(list(laps.values())),
        "abs_ajuste": [conf.abs_setting(sessions[s]) for s in ("2026-10-22_09-46-01_vhe_interlagos",
                                                               "2026-10-21_20-30-54_vhe_interlagos",
                                                               "2026-10-24_13-43-32_vhe_interlagos") if s in sessions],
    }

    # --- Parte D
    ai_passages = passages[passages["origem"] == "ia"]
    ordered_best = [l.volta.lap_id for l in sorted(humans, key=lambda l: l.total)]
    comparison = None
    if rodada < 2:
        losses = loss_table(humans, ref, best, track, phases, margem_s=data.margem_s)
        rankings = rankings_for(humans, losses, passages, states, phases, ordered_best, ai_passages, rodada)
        closure = closure_of(losses, humans, ref)
        reference = {"volta_ia": ref_id, "tempo_s": ref.total, "melhor_volta": best.volta.lap_id, "melhor_tempo_s": best.total}
    else:
        # Secao 4.4: a volta do modelo; a `#0013` so como comparacao com a rodada 1.
        model_lap = Lap.build(volta_do_modelo(track))
        model_rows = [measure_passage(model_lap, track, cp, phases[cp.k - 1], env, rodada=rodada, geometria=geometria)
                      for cp in phases]
        model_points = pd.DataFrame([{k: v for k, v in r.items() if k != "_ausente"} for r in model_rows]).set_index("curva")
        ref_points_0013 = passages[passages["lap_id"] == ref_id].set_index("curva")
        losses = loss_table(humans, model_lap, best, track, phases, margem_s=data.margem_s)
        rankings = rankings_for(humans, losses, passages, states, phases, ordered_best, ai_passages, rodada,
                                model_points, "volta de referencia (volta do modelo)")
        closure = closure_of(losses, humans, model_lap)
        losses_0013 = loss_table(humans, ref, best, track, phases, margem_s=data.margem_s)
        comparison = {"marca": "so comparacao: contra a #0013, a referencia da rodada 1 (secao 4.1)",
                      "referencia": {"lap_id": ref_id, "tempo_s": ref.total},
                      "fechamento_soma_das_fases_s": closure_of(losses_0013, humans, ref),
                      "sessoes": rankings_for(humans, losses_0013, passages, states, phases, ordered_best, ai_passages,
                                              rodada, ref_points_0013, "so comparacao: #0013")}
        reference = {"volta_de_referencia": model_lap.volta.lap_id, "tempo_s": model_lap.total,
                     "melhor_volta": best.volta.lap_id, "melhor_tempo_s": best.total,
                     "segunda_melhor_volta": ordered_best[1] if len(ordered_best) > 1 else None,
                     "pontos_da_volta_de_referencia": model_points[["s_b_rel", "s_vmin_rel", "v_min", "retomada_s",
                                                                    "afastamento_m", "freia", "retoma"]]
                     .reset_index().to_dict("records")}

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

    # --- Parte H (rodada 1) ou o kit 2 (rodada 2, Parte E.1 do pedido 42)
    root = out_dir
    kit_dir = root / "rotulagem"
    kit_dir.mkdir(parents=True, exist_ok=True)
    stem = handoff_prefix or "kit"
    if rodada < 2:
        kit_html = kit_dir / f"{Path(stem).name}_kit_rotulagem.html"
        kit_csv = kit_dir / f"{Path(stem).name}_rotulagem.csv"
        key = root / "rotulagem_gabarito.json"
        kit = rotulagem.build_kit(states, laps, track, phases, kit_html, kit_csv, key)
        kit_files = [kit_html, kit_csv, key]
    else:
        kit_html = kit_dir / "kit2_rotulagem.html"
        kit_csv = kit_dir / "kit2_consistencia.csv"
        key = root / "kit2_gabarito.json"
        consistency_html = kit_dir / "kit2_consistencia.html"
        kit = rotulagem.build_kit2(raiz() / "rotulagem_gabarito.json", states, laps, track, phases, model_lap,
                                   ordered_best, kit_html, consistency_html, kit_csv, key, model_points=model_points)
        kit_files = [kit_html, consistency_html, kit_csv, key]
        kit["sha256_html"] = sha256(kit_html)

    # --- Parte D.6 (pedido 42): o E3 nas saidas de traseira relatadas em 01/11, a parte dos rotulos
    e3_exits = saidas.run_e3(track, phases, refs, env, rodada, geometria)

    # --- Parte D.3 (rodada 2): as sessoes depois do kit, so medidas, com as fases, o envelope e a calibracao das 144
    after_kit = None
    if rodada >= 2:
        extra_humans = [l for l in extras.values() if l.volta.origem != "ia"]
        extra_rows = []
        for lap in extra_humans:
            for cp in phases:
                r = measure_passage(lap, track, cp, phases[cp.k - 1], env, rodada=rodada, geometria=geometria)
                r["tipo"] = cp.tipo
                r["tempo_trecho_s"] = phase_time(lap, track, *cp.trecho)
                r["sessao_com_margem"] = lap.volta.com_margem
                extra_rows.append(r)
        ai_rows = [r for r in rows if r["origem"] == "ia"]
        extra_states_all, _ = assign_states(ai_rows + extra_rows)
        extra_states = extra_states_all[extra_states_all["origem"] != "ia"]
        extra_passages = pd.DataFrame([{k: v for k, v in r.items() if k != "_ausente"} for r in extra_rows])
        both_passages = pd.concat([passages, extra_passages], ignore_index=True)
        both_states = pd.concat([states, extra_states], ignore_index=True)
        extra_losses = loss_table(extra_humans, model_lap, best, track, phases, margem_s=data.margem_s)
        after_kit = {"pedidas": len(extra_wanted), "medidas": len(extra_humans),
                     "fora_da_selecao": sorted(set(extra_wanted) - set(extras)),
                     "voltas": [{"lap_id": l.volta.lap_id, "sessao": l.volta.sessao, "tempo_s": round(l.total, 3),
                                 "sessao_com_margem": l.volta.com_margem} for l in extra_humans],
                     "fechamento_soma_das_fases_s": closure_of(extra_losses, extra_humans, model_lap) if extra_humans else None,
                     "sessoes": rankings_for(extra_humans, extra_losses, both_passages, both_states, phases, ordered_best,
                                             ai_passages, rodada, model_points, "volta de referencia (volta do modelo)")}
        if len(extra_passages):
            extra_passages.to_parquet(root / "passagens_depois_do_kit.parquet")

    # --- saidas
    outputs = {
        "fases": {"curvas": [cp.to_dict() for cp in phases], "metros_cobertos": covered, "comprimento_da_volta": track.length,
                  "envelope": env.table},
        "canais_e_conferencias": {"voltas": per_lap, "fora_do_store": data.fora_relatorio, "conferencias": checks},
        "erros_por_sessao": {"rodada": rodada, "referencia": reference,
                             "fechamento_soma_das_fases_s": closure, "sessoes": rankings},
        "tecnicas": {"fracoes": frac.to_dict("records"), "listas": lists, "evolucao_piloto": evolution,
                     "por_volta": lstates.to_dict("records"), "consistencia_v5": v5.to_dict("records"),
                     "verificacoes_da_ia": ai_checks,
                     "estados": all_states[["lap_id", "curva", "detector", "estado", "motivo", "valor_regra", "indicador",
                                            "origem", "sessao"]].to_dict("records")},
        "estilo": signature,
        "modelo_leve": models,
    }
    outputs["e3_saidas_de_traseira"] = e3_exits
    if comparison is not None:
        outputs["erros_por_sessao_so_comparacao_0013"] = comparison
    if after_kit is not None:
        outputs["erros_depois_do_kit"] = after_kit
    paths = {}
    for name, payload in outputs.items():
        paths[name] = write(root / f"{name}.json", payload)
    passages.to_parquet(root / "passagens.parquet")
    timings["total_s"] = round(time.time() - started, 1)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(BACKEND.parent), capture_output=True, text=True).stdout.strip()
    read_files = [dict(e, sha256=sha256(Path(e["arquivo"]))) for e in data.lidos]
    read_files.append({"arquivo": str(model_file), "bytes": model_file.stat().st_size, "sha256": sha256(model_file)})
    results = {
        "pedido": ("docs/prompts/2026-10-24_38_modelo2-erro-tecnica-e-estilo.md" if rodada < 2 else
                   "docs/prompts/2026-10-29_42_modelo2-rodada-2.md"),
        "rodada": rodada, "regras": "secoes 1 e 2" if rodada < 2 else "secao 4 (pedido 42, Parte A)",
        "commit": commit, "geometry_id": track.geometry_id, "geometria_source_hash": track.source_hash,
        "store_v2": {"commit": data.store_meta.get("commit"), "construido_em": data.store_meta.get("construido_em")},
        "ambiente": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "comandos": [" ".join(["python -m ml.scripts.modelo2 todos --saida", saida, "--rodada", str(rodada)]
                              + (["--handoff", handoff_prefix] if handoff_prefix else []))],
        "saida": str(out_dir),
        "voltas": {"total": len(laps), "piloto": len(humans), "ia": len(ais),
                   "fora_do_store": sum(l.volta.fora_do_store for l in laps.values()),
                   "pedidas": len(wanted), "fonte_da_lista": "docs/handoff/2026-10-24_38_modelo2-erro-tecnica-e-estilo_canais_e_conferencias.json"},
        "sessoes_com_margem": {"margem_s": data.margem_s, "sessoes": data.com_margem,
                               "voltas": sorted(l.volta.lap_id for l in laps.values() if l.volta.com_margem)},
        "lidos": read_files,
        "escritos": [{"arquivo": str(p), "sha256": sha256(p)} for p in list(paths.values()) + kit_files]
                    + [{"arquivo": p, "sha256": sha256(Path(p))} for p in data.escritos],
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
        for p in [f for f in kit_files if f != key]:
            name = p.name.replace("kit_kit", "kit").replace(Path(stem).name, base.name)
            target = base.parent / (name if name.startswith(base.name) else f"{base.name}_{name}")
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
    parser.add_argument("comando", choices=["todos", "rotulos", "conferir", "comparar"])
    parser.add_argument("--handoff", default=None)
    parser.add_argument("--saida", default=None, help="pasta da rodada dentro de data/ml/modelo2/ (pedido 42)")
    parser.add_argument("--rodada", type=int, choices=[1, 2], default=1)
    parser.add_argument("--rodada1", default=None, help="comparar: a pasta da rodada 1 refeita")
    parser.add_argument("--rotulos", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.comando == "rotulos":
        return labels(args.rotulos)
    if args.comando == "conferir":
        out = comparacao.conferir_rodada1(raiz(), pasta_da_rodada(args.saida or "rodada1_refeita"))
        write(pasta_da_rodada(args.saida or "rodada1_refeita") / "conferencia_com_a_rodada1.json", out)
        if args.handoff:
            write(BACKEND.parent / f"{args.handoff}_conferencia_rodada1.json", out)
        print(json.dumps(_clean(out), indent=1, ensure_ascii=False))
        return 0 if out["reproduz"] else 3
    if args.comando == "comparar":
        out = comparacao.comparar(raiz(), pasta_da_rodada(args.rodada1 or "rodada1_refeita"),
                                  pasta_da_rodada(args.saida or "rodada2"))
        write(pasta_da_rodada(args.saida or "rodada2") / "comparacao_com_a_rodada1.json", out)
        if args.handoff:
            write(BACKEND.parent / f"{args.handoff}_comparacao.json", out)
        print("ok")
        return 0
    if not args.saida:
        parser.error("todos exige --saida (pedido 42: nada da rodada 1 em data/ml/modelo2/ e sobrescrito)")
    try:
        result = run(args.saida, args.handoff, args.rodada)
    except SystemExit as stop:
        print(stop)
        return 2
    r = result["resultados"]
    print(json.dumps({"voltas": r["voltas"], "tempos": r["tempos"], "kit": r["kit"]}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
