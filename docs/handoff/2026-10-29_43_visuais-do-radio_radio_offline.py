"""Pedido 43 (a partir do script do pedido 35, Parte F.4, e do 36, Parte C.3): o que o radio novo diria numa sessao gravada, fora do tempo real, com a voz de verdade.

A sessao passa, amostra a amostra e na ordem do arquivo, pelo mesmo caminho do backend:
o `LiveDrivingCoach` (o modelo atual do repositorio, a referencia volta da IA), a
`VoltaAoVivo` e o `RadioDoEngenheiro`, cada um com o quadro, como no barramento. O relogio
e o do gravador (o coach usa `time`, trocado so neste script). A voz e a do radio
(OneCore Daniel a 1,4x, `core/radio/audio.py`); o tempo de gerar o audio nao conta aqui: o script espera o audio
ficar pronto antes do quadro seguinte. Nada do coach nem do radio muda.

Uso (na pasta backend): python radio_offline.py <pasta da sessao> <saida.json>

Pedido 43: guarda tambem, por mensagem do coach, o `evidence` da frase (os numeros e os pontos que o
coach mediu), o tamanho em bytes da resposta da rota do replay e o tempo para monta-la.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

# Pedido 36, Parte C.3: com TEXTO_ANTIGO=<arquivo>, o radio usa esse texto.py (o de antes das
# unidades) no lugar do atual; o resto do radio e o mesmo. Assim, so o texto muda entre as rodadas.
if os.environ.get("TEXTO_ANTIGO"):
    import importlib.util
    import core.radio  # noqa: F401  (o pacote, antes do modulo trocado)
    _spec = importlib.util.spec_from_file_location("core.radio.texto", os.environ["TEXTO_ANTIGO"])
    _mod = importlib.util.module_from_spec(_spec)
    _mod.__package__ = "core.radio"
    sys.modules["core.radio.texto"] = _mod
    _spec.loader.exec_module(_mod)

import core.live.driving_coach as dc  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from core.coleta.estado import tempos_do_store  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.live.volta_ao_vivo import VoltaAoVivo  # noqa: E402
from core.radio.servico import RadioDoEngenheiro  # noqa: E402
from core.telemetry_events import COACHING_EVENT  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

import time as _time  # noqa: E402

# Pedido 43: o tempo para montar o replay (a analise e a frase), no proprio radio.
TEMPOS = []


def _cronometrar(nome, f):
    def g(self, *a, **k):
        t0 = _time.perf_counter()
        r = f(self, *a, **k)
        TEMPOS.append({"tipo": nome, "ms": round((_time.perf_counter() - t0) * 1000, 2), "curvas": len(r or [])})
        return r
    return g


RadioDoEngenheiro._replay_da_analise = _cronometrar("analise", RadioDoEngenheiro._replay_da_analise)
RadioDoEngenheiro._replay_da_frase = _cronometrar("frase", RadioDoEngenheiro._replay_da_frase)

# Pedido 43: onde o coach recomecou a contar fora da linha (a volta nao fecha para o radio).
INICIOS_FORA_DA_LINHA = []
_start_lap = dc.LiveDrivingCoach._start_lap


def _start_lap_com_registro(self, lap_number, index, clock, progress, at_line=False):
    if not at_line:
        INICIOS_FORA_DA_LINHA.append({"volta": lap_number, "microssetor": index + 1})
    return _start_lap(self, lap_number, index, clock, progress, at_line=at_line)


dc.LiveDrivingCoach._start_lap = _start_lap_com_registro

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


EVIDENCIAS = []   # pedido 43: o evidence de cada frase do coach, na ordem


class Barramento:
    def schedule(self, topic, payload, loop=None):
        if topic == COACHING_EVENT:
            if payload.get("type") == "coaching_event":
                EVIDENCIAS.append({"volta": payload.get("lap_number"), **(payload.get("evidence") or {})})
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
    volta_atual=volta.estado,
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
                  "isAIControlled": d.get("ai_controlled")}  # a chave que o coach le (channels.ai_controlled)
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
                                            "tempoS", "restaS", "replay")})
resultado = {"sessao": SESSAO, "quadros": quadros, "referencia": {"tipo": modelo.reference_kind, "volta": ref_id,
             "tempoS": tempo_ref}, "janelas": radio.estado()["janelas"], "pendentesNoFim": saida["pendentes"],
             "mensagens": mensagens,
             # pedido 36: os dados do replay de cada mensagem que tem
             "replays": {str(m["id"]): radio.replay(m["id"]) for m in saida["mensagens"] if m.get("replay")},
             "evidencias": EVIDENCIAS,
             "temposDoReplay": TEMPOS,
             "iniciosForaDaLinha": INICIOS_FORA_DA_LINHA,
             "grade": radio.grade_da_sessao() if hasattr(radio, "grade_da_sessao") else None,
             # pedido 43: o tamanho da resposta da rota (o JSON como o FastAPI devolve, sem espacos)
             "bytesDaRota": {str(m["id"]): len(json.dumps(radio.replay(m["id"]), ensure_ascii=False,
                                                           separators=(",", ":")).encode("utf-8"))
                             for m in saida["mensagens"] if m.get("replay")}}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
por_tipo = {}
for m in mensagens:
    por_tipo.setdefault(m["origem"], []).append(m["duracaoS"] or 0)
print(SESSAO, quadros, "quadros;", {k: (len(v), round(min(v), 1), round(max(v), 1)) for k, v in por_tipo.items()},
      "pendentes no fim:", saida["pendentes"])
