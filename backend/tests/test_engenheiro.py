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


def _engenheiro_sem_arquivos(blocos, lista, Lt=1000.0):
    from core.engenheiro.servico import Engenheiro

    e = Engenheiro.__new__(Engenheiro)
    e.L, e.blocos, e.lista, e._lock, e.ativo = Lt, blocos, lista, threading.RLock(), True
    e._dadas, e._audios, e._s_anterior, e.versao = {}, {}, None, 0
    e.contagem = {"avisosPelaVoz": 0, "avisosSoNaJanela": 0}
    e._registrar = lambda linha: None
    return e


def test_a_reserva_do_bloco_comeca_no_primeiro_aviso_pela_voz():
    bloco = {"trecho": "C02", "inicio": 0.0, "fim": 330.0}
    item = {"k": 1, "trecho": "C02", "voz": True, "bloco": [0.0, 330.0], "sFala": 180.0}
    e = _engenheiro_sem_arquivos([bloco], {"C02": item})
    assert e.reserva(50.0) == pytest.approx(180.0)        # o feedback tem de acabar antes do aviso
    assert e.reserva(200.0) == pytest.approx(330.0)       # depois do aviso, ate o fim do bloco
    assert e.reserva(400.0) is None                       # fora do bloco: o feedback espera
    item["voz"] = False
    assert e.reserva(50.0) == pytest.approx(330.0)        # o aviso so na janela nao reserva


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


def test_a_dica_dada_antes_da_linha_espera_o_carro_passar_a_acao():
    item = {"k": 0, "trecho": "C01", "frase": "freie na placa de 100", "fala": "Curva 1: freie na placa de 100.",
            "voz": False, "porqueSoNaJanela": "teste", "sFala": 950.0, "sAcao": 50.0, "sDito": 50.0, "acao": "freie",
            "causa": "frenagem cedo", "perdaS": 0.2, "duracaoS": 3.0, "refFreada": 50.0}
    e = _engenheiro_sem_arquivos([], {"C01": item})
    for s in (900.0, 940.0, 960.0):
        e.no_quadro(s, 200.0, True, False, False)
    assert "C01" in e._dadas and e._dadas["C01"]["acaoPassada"] is False
    for s in (990.0, 10.0, 40.0):                  # a linha: a acao ainda nao passou
        e.no_quadro(s, 200.0, True, False, False)
    assert e._dadas["C01"]["acaoPassada"] is False
    e.no_quadro(60.0, 200.0, True, False, False)
    assert e._dadas["C01"]["acaoPassada"] is True  # agora a linha seguinte confere


def test_o_aviso_pela_voz_tem_prioridade_e_nunca_fala_por_cima():
    item = {"k": 0, "trecho": "C04", "frase": "freie na placa de 100", "fala": "Curva 4: freie na placa de 100.",
            "voz": True, "sFala": 500.0, "sAcao": 700.0, "sDito": 700.0, "acao": "freie", "causa": "frenagem cedo",
            "perdaS": 0.3, "duracaoS": 3.0, "refFreada": 700.0, "bloco": [0.0, 640.0]}

    class _Pronto:
        def done(self):
            return True

        def result(self):
            return (Path("aviso.wav"), 3.0)

    e = _engenheiro_sem_arquivos([], {"C04": item})
    e._audios = {item["fala"]: _Pronto()}
    e.no_quadro(480.0, 216.0, True, False, False)
    aviso = e.no_quadro(505.0, 216.0, True, False, False)          # 60 m/s: 195 m ate a freada, 3,25 s >= 4 s? nao
    assert aviso is None                                           # pouco tempo ate a freada: so na janela
    e._dadas.clear()
    e._s_anterior = 480.0
    aviso = e.no_quadro(505.0, 144.0, True, False, False)          # 40 m/s: 4,9 s ate a freada
    assert aviso is not None and aviso["origem"] == "aviso" and aviso["fala"] == item["fala"]
    e._dadas.clear()
    e._s_anterior = 480.0
    assert e.no_quadro(505.0, 144.0, True, False, True) is None     # outra fala em andamento: nunca por cima
    e._dadas.clear()
    e._s_anterior = 480.0
    assert e.no_quadro(505.0, 144.0, False, False, False) is None   # a volta de saida dos boxes


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
    assert "VERSION = 0.7.0" in manifesto and "FUNCTION_MAIN = engenheiro" in manifesto


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
