"""Pedido 50 (ADR 0031): a linha do projeto. Tudo com dados sinteticos.

* a codificacao nova: as janelas das curvas, os pontos de controle mais densos nelas, a curvatura
  continua, a ida e volta, o raio minimo e a taxa de variacao por trecho e a conferencia do item 4.5;
* a calibracao do medidor com uma linha de fora e a escolha pelo Spearman;
* a regiao de confianca;
* a montagem por trecho e as emendas;
* o veredito da meta com os blocos vizinhos e os blocos do registro;
* o `trocar_linha.ps1` com L1 e L2, nas travas do pedido 47.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ml.optimization import aptidao_do_projeto as AP  # noqa: E402
from ml.optimization import codificacao_nova as CN  # noqa: E402
from ml.optimization import medidor_calibrado as MC  # noqa: E402
from ml.optimization import montagem as MO  # noqa: E402
from ml.pista_teste import ai_spline as A  # noqa: E402
from ml.pista_teste import linha_do_projeto as LP  # noqa: E402
from ml.pista_teste import linha_nova as N  # noqa: E402
from ml.pista_teste import registro as R  # noqa: E402
from ml.pista_teste.por_trecho import Trecho  # noqa: E402
from test_pista_teste import _args, _ps, jogo_falso, pista_circular, pytestmark_windows, spline_circular  # noqa: E402,F401

RAIO = 100.0


def _trechos(track, cortes=(0.0, 150.0, 400.0)):
    bordas = list(cortes) + [track.length]
    return [Trecho(f"T{i}", bordas[i], bordas[i + 1], bordas[i] + 20.0, bordas[i] + 30.0, bordas[i] + 40.0, True)
            for i in range(len(cortes))]


# --------------------------------------------------------- a codificacao ---

def test_janelas_juntam_e_dao_a_volta():
    j = CN.janelas_das_curvas(1000.0, [(100.0, 150.0), (200.0, 260.0), (980.0, 990.0)], margem_m=40.0)
    # (60, 190) e (160, 300) se tocam; a ultima passa da linha: (940, 1030).
    assert j == [(60.0, 300.0), (940.0, 1030.0)]
    j = CN.janelas_das_curvas(1000.0, [(10.0, 20.0), (950.0, 990.0)], margem_m=40.0)
    assert len(j) == 1 and j[0][0] == pytest.approx(910.0) and j[0][1] == pytest.approx(1060.0)


def test_pontos_de_controle_mais_densos_nas_janelas():
    s = CN.pontos_de_controle(1000.0, [(100.0, 200.0)], 10.0, 25.0)
    dentro = s[(s >= 100) & (s < 200)]
    fora = s[(s >= 200) | (s < 100)]
    assert np.allclose(np.diff(dentro), 10.0)
    assert np.all(np.diff(np.sort(fora[fora >= 200])) <= 25.0 + 1e-9)
    assert np.all((s >= 0) & (s < 1000)) and np.all(np.diff(s) > 0)


def test_lateral_constante_vira_circulo_com_a_curvatura_continua():
    track = pista_circular()
    cod = CN.construir(track, [(100.0, 150.0)], 10.0, 25.0)
    g = np.full(cod.genes, 2.0)
    lat = cod.decode(g)
    assert np.max(np.abs(lat - 2.0)) < 0.01
    # A curvatura da curva X/Z, pela segunda derivada da spline, sem saltos nos nos.
    u = np.linspace(0.0, track.length, 4000, endpoint=False)
    xz = cod.curva(g, u)
    k = CN.raio_de_tres_pontos(xz)
    assert np.allclose(k, RAIO + 2.0, rtol=0.01)          # lateral positiva e para fora no circulo sintetico


def test_ida_e_volta_de_uma_linha_suave():
    track = pista_circular()
    cod = CN.construir(track, [(100.0, 150.0)], 10.0, 25.0)
    lat = 1.5 * np.sin(2 * np.pi * track.s / track.length * 3)
    volta = cod.decode(cod.encode(lat))
    assert np.percentile(np.abs(volta - lat), 95) < 0.02


def test_curvatura_continua_mesmo_com_um_gene_deslocado():
    track = pista_circular()
    cod = CN.construir(track, [], 10.0, 25.0)
    g = np.zeros(cod.genes)
    g[5] = 1.0
    u = np.linspace(0.0, track.length, 20000, endpoint=False)
    xz = cod.curva(g, u)
    kappa = 1.0 / CN.raio_de_tres_pontos(xz)
    # Spline cubica: a curvatura nao salta; o maior passo entre amostras vizinhas e pequeno.
    assert np.max(np.abs(np.diff(kappa))) < 2e-4


def test_raio_minimo_e_taxa_por_trecho_e_limites():
    track = pista_circular()
    trechos = _trechos(track)
    reta = np.zeros(track.size)
    onda = 2.0 * np.sin(2 * np.pi * track.s / 60.0)        # uma onda curta deixa a linha mais fechada
    m_reta = CN.medidas_por_trecho(track, reta, trechos)
    m_onda = CN.medidas_por_trecho(track, onda, trechos)
    assert np.allclose(m_reta["raio_min_m"], RAIO, rtol=0.02)
    assert (m_onda["raio_min_m"] < m_reta["raio_min_m"]).all()
    assert (m_onda["taxa_max"] > m_reta["taxa_max"]).all()
    lim = CN.limites_por_trecho(track, [reta, onda], trechos)
    assert np.allclose(lim["raio_min_m"], 0.9 * m_onda["raio_min_m"])
    assert np.allclose(lim["taxa_max"], 1.1 * m_onda["taxa_max"])
    exc = CN.excesso_das_restricoes(m_onda, lim)
    assert (exc["raio"] == 0).all() and (exc["taxa"] == 0).all()
    exc = CN.excesso_das_restricoes(m_onda, CN.limites_por_trecho(track, [reta], trechos))
    assert (exc["raio"] > 0).all() and (exc["taxa"] > 0).all()


def test_emenda_da_volta_fica_fora():
    track = pista_circular()
    ok = CN.fora_da_emenda(track)
    assert not ok[track.s < 30].any() and not ok[track.s > track.length - 30].any() and ok[(track.s > 40) & (track.s < 500)].all()


def test_conferencia_passa_no_circulo_e_falha_com_um_raio_fechado():
    track = pista_circular()
    original = spline_circular(n=400)
    cod = CN.construir(track, [(100.0, 150.0)], 10.0, 25.0)
    estacao = np.mod(N.estacoes(original, track), track.length)
    xz = original.pos[:, [0, 2]].astype(float)
    trechos = _trechos(track)
    r = CN.conferir_c0(cod, xz, estacao, original.campo("raio").astype(float), trechos)
    assert r["passa"] and r["distancia_p95_m"] < 0.01 and r["maior_diferenca_relativa_do_raio"] < 0.01
    # Um raio "original" bem menor num trecho (um ponto fechado que a curva suave nao segue) reprova.
    raio = original.campo("raio").astype(float).copy()
    raio[50] = 50.0
    r = CN.conferir_c0(cod, xz, estacao, raio, trechos)
    assert not r["passa"]
    v = CN.conferir_volta(cod, np.full(track.size, 1.0), trechos, "volta")
    assert v["passa"]


def test_reparo_do_corredor_traz_a_linha_para_dentro():
    track = pista_circular(largura=3.0)
    cod = CN.construir(track, [], 10.0, 25.0)
    g = np.full(cod.genes, 2.5)
    g[3] = 4.0                                   # alem do limite: o clip ja traz, mas a spline pode passar
    g, _ = CN.reparar_corredor(cod, g)
    from ml.track.trajectory import corridor_violation
    assert corridor_violation(track, cod.decode(g)).max() == 0.0


# ------------------------------------------------------------- o medidor ---

def test_calibracao_com_uma_linha_de_fora():
    linhas = ("C1", "C2", "C3", "C4")
    dS = {x: np.array([1.0, -2.0, 0.5]) * (i + 1) for i, x in enumerate(linhas)}
    dJ = {x: dS[x] * np.array([0.5, 1.0, -1.0]) for x in linhas}       # o 3o trecho anda ao contrario
    beta = MC.ajustar_beta(dJ, dS, linhas)
    assert beta == pytest.approx([0.5, 1.0, 0.0])                       # o negativo fica em 0
    # Uma linha de fora: o ajuste nao usa a linha testada.
    dJ_ruim = dict(dJ)
    dJ_ruim["C4"] = dS["C4"] * 2.0
    fora = MC.deixar_uma_de_fora(dJ_ruim, dS, linhas)
    assert fora["C4"] == pytest.approx([0.5, 1.0, 0.0])
    assert fora["C1"][0] > 0.5
    # Sem diferenca no simulador, beta = 1; e o teto e 2.
    assert MC.ajustar_beta({"a": np.array([1.0, 9.0])}, {"a": np.array([0.0, 1.0])}, ["a"]) == pytest.approx([1.0, 2.0])


def test_diferenca_por_grupo_com_pesos_e_spearman():
    passos_x = np.array([1.0, 1.0, 2.0, 2.0])
    base = np.array([0.5, 1.0, 1.0, 1.0])
    grupo = np.array([0, 0, 1, 1])
    assert MC.diferenca_por_grupo(passos_x, base, grupo, 2) == pytest.approx([0.5, 2.0])
    pesos = MC.pesos_por_passo(np.array([2.0, 0.0]), grupo)
    assert MC.diferenca_por_grupo(passos_x, base, grupo, 2, pesos) == pytest.approx([1.0, 0.0])
    jogo = {"a": np.array([1.0, 2.0, 3.0]), "b": np.array([3.0, 2.0, 1.0])}
    bom = {"a": np.array([10.0, 20.0, 30.0]), "b": np.array([30.0, 20.0, 10.0])}
    ruim = {"a": np.array([3.0, 2.0, 1.0]), "b": np.array([1.0, 2.0, 3.0])}
    cand = {"ruim": MC.spearman_juntos(ruim, jogo, ["a", "b"]), "bom": MC.spearman_juntos(bom, jogo, ["a", "b"])}
    assert cand["bom"]["rho"] == pytest.approx(1.0) and MC.escolher(cand) == "bom"


# ------------------------------------------------- a regiao de confianca ---

def test_regiao_de_confianca():
    l1 = np.zeros(10)
    dentro = np.full(10, 0.9)
    fora = np.r_[np.zeros(9), 1.3]
    pen = AP.penalizacao_da_regiao(np.vstack([dentro, fora]), l1)
    assert pen[0] == 0.0 and pen[1] == pytest.approx(5.0 + 100.0 * 0.3)
    track = pista_circular()
    cod = CN.construir(track, [], 10.0, 25.0)
    g1 = np.full(cod.genes, 0.5)
    reg = AP.regiao_nos_genes(cod, g1)
    assert np.allclose(reg.lower, np.maximum(g1 - 1.0, cod.lower)) and np.allclose(reg.upper, np.minimum(g1 + 1.0, cod.upper))
    assert np.all(np.abs(reg.clip(np.full(cod.genes, 9.0)) - g1) <= 1.0 + 1e-12)
    assert AP.penalizacao_das_restricoes({"raio": np.array([0.0, 0.1]), "taxa": np.array([0.0, 0.0])}) == pytest.approx(5.0 + 10.0)


# ------------------------------------------------------------ a montagem ---

def test_montagem_por_trecho_e_emendas():
    s = np.arange(0.0, 1000.0, 2.0)
    trechos = [Trecho("T1", 0.0, 300.0, 200.0, 250.0, 300.0, True),
               Trecho("T2", 300.0, 700.0, 500.0, 600.0, 700.0, True),
               Trecho("T3", 700.0, 1000.0, 700.0, None, 1000.0, False)]
    A_ = np.full(s.size, 1.0)
    B_ = 1.2 + 0.8 * np.clip((420.0 - s) / 100.0, 0.0, 1.0)  # suave; as linhas se encontram mais perto em s >= 420
    r = MO.montar(s, 1000.0, trechos, ["A", "B", "A"], {"A": A_, "B": B_})
    lat = r["lateral"]
    e1 = r["emendas"][0]
    assert e1["entre"] == "T1/T2" and 420.0 <= e1["centro_s"] <= 480.0 and e1["janela_m"] == 40.0
    assert np.allclose(lat[(s >= 0) & (s < 300)], 1.0)                        # T1 inteiro e A
    assert np.allclose(lat[(s >= 300) & (s < e1["centro_s"] - 20)], 1.0)      # antes da janela, ainda A
    assert np.allclose(lat[(s > e1["centro_s"] + 20) & (s < 700)], B_[(s > e1["centro_s"] + 20) & (s < 700)])
    assert np.max(np.abs(np.diff(lat))) < 0.1                                 # sem degrau
    e2 = r["emendas"][1]
    assert e2["entre"] == "T2/T3" and 720.0 <= e2["centro_s"] <= 980.0
    assert MO.suave(np.array([0.0, 0.5, 1.0])) == pytest.approx([0.0, 0.5, 1.0])
    h = 1e-4
    assert (MO.suave(np.array([h])) - 0.0) / h < 1e-6                          # derivada nula na ponta
    assert MO.escolher_por_trecho({"C2": [1.0, 2.0], "C3": [0.5, 3.0], "C4": [0.7, 2.0]}, ["C2", "C3", "C4"]) == ["C3", "C2"]


# ----------------------------------------------------------- o veredito ---

def test_veredito_da_meta_com_os_blocos_vizinhos():
    c0a = [85.40, 85.45, 85.50, 85.42, 85.48, 85.44, 85.46]
    c0d = [85.50, 85.55, 85.60, 85.52, 85.58, 85.54, 85.56]
    assert LP.veredito_da_meta([85.39] + [85.6] * 6, c0a, c0d)["veredito"] == "meta atingida"
    assert LP.veredito_da_meta([85.40] + [85.6] * 6, c0a, c0d)["veredito"] == "meta atingida"     # igual vale
    r = LP.veredito_da_meta([85.45] + [85.3 + 1] * 6, c0a, c0d)
    assert r["veredito"] == "meta nao atingida" and r["falta_s"]["contra_c0_antes"] == pytest.approx(0.05)
    assert LP.veredito_da_meta([85.0] * 4, c0a, c0d)["veredito"].startswith("nao conclusivo")
    assert LP.veredito_da_meta([85.0] * 7, c0a, c0d, troca_pegou=False)["veredito"].startswith("fora do veredito")
    d = LP.diferenca_contra_os_vizinhos([85.3] * 7, c0a, c0d)
    assert d["diferenca_s"] < 0 and d["nao_inferior"]


def test_blocos_do_pedido_50_e_vizinhos():
    t0 = datetime(2026, 11, 13, 10, 0, 0)
    sha = {"C0": "a" * 64, "L1": "b" * 64, "L2": "c" * 64, "C3": "d" * 64}
    linhas = [(t0 - timedelta(days=3), "C3"), (t0, "C0"), (t0 + timedelta(minutes=20), "L1"),
              (t0 + timedelta(minutes=40), "C0"), (t0 + timedelta(hours=5), "L2"), (t0 + timedelta(hours=5, minutes=20), "C0")]
    trocas = [R.Troca(h, c, sha[c]) for h, c in linhas]
    bl = R.blocos(trocas, desde=t0 - timedelta(hours=1))
    assert [b.condicao for b in bl] == ["C0", "L1", "C0", "L2", "C0"] and [b.numero for b in bl] == [1, 2, 3, 4, 5]
    assert [b.numero for b in R.vizinhos_de_c0(bl, 2)] == [1, 3]
    assert [b.numero for b in R.vizinhos_de_c0(bl, 4)] == [3, 5]
    sess = {"s1": t0 + timedelta(minutes=1), "s2": t0 + timedelta(minutes=21), "s0": t0 - timedelta(minutes=5)}
    at = {a["sessao"]: a for a in R.atribuir_aos_blocos(sess, bl, sha)}
    assert at["s1"]["bloco"] == 1 and at["s2"]["condicao"] == "L1" and at["s0"]["bloco"] is None
    errado = dict(sha, L1="e" * 64)
    assert R.atribuir_aos_blocos({"s2": sess["s2"]}, bl, errado)[0]["bloco"] is None


def test_registro_aceita_l1_e_l2(tmp_path):
    p = tmp_path / "registro.csv"
    p.write_text("hora,condicao,sha256,arquivo\r\n2026-11-13T10:00:00,L1,ab,x\r\n2026-11-13T10:30:00,L2,cd,x\r\n", encoding="utf-8")
    assert [t.condicao for t in R.ler(p)] == ["L1", "L2"]
    p.write_text("hora,condicao,sha256,arquivo\r\n2026-11-13T10:00:00,L3,ab,x\r\n", encoding="utf-8")
    with pytest.raises(ValueError):
        R.ler(p)


# ------------------------------------------------------- o arquivo e o ps1 ---

def test_arquivo_pela_curva_tem_o_raio_suave_e_a_velocidade_do_original():
    track = pista_circular()
    original = spline_circular(n=400)
    cod = CN.construir(track, [(100.0, 150.0)], 10.0, 25.0)
    ln = LP.montar_da_curva(original, track, cod, np.full(cod.genes, 1.0))
    sp = ln.spline
    assert sp.n == original.n
    assert np.allclose(sp.campo("raio"), RAIO + 1.0, rtol=0.01)
    assert np.array_equal(sp.campo("velocidade"), original.campo("velocidade"))
    assert A.ler(A.escrever(sp)).n == original.n


def _manifesto_do_projeto(f):
    linhas = f["repo"] / "data" / "pista_teste" / "linhas"
    original = A.ler(f["pista"] / "gp" / "ai" / "fast_lane.ai")
    man = {"condicoes": {}}
    for i, cond in enumerate(("L1", "L2")):
        dados = A.escrever(N.montar(original, pista_circular(), np.full(pista_circular().size, 0.3 + 0.4 * i)).spline)
        (linhas / cond).mkdir(parents=True)
        (linhas / cond / "fast_lane.ai").write_bytes(dados)
        man["condicoes"][cond] = {"sha256": hashlib.sha256(dados).hexdigest()}
    (linhas / "linha_do_projeto.json").write_text(json.dumps(man), encoding="utf-8")
    return man


@pytestmark_windows
def test_trocar_linha_com_l1_e_l2_nas_travas_do_47(jogo_falso):
    from test_pista_teste import _hash_da_pasta

    f = jogo_falso
    man = _manifesto_do_projeto(f)
    antes = _hash_da_pasta(f["pista"])
    assert _ps("criar_copia.ps1", *_args(f)).returncode == 0
    for cond in ("C0", "L1", "C0", "L2", "C0"):
        r = _ps("trocar_linha.ps1", "-Condicao", cond, *_args(f))
        assert r.returncode == 0, r.stdout + r.stderr
        sha = hashlib.sha256((f["copia"] / "gp" / "ai" / "fast_lane.ai").read_bytes()).hexdigest()
        esperado = (man if cond in ("L1", "L2") else f["manifesto"])["condicoes"][cond]["sha256"]
        assert sha == esperado
    registro = R.ler(f["repo"] / "data" / "pista_teste" / "registro.csv")
    assert [t.condicao for t in registro] == ["C0", "L1", "C0", "L2", "C0"]
    assert _hash_da_pasta(f["pista"]) == antes
    # As travas: o jogo aberto, e um arquivo que nao bate com o manifesto do projeto.
    aberto = ("-JogoRaiz", str(f["jogo"]), "-RepoRaiz", str(f["repo"]), "-ProcessosDoJogo", "powershell")
    r = _ps("trocar_linha.ps1", "-Condicao", "L1", *aberto)
    assert r.returncode == 1 and "jogo esta aberto" in r.stdout
    (f["repo"] / "data" / "pista_teste" / "linhas" / "L2" / "fast_lane.ai").write_bytes(b"outro")
    r = _ps("trocar_linha.ps1", "-Condicao", "L2", *_args(f))
    assert r.returncode == 1 and "nao bate com o linha_do_projeto.json" in r.stdout
    assert _ps("remover_copia.ps1", *_args(f)).returncode == 0
    assert _hash_da_pasta(f["pista"]) == antes


@pytestmark_windows
def test_trocar_linha_recusa_l1_sem_o_manifesto_do_projeto(jogo_falso):
    f = jogo_falso
    assert _ps("criar_copia.ps1", *_args(f)).returncode == 0
    r = _ps("trocar_linha.ps1", "-Condicao", "L1", *_args(f))
    assert r.returncode == 1 and "linha_do_projeto.json" in r.stdout
    r = _ps("trocar_linha.ps1", "-Condicao", "L3", *_args(f))
    assert r.returncode != 0
