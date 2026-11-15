"""Pedido 45, B.1: por que a volta sai incompleta, e o que mudaria com a proposta. So le: nada do coach muda.

Passa cada sessao pelo `LiveDrivingCoach` duas vezes: com a regra de hoje e com a proposta (a regra "boxes" so vale
nos trechos em que existe pit lane, os microssetores 54 a 59 e 0 a 10, medidos nas gravacoes: a lateral passa de 10 m
nas saidas e entradas dos boxes e em nenhum outro lugar de uma volta limpa). Em cada volta que fecha: o tempo, os
microssetores sem medida e o motivo.

Uso (na pasta backend): python incompletas.py <saida.json> <pasta da sessao>...
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

import core.live.driving_coach as dc  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

REPO = Path(os.environ.get("REPO_REAL") or Path(os.getcwd()).parent)
modelo = DriverReferenceModel.load(model_path(REPO, "vhe_interlagos"))
geo = find_official_geometry([REPO], "vhe_interlagos")
PIT_LANE = set(range(54, 60)) | set(range(0, 11))


class Bus:
    def schedule(self, *a, **k):
        pass


def passar(pasta, proposta):
    coach = dc.LiveDrivingCoach(Bus(), model_provider=lambda _: modelo, geometry_provider=lambda _: geo)
    motivos = {}
    original = coach._close_sector

    def fechar(frame, model, finished, entry, crossing):
        fora_do_pit = finished is not None and finished not in PIT_LANE
        if finished is not None and entry is not None and finished != coach._partial_sector:
            parado = coach._closing_min_speed is not None and coach._closing_min_speed < dc.STOPPED_KMH
            boxes = (coach._closing_max_lateral is not None and coach._closing_max_lateral > dc.PIT_LATERAL_M
                     and coach._closing_min_speed is not None and coach._closing_min_speed < dc.PIT_SPEED_KMH)
            if parado:
                motivos[finished] = {"motivo": "parado", "kmh": round(coach._closing_min_speed, 1)}
            elif boxes:
                motivos[finished] = {"motivo": "boxes", "lateralM": round(coach._closing_max_lateral, 1),
                                     "kmh": round(coach._closing_min_speed, 1), "noPitLane": finished in PIT_LANE}
            if proposta and boxes and not parado and fora_do_pit:
                coach._closing_max_lateral = None
        original(frame, model, finished, entry, crossing)

    coach._close_sector = fechar
    ses = Session(session_id=pasta.name, directory=pasta, track="vhe_interlagos")
    ult = None
    voltas = []
    for lap in iter_laps(ses):
        for d in lap.frame.to_dict("records"):
            def num(n):
                v = d.get(n)
                return float(v) if v is not None and v == v else None
            coach.on_frame({"lap_time": num("lap_time_s"), "lap_number": d.get("lap_number"), "lap": d.get("lap_number"),
                            "world_x": num("x"), "world_z": num("z"), "speedKmh": num("speed_kmh"), "brake": num("brake"),
                            "throttle": num("throttle"), "track": "vhe_interlagos", "driver_id": "player_1",
                            "isAIControlled": d.get("ai_controlled")})
            u = coach.ultima_volta
            if u and u is not ult:
                ult = u
                sem = u["semMedida"]
                voltas.append({"volta": int(u["volta"]), "tempoS": round(u["tempoS"], 3), "completa": u["completa"], "ia": u["teveIA"],
                               "semMedida": sem, "motivos": {str(k): motivos[k] for k in sem if k in motivos},
                               "semMotivo": [k for k in sem if k not in motivos]})
                motivos.clear()
    return voltas


saida = {}
for pasta in map(Path, sys.argv[2:]):
    hoje, proposta = passar(pasta, False), passar(pasta, True)
    saida[pasta.name] = {"hoje": hoje, "proposta": proposta}
    numeros = [v["volta"] for v in hoje]
    print(pasta.name, "voltas", len(hoje), "completas hoje", sum(v["completa"] for v in hoje),
          "com a proposta", sum(v["completa"] for v in proposta), "numeros repetidos", len(numeros) - len(set(numeros)))
    for a, b in zip(hoje, proposta):
        if not a["completa"]:
            print("  V", a["volta"], a["tempoS"], "fica", "completa" if b["completa"] else "incompleta",
                  json.dumps(a["motivos"], ensure_ascii=True)[:150], "sem motivo", a["semMotivo"][:6])
Path(sys.argv[1]).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
