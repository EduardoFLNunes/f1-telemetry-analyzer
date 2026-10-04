"""Ensaio do coach da fase de aprendizado (pedidos 14 e 15, ADR 0016).

    python tools/ensaio_coach.py --modelo M.json --geometria-arquivo G.json --saida ensaio.json
        [--sessao-prefixo 2026-10-04] [--voltas lap_id ...] [--volta-destaque lap_id]

O coach roda amostra por amostra, na ordem gravada, sobre os arquivos da sessao
rotulada, nos dois modos de referencia. Um coach so atravessa todos os arquivos
do dia, como o app aberto, para o foco (pedido 15) acompanhar a sessao. Cada
frase fica ligada a volta do `ml` em que foi dita, pelo relogio da amostra
anterior a fala: a frase do ultimo trecho e o resumo saem na amostra que ja
cruzou a linha. Contam as voltas `humano` do inventario rotulado (ou as dadas
em `--voltas`). O intervalo minimo entre falas e zerado, como no replay: o de
3 s usa o relogio da maquina e, numa reproducao rapida, calaria quase tudo.

Cada modo roda duas vezes: "antes", com o foco aberto a todos os microsetores
(o coach do pedido 14: as 3 primeiras frases que passam do limiar), e "agora",
com os 3 trechos de foco.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.assisted_analysis.official_geometry import OfficialGeometry  # noqa: E402
from core.assisted_analysis.reference_model import REFERENCE_KINDS, DriverReferenceModel  # noqa: E402
from core.live.driving_coach import FOCUS_EVENT, LiveDrivingCoach  # noqa: E402
from core.telemetry_events import COACHING_EVENT, ENGINEER_SPEECH  # noqa: E402
from ml import config  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402


class Bus:
    def __init__(self):
        self.items: List[tuple] = []

    def schedule(self, topic, payload, loop_ref=None):
        self.items.append((topic, payload))


def lap_finder(laps: pd.DataFrame):
    starts = laps["inicio_epoch_s"].to_numpy(dtype=float)
    ends = laps["fim_epoch_s"].to_numpy(dtype=float)
    ids = laps["lap_id"].to_numpy()

    def find(stamp_s: float) -> Optional[str]:
        hit = np.flatnonzero((starts <= stamp_s) & (stamp_s <= ends))
        return str(ids[hit[0]]) if hit.size else None

    return find


def summary_sectors(text: str) -> List[int]:
    """Os microsetores do resumo de fim de volta ("... setor 32 (0.67s), setor 38 ...")."""
    return [int(k) for k in re.findall(r"setor (\d+) \(", text or "")]


def where_they_fall(phrases: List[Dict[str, object]], lap_ids) -> Dict[str, object]:
    """Quantas frases de trecho caem nos 3 maiores da propria volta (os do resumo) e onde na volta."""
    lap_ids = set(lap_ids)
    top = {p["volta"]: set(summary_sectors(p["texto"])) for p in phrases
           if p["tipo"] == "fim de volta" and p["volta"] in lap_ids}
    said = [p for p in phrases if p["tipo"] == "trecho" and p["volta"] in lap_ids]
    judged = [p for p in said if p["volta"] in top]
    hits = [p for p in judged if p["microsetor"] in top[p["volta"]]]
    sectors = np.array([p["microsetor"] for p in said], dtype=float)
    return {
        "frases_de_trecho": len(said),
        "frases_em_voltas_com_resumo": len(judged),
        "nos_3_maiores_da_volta": len(hits),
        "fracao_nos_3_maiores": round(len(hits) / len(judged), 3) if judged else None,
        "microsetor_mediano": float(np.median(sectors)) if sectors.size else None,
        "nos_microsetores_0_a_5": int((sectors <= 5).sum()),
    }


def run(model: DriverReferenceModel, kind: str, geometry, sessions, laps: pd.DataFrame, *,
        open_focus: bool = False) -> Dict[str, object]:
    model.use_reference(kind)
    find = lap_finder(laps)
    wanted = set(laps["lap_id"])
    phrases: List[Dict[str, object]] = []
    focus_lines: List[Dict[str, object]] = []
    bus = Bus()
    coach = LiveDrivingCoach(bus, lambda _t: model, geometry_provider=lambda _t: geometry, min_gap_seconds=0.0)
    if open_focus:
        # O coach do pedido 14: qualquer microsetor pode falar, as 3 primeiras frases da volta.
        coach.focus_sectors = lambda m: (tuple(range(m.microsectors)), "todos")
    for session in sessions:
        previous_stamp = None
        with (session.directory / "player.jsonl").open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sample = dict(payload.get("sample", payload))
                sample.setdefault("track", payload.get("track"))
                stamp = payload.get("timestamp") or sample.get("timestamp")
                before = len(bus.items)
                coach.on_frame(sample)
                for topic, item in bus.items[before:]:
                    at = previous_stamp if previous_stamp is not None else stamp
                    lap_id = find(float(at) / 1000.0) if at is not None else None
                    if topic == COACHING_EVENT and item.get("type") == FOCUS_EVENT:
                        if not open_focus:
                            focus_lines.append({"sessao": session.session_id, "fim_da_volta": lap_id,
                                                "foco": item.get("focusSectors"), "fonte": item.get("focusSource"),
                                                "texto": item.get("event")})
                        continue
                    if lap_id not in wanted:
                        continue
                    phrases.append({
                        "volta": lap_id,
                        "tipo": "trecho" if topic == COACHING_EVENT else "fim de volta",
                        "microsetor": (item.get("evidence") or {}).get("microsector") if topic == COACHING_EVENT else None,
                        "foco": list(coach._focus or ()) if topic == COACHING_EVENT and not open_focus else None,
                        "texto": item.get("event") if topic == COACHING_EVENT else item.get("message"),
                    })
                if stamp is not None:
                    previous_stamp = stamp
    per_lap = Counter(p["volta"] for p in phrases if p["tipo"] == "trecho")
    counts = np.array([per_lap.get(lap_id, 0) for lap_id in sorted(wanted)])
    sectors = Counter(p["microsetor"] for p in phrases if p["tipo"] == "trecho")
    valid_ids = sorted(laps.loc[laps["valid"].astype(bool), "lap_id"])
    valid_counts = np.array([per_lap.get(lap_id, 0) for lap_id in valid_ids])
    valid_sectors = Counter(p["microsetor"] for p in phrases if p["tipo"] == "trecho" and p["volta"] in set(valid_ids))
    return {
        "voltas_validas": {
            "voltas": len(valid_ids),
            "frases_por_volta": {"media": float(valid_counts.mean()) if valid_counts.size else 0.0,
                                 "mediana": float(np.median(valid_counts)) if valid_counts.size else 0.0,
                                 "max": int(valid_counts.max()) if valid_counts.size else 0},
            "microsetores_mais_citados": [{"microsetor": int(k), "frases": int(v)} for k, v in valid_sectors.most_common(10)],
        },
        "referencia": kind,
        "volta_de_referencia": model.reference_lap_id,
        "tempo_da_referencia_s": model.reference_lap_seconds,
        "voltas": len(wanted),
        "frases_de_trecho": int(sum(per_lap.values())),
        "frases_de_fim_de_volta": sum(1 for p in phrases if p["tipo"] == "fim de volta"),
        "frases_por_volta": {"media": float(counts.mean()) if counts.size else 0.0,
                             "mediana": float(np.median(counts)) if counts.size else 0.0,
                             "max": int(counts.max()) if counts.size else 0},
        "microsetores_mais_citados": [{"microsetor": int(k), "frases": int(v)} for k, v in sectors.most_common(10)],
        "onde_caem": {"todas": where_they_fall(phrases, wanted), "validas": where_they_fall(phrases, valid_ids)},
        "mudancas_de_foco": focus_lines,
        "frases": phrases,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--modelo", type=Path, required=True)
    parser.add_argument("--geometria-arquivo", type=Path, required=True)
    parser.add_argument("--saida", type=Path, required=True)
    parser.add_argument("--sessao-prefixo", default="2026-10-04")
    parser.add_argument("--voltas", nargs="*", default=None, help="lap_id do ml (padrao: as voltas humano da sessao)")
    parser.add_argument("--volta-destaque", default="2026-10-04_03-21-52_vhe_interlagos#0002",
                        help="volta mostrada em detalhe (padrao: a de 91,74 s)")
    args = parser.parse_args(argv)

    geometry = OfficialGeometry.load(args.geometria_arquivo)
    model = DriverReferenceModel.load(args.modelo)
    if geometry is None or model is None:
        print("PARADO: geometria ou modelo ilegivel")
        return 2
    inventory = pd.read_parquet(config.artifacts_root() / "origem" / "lap_inventory.parquet")
    laps = inventory[inventory["session_id"].str.startswith(args.sessao_prefixo)]
    laps = laps[laps["lap_id"].isin(args.voltas)] if args.voltas else laps[laps["origem"] == "humano"]
    sessions = sorted((s for s in list_all_sessions() if s.session_id.startswith(args.sessao_prefixo)),
                      key=lambda s: s.session_id)
    result = {"modelo": str(args.modelo), "sessoes": [s.session_id for s in sessions],
              "volta_destaque": args.volta_destaque, "modos": {}}
    for kind in REFERENCE_KINDS:
        if kind not in model.references:
            continue
        result["modos"][kind] = {}
        for label, open_focus in (("antes", True), ("agora", False)):
            out = run(model, kind, geometry, sessions, laps, open_focus=open_focus)
            result["modos"][kind][label] = out
            spotlight = [p for p in out["frases"] if p["volta"] == args.volta_destaque]
            out["destaque"] = {
                "trechos": [p["microsetor"] for p in spotlight if p["tipo"] == "trecho"],
                "foco": next((p["foco"] for p in spotlight if p["tipo"] == "trecho"), None),
                "resumo": [summary_sectors(p["texto"]) for p in spotlight if p["tipo"] == "fim de volta"],
                "frases": [p["texto"] for p in spotlight],
            }
            print(f"{kind} {label}: {out['voltas']} voltas, {out['frases_de_trecho']} frases de trecho "
                  f"({out['frases_por_volta']}), {out['frases_de_fim_de_volta']} de fim de volta; "
                  f"mais citados {out['microsetores_mais_citados'][:5]}")
            print(f"   so voltas validas: {out['voltas_validas']}")
            print(f"   onde caem: {out['onde_caem']}")
            print(f"   {args.volta_destaque}: {out['destaque']}")
            if not open_focus:
                changes = [(f["fim_da_volta"], f["foco"], f["fonte"]) for f in out["mudancas_de_foco"]]
                print(f"   mudancas de foco: {changes}")
    texts = [p["texto"] for m in result["modos"].values() for run_ in m.values() for p in run_["frases"]]
    result["frases_proibidas"] = [t for t in texts if any(w in t.lower() for w in ("ganh", "ideal", "otimo"))]
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"frases proibidas: {len(result['frases_proibidas'])}\n-> {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
