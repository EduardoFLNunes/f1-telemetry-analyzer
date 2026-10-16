"""Pedido 32, Parte C: o botao do coach, a anotacao de sessao e a trava de execucao.

Tudo numa pasta temporaria, com um comando falso no lugar do `atualizar_coach`:
nenhum teste le ou grava o repositorio de verdade.
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from core.coleta import anotacao as anot  # noqa: E402
from core.coleta.rodada_coach import RodadaDoCoach  # noqa: E402
from core.coleta.trava_coach import TravaDeExecucao, TravaOcupada, caminho_da_trava, ler_trava  # noqa: E402

CABECALHO = "sessao,origem,carModel,anotado_em,observacao\r\n"
SESSAO = "2026-10-20_10-00-00_vhe_interlagos"


def _conferencia(*origens, carro=None, sessao=SESSAO):
    return {"sessao": sessao, "gravacao": {"carModel": carro}, "voltas": [{"origem": o} for o in origens]}


# ------------------------------------------------------------------ trava ---

def test_trava_impede_a_segunda_rodada_e_sai_no_fim(tmp_path):
    with TravaDeExecucao(tmp_path) as trava:
        assert caminho_da_trava(tmp_path).exists()
        assert ler_trava(tmp_path)["ativa"] is True
        with pytest.raises(TravaOcupada) as ocupada:
            TravaDeExecucao(tmp_path).__enter__()
        assert str(ocupada.value).startswith("PARADO: outra rodada do atualizar_coach esta em andamento")
        assert trava.substituiu is None
    assert not caminho_da_trava(tmp_path).exists()


def test_trava_velha_e_substituida(tmp_path):
    caminho = caminho_da_trava(tmp_path)
    caminho.parent.mkdir(parents=True)
    caminho.write_text(json.dumps({"pid": 4_000_000, "inicio": "2026-10-15T23:00:00", "origem": "terminal"}),
                       encoding="utf-8")
    assert ler_trava(tmp_path)["ativa"] is False
    with TravaDeExecucao(tmp_path) as trava:
        assert trava.substituiu["pid"] == 4_000_000
        assert json.loads(caminho.read_text(encoding="utf-8"))["pid"] == os.getpid()
    assert not caminho.exists()


def test_atualizar_coach_para_com_a_trava_ocupada_sem_rodar(monkeypatch, capsys):
    sys.path.insert(0, str(BACKEND / "tools"))
    import atualizar_coach

    class Ocupada:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            raise TravaOcupada({"pid": 123, "inicio": "2026-10-16T01:00:00", "origem": "app"})

    chamou = []
    monkeypatch.setattr(atualizar_coach, "TravaDeExecucao", Ocupada)
    monkeypatch.setattr(atualizar_coach, "_main", lambda argv=None: chamou.append(argv) or 0)
    assert atualizar_coach.main([]) == 3
    assert chamou == []
    assert "PARADO: outra rodada do atualizar_coach esta em andamento (processo 123, desde 01:00:00, pelo app)." \
        in capsys.readouterr().out


# --------------------------------------------------------------- anotacao ---

def test_origem_da_gravacao():
    assert anot.classificar(_conferencia("humano", "humano")) == anot.INDICADOR
    assert anot.classificar(_conferencia("desconhecida", "desconhecida")) == anot.SEM_INDICADOR
    assert anot.classificar(_conferencia("desconhecida", "ia")) == anot.COM_IA
    assert anot.classificar(_conferencia("humano", "misturada")) == anot.COM_IA
    assert anot.classificar(None) == anot.SEM_CONFERENCIA


def test_linha_no_formato_do_arquivo_com_crlf_e_observacao(tmp_path):
    arquivo = tmp_path / anot.ARQUIVO
    arquivo.parent.mkdir(parents=True)
    existente = CABECALHO + '2026-10-05_20-33-47_vhe_interlagos,humano,rss_formula_rss_3_v6_2026,2026-10-08,"Todas as voltas"\r\n'
    arquivo.write_bytes(existente.encode("utf-8"))
    r = anot.anotar(tmp_path, SESSAO, _conferencia("desconhecida", "desconhecida"), hoje=date(2026, 10, 16))
    esperado = f'{SESSAO},humano,rss_formula_rss_3_v6_2026,2026-10-16,"anotada pelo app em 2026-10-16"'
    assert r["linha"] == esperado
    assert r["carroGravado"] is False and r["commit"] is False
    assert arquivo.read_bytes() == (existente + esperado + "\r\n").encode("utf-8")
    # O leitor do pipeline le a linha nova.
    from ml.data.session_annotations import session_annotations
    notas = session_annotations(arquivo)
    assert notas.iloc[-1].to_dict() == {"sessao": SESSAO, "origem": "humano", "carModel": "rss_formula_rss_3_v6_2026",
                                        "anotado_em": "2026-10-16", "observacao": "anotada pelo app em 2026-10-16"}


def test_carro_gravado_e_arquivo_sem_quebra_no_fim(tmp_path):
    arquivo = tmp_path / anot.ARQUIVO
    arquivo.parent.mkdir(parents=True)
    arquivo.write_bytes(CABECALHO.rstrip("\r\n").encode("utf-8"))
    r = anot.anotar(tmp_path, SESSAO, _conferencia("desconhecida", carro="ks_carro"), hoje=date(2026, 10, 16))
    assert r["carro"] == "ks_carro" and r["carroGravado"] is True
    assert arquivo.read_bytes().endswith(b'observacao\r\n' + r["linha"].encode() + b"\r\n")


@pytest.mark.parametrize("conferencia, motivo", [
    (_conferencia("humano"), "indicador de IA"),
    (_conferencia("desconhecida", "ia"), "voltas da IA"),
    (None, "confira a sessão"),
    (_conferencia("desconhecida", sessao="outra"), "não é desta sessão"),
])
def test_anotacao_recusada(tmp_path, conferencia, motivo):
    with pytest.raises(anot.AnotacaoRecusada, match=motivo):
        anot.anotar(tmp_path, SESSAO, conferencia)
    assert not (tmp_path / anot.ARQUIVO).exists()


def test_anotacao_repetida_e_nome_invalido(tmp_path):
    anot.anotar(tmp_path, SESSAO, _conferencia("desconhecida"), hoje=date(2026, 10, 16))
    with pytest.raises(anot.AnotacaoRecusada, match="já está anotada"):
        anot.anotar(tmp_path, SESSAO, _conferencia("desconhecida"))
    with pytest.raises(anot.AnotacaoRecusada, match="inválido"):
        anot.anotar(tmp_path, "../x", _conferencia("desconhecida", sessao="../x"))


# ----------------------------------------------------------------- rodada ---

FALSO_OK = """
import time
print("1/7 inventario novo (incremental)", flush=True)
print("[1/2] 2026-10-11_14-19-52_vhe_interlagos: 23 voltas", flush=True)
print("[2/2] 2026-10-04_02-24-04_vhe_interlagos: 20 voltas (cache)", flush=True)
print("2/7 anotacoes versionadas de 04/10 e 3/7 sessoes novas sem anotacao", flush=True)
time.sleep(0.2)
for n in (4, 5, 6, 7):
    print(f"{n}/7 passo", flush=True)
"""

FALSO_PARADO = """
print("1/7 inventario novo (incremental)", flush=True)
print("6/7 store v2, com as checagens", flush=True)
print("PARADO: o store v2 nao passou nas checagens (acima); o relatorio de evolucao nao rodou.", flush=True)
raise SystemExit(1)
"""


def _repo_falso(tmp_path, script):
    repo = tmp_path / "repo"
    (repo / "data" / "ml" / "origem").mkdir(parents=True)
    (repo / "backend").mkdir()
    (repo / "data" / "ml" / "origem" / "atualizar_coach.json").write_text(json.dumps({"referencias": {
        "minha_melhor": {"volta": "a#0018", "tempo_s": 89.389}}}), encoding="utf-8")
    falso = tmp_path / "falso.py"
    falso.write_text(script, encoding="utf-8")
    return repo, falso


def _rodada(repo, falso, gravando=False, repositorio=True, recarregar=None):
    return RodadaDoCoach(
        repositorio=lambda: repo if repositorio else None,
        gravando=lambda: gravando,
        pasta_de_logs=repo.parent / "logs",
        recarregar_coach=recarregar or (lambda: None),
        comando=lambda _repo: [sys.executable, str(falso)],
    )


def _esperar(rodada, limite=20.0):
    fim = time.time() + limite
    while rodada.em_andamento() and time.time() < fim:
        time.sleep(0.05)
    assert not rodada.em_andamento()
    return rodada.estado()


def test_botao_desligado(tmp_path):
    repo, falso = _repo_falso(tmp_path, FALSO_OK)
    assert _rodada(repo, falso).estado()["ligado"] is True
    assert "não está configurado" in _rodada(repo, falso, repositorio=False).estado()["motivos"][0]
    assert "sendo gravada" in _rodada(repo, falso, gravando=True).estado()["motivos"][0]
    with TravaDeExecucao(repo, origem="terminal"):
        estado = _rodada(repo, falso).estado()
        assert estado["ligado"] is False and "outra rodada" in estado["motivos"][0]
        with pytest.raises(RuntimeError):
            _rodada(repo, falso).iniciar()


def test_rodada_progresso_resumo_e_recarregamento(tmp_path):
    repo, falso = _repo_falso(tmp_path, FALSO_OK)
    recarregou = []
    rodada = _rodada(repo, falso, recarregar=lambda: recarregou.append(True))
    inicio = rodada.iniciar()
    assert inicio["emAndamento"] is True and inicio["ligado"] is False
    estado = _esperar(rodada)
    r = estado["rodada"]
    assert r["situacao"] == "concluida" and r["codigo"] == 0
    assert set(r["passos"].values()) == {"feito"}
    assert r["sessoesLidas"] == [{"sessao": "2026-10-11_14-19-52_vhe_interlagos", "voltas": 23}]
    assert r["resumo"]["referenciasAntes"]["minha_melhor"]["tempo_s"] == 89.389
    assert r["resumo"]["m1"]["disponivel"] is False
    assert recarregou == [True] and r["coachRecarregado"] is True
    assert Path(r["log"]).read_text(encoding="utf-8").startswith("1/7 inventario novo")
    assert estado["ligado"] is True


def test_rodada_parada_numa_trava_nao_tenta_de_novo(tmp_path):
    repo, falso = _repo_falso(tmp_path, FALSO_PARADO)
    recarregou = []
    rodada = _rodada(repo, falso, recarregar=lambda: recarregou.append(True))
    rodada.iniciar()
    r = _esperar(rodada)["rodada"]
    assert r["situacao"] == "parada" and r["codigo"] == 1
    assert r["mensagemDeParada"].startswith("PARADO: o store v2 nao passou")
    assert r["passos"]["6"] == "parado" and r["passos"]["7"] == "pendente"
    assert r["resumo"] is None and recarregou == []
    time.sleep(0.3)
    assert rodada.em_andamento() is False  # nao comecou outra sozinha
