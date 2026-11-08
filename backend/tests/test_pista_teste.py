"""Pedido 47 (ADR 0029): a linha gerada dirigida pela IA do jogo. Tudo com dados sinteticos.

* a ida e volta do leitor e do escritor do `fast_lane.ai`, byte a byte;
* a linha nova fechada, no sentido certo, com o espacamento do original e as alturas;
* os scripts da pista de teste: recusam com o jogo aberto, recusam caminho fora da
  copia e nunca escrevem na original (numa pasta falsa "[teste]", apagada no fim);
* a exclusao das sessoes da copia do inventario, do store, do treino, do coach e da evolucao;
* a atribuicao das voltas as condicoes pelo `registro.csv`;
* o veredito e o bootstrap do ADR 0029.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml import config  # noqa: E402
from ml.data import recordings as REC  # noqa: E402
from ml.pista_teste import ai_spline as A  # noqa: E402
from ml.pista_teste import etapas as E  # noqa: E402
from ml.pista_teste import linha_nova as N  # noqa: E402
from ml.pista_teste import registro as R  # noqa: E402
from ml.track.geometry import TrackGeometry  # noqa: E402

TOOLS = Path(__file__).resolve().parents[2] / "tools" / "pista_teste"
RAIO = 100.0


# ------------------------------------------------------------- sinteticos ---

def spline_circular(n: int = 300, raio: float = RAIO, lado: float = 5.0) -> A.AiSpline:
    """Uma linha da IA num circulo, no sentido de theta crescente, com altura variando e bordas a `lado` m."""
    theta = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    pos = np.column_stack([raio * np.cos(theta), 2.0 * np.sin(theta), raio * np.sin(theta)]).astype(np.float32)
    g = N.geometria(pos)
    extras = np.zeros((n, 18), np.float32)
    extras[:, A.COL["velocidade"]] = 30.0 + 5 * np.cos(theta)
    extras[:, A.COL["acelerador"]] = 1.0
    extras[:, A.COL["raio"]] = g["raio"]
    extras[:, A.COL["lateral_esquerda"]] = lado
    extras[:, A.COL["lateral_direita"]] = lado
    extras[:, A.COL["direcao"]] = g["direcao"]
    extras[:, A.COL["normal_y"]] = 1.0
    extras[:, A.COL["comprimento"]] = g["comprimento"]
    extras[:, A.COL["frente_x"]:A.COL["frente_z"] + 1] = g["frente"]
    extras[:, A.COL["inclinacao"]] = g["inclinacao"]
    seg = np.linalg.norm(np.diff(pos.astype(float), axis=0), axis=1)
    sp = A.AiSpline(7, 0, 0, pos, np.r_[0.0, np.cumsum(seg)].astype(np.float32), np.arange(n, dtype=np.int32), extras)
    sp.grade = A.construir_grade(pos)
    return sp


def pista_circular(raio: float = RAIO, passo: float = 2.0, largura: float = 6.0) -> TrackGeometry:
    comprimento = 2 * np.pi * raio
    n = int(round(comprimento / passo))
    theta = np.arange(n) * (2 * np.pi / n)
    tangente = np.column_stack([-np.sin(theta), np.cos(theta)])
    normal = np.column_stack([tangente[:, 1], -tangente[:, 0]])     # (t_z, -t_x): a convencao do projeto
    return TrackGeometry(name="circulo", length=comprimento, step=comprimento / n, s=np.arange(n) * comprimento / n,
                         x=raio * np.cos(theta), z=raio * np.sin(theta), elevation=np.zeros(n), tangent=tangente,
                         normal=normal, curvature=np.full(n, -1.0 / raio), width_left=np.full(n, largura),
                         width_right=np.full(n, largura), geometry_id="sintetica")


# ------------------------------------------------------ leitor e escritor ---

def test_ida_e_volta_byte_a_byte():
    sp = spline_circular()
    dados = A.escrever(sp)
    lido = A.ler(dados)
    assert A.escrever(lido) == dados
    assert lido.n == sp.n and lido.versao == 7
    np.testing.assert_array_equal(lido.pos, sp.pos)
    np.testing.assert_array_equal(lido.extras, sp.extras)
    np.testing.assert_array_equal(lido.grade.celulas, sp.grade.celulas)
    # tamanho: cabecalho, pontos, contagem, extras, HasGrid, grade
    colunas, linhas, k = sp.grade.celulas.shape
    assert len(dados) == 16 + sp.n * 20 + 4 + sp.n * 72 + 4 + 36 + colunas * (4 + linhas * (k + 1) * 4)


def test_ida_e_volta_preserva_bytes_depois_da_grade_e_cabecalho():
    sp = spline_circular(n=80)
    sp.tempo_de_volta, sp.amostras, sp.cauda = 1234, 56, b"\x01\x02\x03\x04"
    dados = A.escrever(sp)
    assert A.escrever(A.ler(dados)) == dados


def test_leitor_recusa_outra_versao():
    dados = bytearray(A.escrever(spline_circular(n=40)))
    dados[0] = 6
    with pytest.raises(A.FormatoInvalido):
        A.ler(bytes(dados))


def test_grade_recalculada_e_a_mesma_e_ordenada_pela_distancia():
    sp = spline_circular(n=120)
    g = A.construir_grade(sp.pos)
    np.testing.assert_array_equal(g.celulas, A.construir_grade(sp.pos.copy()).celulas)
    assert g.minimo[0] == pytest.approx(sp.pos[:, 0].min() - 350.0, abs=1e-3)
    centro = np.array([g.minimo[0] + 5.0, g.minimo[2] + 5.0])
    d = np.linalg.norm(sp.pos[g.celulas[0, 0]][:, [0, 2]] - centro, axis=1)
    assert np.all(np.diff(d) >= -1e-6)


# ------------------------------------------------------------ linha nova ---

def test_formulas_reproduzem_o_original_sintetico():
    erros = N.conferir_formulas(spline_circular())
    for campo in ("lateral_esquerda", "lateral_direita", "frente_x", "frente_z", "comprimento", "inclinacao"):
        assert erros[campo]["erro_max"] < 1e-3, campo
    assert erros["direcao"]["iguais"] == 1.0
    assert erros["raio"]["erro_relativo_mediano"] < 1e-3


def test_linha_nova_fechada_no_sentido_certo_com_o_espacamento_e_as_alturas():
    original = spline_circular()
    track = pista_circular()
    nova = N.montar(original, track, np.full(track.size, 1.0)).spline     # 1 m para a esquerda (para fora)
    assert nova.n == original.n
    raio = np.linalg.norm(nova.pos[:, [0, 2]].astype(float), axis=1)
    np.testing.assert_allclose(raio, RAIO + 1.0, atol=0.05)
    # fechada: o comprimento do ponto 0 e o segmento do ultimo ao primeiro, do tamanho dos outros
    seg = nova.campo("comprimento").astype(float)
    assert seg[0] == pytest.approx(np.median(seg), rel=0.02)
    # o sentido: a distancia cresce e o ponto 0 fica na mesma estacao do original
    assert np.all(np.diff(nova.dist) > 0)
    ang = np.arctan2(nova.pos[:, 2], nova.pos[:, 0])
    ang0 = np.arctan2(original.pos[:, 2], original.pos[:, 0])
    np.testing.assert_allclose(np.unwrap(ang) - np.unwrap(ang0), 0.0, atol=0.01)
    # o espacamento do original, na proporcao do raio
    np.testing.assert_allclose(np.median(seg), np.median(original.campo("comprimento")) * (RAIO + 1) / RAIO, rtol=0.01)
    # as alturas do ponto mais proximo da linha original
    np.testing.assert_allclose(nova.pos[:, 1], original.pos[:, 1], atol=0.02)
    # as laterais: a borda fica no mesmo lugar e a distancia muda
    np.testing.assert_allclose(nova.campo("lateral_esquerda"), 4.0, atol=0.05)
    np.testing.assert_allclose(nova.campo("lateral_direita"), 6.0, atol=0.05)
    # a velocidade e os pedais sao os do original; o raio e a geometria sao da linha nova
    np.testing.assert_array_equal(nova.campo("velocidade"), original.campo("velocidade"))
    # o raio por 3 pontos vizinhos sente o poligono de 2 m da pista sintetica: a mediana e justa, cada ponto, nao tanto
    assert float(np.median(nova.campo("raio"))) == pytest.approx(RAIO + 1.0, rel=0.01)
    np.testing.assert_allclose(nova.campo("raio"), RAIO + 1.0, rtol=0.05)
    # e o arquivo volta igual
    assert A.escrever(A.ler(A.escrever(nova))) == A.escrever(nova)


def test_lateral_alem_da_borda_fica_em_zero():
    original = spline_circular(lado=5.0)
    track = pista_circular()
    nova = N.montar(original, track, np.full(track.size, 5.3)).spline
    assert float(nova.campo("lateral_esquerda").min()) == 0.0
    assert np.all(nova.campo("lateral_direita") > 10.0)


def test_linha_nova_recusa_grade_errada():
    with pytest.raises(ValueError):
        N.montar(spline_circular(), pista_circular(), np.zeros(10))


# --------------------------------------------------------------- scripts ---

pytestmark_windows = pytest.mark.skipif(os.name != "nt" or shutil.which("powershell") is None,
                                        reason="os scripts sao do Windows PowerShell")


def _hash_da_pasta(pasta: Path) -> dict:
    return {str(p.relative_to(pasta)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pasta.rglob("*")) if p.is_file()}


def _ps(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(TOOLS / script), *args],
                          capture_output=True, text=True, timeout=180)


@pytest.fixture
def jogo_falso(tmp_path):
    """Uma pasta "[teste]" com uma pista falsa e um repositorio falso com as linhas. Apagada no fim."""
    base = tmp_path / "[teste] pista falsa"
    jogo = base / "jogo"
    pista = jogo / "content" / "tracks" / "vhe_interlagos"
    (pista / "gp" / "ai").mkdir(parents=True)
    (pista / "gp" / "data").mkdir(parents=True)
    (pista / "ui" / "gp").mkdir(parents=True)
    (pista / "ui" / "norm").mkdir(parents=True)
    original = spline_circular()
    (pista / "gp" / "ai" / "fast_lane.ai").write_bytes(A.escrever(original))
    (pista / "gp" / "ai" / "pit_lane.ai").write_bytes(b"pit")
    (pista / "gp" / "data" / "surfaces.ini").write_bytes(b"[SURFACE_0]\r\n")
    (pista / "data.acd").write_bytes(os.urandom(256))
    for layout, nome in (("gp", "Interlagos - GP"), ("norm", "Interlagos - National")):
        (pista / "ui" / layout / "ui_track.json").write_bytes(
            ('{\r\n  "name": "%s",\r\n  "city": "São Paulo"\r\n}' % nome).encode("utf-8"))
    repo = base / "repo"
    linhas = repo / "data" / "pista_teste" / "linhas"
    manifesto = {"condicoes": {}}
    for i, cond in enumerate(("C0", "C1", "C2", "C3", "C4")):
        if cond == "C0":
            dados = A.escrever(original)
        else:
            dados = A.escrever(N.montar(original, pista_circular(), np.full(pista_circular().size, 0.5 * i)).spline)
        (linhas / cond).mkdir(parents=True)
        (linhas / cond / "fast_lane.ai").write_bytes(dados)
        manifesto["condicoes"][cond] = {"sha256": hashlib.sha256(dados).hexdigest()}
    (linhas / "linhas.json").write_text(json.dumps(manifesto), encoding="utf-8")
    yield {"base": base, "jogo": jogo, "pista": pista, "copia": jogo / "content" / "tracks" / "vhe_interlagos_teste_m1",
           "repo": repo, "manifesto": manifesto}
    shutil.rmtree(base, ignore_errors=True)
    assert not base.exists()


def _args(f, *extra):
    return ("-JogoRaiz", str(f["jogo"]), "-RepoRaiz", str(f["repo"]), "-ProcessosDoJogo", "processo_que_nao_existe_47", *extra)


@pytestmark_windows
def test_scripts_criam_trocam_e_removem_sem_tocar_na_original(jogo_falso):
    f = jogo_falso
    antes = _hash_da_pasta(f["pista"])
    r = _ps("criar_copia.ps1", *_args(f))
    assert r.returncode == 0, r.stdout + r.stderr
    assert f["copia"].is_dir()
    ui = (f["copia"] / "ui" / "gp" / "ui_track.json").read_bytes()
    assert b'"name": "Interlagos [teste]"' in ui and "São Paulo".encode("utf-8") in ui and b"\r\n" in ui
    assert b'"name": "Interlagos National [teste]"' in (f["copia"] / "ui" / "norm" / "ui_track.json").read_bytes()
    assert (f["copia"] / "data.acd").read_bytes() == (f["pista"] / "data.acd").read_bytes()

    for cond in ("C0", "C3", "C0"):
        r = _ps("trocar_linha.ps1", "-Condicao", cond, *_args(f))
        assert r.returncode == 0, r.stdout + r.stderr
        sha = hashlib.sha256((f["copia"] / "gp" / "ai" / "fast_lane.ai").read_bytes()).hexdigest()
        assert sha == f["manifesto"]["condicoes"][cond]["sha256"]
    registro = R.ler(f["repo"] / "data" / "pista_teste" / "registro.csv")
    assert [t.condicao for t in registro] == ["C0", "C3", "C0 final"]
    assert _hash_da_pasta(f["pista"]) == antes

    r = _ps("remover_copia.ps1", *_args(f))
    assert r.returncode == 0, r.stdout + r.stderr
    assert not f["copia"].exists()
    assert _hash_da_pasta(f["pista"]) == antes


@pytestmark_windows
def test_scripts_recusam_com_o_jogo_aberto(jogo_falso):
    f = jogo_falso
    aberto = ("-JogoRaiz", str(f["jogo"]), "-RepoRaiz", str(f["repo"]), "-ProcessosDoJogo", "powershell")
    r = _ps("criar_copia.ps1", *aberto)
    assert r.returncode == 1 and "jogo esta aberto" in r.stdout
    assert not f["copia"].exists()
    assert _ps("criar_copia.ps1", *_args(f)).returncode == 0
    conteudo = (f["copia"] / "gp" / "ai" / "fast_lane.ai").read_bytes()
    r = _ps("trocar_linha.ps1", "-Condicao", "C3", *aberto)
    assert r.returncode == 1 and "jogo esta aberto" in r.stdout
    assert (f["copia"] / "gp" / "ai" / "fast_lane.ai").read_bytes() == conteudo
    assert not (f["repo"] / "data" / "pista_teste" / "registro.csv").exists()
    r = _ps("remover_copia.ps1", *aberto)
    assert r.returncode == 1 and f["copia"].exists()


@pytestmark_windows
def test_scripts_recusam_caminho_fora_da_copia(jogo_falso):
    f = jogo_falso
    comum = TOOLS / "comum.ps1"
    for alvo in (f["pista"] / "gp" / "ai" / "fast_lane.ai", f["jogo"] / "content" / "tracks" / "outra" / "x.ai",
                 f["base"] / "fora.txt"):
        cmd = (f". '{comum}'; $p = Resolver-Pastas '{f['jogo']}' '{f['repo']}'; "
               f"Conferir-DentroDaCopia $p '{alvo}'; Write-Host 'ACEITO'")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           capture_output=True, text=True, timeout=120)
        assert "ACEITO" not in r.stdout and "recusado" in r.stdout, (alvo, r.stdout, r.stderr)


@pytestmark_windows
def test_trocar_linha_recusa_copia_que_e_juncao_para_a_original(jogo_falso):
    f = jogo_falso
    antes = _hash_da_pasta(f["pista"])
    (f["repo"] / "data" / "pista_teste").mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256((f["pista"] / "gp" / "ai" / "fast_lane.ai").read_bytes()).hexdigest()
    (f["repo"] / "data" / "pista_teste" / "copia.json").write_text(json.dumps({"sha256_fast_lane_original": sha}),
                                                                    encoding="utf-8")
    subprocess.run(["cmd", "/c", "mklink", "/J", str(f["copia"]), str(f["pista"])], check=True, capture_output=True)
    try:
        r = _ps("trocar_linha.ps1", "-Condicao", "C3", *_args(f))
        assert r.returncode == 1 and "juncao" in r.stdout, r.stdout + r.stderr
        r = _ps("remover_copia.ps1", *_args(f))
        assert r.returncode == 1
        assert _hash_da_pasta(f["pista"]) == antes
    finally:
        os.rmdir(f["copia"])        # remove so a juncao
    assert _hash_da_pasta(f["pista"]) == antes


@pytestmark_windows
def test_trocar_linha_recusa_arquivo_que_nao_bate_com_o_manifesto(jogo_falso):
    f = jogo_falso
    assert _ps("criar_copia.ps1", *_args(f)).returncode == 0
    (f["repo"] / "data" / "pista_teste" / "linhas" / "C2" / "fast_lane.ai").write_bytes(b"outro")
    r = _ps("trocar_linha.ps1", "-Condicao", "C2", *_args(f))
    assert r.returncode == 1 and "nao bate" in r.stdout


# -------------------------------------------------------------- exclusao ---

def _sessao(raiz: Path, nome: str, pista: str) -> None:
    d = raiz / nome
    d.mkdir(parents=True)
    linha = {"type": "player", "track": pista, "sample": {"track": pista, "lap_number": 1}}
    (d / "player.jsonl").write_text(json.dumps(linha) + "\n", encoding="utf-8")


def test_sessoes_da_copia_ficam_fora_do_ml(tmp_path):
    raiz = tmp_path / "recordings"
    _sessao(raiz, "2026-11-08_10-00-00_vhe_interlagos", "vhe_interlagos")
    _sessao(raiz, "2026-11-08_11-00-00_vhe_interlagos_teste_m1", "vhe_interlagos_teste_m1")
    _sessao(raiz, "2026-11-08_12-00-00_vhe_interlagos40", "vhe_interlagos40")
    ids = [s.session_id for s in REC.list_sessions(root=raiz)]
    assert ids == ["2026-11-08_10-00-00_vhe_interlagos", "2026-11-08_12-00-00_vhe_interlagos40"]
    assert "2026-11-08_11-00-00_vhe_interlagos_teste_m1" not in [s.session_id for s in REC.list_all_sessions(roots=[raiz])]
    so_copia = REC.list_all_sessions(roots=[raiz], track_prefixes=("vhe_interlagos_teste_m1",), incluir_pistas_de_teste=True)
    assert [s.session_id for s in so_copia] == ["2026-11-08_11-00-00_vhe_interlagos_teste_m1"]
    assert REC.is_test_track_session(None, "2026-11-08_11-00-00_vhe_interlagos_teste_m1")


def test_so_o_resultado_do_pedido_47_pede_as_sessoes_da_copia():
    """O inventario, o store, o treino, o coach e a evolucao leem as sessoes por list_sessions sem a opcao."""
    backend = Path(__file__).resolve().parents[1]
    def pede(p: Path) -> bool:
        linhas = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        return any("incluir_pistas_de_teste=True" in l and not l.strip().startswith("#") for l in linhas)

    quem_pede = sorted(str(p.relative_to(backend)) for p in backend.rglob("*.py") if "tests" not in p.parts and pede(p))
    assert quem_pede == [str(Path("ml/pista_teste/etapas.py"))]
    consumidores = ["ml/data/inventory.py", "ml/data/store_v2.py", "ml/data/lap_store.py", "ml/models/retreino.py",
                    "ml/scripts/build_inventory.py", "ml/scripts/build_lap_store_v2.py", "tools/train_reference_model.py",
                    "ml/modelo2/dados.py", "ml/modelo_carro/dados.py"]
    for nome in consumidores:
        texto = (backend / nome).read_text(encoding="utf-8")
        assert "list_all_sessions" in texto or "list_sessions" in texto, nome
        assert "track_prefixes" not in texto and "incluir_pistas_de_teste" not in texto, nome
    assert "vhe_interlagos_teste_m1" in config.TEST_TRACK_NAMES


# ------------------------------------------------------------ atribuicao ---

T0 = datetime(2026, 11, 8, 10, 0, 0)
SHA = {c: c.lower() * 8 for c in ("C0", "C1", "C2", "C3", "C4")}


def _trocas(*linhas):
    return R.rotular([(T0 + timedelta(minutes=m), c, SHA[c] if s is None else s, "") for m, c, s in linhas])


def test_atribuicao_pela_hora_da_ultima_troca_e_o_c0_final():
    trocas = _trocas((0, "C0", None), (20, "C1", None), (40, "C4", None), (60, "C0", None))
    assert [t.condicao for t in trocas] == ["C0", "C1", "C4", "C0 final"]
    sessoes = {"a": T0 - timedelta(minutes=5), "b": T0 + timedelta(minutes=2), "c": T0 + timedelta(minutes=21),
               "d": T0 + timedelta(minutes=30), "e": T0 + timedelta(minutes=45), "f": T0 + timedelta(minutes=61)}
    atrib = {a.sessao: a for a in R.atribuir(sessoes, trocas, SHA)}
    assert atrib["a"].condicao is None and "antes da primeira troca" in atrib["a"].motivo
    assert [atrib[k].condicao for k in "bcdef"] == ["C0", "C1", "C1", "C4", "C0 final"]
    assert R.atribuicoes_por_condicao(list(atrib.values()))["C1"] == ["c", "d"]


def test_atribuicao_recusa_troca_com_o_sha_errado():
    trocas = _trocas((0, "C0", None), (10, "C3", "f" * 64))
    atrib = R.atribuir({"x": T0 + timedelta(minutes=11)}, trocas, SHA)
    assert atrib[0].condicao is None and "sha256" in atrib[0].motivo


def test_registro_csv_lido_com_o_c0_final(tmp_path):
    p = tmp_path / "registro.csv"
    p.write_text("hora,condicao,sha256,arquivo\r\n2026-11-08T10:00:00,C0,AA,x\r\n2026-11-08T10:30:00,C2,bb,x\r\n"
                 "2026-11-08T11:00:00,C0,aa,x\r\n", encoding="utf-8")
    trocas = R.ler(p)
    assert [(t.condicao, t.sha256) for t in trocas] == [("C0", "aa"), ("C2", "bb"), ("C0 final", "aa")]


def test_papeis_saida_primeira_lancada_e_as_que_contam():
    voltas = [R.VoltaNaCondicao("s1", i, 100.0 + i, i == 0) for i in range(11)]
    R.papeis("C3", voltas)
    papeis = [v.papel for v in voltas]
    assert papeis[:2] == ["saida", "primeira lancada"]
    assert papeis[2:9] == ["conta"] * 7 and papeis[9:] == ["alem das que contam"] * 2
    # duas gravacoes na mesma condicao: a primeira volta de cada uma e de saida; so uma primeira lancada
    voltas = ([R.VoltaNaCondicao("s1", i, 100.0 + i, i == 0) for i in range(4)]
              + [R.VoltaNaCondicao("s2", i, 200.0 + i, i == 0) for i in range(5)])
    R.papeis("C0 final", voltas)
    assert [v.papel for v in voltas] == ["saida", "primeira lancada", "conta", "conta", "saida", "conta", "conta",
                                         "alem das que contam", "alem das que contam"]


# ------------------------------------------------------ veredito do ADR ---

def test_bootstrap_e_veredito():
    c0 = [85.0, 85.1, 84.9, 85.05, 85.02, 84.98, 85.0]
    rapida = [x - 0.5 for x in c0]
    d = E.bootstrap_diferenca(rapida, c0)
    assert d["diferenca_s"] == pytest.approx(-0.5) and d["ic95_superior_s"] < 0
    assert E.bootstrap_diferenca(rapida, c0) == d                                  # semente fixa
    assert E.veredito(d, 7, 7) == "mais rapida que a linha da IA"
    assert E.veredito({"diferenca_s": 0, "ic95_inferior_s": -0.05, "ic95_superior_s": 0.08}, 7, 7) == \
        "tao rapida quanto (nao inferior)"
    assert E.veredito({"diferenca_s": 0.3, "ic95_inferior_s": 0.2, "ic95_superior_s": 0.4}, 7, 7) == "mais lenta"
    assert E.veredito({"diferenca_s": 0.1, "ic95_inferior_s": -0.1, "ic95_superior_s": 0.3}, 7, 7) == "nao conclusivo"
    assert E.veredito(d, 4, 7) == "nao dirigivel pela IA"
    assert E.veredito(d, 4, 5).startswith("incompleta")
    assert E.veredito(d, 7, 7, deriva=True) == "nao conclusivo (deriva)"
    assert E.tempo_mmss(84.829) == "1:24,829"
