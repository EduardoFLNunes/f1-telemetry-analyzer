"""Pedido 35, Parte F.4: o que o radio novo diria numa sessao gravada, fora do tempo real, com a voz de verdade.

A sessao passa, amostra a amostra e na ordem do arquivo, pelo mesmo caminho do backend:
o `LiveDrivingCoach` (o modelo atual do repositorio, a referencia volta da IA), a
`VoltaAoVivo` e o `RadioDoEngenheiro`, cada um com o quadro, como no barramento. O relogio
e o do gravador (o coach usa `time`, trocado so neste script). A voz e a do radio
(OneCore Daniel a 1,4x, `core/radio/audio.py`); o tempo de gerar o audio nao conta aqui: o script espera o audio
ficar pronto antes do quadro seguinte. Nada do coach nem do radio muda.

Uso (na pasta backend): python radio_v2_offline.py <pasta da sessao> <saida.json>
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

import core.live.driving_coach as dc  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from core.coleta.estado import tempos_do_store  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.live.volta_ao_vivo import VoltaAoVivo  # noqa: E402
from core.radio.servico import RadioDoEngenheiro  # noqa: E402
from core.telemetry_events import COACHING_EVENT  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

REPO = Path(os.getcwd()).parent
PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SESSAO = PASTA.name


class Relogio:
    agora = 0.0

    def time(self):
        return self.agora

    def monotonic(self):
        return self.agora


relogio = Relogio()
dc.time = relogio

modelo = DriverReferenceModel.load(model_path(REPO, "vhe_interlagos"))
geometria = find_official_geometry([REPO], "vhe_interlagos")
leitor = LeitorDoStore()
ref_id = modelo.reference_lap_id
tempo_ref = tempos_do_store(REPO).get(str(ref_id))
volta_ref = leitor.ler_volta(REPO, str(ref_id))


class Barramento:
    def schedule(self, topic, payload, loop=None):
        if topic == COACHING_EVENT:
            radio.on_coaching_event(payload)


coach = dc.LiveDrivingCoach(Barramento(), model_provider=lambda _t: modelo, geometry_provider=lambda _t: geometria)
volta = VoltaAoVivo(posicao=coach.posicao_oficial,
                    pontos=lambda: len(coach._projector.geometry.x) if coach._projector is not None else None)
radio = RadioDoEngenheiro(
    pasta_de_dados=Path(tempfile.mkdtemp(prefix="radio_v2_")),
    repositorio=lambda: REPO,
    posicao=coach.posicao_oficial,
    ultima_volta=lambda: coach.ultima_volta,
    referencia=lambda: {"tipo": modelo.reference_kind, "volta": ref_id, "tempoS": tempo_ref},
    sessao=lambda: SESSAO,
    relogio=lambda: relogio.agora,
    volta_fechada=volta.ultima_fechada,
    volta_de_referencia=lambda: volta_ref,
)


def esperar_o_audio():
    for m in list(radio._pendentes):
        f = m.get("_futuro")
        if f is not None:
            f.result(timeout=120)


sessao = Session(session_id=SESSAO, directory=PASTA, track="vhe_interlagos")
t0 = None
quadros = 0
for lap in iter_laps(sessao):
    for d in lap.frame.to_dict("records"):
        ts = d.get("timestamp_s")
        if ts is None or ts != ts:
            continue
        t0 = ts if t0 is None else t0
        relogio.agora = float(ts) - t0

        def num(nome):
            v = d.get(nome)
            return float(v) if v is not None and v == v else None

        quadro = {"lap_time": num("lap_time_s"), "lap_number": d.get("lap_number"), "lap": d.get("lap_number"),
                  "world_x": num("x"), "world_z": num("z"), "speedKmh": num("speed_kmh"), "brake": num("brake"),
                  "throttle": num("throttle"), "track": "vhe_interlagos", "driver_id": "player_1",
                  "ai_controlled": d.get("ai_controlled")}
        coach.on_frame(quadro)
        volta.on_frame(quadro)
        radio.on_frame(quadro)
        esperar_o_audio()
        quadros += 1

saida = radio.desde(0)
mensagens = []
for m in saida["mensagens"]:
    mensagens.append({k: m.get(k) for k in ("id", "origem", "voltaDoCarro", "sCarro", "velocidadeKmh", "janela", "titulo",
                                            "texto", "detalhe", "linhas", "fala", "duracaoS", "falaMaxS", "causa",
                                            "piorCurva", "voltasAnalisadas", "curvasDaAnalise", "perdaS", "volta",
                                            "tempoS")})
resultado = {"sessao": SESSAO, "quadros": quadros, "referencia": {"tipo": modelo.reference_kind, "volta": ref_id,
             "tempoS": tempo_ref}, "janelas": radio.estado()["janelas"], "pendentesNoFim": saida["pendentes"],
             "mensagens": mensagens}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
por_tipo = {}
for m in mensagens:
    por_tipo.setdefault(m["origem"], []).append(m["duracaoS"] or 0)
print(SESSAO, quadros, "quadros;", {k: (len(v), round(min(v), 1), round(max(v), 1)) for k, v in por_tipo.items()},
      "pendentes no fim:", saida["pendentes"])
