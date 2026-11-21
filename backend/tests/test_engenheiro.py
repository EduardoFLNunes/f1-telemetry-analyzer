"""Pedido 52 (ADR 0033): o engenheiro que acompanha a volta, com dados sinteticos.

* o kn5 (um arquivo sintetico) e as placas: a separacao das pecas e o valor pela coluna da textura;
* a projecao e o lado;
* a regra da frase: a janela, o custo, o bonus, o empate e o arredondamento;
* os blocos de voz e a reserva;
* a conferencia da dica;
* a volta lenta (5,0 s);
* a troca da referencia do trecho pela melhor passagem;
* a dica dada antes da linha (a C01) so e conferida depois de o carro passar a acao.
"""
import struct
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

from core.engenheiro import marcos as M
from core.engenheiro import regras as R
from core.kn5.kn5_marcos import Malha, ler_kn5, pecas_ligadas

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "tests"))


# ── o kn5 e as placas ───────────────────────────────────────────────────

def _texto(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack("<I", len(b)) + b


def _kn5_sintetico(caminho: Path, vertices, uvs, indices, textura="DISTMARKERB.DDS", translacao=(0.0, 0.0, 0.0)):
    """Um kn5 minimo: uma textura, um material com a textura difusa, um no com uma malha estatica."""
    out = b"sc6969" + struct.pack("<I", 5)
    out += struct.pack("<I", 1) + struct.pack("<I", 1) + _texto(textura) + struct.pack("<I", 4) + b"DDS "
    out += struct.pack("<I", 1) + _texto("DISTANCEMARKERB") + _texto("ksPerPixel") + b"\0" * 6
    out += struct.pack("<I", 0) + struct.pack("<I", 1) + _texto("txDiffuse") + struct.pack("<I", 0) + _texto(textura)
    m = np.eye(4)
    m[3, :3] = translacao
    out += struct.pack("<I", 1) + _texto("raiz") + struct.pack("<I", 1) + b"\1" + struct.pack("<16f", *m.ravel())
    out += struct.pack("<I", 2) + _texto("distancem001") + struct.pack("<I", 0) + b"\1" + b"\0\1\0"
    out += struct.pack("<I", len(vertices))
    for (x, y, z), (u, v) in zip(vertices, uvs):
        out += struct.pack("<11f", x, y, z, 0.0, 0.0, -1.0, u, v, 1.0, 0.0, 0.0)
    out += struct.pack("<I", len(indices)) + struct.pack(f"<{len(indices)}H", *indices)
    out += struct.pack("<I", 0) + b"\0" * 29
    caminho.write_bytes(out)


def _duas_placas():
    """Duas placas soltas (cada uma: 2 triangulos, os vertices repetidos por face), uma na coluna do 100 e
    outra na do 50, e o verso (a quarta coluna) junto da primeira."""
    vs, uv, idx = [], [], []

    def quad(x0, z0, u0, v0=0.6):
        base = len(vs)
        for (dx, dy), (du, dv) in zip(((0, 0), (1, 0), (1, 1), (0, 1)), ((0, 0), (0.2, 0), (0.2, 0.3), (0, 0.3))):
            vs.append((x0 + dx, dy, z0))
            uv.append((u0 + du, v0 + dv))
        # os vertices repetidos: o segundo triangulo tem copias dos vertices do primeiro
        vs.extend([vs[base], vs[base + 2]])
        uv.extend([uv[base], uv[base + 2]])
        idx.extend([base, base + 1, base + 2, base + 4, base + 5, base + 3])

    quad(0.0, 0.0, 0.27)       # a coluna 2: 100
    quad(0.0, 0.0, 0.77)       # o verso, no mesmo lugar: a mesma peca
    quad(30.0, 0.0, 0.02)      # a coluna 1: 50
    return vs, uv, idx


def test_o_kn5_e_lido_inteiro_com_a_textura_o_uv_e_a_transformacao(tmp_path):
    vs, uv, idx = _duas_placas()
    arq = tmp_path / "pista.kn5"
    _kn5_sintetico(arq, vs, uv, idx, translacao=(100.0, 0.0, -5.0))
    k = ler_kn5(arq, ["DISTMARKERB.DDS"])
    assert k.versao == 5 and list(k.texturas) == ["DISTMARKERB.DDS"]
    m = k.malhas[0]
    assert m.nome == "distancem001" and m.material == "DISTANCEMARKERB" and m.textura == "DISTMARKERB.DDS"
    assert m.posicoes[0] == pytest.approx([100.0, 0.0, -5.0])      # a matriz do no (translacao na ultima linha)
    assert m.uv[0] == pytest.approx([0.27, 0.6])
    assert m.triangulos.shape == (6, 3)


def test_as_placas_sao_separadas_pelas_faces_ligadas_e_o_valor_vem_da_coluna_da_textura(tmp_path):
    vs, uv, idx = _duas_placas()
    arq = tmp_path / "pista.kn5"
    _kn5_sintetico(arq, vs, uv, idx)
    m = ler_kn5(arq).malhas[0]
    pecas = pecas_ligadas(m)
    assert len(pecas) == 2                                   # o verso no mesmo lugar e a mesma placa
    valores = sorted(M.valor_da_placa(m, p, False)[0] for p in pecas)
    assert valores == [50, 100]


def test_no_distmarker_so_a_metade_de_baixo_tem_numero():
    vs = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0), (1, 1, 0), (0, 1, 0)]
    malha = Malha("m", "m", "DISTMARKER", "DISTMARKER.DDS", np.array(vs, float), np.zeros((6, 3)),
                  np.array([(0.55, 0.1)] * 3 + [(0.6, 0.2)] * 3, float), np.array([[0, 1, 2], [3, 4, 5]]))
    assert M.valor_da_placa(malha, np.array([0, 1]), True)[0] is None            # a metade de cima: a moldura
    assert M.valor_da_placa(malha, np.array([0, 1]), False)[0] == 200


# ── a projecao e o lado ─────────────────────────────────────────────────

def test_a_projecao_da_o_s_e_o_lado_pelo_vetor_normal():
    from test_lap_origin import circular_track

    track = circular_track()
    k = 120
    p = np.array([track.x[k], track.z[k]])
    esquerda = p + 5.0 * np.asarray(track.normal[k])
    s, lat = M._projetar(track, [esquerda, p - 5.0 * np.asarray(track.normal[k])])
    assert s[0] == pytest.approx(float(track.s[k]), abs=0.5)
    assert lat[0] == pytest.approx(5.0, abs=0.05) and M._lado(lat[0]) == "esquerda"     # ADR 0003
    assert lat[1] == pytest.approx(-5.0, abs=0.05) and M._lado(lat[1]) == "direita"


# ── a frase ─────────────────────────────────────────────────────────────

L = 1000.0
MARCOS = M.pontos_de_referencia([
    {"id": "M1", "tipo": "posto", "s": 50.0, "lado": "direita"},
    {"id": "M2", "tipo": "placa", "s": 100.0, "valor": 100, "lado": "direita"},
    {"id": "M3", "tipo": "zebra", "s": 200.0, "sFim": 260.0, "lado": "direita"},
])


def test_a_frase_pelo_marco_de_menor_custo_com_o_bonus_da_placa():
    f = R.frase_da_acao("freie", 110.0, MARCOS, L)
    assert f["frase"] == "freie 10 metros depois da placa de 100" and f["sDito"] == 110.0
    assert f["custo"] == pytest.approx(10 - 15)                              # d - o bonus da placa
    assert R.frase_da_acao("freie", 102.0, MARCOS, L)["frase"] == "freie na placa de 100"   # |d| < 5
    f = R.frase_da_acao("freie", 90.0, MARCOS, L)                              # a placa depois: 1,5 x 10 - 15
    assert f["frase"] == "freie 10 metros antes da placa de 100" and f["sDito"] == 90.0
    # o molde curto da voz (emenda de 16/11, item 2): so a frase; o cartao e a janela com "Curva N:"
    assert R.fala_do_aviso("C01", f["frase"]) == "Freie 10 metros antes da placa de 100."
    assert R.escrita_do_aviso("C01", f["frase"]) == "Curva 1: freie 10 metros antes da placa de 100"


def test_a_janela_de_cada_acao_e_o_marco_depois_custa_mais():
    assert R.frase_da_acao("freie", 300.0, MARCOS[:2], L)["comMarco"] is False          # 200 m: fora da janela
    f = R.frase_da_acao("freie", 300.0, MARCOS[:2], L)
    assert f["frase"] == "freie no ponto marcado" and f["sDito"] == 300.0
    f = R.frase_da_acao("freie", 45.0, MARCOS, L)                                      # posto 5 m depois: 7,5
    assert f["frase"] == "freie 5 metros antes do posto de bandeira à direita"
    assert R.frase_da_acao("vire", 185.0, MARCOS[:2], L)["comMarco"] is False           # vire: so 80 m antes


def test_o_bonus_da_zebra_vale_para_virar_e_acelerar():
    f = R.frase_da_acao("vire", 215.0, MARCOS, L)
    assert f["frase"] == "vire 15 metros depois do começo da zebra à direita" and f["custo"] == pytest.approx(5.0)
    f = R.frase_da_acao("acelere", 262.0, MARCOS, L)
    assert f["frase"] == "acelere no fim da zebra à direita"


def test_o_empate_fica_com_o_marco_de_menor_s_e_o_arredondamento_a_5_m():
    dois = M.pontos_de_referencia([{"id": "A", "tipo": "posto", "s": 300.0, "lado": "esquerda"},
                                   {"id": "B", "tipo": "posto", "s": 320.0, "lado": "direita"}])
    # o ponto em 312: A antes (12) e B depois (1,5 x 8 = 12): empate, fica o de menor s
    assert R.frase_da_acao("freie", 312.0, dois, L)["marco"]["id"] == "A"
    assert [R.arredondar_5(x) for x in (7.4, 7.5, 12.4, 12.5, 14.9)] == [5, 10, 10, 15, 15]


def test_a_frase_passa_pela_linha():
    um = M.pontos_de_referencia([{"id": "A", "tipo": "placa", "s": 990.0, "valor": 200, "lado": "direita"}])
    f = R.frase_da_acao("freie", 20.0, um, L)
    assert f["frase"] == "freie 30 metros depois da placa de 200" and f["sDito"] == 20.0


# ── a causa ─────────────────────────────────────────────────────────────

def _medida(freada=None, minima=0.0, tracado=0.0, acelerador=None, partes=None, lado="esquerda"):
    return {"freadaM": freada, "minimaKmh": minima, "tracadoM": tracado, "aceleradorM": acelerador, "saidaKmh": -1.0,
            "lado": lado, "trechos": partes or {"reta": 0.0, "freada": 0.2, "minima": 0.05, "saida": 0.0}}


def test_a_causa_do_engenheiro_vem_da_causa_do_45():
    assert R.causa_do_engenheiro(_medida(freada=-30.0))["causa"] == "frenagem cedo"
    assert R.causa_do_engenheiro(_medida(freada=20.0))["acao"] == "freie"
    assert R.causa_do_engenheiro(_medida(freada=-10.0)) is None                       # abaixo do corte de 15 m
    mp = {"reta": 0.0, "freada": 0.0, "minima": 0.3, "saida": 0.0}
    assert R.causa_do_engenheiro(_medida(minima=-12.0, partes=mp))["causa"] == "mínima baixa"
    c = R.causa_do_engenheiro(_medida(minima=-2.0, tracado=-2.5, partes=mp))         # a direita numa curva a esquerda
    assert c["causa"] == "traçado por fora" and c["acao"] == "vire"
    sp = {"reta": 0.0, "freada": 0.0, "minima": 0.0, "saida": 0.3}
    assert R.causa_do_engenheiro(_medida(acelerador=25.0, partes=sp))["causa"] == "acelerador tarde"
    assert R.causa_do_engenheiro(_medida(acelerador=5.0, partes=sp)) is None


# ── os blocos e o s_fala ────────────────────────────────────────────────

def _volta_de_teste(track, v_ms=50.0):
    """Uma volta a velocidade constante: freia de 380 a 420 m e acelera cheio desde 470 m."""
    s = np.asarray(track.s, float)
    freio = np.where((s >= 380) & (s < 420), 0.8, 0.0)
    acel = np.where((s >= 380) & (s < 470), 0.2, 1.0)
    return {"elapsed": s / v_ms, "velocidade": np.full(s.size, v_ms * 3.6), "freio": freio, "acelerador": acel,
            "lateral": np.zeros(s.size)}


def _trechos_de_teste(track):
    from ml.pista_teste.por_trecho import NOME_DA_CHEGADA, Trecho
    Lt = float(track.length)
    return [Trecho("C01", 0.0, 300.0, 200.0, 250.0, 300.0, True),
            Trecho("C02", 300.0, 500.0, 430.0, 450.0, 500.0, True),
            Trecho(NOME_DA_CHEGADA, 500.0, Lt, 500.0, None, Lt, False)]


def test_o_bloco_vai_da_retomada_anterior_a_1_s_antes_da_primeira_acao():
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    total = float(track.length) / 50.0
    trechos = _trechos_de_teste(track)
    blocos = R.blocos_de_voz(g, total, track, trechos)
    b = next(b for b in blocos if b["trecho"] == "C02")
    assert b["inicio"] == pytest.approx(0.0)              # a retomada da C01: acelerador cheio no trecho todo
    assert b["acao"] == pytest.approx(380.0, abs=2.0)     # a freada vem antes da entrada (430)
    assert b["fim"] == pytest.approx(330.0, abs=2.0)      # 1,0 s a 50 m/s antes da freada
    assert b["duracaoS"] == pytest.approx(330.0 / 50.0, abs=0.05)
    sf = R.s_fala(380.0, 180.0, 3.0, L)                   # 50 m/s x (3 + 1) s
    assert sf == pytest.approx(180.0)
    assert R.dentro_do_bloco(sf, b, float(track.length)) and not R.dentro_do_bloco(340.0, b, float(track.length))


def _engenheiro_sem_arquivos(blocos, lista, Lt=1000.0, falas=None):
    from core.engenheiro.servico import Engenheiro

    e = Engenheiro.__new__(Engenheiro)
    e.L, e.blocos, e.lista, e._lock, e.ativo = Lt, blocos, lista, threading.RLock(), True
    e._audios, e._s_anterior, e.versao = {}, None, 0
    e.contagem = {"fichas": 0, "lembretes": 0, "falasCaladas": 0}
    e.linhas = []
    e._registrar = e.linhas.append
    e.relogio, e.perfil, e.pedacos, e.falas = None, None, [], list(falas or [])
    e._medidas_no_plano, e._voz_liberada = set(), True
    e.retas_longas, e.foco, e.ficha, e.esperando = [], None, None, None
    return e


def test_a_reserva_do_bloco_comeca_na_primeira_fala_planejada():
    """Emenda de 20/11, item 11: a reserva comeca no `s_fala` da primeira fala planejada a frente do carro no bloco
    (de qualquer tipo de aviso)."""
    bloco = {"trecho": "C02", "inicio": 0.0, "fim": 330.0}
    e = _engenheiro_sem_arquivos([bloco], {}, falas=[{"sFala": 180.0, "texto": "Vire na zebra.", "duracaoS": 2.0,
                                                       "trechos": ["C02"], "folgaS": {"C02": 3.0}}])
    assert e.reserva(50.0) == pytest.approx(180.0)        # o feedback tem de acabar antes do aviso
    assert e.reserva(200.0) == pytest.approx(330.0)       # depois da fala, ate o fim do bloco
    assert e.reserva(400.0) is None                       # fora do bloco: o feedback espera
    e.falas = []
    assert e.reserva(50.0) == pytest.approx(330.0)        # sem fala planejada, o bloco inteiro


# ── a conferencia ───────────────────────────────────────────────────────

def test_a_conferencia_da_dica():
    marco = {"nome": "placa de 100", "sMarco": 100.0}
    freie = {"trecho": "C01", "acao": "freie", "sDito": 110.0, "marco": marco}
    assert R.conferir(freie, {"freada": 118.0}, L)["aplicada"] is True
    c = R.conferir(freie, {"freada": 98.0}, L)
    assert c["aplicada"] is False and c["difM"] == pytest.approx(-12.0)
    assert R.texto_da_conferencia(freie, c, L) == "C01: freou 2 m antes da placa de 100; dito: 10 m depois da placa de 100"
    assert R.conferir(freie, {"freada": None}, L)["aplicada"] is None
    vire = {"trecho": "C03", "acao": "vire", "sDito": 434.0, "refMinimaKmh": 140.0}
    assert R.conferir(vire, {"minimaKmh": 135.5}, L)["aplicada"] is True
    assert R.conferir(vire, {"minimaKmh": 134.0}, L)["aplicada"] is False
    acelere = {"trecho": "C04", "acao": "acelere", "sDito": 995.0}
    assert R.conferir(acelere, {"retomada": 4.0}, L)["aplicada"] is True             # pela linha: 9 m
    assert R.conferir(acelere, {"retomada": 6.0}, L)["aplicada"] is False


# ── a referencia do trecho ──────────────────────────────────────────────

def test_a_referencia_do_trecho_vira_a_melhor_passagem_quando_ela_e_mais_rapida():
    from core.engenheiro.servico import Engenheiro
    from ml.pista_teste.por_trecho import Trecho

    e = Engenheiro.__new__(Engenheiro)
    e.trechos = [Trecho("C01", 0.0, 300.0, 200.0, 250.0, 300.0, True)]
    e.tempos_modelo = np.array([6.40])
    e.modelo = {"grade": {"g": "modelo"}, "tempoS": 84.55, "origem": "volta_do_modelo", "rotulo": "volta de referência"}
    e.melhores = {}
    assert e.referencia_do_trecho(0)["origem"] == "volta_do_modelo"
    e.melhores = {"C01": {"tempoS": 6.45, "grade": {"g": "minha"}, "total": 86.5, "origem": "volta 3"}}
    assert e.referencia_do_trecho(0)["origem"] == "volta_do_modelo"               # mais lenta que o modelo
    e.melhores["C01"]["tempoS"] = 6.35
    r = e.referencia_do_trecho(0)
    assert r["origem"] == "melhor_passagem" and r["grade"] == {"g": "minha"} and r["tempoDoTrechoS"] == 6.35


# ── a volta lenta ───────────────────────────────────────────────────────

def test_a_volta_lenta_e_5_s_atras_da_melhor_da_sessao_e_fica_ate_a_linha(tmp_path):
    from core.radio.analise import Pista
    from core.radio.servico import RadioDoEngenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    radio = RadioDoEngenheiro(tmp_path, lambda: None, lambda: None, lambda: None, lambda: {}, lambda: None,
                              engenheiro=False)
    radio._geometria = Pista(track=track, segmentos=[])
    s = np.asarray(track.s, float)
    radio._voltas_da_sessao = [{"volta": 3, "tempoS": float(track.length) / 50.0, "grade": {"elapsed": s / 50.0}}]
    radio._melhor_volta = 3
    pos = {"volta": 5, "s": 500.0, "tempoDaVolta": 500.0 / 50.0 + 4.9, "desdeALinha": True}
    radio._acompanhar_a_volta_lenta(pos)
    assert radio._lenta["lenta"] is False
    pos["tempoDaVolta"] = 500.0 / 50.0 + 5.0
    radio._acompanhar_a_volta_lenta(pos)
    assert radio._lenta["lenta"] is True
    pos.update(s=600.0, tempoDaVolta=600.0 / 50.0 + 1.0)                          # recuperou, mas a volta ja foi lenta
    radio._acompanhar_a_volta_lenta(pos)
    assert radio._lenta["lenta"] is True
    radio._acompanhar_a_volta_lenta({"volta": 6, "s": 10.0, "tempoDaVolta": 0.2, "desdeALinha": True})
    assert radio._lenta["lenta"] is False                                         # a volta seguinte comeca rapida
    radio._acompanhar_a_volta_lenta({"volta": 7, "s": 10.0, "tempoDaVolta": 0.2, "desdeALinha": False})
    assert radio._lenta["lenta"] is True and radio._lenta["motivo"] == "volta de saída dos boxes"


def test_os_arquivos_do_engenheiro_vao_no_instalador():
    pacote = (BACKEND.parent / "desktop" / "package.json").read_text(encoding="utf-8")
    assert '"*.marcos.json"' in pacote and '"*.ruido_por_trecho.json"' in pacote
    assert '"version": "0.9.0-engenheiro"' in pacote
    manifesto = (BACKEND.parent / "tools" / "csp_app" / "radio_engenheiro" / "manifest.ini").read_text(encoding="utf-8")
    assert "VERSION = 0.9.0" in manifesto and "FUNCTION_MAIN = engenheiro" in manifesto


# ── as decisoes do Eduardo de 16/11 (ADR 0033, emenda) ─────────────────

def test_a_freada_so_e_buscada_depois_da_saida_do_trecho_anterior():
    """Item 4: um toque de freio entre o apice e a saida da curva anterior nao e a freada da curva."""
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    s = np.asarray(track.s, float)
    g["freio"] = np.where((s >= 270) & (s < 280), 0.5, g["freio"])        # o toque: depois do apice (250) da C01
    total = float(track.length) / 50.0
    trechos = _trechos_de_teste(track)
    assert R.inicio_da_busca_da_freada(trechos, 1) == pytest.approx(300.0)  # a saida da C01
    assert R.inicio_da_busca_da_freada(trechos, 0) == pytest.approx(float(track.length))  # a linha
    assert R.pontos_do_trecho(g, total, track, trechos, 1)["freada"] == pytest.approx(380.0, abs=2.0)
    # a regra antiga (do apice anterior) pegava o toque
    assert R.ponto_de_freada(g["freio"], track, 250.0, 450.0) == pytest.approx(270.0, abs=2.0)


def test_a_pisada_em_andamento_na_saida_do_trecho_anterior_conta_desde_o_comeco():
    """Item 10 (a C10): o freio ja apertado na saida do trecho anterior; a frenagem e onde a pisada comecou."""
    from core.radio.analise import freada_desde
    from test_lap_origin import circular_track

    track = circular_track()
    s = np.asarray(track.s, float)
    freio = np.where((s >= 290) & (s < 330), 0.9, 0.0) + np.where((s >= 360) & (s < 370), 0.6, 0.0)
    assert freada_desde(freio, track, 300.0, 450.0) == pytest.approx(290.0, abs=2.0)    # e nao a segunda pisada (360)
    freio = np.where((s >= 310) & (s < 330), 0.9, 0.0)
    assert freada_desde(freio, track, 300.0, 450.0) == pytest.approx(310.0, abs=2.0)    # sem pisada na saida: a subida


def test_sem_tirar_o_pe_quando_a_referencia_nao_freia_nem_alivia():
    """Item 3: o acelerador em 0,90 ou mais do comeco ao fim do trecho; a frase sem marco e a conferencia."""
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    total = float(track.length) / 50.0
    trechos = _trechos_de_teste(track)
    assert R.pontos_do_trecho(g, total, track, trechos, 0)["semTirarOPe"] is True    # a C01: cheio no trecho todo
    p2 = R.pontos_do_trecho(g, total, track, trechos, 1)
    assert p2["semTirarOPe"] is False and p2["aceleradorMinimo"] == pytest.approx(0.2)
    f = R.frase_sem_tirar_o_pe(200.0, L)
    assert f["frase"] == "sem tirar o pé" and f["comMarco"] is False and f["marco"] is None
    assert R.fala_do_aviso("C13", f["frase"]) == "Sem tirar o pé."
    assert R.escrita_do_aviso("C13", f["frase"]) == "Curva 13: sem tirar o pé"
    item = {"trecho": "C13", "acao": R.SEM_TIRAR_O_PE, "sDito": 200.0}
    c = R.conferir(item, {"semTirarOPe": True, "aceleradorMinimo": 0.97}, L)
    assert c["aplicada"] is True and R.texto_da_conferencia(item, c, L) == "C13: sem tirar o pé"
    c = R.conferir(item, {"semTirarOPe": False, "aceleradorMinimo": 0.62}, L)
    assert c["aplicada"] is False and R.texto_da_conferencia(item, c, L) == "C13: tirou o pé (acelerador a 62%)"


class _EngDosBlocos:
    """Dois blocos: um curto (0 a 300 m) e a reta longa (400 a 900 m); a reserva e o fim do bloco."""

    def __init__(self):
        self.curto = {"inicio": 0.0, "fim": 300.0}
        self.longo = {"inicio": 400.0, "fim": 900.0}

    def bloco_em(self, s):
        return self.curto if 0.0 <= s <= 300.0 else self.longo if 400.0 <= s <= 900.0 else None

    def reta_longa(self, bloco):
        return bloco is self.longo

    def reserva(self, s):
        b = self.bloco_em(s)
        return None if b is None else b["fim"]

    def tempo_entre(self, s1, s2, v_kmh=None):
        return ((s2 - s1) % 1000.0) / 50.0           # o perfil: 50 m/s

    def _registrar(self, linha):
        self.linhas = getattr(self, "linhas", []) + [linha]


def _radio_com_variantes(tmp_path, s_ao_nascer):
    from core.radio.servico import RadioDoEngenheiro

    eng = _EngDosBlocos()
    pos = {"s": s_ao_nascer}
    radio = RadioDoEngenheiro(tmp_path, lambda: None, lambda: dict(pos), lambda: None, lambda: {}, lambda: None,
                              falar=lambda texto, destino: 2.0, engenheiro=False)
    radio._eng = lambda: eng
    radio._velocidade_kmh = 180.0                      # 50 m/s
    m = radio._nova({"origem": "coach", "fala": "x", "falas": [], "falaMaxS": 7.3})
    m["_futuro"].result(timeout=10)
    m["_futuro"] = None
    m["_variantes"] = [(0, Path("a.wav"), 5.0, "Curva 7: 8 décimos atrás. Freou 39 metros antes da referência."),
                       (1, Path("b.wav"), 2.5, "Curva 7: 8 décimos atrás.")]
    radio._pendentes.append(m)
    return radio, eng, m, pos


def test_o_feedback_espera_o_bloco_em_que_cabe_a_variante_com_a_causa(tmp_path):
    """Item 1: num bloco curto em que so cabe a variante sem a causa, a mensagem espera; num bloco em que a
    variante com a causa cabe, sai ela."""
    radio, eng, m, pos = _radio_com_variantes(tmp_path, 350.0)       # nasce fora dos blocos
    L = 1000.0
    radio._acompanhar_as_retas_longas(eng, 150.0)
    assert radio._escolher_a_variante(m, eng, 150.0, L, 0.0) is False          # 150 m / 50 - 0,3 = 2,7 s: so a curta
    assert radio._escolher_a_variante(m, eng, 0.0, L, 0.0) is True             # 5,7 s: a com a causa (5,0 s) cabe
    assert m["_falaEscolhida"] == 0 and "Freou" in m["fala"]


def test_na_primeira_reta_longa_sai_a_mais_completa_que_couber(tmp_path):
    """Item 1: a variante com a causa nao cabe nem na primeira reta longa depois de nascer: sai a mais completa
    que couber, e a mensagem nao espera mais."""
    radio, eng, m, pos = _radio_com_variantes(tmp_path, 350.0)
    L = 1000.0
    radio._acompanhar_as_retas_longas(eng, 450.0)                              # entrou na reta longa
    assert m["_retaLongaDepoisDeNascer"] is True
    assert radio._escolher_a_variante(m, eng, 750.0, L, 0.0) is True           # 3,0 s ate a reserva
    assert m["_falaEscolhida"] == 1 and m["_saiuNaRegra"].startswith("a mais completa que coube, depois")


def test_a_reta_longa_em_que_a_mensagem_nasce_nao_conta(tmp_path):
    radio, eng, m, pos = _radio_com_variantes(tmp_path, 700.0)       # nasce dentro da reta longa
    L = 1000.0
    radio._acompanhar_as_retas_longas(eng, 750.0)
    assert m["_retaLongaDepoisDeNascer"] is False
    assert radio._escolher_a_variante(m, eng, 750.0, L, 0.0) is False          # 3,0 s: espera a com a causa
    for s in (950.0, 100.0, 350.0, 420.0):                                     # sai, passa o curto, entra de novo
        radio._acompanhar_as_retas_longas(eng, s)
    assert m["_retaLongaDepoisDeNascer"] is True


def test_o_aviso_e_falado_sem_a_vinheta(tmp_path):
    from core.radio.servico import RadioDoEngenheiro

    chamadas = []

    def falar(texto, destino, vinheta_antes=True):
        chamadas.append((texto, vinheta_antes))
        Path(destino).write_bytes(b"RIFF")
        return 2.4

    radio = RadioDoEngenheiro(tmp_path, lambda: None, lambda: None, lambda: None, lambda: {}, lambda: None,
                              falar=falar, engenheiro=False)
    arquivo, dur = radio._falar_o_aviso("Freie na placa de 50.").result(timeout=10)
    assert chamadas == [("Freie na placa de 50.", False)] and dur == pytest.approx(2.4)


# ── as decisoes do Eduardo de 20/11 (ADR 0033, emenda): o plano das falas ──

def _pista_do_plano():
    """A pista circular (L = 1256,6 m) a 50 m/s: um alivio na C01 (180 a 260 m) e a frenagem da C02 (380 a 420 m).
    Os pedacos livres: 260 a 378 m e 470 a 178 m (atravessa a linha)."""
    from core.engenheiro import plano as P
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    s = np.asarray(track.s, float)
    g["acelerador"] = np.where((s >= 180) & (s < 260), 0.5, g["acelerador"])
    total = float(track.length) / 50.0
    perfil = P.Perfil(g, total, track, "teste")
    return track, g, perfil, P.pedacos_livres(g, track), _trechos_de_teste(track)


def test_os_pedacos_livres_formam_um_laco():
    track, g, perfil, pedacos, _ = _pista_do_plano()
    assert len(pedacos) == 2
    a, b = sorted(pedacos, key=lambda p: p["sIni"])
    assert a["sIni"] == pytest.approx(260.0, abs=2.5) and a["sFim"] == pytest.approx(378.0, abs=2.5)
    assert b["sIni"] == pytest.approx(470.0, abs=2.5) and b["sFim"] == pytest.approx(178.0, abs=2.5)   # pela linha


def test_a_acao_do_piloto_em_cada_tipo_de_aviso():
    from core.engenheiro import plano as P

    track, g, perfil, pedacos, trechos = _pista_do_plano()
    assert P.acao_do_piloto(g, track, trechos, 1, "freie")[0] == pytest.approx(380.0, abs=2.5)
    s, tipo = P.acao_do_piloto(g, track, trechos, 0, "vire")                   # o alivio em 180 m
    assert s == pytest.approx(180.0, abs=2.5) and tipo == "alívio"
    assert P.acao_do_piloto(g, track, trechos, 0, R.SEM_TIRAR_O_PE) == (200.0, "entrada")
    s, tipo = P.acao_do_piloto(g, track, trechos, 1, "acelere")                # volta ao acelerador cheio em 470 m
    assert s == pytest.approx(470.0, abs=2.5) and tipo == "retomada"
    sem = dict(g, freio=np.zeros_like(g["freio"]), acelerador=np.ones_like(g["acelerador"]))
    assert P.acao_do_piloto(sem, track, trechos, 1, "freie") == (430.0, "entrada")   # sem frenagem nem alivio


def test_o_perfil_vem_da_ultima_volta_que_conta_da_sua_melhor_ou_da_referencia():
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    total = float(track.length) / 50.0
    e = _engenheiro_sem_arquivos([], {})
    e.track, e.L, e.trechos, e.melhores = track, float(track.length), _trechos_de_teste(track), {}
    e.modelo = {"grade": g, "tempoS": total, "origem": "volta_do_modelo", "rotulo": "volta de referência"}
    e.tempos_modelo = R.tempos_dos_trechos(g["elapsed"], total, track, e.trechos)
    e.ultima_conferencia, e.pista, e.ruido_por_trecho, e.inicio_da_freada = None, None, {}, {}
    Engenheiro.nova_sessao(e, "s1", None)
    assert e.perfil.origem == "volta de referência"
    Engenheiro.nova_sessao(e, "s1", {"grade": g, "tempoS": total})
    assert e.perfil.origem == "sua melhor volta"
    versao = e.versao
    Engenheiro.na_linha(e, 5, g, total, conta=True)                 # o perfil e o plano refeitos depois da volta
    assert e.perfil.origem == "volta 5 da sessão" and e.versao > versao
    assert any(x["tipo"] == "volta" and x["volta"] == 5 for x in e.linhas)
    Engenheiro.na_linha(e, 6, g, total, conta=False)                 # a volta que nao conta nao muda o perfil
    assert e.perfil.origem == "volta 5 da sessão"


def test_a_folga_de_3_s_vale_contra_o_mais_cedo_entre_a_acao_e_o_ponto_dito():
    from core.engenheiro import plano as P

    track, g, perfil, pedacos, _ = _pista_do_plano()
    assert P.ponto_limite(perfil, 380.0, 390.0) == 380.0         # a acao vem antes
    assert P.ponto_limite(perfil, 380.0, 350.0) == 350.0         # o ponto dito vem antes
    c = P.candidatos(perfil, pedacos, 350.0)[0]                    # o ponto dentro do pedaco 260-378: acaba nele
    assert c["relFim"] == 0.0 and c["relIni"] == pytest.approx(-90.0 / 50.0, abs=0.06)
    assert not P.cabe_sozinha(c, 0.5)                              # 1,8 s de pedaco < 3,0 + 0,1 + 0,5


def test_os_tres_moldes_da_fala():
    from core.engenheiro import plano as P

    placa = {"tipo": "placa", "valor": 100, "nome": "placa de 100"}
    zebra = {"tipo": "zebra", "nome": "começo da zebra à direita"}
    a = "freie 10 metros depois da placa de 100"
    assert P.frase_falada("freie", placa, 10.0, "a", a) == a
    assert P.frase_falada("freie", placa, 10.0, "b", a) == "freie 10 depois do 100"
    assert P.frase_falada("freie", placa, 10.0, "c", a) == "freie no 100, mais 10"
    assert P.frase_falada("freie", placa, -12.0, "c", a) == "freie no 100, menos 10"
    assert P.frase_falada("freie", placa, 2.0, "b", a) == "freie no 100"
    assert P.frase_falada("vire", zebra, 5.0, "b", "x") == "vire 5 depois do começo da zebra à direita"
    assert P.frase_falada("vire", zebra, 5.0, "c", "x") == "vire no começo da zebra à direita, mais 5"
    assert P.frase_falada(R.SEM_TIRAR_O_PE, None, None, "c", "sem tirar o pé") == "sem tirar o pé"


def test_o_molde_padrao_e_o_b_da_escolha_de_20_11():
    """ADR 0033, a decisao de 20/11 sobre o molde: o (b) e o padrao, sem `AT_ENGENHEIRO_MOLDE`."""
    import inspect

    from core.engenheiro import plano as P
    from core.engenheiro.servico import Engenheiro

    assert P.MOLDE_PADRAO == "b" and P.MOLDE_PADRAO in P.MOLDES
    fonte = inspect.getsource(Engenheiro.__init__)
    assert 'os.environ.get("AT_ENGENHEIRO_MOLDE") or P.MOLDE_PADRAO' in fonte
    assert "else P.MOLDE_PADRAO" in fonte


def test_o_aviso_corta_o_feedback_e_ele_volta_numa_reta_longa_seguinte(tmp_path):
    """Emenda de 20/11, item 1: a fala do aviso corta o feedback em andamento; o corte vai ao registro; o feedback
    volta a fila e so sai numa reta longa seguinte. O backend nao entrega o aviso (quem toca e o app do jogo)."""
    radio, eng, m, pos = _radio_com_variantes(tmp_path, 350.0)
    variantes = list(m["_variantes"])
    entregue = radio._pendentes.popleft()
    entregue["_arquivoPronto"] = "a.wav"
    entregue["fala"] = m["_variantes"][0][3]
    radio._entregar(entregue, 10.0, {"s": 420.0})
    assert radio._ultima_entregue is not None and radio._ocupado_ate > 10.0
    fala = {"texto": "Quatro: freie no 100. Cinco: sem tirar o pé.", "duracaoS": 3.4, "trechos": ["C04", "C05"]}
    entregues = len(radio._entregues)
    radio._cortar_o_feedback(eng, fala, 11.0, 470.0)
    assert eng.linhas[-1]["tipo"] == "corte" and eng.linhas[-1]["pelaFala"] == fala["texto"]
    assert len(radio._entregues) == entregues                         # o aviso nao entra na fila do radio
    refeita = radio._pendentes[0]
    assert refeita["_soNaRetaLonga"] and refeita["origem"] == "coach"
    refeita["_futuro"].result(timeout=10)
    refeita["_futuro"] = None
    refeita["_variantes"] = variantes
    pos["s"] = 470.0
    assert radio._escolher_a_variante(refeita, eng, 470.0, 1000.0, 12.0) is False   # na mesma reta: nao volta
    for s in (950.0, 100.0, 350.0, 420.0):                                          # sai e entra numa reta longa
        radio._acompanhar_as_retas_longas(eng, s)
    assert radio._escolher_a_variante(refeita, eng, 420.0, 1000.0, 20.0) is True


def test_a_reserva_usa_o_tempo_do_perfil_e_nao_a_velocidade_do_momento():
    from core.engenheiro import plano as P
    from test_lap_origin import circular_track

    track = circular_track()
    g = _volta_de_teste(track)
    s = np.asarray(track.s, float)
    g["elapsed"] = np.where(s < 600, s / 40.0, 600 / 40.0 + (s - 600) / 70.0)      # acelera de 40 para 70 m/s
    total = float(g["elapsed"][-1] + track.step / 70.0)
    e = _engenheiro_sem_arquivos([], {}, Lt=float(track.length))
    e.perfil = P.Perfil(g, total, track, "teste")
    assert e.tempo_entre(400.0, 800.0, 144.0) == pytest.approx(200 / 40.0 + 200 / 70.0, abs=0.05)
    e.perfil = None
    assert e.tempo_entre(400.0, 800.0, 144.0) == pytest.approx(400 / 40.0)          # sem perfil: a velocidade




# ── as decisoes do Eduardo de 21/11 (ADR 0033, emenda): a curva de foco ──

PLACAS_DA_C02 = [{"id": "P1", "tipo": "placa", "s": 340.0, "valor": 100, "lado": "direita"},
                 {"id": "P2", "tipo": "placa", "s": 400.0, "valor": 50, "lado": "direita"}]


def _futuro(duracao):
    from concurrent.futures import Future

    f = Future()
    f.set_result((Path("x.wav"), duracao))
    return f


def _volta_com_perdas(track, trechos, perdas, freada=380.0):
    """A volta de teste (50 m/s) com `perdas` (s) espalhadas em cada trecho e a frenagem da C02 em `freada`."""
    g = _volta_de_teste(track)
    s = np.asarray(track.s, float)
    extra = np.zeros(s.size)
    for t in trechos:
        if t.nome in perdas:
            extra += perdas[t.nome] * np.clip((s - t.inicio_s) / (t.fim_s - t.inicio_s), 0.0, 1.0)
    g["elapsed"] = s / 50.0 + extra
    g["freio"] = np.where((s >= freada) & (s < freada + 40.0), 0.8, 0.0)
    g["acelerador"] = np.where((s >= freada) & (s < 470.0), 0.2, 1.0)
    return g, float(track.length) / 50.0 + sum(perdas.values())


def _engenheiro_de_teste(track, bipe=True):
    """O engenheiro sem arquivos, com a volta de teste como referencia, as placas da C02, uma reta longa
    (de 1.000 m a 290 m, pela linha) e a voz que mede 3,0 s (a ficha) e 1,0 s (o lembrete)."""
    from core.engenheiro.servico import Engenheiro

    g = _volta_de_teste(track)
    total = float(track.length) / 50.0
    e = _engenheiro_sem_arquivos([], {}, Lt=float(track.length))
    e.track, e.trechos, e.melhores = track, _trechos_de_teste(track), {}
    e.modelo = {"grade": g, "tempoS": total, "origem": "volta_do_modelo", "rotulo": "volta de referência"}
    e.tempos_modelo = R.tempos_dos_trechos(g["elapsed"], total, track, e.trechos)
    e.ultima_conferencia, e.pista, e.inicio_da_freada = None, None, {}
    e.ruido_por_trecho = {t.nome: 0.05 for t in e.trechos}
    e.marcos = {"marcos": PLACAS_DA_C02}
    e.pontos_dos_marcos = M.pontos_de_referencia(PLACAS_DA_C02)
    e.bipe, e.molde, e.motivo = bipe, "b", None
    e._falar = lambda fala: _futuro(1.0 if ":" in fala else 3.0)
    e.blocos = e.retas_longas = [{"trecho": "C02", "inicio": 1000.0, "fim": 290.0, "duracaoS": 10.9}]
    Engenheiro._usar_o_perfil(e, g, total, "volta de referência")
    return e


def test_o_foco_e_a_curva_de_maior_perda_e_troca_depois_de_3_voltas_sem_aplicar():
    """Itens 3 e 4: o foco e a curva de maior perda acima do ruido; sem aplicar em 3 voltas que contam, ele vai
    para a curva seguinte em perda; a curva que saiu pode voltar."""
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    e = _engenheiro_de_teste(track)
    cedo, total = _volta_com_perdas(track, e.trechos, {"C01": 0.10, "C02": 0.30}, freada=340.0)   # 40 m antes
    Engenheiro.na_linha(e, 1, cedo, total, conta=True)
    assert e.foco["trecho"] == "C02" and e.foco["desdeAVolta"] == 1 and e.foco["voltasEmFoco"] == 0
    assert [x for x in e.linhas if x["tipo"] == "foco"][-1]["trecho"] == "C02"
    for volta in (2, 3):
        conf = Engenheiro.na_linha(e, volta, cedo, total, conta=True)
        assert conf["aplicada"] is False and e.foco["trecho"] == "C02"
    assert conf["texto"] == "Curva 2: freou 40 m antes do ponto"
    Engenheiro.na_linha(e, 4, cedo, total, conta=True)                    # a terceira volta sem aplicar
    saida = [x for x in e.linhas if x["tipo"] == "foco" and x.get("saiu")][-1]
    assert saida["saiu"] == "C02" and saida["motivo"] == "3 voltas sem aplicar"
    assert e.foco["trecho"] == "C01" and e.foco["desdeAVolta"] == 4        # a curva seguinte em perda
    Engenheiro.na_linha(e, 5, cedo, total, conta=True)                    # a C01 de pe embaixo: aplicou
    assert e.ultima_conferencia["conferidas"][0]["aplicada"] is True
    assert e.foco["trecho"] == "C02"                                      # a C02 voltou


def test_o_foco_sai_quando_a_conferencia_mostra_que_aplicou():
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    e = _engenheiro_de_teste(track)
    cedo, total = _volta_com_perdas(track, e.trechos, {"C02": 0.30}, freada=340.0)
    Engenheiro.na_linha(e, 1, cedo, total, conta=True)
    no_ponto, total2 = _volta_com_perdas(track, e.trechos, {"C02": 0.30}, freada=384.0)          # 4 m do ponto
    conf = Engenheiro.na_linha(e, 2, no_ponto, total2, conta=True)
    assert conf["aplicada"] is True and conf["texto"] == "Curva 2: freou no ponto"
    assert [x["motivo"] for x in e.linhas if x["tipo"] == "foco" and x.get("saiu")] == ["aplicada na volta 2"]
    assert e.foco is None and e.falas == []                               # sem outra curva acima do ruido: sem foco
    assert Engenheiro.estado_publico(e)["esperando"] == (
        "Esperando uma volta que conte (nenhuma curva acima do ruído na última volta que contou)")
    Engenheiro.na_linha(e, 3, cedo, total, conta=True)                    # a C02 pode voltar na volta seguinte
    assert e.foco["trecho"] == "C02" and e.foco["desdeAVolta"] == 3


def test_o_foco_vem_da_sessao_anterior_e_sem_ela_a_janela_espera_uma_volta(tmp_path):
    """Item 5: o foco com que a ultima sessao com volta que conta terminou; sem a linha `foco` (antes de 21/11), a
    maior perda acima do ruido da ultima volta; sem sessao, "Esperando uma volta que conte" com o motivo."""
    import json

    from core.engenheiro.servico import Engenheiro, foco_do_registro
    from test_lap_origin import circular_track

    ruido = {"C01": 0.05, "C02": 0.05}
    assert foco_do_registro(tmp_path, "2026-11-22_10-00-00_vhe_interlagos", ruido) is None
    antiga = tmp_path / "2026-11-20_19-06-14_vhe_interlagos.engenheiro.jsonl"
    antiga.write_text("\n".join(json.dumps(x) for x in (
        {"tipo": "volta", "volta": 3, "perdas": {"C01": 0.30, "C02": 0.40, "C14->linha": 0.9}},
        {"tipo": "volta", "volta": 4, "perdas": {"C01": 0.60, "C02": 0.40, "C14->linha": 0.9}})), encoding="utf-8")
    sem_volta = tmp_path / "2026-11-21_09-00-00_vhe_interlagos.engenheiro.jsonl"
    sem_volta.write_text(json.dumps({"tipo": "foco", "trecho": "C02"}), encoding="utf-8")   # sem volta que conta
    f = foco_do_registro(tmp_path, "2026-11-22_10-00-00_vhe_interlagos", ruido)
    assert f["trecho"] == "C01" and f["sessao"] == "2026-11-20_19-06-14_vhe_interlagos"      # a ultima linha volta
    nova = tmp_path / "2026-11-21_18-10-46_vhe_interlagos.engenheiro.jsonl"
    nova.write_text("\n".join(json.dumps(x) for x in (
        {"tipo": "foco", "trecho": "C01"}, {"tipo": "volta", "volta": 5, "perdas": {"C01": 0.6}},
        {"tipo": "foco", "trecho": "C02"})), encoding="utf-8")
    assert foco_do_registro(tmp_path, "2026-11-22_10-00-00_vhe_interlagos", ruido)["trecho"] == "C02"
    assert foco_do_registro(tmp_path, "2026-11-21_18-10-46_vhe_interlagos", ruido)["trecho"] == "C01"   # so as de antes
    track = circular_track()
    e = _engenheiro_de_teste(track)
    Engenheiro.nova_sessao(e, "s2", None, {"trecho": "C02", "sessao": "2026-11-21_18-10-46_vhe_interlagos"})
    estado = Engenheiro.estado_publico(e)
    assert estado["foco"]["trecho"] == "C02" and estado["foco"]["origem"] == "sessão 2026-11-21_18-10-46_vhe_interlagos"
    assert estado["esperando"] is None
    Engenheiro.nova_sessao(e, "s3", None, None)
    Engenheiro.na_linha(e, 3, None, None, conta=False, motivo="rodada (perdeu 19,9 s na C13)")
    estado = Engenheiro.estado_publico(e)
    assert estado["foco"] is None
    assert estado["esperando"] == "Esperando uma volta que conte (volta 3: rodada (perdeu 19,9 s na C13))"


def test_a_tecnica_vem_da_melhor_passagem_do_piloto_e_sem_ela_fica_fora():
    """Item 7: "com trail braking" (o freio pisado 10 m ou mais depois da entrada) ou "frenagem em linha reta",
    pela passagem do piloto; sem passagem, a tecnica fica fora da fala e da escrita."""
    from core.engenheiro import ficha as F
    from test_lap_origin import circular_track

    track = circular_track()
    trechos = _trechos_de_teste(track)
    s = np.asarray(track.s, float)
    g = _volta_de_teste(track)                                    # a C02: entrada em 430, freio de 380 a 420
    assert F.tecnica_da_passagem(g, track, trechos, 1) == "frenagem em linha reta"
    trail = dict(g, freio=np.where((s >= 380) & (s < 445), 0.6, 0.0))     # pisado ate 445 (15 m depois da entrada)
    assert F.tecnica_da_passagem(trail, track, trechos, 1) == "com trail braking"
    assert F.tecnica_da_passagem(None, track, trechos, 1) is None
    sem = dict(g, freio=np.zeros_like(g["freio"]))
    assert F.tecnica_da_passagem(sem, track, trechos, 1) is None          # a passagem dele sem frenagem
    ref = {"grade": g, "tempoS": float(track.length) / 50.0}
    pts = M.pontos_de_referencia(PLACAS_DA_C02)
    f = F.ficha_da_curva(1, ref, track, trechos, PLACAS_DA_C02, pts, None)
    assert f["tipo"] == F.FRENAGEM and f["tecnica"] is None
    assert "Freie entre o 100 e o 50." in f["fala"] and "trail" not in f["fala"]
    assert f["escrita"].startswith("Curva 2; freie entre a placa de 100 e a de 50; ")
    assert f["lembrete"] == "Dois: entre o 100 e o 50."
    f = F.ficha_da_curva(1, ref, track, trechos, PLACAS_DA_C02, pts, trail)
    assert "Freie entre o 100 e o 50, com trail braking." in f["fala"] and f["tecnicaDe"] == "sua melhor passagem"
    c01 = F.ficha_da_curva(0, ref, track, trechos, PLACAS_DA_C02, pts, trail)
    assert c01["tipo"] == F.PE_EMBAIXO and c01["tecnica"] == "de pé embaixo" and c01["tecnicaDe"] == "referência"
    assert c01["lembrete"] == "Um: pé embaixo." and "Passe a 180." in c01["fala"] and c01["marca"] is None


def test_o_alivio_so_conta_com_10_m_ou_mais():
    """Item 8: a queda de 2 a 4 m na troca de marcha nao e alivio; a mesma regra vale para o "sem tirar o pe"."""
    from test_lap_origin import circular_track

    track = circular_track()
    s = np.asarray(track.s, float)
    trechos = _trechos_de_teste(track)
    idx = trechos[0].indices(s, float(track.length))
    troca = np.where((s >= 100) & (s < 104), 0.0, 1.0)                    # 4 m: dois pontos da grade
    assert not R.tem_alivio(troca, track, idx) and R.sem_tirar_o_pe(troca, track, trechos[0])
    alivio = np.where((s >= 100) & (s < 112), 0.5, 1.0)                   # 12 m
    assert R.tem_alivio(alivio, track, idx) and not R.sem_tirar_o_pe(alivio, track, trechos[0])
    assert R.maior_alivio_m(alivio, track, idx) == pytest.approx(12.0, abs=2.1)


def test_a_ficha_uma_vez_por_volta_na_reta_longa_com_prioridade_sobre_o_feedback():
    """Item 9: a ficha no pedaco livre que contem o fim da reta longa, 3,0 s antes do fim dele e do ponto da curva,
    o mais tarde possivel; uma vez por volta; a reserva do bloco comeca nela."""
    from core.engenheiro import plano as P
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    Lt = float(track.length)
    e = _engenheiro_de_teste(track)
    cedo, total = _volta_com_perdas(track, e.trechos, {"C02": 0.30}, freada=340.0)
    Engenheiro.na_linha(e, 1, cedo, total, conta=True)
    ficha = next(f for f in e.falas if f["tipo"] == "ficha")
    assert ficha["duracaoS"] == pytest.approx(3.0) and ficha["folgaS"]["C02"] >= P.FOLGA_MINIMA_S - 1e-6
    # o pedaco livre da volta (470 a 338 m, pela linha) acaba na frenagem dele (340): a ficha acaba 3,0 s antes
    fim_da_ficha = (ficha["sFala"] + (P.LATENCIA_NO_JOGO_S + 3.0) * 50.0) % Lt
    assert (338.0 - fim_da_ficha) % Lt == pytest.approx(150.0, abs=6.0)
    assert [f["tipo"] for f in e.falas] == ["ficha"]                     # o lembrete cairia no mesmo pedaco
    assert e.ficha["planoDoLembrete"]["motivo"] == "a ficha já é dita neste pedaço livre"
    assert e.reserva(1100.0) == pytest.approx(ficha["sFala"])            # o feedback acaba antes da ficha
    assert e.reserva(100.0) == pytest.approx(290.0)                      # depois da ficha, o fim do bloco
    ditas = []
    for _volta in range(2):                                              # duas voltas inteiras: uma ficha em cada
        for s in np.arange(0.0, Lt, 20.0):
            ditas += e.no_quadro(float(s), 180.0, True, False)
    assert [f["tipo"] for f in ditas] == ["ficha", "ficha"]
    assert [x["tipo"] for x in e.linhas if x["tipo"] in ("ficha", "lembrete")] == ["ficha", "ficha"]


def test_o_lembrete_com_a_folga_e_o_lembrete_que_nao_cabe():
    """Item 11: o lembrete no pedaco livre logo antes da curva, o mais tarde possivel com a folga de 3,0 s; se nao
    couber, nao ha lembrete; no pedaco da ficha, fica so a ficha."""
    from core.engenheiro import plano as P
    from test_lap_origin import circular_track

    track = circular_track()
    s = np.asarray(track.s, float)
    g = _volta_de_teste(track)
    g["acelerador"] = np.where((s >= 180) & (s < 200), 0.5, g["acelerador"])   # um alivio de 20 m
    perfil = P.Perfil(g, float(track.length) / 50.0, track, "teste")
    pedacos = P.pedacos_livres(g, track)                                       # 200 a 378 m e 470 a 178 m
    reta = {"inicio": 600.0, "fim": 1000.0}
    pf = P.planejar_a_ficha(perfil, pedacos, reta, 380.0, 3.0)
    assert pf["folgaS"] == pytest.approx(3.0 + 202.0 / 50.0, abs=0.1)          # 3,0 s antes do fim do pedaco (178)
    pl = P.planejar_o_lembrete(perfil, pedacos, 380.0, 0.4, pf["pedaco"])
    assert pl["folgaS"] == pytest.approx(3.0, abs=0.05) and pl["pedaco"] != pf["pedaco"]
    assert pl["sFala"] == pytest.approx(380.0 - (3.0 + P.LATENCIA_NO_JOGO_S + 0.4) * 50.0, abs=2.0)
    nao = P.planejar_o_lembrete(perfil, pedacos, 380.0, 1.0, pf["pedaco"])     # 3,0 + 0,1 + 1,0 > 3,56 s
    assert "sFala" not in nao and nao["motivo"] == "o lembrete não cabe no pedaço livre antes da curva"
    assert P.planejar_a_ficha(perfil, pedacos, reta, 380.0, 40.0)["motivo"] == "a ficha não cabe na reta longa"


def test_a_contagem_de_tres_bipes_e_a_falta_dela_nas_curvas_sem_frenagem():
    """Item 12: tres bipes a 0,5 s um do outro pelo perfil, o ultimo no ponto de frenagem da referencia; nas curvas
    de pe embaixo (e com o bipe desligado), nenhum."""
    from core.engenheiro import plano as P
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    e = _engenheiro_de_teste(track)
    assert P.pontos_da_contagem(e.perfil, 380.0) == [pytest.approx(330.0, abs=1.0), pytest.approx(355.0, abs=1.0), 380.0]
    cedo, total = _volta_com_perdas(track, e.trechos, {"C02": 0.30}, freada=340.0)
    Engenheiro.na_linha(e, 1, cedo, total, conta=True)
    assert e.ficha["sBipes"][-1] == pytest.approx(380.0, abs=2.0) and len(e.ficha["sBipes"]) == 3
    e.foco = None
    Engenheiro._novo_foco(e, 0, 1, "teste", None)                        # a C01: de pe embaixo
    Engenheiro._planejar_o_foco(e)
    assert e.ficha["tipo"] == "pé embaixo" and e.ficha["sBipes"] == []
    e2 = _engenheiro_de_teste(track, bipe=False)
    Engenheiro.na_linha(e2, 1, cedo, total, conta=True)
    assert e2.ficha["trecho"] == "C02" and e2.ficha["sBipes"] == []


def test_a_marca_so_na_curva_de_foco():
    """Item 13: a marca no asfalto so na curva de foco (no ponto de frenagem da referencia); a lista da volta nao
    leva marca nem bipe."""
    from core.engenheiro.servico import Engenheiro
    from test_lap_origin import circular_track

    track = circular_track()
    e = _engenheiro_de_teste(track)
    cedo, total = _volta_com_perdas(track, e.trechos, {"C01": 0.10, "C02": 0.30}, freada=340.0)
    Engenheiro.na_linha(e, 1, cedo, total, conta=True)
    estado = Engenheiro.estado_publico(e)
    assert estado["foco"]["trecho"] == "C02" and estado["foco"]["marca"]["x"] is not None
    assert estado["foco"]["sFreada"] == pytest.approx(380.0, abs=2.0)
    assert all("x" not in i and "sBipe" not in i and "sBipes" not in i for i in estado["lista"])


def test_o_app_do_jogo_toca_a_ficha_e_a_contagem_pelo_s_e_mostra_o_foco():
    pasta = BACKEND.parent / "tools" / "csp_app" / "radio_engenheiro"
    lua = (pasta / "radio_engenheiro.lua").read_text(encoding="utf-8")
    assert "function tocarOAviso" in lua and "function acompanharOsAvisos" in lua
    assert "setInterval(acompanharOsAvisos, 0)" in lua                 # a cada quadro, pelo s do carro
    corpo = lua.split("function tocarOAviso", 1)[1].split("\nend", 1)[0]
    assert "estado.atual = nil" in corpo                                # o cartao que estava na tela sai
    assert "foco.sBipes" in lua and "'bipe_agudo.wav'" in lua and "'bipe.wav'" in lua
    assert (pasta / "bipe.wav").exists() and (pasta / "bipe_agudo.wav").exists()
    marca = lua.split("local function desenharAMarca", 1)[1].split("\nend", 1)[0]
    assert "foco.marca" in marca and "d.lista" not in marca            # a marca so na curva de foco
    assert "Esperando uma volta que conte" in lua
