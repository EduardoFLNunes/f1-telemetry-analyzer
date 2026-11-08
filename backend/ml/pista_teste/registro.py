"""Cada gravacao e cada volta numa condicao, pelo `registro.csv` (pedido 47, E.2; ADR 0029, item 6).

O `trocar_linha.ps1` escreve uma linha por troca: `hora,condicao,sha256,arquivo`,
com a hora local em ISO (`2026-11-08T10:15:03`). Uma gravacao pertence a
condicao da ultima troca registrada antes do inicio dela. Um C0 depois de
outra condicao **que teve gravacao** e o **C0 final** (ADR 0029, item 16: uma
troca seguida de outra, sem gravacao entre elas, nao conta).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

C0_FINAL = "C0 final"
CABECALHO = ("hora", "condicao", "sha256", "arquivo")
VOLTAS_QUE_CONTAM = {"C0": 7, "C1": 7, "C2": 7, "C3": 7, "C4": 7, C0_FINAL: 4}


@dataclass(frozen=True)
class Troca:
    hora: datetime
    condicao: str          # C0..C4, ou "C0 final"
    sha256: str
    arquivo: str = ""


def _hora(texto: str) -> datetime:
    return datetime.fromisoformat(str(texto).strip())


def ler(path: Path) -> List[Troca]:
    """As trocas do registro, em ordem de hora, com a condicao como esta escrita (C0 a C4)."""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        linhas = list(csv.DictReader(handle))
    trocas = [Troca(_hora(r["hora"]), r["condicao"].strip(), r["sha256"].strip().lower(), r.get("arquivo", ""))
              for r in linhas]
    for t in trocas:
        if t.condicao not in ("C0", "C1", "C2", "C3", "C4"):
            raise ValueError(f"condicao desconhecida no registro: {t.condicao!r}")
    return sorted(trocas, key=lambda t: t.hora)


def _base(condicao: str) -> str:
    return "C0" if condicao == C0_FINAL else condicao


def rotular(linhas: Sequence[Tuple[datetime, str, str, str]], com_gravacao: Optional[Set[int]] = None) -> List[Troca]:
    """Ordena pela hora e marca como C0 final o C0 que vem depois de outra condicao.

    `com_gravacao` (ADR 0029, item 16): os indices, na ordem da hora, das trocas que tiveram pelo menos
    uma gravacao. So uma troca com gravacao faz o C0 seguinte virar o C0 final; uma troca seguida de
    outra antes de qualquer gravacao nao conta. Sem `com_gravacao`, todas contam.
    """
    out: List[Troca] = []
    outra_antes = False
    for i, (hora, cond, sha, arquivo) in enumerate(sorted(linhas, key=lambda r: r[0])):
        cond = _base(cond)
        if cond not in ("C0", "C1", "C2", "C3", "C4"):
            raise ValueError(f"condicao desconhecida no registro: {cond!r}")
        rotulo = C0_FINAL if cond == "C0" and outra_antes else cond
        if cond != "C0" and (com_gravacao is None or i in com_gravacao):
            outra_antes = True
        out.append(Troca(hora, rotulo, sha, arquivo))
    return out


def _ultima_troca(ordem: Sequence[Troca], inicio: datetime) -> Optional[int]:
    idx = [i for i, t in enumerate(ordem) if t.hora <= inicio]
    return idx[-1] if idx else None


def trocas_rotuladas(sessoes: Mapping[str, datetime], trocas: Sequence[Troca]) -> List[Dict[str, object]]:
    """Cada troca com o rotulo final (C0 final ou nao) e as gravacoes que ela recebeu."""
    ordem = sorted(trocas, key=lambda t: t.hora)
    recebidas: Dict[int, List[str]] = {}
    for sessao, inicio in sessoes.items():
        i = _ultima_troca(ordem, inicio)
        if i is not None:
            recebidas.setdefault(i, []).append(sessao)
    rot = rotular([(t.hora, t.condicao, t.sha256, t.arquivo) for t in ordem], set(recebidas))
    return [{"hora": t.hora.isoformat(), "condicao": r.condicao, "sha256": t.sha256,
             "gravacoes": sorted(recebidas.get(i, [])),
             "nota": "" if recebidas.get(i) else "sem gravacao: nao conta para o C0 final (ADR 0029, item 16)"}
            for i, (t, r) in enumerate(zip(ordem, rot))]


@dataclass(frozen=True)
class Atribuicao:
    sessao: str
    inicio: datetime
    condicao: Optional[str]
    motivo: str = ""


def atribuir(sessoes: Mapping[str, datetime], trocas: Sequence[Troca], esperado: Mapping[str, str]) -> List[Atribuicao]:
    """{sessao: inicio} -> a condicao de cada gravacao. `esperado`: {C0..C4: sha256 do arquivo da condicao}.

    A gravacao pertence a ultima troca antes do inicio dela. O C0 final e decidido depois de saber quais
    trocas tiveram gravacao (`rotular`, item 16 do ADR 0029).
    """
    ordem = sorted(trocas, key=lambda t: t.hora)
    ultima = {sessao: _ultima_troca(ordem, inicio) for sessao, inicio in sessoes.items()}
    com_gravacao = {i for i in ultima.values() if i is not None}
    rot = rotular([(t.hora, t.condicao, t.sha256, t.arquivo) for t in ordem], com_gravacao)
    out = []
    for sessao, inicio in sorted(sessoes.items(), key=lambda kv: kv[1]):
        i = ultima[sessao]
        if i is None:
            out.append(Atribuicao(sessao, inicio, None, "comecou antes da primeira troca registrada"))
            continue
        troca = rot[i]
        base = _base(troca.condicao)
        if esperado.get(base, "").lower() != troca.sha256.lower():
            out.append(Atribuicao(sessao, inicio, None,
                                  f"a troca de {troca.hora.isoformat()} registrou um sha256 que nao e o da {base}"))
            continue
        out.append(Atribuicao(sessao, inicio, troca.condicao))
    return out


@dataclass
class VoltaNaCondicao:
    sessao: str
    sequencia: int
    inicio: float                 # instante da volta (para ordenar), em segundos
    primeira_da_gravacao: bool
    interrompida: bool = False    # a ultima volta da gravacao, sem completar
    papel: str = ""               # "saida", "primeira lancada", "conta", "alem das que contam", "interrompida"


def papeis(condicao: str, voltas: List[VoltaNaCondicao]) -> List[VoltaNaCondicao]:
    """ADR 0029, item 4: a volta de saida (a primeira de cada gravacao) e a primeira lancada ficam fora; contam as seguintes."""
    limite = VOLTAS_QUE_CONTAM[condicao]
    contadas = 0
    lancada_vista = False
    for v in sorted(voltas, key=lambda v: v.inicio):
        if v.primeira_da_gravacao:
            v.papel = "saida"
        elif v.interrompida:
            v.papel = "interrompida"
        elif not lancada_vista:
            v.papel = "primeira lancada"
            lancada_vista = True
        elif contadas < limite:
            v.papel = "conta"
            contadas += 1
        else:
            v.papel = "alem das que contam"
    return sorted(voltas, key=lambda v: v.inicio)


def atribuicoes_por_condicao(atrib: Sequence[Atribuicao]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for a in atrib:
        if a.condicao:
            out.setdefault(a.condicao, []).append(a.sessao)
    return out
