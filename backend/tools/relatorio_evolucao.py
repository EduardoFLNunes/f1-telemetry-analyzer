"""Relatorio da evolucao do piloto, todas as sessoes (pedido 16, peca B).

    python tools/relatorio_evolucao.py [--saida data/ml/evolucao] [--modelo ARQUIVO]

Le o store v2 (recusa um store cujas checagens nao passaram), pega a volta da
IA do coach (`volta_ia` do modelo do repositorio) como referencia e escreve,
fora do git:

* `sessao_<AAAA-MM-DD>.json` -- uma sessao (as gravacoes do mesmo dia): as
  voltas, o resumo, as 14 curvas e os 60 microsetores;
* `resumo.json` -- a serie das sessoes, a tendencia, as 3 curvas de maior
  perda e o criterio de estabilizacao do ADR 0015;
* `painel.html` -- o painel da evolucao (pedido 17), o modelo
  `painel_evolucao.html` com os dados no lugar do marcador `/*DADOS*/`.

O formato dos campos esta em `docs/store_v2_e_evolucao.md`. As regras foram
registradas antes da primeira rodada, no mesmo documento.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pandas as pd  # noqa: E402

from core.assisted_analysis.official_geometry import OfficialGeometry, find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import REFERENCE_AI, DriverReferenceModel, model_path  # noqa: E402
from ml import config  # noqa: E402
from ml.comparison import evolution as ev  # noqa: E402
from ml.data.store_v2 import STORE_V2_FILENAME, file_entry, load_store_v2, store_v2_meta  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

TRACK = "vhe_interlagos"
TRACK_NAME = "Interlagos"
PANEL_TEMPLATE = Path(__file__).resolve().parent / "painel_evolucao.html"
PANEL_FILENAME = "painel.html"
PANEL_MARKER = "/*DADOS*/"
# `<` dentro de uma string JSON, escrito como escape unicode.
LESS_THAN_ESCAPE = chr(92) + "u003c"


def panel_data(summary: Dict[str, object], reports, geometry: OfficialGeometry, cars) -> Dict[str, object]:
    """O que o painel le: o resumo, as sessoes pela data, a pista e o carro."""
    return {
        "resumo": summary,
        "sessoes": {report["sessao"]: report for report in reports},
        "pista": {
            "x": [round(float(v), 2) for v in geometry.x],
            "z": [round(float(v), 2) for v in geometry.z],
            "ds": float(geometry.length) / int(geometry.x.size),
            "L": float(geometry.length),
        },
        "carro": ", ".join(sorted({str(c) for c in cars if c})) or None,
        "pista_nome": TRACK_NAME,
    }


def render_panel(template: str, data: Dict[str, object]) -> str:
    """Troca o marcador pelo JSON, com `<` escapado: nenhum texto dos dados fecha o `<script>`."""
    if template.count(PANEL_MARKER) != 1:
        raise SystemExit(f"PARADO: o modelo do painel deve ter o marcador {PANEL_MARKER} uma vez so.")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", LESS_THAN_ESCAPE)
    return template.replace(PANEL_MARKER, payload)


def run(out_dir: Path, model_file: Path, store_root: Optional[Path] = None) -> Dict[str, object]:
    """Roda o relatorio; levanta SystemExit("PARADO: ...") nas travas."""
    meta = store_v2_meta(store_root)
    if not meta:
        raise SystemExit("PARADO: store v2 nao encontrado. Rode: python -m ml.scripts.build_lap_store_v2")
    if not meta.get("aprovado"):
        raise SystemExit("PARADO: as checagens do store v2 nao passaram (aprovado: false no meta).")
    track = load_geometry()
    store = load_store_v2(store_root, track=track)
    model = DriverReferenceModel.load(model_file)
    reference = (model.references or {}).get(REFERENCE_AI) if model is not None else None
    if not reference:
        raise SystemExit(f"PARADO: o modelo {model_file} nao tem a referencia {REFERENCE_AI}.")
    ref_id = reference["lap_id"]
    if ref_id not in set(store.lap_ids):
        raise SystemExit(f"PARADO: a volta da IA do coach ({ref_id}) nao esta no store v2.")
    ref_grid = store.lap(ref_id)
    ref_total = float(store.laps.set_index("lap_id").at[ref_id, "lap_time_s"])

    corners = detect_corners(track)
    segments = ev.corner_segments(track, corners)
    sectors = build_microsectors(track)
    laps = ev.driver_laps(store.laps)
    laps = laps.assign(sessao=laps["session_id"].map(ev.session_of))

    out_dir.mkdir(parents=True, exist_ok=True)
    store_file = (Path(store_root) if store_root else config.artifacts_root()) / STORE_V2_FILENAME
    common = {
        "store": {"arquivo": str(store_file), "sha256": file_entry(store_file)["sha256"],
                  "commit_do_store": meta.get("commit"), "geometry_id": store.geometry_id},
        "referencia": {"tipo": REFERENCE_AI, "volta": ref_id, "tempo_s": round(ref_total, 3),
                       "modelo": str(model_file)},
        "regras": "docs/store_v2_e_evolucao.md, secao 1.4",
    }
    reports = []
    written = []
    for session, rows in sorted(laps.groupby("sessao")):
        grids = {lap_id: store.lap(lap_id) for lap_id in rows["lap_id"]}
        report = {**ev.session_report(session, rows, grids, ref_grid, ref_total, track, segments, sectors), **common}
        path = out_dir / f"sessao_{session}.json"
        path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
        reports.append(report)
        written.append(str(path))
    summary = {**ev.summary_report(reports), **common, "arquivos_de_sessao": written}
    (out_dir / "resumo.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")

    geometry = find_official_geometry([BACKEND_DIR.parent], TRACK)
    if geometry is None:
        raise SystemExit("PARADO: geometria oficial exportada nao encontrada; o painel nao foi gerado.")
    if geometry.geometry_id != store.geometry_id:
        raise SystemExit(f"PARADO: a geometria exportada ({geometry.geometry_id}) nao e a do store v2 "
                         f"({store.geometry_id}); o painel nao foi gerado.")
    cars = laps["carModel"].dropna().unique() if "carModel" in laps else []
    panel = out_dir / PANEL_FILENAME
    panel.write_text(render_panel(PANEL_TEMPLATE.read_text(encoding="utf-8"),
                                  panel_data(summary, reports, geometry, cars)), encoding="utf-8")
    return {"resumo": summary, "sessoes": reports, "saida": str(out_dir), "painel": str(panel)}


def print_report(result: Dict[str, object]) -> None:
    summary = result["resumo"]
    print("=" * 70)
    print(f"EVOLUCAO  (referencia: volta da IA {summary['referencia']['volta']}, {summary['referencia']['tempo_s']} s)")
    for session in summary["sessoes"]:
        print(f"  {session['sessao']}: {session['voltas']} voltas, melhor {session['melhor_s']} s, mediana "
              f"{session['mediana_s']} s (desvio {session['desvio_s']}), mediana - IA {session['mediana_menos_ia_s']} s"
              f"{'  [poucos dados]' if session['poucos_dados'] else ''}")
    for report in result["sessoes"]:
        print(f"\n  curvas em {report['sessao']} (perda mediana para a IA, intervalo de 90%):")
        for c in report["curvas"]:
            loss = c["perda_para_ia_s"] or {}
            braking = c["frenagem_vs_ia_m"]
            brake_text = "-" if braking is None else "%+.0f m" % braking["mediana"]
            side = " (%s)" % c["lado"] if c["lado"] else ""
            print(f"    {c['curva']:8s} {loss.get('mediana', float('nan')):+.3f} s  {c['intervalo_90_s']}  "
                  f"{c['situacao']}{side}  freio {brake_text}  "
                  f"apice {c['lateral_apice_vs_ia_m']['mediana']:+.2f} m  "
                  f"minima {c['velocidade_minima_vs_ia_kmh']['mediana']:+.1f} km/h")
    print(f"\n  tendencia da mediana: {summary['tendencia_mediana_s_por_sessao']} s por sessao")
    print(f"  3 curvas de maior perda: {[c['curva'] for c in summary['curvas_de_maior_perda']]}")
    print(f"  criterio do ADR 0015: {summary['criterio_adr_0015']['situacao']}")
    print("=" * 70)
    print(f"-> {result['saida']}")
    print(f"painel: {result['painel']}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "evolucao")
    parser.add_argument("--modelo", type=Path, default=model_path(BACKEND_DIR.parent, TRACK),
                        help="modelo do coach com a volta da IA (padrao: o do repositorio)")
    args = parser.parse_args(argv)
    try:
        result = run(args.saida, args.modelo)
    except SystemExit as stop:
        print(stop)
        return 2
    print_report(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
