"""Pedido 31, Parte E.1: o radio do engenheiro.

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
    assert m["fala"] == "Curva 1, esquerda: 0,74 atrás da IA."
    assert m["s"] == pytest.approx(3 * L / 60, abs=0.1)  # o fim do microssetor: ali o coach fecha a medida
    assert "." not in m["texto"].split(" s ")[0]  # numero com virgula


def test_frase_contra_a_sua_melhor_e_na_curva_da_direita():
    m = mensagem_de_diferenca(_evento(indice=29, perda=0.215, tipo="minha_melhor"), CURVAS, L)
    assert m["titulo"] == "C02, direita" and m["microssetor"] == 30
    assert m["fala"] == "Curva 2, direita: 0,21 atrás da sua melhor."
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
    )
    # A pista de mentira, sem ler a geometria do repositorio.
    radio._chave_da_pista = str(tmp_path)
    radio._curvas, radio._comprimento = CURVAS, L
    radio._janelas = janelas_de_radio(CURVAS, L, antes=100.0, depois=20.0, minima=50.0)
    return radio


def _esperar_o_audio(radio):
    for m in list(radio._pendentes):
        m["_futuro"].result(timeout=5)


def test_mensagem_gerada_dentro_da_curva_espera_a_reta(tmp_path):
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    pista.s = 300.0  # dentro da C01
    radio.on_coaching_event(_evento(indice=3))
    _esperar_o_audio(radio)
    radio.on_frame()
    assert radio.desde(0)["mensagens"] == [] and radio.desde(0)["pendentes"] == 1
    pista.s = 500.0  # a reta
    radio.on_frame()
    entregue = radio.desde(0)["mensagens"]
    assert len(entregue) == 1 and entregue[0]["sCarro"] == 500.0 and entregue[0]["audio"] == "/api/radio/audio/1"


def test_uma_mensagem_por_vez_e_o_resto_vai_com_o_resumo(tmp_path):
    pista = _Pista()
    radio = _radio(tmp_path, pista)
    pista.s = 500.0
    radio.on_coaching_event(_evento(indice=6))
    radio.on_coaching_event(_evento(indice=7))
    _esperar_o_audio(radio)
    radio.on_frame()
    assert len(radio.desde(0)["mensagens"]) == 1  # a segunda espera o audio da primeira (2 s)
    pista.s = 2100.0  # a volta segue, entra no miolo e acaba antes da proxima janela
    pista.agora += 3.0
    radio.on_frame()
    assert len(radio.desde(0)["mensagens"]) == 1
    pista.volta = {"volta": 2, "tempoS": 88.132, "teveIA": False, "momento": 1}
    radio.on_frame()            # a linha: o resumo espera as ultimas frases chegarem
    pista.agora += 1.0
    radio.on_frame()            # o que sobrou da volta sai na linha, sem esperar janela
    _esperar_o_audio(radio)
    pista.agora += 3.0
    radio.on_frame()            # e depois o resumo
    origens = [m["origem"] for m in radio.desde(0)["mensagens"]]
    assert origens == ["coach", "coach", "resumo"]


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
    radio.on_frame()
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
