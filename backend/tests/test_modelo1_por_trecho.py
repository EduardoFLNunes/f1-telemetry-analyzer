"""Pedido 49 (ADR 0030): o Modelo 1 por trecho, com dados sinteticos."""

import itertools
from dataclasses import dataclass

import numpy as np
import pytest

from ml.pista_teste import por_trecho as PT


@dataclass(frozen=True)
class Curva:
    index: int
    start_s: float
    apex_s: float
    end_s: float

    @property
    def label(self):
        return f"C{self.index + 1:02d}-esq"


COMPRIMENTO = 1000.0
PASSO = 2.0
S = np.arange(0.0, COMPRIMENTO, PASSO)


def _curvas():
    return [Curva(0, 100.0, 160.0, 200.0), Curva(1, 400.0, 450.0, 500.0), Curva(2, 700.0, 740.0, 780.0)]


# ------------------------------------------------------------ trechos ---

def test_os_trechos_cobrem_a_volta_sem_buraco_e_sem_sobreposicao():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    assert [t.nome for t in lista] == ["C01", "C02", "C03", PT.NOME_DA_CHEGADA]
    assert lista[0].inicio_s == 0.0 and lista[-1].fim_s == COMPRIMENTO
    for a, b in zip(lista[:-1], lista[1:]):
        assert a.fim_s == b.inicio_s
    # Cada ponto da grade fica em exatamente um trecho.
    contagem = np.zeros(len(S), int)
    for t in lista:
        contagem[t.indices(S, COMPRIMENTO)] += 1
    assert (contagem == 1).all()
    assert lista[-1].tem_curva is False and lista[-1].apice_s is None
    assert lista[1].pontos_de_linha() == {"entrada": 400.0, "apice": 450.0, "saida": 500.0}
    assert lista[-1].pontos_de_linha() == {"entrada": 780.0, "apice": 890.0, "saida": 1000.0}


def test_buraco_sobreposicao_e_curva_que_cruza_a_linha_sao_recusados():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    with pytest.raises(ValueError):
        PT.conferir_cobertura([lista[0], lista[2], lista[3]], COMPRIMENTO)
    sobreposto = PT.Trecho("X", 150.0, 500.0, 400.0, 450.0, 500.0, True)
    with pytest.raises(ValueError):
        PT.conferir_cobertura([lista[0], sobreposto, lista[2], lista[3]], COMPRIMENTO)
    with pytest.raises(ValueError):
        PT.trechos([Curva(0, 990.0, 995.0, 1010.0)], COMPRIMENTO)


def test_a_soma_dos_trechos_bate_com_o_tempo_da_volta():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    rng = np.random.default_rng(1)
    velocidade = 30.0 + 20.0 * rng.random(len(S))
    elapsed = np.r_[0.0, np.cumsum(PASSO / velocidade)[:-1]]
    volta = float(elapsed[-1] + PASSO / velocidade[-1])
    tempos = PT.tempos_por_trecho(elapsed, S, volta, lista)
    assert len(tempos) == 4 and (tempos > 0).all()
    assert abs(PT.conferir_soma(tempos, volta)) < 1e-12
    # O primeiro trecho vai da linha ao fim da C01: o tempo no ponto s = 200.
    assert tempos[0] == pytest.approx(elapsed[100])
    with pytest.raises(ValueError):
        PT.conferir_soma(tempos, volta + 0.006)
    assert PT.conferir_soma(tempos, volta + 0.004) == pytest.approx(-0.004)


# ------------------------------------------------------- a regra A.3 ---

def _p_ingenuo(a, b):
    x = np.r_[a, b]
    obs = abs(np.mean(a) - np.mean(b))
    cont = tot = 0
    for idx in itertools.combinations(range(len(x)), len(a)):
        m = np.zeros(len(x), bool)
        m[list(idx)] = True
        cont += abs(x[m].mean() - x[~m].mean()) >= obs - 1e-12
        tot += 1
    return cont / tot


def test_a_permutacao_exata_da_diferenca_das_medias():
    a = np.arange(7) * 0.01 + 1.0
    b = np.arange(7) * 0.01
    assert PT.permutacao_exata(a, b) == pytest.approx(2 / 3432)
    b4 = np.array([0.0, 0.01, 0.02, 0.03])
    assert PT.permutacao_exata(a, b4) == pytest.approx(_p_ingenuo(a, b4))
    assert PT.permutacao_exata(a, b4) <= 2 / 330
    assert PT.permutacao_exata(np.ones(7), np.ones(4)) == 1.0
    rng = np.random.default_rng(3)
    x, y = rng.normal(0, 1, 7), rng.normal(0.3, 1, 7)
    assert PT.permutacao_exata(x, y) == pytest.approx(_p_ingenuo(x, y))


def test_o_bootstrap_e_fixo_pela_semente_e_cobre_a_diferenca():
    a = np.array([10.0, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6])
    b = a + 1.0
    d1 = PT.bootstrap_mediana(a, b)
    d2 = PT.bootstrap_mediana(a, b)
    assert d1 == d2
    assert d1["diferenca_s"] == pytest.approx(-1.0)
    assert d1["ic95_inferior_s"] <= -1.0 <= d1["ic95_superior_s"] < 0


def test_holm_num_caso_conhecido():
    rej = PT.holm([0.01, 0.04, 0.03, 0.005])
    assert rej.tolist() == [True, False, False, True]
    assert PT.holm([0.2, 0.3]).tolist() == [False, False]
    assert PT.holm([0.0005] * 15).all()
    # Com 15 trechos, o piso da diferenca das medianas (0,0117) nunca passaria; o das medias (2/3432) passa.
    assert not PT.holm([0.0117] + [1.0] * 14)[0]
    assert PT.holm([2 / 3432] + [1.0] * 14)[0]


def test_comparar_e_classificar():
    rng = np.random.default_rng(5)
    nomes = ["T1", "T2", "T3"]
    base = rng.normal(10.0, 0.01, (7, 3))
    final = rng.normal(10.0, 0.01, (4, 3))
    x = rng.normal(10.0, 0.01, (7, 3))
    x[:, 0] -= 0.5   # ganho claro no T1
    x[:, 1] += 0.5   # perda clara no T2
    x[:, 2] = base[:, 2]   # igual ao C0 no T3
    a = PT.comparar(x, base, nomes)
    b = PT.comparar(x, final, nomes)
    assert [d["sentido"] for d in a] == ["menor", "maior", "nenhum"]
    assert a[0]["p_permutacao"] == pytest.approx(2 / 3432)
    assert PT.classificar(a, b) == ["ganho", "perda", "empate"]
    # Sem significancia contra o C0 final, nao ha ganho.
    b_sem = [dict(d, sentido="nenhum") for d in b]
    assert PT.classificar(a, b_sem) == ["empate", "empate", "empate"]
    # Sentidos opostos nas duas comparacoes: empate.
    b_oposto = [dict(d, sentido={"menor": "maior", "maior": "menor"}.get(d["sentido"], "nenhum")) for d in b]
    assert PT.classificar(a, b_oposto) == ["empate", "empate", "empate"]


def test_sinais_diferentes_da_mediana_e_da_media_nao_contam():
    # Mediana menor, media maior (um valor alto puxa a media): sem sentido.
    x = np.array([[1.0], [1.0], [1.0], [1.0], [9.0], [9.0], [9.0]])
    y = np.array([[2.0]] * 7)
    d = PT.comparar(x, y, ["T"])[0]
    assert d["diferenca_s"] < 0 < d["diferenca_das_medias_s"]
    assert d["sentido"] == "nenhum"


# ------------------------------------------------------ medidas A.5 ---

def _traco():
    """Uma volta sintetica na grade de 2 m, com a curva C01 de 100 a 200 m (apice 160)."""
    freio = np.zeros(len(S))
    freio[(S >= 104) & (S <= 150)] = 0.8
    freio[S == 120] = 0.95
    vel = 250.0 - np.clip(160.0 - np.abs(S - 160.0), 0, None)
    marcha = np.full(len(S), 6.0)
    marcha[(S >= 120) & (S < 140)] = 5.0
    marcha[(S >= 140) & (S < 180)] = 4.0
    marcha[(S >= 180) & (S < 190)] = 5.0
    acel = np.ones(len(S))
    acel[(S >= 98) & (S < 170)] = 0.0
    acel[(S >= 170) & (S < 186)] = 0.5
    return {"brake": freio, "speed_kmh": vel, "gear": marcha, "throttle": acel}


def test_medidas_da_execucao_num_traco_sintetico():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    m = PT.medidas_da_execucao(_traco(), S, COMPRIMENTO, lista[0])
    assert m["frenagem_inicio_s"] == 104.0
    assert m["freio_maximo"] == pytest.approx(0.95)
    assert m["frenagem_ate_o_apice_m"] == pytest.approx(56.0)
    assert m["velocidade_minima_kmh"] == pytest.approx(90.0) and m["velocidade_minima_s"] == 160.0
    assert m["marcha_minima"] == 4
    assert m["trocas"] == [{"s": 120.0, "de": 6, "para": 5}, {"s": 140.0, "de": 5, "para": 4},
                           {"s": 180.0, "de": 4, "para": 5}, {"s": 190.0, "de": 5, "para": 6}]
    assert m["retomada_s"] == 186.0


def test_medidas_sem_frenagem_sem_retomada_e_canal_que_falta():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    tr = _traco()
    tr["brake"] = np.zeros(len(S))
    tr["throttle"] = np.where(S >= 190, 0.5, 1.0)
    m = PT.medidas_da_execucao(tr, S, COMPRIMENTO, lista[0])
    assert m["frenagem_inicio_s"] is None and m["retomada_s"] is None
    sem = PT.medidas_da_execucao({"brake": None, "speed_kmh": tr["speed_kmh"], "gear": None, "throttle": None},
                                 S, COMPRIMENTO, lista[0])
    assert sem["frenagem_inicio_s"] == "nao gravado" and sem["marcha_minima"] == "nao gravado"
    assert sem["retomada_s"] == "nao gravado"
    # A frenagem que vem do trecho anterior (freio ja alto no comeco) nao e um inicio neste trecho.
    tr2 = _traco()
    tr2["brake"] = np.where((S >= 190) & (S <= 220), 0.9, 0.0)
    m2 = PT.medidas_da_execucao(tr2, S, COMPRIMENTO, lista[1])
    assert m2["frenagem_inicio_s"] is None
    # Uma frenagem depois do apice nao conta.
    tr3 = _traco()
    tr3["brake"] = np.where((S >= 170) & (S <= 180), 0.9, 0.0)
    assert PT.medidas_da_execucao(tr3, S, COMPRIMENTO, lista[0])["frenagem_inicio_s"] is None
    # O trecho da chegada nao tem apice: a busca vai ate o fim dele, e a distancia e "sem curva".
    tr4 = _traco()
    tr4["brake"] = np.where((S >= 850) & (S <= 870), 0.7, 0.0)
    m4 = PT.medidas_da_execucao(tr4, S, COMPRIMENTO, lista[-1])
    assert m4["frenagem_inicio_s"] == 850.0 and m4["frenagem_ate_o_apice_m"] == "sem curva"


def test_resumir_medidas():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    voltas = []
    for k in range(5):
        tr = _traco()
        tr["brake"] = np.roll(tr["brake"], k)
        voltas.append(PT.medidas_da_execucao(tr, S, COMPRIMENTO, lista[0]))
    r = PT.resumir_medidas(voltas)
    assert r["voltas"] == 5
    assert r["frenagem_inicio_s"]["mediana"] == pytest.approx(108.0)
    assert r["frenagem_inicio_s"]["voltas_com_a_medida"] == 5
    assert r["trocas"]["sequencia_mais_comum"] == ["6->5", "5->4", "4->5", "5->6"]
    assert r["trocas"]["voltas_com_ela"] == 5
    assert r["trocas"]["s_mediano"] == [120.0, 140.0, 180.0, 190.0]
    vazio = PT.resumir_medidas([{"frenagem_inicio_s": None, "retomada_s": None, "trocas": []}] * 2)
    assert vazio["frenagem_inicio_s"]["mediana"] == "sem frenagem no trecho"
    assert vazio["retomada_s"]["mediana"] == "sem retomada no trecho"
    assert vazio["velocidade_minima_kmh"]["mediana"] == "sem dados"


def test_a_leitura_sem_o_neutro_da_troca():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    tr = _traco()
    # 6 -> 0 -> 5 em 118-120 e 5 -> 0 -> 4 em 138-140: o neutro da troca, como o gravador guarda.
    tr["gear"][(S >= 116) & (S < 120)] = 0.0
    tr["gear"][(S >= 136) & (S < 140)] = 0.0
    m = PT.medidas_da_execucao(tr, S, COMPRIMENTO, lista[0])
    assert m["marcha_minima"] == 0
    assert m["marcha_minima_sem_neutro"] == 4
    assert m["trocas_sem_neutro"] == [{"s": 120.0, "de": 6, "para": 5}, {"s": 140.0, "de": 5, "para": 4},
                                      {"s": 180.0, "de": 4, "para": 5}, {"s": 190.0, "de": 5, "para": 6}]
    # Um neutro que atravessa o comeco do trecho: a marcha de antes vem de antes do neutro.
    g = np.full(len(S), 3.0)
    g[(S >= 196) & (S < 204)] = 0.0
    g[S >= 204] = 2.0
    m2 = PT.medidas_da_execucao({"gear": g}, S, COMPRIMENTO, lista[1])
    assert m2["trocas_sem_neutro"] == [{"s": 204.0, "de": 3, "para": 2}]
    assert m2["marcha_minima_sem_neutro"] == 2


# ---------------------------------------------------------- regras A.7 ---

def test_a_rampa_do_freio():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    freio = np.clip((S - 100.0) / 20.0, 0.0, 1.0)
    freio[S > 150] = 0.0
    # 0,10 em 102 m e 0,90 em 118 m.
    assert PT.rampa_do_freio(freio, S, COMPRIMENTO, lista[0]) == pytest.approx(16.0)
    # Com o maximo em 0,5, o alvo e 0,45: de 102 a 109 m.
    assert PT.rampa_do_freio(np.minimum(freio, 0.5), S, COMPRIMENTO, lista[0]) == pytest.approx(7.0)
    # Um degrau: a rampa fica dentro de um passo da grade.
    degrau = np.where((S >= 110) & (S <= 150), 1.0, 0.0)
    assert 0.0 <= PT.rampa_do_freio(degrau, S, COMPRIMENTO, lista[0]) <= PASSO
    assert PT.rampa_do_freio(np.zeros(len(S)), S, COMPRIMENTO, lista[0]) is None


def test_o_limite_de_linha():
    offsets = np.linspace(-1.0, 1.0, 11)
    laterais = np.tile(np.linspace(-3, 3, len(S)), (11, 1)) + offsets[:, None]
    lim = PT.limite_de_linha(laterais, [10, 20])
    assert lim["mediana"] == pytest.approx(laterais[5, [10, 20]])
    assert lim["limite"] == pytest.approx([np.percentile(np.abs(offsets), 90)] * 2)
    acima = PT.acima_do_limite(lim["mediana"], lim["limite"], lim["mediana"] + np.array([0.5, 1.5]))
    assert acima.tolist() == [False, True]


# ------------------------------------------------------- rugosidade ---

def test_a_rugosidade_zero_num_raio_constante_e_maior_serrilhada():
    n = 800
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    raio = 300.0
    xz = np.column_stack([raio * np.cos(ang), raio * np.sin(ang)])
    estacao = ang * raio
    comp = 2 * np.pi * raio
    k = PT.curvatura_de_tres_pontos(xz)
    assert k == pytest.approx(np.full(n, 1 / raio), rel=1e-6)
    lisa = PT.rugosidade(k, estacao, comp)
    assert np.max(lisa) < 1e-9
    serr = xz * (1.0 + 0.002 * (-1) ** np.arange(n))[:, None]
    rug = PT.rugosidade(PT.curvatura_de_tres_pontos(serr), estacao, comp)
    assert np.min(rug) > 1e-4
    # Pelos campos do arquivo: raio constante da zero; raio alternado nao.
    assert np.max(PT.rugosidade(PT.curvatura_do_arquivo(np.full(n, raio), np.ones(n)), estacao, comp)) == 0.0
    alternado = PT.curvatura_do_arquivo(np.where(np.arange(n) % 2, 250.0, 350.0), np.ones(n))
    assert np.min(PT.rugosidade(alternado, estacao, comp)) > 0.0
    assert PT.curvatura_do_arquivo(np.array([np.inf, 0.0, -5.0, 100.0]), np.array([1, 1, 1, -1])).tolist() == [0, 0, 0, -0.01]


def test_a_rugosidade_usa_a_janela_de_20_m():
    n = 1000
    estacao = np.arange(n) * 1.0
    k = np.zeros(n)
    k[500] = 0.01   # um pico so: a segunda diferenca vale 0,01 em 499 e 501 e -0,02 em 500
    rug = PT.rugosidade(k, estacao, float(n))
    assert rug[100] == 0.0
    assert rug[505] > 0 and rug[515] == 0.0
    esperado = np.sqrt((0.01 ** 2 * 2 + 0.02 ** 2) / 21)
    assert rug[500] == pytest.approx(esperado)


def test_media_por_microssetor():
    bordas = np.array([0.0, 10.0, 20.0, 30.0])
    # A estacao 31 m vira 1 m (a linha fecha): fica no primeiro microssetor.
    v = PT.media_por_microssetor(np.array([1.0, 3.0, 5.0, 7.0]), np.array([1.0, 2.0, 15.0, 31.0]), bordas, 30.0)
    assert v[0] == pytest.approx((1 + 3 + 7) / 3) and v[1] == 5.0 and np.isnan(v[2])


# ------------------------------------------------ o JSON da Parte C ---

def _referencia():
    lista = PT.trechos(_curvas(), COMPRIMENTO)
    trechos = []
    for t in lista:
        trechos.append({"trecho": t.nome, "inicio_s": t.inicio_s, "fim_s": t.fim_s, "pontos_de_linha_s": t.pontos_de_linha(),
                        "linha_de_referencia": {"linha": "C0", "s": [0.0, 2.0], "lateral_m": [0.1, 0.2]},
                        "execucao_da_ia": {}, "candidata": None,
                        "provisorio": {"marca": "provisorio, sem confirmacao"}})
    return {"pedido": 49, "adr": "0030", "commit": "x", "geometry_id": "g", "corridor_id": "c", "grade_m": 2.0,
            "gravacoes": [], "arquivos": {}, "trechos": trechos, "aviso": "o coach nao le"}


def test_o_formato_do_json_da_referencia():
    p = _referencia()
    PT.conferir_formato_da_referencia(p, n_trechos=4)
    p["trechos"][1]["candidata"] = {"linha": "C3", "marca": "a validar no jogo"}
    PT.conferir_formato_da_referencia(p, n_trechos=4)
    for estragar in (lambda q: q.pop("geometry_id"),
                     lambda q: q["trechos"].pop(),
                     lambda q: q["trechos"][0].pop("provisorio"),
                     lambda q: q["trechos"][0]["linha_de_referencia"].update(linha="C3"),
                     lambda q: q["trechos"][1].update(candidata={"linha": "C3"}),
                     lambda q: q["trechos"][2]["provisorio"].update(marca="confirmado"),
                     lambda q: q["trechos"][0]["linha_de_referencia"].update(lateral_m=[0.1]),
                     lambda q: q["trechos"][1].update(inicio_s=123.0)):
        q = _referencia()
        estragar(q)
        with pytest.raises(ValueError):
            PT.conferir_formato_da_referencia(q, n_trechos=4)
