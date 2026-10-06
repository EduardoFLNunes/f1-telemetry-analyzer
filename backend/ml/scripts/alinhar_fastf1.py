"""Alinha a volta da F1 importada pelo FastF1 a geometria oficial e mede o erro (pedido 22).

    python -m ml.scripts.alinhar_fastf1 [--referencia ARQUIVO] [--saida data/ml/externo]

So a posicao (`x`, `y`) da volta e lida: velocidade, pedais e pontos de
frenagem sao de outro carro (ADR 0018). Nada e treinado, e nada muda coach,
store ou criterio: a comparacao com as voltas do store v2 e so descritiva.

Escreve, fora do git:

* `fastf1_alinhamento_resumo.json` -- os numeros das etapas 1 a 5 e o veredito
  do criterio fixado no pedido 22;
* `fastf1_linha_na_grade.csv` -- a linha na grade: `s`, lateral, corredor,
  excesso e as linhas medianas da IA e do piloto;
* `fastf1_alinhamento.png` -- a pista, a linha da F1 alinhada e a mediana da
  IA, com zoom no S do Senna e no Bico de Pato.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison import evolution as ev  # noqa: E402
from ml.data.origin import AI, SOURCE_ANNOTATION, SOURCE_INDICATOR, SOURCE_SESSION_ANNOTATION  # noqa: E402
from ml.data.store_v2 import file_entry, git_commit, load_store_v2, store_v2_meta  # noqa: E402
from ml.external import f1_line  # noqa: E402
from ml.track.corners import Corner, detect_corners  # noqa: E402
from ml.track.geometry import TrackGeometry, load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from ml.track.trajectory import path_length  # noqa: E402
from ml.validation.controlled import CORNER_NAMES  # noqa: E402
from ml.visualization.track_plots import draw_track  # noqa: E402

DEFAULT_REFERENCE = config.repo_root() / "data" / "external_references" / (
    "fastf1__2024__Brazil__Q__NOR__32__093bbee0.json"
)
OFFICIAL_GEOMETRY_ID = "0ed16f0dd2225990"
# As voltas `ia` rotuladas da sessao de 04/10 (ADR 0018, esclarecimento do pedido 22):
# rotulo pelo indicador do jogo ou por anotacao, nunca pelo detector.
AI_DAY = "2026-10-04"
LABELLED_SOURCES = (SOURCE_INDICATOR, SOURCE_ANNOTATION, SOURCE_SESSION_ANNOTATION)
# Margem de cada zoom alem da curva, em metros de `s`.
ZOOM_MARGIN_M = 40.0

SUMMARY_FILE = "fastf1_alinhamento_resumo.json"
GRID_FILE = "fastf1_linha_na_grade.csv"
FIGURE_FILE = "fastf1_alinhamento.png"


# ----------------------------------------------------------------- voltas ---

def labelled_ai_laps(laps: pd.DataFrame, day: str = AI_DAY) -> pd.DataFrame:
    """Voltas `ia` rotuladas do dia, com o relogio conferido e nao suspeito."""
    mask = (
        (laps["origem"] == AI)
        & laps["origem_fonte"].isin(LABELLED_SOURCES)
        & (laps["session_id"].str[:10] == day)
        & laps["relogio_verificado"].fillna(False).astype(bool)
        & ~laps["relogio_suspeito"].fillna(True).astype(bool)
    )
    return laps[mask]


def lateral_matrix(store, lap_ids: Sequence[str]) -> np.ndarray:
    return np.vstack([store.lap(lap_id)["lateral"].to_numpy(dtype=float) for lap_id in lap_ids])


# ----------------------------------------------------------------- figura ---

def corner_by_name(corners: Sequence[Corner], name: str) -> Corner:
    label = CORNER_NAMES[name]
    for corner in corners:
        if corner.label == label:
            return corner
    raise SystemExit(f"PARADO: a curva {name} ({label}) nao foi detectada na geometria.")


def zoom_windows(corners: Sequence[Corner]) -> List[Tuple[str, float, float]]:
    """S do Senna: da entrada da C01 a saida da C02. Bico de Pato: a C10."""
    senna = corner_by_name(corners, "S do Senna")
    after_senna = corners[[c.index for c in corners].index(senna.index) + 1]
    pato = corner_by_name(corners, "Bico de Pato")
    return [
        ("S do Senna", senna.start_s - ZOOM_MARGIN_M, after_senna.end_s + ZOOM_MARGIN_M),
        ("Bico de Pato", pato.start_s - ZOOM_MARGIN_M, pato.end_s + ZOOM_MARGIN_M),
    ]


def _closed(points: np.ndarray) -> np.ndarray:
    return np.vstack([points, points[:1]])


def draw_lines(ax, track: TrackGeometry, f1: np.ndarray, ai: np.ndarray, samples: np.ndarray,
               window=None) -> None:
    draw_track(track, ax)
    low, high = track.corridor()
    for bound in (low, high):
        edge = _closed(track.to_world(track.s, bound))
        ax.plot(edge[:, 0], edge[:, 1], color="#c9a227", linewidth=0.6, linestyle="--", zorder=2)
    centre = _closed(track.points)
    ax.plot(centre[:, 0], centre[:, 1], color="#6b6b75", linewidth=0.6, linestyle=":", zorder=2)
    ai_xy = _closed(track.to_world(track.s, ai))
    f1_xy = _closed(track.to_world(track.s, f1))
    ax.plot(ai_xy[:, 0], ai_xy[:, 1], color="#4fa3ff", linewidth=1.4, zorder=3)
    ax.plot(f1_xy[:, 0], f1_xy[:, 1], color="#ff7a1a", linewidth=1.4, zorder=4)
    if window is not None:
        ax.scatter(samples[:, 0], samples[:, 1], s=9, color="#ff7a1a", edgecolor="white",
                   linewidth=0.4, zorder=5)
        start, end = window
        inside = (track.s >= start) & (track.s <= end)
        span = np.vstack([track.to_world(track.s[inside], track.width_left[inside] + 1.0),
                          track.to_world(track.s[inside], -track.width_right[inside] - 1.0)])
        pad = 8.0
        ax.set_xlim(span[:, 0].min() - pad, span[:, 0].max() + pad)
        ax.set_ylim(span[:, 1].min() - pad, span[:, 1].max() + pad)


def plot_figure(path: Path, track: TrackGeometry, f1: np.ndarray, ai: np.ndarray, samples: np.ndarray,
                windows, verdict_text: str, mirrored: bool) -> Path:
    figure = plt.figure(figsize=(15, 10))
    grid = figure.add_gridspec(2, 2, width_ratios=[1.25, 1.0], hspace=0.28)
    full = figure.add_subplot(grid[:, 0])
    draw_lines(full, track, f1, ai, samples)
    full.set_title("Interlagos, geometria oficial " + track.geometry_id, fontsize=10)
    zooms = [figure.add_subplot(grid[row, 1]) for row in (0, 1)]
    for ax, (name, start, end) in zip(zooms, windows):
        draw_lines(ax, track, f1, ai, samples, window=(start, end))
        ax.set_title(f"{name} (s = {start:.0f} a {end:.0f} m)", fontsize=10)
        box = np.vstack([ax.get_xlim(), ax.get_ylim()]).T
        full.add_patch(plt.Rectangle((box[0, 0], box[0, 1]), box[1, 0] - box[0, 0], box[1, 1] - box[0, 1],
                                     fill=False, edgecolor="#d62728", linewidth=1.2, zorder=6))
        full.annotate(name, (box[1, 0] + 4.0, box[1, 1]), color="#d62728", fontsize=9)
    handles = [
        plt.Line2D([], [], color="#ff7a1a", linewidth=1.6, label="F1 2024 (NOR, Q, volta 32), alinhada"),
        plt.Line2D([], [], color="#4fa3ff", linewidth=1.6, label="mediana das 13 voltas ia de 04/10"),
        plt.Line2D([], [], color="#c9a227", linewidth=0.8, linestyle="--", label="corredor (ml/track)"),
        plt.Line2D([], [], color="#6b6b75", linewidth=0.8, linestyle=":", label="linha central oficial"),
        plt.Line2D([], [], color="#ff7a1a", marker="o", linestyle="", markersize=4,
                   label="amostras do FastF1 (zoom)"),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=5, fontsize=8, frameon=False)
    figure.suptitle(
        "Forma da linha da F1 na geometria oficial (pedido 22). Alinhamento rígido com escala única"
        + (", com espelho" if mirrored else "") + f". Critério: {verdict_text}.",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.96))
    figure.savefig(path, dpi=130)
    plt.close(figure)
    return path


# ------------------------------------------------------------------ fluxo ---

def _round(value, digits: int = 4):
    if isinstance(value, dict):
        return {k: _round(v, digits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v, digits) for v in value]
    if isinstance(value, (float, np.floating)):
        return round(float(value), digits)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def run(reference: Path, out_dir: Path) -> Dict[str, object]:
    track = load_geometry()
    if track.geometry_id != OFFICIAL_GEOMETRY_ID:
        raise SystemExit(f"PARADO: a geometria carregada e {track.geometry_id}, e o pedido 22 fala da "
                         f"{OFFICIAL_GEOMETRY_ID}.")
    meta = store_v2_meta()
    if not meta or not meta.get("aprovado"):
        raise SystemExit("PARADO: store v2 ausente ou sem as checagens aprovadas.")
    store = load_store_v2(track=track)
    if store.geometry_id != track.geometry_id:
        raise SystemExit(f"PARADO: o store v2 e da geometria {store.geometry_id}.")
    sectors = build_microsectors(track)

    # Etapa 1: unidade e amostragem, so com x e y.
    raw, identity = f1_line.load_xy(reference)
    unit = f1_line.infer_unit(raw, track.length)
    spacing = f1_line.spacing_summary(f1_line.segment_lengths(raw) * unit["metros_por_unidade"])

    # Etapa 2: alinhamento rigido com escala unica contra a linha central.
    similarity, fit = f1_line.align(raw, track)
    aligned = similarity.apply(raw)
    aligned_length = float(f1_line.segment_lengths(aligned).sum())

    # Etapa 3: projecao na grade.
    line = f1_line.project_to_grid(track, aligned)
    s_steps = np.diff(np.maximum.accumulate(line.s_unwrapped))
    closing = float(line.s_unwrapped[0] + track.length - np.maximum.accumulate(line.s_unwrapped)[-1])

    # Etapa 4: erro de alinhamento, o excesso sobre o corredor.
    excess = f1_line.excess_on_grid(track, line.grid_lateral)
    summary = f1_line.excess_summary(excess)
    verdict = f1_line.verdict(summary)
    at_samples = f1_line.excess_summary(f1_line.excess_at_samples(track, line.s, line.lateral))
    worst = f1_line.worst_sectors(sectors, excess, top=5)
    for row in worst:
        # O lado do ponto de maior excesso: fora do corredor, o sinal do lateral diz o lado (ADR 0003).
        points = np.flatnonzero(sectors.index == row["microsetor"])
        peak = points[int(np.argmax(excess[points]))]
        row["lado_do_maior_excesso"] = (
            None if excess[peak] == 0.0 else ("esquerda" if line.grid_lateral[peak] > 0 else "direita"))
    sectors_with_excess = int(sum(excess[sectors.index == k].max() > 0.0 for k in range(sectors.count)))

    # Etapa 5: comparacao descritiva com as voltas do store v2.
    ai = labelled_ai_laps(store.laps)
    human = ev.driver_laps(store.laps)
    if ai.empty or human.empty:
        raise SystemExit(f"PARADO: {len(ai)} voltas ia rotuladas de {AI_DAY} e {len(human)} humano atual no store v2.")
    ai_ids = ai["lap_id"].tolist()
    human_ids = human["lap_id"].tolist()
    vs_ai, ai_median = f1_line.sector_median_difference(sectors, line.grid_lateral, lateral_matrix(store, ai_ids))
    vs_human, human_median = f1_line.sector_median_difference(
        sectors, line.grid_lateral, lateral_matrix(store, human_ids))
    low, high = track.corridor()

    out_dir.mkdir(parents=True, exist_ok=True)
    grid_frame = pd.DataFrame({
        "grid_index": np.arange(track.size),
        "s": track.s,
        "microsetor": sectors.index,
        "lateral_f1": line.grid_lateral,
        "corredor_dir": low,
        "corredor_esq": high,
        "excesso_m": excess,
        "mediana_ia": ai_median,
        "mediana_humano": human_median,
    })
    grid_frame.to_csv(out_dir / GRID_FILE, index=False, float_format="%.4f")

    corners = detect_corners(track)
    windows = zoom_windows(corners)
    figure = plot_figure(out_dir / FIGURE_FILE, track, line.grid_lateral, ai_median, aligned,
                         windows, verdict["veredito"], similarity.mirrored)

    result = {
        "pedido": "docs/prompts/2026-10-05_22_fontes-e-alinhamento-f1.md",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "entrada": {
            "arquivo": str(reference),
            "sha256": file_entry(Path(reference))["sha256"],
            **identity,
            "amostras": int(len(raw)),
            "campos_lidos": ["x", "y"],
            "nao_lidos": "velocidade, pedais, marcha, rotacao, tempo e distancia do FastF1 (ADR 0018)",
        },
        "geometria": {
            "geometry_id": track.geometry_id,
            "comprimento_m": track.length,
            "pontos_da_grade": track.size,
            "passo_m": track.step,
        },
        "etapa1_unidade": {
            **unit,
            "espacamento_entre_amostras_m": spacing,
        },
        "etapa2_alinhamento": {
            "escala_m_por_unidade": similarity.scale,
            "escala_sobre_a_unidade": similarity.scale / unit["metros_por_unidade"],
            "comprimento_da_linha_alinhada_m": aligned_length,
            "comprimento_oficial_m": track.length,
            "diferenca_pct": 100.0 * (aligned_length / track.length - 1.0),
            "rotacao_graus": similarity.rotation_deg,
            "espelhado": similarity.mirrored,
            "espelho": "y -> -y no sistema do FastF1, antes da rotacao",
            "translacao_m": [float(v) for v in similarity.translation],
            **fit,
            # Descritivo: o comprimento de cada linha medido do mesmo jeito, na grade (`path_length`).
            "comprimentos_na_grade_m": {
                "linha_da_f1": path_length(track, line.grid_lateral),
                "mediana_ia": path_length(track, ai_median),
                "mediana_humano": path_length(track, human_median),
                "linha_central": path_length(track, np.zeros(track.size)),
            },
        },
        "etapa3_grade": {
            "cobertura": line.coverage,
            "passos_para_tras": line.backward_steps,
            "espacamento_em_s_m": f1_line.spacing_summary(np.append(s_steps, closing)),
            "lateral_m": {
                "min": float(line.grid_lateral.min()),
                "max": float(line.grid_lateral.max()),
                "media": float(line.grid_lateral.mean()),
            },
            "interpolacao": "linear em s entre as amostras, fechando o laco (como resample_lap)",
        },
        "etapa4_erro": {
            "corredor": {
                "regra": "ml.track.trajectory.corridor_violation: meia-largura medida + folga de zebra - meia-bitola",
                "meia_bitola_m": config.CAR_HALF_WIDTH_M,
                "folga_de_zebra_m": config.KERB_ALLOWANCE_M,
            },
            "na_grade": summary,
            "nas_amostras": at_samples,
            "microsetores_de_maior_excesso": worst,
            "ordem": "excesso maximo no microsetor; desempate pelo excesso medio",
            "microsetores_com_excesso": sectors_with_excess,
        },
        "criterio": {
            "regra": "aceito se fracao fora <= 10% e p95 do excesso <= 1 m, na grade; fixado antes de rodar",
            **verdict,
        },
        "etapa5_comparacao": {
            "aviso": "descritivo, so para leitura; nada muda coach, store ou criterio",
            "diferenca": "lateral da F1 - mediana das voltas, positivo = F1 mais a esquerda",
            "voltas_ia": ai_ids,
            "voltas_humano": human_ids,
            "f1_menos_ia": f1_line.difference_summary(vs_ai),
            "f1_menos_humano": f1_line.difference_summary(vs_human),
            "lateral_medio_m": {
                "f1": float(line.grid_lateral.mean()),
                "mediana_ia": float(ai_median.mean()),
                "mediana_humano": float(human_median.mean()),
            },
            "por_microsetor": [
                {
                    "microsetor": k,
                    "inicio_m": float(sectors.edges_s[k]),
                    "fim_m": float(sectors.edges_s[k + 1]),
                    "f1_menos_ia_m": float(vs_ai[k]),
                    "f1_menos_humano_m": float(vs_human[k]),
                }
                for k in range(sectors.count)
            ],
        },
        "figura": {
            "arquivo": str(figure),
            "zooms": [{"nome": name, "inicio_s_m": start, "fim_s_m": end} for name, start, end in windows],
        },
        "store_v2": {"commit_do_store": meta.get("commit"), "geometry_id": store.geometry_id},
    }
    result = _round(result)
    (out_dir / SUMMARY_FILE).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def print_report(result: Dict[str, object]) -> None:
    unit, fit = result["etapa1_unidade"], result["etapa2_alinhamento"]
    grid, error, rule = result["etapa3_grade"], result["etapa4_erro"], result["criterio"]
    comparison = result["etapa5_comparacao"]
    print("=" * 72)
    print(f"1. unidade: {unit['unidade']} ({unit['unidades_por_metro_da_pista']:.3f} unidades por metro da pista); "
          f"espacamento {unit['espacamento_entre_amostras_m']}")
    print(f"2. escala {fit['escala_m_por_unidade']} m/unidade ({fit['escala_sobre_a_unidade']} da unidade); "
          f"comprimento {fit['comprimento_da_linha_alinhada_m']} m contra {fit['comprimento_oficial_m']} m "
          f"({fit['diferenca_pct']}%); rotacao {fit['rotacao_graus']} graus; espelho {fit['espelhado']}")
    print(f"   busca inicial {fit['busca_inicial']}; icp {fit['icp']}")
    print(f"3. cobertura {grid['cobertura']}; passos para tras {grid['passos_para_tras']}; "
          f"espacamento em s {grid['espacamento_em_s_m']}")
    print(f"4. na grade {error['na_grade']}")
    print(f"   nas amostras {error['nas_amostras']}")
    for row in error["microsetores_de_maior_excesso"]:
        print(f"   {row['rotulo']}: max {row['excesso_max_m']} m, medio {row['excesso_medio_m']} m, "
              f"fora {row['fracao_fora']}")
    print(f"   criterio: {rule['veredito']} (fracao {rule['fracao_fora']} <= {rule['fracao_fora_max']}: "
          f"{rule['fracao_ok']}; p95 {rule['p95_m']} <= {rule['p95_max_m']}: {rule['p95_ok']})")
    print(f"5. {len(comparison['voltas_ia'])} voltas ia, {len(comparison['voltas_humano'])} humano; "
          f"F1 - IA {comparison['f1_menos_ia']}; F1 - humano {comparison['f1_menos_humano']}")
    print("=" * 72)
    print(f"figura: {result['figura']['arquivo']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--referencia", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "externo")
    args = parser.parse_args(argv)
    try:
        result = run(args.referencia, args.saida)
    except SystemExit as stop:
        print(stop)
        return 2
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
