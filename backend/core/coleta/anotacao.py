"""A anotacao "Todas as voltas foram minhas" (pedido 32, Parte B.1 e B.2).

Cada gravacao fora do relatorio tem uma origem, pela conferencia da Coleta:

* **indicador de IA gravado** (app 0.3.0 em diante): todas as voltas `humano`
  pelo indicador. Nao precisa de anotacao.
* **sem indicador:** voltas `desconhecida`. Precisa da confirmacao do piloto de
  que todas as voltas foram dele; so estas tem o botao.
* **com voltas da IA ou misturada:** fica como esta, sem botao.

Ao confirmar, a linha entra em `docs/experimentos/anotacoes_de_sessao.csv` do
repositorio configurado, no formato do arquivo, com fim de linha CRLF e a
observacao "anotada pelo app em AAAA-MM-DD". O commit fica para depois: a
anotacao so vale para o coach na proxima rodada do `atualizar_coach`.
"""
from __future__ import annotations

import csv
import io
import re
import threading
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ARQUIVO = Path("docs") / "experimentos" / "anotacoes_de_sessao.csv"
COLUNAS = ["sessao", "origem", "carModel", "anotado_em", "observacao"]
CARRO_PADRAO = "rss_formula_rss_3_v6_2026"
_SESSAO_VALIDA = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[A-Za-z0-9_]+$")
_lock = threading.Lock()

INDICADOR = "indicador"
SEM_INDICADOR = "sem_indicador"
COM_IA = "com_ia"
SEM_CONFERENCIA = "sem_conferencia"


def classificar(conferencia: Optional[Mapping[str, Any]]) -> str:
    """A origem da gravacao pela conferencia: indicador, sem indicador ou com voltas da IA."""
    voltas = list((conferencia or {}).get("voltas") or [])
    if not voltas:
        return SEM_CONFERENCIA
    origens = {str(v.get("origem") or "desconhecida") for v in voltas}
    if origens & {"ia", "misturada"}:
        return COM_IA
    if origens == {"humano"}:
        return INDICADOR
    return SEM_INDICADOR


def ler_anotacoes(repositorio: Path) -> List[Dict[str, str]]:
    caminho = Path(repositorio) / ARQUIVO
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8", newline="") as handle:
        return [dict(linha) for linha in csv.DictReader(handle)]


def linha_da_anotacao(sessao: str, carro: str, hoje: date) -> str:
    """A linha no formato do arquivo (observacao entre aspas, como as outras), com CRLF."""
    dia = hoje.isoformat()
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\r\n", quoting=csv.QUOTE_MINIMAL)
    escritor.writerow([sessao, "humano", carro, dia, f"anotada pelo app em {dia}"])
    texto = buffer.getvalue()
    # As outras linhas poem a observacao entre aspas mesmo sem virgula: mesma forma aqui.
    if not texto.rstrip("\r\n").endswith('"'):
        corpo, _ = texto.rsplit(",", 1)
        texto = f'{corpo},"anotada pelo app em {dia}"\r\n'
    return texto


class AnotacaoRecusada(ValueError):
    pass


def anotar(repositorio: Path, sessao: str, conferencia: Optional[Mapping[str, Any]],
           hoje: Optional[date] = None) -> Dict[str, Any]:
    """Acrescenta a anotacao de uma gravacao sem indicador; devolve a linha gravada."""
    if not _SESSAO_VALIDA.match(sessao or ""):
        raise AnotacaoRecusada(f"nome de sessão inválido: {sessao!r}")
    if (conferencia or {}).get("sessao") not in (None, sessao):
        raise AnotacaoRecusada("a conferência não é desta sessão")
    tipo = classificar(conferencia)
    if tipo == SEM_CONFERENCIA:
        raise AnotacaoRecusada("confira a sessão na aba Coleta de dados antes de anotar")
    if tipo == INDICADOR:
        raise AnotacaoRecusada("esta gravação tem o indicador de IA: não precisa de anotação")
    if tipo == COM_IA:
        raise AnotacaoRecusada("esta gravação tem voltas da IA ou misturadas: não pode ser anotada como sua")
    gravado = ((conferencia or {}).get("gravacao") or {}).get("carModel")
    carro = str(gravado or CARRO_PADRAO)
    caminho = Path(repositorio) / ARQUIVO
    with _lock:
        if any(a.get("sessao") == sessao for a in ler_anotacoes(repositorio)):
            raise AnotacaoRecusada("esta gravação já está anotada")
        linha = linha_da_anotacao(sessao, carro, hoje or date.today())
        if caminho.exists():
            atual = caminho.read_bytes()
            prefixo = b"" if not atual or atual.endswith(b"\n") else b"\r\n"
        else:
            caminho.parent.mkdir(parents=True, exist_ok=True)
            prefixo = (",".join(COLUNAS) + "\r\n").encode("utf-8")
        with caminho.open("ab") as handle:
            handle.write(prefixo + linha.encode("utf-8"))
    return {"sessao": sessao, "linha": linha.rstrip("\r\n"), "arquivo": str(caminho),
            "carro": carro, "carroGravado": bool(gravado), "commit": False}
