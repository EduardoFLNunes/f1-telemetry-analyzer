"""Pedido 51, Parte D.1 (a partir do script do pedido 43): o que o radio diria numa sessao gravada, fora
do tempo real, com a voz de verdade, em tres rodadas.

* `antes`: o texto de `develop` (`TEXTO_ANTIGO`, o `texto.py` de antes do pedido 51) e a referencia
  `volta_ia` (a `#0013`), do modelo do repositorio, como o app estava;
* `palavras`: o texto novo e a mesma `#0013`. Com o texto novo, a referencia que nao e a "sua melhor"
  diz "da referência". So as palavras mudam contra o `antes`: e aqui que se conta a causa perdida;
* `depois`: o texto novo e a volta do modelo (ADR 0032), lida do arquivo derivado, como o app novo.

A sessao passa, amostra a amostra, pelo `LiveDrivingCoach`, a `VoltaAoVivo` e o `RadioDoEngenheiro`;
o relogio e o do gravador; o script espera cada audio ficar pronto. Os limites (7,3, 8,0 e 8,8 s) e
a ordem do corte sao os do codigo. A melhor do store e a das sessoes anteriores, no mesmo carro.

Uso (na pasta backend): python <este arquivo> <pasta da sessao> <modo> <saida.json>
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.getcwd())

if os.environ.get("TEXTO_ANTIGO"):
    import importlib.util
    import core.radio  # noqa: F401
    _spec = importlib.util.spec_from_file_location("core.radio.texto", os.environ["TEXTO_ANTIGO"])
    _mod = importlib.util.module_from_spec(_spec)
    _mod.__package__ = "core.radio"
    sys.modules["core.radio.texto"] = _mod
    _spec.loader.exec_module(_mod)

import core.live.driving_coach as dc  # noqa: E402
from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from core.coleta.estado import tempos_do_store  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.live.volta_ao_vivo import VoltaAoVivo  # noqa: E402
from core.radio.servico import RadioDoEngenheiro  # noqa: E402
from core.telemetry_events import COACHING_EVENT  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

REPO = Path(os.getcwd()).parent
PASTA, MODO, SAIDA = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
SESSAO = PASTA.name
assert MODO in ("antes", "palavras", "depois"), MODO


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
if MODO == "depois":
    dados = VM.encontrar([REPO], "vhe_interlagos")
    VM.anexar(modelo, dados)
    assert modelo.use_reference("volta_do_modelo")
    ref_id = modelo.reference_lap_id
    tempo_ref = dados["tempo_s"]
    volta_ref = VM.como_volta_do_store(dados)
else:
    assert modelo.use_reference("volta_ia"), "o modelo do repositorio nao tem mais a volta_ia"
    ref_id = modelo.reference_lap_id
    tempo_ref = tempos_do_store(REPO).get(str(ref_id))
    volta_ref = leitor.ler_volta(REPO, str(ref_id))

meta_sessao = json.loads((PASTA / "metadata.json").read_text(encoding="utf-8"))
carro = (meta_sessao.get("metadata") or {}).get("carModel") or "rss_formula_rss_3_v6_2026"
store_meta = json.loads((REPO / "data" / "ml" / "laps_grid_v2_meta.json").read_text(encoding="utf-8"))
anteriores = [float(v["lap_time_s"]) for v in store_meta.get("laps") or []
              if str(v.get("session_id", "")) < SESSAO and v.get("origem") == "humano"
              and v.get("carModel") in (carro, None) and v.get("lap_time_s") is not None]
MELHOR_ANTES = min(anteriores) if anteriores else None


class Barramento:
    def schedule(self, topic, payload, loop=None):
        if topic == COACHING_EVENT:
            radio.on_coaching_event(payload)


coach = dc.LiveDrivingCoach(Barramento(), model_provider=lambda _t: modelo, geometry_provider=lambda _t: geometria)
volta = VoltaAoVivo(posicao=coach.posicao_oficial,
                    pontos=lambda: len(coach._projector.geometry.x) if coach._projector is not None else None)
radio = RadioDoEngenheiro(
    pasta_de_dados=Path(tempfile.mkdtemp(prefix="radio_51_")),
    repositorio=lambda: REPO,
    posicao=coach.posicao_oficial,
    ultima_volta=lambda: coach.ultima_volta,
    referencia=lambda: {"tipo": modelo.reference_kind, "volta": ref_id, "tempoS": tempo_ref},
    sessao=lambda: SESSAO,
    relogio=lambda: relogio.agora,
    volta_fechada=volta.ultima_fechada,
    volta_de_referencia=lambda: volta_ref,
    volta_atual=volta.estado,
    melhor_do_store=lambda: MELHOR_ANTES,
    volta_parcial=volta.ultima_parcial,
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
                  "isAIControlled": d.get("ai_controlled")}
        coach.on_frame(quadro)
        volta.on_frame(quadro)
        radio.on_frame(quadro)
        esperar_o_audio()
        quadros += 1

saida = radio.desde(0)
mensagens = [{k: m.get(k) for k in ("id", "origem", "voltaDoCarro", "titulo", "texto", "detalhe", "fala", "duracaoS",
                                    "falaMaxS", "causa", "piorCurva", "perdaS", "volta", "tempoS")}
             for m in saida["mensagens"]]
replays = {str(m["id"]): radio.replay(m["id"]) for m in saida["mensagens"] if m.get("replay")}
rotulos = sorted({str((r or {}).get("rotuloDaReferencia")) for r in replays.values() if r})
resultado = {"sessao": SESSAO, "modo": MODO, "quadros": quadros,
             "referencia": {"tipo": modelo.reference_kind, "volta": ref_id, "tempoS": tempo_ref},
             "melhorDoStoreAntes": MELHOR_ANTES, "pendentesNoFim": saida["pendentes"],
             "rotulosDoReplay": rotulos, "mensagens": mensagens}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
por = {}
for m in mensagens:
    por.setdefault(m["origem"], []).append(m["duracaoS"] or 0)
print(SESSAO, MODO, quadros, "quadros;", {k: (len(v), round(min(v), 2), round(max(v), 2)) for k, v in por.items()},
      "pendentes:", saida["pendentes"], flush=True)
