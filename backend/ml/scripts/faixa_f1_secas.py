"""Faixa de linhas reais da F1 em Interlagos com voltas secas de classificacao (pedido 23).

    python -m ml.scripts.faixa_f1_secas [--saida data/ml/externo/f1_faixa]

Carrega pelo FastF1 3.4.0 (cache em `data/fastf1_cache/`) a classificacao de
2018, 2019 e 2021 a 2025 e as classificatorias da sprint (2023 em diante),
passa cada volta pelo funil de `ml.external.f1_dry_laps`, le so `X` e `Y` dos
dados de posicao das voltas escolhidas e alinha cada uma pelo metodo do pedido
22. Com as voltas aceitas, mede a incerteza do alinhamento (V1 e V2), forma a
faixa e compara, so para leitura, a IA, o piloto e a volta de chuva de 2024.

Nada e treinado, e nada muda coach, store ou criterio. Nada da F1 alem da
posicao e lido (ADR 0018).

Escreve, fora do git, em `data/ml/externo/f1_faixa/`:

* `manifesto.json` -- cada sessao e cada volta considerada, com a etapa do
  funil, os numeros do criterio e o veredito;
* `voltas/<ano>_<tipo>_<piloto>_<volta>.csv` -- `s`, lateral e excesso de cada
  volta aceita;
* `faixa.csv` -- `s`, p10, p50, p90, n e a incerteza V1 e V2 por ponto;
* `resumo.json`, `faixa_pista.png` e `faixa_lateral.png`.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison import evolution as ev  # noqa: E402
from ml.data.store_v2 import git_commit, load_store_v2, store_v2_meta  # noqa: E402
from ml.external import f1_band, f1_dry_laps, f1_line  # noqa: E402
from ml.scripts.alinhar_fastf1 import (  # noqa: E402
    OFFICIAL_GEOMETRY_ID,
    ZOOM_MARGIN_M,
    _closed,
    _round,
    corner_by_name,
    labelled_ai_laps,
    lateral_matrix,
)
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import TrackGeometry, load_geometry  # noqa: E402
from ml.track.microsectors import Microsectors, build_microsectors  # noqa: E402
from ml.visualization.track_plots import draw_track  # noqa: E402

PEDIDO = "docs/prompts/2026-10-05_23_voltas-secas-f1.md"
CACHE_DIR = config.repo_root() / "data" / "fastf1_cache"
DEFAULT_OUT = config.artifacts_root() / "externo" / "f1_faixa"
# A volta de chuva: Norris, classificacao de 2024, volta 32 (pedido 22).
RAIN_LAP = (2024, f1_dry_laps.QUALIFYING, "NOR", 32)
P22_DIR = config.artifacts_root() / "externo"
P22_SUMMARY = P22_DIR / "fastf1_alinhamento_resumo.json"
P22_GRID = P22_DIR / "fastf1_linha_na_grade.csv"

MANIFEST_FILE = "manifesto.json"
SUMMARY_FILE = "resumo.json"
BAND_FILE = "faixa.csv"
TRACK_FIGURE = "faixa_pista.png"
LATERAL_FIGURE = "faixa_lateral.png"

COLOURS = {"f1": "#ff7a1a", "ia": "#4fa3ff", "humano": "#2ca02c", "chuva": "#9467bd", "faixa": "#ff9f5a"}


def folder_bytes(path: Path) -> int:
    return int(sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file()))


# ---------------------------------------------------------------- coleta ---

def plan_sessions(fastf1, years: Sequence[int]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """As sessoes de cada ano conferidas pelo nome e pela data no calendario do FastF1."""
    chosen, skipped = [], []
    for year in years:
        try:
            event = fastf1.get_event(int(year), f1_dry_laps.EVENT)
        except Exception as exc:
            skipped.append({"ano": int(year), "nome": None, "motivo": f"calendario: {type(exc).__name__}: {exc}"})
            continue
        take, leave = f1_dry_laps.choose_sessions(event)
        chosen += [{"ano": int(year), "evento": str(event.get("EventName", "")), **row} for row in take]
        skipped += [{"ano": int(year), "evento": str(event.get("EventName", "")), **row} for row in leave]
    return chosen, skipped


def collect(fastf1, plan: Sequence[Dict[str, object]]) -> List[f1_dry_laps.SessionData]:
    out = []
    for row in plan:
        extra = [RAIN_LAP[2:]] if (row["ano"], row["nome"]) == RAIN_LAP[:2] else []
        data = f1_dry_laps.collect_session(fastf1, int(row["ano"]), str(row["nome"]), str(row["tipo"]),
                                           extra_laps=extra)
        data.info["data_no_calendario"] = row["data"]
        state = "ok" if data.info["carregou"] else f"ERRO {data.info.get('erro')}"
        print(f"  {row['ano']} {row['nome']}: {state} ({data.info['tempo_de_carga_s']:.1f} s)", flush=True)
        out.append(data)
    return out


# ---------------------------------------------------------------- figuras ---

def zoom_windows(track: TrackGeometry) -> List[Tuple[str, float, float]]:
    """S do Senna (C01 ate a saida da C02), Bico de Pato (C10) e Juncao (C12)."""
    corners = detect_corners(track)
    senna = corner_by_name(corners, "S do Senna")
    after_senna = corners[[c.index for c in corners].index(senna.index) + 1]
    pato = corner_by_name(corners, "Bico de Pato")
    juncao = corner_by_name(corners, "Juncao")
    return [
        ("S do Senna", senna.start_s - ZOOM_MARGIN_M, after_senna.end_s + ZOOM_MARGIN_M),
        ("Bico de Pato", pato.start_s - ZOOM_MARGIN_M, pato.end_s + ZOOM_MARGIN_M),
        ("Junção", juncao.start_s - ZOOM_MARGIN_M, juncao.end_s + ZOOM_MARGIN_M),
    ]


def _draw_track_band(ax, track: TrackGeometry, faixa: Dict[str, np.ndarray], lines: Dict[str, np.ndarray],
                     window=None) -> None:
    draw_track(track, ax)
    high = _closed(track.to_world(track.s, faixa["p90"]))
    low = _closed(track.to_world(track.s, faixa["p10"]))
    ax.fill(np.concatenate([high[:, 0], low[::-1, 0]]), np.concatenate([high[:, 1], low[::-1, 1]]),
            color=COLOURS["faixa"], alpha=0.45, linewidth=0, zorder=2)
    for key, width in (("humano", 1.2), ("ia", 1.2), ("f1", 1.5)):
        xy = _closed(track.to_world(track.s, lines[key]))
        ax.plot(xy[:, 0], xy[:, 1], color=COLOURS[key], linewidth=width, zorder=3)
    if window is not None:
        start, end = window
        inside = (track.s >= start) & (track.s <= end)
        span = np.vstack([track.to_world(track.s[inside], track.width_left[inside] + 1.0),
                          track.to_world(track.s[inside], -track.width_right[inside] - 1.0)])
        pad = 8.0
        ax.set_xlim(span[:, 0].min() - pad, span[:, 0].max() + pad)
        ax.set_ylim(span[:, 1].min() - pad, span[:, 1].max() + pad)


def plot_track(path: Path, track: TrackGeometry, faixa, lines, windows, laps: int, sessions: int) -> Path:
    figure = plt.figure(figsize=(16, 12))
    grid = figure.add_gridspec(3, 2, width_ratios=[1.3, 1.0], hspace=0.3)
    full = figure.add_subplot(grid[:, 0])
    _draw_track_band(full, track, faixa, lines)
    full.set_title("Interlagos, geometria oficial " + track.geometry_id, fontsize=10)
    for row, (name, start, end) in enumerate(windows):
        ax = figure.add_subplot(grid[row, 1])
        _draw_track_band(ax, track, faixa, lines, window=(start, end))
        ax.set_title(f"{name} (s = {start:.0f} a {end:.0f} m)", fontsize=10)
        box = np.vstack([ax.get_xlim(), ax.get_ylim()]).T
        full.add_patch(plt.Rectangle((box[0, 0], box[0, 1]), box[1, 0] - box[0, 0], box[1, 1] - box[0, 1],
                                     fill=False, edgecolor="#d62728", linewidth=1.2, zorder=6))
        full.annotate(name, (box[1, 0] + 4.0, box[1, 1]), color="#d62728", fontsize=9)
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOURS["faixa"], alpha=0.45, label="faixa da F1, p10 a p90"),
        plt.Line2D([], [], color=COLOURS["f1"], linewidth=1.6, label="mediana da F1"),
        plt.Line2D([], [], color=COLOURS["ia"], linewidth=1.4, label="mediana das voltas ia de 04/10"),
        plt.Line2D([], [], color=COLOURS["humano"], linewidth=1.4, label="mediana das voltas humano (atual)"),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=4, fontsize=9, frameon=False)
    figure.suptitle(f"Faixa das linhas da F1 (posição do FastF1), voltas secas de classificação (pedido 23): "
                    f"{laps} voltas de {sessions} sessões", fontsize=11)
    figure.tight_layout(rect=(0, 0.04, 1, 0.96))
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return path


def plot_lateral(path: Path, track: TrackGeometry, sectors: Microsectors, faixa, lines,
                 rain: Optional[np.ndarray], rain_label: str, unreliable: Sequence[int]) -> Path:
    rows = 4
    figure, axes = plt.subplots(rows, 1, figsize=(16, 15))
    edges = np.linspace(0.0, track.length, rows + 1)
    low, high = track.corridor()
    for ax, start, end in zip(axes, edges[:-1], edges[1:]):
        mask = (track.s >= start) & (track.s <= end)
        s = track.s[mask]
        for k in unreliable:
            a, b = sectors.edges_s[k], sectors.edges_s[k + 1]
            if b > start and a < end:
                ax.axvspan(max(a, start), min(b, end), color="#bbbbbb", alpha=0.35, linewidth=0, zorder=0)
        ax.plot(s, low[mask], color="#8a8a93", linewidth=0.7, linestyle="--", zorder=1)
        ax.plot(s, high[mask], color="#8a8a93", linewidth=0.7, linestyle="--", zorder=1)
        ax.fill_between(s, faixa["p10"][mask], faixa["p90"][mask], color=COLOURS["faixa"], alpha=0.45,
                        linewidth=0, zorder=2)
        ax.plot(s, lines["f1"][mask], color=COLOURS["f1"], linewidth=1.5, zorder=4)
        ax.plot(s, lines["ia"][mask], color=COLOURS["ia"], linewidth=1.1, zorder=3)
        ax.plot(s, lines["humano"][mask], color=COLOURS["humano"], linewidth=1.1, zorder=3)
        if rain is not None:
            ax.plot(s, rain[mask], color=COLOURS["chuva"], linewidth=1.1, linestyle="--", zorder=3)
        for edge in sectors.edges_s:
            if start <= edge <= end:
                ax.axvline(edge, color="#dddddd", linewidth=0.5, zorder=0)
        ax.set_xlim(start, end)
        ax.set_ylabel("lateral (m), + à esquerda")
    axes[-1].set_xlabel("s (m)")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=COLOURS["faixa"], alpha=0.45, label="faixa da F1, p10 a p90"),
        plt.Line2D([], [], color=COLOURS["f1"], linewidth=1.6, label="mediana da F1"),
        plt.Line2D([], [], color=COLOURS["ia"], linewidth=1.2, label="mediana das voltas ia de 04/10"),
        plt.Line2D([], [], color=COLOURS["humano"], linewidth=1.2, label="mediana das voltas humano (atual)"),
        plt.Line2D([], [], color=COLOURS["chuva"], linewidth=1.2, linestyle="--", label=rain_label),
        plt.Line2D([], [], color="#8a8a93", linewidth=0.8, linestyle="--", label="corredor (ml/track)"),
        plt.Rectangle((0, 0), 1, 1, color="#bbbbbb", alpha=0.35, label="faixa pouco confiável (V1 ou V2)"),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=4, fontsize=9, frameon=False)
    figure.suptitle("Lateral × s: faixa da F1, IA, piloto e volta de chuva (pedido 23)", fontsize=11)
    figure.tight_layout(rect=(0, 0.05, 1, 0.97))
    figure.savefig(path, dpi=110)
    plt.close(figure)
    return path


# ------------------------------------------------------------------ fluxo ---

def _sector_rows(sectors: Microsectors, **columns) -> List[Dict[str, object]]:
    rows = []
    for k in range(sectors.count):
        row = {"microsetor": k, "inicio_m": float(sectors.edges_s[k]), "fim_m": float(sectors.edges_s[k + 1])}
        for name, values in columns.items():
            row[name] = None if values is None else float(values[k])
        rows.append(row)
    return rows


def _abs_summary(values: np.ndarray) -> Dict[str, float]:
    values = np.abs(np.asarray(values, dtype=float))
    return {"mediana": float(np.median(values)), "p90": float(np.percentile(values, 90)), "max": float(values.max())}


def session_diagnosis(main: np.ndarray, sessions: Sequence[str], rain: Optional[np.ndarray]) -> Dict[str, object]:
    """Descritivo, por sessao: quanto as voltas variam entre si e quanto a sessao se afasta do resto.

    * `dispersao_entre_voltas_m`: por ponto da grade, o desvio-padrao e a
      amplitude (max - min) do lateral entre as voltas da sessao, resumidos pela
      mediana e pelo p90 dos pontos;
    * `ate_a_mediana_geral_m`: |mediana da sessao - mediana de todas as voltas|;
    * `volta_de_chuva_ate_a_mediana_da_sessao_m`: |volta de chuva - mediana da sessao|.

    Nao muda a faixa nem nenhum criterio.
    """
    labels = np.asarray(list(sessions))
    overall = np.median(main, axis=0)
    out: Dict[str, object] = {}
    for key in dict.fromkeys(sessions):
        laps = main[labels == key]
        median = np.median(laps, axis=0)
        spread = laps.max(axis=0) - laps.min(axis=0)
        sd = laps.std(axis=0)
        out[key] = {
            "voltas": int(len(laps)),
            "dispersao_entre_voltas_m": {
                "dp_mediano": float(np.median(sd)), "dp_p90": float(np.percentile(sd, 90)),
                "amplitude_mediana": float(np.median(spread)), "amplitude_p90": float(np.percentile(spread, 90)),
            },
            "ate_a_mediana_geral_m": _abs_summary(median - overall),
            "volta_de_chuva_ate_a_mediana_da_sessao_m": None if rain is None else _abs_summary(rain - median),
        }
    return out


def conference_with_p22(track: TrackGeometry, fit: f1_band.LapFit) -> Dict[str, object]:
    """A volta de Norris pelo caminho novo (posicao crua) contra os numeros do pedido 22."""
    old = json.loads(P22_SUMMARY.read_text(encoding="utf-8"))
    grid = pd.read_csv(P22_GRID)
    delta = np.abs(fit.line.grid_lateral - grid["lateral_f1"].to_numpy(dtype=float))
    return {
        "aviso": "so relato; nao muda nada",
        "pedido_22": {
            "fracao_fora": old["etapa4_erro"]["na_grade"]["fracao_fora"],
            "p95_excesso_m": old["etapa4_erro"]["na_grade"]["p95_m"],
            "escala_m_por_unidade": old["etapa2_alinhamento"]["escala_m_por_unidade"],
            "rotacao_graus": old["etapa2_alinhamento"]["rotacao_graus"],
            "amostras": old["entrada"]["amostras"],
        },
        "caminho_novo": {
            "fracao_fora": fit.summary["fracao_fora"],
            "p95_excesso_m": fit.summary["p95_m"],
            "escala_m_por_unidade": fit.similarity.scale,
            "rotacao_graus": fit.similarity.rotation_deg,
            "espelhado": fit.similarity.mirrored,
        },
        "diferenca_de_lateral_ponto_a_ponto_m": {
            "mediana": float(np.median(delta)), "p95": float(np.percentile(delta, 95)), "max": float(delta.max()),
        },
    }


def run(out_dir: Path, years: Sequence[int] = f1_dry_laps.YEARS) -> Dict[str, object]:
    started = time.perf_counter()
    track = load_geometry()
    if track.geometry_id != OFFICIAL_GEOMETRY_ID:
        raise SystemExit(f"PARADO: a geometria carregada e {track.geometry_id}, e o pedido fala da "
                         f"{OFFICIAL_GEOMETRY_ID}.")
    meta = store_v2_meta()
    if not meta or not meta.get("aprovado"):
        raise SystemExit("PARADO: store v2 ausente ou sem as checagens aprovadas.")
    store = load_store_v2(track=track)
    if store.geometry_id != track.geometry_id:
        raise SystemExit(f"PARADO: o store v2 e da geometria {store.geometry_id}.")
    sectors = build_microsectors(track)

    import fastf1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_before = folder_bytes(CACHE_DIR)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    # Parte B: sessoes, funil e leitura de X/Y.
    plan, skipped = plan_sessions(fastf1, years)
    print(f"{len(plan)} sessoes no plano; {len(skipped)} ligadas a sprint fora", flush=True)
    sessions = collect(fastf1, plan)
    loaded = [data for data in sessions if data.info["carregou"]]
    cache_after = folder_bytes(CACHE_DIR)
    collected_s = time.perf_counter() - started
    if not loaded:
        raise SystemExit("PARADO: nenhuma sessao carregou. " + "; ".join(
            f"{d.info['ano']} {d.info['sessao']}: {d.info.get('erro')}" for d in sessions))

    # Parte C, itens 1 e 3: alinhamento e criterio por volta.
    out_dir.mkdir(parents=True, exist_ok=True)
    lap_dir = out_dir / "voltas"
    lap_dir.mkdir(exist_ok=True)
    fits: Dict[str, f1_band.LapFit] = {}
    raws: Dict[str, np.ndarray] = {}
    lap_session: Dict[str, str] = {}
    rain_fit: Optional[f1_band.LapFit] = None
    for data in loaded:
        session_key = f"{data.info['ano']} {data.info['sessao']}"
        for record in data.laps:
            if record["chave"] not in data.xy:
                continue
            raw = data.xy[record["chave"]]
            fit = f1_band.fit_lap(track, raw)
            record["criterio"] = fit.verdict
            record["alinhamento"] = {
                "escala_m_por_unidade": fit.similarity.scale,
                "escala_sobre_o_decimetro": fit.similarity.scale / f1_band.NOMINAL_M_PER_UNIT,
                "rotacao_graus": fit.similarity.rotation_deg,
                "espelhado": fit.similarity.mirrored,
                "icp": fit.fit["icp"],
            }
            if record.get("a_parte"):
                rain_fit = fit
                continue
            print(f"    {record['chave']}: {fit.verdict['veredito']} (cob {fit.verdict['cobertura']:.4f}, "
                  f"buraco {fit.verdict['maior_buraco_m']:.1f} m, fora {fit.verdict['fracao_fora']:.4f}, "
                  f"p95 {fit.verdict['p95_excesso_m']:.2f} m)", flush=True)
            if fit.verdict["aceita"]:
                fits[record["chave"]] = fit
                raws[record["chave"]] = raw
                lap_session[record["chave"]] = session_key
                pd.DataFrame({"s": track.s, "lateral": fit.line.grid_lateral, "excesso_m": fit.excess}).to_csv(
                    lap_dir / f"{record['chave']}.csv", index=False, float_format="%.4f")
    accepted = list(fits)
    session_keys = list(dict.fromkeys(lap_session[key] for key in accepted))

    # Parte C, item 4: incerteza do alinhamento (V1 e V2). Nunca escolhe volta.
    main = np.vstack([fits[key].line.grid_lateral for key in accepted]) if accepted else np.zeros((0, track.size))
    v1_lateral, v1_info = [], {}
    for key in accepted:
        sim, info = f1_line.align_fixed_scale(raws[key], track, fits[key].similarity, f1_band.NOMINAL_M_PER_UNIT)
        v1_lateral.append(f1_band.grid_lateral(track, raws[key], sim))
        v1_info[key] = {"rotacao_graus": sim.rotation_deg, "convergiu": info["convergiu"],
                        "iteracoes": info["iteracoes"]}
    v2_lateral: Dict[str, np.ndarray] = {}
    per_session: Dict[str, Dict[str, object]] = {}
    for session_key in session_keys:
        keys = [key for key in accepted if lap_session[key] == session_key]
        sims = [fits[key].similarity for key in keys]
        centroid = np.vstack([raws[key] for key in keys]).mean(axis=0)
        sim, info = f1_line.refine_icp_session([raws[key] for key in keys], track, sims[0])
        for key in keys:
            v2_lateral[key] = f1_band.grid_lateral(track, raws[key], sim)
        relative = np.array([s.scale for s in sims]) / f1_band.NOMINAL_M_PER_UNIT
        per_session[session_key] = {
            "dispersao_por_volta": {
                **f1_band.transform_spread(sims, centroid),
                "escala_sobre_o_decimetro": {"min": float(relative.min()), "mediana": float(np.median(relative)),
                                             "max": float(relative.max())},
            },
            "transformacao_da_sessao": {
                "escala_m_por_unidade": sim.scale, "escala_sobre_o_decimetro": sim.scale / f1_band.NOMINAL_M_PER_UNIT,
                "rotacao_graus": sim.rotation_deg, "espelhado": sim.mirrored,
                "centroide_vai_para_m": [float(v) for v in sim.apply(centroid.reshape(1, 2))[0]], **info,
            },
        }
    v1 = v2 = None
    unreliable: List[int] = []
    if accepted:
        v1_diff = np.vstack(v1_lateral) - main
        v2_diff = np.vstack([v2_lateral[key] for key in accepted]) - main
        v1 = f1_band.sector_abs_stats(sectors, v1_diff)
        v2 = f1_band.sector_abs_stats(sectors, v2_diff)
        unreliable = f1_band.unreliable_sectors(v1["p90"], v2["p90"])
        for i, key in enumerate(accepted):
            v1_info[key]["abs_mediana_m"] = float(np.median(np.abs(v1_diff[i])))
            v1_info[key]["abs_p90_m"] = float(np.percentile(np.abs(v1_diff[i]), 90))

    # Parte C, item 5: a faixa.
    formed = f1_band.band_is_formed(len(accepted), len(session_keys))
    rain_line, rain_label, rain_source = None, "", None
    if rain_fit is not None:
        rain_line = rain_fit.line.grid_lateral
        rain_label = "volta de chuva 2024 (NOR, Q, 32), posição crua"
        rain_source = "dados de posicao crus (get_pos_data), pelo caminho novo"
    elif P22_GRID.exists():
        rain_line = pd.read_csv(P22_GRID)["lateral_f1"].to_numpy(dtype=float)
        rain_label = "volta de chuva 2024 (NOR, Q, 32), linha do pedido 22"
        rain_source = ("a classificacao de 2024 nao carregou; linha ja alinhada do pedido 22 "
                       "(fastf1_linha_na_grade.csv, que veio do get_telemetry)")

    result: Dict[str, object] = {
        "pedido": PEDIDO,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "fastf1_versao": getattr(fastf1, "__version__", None),
        "campos_lidos": ["X", "Y"],
        "nao_lidos": "velocidade, pedais, marcha, rotacao, DRS e distancia (ADR 0018); get_telemetry nao e usado",
        "cache": {"pasta": str(CACHE_DIR), "bytes_antes": cache_before, "bytes_depois": cache_after},
        "tempo_s": {"coleta": collected_s},
        "sessoes_fora_do_plano": skipped,
        "sessoes": [data.info for data in sessions],
        "criterio_por_volta": {
            "regra": "cobertura >= 0,99, maior buraco <= 80 m, fracao fora <= 10% e p95 do excesso <= 1 m; "
                     "fixado antes de rodar",
            "voltas_escolhidas": int(sum(1 for d in loaded for r in d.laps if r["etapa"] == "escolhida")),
            "voltas_aceitas": len(accepted),
            "sessoes_com_voltas_aceitas": session_keys,
        },
        "incerteza": {
            "v1": "escala presa em 0,1 m por unidade; so rotacao, translacao e espelho",
            "v2": "uma transformacao por sessao, ajustada com todas as voltas aceitas da sessao",
            "por_sessao": per_session,
            "por_volta_v1": v1_info,
            "limite_p90_m": f1_band.UNRELIABLE_P90_M,
            "microsetores_pouco_confiaveis": [sectors.label(k) for k in unreliable],
            "por_microsetor": _sector_rows(
                sectors,
                v1_mediana_m=None if v1 is None else v1["mediana"], v1_p90_m=None if v1 is None else v1["p90"],
                v2_mediana_m=None if v2 is None else v2["mediana"], v2_p90_m=None if v2 is None else v2["p90"]),
        },
        "faixa": {"formada": formed, "minimo": {"voltas": f1_band.MIN_BAND_LAPS,
                                                "sessoes": f1_band.MIN_BAND_SESSIONS},
                  "voltas": len(accepted), "sessoes": len(session_keys)},
        "volta_de_chuva": {"fonte": rain_source, "criterio": None if rain_fit is None else rain_fit.verdict},
        "conferencia_pedido_22": None,
    }
    if rain_fit is not None:
        result["conferencia_pedido_22"] = conference_with_p22(track, rain_fit)
    else:
        result["conferencia_pedido_22"] = {"feita": False, "motivo": "a classificacao de 2024 nao carregou"}

    if formed:
        faixa = f1_band.band(main)
        spread = f1_band.session_spread(sectors, main, [lap_session[key] for key in accepted])
        per_point = {}
        for name, lateral in (("v1", np.vstack(v1_lateral)), ("v2", np.vstack([v2_lateral[k] for k in accepted]))):
            diff = np.abs(lateral - main)
            per_point[f"{name}_mediana_abs_m"] = np.median(diff, axis=0)
            per_point[f"{name}_p90_abs_m"] = np.percentile(diff, 90, axis=0)
        pd.DataFrame({"s": track.s, "microsetor": sectors.index, "p10": faixa["p10"], "p50": faixa["p50"],
                      "p90": faixa["p90"], "n": faixa["n"], **per_point}).to_csv(
            out_dir / BAND_FILE, index=False, float_format="%.4f")

        # Parte C, item 6: comparacao descritiva.
        ai = labelled_ai_laps(store.laps)
        human = ev.driver_laps(store.laps)
        ai_ids, human_ids = ai["lap_id"].tolist(), human["lap_id"].tolist()
        ai_laps, human_laps = lateral_matrix(store, ai_ids), lateral_matrix(store, human_ids)
        ai_median, human_median = np.median(ai_laps, axis=0), np.median(human_laps, axis=0)
        vs_ai = f1_band.difference_table(sectors, faixa["p50"], ai_laps)
        vs_human = f1_band.difference_table(sectors, faixa["p50"], human_laps)
        comparison = {
            "aviso": "descritivo, so para leitura; nada muda coach, store ou criterio",
            "voltas_ia": ai_ids,
            "voltas_humano": human_ids,
            "ia": f1_band.compare_to_band(sectors, ai_median, faixa["p10"], faixa["p90"]),
            "humano": f1_band.compare_to_band(sectors, human_median, faixa["p10"], faixa["p90"]),
            "chuva": None if rain_line is None else f1_band.compare_to_band(
                sectors, rain_line, faixa["p10"], faixa["p90"]),
            "mediana_f1_menos_ia": vs_ai["resumo"],
            "mediana_f1_menos_humano": vs_human["resumo"],
            "por_microsetor_diferenca": _sector_rows(sectors, f1_menos_ia_m=vs_ai["por_microsetor"],
                                                     f1_menos_humano_m=vs_human["por_microsetor"]),
        }
        windows = zoom_windows(track)
        lines = {"f1": faixa["p50"], "ia": ai_median, "humano": human_median}
        track_png = plot_track(out_dir / TRACK_FIGURE, track, faixa, lines, windows, len(accepted),
                               len(session_keys))
        lateral_png = plot_lateral(out_dir / LATERAL_FIGURE, track, sectors, faixa, lines, rain_line,
                                   rain_label, unreliable)
        result["faixa"].update({
            "por_microsetor": _sector_rows(
                sectors,
                p10_m=f1_band.sector_median(sectors, faixa["p10"]),
                p50_m=f1_band.sector_median(sectors, faixa["p50"]),
                p90_m=f1_band.sector_median(sectors, faixa["p90"]),
                largura_p10_p90_m=f1_band.sector_median(sectors, faixa["p90"] - faixa["p10"]),
                amplitude_entre_sessoes_m=spread["amplitude"]),
            "largura_p10_p90_m": {"mediana": float(np.median(faixa["p90"] - faixa["p10"])),
                                  "p90": float(np.percentile(faixa["p90"] - faixa["p10"], 90))},
            "amplitude_entre_sessoes_m": {"mediana": float(np.median(spread["amplitude"])),
                                          "p90": float(np.percentile(spread["amplitude"], 90)),
                                          "max": float(spread["amplitude"].max()),
                                          "microsetor_do_max": sectors.label(int(np.argmax(spread["amplitude"])))},
            "voltas_por_sessao": spread["voltas_por_sessao"],
            "diagnostico_por_sessao": session_diagnosis(main, [lap_session[key] for key in accepted], rain_line),
            "lateral_medio_m": {"mediana_f1": float(faixa["p50"].mean()), "mediana_ia": float(ai_median.mean()),
                                "mediana_humano": float(human_median.mean())},
        })
        result["comparacao"] = comparison
        result["figuras"] = {"pista": str(track_png), "lateral": str(lateral_png),
                             "zooms": [{"nome": n, "inicio_s_m": a, "fim_s_m": b} for n, a, b in windows]}
    else:
        result["faixa"]["motivo"] = (f"faixa nao formada: {len(accepted)} voltas aceitas de {len(session_keys)} "
                                     f"sessoes; o minimo e {f1_band.MIN_BAND_LAPS} voltas de "
                                     f"{f1_band.MIN_BAND_SESSIONS} sessoes")

    result["tempo_s"]["total"] = time.perf_counter() - started
    result = _round(result)
    manifest = {
        "pedido": PEDIDO,
        "gerado_em": result["gerado_em"],
        "commit": result["commit"],
        "sessoes_fora_do_plano": result["sessoes_fora_do_plano"],
        "sessoes": result["sessoes"],
        "voltas": _round([record for data in sessions for record in data.laps]),
    }
    (out_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (out_dir / SUMMARY_FILE).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def print_report(result: Dict[str, object]) -> None:
    print("=" * 72)
    for info in result["sessoes"]:
        state = info.get("erro") or info.get("fora") or info.get("funil")
        print(f"{info['ano']} {info['sessao']}: {state}")
    rule = result["criterio_por_volta"]
    print(f"escolhidas {rule['voltas_escolhidas']}, aceitas {rule['voltas_aceitas']} de "
          f"{len(rule['sessoes_com_voltas_aceitas'])} sessoes")
    print(f"pouco confiaveis: {result['incerteza']['microsetores_pouco_confiaveis']}")
    print(f"faixa: {result['faixa'].get('motivo') or 'formada'}")
    if "comparacao" in result:
        comparison = result["comparacao"]
        for key in ("ia", "humano", "chuva"):
            if comparison[key]:
                print(f"  {key}: {comparison[key]['microsetores_dentro']} de 60 microsetores dentro")
        print(f"  F1 - IA {comparison['mediana_f1_menos_ia']}; F1 - humano {comparison['mediana_f1_menos_humano']}")
    print(f"conferencia: {result['conferencia_pedido_22']}")
    print(f"cache {result['cache']}; tempo {result['tempo_s']}")
    print("=" * 72)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        result = run(args.saida)
    except SystemExit as stop:
        print(stop)
        return 2
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
