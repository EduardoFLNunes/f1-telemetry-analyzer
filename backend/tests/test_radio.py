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
    # Pedido 36: com a unidade (abaixo de 1 s, em decimos).
    assert m["fala"] == "Curva 1, esquerda: 7 décimos atrás da IA. Freia 38 metros antes da IA."
    assert m["falas"][-3:] == ["Curva 1, esquerda: 7 décimos atrás da IA.", "Curva 1: 7 décimos atrás da IA.",
                               "Curva 1: 7 décimos atrás."]
    assert m["falaMaxS"] == 7.3                     # cerca de 6 s, com folga para a causa (pedido 36)
    assert m["s"] == pytest.approx(3 * L / 60, abs=0.1)  # o fim do microssetor: ali o coach fecha a medida
    assert "." not in m["texto"].split(" s ")[0]  # numero com virgula


def test_frase_contra_a_sua_melhor_e_na_curva_da_direita():
    m = mensagem_de_diferenca(_evento(indice=29, perda=0.215, tipo="minha_melhor"), CURVAS, L)
    assert m["titulo"] == "C02, direita" and m["microssetor"] == 30
    assert m["fala"] == "Curva 2, direita: 2 décimos atrás da sua melhor. Freia 38 metros antes da sua melhor."
    assert "na sua melhor volta você freou 38 m depois" in m["detalhe"]


def test_evento_sem_os_numeros_nao_vira_radio():
    assert mensagem_de_diferenca({"type": "coaching_event", "evidence": "texto"}, CURVAS, L) is None


def test_resumo_na_linha():
    m = mensagem_de_resumo(7, 88.132, 84.829, "volta_ia")
    assert m["titulo"] == "Volta 7: 1:28,132"
    assert m["texto"] == "+3,303 s para a volta da IA (1:24,829)"
    assert m["fala"] == "Volta 7: 1 minuto e 28,1 segundos, 3,3 segundos atrás da IA."


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
    assert causa_principal(ev, "volta_ia")["fala"] == "Freia 15 metros antes da IA."   # no corte: conta
    assert causa_principal(ev, "volta_ia")["falaCurta"] == "Freia 15 metros antes."
    ev["brakeDeltaM"] = -14.9                                                     # abaixo: vai para a minima
    assert causa_principal(ev, "volta_ia")["fala"] == "Mínima de 64 contra 94 quilômetros por hora."
    ev["yourMinSpeedKmh"] = 94.0 - CORTE_MINIMA_KMH + 0.1                         # abaixo dos dois cortes
    assert causa_principal(ev, "volta_ia") is None
    ev["brakeDeltaM"] = -30.0
    assert causa_principal(ev, "volta_ia")["fala"] == "Freia 30 metros depois da IA."
    assert (CORTE_FREADA_M, CORTE_MINIMA_KMH) == (15.0, 8.0)


def test_resumo_com_a_curva_de_maior_perda():
    m = mensagem_de_resumo(7, 90.363, 84.829, "volta_ia", {"curva": "C11", "lado": "esquerda", "perdaS": 1.14})
    assert m["detalhe"] == "mais perdeu na C11, esquerda: +1,14 s"
    assert m["fala"] == ("Volta 7: 1 minuto e 30,4 segundos, 5,5 segundos atrás da IA. "
                         "Mais perdeu na curva 11: 1,1 segundo.")
    assert m["falas"][-1] == "Volta 7: 5,5 segundos atrás."
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
    assert m["linhas"][0].startswith("C12, esquerda: perde 0,90 s por volta (0,85 s · 0,90 s · 1,02 s)")
    assert "mínima 80 contra 110 km/h" in m["linhas"][0] and "freada 50 m antes" in m["linhas"][0]
    assert "traçado 0,4 m mais à esquerda" in m["linhas"][0]        # o lado por extenso (ADR 0003)
    # A fala no estilo da frase do coach, cada diferenca uma frase, com as unidades (pedido 36).
    assert m["fala"].startswith("Análise das voltas 6 a 8. Curva 12: perde 9 décimos por volta. "
                                "Mínima de 80 contra 110 quilômetros por hora. Freia 50 metros antes da IA.")
    from core.radio.texto import _diferenca_falada
    assert _diferenca_falada("tracado", -7.9, {}) == "Passa 8 metros mais à direita."
    assert _diferenca_falada("tracado", 1.5, {}) == "Passa 1,5 metro mais à esquerda."
    assert _diferenca_falada("acelerador", 14.0, {}) == "Acelera 14 metros depois."
    assert _diferenca_falada("tracado", -7.9, {}, "da IA") == "Passa 8 metros mais à direita que a IA."
    assert _diferenca_falada("tracado", 2.4, {}, "da sua melhor") == "Passa 2 metros mais à esquerda que a sua melhor."
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
    assert 0.12 * len(m["falas"][0]) > 7.3               # a completa, com a causa, passa do limite
    # O radio gera da mais completa a mais curta e fica com a primeira que cabe: ainda com a causa.
    cabe = next(i for i, f in enumerate(m["falas"]) if 0.12 * len(f) <= 7.3)
    assert m["fala"] == m["falas"][cabe] and "Freia 38 metros antes" in m["fala"]
    assert m["duracaoS"] <= 7.3 and ditas == m["falas"][:cabe + 1]


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


def test_a_volta_com_rodada_sai_da_analise_e_o_resumo_nao_cita_a_curva(tmp_path, monkeypatch):
    """Pedido 36, Parte B.2: como a volta 5 de 21/10 (26,5 s na C12), que entrou na primeira analise."""
    from core.radio.analise import PERDA_DE_RODADA_S, teve_rodada

    assert PERDA_DE_RODADA_S == 5.0 and teve_rodada(_medidas([26.5, 0.3, 0.5])) and not teve_rodada(_medidas([4.9, 0, 0]))
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    medidas = iter([_medidas([26.54, 0.30, 0.47]), _medidas([0.73, -0.1, 0.76]), _medidas([0.51, 0.2, 0.94]),
                    _medidas([0.60, 0.1, 0.80])])
    monkeypatch.setattr(radio, "_medidas_da_volta", lambda volta: next(medidas))

    def linha(n):
        pista.volta = {"volta": n, "tempoS": 110.0, "teveIA": False, "momento": n, "completa": True}
        radio.on_frame(QUADRO)
        pista.agora += 1.0
        radio.on_frame(QUADRO)

    pista.s = 50.0
    for n in (5, 9, 11, 12):
        linha(n)
    resumos = [m for m in radio._pendentes if m["origem"] == "resumo"]
    analises = [m for m in radio._pendentes if m["origem"] == "analise"]
    da_volta_5 = next(r for r in resumos if r["volta"] == 5)
    assert da_volta_5["piorCurva"] is None and "curva" not in da_volta_5["fala"].lower()
    # A analise usa a volta valida seguinte (12) no lugar da 5.
    assert len(analises) == 1 and analises[0]["voltasAnalisadas"] == [9, 11, 12]


def test_o_log_de_acesso_deixa_de_fora_so_as_rotas_frequentes_bem_sucedidas():
    """Pedido 36, Parte B.3: os pontos novos e as mensagens do radio saem do log; os erros e o resto ficam."""
    import logging

    from core.registro_de_acesso import LOGGER_DE_ACESSO, SemPedidosFrequentes, silenciar_rotas_frequentes

    filtro = SemPedidosFrequentes()

    def linha(caminho, codigo):
        return logging.LogRecord(LOGGER_DE_ACESSO, logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                                 ("127.0.0.1:5000", "GET", caminho, "1.1", codigo), None)

    assert not filtro.filter(linha("/api/live/volta/novos?versao=3&desde=10", 200))
    assert not filtro.filter(linha("/api/radio/mensagens?desde=4&instancia=x", 200))
    assert filtro.filter(linha("/api/live/volta/novos?versao=3&desde=10", 500))      # erro fica
    assert filtro.filter(linha("/api/radio/minimapa", 200))                          # outra rota fica
    assert filtro.filter(linha("/api/radio/mensagens-antigas", 200))
    silenciar_rotas_frequentes()
    silenciar_rotas_frequentes()
    assert sum(isinstance(f, SemPedidosFrequentes) for f in logging.getLogger(LOGGER_DE_ACESSO).filters) == 1


def _numeros_sem_unidade(fala: str):
    """Os numeros de medida da fala que nao tem a unidade logo depois (pedido 36, Parte C.5).

    Ficam de fora os numeros que nao sao medida: a curva, a volta, o microssetor e a lista
    das voltas da analise. Dois numeros juntos podem dividir a unidade, no fim:
    "minima de 102 contra 128 quilometros por hora"."""
    import re

    resto = re.sub(r"\b(Curva|curva|Volta|Microssetor) \d+", "", fala)
    resto = re.sub(r"(Análise das voltas|Voltas) [\d, ea]+?\.", "", resto)
    unidade = r"(décimos?|segundos?|metros?|minutos?|quilômetros por hora)\b"
    faltando = []
    for m in re.finditer(r"\d+(,\d+)?", resto):
        depois = resto[m.end():]
        if re.match(r"\s+" + unidade, depois) or re.match(r"\s+contra\s+\d+(,\d+)?\s+" + unidade, depois):
            continue
        faltando.append((m.group(0), fala))
    return faltando


def test_todo_numero_falado_tem_a_unidade_em_todos_os_tipos_de_mensagem():
    """Pedido 36, Parte C.5: em todas as variantes de fala de todos os tipos de mensagem."""
    from core.radio.texto import mensagem_de_resumo, mensagem_de_teste

    mensagens = []
    for perda, freada, minima_sua, tipo in ((0.04, 38.0, 93.5, "volta_ia"), (0.742, -20.0, 150.0, "volta_ia"),
                                           (1.253, 0.0, 64.0, "volta_ia"), (2.5, 3.0, 154.0, "minha_melhor"),
                                           (0.97, 60.0, 157.0, "minha_melhor")):
        ev = _evento(indice=38, perda=perda, tipo=tipo)
        ev["evidence"].update(brakeDeltaM=freada, yourMinSpeedKmh=minima_sua)
        mensagens.append(mensagem_de_diferenca(ev, CURVAS, L))
    for tempo, ref, pior in ((88.132, 84.829, None), (90.363, 84.829, {"curva": "C11", "lado": "esquerda", "perdaS": 1.14}),
                             (85.3, 84.829, {"curva": "C01", "lado": "esquerda", "perdaS": 0.7}),
                             (136.188, 84.829, {"curva": "C12", "lado": "esquerda", "perdaS": 2.6}),
                             (59.95, None, None), (84.1, 84.829, None)):
        mensagens.append(mensagem_de_resumo(8, tempo, ref, "volta_ia", pior))
    voltas = [{"volta": n, "medidas": _medidas(p, freada=f, minima=mi, acelerador=a, tracado=tr)}
              for n, p, f, mi, a, tr in ((6, [0.85, 0.30, 0.9], -50.0, -30.0, 12.0, 7.9),
                                         (7, [0.90, -0.1, 1.1], -46.0, -24.0, 14.0, -1.5),
                                         (8, [1.02, 0.25, 0.95], -40.0, -26.0, -9.0, 2.0))]
    a = analisar(voltas)
    for c in a["curvas"]:
        c["ditas"] = ["freada", "minima", "acelerador", "tracado"]     # todas as medidas faladas
    mensagens.append(mensagem_de_analise(a, "volta_ia"))
    mensagens.append(mensagem_de_analise(a, "minha_melhor"))
    mensagens.append(mensagem_de_teste())
    falas = [f for m in mensagens for f in (m.get("falas") or [m["fala"]])]
    assert len(falas) > 40
    faltando = [x for f in falas for x in _numeros_sem_unidade(f)]
    assert faltando == []
    # O teste do teste: um numero solto e achado.
    assert _numeros_sem_unidade("Curva 4: 1,0 por volta. Mínima 102 contra 128.") == [
        ("1,0", "Curva 4: 1,0 por volta. Mínima 102 contra 128."), ("102", "Curva 4: 1,0 por volta. Mínima 102 contra 128."),
        ("128", "Curva 4: 1,0 por volta. Mínima 102 contra 128.")]


def test_a_freada_da_ia_por_curva_pela_regra_do_relatorio_de_evolucao():
    """Pedido 36, Parte D.2: o primeiro ponto, do apice anterior ao apice, em que o freio passa de 0,15
    (`ml.comparison.evolution.braking_point`); a curva sem freada fica de fora; a linha atravessa a pista."""
    import numpy as np

    from core.radio import minimapa
    from ml.comparison.evolution import braking_point

    sys.path.insert(0, str(BACKEND / "tests"))
    from test_lap_origin import circular_track

    track = circular_track()
    s = np.asarray(track.s)

    class _Curva:
        def __init__(self, label, apice):
            self.label, self.apex_s = label, float(apice)

    class _Trecho:
        def __init__(self, label, apice):
            self.corner = _Curva(label, apice)

    trechos = [_Trecho("C01-esq", s[100]), _Trecho("C02-dir", s[300]), _Trecho("C03-esq", s[500])]
    freio = np.zeros(track.size)
    freio[80:100] = 0.6          # a freada da C01 comeca no ponto 80
    freio[270:300] = 0.14        # na C02, o freio nao passa de 0,15: sem freada
    freio[460:500] = 0.9         # a da C03 comeca no 460
    freadas = minimapa.freadas_da_referencia(track, trechos, freio.tolist())
    assert [f["curva"] for f in freadas] == ["C01", "C03"]
    assert freadas[0]["s"] == pytest.approx(braking_point(freio, track, s[500], s[100]), abs=0.05)
    assert freadas[1]["s"] == pytest.approx(float(s[460]), abs=0.05)
    (ax, az), (bx, bz) = freadas[0]["pontos"]
    i = 80
    largura = float(np.asarray(track.width_left)[i] + np.asarray(track.width_right)[i])
    assert np.hypot(ax - bx, az - bz) == pytest.approx(largura, abs=0.05)   # de uma borda a outra
    assert minimapa.freadas_da_referencia(track, trechos, [0.0] * 10) == []  # sem a grade inteira


def _pista_de_teste_com_uma_curva():
    """A pista circular de teste com uma curva de mentira (C03, a esquerda), para o replay."""
    import numpy as np

    from core.radio.analise import Pista

    sys.path.insert(0, str(BACKEND / "tests"))
    from test_lap_origin import circular_track

    track = circular_track()
    s = np.asarray(track.s)

    class _Curva:
        def __init__(self, label, inicio, apice, fim):
            self.label, self.start_s, self.apex_s, self.end_s = label, float(inicio), float(apice), float(fim)

    class _Trecho:
        def __init__(self, curva, inicio, fim):
            self.corner, self.start_s, self.end_s = curva, float(inicio), float(fim)

    trechos = [_Trecho(_Curva("C02-dir", s[100], s[120], s[140]), s[60], s[200]),
               _Trecho(_Curva("C03-esq", s[400], s[430], s[460]), s[200], s[600])]
    return track, Pista(track=track, segmentos=trechos), s


def _grade_de_teste(s, v_ms, lateral, freia_em, minima_em, minima_kmh):
    import numpy as np

    n = s.size
    velocidade = np.full(n, v_ms * 3.6)
    velocidade[minima_em] = minima_kmh
    freio = np.zeros(n)
    freio[freia_em:minima_em] = 0.8
    acelerador = np.where(freio > 0, 0.0, 1.0)
    return {"elapsed": s / v_ms, "velocidade": velocidade, "freio": freio, "acelerador": acelerador,
            "lateral": np.full(n, float(lateral))}


def test_o_replay_da_curva_tem_as_duas_linhas_freadas_minimas_tracado_e_a_perda():
    """Pedido 36, Parte E: os dados de uma curva, so com as grades (nada de fisica nova)."""
    import numpy as np

    from core.radio.replay import dados_da_curva
    from ml.comparison.evolution import segment_time

    track, pista, s = _pista_de_teste_com_uma_curva()
    voce = _grade_de_teste(s, 45.0, 1.5, freia_em=380, minima_em=425, minima_kmh=95.0)    # freia antes, mais a esquerda
    ia = _grade_de_teste(s, 50.0, 0.0, freia_em=395, minima_em=430, minima_kmh=110.0)
    d = dados_da_curva(pista, "C03", voce, float(s[-1] / 45.0), ia, float(s[-1] / 50.0), 7, "volta_ia")
    assert d["curva"] == "C03" and d["lado"] == "esquerda" and d["volta"] == 7
    assert d["rotuloDaReferencia"] == "IA (referência)"
    lv, lr = d["linhas"]["voce"], d["linhas"]["referencia"]
    assert len(lv) == len(lr) > 50 and lv[0][2] == 0.0 and lr[0][2] == 0.0          # cada um no seu tempo, da mesma entrada
    assert lv[-1][2] > lr[-1][2]                                                    # a IA abre
    assert d["duracaoS"] == pytest.approx(lv[-1][2], abs=1e-3)
    assert {p[3] for p in lv} >= {1, 2}                                              # o pedal: freio e acelerador
    assert d["freadas"]["distanciaM"] == pytest.approx(float(s[380] - s[395]), abs=0.1)   # freou 15 pontos antes
    assert d["minimas"]["voce"]["kmh"] == 95.0 and d["minimas"]["referencia"]["kmh"] == 110.0
    t = d["tracado"]
    assert t["distanciaM"] == pytest.approx(1.5) and t["lado"] == "esquerda"         # ADR 0003: positivo = esquerda
    assert np.hypot(t["voce"][0] - t["referencia"][0], t["voce"][1] - t["referencia"][1]) == pytest.approx(1.5, abs=0.01)
    seg = pista.segmentos[1]
    perda = segment_time(voce["elapsed"], s[-1] / 45.0, track, seg) - segment_time(ia["elapsed"], s[-1] / 50.0, track, seg)
    assert d["perdaS"] == pytest.approx(perda, abs=1e-3) and d["perdaS"] > 0
    assert dados_da_curva(pista, "C14", voce, 1.0, ia, 1.0, 7, "volta_ia") is None


def test_o_replay_da_analise_usa_a_volta_mais_perto_da_mediana():
    """Pedido 36, Parte E.2: na analise, a volta das 3 cuja perda na curva fica mais perto da mediana."""
    from core.radio.replay import replay_da_analise, volta_mais_perto_da_mediana

    voltas = [{"volta": 6}, {"volta": 7}, {"volta": 8}]
    assert volta_mais_perto_da_mediana(voltas, {"perdas": [0.85, 0.90, 1.02], "perdaMedianaS": 0.90}) == 1
    assert volta_mais_perto_da_mediana(voltas, {"perdas": [26.54, 0.73, 0.51], "perdaMedianaS": 0.73}) == 1
    assert volta_mais_perto_da_mediana(voltas, {"perdas": [0.5], "perdaMedianaS": 0.5}) is None   # nao sao as 3

    track, pista, s = _pista_de_teste_com_uma_curva()
    ia = _grade_de_teste(s, 50.0, 0.0, 395, 430, 110.0)
    tres = [{"volta": n, "tempoS": float(s[-1] / v), "grade": _grade_de_teste(s, v, 1.0, 385, 428, 100.0)}
            for n, v in ((6, 44.0), (7, 46.0), (8, 48.0))]
    analise = {"curvas": [{"curva": "C03", "perdas": [0.9, 0.6, 0.3], "perdaMedianaS": 0.6}]}
    replays = replay_da_analise(pista, tres, analise, ia, float(s[-1] / 50.0), "volta_ia")
    assert [(r["curva"], r["volta"]) for r in replays] == [("C03", 7)]


def test_a_rota_do_replay(tmp_path, monkeypatch):
    """Pedido 36, Parte E.6: a rota entrega os dados do replay de uma mensagem entregue; 404 sem replay."""
    import asyncio

    from fastapi import HTTPException

    import main
    from routers import radio as rota

    radio = _radio(tmp_path, _Pista())
    monkeypatch.setattr(main, "radio_do_engenheiro", radio)
    radio._entregues.append({"id": 3, "origem": "analise", "_replay": [{"curva": "C01"}]})
    radio._entregues.append({"id": 4, "origem": "resumo"})
    dados = json.loads(asyncio.run(rota.get_replay(3)).body)
    assert dados == {"id": 3, "origem": "analise", "curvas": [{"curva": "C01"}]}
    for sem in (4, 99):
        with pytest.raises(HTTPException) as erro:
            asyncio.run(rota.get_replay(sem))
        assert erro.value.status_code == 404


# ------------------------------------------------------------ pedido 43 ---

def _voz_de_teste(s, comprimento):
    """O evidence de uma frase do coach no microssetor que contem a sua minima na C03 de teste (s[425])."""
    indice = int(float(s[425]) / (comprimento / 60))
    return indice, {"microsector": indice, "lossSeconds": 0.635, "yourBrakeOnsetM": float(s[380]),
                    "referenceBrakeOnsetM": float(s[395]), "brakeDeltaM": 30.5,
                    "yourMinSpeedKmh": 100.7, "referenceMinSpeedKmh": 144.5}


def test_o_replay_da_frase_do_coach_escreve_os_numeros_da_voz_nos_pontos_do_coach():
    """Pedido 43, Parte B: os rotulos com os numeros da voz (arredondados como o cartao), as freadas
    onde o coach mediu, as minimas no microssetor da fala, sem tracado, e o trecho da fala."""
    from core.radio.replay import dados_da_curva

    track, pista, s = _pista_de_teste_com_uma_curva()
    voce = _grade_de_teste(s, 45.0, 1.5, freia_em=370, minima_em=425, minima_kmh=95.0)
    ia = _grade_de_teste(s, 50.0, 0.0, freia_em=400, minima_em=430, minima_kmh=110.0)
    indice, voz = _voz_de_teste(s, float(track.length))
    args = (pista, "C03", voce, float(s[-1] / 45.0), ia, float(s[-1] / 50.0), 7, "volta_ia")
    sem, d = dados_da_curva(*args), dados_da_curva(*args, voz=voz)
    # sem a voz, o replay e o da curva inteira (a freada pela regra do relatorio de evolucao)
    assert sem["voz"] is None and sem["tracado"] is not None
    assert sem["freadas"]["distanciaM"] == pytest.approx(float(s[370] - s[400]), abs=0.1)
    # com a voz: 30,5 m vira 30 (o `round` do cartao); o cliente escreve sem arredondar de novo
    assert d["freadas"]["distanciaM"] == -30.0
    assert d["freadas"]["voce"]["s"] == pytest.approx(float(s[380]), abs=0.05)
    assert d["freadas"]["referencia"]["s"] == pytest.approx(float(s[395]), abs=0.05)
    assert d["minimas"]["voce"]["kmh"] == 101.0 and d["minimas"]["referencia"]["kmh"] == 144.0   # round(144,5) = 144
    assert d["tracado"] is None                                      # o coach nao mede o lado
    assert d["voz"]["microssetor"] == indice + 1 and d["voz"]["perdaS"] == 0.64
    assert d["voz"]["fimM"] - d["voz"]["inicioM"] == pytest.approx(float(track.length) / 60, abs=0.2)
    # as minimas no ponto mais lento de cada grade dentro do microssetor: a sua em s[425]
    for lado in ("voce", "referencia"):
        assert d["voz"]["inicioM"] - 0.1 <= d["minimas"][lado]["dM"] <= d["voz"]["fimM"] + 0.1
    assert d["minimas"]["voce"]["dM"] == pytest.approx(d["freadas"]["voce"]["dM"] + float(s[425] - s[380]), abs=0.2)
    # as linhas e os carros continuam os da curva inteira
    assert d["linhas"] == sem["linhas"] and d["perdaS"] == sem["perdaS"]


def test_o_replay_da_frase_cresce_para_conter_o_trecho_da_fala():
    """Pedido 43, B.3: o microssetor da fala que comeca antes da janela da curva entra no replay."""
    from core.radio.replay import dados_da_curva

    track, pista, s = _pista_de_teste_com_uma_curva()
    voce = _grade_de_teste(s, 45.0, 1.5, freia_em=380, minima_em=425, minima_kmh=95.0)
    ia = _grade_de_teste(s, 50.0, 0.0, freia_em=395, minima_em=430, minima_kmh=110.0)
    args = (pista, "C03", voce, float(s[-1] / 45.0), ia, float(s[-1] / 50.0), 7, "volta_ia")
    sem = dados_da_curva(*args)
    indice = int(float(s[340]) / (float(track.length) / 60))      # a janela comeca em s[355]
    d = dados_da_curva(*args, voz={"microsector": indice, "lossSeconds": 0.2, "yourMinSpeedKmh": 150.0,
                                   "referenceMinSpeedKmh": 160.0})
    assert len(d["linhas"]["voce"]) > len(sem["linhas"]["voce"])
    assert d["voz"]["inicioM"] == pytest.approx(0.0, abs=track.step)
    assert d["freadas"] == {"voce": None, "referencia": None, "distanciaM": None}   # a voz nao falou da freada


def test_os_dados_dos_visuais_vem_na_rota_do_replay():
    """Pedido 43, Parte C: a velocidade em cada ponto, o passo da grade, as marcas e as separacoes."""
    from core.radio.replay import dados_da_curva

    track, pista, s = _pista_de_teste_com_uma_curva()
    voce = _grade_de_teste(s, 45.0, 1.5, freia_em=380, minima_em=425, minima_kmh=95.0)
    ia = _grade_de_teste(s, 50.0, 0.0, freia_em=395, minima_em=430, minima_kmh=110.0)
    d = dados_da_curva(pista, "C03", voce, float(s[-1] / 45.0), ia, float(s[-1] / 50.0), 7, "volta_ia")
    n = len(d["linhas"]["voce"])
    assert d["passoM"] == pytest.approx(track.step, abs=1e-3)
    assert len(d["velocidades"]["voce"]) == len(d["velocidades"]["referencia"]) == n
    assert min(d["velocidades"]["voce"]) == 95.0 and min(d["velocidades"]["referencia"]) == 110.0
    # a minima marcada no ponto da velocidade minima, na mesma distancia do eixo
    k = d["velocidades"]["voce"].index(95.0)
    assert d["minimas"]["voce"]["dM"] == pytest.approx(k * d["passoM"], abs=0.1)
    assert d["freadas"]["voce"]["dM"] == pytest.approx(d["freadas"]["referencia"]["dM"] - float(s[395] - s[380]), abs=0.2)
    sec = d["secoes"]
    assert sec["freadaM"] == d["freadas"]["voce"]["dM"]                       # a primeira das duas freadas
    assert sec["minimaM"] == d["minimas"]["referencia"]["dM"]
    assert sec["freadaM"] < sec["minimaM"] < sec["saidaM"] <= (n - 1) * d["passoM"] + 0.1


def test_o_replay_da_analise_escreve_os_numeros_do_cartao_e_a_linha_termina_na_perda():
    """Decisoes do fechamento do pedido 43: as medianas nos rotulos, as marcas medindo o rotulo, as
    linhas da volta mais perto da mediana e a diferenca acumulada cobrindo o trecho da curva."""
    import numpy as np

    from core.radio.replay import dados_da_curva

    track, pista, s = _pista_de_teste_com_uma_curva()
    voce = _grade_de_teste(s, 45.0, 1.5, freia_em=370, minima_em=425, minima_kmh=95.0)
    ia = _grade_de_teste(s, 50.0, 0.0, freia_em=400, minima_em=430, minima_kmh=110.0)
    args = (pista, "C03", voce, float(s[-1] / 45.0), ia, float(s[-1] / 50.0), 7, "volta_ia")
    curva = {"curva": "C03", "diferencas": [{"medida": "freada", "valor": -42.5, "peso": 2.8},
                                            {"medida": "minima", "valor": -20.0, "peso": 2.5, "sua": 90.5, "ref": 110.0},
                                            {"medida": "tracado", "valor": -7.94, "peso": 4.4}]}
    sem, d = dados_da_curva(*args), dados_da_curva(*args, da_analise=curva)
    assert sem["diferencaNoTrecho"] is None
    assert d["freadas"]["distanciaM"] == -42.0                                # round(-42,5), como o cartao
    assert d["freadas"]["referencia"]["s"] == sem["freadas"]["referencia"]["s"]
    assert d["freadas"]["referencia"]["s"] - d["freadas"]["voce"]["s"] == pytest.approx(42.5, abs=0.1)  # a marca mede o rotulo
    assert d["minimas"]["voce"]["kmh"] == 90.0 and d["minimas"]["referencia"]["kmh"] == 110.0
    t = d["tracado"]
    assert t["distanciaM"] == 7.9 and t["lado"] == "direita"
    assert np.hypot(t["voce"][0] - t["referencia"][0], t["voce"][1] - t["referencia"][1]) == pytest.approx(7.94, abs=0.02)
    # as linhas, os carros e o pedal continuam os da volta; so crescem se a marca cair antes da janela
    assert d["linhas"] == sem["linhas"] and d["perdaS"] == sem["perdaS"] and d["velocidades"] == sem["velocidades"]
    fora = dados_da_curva(*args, da_analise={**curva, "diferencas": [{"medida": "freada", "valor": -300.0, "peso": 20}]})
    assert len(fora["linhas"]["voce"]) > len(sem["linhas"]["voce"]) and fora["freadas"]["voce"]["dM"] <= track.step
    sem_freada = dados_da_curva(*args, da_analise={**curva, "diferencas": []})
    assert sem_freada["freadas"] == {"voce": None, "referencia": None, "distanciaM": None}
    assert sem_freada["minimas"]["voce"]["kmh"] == sem["minimas"]["voce"]["kmh"]
    # a diferenca: zero na entrada do trecho e, no fim, exatamente a perda da curva
    n = d["diferencaNoTrecho"]
    seg = pista.segmentos[1]
    assert n["valores"][0] == 0.0 and n["valores"][-1] == d["perdaS"]
    assert n["comprimentoM"] == pytest.approx(float(np.mod(seg.end_s - seg.start_s, track.length)), abs=0.1)
    assert (len(n["valores"]) - 1) * n["passoM"] == pytest.approx(n["comprimentoM"], abs=0.1)
    entrada = d["freadas"]["referencia"]["s"] - d["freadas"]["referencia"]["dM"]
    assert n["entradaDoReplayM"] == pytest.approx(entrada - float(seg.start_s), abs=0.2)
    assert all(b >= a for a, b in zip(n["valores"], n["valores"][1:]))        # sempre perdendo, nesta volta de teste


def test_a_grade_da_sessao_tem_as_perdas_da_analise_as_voltas_de_fora_e_as_citadas(tmp_path, monkeypatch):
    """Pedido 43, C.4: a perda de cada curva e a da analise; a IA, a incompleta e a rodada ficam fora."""
    import asyncio
    from types import SimpleNamespace

    import main
    from routers import radio as rota

    pista = _Pista()
    radio = _radio(tmp_path, pista)
    radio._geometria = SimpleNamespace(segmentos=[SimpleNamespace(corner=SimpleNamespace(label=c))
                                                  for c in ("C01-esq", "C04-esq", "C12-esq")])
    sequencia = iter([_medidas([0.85, 0.30, 0.9]), _medidas([9.0, 0.1, 0.1]), _medidas([0.90, -0.1, -0.1]),
                      _medidas([0.5, 0.5, 0.5]), _medidas([1.02, 0.25, -0.2])])
    monkeypatch.setattr(radio, "_medidas_da_volta", lambda volta: next(sequencia))

    def linha(n, momento, **extra):
        pista.volta = {"volta": n, "tempoS": 90.0 + n, "teveIA": False, "momento": momento, "completa": True, **extra}
        radio.on_frame(QUADRO)
        pista.agora += 1.0
        radio.on_frame(QUADRO)

    pista.s = 50.0
    linha(5, 0, teveIA=True)
    linha(6, 1)
    linha(7, 2)                         # rodada: 9 s na C12
    linha(8, 3)
    linha(9, 4, completa=False)
    linha(10, 5)
    g = radio.grade_da_sessao()
    assert g["curvas"] == ["C01", "C04", "C12"]
    assert [v["volta"] for v in g["voltas"]] == [6, 8, 10]
    assert g["voltas"][0]["perdas"] == [0.9, 0.3, 0.85]          # na ordem das curvas da pista
    assert [f["volta"] for f in g["fora"]] == [5, 7, 9]
    assert g["fora"][0]["motivo"].startswith("a IA") and g["fora"][2]["motivo"] == "incompleta"
    assert g["fora"][1]["motivo"] == "rodada ou saída de pista: perdeu 9,0 s na C12"
    # a volta que nao fechou na linha nao passa pelo radio: aparece pelo buraco na numeracao
    radio._grade_fora.append({"volta": 14, "tempoS": 95.0, "motivo": "a IA pilotou parte da volta"})
    com_buraco = radio.grade_da_sessao()["fora"]
    assert [f["volta"] for f in com_buraco] == [5, 7, 9, 11, 12, 13, 14]
    assert com_buraco[3]["tempoS"] is None and com_buraco[3]["motivo"] == "o rádio não viu esta volta fechar na linha"
    radio._grade_fora.pop()
    # a analise das voltas 6, 8 e 10 cita a C12 na volta da mediana (0,90 s, a volta 8), ao ser entregue
    analise = [m for m in radio._pendentes if m["origem"] == "analise"][0]
    assert analise["_citadas"][0] == {"volta": 8, "curva": "C12", "perdaS": 0.9}
    radio._entregar(analise, pista.agora, {"s": 500.0})
    assert {"volta": 8, "curva": "C12", "origem": "analise"}.items() <= radio.grade_da_sessao()["citadas"][0].items()
    assert g["voltas"][1]["perdas"][2] == analise["_citadas"][0]["perdaS"]   # a celula tem o numero da analise
    # a frase do coach marca a curva dela na volta dela, e guarda o que o coach mediu
    radio.on_coaching_event(_evento(indice=3, volta=11))
    frase = [m for m in radio._pendentes if m["origem"] == "coach"][0]
    frase["_futuro"].result(timeout=5)
    assert frase["_voz"]["brakeDeltaM"] == 38.0 and "_voz" not in radio._publica(frase)
    radio._entregar(frase, pista.agora, {"s": 500.0})
    assert {"volta": 11, "curva": "C01", "origem": "coach"}.items() <= radio.grade_da_sessao()["citadas"][-1].items()
    # cada volta de fora lista as curvas citadas nela (decisao do fechamento); a 11 ainda nao fechou
    assert all(f["citadas"] == [] for f in radio.grade_da_sessao()["fora"])
    for volta_citada in (9, 4):                                        # a 4: antes da primeira volta que fechou
        radio.on_coaching_event(_evento(indice=3, volta=volta_citada))
        outra = [m for m in radio._pendentes if m["origem"] == "coach"][-1]
        outra["_futuro"].result(timeout=5)
        radio._entregar(outra, pista.agora, {"s": 500.0})
    por_volta = {f["volta"]: f["citadas"] for f in radio.grade_da_sessao()["fora"]}
    assert por_volta[9] == ["C01"] and por_volta[4] == ["C01"] and por_volta[5] == [] and 11 not in por_volta
    monkeypatch.setattr(main, "radio_do_engenheiro", radio)
    assert json.loads(asyncio.run(rota.get_grade()).body)["voltas"][0]["volta"] == 6
