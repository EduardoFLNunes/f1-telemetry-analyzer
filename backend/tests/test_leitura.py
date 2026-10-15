"""Rotas de leitura das telas Sessoes, Volta e Evolucao (pedido 30).

So leem o que o `atualizar_coach` ja gravou. Os testes montam um repositorio
de mentira com os mesmos arquivos e conferem que o que sai e o que esta no
arquivo, sem conta nova; o ultimo confere a volta da conferencia do pedido 30
nos arquivos reais, quando eles existem.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from core.leitura import arquivos

REPO = Path(__file__).resolve().parents[2]


def _escrever(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def _repositorio(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    evolucao = raiz / "data" / "ml" / "evolucao"
    _escrever(evolucao / "resumo.json", {"formato": "evolucao-resumo/1", "sessoes": [{"sessao": "2026-10-05-2"}]})
    _escrever(evolucao / "sessao_2026-10-05-2.json", {"formato": "evolucao-sessao/1", "sessao": "2026-10-05-2",
                                                       "voltas": [{"volta": "g#0008", "tempo_s": 90.629}]})
    _escrever(raiz / "data" / "reference_models" / "vhe_interlagos.json", {
        "geometry_id": "abc", "built_at": "2026-10-10T20:38:13", "lap_count": 43,
        "references": {"volta_ia": {"lap_id": "ia#0013", "lap_seconds": 84.828, "carro": "c"},
                       "minha_melhor": {"lap_id": "eu#0018", "lap_seconds": 89.389, "carro": "c"}},
    })
    # Store v2: duas voltas, fora de ordem na grade, como o parquet pode guardar.
    linhas = []
    for lap_id, desloc in (("g#0008", 0.0), ("ia#0013", 0.5)):
        for i in (3, 0, 2, 1):
            linhas.append({"lap_id": lap_id, "grid_index": i, "elapsed_s": i * 10.0 + desloc, "speed_kmh": 100.0 + i,
                           "throttle": 0.5, "brake": 0.0, "lateral": 0.1 * i, "outra": 1.0})
    ml = raiz / "data" / "ml"
    ml.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_parquet(ml / "laps_grid_v2.parquet", index=False)
    _escrever(ml / "laps_grid_v2_meta.json", {
        "geometry_id": "abc", "grid_size": 4, "track_length": 40.0, "aprovado": True,
        "laps": [{"lap_id": "g#0008", "session_id": "g", "sequence": 8, "game_lap_number": 9, "lap_time_s": 40.2,
                  "replay_lap_id": "rec__g__9", "origem": "humano", "carModel": "c"},
                 {"lap_id": "ia#0013", "session_id": "ia", "sequence": 13, "lap_time_s": 40.7, "origem": "ia"}],
    })
    _escrever(raiz / "data" / "reference_models" / "vhe_interlagos.geometry.json", {
        "version": 1, "geometry_id": "abc", "track_length": 40.0, "step": 10.0, "normal_side": "left",
        "x": [0.0, 10.0, 10.0, 0.0], "z": [0.0, 0.0, 10.0, 10.0], "s": [0.0, 10.0, 20.0, 30.0],
        "normal_x": [0.0, -1.0, 0.0, 1.0], "normal_z": [1.0, 0.0, -1.0, 0.0], "microsector_edges": [0.0, 20.0, 40.0],
    })
    return raiz


def test_evolucao_devolve_os_arquivos_como_estao(tmp_path):
    raiz = _repositorio(tmp_path)
    resumo = arquivos.ler_resumo(raiz)
    assert resumo["disponivel"] and resumo["resumo"]["formato"] == "evolucao-resumo/1"
    assert resumo["arquivosDeSessao"] == ["2026-10-05-2"]
    sessao = arquivos.ler_sessao(raiz, "2026-10-05-2")
    assert sessao["disponivel"] and sessao["sessao"]["voltas"][0]["tempo_s"] == 90.629


def test_sem_arquivo_ou_nome_invalido_diz_por_que(tmp_path):
    raiz = _repositorio(tmp_path)
    assert arquivos.ler_resumo(None)["disponivel"] is False
    assert arquivos.ler_resumo(tmp_path / "vazio")["disponivel"] is False
    assert arquivos.ler_sessao(raiz, "2026-10-09")["disponivel"] is False
    # Nada fora da pasta da evolucao: o nome da sessao e conferido antes de abrir.
    assert "inválido" in arquivos.ler_sessao(raiz, "../../segredo")["motivo"]


def test_referencias_do_modelo_do_coach(tmp_path):
    ref = arquivos.ler_referencias(_repositorio(tmp_path))
    assert ref["disponivel"] and ref["geometryId"] == "abc"
    assert ref["referencias"]["volta_ia"] == {"volta": "ia#0013", "tempoS": 84.828, "carro": "c"}
    assert ref["referencias"]["minha_melhor"]["volta"] == "eu#0018"


def test_volta_do_store_na_ordem_da_grade_e_sem_conta(tmp_path):
    raiz = _repositorio(tmp_path)
    leitor = arquivos.LeitorDoStore()
    volta = leitor.ler_volta(raiz, "g#0008")
    assert volta["disponivel"]
    assert volta["gridIndex"] == [0, 1, 2, 3]
    assert volta["elapsedS"] == [0.0, 10.0, 20.0, 30.0]
    assert volta["lateralM"] == [0.0, 0.1, 0.2, 0.3]
    assert volta["tempoS"] == 40.2 and volta["replayLapId"] == "rec__g__9" and volta["voltaDoJogo"] == 9
    assert volta["passoM"] == 10.0 and volta["geometryId"] == "abc"
    assert "outra" not in volta
    # A segunda leitura vem da memoria, a mesma resposta.
    assert leitor.ler_volta(raiz, "g#0008") is volta


def test_volta_desconhecida_ou_id_invalido(tmp_path):
    raiz = _repositorio(tmp_path)
    leitor = arquivos.LeitorDoStore()
    assert "não está no store" in leitor.ler_volta(raiz, "x#0001")["motivo"]
    assert "inválido" in leitor.ler_volta(raiz, "../x")["motivo"]
    assert leitor.ler_volta(None, "g#0008")["disponivel"] is False


def test_geometria_exportada_sem_cache_fica_sem_relevo(tmp_path):
    geo = arquivos.ler_geometria(_repositorio(tmp_path))
    assert geo["disponivel"] and geo["geometryId"] == "abc"
    assert geo["x"] == [0.0, 10.0, 10.0, 0.0] and geo["bordasDosMicrossetores"] == [0.0, 20.0, 40.0]
    assert geo["elevacaoM"] is None and geo["relevo"].startswith("sem altitude")


@pytest.mark.skipif(not (REPO / "data" / "ml" / "laps_grid_v2.parquet").exists(), reason="store v2 do repositório ausente")
def test_volta_da_conferencia_nos_arquivos_reais():
    """Pedido 30: a volta 8 de 05/10 20:33 e a volta da IA do coach, como o store v2 as guarda."""
    leitor = arquivos.LeitorDoStore()
    volta = leitor.ler_volta(REPO, "2026-10-05_20-33-47_vhe_interlagos#0008")
    assert volta["disponivel"] and volta["pontosDaGrade"] == 2167 and len(volta["elapsedS"]) == 2167
    assert volta["tempoS"] == pytest.approx(90.6288, abs=1e-3)
    assert volta["replayLapId"] == "rec__2026-10-05_20-33-47_vhe_interlagos__9"
    geo = arquivos.ler_geometria(REPO)
    assert geo["geometryId"] == volta["geometryId"] == "0ed16f0dd2225990"
    assert len(geo["x"]) == 2167 and len(geo["bordasDosMicrossetores"]) == 61
    assert geo["elevacaoM"] is not None and len(geo["elevacaoM"]) == 2167
