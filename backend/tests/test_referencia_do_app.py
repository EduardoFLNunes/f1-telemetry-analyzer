"""Pedido 51 (ADR 0032): a referencia do app e a volta do modelo.

* nenhuma fala, cartao ou rotulo ligado a referencia diz "IA" (o rádio, o coach, o replay e o app do jogo);
* a configuracao antiga `volta_ia` vira `volta_do_modelo` ao abrir; `minha_melhor` fica;
* sem a volta do modelo, so "Sua melhor volta", com a frase do ADR 0032, item 4;
* a volta do modelo vem do arquivo derivado, no formato da volta do store, e so entra na mesma geometria.
"""
import json
import os
import re
import sys
from pathlib import Path
from unittest import mock

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.assisted_analysis.reference_model import (  # noqa: E402
    DEFAULT_REFERENCE, REFERENCE_KINDS, DriverReferenceModel, normalized_kind,
)
from core.coleta.configuracao import AppConfig  # noqa: E402
from core.live import driving_coach as dc  # noqa: E402
from core.radio.analise import analisar  # noqa: E402
from core.radio.texto import (  # noqa: E402
    CurvaDaPista, causa_principal, mensagem_da_curva, mensagem_de_analise, mensagem_de_diferenca, mensagem_de_resumo,
)

IA = re.compile(r"\bIA\b")
TIPO = "volta_do_modelo"
L = 4334.08
CURVAS = [CurvaDaPista("C01", "esquerda", 200.0, 340.0, 3500.0, 1170.0),
          CurvaDaPista("C02", "direita", 2000.0, 2200.0, 1170.0, 3500.0)]
CURVA_1 = {"curva": "C01", "lado": "esquerda", "perdaS": 0.7,
           "causa": {"trecho": "freada", "perdaTrechoS": 0.5, "medida": "freada", "valor": -15.0}}


def _textos(m):
    """Tudo o que a mensagem mostra ou fala: o titulo, o texto, o detalhe, as linhas e as falas."""
    out = [m.get("titulo"), m.get("texto"), m.get("detalhe"), m.get("fala")]
    out += list(m.get("falas") or []) + list(m.get("linhas") or [])
    return [str(t) for t in out if t]


def _medidas(perdas):
    def curva(codigo, perda):
        return {"curva": codigo, "lado": "esquerda", "perdaS": perda, "freadaM": -50.0, "minimaKmh": -30.0,
                "minimaSuaKmh": 80.0, "minimaRefKmh": 110.0, "aceleradorM": 12.0, "tracadoM": 0.4, "sDaCurva": 3100.0}
    return [curva("C12", perdas[0]), curva("C04", perdas[1]), curva("C01", perdas[2])]


def test_nenhuma_fala_cartao_ou_rotulo_da_referencia_diz_ia():
    mensagens = []
    for perda, freada, minima in ((0.742, 38.0, 93.5), (0.3, -30.0, 150.0), (1.2, 0.0, 64.0)):
        ev = {"type": "coaching_event", "lap_number": 2, "evidence": {
            "microsector": 2, "yourSeconds": 1.991, "referenceSeconds": 1.249, "lossSeconds": perda,
            "referenceKind": TIPO, "referenceLabel": "volta de referência", "brakeDeltaM": freada,
            "referenceMinSpeedKmh": 157.0, "yourMinSpeedKmh": minima}}
        mensagens.append(mensagem_de_diferenca(ev, CURVAS, L))
    for melhor in (None, {"situacao": "atras", "difS": 0.3, "melhorS": 88.7},
                   {"situacao": "melhor", "difS": 0.2, "melhorS": 88.0}):
        mensagens.append(mensagem_de_resumo(7, 89.0, 84.552, TIPO, CURVA_1, melhor))
    mensagens.append(mensagem_da_curva(7, CURVA_1, TIPO))
    analise = analisar([{"volta": n, "medidas": _medidas(p)} for n, p in
                        ((6, [0.85, 0.30, 0.9]), (7, [0.90, 0.2, 1.1]), (8, [1.02, 0.25, 0.95]))])
    mensagens.append(mensagem_de_analise(analise, TIPO, "m#0008"))
    textos = [t for m in mensagens for t in _textos(m)]
    assert len(textos) > 20
    assert [t for t in textos if IA.search(t)] == []
    # Diz contra quem: "da referência".
    assert any("atrás da referência" in t for t in textos)
    assert any("antes da referência" in t or "depois da referência" in t for t in textos)
    causa = causa_principal({"brakeDeltaM": 34.0}, TIPO)
    assert causa["fala"] == "Freou 34 metros antes da referência."


def test_melhor_da_sessao_no_lugar_de_melhor_volta_da_sessao():
    m = mensagem_de_resumo(8, 87.8, 84.552, TIPO, None, {"situacao": "melhor", "difS": 0.2, "melhorS": 88.0})
    textos = _textos(m)
    assert any(t.startswith("Melhor da sessão") for t in textos)
    assert not any("Melhor volta da sessão" in t or "melhor volta da sessão" in t for t in textos)


def test_as_frases_do_coach_dizem_a_referencia():
    assert dc._braking_clause(TIPO, 12.0) == "a referencia freia 12 m depois de voce"
    assert dc._min_speed_clause(TIPO, 104.0, 96.0) == "minima na referencia 104 km/h, a sua 96 km/h"
    assert dc._braking_clause("minha_melhor", 12.0).startswith("na sua melhor volta")


def test_o_rotulo_do_replay_e_referencia():
    texto = (BACKEND / "core" / "radio" / "replay.py").read_text(encoding="utf-8")
    assert '"IA (referência)"' not in texto and '"Referência"' in texto


def test_o_app_do_jogo_nao_diz_ia_para_a_referencia():
    lua = (BACKEND.parent / "tools" / "csp_app" / "radio_engenheiro" / "radio_engenheiro.lua").read_text(encoding="utf-8")
    assert "'frenagem da referência'" in lua and "'Referência'" in lua
    for proibido in ("'freada da IA'", "or 'IA'", "'da IA'", "'para a volta da IA'", "'IA (referência)'"):
        assert proibido not in lua, proibido
    manifest = (BACKEND.parent / "tools" / "csp_app" / "radio_engenheiro" / "manifest.ini").read_text(encoding="utf-8")
    assert "VERSION = 0.7.0" in manifest           # pedido 52: o app do jogo 0.7.0


def test_os_tipos_do_app():
    assert REFERENCE_KINDS == ("volta_do_modelo", "minha_melhor") and DEFAULT_REFERENCE == "volta_do_modelo"
    assert normalized_kind("volta_ia") == "volta_do_modelo" and normalized_kind("minha_melhor") == "minha_melhor"


def _arquivo(raiz: Path, geometry_id="g1", n=4):
    dados = {
        "formato": VM.FORMATO, "pista": "vhe_interlagos", "lap_id": "m_teste_m1#0008", "tempo_s": 84.552,
        "tempo": "1:24,552", "carro": "c", "geometry_id": geometry_id, "marca": "linha do projeto, meta atingida em 2026-11-15",
        "executada_por": "executada pela IA do jogo na linha do projeto",
        "origem": {"sessao": "m_teste_m1", "sequencia": 8, "volta_do_jogo": 9},
        "grade": {"pontos": n, "passo_m": 10.0, "comprimento_m": 40.0,
                  "elapsed_s": [0.0, 1.0, 2.0, 3.0], "lateral": [0.1, 0.2, 0.3, 0.4], "x": [0, 1, 2, 3],
                  "z": [0, 0, 0, 0], "speed_kmh": [100, 110, 120, 130], "gear": [3, 4, 4, 5],
                  "throttle": [1, 1, 0.5, 0], "brake": [0, 0, 0.2, 0.9]},
        "referencia": {"kind": VM.KIND, "lap_id": "m_teste_m1#0008", "lap_seconds": 84.55,
                       "sectors": [{"index": 0, "seconds": 84.55, "min_speed_kmh": 100.0, "brake_onset_m": 30.0}]},
    }
    caminho = VM.caminho(raiz, "vhe_interlagos")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def test_a_configuracao_antiga_vira_a_volta_do_modelo_ao_abrir(tmp_path):
    arquivo = tmp_path / "dados" / "data" / "configuracao" / "app.json"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(json.dumps({"referenciaCoach": "volta_ia"}), encoding="utf-8")
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AT_COACH_REFERENCE", None)
        config = AppConfig(tmp_path / "dados")
        assert config.reference() == ("volta_do_modelo", "configuracao")
        assert json.loads(arquivo.read_text(encoding="utf-8"))["referenciaCoach"] == "volta_do_modelo"
        arquivo.write_text(json.dumps({"referenciaCoach": "minha_melhor"}), encoding="utf-8")
        assert AppConfig(tmp_path / "dados").reference() == ("minha_melhor", "configuracao")


def test_sem_a_volta_do_modelo_so_a_sua_melhor_com_a_frase(tmp_path):
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AT_COACH_REFERENCE", None)
        repo = tmp_path / "repo"
        repo.mkdir()
        config = AppConfig(tmp_path / "dados", default_repository=repo)
        api = config.to_api()
        assert [o["id"] for o in api["opcoesReferencia"]] == ["minha_melhor", "desligado"]
        assert api["avisoReferencia"] == "A volta de referência desta pista ainda não foi gerada pelo modelo"
        _arquivo(repo)
        api = config.to_api()
        assert [(o["id"], o["rotulo"]) for o in api["opcoesReferencia"]] == [
            ("volta_do_modelo", "Volta de referência"), ("minha_melhor", "Sua melhor volta"), ("desligado", "coach desligado")]
        assert api["avisoReferencia"] is None and api["voltaDoModelo"]["tempo"] == "1:24,552"
        assert not any(IA.search(o["rotulo"]) for o in api["opcoesReferencia"])


def test_a_volta_do_modelo_no_formato_da_volta_do_store_e_so_na_mesma_geometria(tmp_path):
    from core.leitura.arquivos import LeitorDoStore

    dados = VM.ler(_arquivo(tmp_path))
    volta = VM.como_volta_do_store(dados)
    assert volta["disponivel"] and volta["lapId"] == "m_teste_m1#0008" and volta["pontosDaGrade"] == 4
    assert volta["freio"] == [0.0, 0.0, 0.2, 0.9] and volta["marcha"] == [3.0, 4.0, 4.0, 5.0]
    assert volta["rotulo"] == "Volta de referência"
    leitor = LeitorDoStore(volta_do_modelo=lambda: dados)
    assert leitor.ler_volta(None, "m_teste_m1#0008")["voltaDoModelo"] is True
    modelo = DriverReferenceModel(version="v", track="t", microsectors=1, lap_count=0, rejected_count=0,
                                  best_lap_id=None, best_lap_seconds=None, ideal_lap_seconds=None, geometry_id="outra")
    assert VM.anexar(modelo, dados) is False                  # outra geometria: fora
    modelo.geometry_id = "g1"
    assert VM.anexar(modelo, dados) is True and modelo.references["volta_do_modelo"]["lap_id"] == "m_teste_m1#0008"
    assert VM.encontrar([None, tmp_path / "nada", tmp_path], "vhe_interlagos")["lap_id"] == "m_teste_m1#0008"


@pytest.mark.parametrize("arquivo", ["main.py"])
def test_a_versao_do_backend(arquivo):
    # pedido 52: a 0.9.0-engenheiro
    assert 'BACKEND_PHASE_VERSION = "engenheiro"' in (BACKEND / arquivo).read_text(encoding="utf-8")
