"""Diagnostico da M1 v2 (pedido 48, Parte E), com dados sinteticos."""

from __future__ import annotations

import numpy as np
import pytest

from ml.modelo_carro import diagnostico as DG

DT_FINO = 0.005


# ------------------------------------------------------- bootstrap ---

def test_bootstrap_com_razao_constante_tem_ic_de_largura_zero():
    rng = np.random.default_rng(1)
    lap = np.repeat(np.arange(40), 25)
    sq_ref = rng.uniform(0.5, 2.0, lap.size)
    sq_model = 0.25 * sq_ref                      # skill = 1 - sqrt(0,25) = 0,5 em qualquer reamostragem
    out = DG.bootstrap_por_volta(sq_model, sq_ref, lap, n=2000, seed=48)
    assert out["skill"] == pytest.approx(0.5)
    assert out["p2_5"] == pytest.approx(0.5)
    assert out["p97_5"] == pytest.approx(0.5)
    assert out["voltas"] == 40


def test_bootstrap_bate_com_o_intervalo_do_metodo_delta():
    # 400 voltas, um caso cada: R0 vale 1 e o modelo tem media 0,25 e desvio 0,1.
    rng = np.random.default_rng(7)
    n = 400
    sq_model = rng.normal(0.25, 0.1, n)
    sq_ref = np.ones(n)
    out = DG.bootstrap_por_volta(sq_model, sq_ref, np.arange(n), n=10000, seed=48)
    mean = sq_model.mean()
    se = sq_model.std() / np.sqrt(n)
    half = 1.96 * se / (2.0 * np.sqrt(mean))       # d(1 - sqrt(m))/dm = -1/(2 sqrt(m))
    assert out["skill"] == pytest.approx(1.0 - np.sqrt(mean))
    assert (out["p97_5"] - out["p2_5"]) / 2.0 == pytest.approx(half, rel=0.08)
    assert out["p2_5"] < out["skill"] < out["p97_5"]


# ---------------------------------------------------------- deriva ---

def test_deriva_numa_curva_a_esquerda_em_regime_permanente():
    a, b, t_f, t_r, k = 1.6, 1.36, 1.588, 1.509, 0.304
    vx, R = 30.0, 60.0
    r = vx / R                                       # curva a esquerda: r > 0
    vy = b * r                                       # o eixo traseiro anda reto: deriva atras zero
    delta = np.arctan2(vy + a * r, vx) + 0.02        # a frente vira 0,02 rad a mais que o caminho dela
    steer = -delta / k                               # steer positivo a direita (M0)
    al = DG.deriva_rodas([vx], [vy], [r], [steer], a, b, t_f, t_r, k)[0]
    front, rear = DG.deriva_eixos(al[None])
    assert front[0] == pytest.approx(0.02, abs=1e-3)   # positiva: empurra o carro para a esquerda (para dentro)
    assert rear[0] == pytest.approx(0.0, abs=1e-3)
    # A roda de fora (direita, y < 0) e a de dentro tem quase a mesma deriva; a de fora anda mais rapido.
    assert al[0] != al[1]
    # A traseira escorregando para fora (para a direita, vy menor) da deriva positiva atras.
    al2 = DG.deriva_rodas([vx], [vy - 0.5], [r], [steer], a, b, t_f, t_r, k)[0]
    _, rear2 = DG.deriva_eixos(al2[None])
    assert rear2[0] == pytest.approx(np.arctan(0.5 / vx), abs=2e-3)
    assert rear2[0] > 0


def test_deriva_e_a_mesma_conta_da_fisica_v2():
    from ml.modelo_carro import fisica_v2 as F2
    a, b, t_f, t_r, k = 1.6, 1.36, 1.588, 1.509, 0.304
    rng = np.random.default_rng(3)
    vx, vy, r, st = rng.uniform(10, 70, 50), rng.normal(0, 0.5, 50), rng.normal(0, 0.5, 50), rng.normal(0, 0.3, 50)
    al = DG.deriva_rodas(vx, vy, r, st, a, b, t_f, t_r, k)
    x = np.array([a, a, -b, -b])
    y = np.array([t_f / 2, -t_f / 2, t_r / 2, -t_r / 2])
    d = np.column_stack([-k * st, -k * st, 0 * st, 0 * st])
    exp = d - np.arctan2(vy[:, None] + x * r[:, None], np.maximum(vx, F2.VX_MIN)[:, None] - y * r[:, None])
    assert np.allclose(al, exp)


# ----------------------------------------------------------- atraso ---

def _primeira_ordem(tau: float, ganho: float = 2.0, rampa: float = 0.5):
    """Volante com entradas suaves e a guinada de primeira ordem: dr/dt = (ganho*steer - r)/tau."""
    t = np.arange(0.0, 6.0, 0.0005)
    st = np.zeros_like(t)
    for t0, sign in ((1.0, 1), (3.5, -1)):
        up = (t >= t0) & (t < t0 + rampa)
        st[up] = sign * 0.4 * (1 - np.cos(np.pi * (t[up] - t0) / rampa)) / 2
        hold = (t >= t0 + rampa) & (t < t0 + rampa + 1.0)
        st[hold] = sign * 0.4
        down = (t >= t0 + rampa + 1.0) & (t < t0 + 2 * rampa + 1.0)
        st[down] = sign * 0.4 * (1 + np.cos(np.pi * (t[down] - t0 - rampa - 1.0) / rampa)) / 2
    r = np.zeros_like(t)
    h = t[1] - t[0]
    for i in range(1, t.size):
        r[i] = r[i - 1] + h * (ganho * st[i - 1] - r[i - 1]) / tau
    k = int(round(DT_FINO / h))
    return t[::k], st[::k], r[::k]


def _atraso(st, r):
    lags = np.arange(-20, 81)
    idx = DG.entradas_de_curva(np.abs(st), antes=100, depois=240)
    assert idx.size == 2
    sums = [DG.correlacao_cruzada(np.gradient(st, DT_FINO), np.gradient(r, DT_FINO), lags, slice(i - 50, i + 150)) for i in idx]
    cxy = np.array([s[0] for s in sums])
    cxx = np.array([s[1] for s in sums])
    cyy = np.array([s[2] for s in sums])
    lag, _ = DG.atraso_somado(cxy, cxx, cyy, lags * DT_FINO)
    return lag


@pytest.mark.parametrize("v", [12.5, 25.0, 50.0])
def test_o_estimador_acha_o_atraso_de_relaxacao(v):
    sigma = 0.5                                       # comprimento de relaxacao (m)
    tau = sigma / v
    _, st, r = _primeira_ordem(tau)
    assert _atraso(st, r) == pytest.approx(tau, abs=0.005)


def _efeito_da_grade(tau: float, ganho: float = 2.0) -> float:
    """O atraso medido no sistema rodado na grade de 50 ms menos o do gravado amostrado na mesma grade.

    O modelo da M1 usa a entrada media de k e k+1 e Heun em 5 subpassos; os dois
    caminhos passam pela mesma interpolacao para 5 ms.
    """
    t, st, r = _primeira_ordem(tau)
    step = 10
    tg = t[::step]
    sg, rg = st[::step], r[::step]
    pred = np.empty_like(rg)
    pred[0] = rg[0]
    h = 0.01
    for k in range(tg.size - 1):
        u = 0.5 * (sg[k] + sg[k + 1])
        x = pred[k]
        for _ in range(5):
            k1 = (ganho * u - x) / tau
            k2 = (ganho * u - (x + h * k1)) / tau
            x = x + 0.5 * h * (k1 + k2)
        pred[k + 1] = x
    fino = np.arange(t.size)
    gravado_grade = np.interp(fino, fino[::step], rg)
    previsto = np.interp(fino, fino[::step], pred)
    return _atraso(st, previsto) - _atraso(st, gravado_grade)


@pytest.mark.parametrize("tau", [0.08, 0.15, 0.3])
def test_a_grade_de_50_ms_quase_nao_atrasa_uma_dinamica_lenta(tau):
    assert _efeito_da_grade(tau) == pytest.approx(0.0, abs=0.005)


def test_a_grade_de_50_ms_atrasa_uma_dinamica_rapida_ate_meio_passo():
    # Secao 7.5.1, emenda de 09/11: com tau curto a resposta reflete a entrada do meio do passo.
    assert 0.010 < _efeito_da_grade(0.01) < 0.025
    assert _efeito_da_grade(0.04) > _efeito_da_grade(0.08) > _efeito_da_grade(0.3)


def test_o_gravado_na_grade_tem_o_mesmo_atraso_do_continuo():
    for tau in (0.01, 0.04, 0.15):
        t, st, r = _primeira_ordem(tau)
        fino = np.arange(t.size)
        assert _atraso(st, np.interp(fino, fino[::10], r[::10])) == pytest.approx(_atraso(st, r), abs=0.002)


def test_pico_parabola_acha_o_maximo_entre_amostras():
    lags = np.arange(-10, 11) * 0.005
    true = 0.0123
    values = -(lags - true) ** 2
    assert DG.pico_parabola(values, 0.005, lags[0]) == pytest.approx(true, abs=1e-9)


def test_entrada_de_curva_pede_volante_subindo_por_0_2_s():
    a = np.zeros(1000)
    a[300:400] = np.linspace(0.0, 0.5, 100)          # sobe devagar e passa de 0,1
    a[400:] = 0.5
    a[700:720] = np.linspace(0.0, 0.12, 20)          # passa de 0,1 e para: nao e entrada
    a[720:] = 0.12
    idx = DG.entradas_de_curva(a, antes=100, depois=240)
    assert idx.tolist() == [320]


# --------------------------------------------------------- direcao ---

def test_regressao_acha_o_ganho_nao_linear_da_direcao():
    rng = np.random.default_rng(11)
    n = 6000
    steer = rng.uniform(-0.9, 0.9, n)
    a_y = rng.normal(0, 10, n)
    gains = {"0 a 0,1": 0.304, "0,1 a 0,2": 0.300, "0,2 a 0,4": 0.29, "0,4 a 0,6": 0.26, "acima de 0,6": 0.22}
    bands = DG.faixa(np.abs(steer), DG.FAIXAS_STEER)
    k_ef = np.array([gains[b] for b in bands])
    K = 0.004
    y = k_ef * (-steer) - K * a_y + rng.normal(0, 1e-4, n)
    out = DG.ganho_direcao(y, -steer, -a_y, bands, min_amostras=200)
    for b, g in gains.items():
        assert out["k_ef"][b] == pytest.approx(g, rel=0.01)
    assert out["K"] == pytest.approx(K, rel=0.01)
    hi = DG.media_pesada(out["k_ef"], out["amostras"], ("0,4 a 0,6", "acima de 0,6"))
    assert 0.22 < hi < 0.26


def test_faixa_com_poucas_amostras_fica_de_fora():
    y = np.ones(300)
    out = DG.ganho_direcao(y, np.ones(300), np.zeros(300), np.array(["a"] * 250 + ["b"] * 50), min_amostras=200)
    assert list(out["k_ef"]) == ["a"]


# ------------------------------------------------- partes e skill ---

def test_as_partes_somam_100_e_o_skill_necessario_bate_com_a_conta_a_mao():
    sq_m1 = np.array([1.0, 1.0, 4.0, 4.0, 0.25, 0.25])
    sq_r0 = np.array([4.0, 4.0, 9.0, 9.0, 1.0, 1.0])
    grupos = np.array(["reta", "reta", "curva", "curva", "freada", "freada"])
    p = DG.partes(sq_m1, grupos)
    assert sum(p.values()) == pytest.approx(100.0)
    assert p["curva"] == pytest.approx(100.0 * 8.0 / 10.5)
    curva = grupos == "curva"
    out = DG.skill_necessario(sq_m1, sq_r0, curva, alvo=0.5)
    # A mao: Sigma_R0 = 28; o total precisa de Sigma_M1 = 0,25*28 = 7; o resto tem 2,5; as curvas, 4,5.
    # O skill das curvas: 1 - sqrt(4,5/18) = 0,5.
    assert out["soma_necessaria"] == pytest.approx(4.5)
    assert out["skill_necessario"] == pytest.approx(1.0 - np.sqrt(4.5 / 18.0))
    assert out["skill_atual"] == pytest.approx(1.0 - np.sqrt(8.0 / 18.0))
    # E com as curvas nesse valor, o total chega a 0,50.
    total = 1.0 - np.sqrt((2.5 + 4.5) / 28.0)
    assert total == pytest.approx(0.5)


def test_erro_e_skill_seguem_a_secao_1_7():
    sq = np.array([3.0, 12.0])                       # soma nas 3 grandezas
    assert DG.erro(sq) == pytest.approx(np.sqrt(7.5 / 3.0))
    assert DG.skill(sq / 4.0, sq) == pytest.approx(0.5)


# ------------------------------------------------ acumulo e memoria ---

def test_razao_de_acumulo_vale_1_num_modelo_sem_realimentacao():
    rng = np.random.default_rng(5)
    n, H = 200, 10
    S = np.cumsum(rng.normal(0, 1, (n, H + 1, 3)), axis=1)
    U = rng.normal(0, 1, (n, H, 3))
    g = lambda u: 0.3 * u                            # o incremento nao depende do estado
    open_loop = np.empty_like(S)
    open_loop[:, 0] = S[:, 0]
    for k in range(H):
        open_loop[:, k + 1] = open_loop[:, k] + g(U[:, k])
    um_passo = S[:, :-1] + g(U)                      # a partir do gravado em cada passo
    inc = DG.soma_de_incrementos(S, um_passo)
    assert np.allclose(inc, open_loop)
    sq_ol = np.sum((open_loop[:, H] - S[:, H]) ** 2, axis=1)
    sq_inc = np.sum((inc[:, H] - S[:, H]) ** 2, axis=1)
    assert DG.razao_acumulo(sq_ol, sq_inc) == pytest.approx(1.0)


def test_autocorrelacao_so_usa_pares_do_mesmo_trecho():
    rng = np.random.default_rng(2)
    n = 4000
    e = rng.normal(size=n)
    res = np.empty(n)
    res[0] = e[0]
    for i in range(1, n):
        res[i] = 0.7 * res[i - 1] + np.sqrt(1 - 0.49) * e[i]   # AR(1) com coeficiente 0,7
    trecho = np.repeat(np.arange(40), 100)
    k = np.tile(np.arange(100), 40)
    out = DG.autocorrelacao_pares(res, trecho, k, np.ones(n, bool), [1, 2])
    assert out[1] == pytest.approx(0.7, abs=0.05)
    assert out[2] == pytest.approx(0.49, abs=0.06)
    a, b = DG.pares(n, trecho, k, 1)
    assert np.all(trecho[a] == trecho[b])
    assert a.size == 40 * 99


def test_correlacao_parcial_desconta_a_parte_linear():
    rng = np.random.default_rng(9)
    z = rng.normal(size=(3000, 2))
    x = z[:, 0] + rng.normal(size=3000)
    y = 2.0 * z[:, 0] + rng.normal(size=3000)        # y so depende de x atraves de z
    assert abs(DG.correlacao_parcial(y, x, z)) < 0.05
    assert np.corrcoef(y, x)[0, 1] > 0.5


# --------------------------------------------------------- episodio ---

def test_o_pico_do_episodio_fica_dentro_da_curva_mais_50_m():
    length = 4000.0
    s = np.linspace(0, length, 4001)[:-1]
    vx = np.full(s.size, 30.0)
    vy = np.zeros(s.size)
    vy[1100] = 2.0                                   # dentro da curva (1000 a 1150)
    vy[1190] = 3.0                                   # nos 50 m depois do fim: conta
    vy[1250] = 5.0                                   # 100 m depois do fim: nao conta
    vy[2500] = 9.0                                   # longe: nao conta
    i = DG.indice_do_pico(s, vx, vy, 1000.0, 1150.0, length)
    assert i == 1190
    # A curva que passa da linha de chegada.
    vy2 = np.zeros(s.size)
    vy2[10] = -4.0                                   # o modulo conta
    j = DG.indice_do_pico(s, vx, vy2, 3950.0, 3990.0, length)
    assert j == 10
