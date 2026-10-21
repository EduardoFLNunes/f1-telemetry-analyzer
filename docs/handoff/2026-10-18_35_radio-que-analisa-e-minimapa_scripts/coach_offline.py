"""Pedido 35, Parte A.2: a sessao de 18/10 pelo coach, fora do tempo real, com o motivo de cada silencio.

Como a Parte E.2 do pedido 31: a sessao passa, volta a volta, por um `LiveDrivingCoach`
(um so, como ao vivo), com o relogio da parede trocado pelo cronometro do jogo SO neste
script. O modelo e o que estava ativo no teste (o backup gravado antes da rodada das
17:32). Um invólucro em volta de `_close_sector` anota, para cada microssetor fechado,
por que ele nao virou frase -- lendo o mesmo estado que o coach le, na mesma ordem
das condicoes do codigo. Nada do coach muda.

Uso (na pasta backend): python coach_offline.py <sessao> <pasta das gravacoes> <modelo.json> <saida.json>
"""
import json
import os
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, os.getcwd())

import core.live.driving_coach as dc  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel  # noqa: E402
from core.telemetry_events import COACHING_EVENT  # noqa: E402

REPO = Path(os.getcwd()).parent
SESSAO, GRAVACOES, MODELO, SAIDA = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])


class Relogio:
    agora = 0.0

    def time(self):
        return self.agora

    def monotonic(self):
        return self.agora


relogio = Relogio()
dc.time = relogio

modelo = DriverReferenceModel.load(MODELO)
geometria = find_official_geometry([REPO], "vhe_interlagos")
eventos = []


class Barramento:
    def schedule(self, topic, payload, loop=None):
        if topic == COACHING_EVENT:
            eventos.append(payload)


coach = dc.LiveDrivingCoach(Barramento(), model_provider=lambda _t: modelo, geometry_provider=lambda _t: geometria)
fechados = []
original = coach._close_sector


def anotado(frame, model, finished, entry, crossing):
    antes = len([e for e in eventos if e.get("type") == "coaching_event"])
    motivo = None
    info = {"volta": coach._volta_do_jogo, "microssetor": finished, "foco": list(coach._focus or ())}
    if entry is None or finished is None:
        motivo = "sem entrada"
    elif finished == coach._partial_sector:
        motivo = "microssetor em que a contagem comecou"
    else:
        stopped = coach._closing_min_speed is not None and coach._closing_min_speed < dc.STOPPED_KMH
        in_pits = (coach._closing_max_lateral is not None and coach._closing_max_lateral > dc.PIT_LATERAL_M
                   and coach._closing_min_speed is not None and coach._closing_min_speed < dc.PIT_SPEED_KMH)
        split = crossing - entry
        target = model.target_at((finished + 0.5) / model.microsectors)
        if stopped or in_pits:
            motivo = "parado ou no box"
        elif split <= 0 or target is None or getattr(target, "reference_seconds", None) is None:
            motivo = "sem medida"
        else:
            loss = split - float(target.reference_seconds)
            limiar = coach._threshold_for(target)
            info.update({"perdaS": round(loss, 3), "limiarS": round(limiar, 3)})
            if loss <= 0:
                motivo = "ganhou da referencia"
            elif loss < limiar:
                motivo = "abaixo do limiar"
            elif finished not in (coach._focus or ()):
                motivo = "acima do limiar, fora do foco"
            elif finished in coach._spoken_sectors:
                motivo = "ja falado nesta volta"
            elif coach._lap_phrases >= dc.MAX_PHRASES_PER_LAP:
                motivo = "limite de 3 frases"
            elif relogio.agora - coach._last_event_at < coach.min_gap_seconds:
                motivo = "menos de 3 s da frase anterior"
            else:
                motivo = "frase"
    original(frame, model, finished, entry, crossing)
    depois = len([e for e in eventos if e.get("type") == "coaching_event"])
    info["motivo"] = motivo if (depois == antes) == (motivo != "frase") else f"{motivo} (divergiu do coach)"
    fechados.append(info)


coach._close_sector = anotado


from ml.data.recordings import Session, iter_laps  # noqa: E402

# Amostra a amostra, na ordem do arquivo, como chegaram ao vivo (o indice da sessao
# parou no meio da gravacao, entao a leitura e direta do player.jsonl).
sessao = Session(session_id=SESSAO + "_vhe_interlagos", directory=GRAVACOES / (SESSAO + "_vhe_interlagos"),
                 track="vhe_interlagos")
voltas_lidas = []
t0 = None
for lap in iter_laps(sessao):
    voltas_lidas.append(int(lap.lap_number))
    f = lap.frame
    for d in f.to_dict("records"):
        ts = d.get("timestamp_s")
        if ts is None or ts != ts:
            continue
        t0 = ts if t0 is None else t0
        relogio.agora = float(ts) - t0

        def num(nome):
            v = d.get(nome)
            return float(v) if v is not None and v == v else None

        coach.on_frame({
            "lap_time": num("lap_time_s"), "lap_number": d.get("lap_number"), "lap": d.get("lap_number"),
            "world_x": num("x"), "world_z": num("z"), "speedKmh": num("speed_kmh"), "brake": num("brake"),
            "track": "vhe_interlagos", "driver_id": "player_1", "ai_controlled": d.get("ai_controlled"),
        })


class _V:
    def __init__(self, n):
        self.lap_number = n


voltas = [_V(n) for n in voltas_lidas]

frases = [e for e in eventos if e.get("type") == "coaching_event"]
focos = [e for e in eventos if e.get("type") == dc.FOCUS_EVENT]
resumo = {}
for f in fechados:
    resumo.setdefault(f["volta"], {}).setdefault(f["motivo"], 0)
    resumo[f["volta"]][f["motivo"]] += 1
saida = {
    "sessao": SESSAO, "modelo": str(MODELO), "referencia": modelo.reference_kind,
    "voltas_lidas": [v.lap_number for v in voltas],
    "frases": [{"volta": e.get("lap_number"), "microssetor_indice": e["evidence"].get("microsector"),
                "perdaS": e["evidence"].get("lossSeconds"), "evidence": e["evidence"], "texto": e.get("event")}
               for e in frases],
    "focos": [{"volta": e.get("lap_number"), "setores": e.get("focusSectors"), "fonte": e.get("focusSource")} for e in focos],
    "motivos_por_volta": resumo,
    "foco_e_acima_do_limiar": [f for f in fechados if f["motivo"] not in ("abaixo do limiar", "ganhou da referencia")],
    "microssetores_fechados": fechados,
}
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("frases:", [(f["volta"], f["microssetor_indice"], f["perdaS"]) for f in saida["frases"]])
print("focos:", saida["focos"])
for volta, m in sorted(resumo.items(), key=lambda x: (x[0] is None, x[0])):
    print(volta, m)
