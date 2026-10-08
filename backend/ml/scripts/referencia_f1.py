"""Traçado de referência único da F1 na época 2023–25 (pedido 24, Parte C; ADR 0019).

    python -m ml.scripts.referencia_f1 [--faixa data/ml/externo/f1_faixa] [--saida data/ml/externo/f1_referencia]

Lê as saídas do `faixa_f1_secas` (pedido 23): o manifesto, com o veredito de
cada volta, e as grades das voltas aceitas. Não usa o FastF1 nem a rede. Escolhe
as voltas da época 2023–25, confere a coerência de cada sessão contra as outras,
forma a referência e a compara, só para leitura, com a IA e o piloto.

Nada é treinado, e nada muda coach, store ou critério. Nada da F1 além da
posição entra (ADR 0018).

Escreve, fora do git, em `data/ml/externo/f1_referencia/`:

* `referencia_2023_25.csv` -- `s`, microssetor, lateral, número de voltas e de
  sessões, amplitude entre as medianas das sessões e a marca de pouco confiável;
* `resumo.json` -- commit, geometria, sessões e voltas usadas, coerência por
  sessão e a comparação com a IA e o piloto;
* `referencia_lateral.png` -- lateral × s, com a referência, a IA e o piloto.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.comparison import evolution as ev  # noqa: E402
from ml.data.store_v2 import git_commit, load_store_v2, store_v2_meta  # noqa: E402
from ml.external import f1_band, f1_reference  # noqa: E402
from ml.scripts.alinhar_fastf1 import OFFICIAL_GEOMETRY_ID, _round, labelled_ai_laps, lateral_matrix  # noqa: E402
from ml.scripts.faixa_f1_secas import COLOURS, MANIFEST_FILE, SUMMARY_FILE, _abs_summary, _sector_rows  # noqa: E402
from ml.track.geometry import TrackGeometry, load_geometry  # noqa: E402
from ml.track.microsectors import Microsectors, build_microsectors  # noqa: E402

PEDIDO = "docs/prompts/2026-10-08_24_f1-referencia-2023-25.md"
DEFAULT_BAND_DIR = config.artifacts_root() / "externo" / "f1_faixa"
DEFAULT_OUT = config.artifacts_root() / "externo" / "f1_referencia"
REFERENCE_FILE = "referencia_2023_25.csv"
OUT_SUMMARY = "resumo.json"
FIGURE_FILE = "referencia_lateral.png"


def load_lap_lateral(band_dir: Path, key: str, track: TrackGeometry) -> np.ndarray:
    """A grade de uma volta aceita do pedido 23, conferida contra a geometria carregada."""
    frame = pd.read_csv(band_dir / "voltas" / f"{key}.csv")
    if len(frame) != track.size or not np.allclose(frame["s"].to_numpy(dtype=float), track.s, atol=1e-3):
        raise SystemExit(f"PARADO: a grade de {key} nao bate com a geometria {track.geometry_id}.")
    return frame["lateral"].to_numpy(dtype=float)


def plot_reference(path: Path, track: TrackGeometry, sectors: Microsectors, reference: np.ndarray,
                   ai: np.ndarray, human: np.ndarray, unreliable: np.ndarray, laps: int, sessions: int) -> Path:
    rows = 4
    figure, axes = plt.subplots(rows, 1, figsize=(16, 15))
    edges = np.linspace(0.0, track.length, rows + 1)
    low, high = track.corridor()
    for ax, start, end in zip(axes, edges[:-1], edges[1:]):
        mask = (track.s >= start) & (track.s <= end)
        s = track.s[mask]
        for k in np.flatnonzero(unreliable):
            a, b = sectors.edges_s[k], sectors.edges_s[k + 1]
            if b > start and a < end:
                ax.axvspan(max(a, start), min(b, end), color="#bbbbbb", alpha=0.35, linewidth=0, zorder=0)
        ax.plot(s, low[mask], color="#8a8a93", linewidth=0.7, linestyle="--", zorder=1)
        ax.plot(s, high[mask], color="#8a8a93", linewidth=0.7, linestyle="--", zorder=1)
        ax.plot(s, ai[mask], color=COLOURS["ia"], linewidth=1.1, zorder=3)
        ax.plot(s, human[mask], color=COLOURS["humano"], linewidth=1.1, zorder=3)
        ax.plot(s, reference[mask], color=COLOURS["f1"], linewidth=1.6, zorder=4)
        for edge in sectors.edges_s:
            if start <= edge <= end:
                ax.axvline(edge, color="#dddddd", linewidth=0.5, zorder=0)
        ax.set_xlim(start, end)
        ax.set_ylabel("lateral (m), + à esquerda")
    axes[-1].set_xlabel("s (m)")
    handles = [
        plt.Line2D([], [], color=COLOURS["f1"], linewidth=1.6, label="referência da F1, época 2023–25"),
        plt.Line2D([], [], color=COLOURS["ia"], linewidth=1.2, label="mediana das voltas ia de 04/10"),
        plt.Line2D([], [], color=COLOURS["humano"], linewidth=1.2, label="mediana das voltas humano (atual)"),
        plt.Line2D([], [], color="#8a8a93", linewidth=0.8, linestyle="--", label="corredor (ml/track)"),
        plt.Rectangle((0, 0), 1, 1, color="#bbbbbb", alpha=0.35, label="pouco confiável (V1 do pedido 23)"),
    ]
    figure.legend(handles=handles, loc="lower center", ncol=5, fontsize=9, frameon=False)
    figure.suptitle(f"Traçado de referência da F1, época 2023–25 (pedido 24; ADR 0019): {laps} voltas de "
                    f"{sessions} sessões", fontsize=11)
    figure.tight_layout(rect=(0, 0.04, 1, 0.97))
    figure.savefig(path, dpi=110)
    plt.close(figure)
    return path


def compare_with_p23(sectors: Microsectors, new: Dict[str, object], p23: Dict[str, object],
                     column: str, summary_key: str) -> Dict[str, object]:
    """A tabela nova contra a "F1 - IA" ou "F1 - piloto" do pedido 23 (mediana da faixa)."""
    old = np.array([row[column] for row in p23["comparacao"]["por_microsetor_diferenca"]], dtype=float)
    delta = np.abs(np.asarray(new["por_microsetor"], dtype=float) - old)
    return {
        "pedido_23": p23["comparacao"][summary_key],
        "diferenca_por_microsetor_m": {**_abs_summary(delta), "microsetor_do_max": sectors.label(int(np.argmax(delta)))},
    }


def run(band_dir: Path, out_dir: Path) -> Dict[str, object]:
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

    manifest = json.loads((band_dir / MANIFEST_FILE).read_text(encoding="utf-8"))
    p23 = json.loads((band_dir / SUMMARY_FILE).read_text(encoding="utf-8"))

    # Itens 1 e 2: voltas da época e coerência por sessão.
    candidates = f1_reference.era_laps(manifest["voltas"])
    if not candidates:
        raise SystemExit("PARADO: nenhuma volta seca aceita de 2023 a 2025 no manifesto do pedido 23.")
    keys = [record["chave"] for record in candidates]
    sessions = [f1_reference.session_key(record) for record in candidates]
    laterals = np.vstack([load_lap_lateral(band_dir, key, track) for key in keys])
    verdicts = f1_reference.coherence(laterals, sessions)
    accepted_sessions = [key for key, verdict in verdicts.items() if verdict["entra"]]
    use = np.array([session in accepted_sessions for session in sessions])
    if not use.any():
        raise SystemExit("PARADO: nenhuma sessao da epoca passou na coerencia.")
    used_keys = [key for key, keep in zip(keys, use) if keep]
    used_sessions = [session for session, keep in zip(sessions, use) if keep]
    used = laterals[use]

    # Item 3: a referência.
    reference = f1_reference.reference_line(used)
    amplitude = f1_reference.session_amplitude(used, used_sessions)
    unreliable_labels = p23["incerteza"]["microsetores_pouco_confiaveis"]
    unreliable = f1_reference.unreliable_flags(unreliable_labels, sectors.count)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "s": track.s,
        "microsetor": sectors.index,
        "lateral": reference,
        "n_voltas": np.full(track.size, len(used_keys)),
        "n_sessoes": np.full(track.size, len(accepted_sessions)),
        "amplitude_entre_sessoes_m": amplitude,
        "pouco_confiavel": unreliable[sectors.index],
    }).to_csv(out_dir / REFERENCE_FILE, index=False, float_format="%.4f")

    # Item 4: comparação, só para leitura.
    ai = labelled_ai_laps(store.laps)
    human = ev.driver_laps(store.laps)
    ai_ids, human_ids = ai["lap_id"].tolist(), human["lap_id"].tolist()
    if ai_ids != p23["comparacao"]["voltas_ia"] or human_ids != p23["comparacao"]["voltas_humano"]:
        raise SystemExit("PARADO: as voltas ia ou humano do store v2 nao sao as mesmas do pedido 23.")
    ai_laps, human_laps = lateral_matrix(store, ai_ids), lateral_matrix(store, human_ids)
    vs_ai = f1_band.difference_table(sectors, reference, ai_laps)
    vs_human = f1_band.difference_table(sectors, reference, human_laps)
    band_p50 = pd.read_csv(band_dir / "faixa.csv")["p50"].to_numpy(dtype=float)

    figure = plot_reference(out_dir / FIGURE_FILE, track, sectors, reference, vs_ai["linha_mediana"],
                            vs_human["linha_mediana"], unreliable, len(used_keys), len(accepted_sessions))

    result = {
        "pedido": PEDIDO,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "adr": "docs/decisoes/0019-f1-tracado-de-referencia-2023-25.md",
        "geometria": {"geometry_id": track.geometry_id, "comprimento_m": track.length,
                      "pontos_da_grade": track.size, "passo_m": track.step},
        "entrada": {
            "faixa_do_pedido_23": str(band_dir),
            "commit_da_faixa": p23.get("commit"),
            "campos_da_f1": "so o lateral na grade, vindo de X e Y da posicao (ADR 0018)",
        },
        "epoca": {"anos": list(f1_reference.ERA_YEARS),
                  "fora": "2019 e 2021-22 (outras epocas), 2018 (sem voltas) e a volta de chuva (ADR 0019)"},
        "coerencia": {
            "regra": "|mediana da sessao - mediana das voltas das outras sessoes da epoca|, por ponto: "
                     "mediana <= 0,10 m e p90 <= 0,30 m; uma passada, fixada antes de rodar",
            "por_sessao": verdicts,
            "sessoes_que_entram": accepted_sessions,
            "sessoes_fora": [key for key in verdicts if key not in accepted_sessions],
        },
        "referencia": {
            "voltas": len(used_keys),
            "sessoes": len(accepted_sessions),
            "voltas_usadas": used_keys,
            "voltas_por_sessao": {key: int(sum(1 for s in used_sessions if s == key)) for key in accepted_sessions},
            "lateral_m": {"min": float(reference.min()), "max": float(reference.max()),
                          "media": float(reference.mean())},
            "amplitude_entre_sessoes_m": {**_abs_summary(amplitude), "p50_por_ponto": float(np.median(amplitude))},
            "microsetores_pouco_confiaveis": unreliable_labels,
            "ate_a_mediana_da_faixa_do_pedido_23_m": _abs_summary(reference - band_p50),
            "por_microsetor": _sector_rows(
                sectors,
                lateral_m=f1_band.sector_median(sectors, reference),
                amplitude_entre_sessoes_m=f1_band.sector_median(sectors, amplitude)),
        },
        "comparacao": {
            "aviso": "descritivo, so para leitura; nada muda coach, store ou criterio",
            "diferenca": "referencia - mediana das voltas, por ponto, reduzida por microssetor pela mediana; "
                         "positivo = F1 mais a esquerda",
            "voltas_ia": ai_ids,
            "voltas_humano": human_ids,
            "referencia_menos_ia": vs_ai["resumo"],
            "referencia_menos_humano": vs_human["resumo"],
            "contra_o_pedido_23": {
                "ia": compare_with_p23(sectors, vs_ai, p23, "f1_menos_ia_m", "mediana_f1_menos_ia"),
                "humano": compare_with_p23(sectors, vs_human, p23, "f1_menos_humano_m", "mediana_f1_menos_humano"),
            },
            "por_microsetor": _sector_rows(sectors, referencia_menos_ia_m=vs_ai["por_microsetor"],
                                           referencia_menos_humano_m=vs_human["por_microsetor"]),
        },
        "figura": str(figure),
    }
    result = _round(result)
    (out_dir / OUT_SUMMARY).write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    return result


def print_report(result: Dict[str, object]) -> None:
    print("=" * 72)
    for key, verdict in result["coerencia"]["por_sessao"].items():
        print(f"{key}: {verdict}")
    ref = result["referencia"]
    print(f"referencia: {ref['voltas']} voltas de {ref['sessoes']} sessoes; amplitude {ref['amplitude_entre_sessoes_m']}")
    print(f"ate a mediana da faixa 23: {ref['ate_a_mediana_da_faixa_do_pedido_23_m']}")
    comparison = result["comparacao"]
    print(f"ref - IA {comparison['referencia_menos_ia']}; ref - humano {comparison['referencia_menos_humano']}")
    print(f"contra o 23: {comparison['contra_o_pedido_23']}")
    print("=" * 72)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--faixa", type=Path, default=DEFAULT_BAND_DIR)
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        result = run(args.faixa, args.saida)
    except SystemExit as stop:
        print(stop)
        return 2
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
