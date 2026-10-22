"""Pedidos 31 (Parte E.1) e 35 (Parte F.1): o radio do engenheiro.

O texto de cada tipo de mensagem, a janela de radio, o limite do coach, a voz,
as rotas e o registro. Tudo numa pasta temporaria; a voz so roda no Windows.
"""
import json
import sys
import wave
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.radio import audio as audio_do_radio  # noqa: E402
from core.radio.janelas import dentro, janelas_de_radio  # noqa: E402
from core.radio.servico import RadioDoEngenheiro  # noqa: E402
from core.radio.texto import (  # noqa: E402
    CurvaDaPista,
    mensagem_de_diferenca,
    mensagem_de_resumo,
    microssetor_para_o_piloto,
)

L = 4334.08
# Duas curvas de mentira: C01 (esquerda, 200 a 340 m) e C02 (direita, 2000 a 2200 m).
CURVAS = [
    CurvaDaPista("C01", "esquerda", 200.0, 340.0, 3500.0, 1170.0),
    CurvaDaPista("C02", "direita", 2000.0, 2200.0, 1170.0, 3500.0),
]


def _evento(indice=2, perda=0.742, tipo="volta_ia", volta=2):
    return {"type": "coaching_event", "lap_number": volta, "evidence": {
        "microsector": indice, "yourSeconds": 1.991, "referenceSeconds": 1.249, "lossSeconds": perda,
        "referenceKind": tipo, "referenceLabel": "volta da IA" if tipo == "volta_ia" else "sua melhor volta",
        "brakeDeltaM": 38.0, "referenceMinSpeedKmh": 157.0, "yourMinSpeedKmh": 93.5}}


# ------------------------------------------------------------------ texto ---

def test_frase_de_diferenca_com_virgula_microssetor_a_partir_de_1_e_lado_por_extenso():
    m = mensagem_de_diferenca(_evento(indice=2), CURVAS, L)
    assert microssetor_para_o_piloto(2) == 3
    assert m["microssetor"] == 3
    assert m["titulo"] == "C01, esquerda"
    assert m["texto"] == "+0,74 s para a volta da IA no microssetor 3"
    assert m["detalhe"] == "1,99 s contra 1,25 s · a IA freia 38 m depois de você · mínima da IA 157 km/h, a sua 94 km/h"
    # Pedido 35: a causa principal na voz (a freada passou do corte de 15 m: voce freou 38 m antes).
    assert m["fala"] == "Curva 1, esquerda: 0,74 atrás da IA. Freia 38 metros antes."
    assert m["falas"][-2:] == ["Curva 1, esquerda: 0,74 atrás da IA.", "Curva 1: 0,74 atrás."]
    assert m["falaMaxS"] == 6.6                     # cerca de 6 s, com 10% de folga
    assert m["s"] == pytest.approx(3 * L / 60, abs=0.1)  # o fim do microssetor: ali o coach fecha a medida
    assert "." not in m["texto"].split(" s ")[0]  # numero com virgula


def test_frase_contra_a_sua_melhor_e_na_curva_da_direita():
    m = mensagem_de_diferenca(_evento(indice=29, perda=0.215, tipo="minha_melhor"), CURVAS, L)
    assert m["titulo"] == "C02, direita" and m["microssetor"] == 30
    assert m["fala"] == "Curva 2, direita: 0,21 atrás da sua melhor. Freia 38 metros antes."
    assert "na sua melhor volta você freou 38 m depois" in m["detalhe"]


def test_evento_sem_os_numeros_nao_vira_radio():
    assert mensagem_de_diferenca({"type": "coaching_event", "evidence": "texto"}, CURVAS, L) is None


def test_resumo_na_linha():
    m = mensagem_de_resumo(7, 88.132, 84.829, "volta_ia")
    assert m["titulo"] == "Volta 7: 1:28,132"
    assert m["texto"] == "+3,303 s para a volta da IA (1:24,829)"
    assert m["fala"] == "Volta 7, 1 minuto e 28,1. 3,30 atrás da IA."


# ----------------------------------------------------------------- janela ---

def test_janelas_ficam_fora_das_curvas_com_as_margens():
    janelas = janelas_de_radio(CURVAS, L, antes=100.0, depois=20.0, minima=50.0)
    assert janelas == [(361.0, 1900.0), (2221.0, 100.0)]
    assert dentro(janelas, 250.0, L) is None          # na C01
    assert dentro(janelas, 1950.0, L) is None         # na freada da C02
    assert dentro(janelas, 800.0, L) == (361.0, 1900.0)
    assert dentro(janelas, 10.0, L) == (2221.0, 100.0)  # a reta cruza a linha


class _Pista:
    """O que o radio le do coach: a posicao, a ultima volta e a referencia."""

    def __init__(self):
        self.s = 0.0
        self.volta = None
        self.agora = 1000.0


def _radio(tmp_path, pista, falar=None):
    radio = RadioDoEngenheiro(
        pasta_de_dados=tmp_path,
        repositorio=lambda: tmp_path,
        posicao=lambda: {"s": pista.s, "comprimento": L, "lateral": 0.0, "volta": 2},
        ultima_volta=lambda: pista.volta,
        referencia=lambda: {"tipo": "volta_ia", "tempoS": 84.829},
        sessao=lambda: "2026-10-20_10-00-00_vhe_interlagos",
        falar=falar or (lambda texto, destino: (Path(destino).write_bytes(b"RIFF"), 2.0)[1]),
        relogio=lambda: pista.agora,
        volta_fechada=lambda: getattr(pista, "fechada", None),
        volta_de_referencia=lambda: getattr(pista, "referencia", None),
    )
    # A pista de mentira, sem ler a geometria do repositorio.
    radio._chave_da_pista = str(tmp_path)
    radio._curvas, radio._comprimento = CURVAS, L
    radio._janelas = janelas_de_radio(CURVAS, L, antes=100.0, depois=20.0, minima=50.0)
    return radio


def _esperar_o_audio(radio):
    for m in list(radio._pendentes):
        m["_futuro"].result(timeout=5)


QUADRO = {"speedKmh": 250.0}   # 69 m/s: o radio mede quanto resta da janela pela velocidade


def test_mensagem_gerada_dentro_da_curva_espera_a_reta(tmp_path):
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    pista.s = 300.0  # dentro da C01
    radio.on_coaching_event(_evento(indice=3))
    _esperar_o_audio(radio)
    radio.on_frame(QUADRO)
    assert radio.desde(0)["mensagens"] == [] and radio.desde(0)["pendentes"] == 1
    pista.s = 500.0  # a reta
    radio.on_frame(QUADRO)
    entregue = radio.desde(0)["mensagens"]
    assert len(entregue) == 1 and entregue[0]["sCarro"] == 500.0 and entregue[0]["audio"] == "/api/radio/audio/1"


def test_uma_por_vez_e_so_quando_a_fala_inteira_cabe_na_janela(tmp_path):
    """Pedido 35: nada e dito dentro das curvas; a fala tem de caber no que resta da janela."""
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    pista.s = 1850.0   # na janela (361 a 1.900 m), mas so 50 m antes do fim: 0,7 s a 250 km/h
    radio.on_coaching_event(_evento(indice=6))
    radio.on_coaching_event(_evento(indice=7))
    _esperar_o_audio(radio)
    radio.on_frame(QUADRO)
    assert radio.desde(0)["mensagens"] == []                     # a fala de 2 s nao cabe
    pista.s = 500.0
    radio.on_frame(QUADRO)
    assert len(radio.desde(0)["mensagens"]) == 1                 # uma por vez: a segunda espera a primeira
    pista.volta = {"volta": 2, "tempoS": 88.132, "teveIA": False, "momento": 1, "completa": True}
    pista.s, pista.agora = 50.0, pista.agora + 3.0              # a linha: o resumo nasce
    radio.on_frame(QUADRO)
    pista.agora += 1.0
    radio.on_frame(QUADRO)
    _esperar_o_audio(radio)
    radio.on_frame(QUADRO)
    assert len(radio.desde(0)["mensagens"]) == 1                 # s = 50: a janela acaba em 100 m (0,7 s)
    pista.s = 2300.0                                             # a reta dos boxes da volta seguinte: 2.134 m
    radio.on_frame(QUADRO)
    pista.agora += 3.0
    radio.on_frame(QUADRO)
    entregues = radio.desde(0)["mensagens"]
    # O resumo vai para a frente da fila (pedido 35): a frase que sobrou da volta espera ele.
    assert [m["origem"] for m in entregues] == ["coach", "resumo", "coach"]
    assert entregues[1]["janela"] == [2221.0, 100.0] and entregues[1]["velocidadeKmh"] == 250.0


def test_o_radio_nao_cria_frases_o_limite_do_coach_continua(tmp_path):
    from core.live import driving_coach

    assert driving_coach.MAX_PHRASES_PER_LAP == 3
    assert driving_coach.MIN_SECONDS_BETWEEN_EVENTS == 3.0
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    radio.on_coaching_event({"type": "coaching_focus", "focusSectors": [2, 38, 43]})  # o foco fica na tela
    for k in range(3):
        radio.on_coaching_event(_evento(indice=10 + k))
    assert radio.desde(0)["pendentes"] == 3  # uma mensagem por frase do coach, nenhuma a mais


def test_registro_fora_da_pasta_de_gravacoes(tmp_path):
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    pista.s = 500.0
    radio.on_coaching_event(_evento(indice=6))
    _esperar_o_audio(radio)
    radio.on_frame(QUADRO)
    registro = tmp_path / "data" / "radio" / "2026-10-20_10-00-00_vhe_interlagos.jsonl"
    linha = json.loads(registro.read_text(encoding="utf-8").splitlines()[0])
    assert {k: linha[k] for k in ("id", "voltaDoCarro", "sCarro", "microssetor", "curva", "origem")} == {
        "id": 1, "voltaDoCarro": 2, "sCarro": 500.0, "microssetor": 7, "curva": "C01", "origem": "coach"}
    assert linha["texto"].startswith("+0,74 s") and linha["entregueEm"]
    # Nenhum leitor do ML ve isto como sessao: nao ha player.jsonl, e a pasta nao e de gravacoes.
    assert not list((tmp_path / "data" / "radio").rglob("player.jsonl"))
    assert "recordings" not in registro.parts


# ------------------------------------------------------------------- voz ---

@pytest.mark.skipif(sys.platform != "win32", reason="a voz do radio usa as vozes do Windows")
def test_a_voz_gera_um_wav_tocavel(tmp_path):
    vozes = audio_do_radio.vozes_disponiveis()
    if not any(v.startswith("OneCore:Microsoft Daniel") for v in vozes):
        pytest.skip(f"sem a voz Microsoft Daniel (OneCore) neste Windows: {vozes}")
    destino = tmp_path / "msg.wav"
    dur = audio_do_radio.falar("Curva 1, esquerda: 0,74 atrás da IA.", destino)
    with wave.open(str(destino), "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getnframes() / w.getframerate() == pytest.approx(dur)
    assert 2.0 < dur < 7.0  # vinheta + uma frase curta


# ----------------------------------------------------------------- rotas ---

def test_rotas(tmp_path, monkeypatch):
    """As funcoes das rotas, chamadas direto (o TestClient pede o httpx, que nao esta instalado)."""
    import asyncio

    from fastapi import HTTPException

    import main
    from routers import radio as rota

    pista = _Pista()

    def falar(texto, destino):
        with wave.open(str(destino), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 1600)
        return 0.1

    radio = _radio(tmp_path, pista, falar=falar)
    monkeypatch.setattr(main, "radio_do_engenheiro", radio)
    teste = asyncio.run(rota.post_teste())
    assert teste["origem"] == "teste" and teste["id"] == 1 and teste["audio"] == "/api/radio/audio/1"
    lista = asyncio.run(rota.get_mensagens(0, None))
    assert [m["id"] for m in lista["mensagens"]] == [1] and lista["instancia"] == radio.instancia
    assert asyncio.run(rota.get_mensagens(1, radio.instancia))["mensagens"] == []
    outra = asyncio.run(rota.get_mensagens(9, "outra"))
    assert [m["id"] for m in outra["mensagens"]] == [1]  # backend reiniciado: manda tudo de novo
    resposta = asyncio.run(rota.get_audio(1))
    assert resposta.media_type == "audio/wav" and Path(resposta.path).exists()
    with pytest.raises(HTTPException) as falta:
        asyncio.run(rota.get_audio(99))
    assert falta.value.status_code == 404
    assert asyncio.run(rota.get_estado())["janelas"]
    monkeypatch.setattr(main, "radio_do_engenheiro", None)
    with pytest.raises(HTTPException) as fora:
        asyncio.run(rota.get_mensagens(0, None))
    assert fora.value.status_code == 503


# ------------------------------------------------- o barramento (achado) ---

def test_emit_com_assinantes_sincronos_e_assincronos():
    """Pedido 31: o `emit` esperava o `None` dos assinantes sincronos e falhava; os assincronos depois deles nao rodavam."""
    import asyncio

    from core.telemetry_events import TelemetryEventBus

    bus = TelemetryEventBus()
    vistos = []
    bus.subscribe("quadro", lambda q: vistos.append(("sincrono", q)))

    async def assincrono(q):
        vistos.append(("assincrono", q))

    bus.subscribe("quadro", assincrono)
    bus.subscribe("quadro", lambda q: vistos.append(("outro sincrono", q)))
    asyncio.run(bus.emit("quadro", 1))
    # Os tres rodam (o assincrono, quando e esperado, depois dos sincronos).
    assert sorted(vistos) == [("assincrono", 1), ("outro sincrono", 1), ("sincrono", 1)]


# ------------------------------------------- pedido 35: o radio que analisa ---

from core.radio.analise import CORTE_FREADA_M, CORTE_MINIMA_KMH, analisar  # noqa: E402
from core.radio.texto import causa_principal, mensagem_de_analise  # noqa: E402


def test_a_causa_principal_freada_antes_da_minima_e_os_cortes():
    ev = {"brakeDeltaM": 15.0, "referenceMinSpeedKmh": 94.0, "yourMinSpeedKmh": 64.0}
    assert causa_principal(ev, "volta_ia")["fala"] == "Freia 15 metros antes."   # no corte: conta
    ev["brakeDeltaM"] = -14.9                                                     # abaixo: vai para a minima
    assert causa_principal(ev, "volta_ia")["fala"] == "Mínima 64 contra 94."
    ev["yourMinSpeedKmh"] = 94.0 - CORTE_MINIMA_KMH + 0.1                         # abaixo dos dois cortes
    assert causa_principal(ev, "volta_ia") is None
    ev["brakeDeltaM"] = -30.0
    assert causa_principal(ev, "volta_ia")["fala"] == "Freia 30 metros depois."
    assert (CORTE_FREADA_M, CORTE_MINIMA_KMH) == (15.0, 8.0)


def test_resumo_com_a_curva_de_maior_perda():
    m = mensagem_de_resumo(7, 90.363, 84.829, "volta_ia", {"curva": "C11", "lado": "esquerda", "perdaS": 1.14})
    assert m["detalhe"] == "mais perdeu na C11, esquerda: +1,14 s"
    assert m["fala"] == "Volta 7, 1 minuto e 30,4. 5,53 atrás da IA. Mais perdeu na curva 11: 1,1."
    assert m["falas"][-1] == "Volta 7, 1 e 30,4. 5,5 atrás."
    assert m["falaMaxS"] == 7.7 and m["curva"] == "C11"


def _medidas(perdas, freada=-50.0, minima=-30.0, acelerador=12.0, tracado=0.4):
    """As medidas de 3 curvas numa volta (C12, C04 e C01), como `analise.medidas_da_volta`."""
    def curva(codigo, perda):
        return {"curva": codigo, "lado": "esquerda", "perdaS": perda, "freadaM": freada, "minimaKmh": minima,
                "minimaSuaKmh": 80.0, "minimaRefKmh": 110.0, "aceleradorM": acelerador, "tracadoM": tracado,
                "sDaCurva": 3100.0}
    return [curva("C12", perdas[0]), curva("C04", perdas[1]), curva("C01", perdas[2])]


def test_a_analise_so_curvas_perdidas_em_2_de_3_e_no_maximo_2():
    voltas = [{"volta": 6, "medidas": _medidas([0.85, 0.30, 0.9])},
              {"volta": 7, "medidas": _medidas([0.90, -0.10, -0.1])},
              {"volta": 8, "medidas": _medidas([1.02, 0.25, -0.2])}]
    a = analisar(voltas)
    assert [c["curva"] for c in a["curvas"]] == ["C12", "C04"]      # a C01 so foi perdida em 1 das 3
    c12 = a["curvas"][0]
    assert c12["perdas"] == [0.85, 0.9, 1.02] and c12["perdaMedianaS"] == 0.9 and c12["perdidaEm"] == 3
    assert c12["ditas"] == ["minima", "freada"]                     # 30/8 e 50/15: as duas que mais pesam
    assert a["voltas"] == [6, 7, 8]
    m = mensagem_de_analise(a, "volta_ia", "ref#0013")
    assert m["titulo"] == "Análise das voltas 6 a 8"
    assert m["linhas"][0].startswith("C12, esquerda: perde 0,90 s por volta (0,85 · 0,90 · 1,02)")
    assert "mínima 80 contra 110 km/h" in m["linhas"][0] and "freada 50 m antes" in m["linhas"][0]
    assert "traçado 0,4 m mais à esquerda" in m["linhas"][0]        # o lado por extenso (ADR 0003)
    # A fala no estilo da frase do coach: cada diferenca e uma frase ("Minima 80 contra 110.").
    assert m["fala"].startswith("Análise das voltas 6 a 8. Curva 12: 0,9 por volta. Mínima 80 contra 110. "
                                "Freia 50 metros antes.")
    from core.radio.texto import _diferenca_falada
    assert _diferenca_falada("tracado", -7.9, {}) == "Passa 8 metros mais à direita."
    assert _diferenca_falada("tracado", 1.5, {}) == "Passa 1,5 metro mais à esquerda."
    assert _diferenca_falada("acelerador", 14.0, {}) == "Acelera 14 metros depois."
    assert m["falaMaxS"] == 8.8 and m["referencia"] == {"tipo": "volta_ia", "volta": "ref#0013"}
    # Tres curvas perdidas em 2 das 3: so as 2 de maior perda mediana.
    voltas[1]["medidas"][2]["perdaS"] = 0.4
    voltas[2]["medidas"][2]["perdaS"] = 0.5
    assert [c["curva"] for c in analisar(voltas)["curvas"]] == ["C12", "C01"]


def test_a_analise_sai_a_cada_3_voltas_validas_espera_a_janela_e_vai_para_o_registro(tmp_path, monkeypatch):
    pista = _Pista()
    radio = _radio(tmp_path, pista, falar=lambda texto, destino: (
        Path(destino).write_bytes(b"RIFF"), 7.5 if texto.startswith(("Análise", "Voltas")) else 2.0)[1])
    medidas = iter([_medidas([0.85, 0.30, 0.9]), _medidas([0.90, -0.1, -0.1]), _medidas([1.02, 0.25, -0.2])])
    monkeypatch.setattr(radio, "_medidas_da_volta", lambda volta: next(medidas))

    def linha(n, momento, **extra):
        pista.volta = {"volta": n, "tempoS": 90.0, "teveIA": False, "momento": momento, "completa": True, **extra}
        radio.on_frame(QUADRO)
        pista.agora += 1.0
        radio.on_frame(QUADRO)

    pista.s = 50.0                       # perto do fim da janela da linha: nada cabe ainda
    linha(5, 0, teveIA=True)             # volta com a IA: nem resumo, nem conta para a analise
    linha(6, 1)
    linha(7, 2)
    assert [m["origem"] for m in radio._pendentes] == ["resumo", "resumo"]
    linha(8, 3)
    assert [m["origem"] for m in radio._pendentes] == ["resumo", "resumo", "resumo", "analise"]
    _esperar_o_audio(radio)
    pista.s = 500.0                      # a reta oposta: cabem os resumos (2 s), um por vez
    for _ in range(3):
        radio.on_frame(QUADRO)
        pista.agora += 3.0
    pista.s = 1700.0                     # 200 m da janela: 2,9 s, a analise (7,5 s) nao cabe
    radio.on_frame(QUADRO)
    assert [m["origem"] for m in radio.desde(0)["mensagens"]] == ["resumo", "resumo", "resumo"]
    pista.s = 2300.0                     # a reta dos boxes: 2.134 m
    radio.on_frame(QUADRO)
    analise = radio.desde(0)["mensagens"][-1]
    assert analise["origem"] == "analise" and analise["duracaoS"] == 7.5
    registro = tmp_path / "data" / "radio" / "2026-10-20_10-00-00_vhe_interlagos.jsonl"
    linha_registrada = json.loads(registro.read_text(encoding="utf-8").splitlines()[-1])
    assert linha_registrada["voltasAnalisadas"] == [6, 7, 8]
    assert linha_registrada["curvasDaAnalise"][0]["perdas"] == [0.85, 0.9, 1.02]
    assert linha_registrada["curvasDaAnalise"][0]["ditas"] == ["minima", "freada"]
    assert linha_registrada["referencia"]["tipo"] == "volta_ia"
    assert linha_registrada["janela"] == [2221.0, 100.0]


def test_a_voz_fica_com_a_primeira_fala_que_cabe(tmp_path):
    pista = _Pista()
    ditas = []

    def falar(texto, destino):
        ditas.append(texto)
        Path(destino).write_bytes(b"RIFF")
        return 0.12 * len(texto)          # 0,12 s por letra

    radio = _radio(tmp_path, pista, falar=falar)
    radio.on_coaching_event(_evento(indice=2))
    _esperar_o_audio(radio)
    m = radio._pendentes[0]
    assert 0.12 * len(m["falas"][0]) > 6.0               # a completa, com a causa, passa de 6 s
    assert m["fala"] == m["falas"][1] == "Curva 1: 0,74 atrás. Freia 38 metros antes."
    assert m["duracaoS"] <= 6.0 and ditas == m["falas"][:2]


def test_volta_ao_vivo_manda_so_os_pontos_novos_e_guarda_a_volta_fechada():
    from core.live.volta_ao_vivo import VoltaAoVivo

    pos = {"s": 0.0}
    v = VoltaAoVivo(lambda: {"s": pos["s"], "comprimento": 100.0, "lateral": 0.5, "volta": 3,
                             "tempoDaVolta": pos["s"] / 50, "desdeALinha": True}, lambda: 50)
    quadro = {"speedKmh": 180.0, "throttle": 1.0, "brake": 0.0}
    for s in (1.0, 3.0, 5.0):
        pos["s"] = s
        v.on_frame(quadro)
    inteira = v.novos(None, None)
    assert inteira["completa"] is True and inteira["seq"] == 3 and inteira["carro"]["s"] == 5.0
    for s in (7.0, 9.0):
        pos["s"] = s
        v.on_frame(quadro)
    novos = v.novos(inteira["versao"], inteira["seq"])
    assert novos["completa"] is False and novos["pontos"]["indices"] == [3, 4] and novos["seq"] == 5
    assert novos["pontos"]["velocidade"] == [180.0, 180.0] and "linhas" not in novos
    # A volta nova (s volta ao comeco) manda a volta inteira de novo e guarda a que fechou.
    pos["s"] = 99.0
    v.on_frame(quadro)
    pos["s"] = 1.0
    v.on_frame(quadro)
    assert v.novos(inteira["versao"], novos["seq"])["completa"] is True
    fechada = v.ultima_fechada()
    assert fechada["volta"] == 3 and fechada["linhas"]["elapsed"][4] == pytest.approx(9.0 / 50)


def test_o_minimapa_monta_a_pista_a_referencia_e_o_relogio_da_linha_do_jogo():
    import numpy as np

    from core.radio import minimapa

    sys.path.insert(0, str(BACKEND / "tests"))
    from test_lap_origin import circular_track

    track = circular_track()
    n = track.size
    referencia = {"disponivel": True, "lapId": "ref#0013", "tempoS": float(track.length / 50.0),
                  "elapsedS": (np.asarray(track.s) / 50.0).tolist(), "lateralM": [1.0] * n}
    analise = {"voltas": [6, 7, 8], "curvas": [{"curva": "C99", "perdaMedianaS": 0.9}]}
    m = minimapa.montar(track, [], referencia, "volta_ia", analise, 1.495)
    # Sem o cache da pista: as duas bordas da geometria oficial, como dois contornos.
    assert m["disponivel"] and m["pista"]["origem"].startswith("geometria oficial")
    esquerda, direita = m["pista"]["contornos"]
    assert len(esquerda) == len(direita) > 100 and len(esquerda) <= minimapa.PONTOS_DA_BORDA
    assert len(m["linhaDoS0"]) == 2
    ref = m["referencia"]
    assert ref["lapId"] == "ref#0013" and len(ref["pontos"]) <= minimapa.PONTOS_DA_REFERENCIA
    assert ref["tempoNaLinhaDoJogoS"] == pytest.approx(1.495 / 50.0, abs=1e-3)   # 50 m/s na referencia
    x0, z0, t0, pedal0 = ref["pontos"][0]
    # centro + normal x lateral (`TrackGeometry.to_world`); na pista circular de teste a normal aponta para fora
    assert t0 == 0.0 and np.hypot(x0, z0) == pytest.approx(200.0 + 1.0, abs=0.05)
    assert pedal0 == 0                                     # sem os pedais na volta: parcial
    assert m["curvasDaAnalise"] == [] and m["versao"] == "volta_ia|ref#0013|6-7-8"   # a C99 nao existe na pista

    # O pedal de cada ponto, como na tela Volta: freio a partir de 0,15, acelerador cheio a partir de 0,9.
    freio = [0.0] * n
    acelerador = [0.5] * n
    freio[0], acelerador[1], acelerador[2], freio[2] = 0.2, 0.95, 0.95, 0.3
    com_pedais = dict(referencia, freio=freio, acelerador=acelerador)
    pontos = minimapa.montar(track, [], com_pedais, "volta_ia", None, 1.495)["referencia"]["pontos"]
    assert len(pontos) == n and [q[3] for q in pontos[:4]] == [2, 1, 2, 0]

    # O nome da curva fica do lado de fora: numa curva a esquerda, do lado direito (-normal), largura + 9 m.
    class _Curva:
        label, apex_s = "C03-esq", float(track.s[10])

    class _Trecho:
        corner = _Curva()

    rotulo = minimapa.rotulos_das_curvas(track, [_Trecho()])[0]
    w = float(np.asarray(track.width_right)[10]) + minimapa.FOLGA_DO_ROTULO_M
    assert rotulo["curva"] == "C03" and rotulo["lado"] == "esquerda"
    assert rotulo["x"] == pytest.approx(float(track.x[10] - w * track.normal[10, 0]), abs=0.01)
    assert rotulo["z"] == pytest.approx(float(track.z[10] - w * track.normal[10, 1]), abs=0.01)


def test_as_mensagens_dizem_a_versao_do_minimapa(tmp_path):
    """Pedido 35, Parte E: o app do jogo baixa o minimapa de novo quando a referencia ou a analise mudam."""
    pista = _Pista()
    escolha = {"tipo": "volta_ia", "volta": "ref#0013", "tempoS": 84.829}
    radio = _radio(tmp_path, pista)
    radio._referencia = lambda: dict(escolha)
    assert radio.desde(0)["minimapaVersao"] == "volta_ia|ref#0013|"
    radio._ultima_analise = {"voltas": [6, 7, 8], "curvas": []}
    assert radio.desde(0)["minimapaVersao"] == "volta_ia|ref#0013|6-7-8"
    escolha.update(tipo="minha_melhor", volta="ref#0021")
    assert radio.desde(0)["minimapaVersao"] == "minha_melhor|ref#0021|6-7-8"
    radio._referencia = lambda: (_ for _ in ()).throw(RuntimeError("sem o coach"))
    assert radio.desde(0)["minimapaVersao"] == "None|None|6-7-8"


def test_as_rotas_novas_pontos_novos_e_minimapa(tmp_path, monkeypatch):
    """Pedido 35, Parte F.1: /api/live/volta/novos e /api/radio/minimapa, chamadas direto (como `test_rotas`)."""
    import asyncio

    import numpy as np

    import main
    from core.live.volta_ao_vivo import VoltaAoVivo
    from core.radio.analise import Pista
    from routers import radio as rota

    sys.path.insert(0, str(BACKEND / "tests"))
    from test_lap_origin import circular_track

    # Sem a volta ao vivo e sem a geometria: respostas que dizem por que.
    monkeypatch.setattr(main, "volta_ao_vivo", None)
    assert asyncio.run(rota.get_volta_novos(None, None))["disponivel"] is False
    radio = _radio(tmp_path, _Pista())
    monkeypatch.setattr(main, "radio_do_engenheiro", radio)
    monkeypatch.setattr(radio, "_pista", lambda: None)
    radio._geometria = None
    assert json.loads(asyncio.run(rota.get_minimapa()).body)["disponivel"] is False

    # Os pontos novos: a volta inteira na primeira leitura, depois so o que chegou.
    pos = {"s": 0.0}
    v = VoltaAoVivo(lambda: {"s": pos["s"], "comprimento": 100.0, "lateral": 0.0, "volta": 2,
                             "tempoDaVolta": pos["s"] / 50, "desdeALinha": True}, lambda: 50)
    monkeypatch.setattr(main, "volta_ao_vivo", v)
    for s in (1.0, 3.0):
        pos["s"] = s
        v.on_frame({"speedKmh": 180.0, "throttle": 1.0, "brake": 0.0})
    inteira = json.loads(asyncio.run(rota.get_volta_novos(None, None)).body)
    pos["s"] = 5.0
    v.on_frame({"speedKmh": 180.0, "throttle": 1.0, "brake": 0.0})
    novos = json.loads(asyncio.run(rota.get_volta_novos(inteira["versao"], inteira["seq"])).body)
    assert inteira["completa"] is True and novos["completa"] is False and novos["pontos"]["indices"] == [2]

    # O minimapa: a pista, a referencia escolhida com o tempo e a versao.
    track = circular_track()
    radio._geometria = Pista(track=track, segmentos=[])
    volta = {"disponivel": True, "lapId": "ref#0013", "tempoS": float(track.length / 50.0),
             "elapsedS": (np.asarray(track.s) / 50.0).tolist(), "lateralM": [0.0] * track.size}
    escolha = lambda: {"tipo": "volta_ia", "volta": "ref#0013"}   # noqa: E731
    monkeypatch.setattr(main, "_referencia_do_radio", escolha)
    radio._referencia = escolha                    # no backend, o radio recebe a mesma funcao (main.py)
    monkeypatch.setattr(main, "_volta_de_referencia_do_radio", lambda: volta)
    monkeypatch.setattr(main.app_config, "coach_root", lambda: tmp_path)   # sem o meta do store: 1,463 m
    m = json.loads(asyncio.run(rota.get_minimapa()).body)
    assert m["disponivel"] and m["linhaDoJogoM"] == 1.463 and m["referencia"]["lapId"] == "ref#0013"
    assert m["referencia"]["tempoNaLinhaDoJogoS"] == pytest.approx(1.463 / 50.0, abs=1e-3)
    assert m["versao"] == "volta_ia|ref#0013|" == radio.desde(0)["minimapaVersao"]


def test_o_minimapa_usa_o_contorno_do_asfalto_tratado_do_cache(tmp_path):
    """Fechamento do pedido 35: o contorno vem do asfalto tratado do cache (asphaltSurface.loops),
    simplificado; os lacos pequenos ficam de fora; as camadas do cache estao em (x, -z)."""
    import numpy as np

    from core.radio import minimapa
    from core.radio.janelas import CACHE_DA_PISTA

    sys.path.insert(0, str(BACKEND / "tests"))
    from test_lap_origin import circular_track

    assert minimapa.contorno_do_asfalto(tmp_path) is None            # sem o cache
    a = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    fora = np.column_stack([300 * np.cos(a), 300 * np.sin(a) + 50])  # (x, -z): um circulo de 300 m
    miolo = np.column_stack([280 * np.cos(a), 280 * np.sin(a) + 50])
    ilha = [[0, 0], [10, 0], [10, 10], [0, 10]]                      # 100 m2: fica de fora
    cache = tmp_path / "data" / "cache" / "tracks" / CACHE_DA_PISTA
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({"asphaltSurface": {"loops": [{"points": fora.tolist()}, {"points": miolo.tolist()},
                                                              {"points": ilha}]}}), encoding="utf-8")
    contornos = minimapa.contorno_do_asfalto(tmp_path)
    assert len(contornos) == 2                                        # a ilha de 100 m2 saiu
    assert 30 < len(contornos[0]) < 400                               # simplificado (2 m de tolerancia)
    p = np.array(contornos[0])
    # (x, -z) do cache -> (x, z): o centro do circulo vai de y = +50 para z = -50
    assert np.hypot(p[:, 0], p[:, 1] + 50).max() == pytest.approx(300, abs=0.5)
    m = minimapa.montar(circular_track(), [], None, None, None, 1.495, contornos)
    assert m["pista"] == {"origem": "asfalto tratado do cache", "contornos": contornos}
