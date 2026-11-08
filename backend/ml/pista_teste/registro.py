"""Cada gravacao e cada volta numa condicao, pelo `registro.csv` (pedido 47, E.2; ADR 0029, item 6).

O `trocar_linha.ps1` escreve uma linha por troca: `hora,condicao,sha256,arquivo`,
com a hora local em ISO (`2026-11-08T10:15:03`). Uma gravacao pertence a
condicao da ultima troca registrada antes do inicio dela. Um C0 depois de
qualquer outra condicao e o **C0 final**.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

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
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        linhas = list(csv.DictReader(handle))
    return rotular([(_hora(r["hora"]), r["condicao"].strip(), r["sha256"].strip().lower(), r.get("arquivo", ""))
                    for r in linhas])


def rotular(linhas: Sequence[Tuple[datetime, str, str, str]]) -> List[Troca]:
    """Ordena pela hora e marca o C0 que vem depois de outra condicao como C0 final."""
    out: List[Troca] = []
    outra_antes = False
    for hora, cond, sha, arquivo in sorted(linhas, key=lambda r: r[0]):
        if cond not in ("C0", "C1", "C2", "C3", "C4"):
            raise ValueError(f"condicao desconhecida no registro: {cond!r}")
        rotulo = C0_FINAL if cond == "C0" and outra_antes else cond
        outra_antes = outra_antes or cond != "C0"
        out.append(Troca(hora, rotulo, sha, arquivo))
    return out


@dataclass(frozen=True)
class Atribuicao:
    sessao: str
    inicio: datetime
    condicao: Optional[str]
    motivo: str = ""


def atribuir(sessoes: Mapping[str, datetime], trocas: Sequence[Troca], esperado: Mapping[str, str]) -> List[Atribuicao]:
    """{sessao: inicio} -> a condicao de cada gravacao. `esperado`: {C0..C4: sha256 do arquivo da condicao}."""
    ordem = sorted(trocas, key=lambda t: t.hora)
    out = []
    for sessao, inicio in sorted(sessoes.items(), key=lambda kv: kv[1]):
        antes = [t for t in ordem if t.hora <= inicio]
        if not antes:
            out.append(Atribuicao(sessao, inicio, None, "comecou antes da primeira troca registrada"))
            continue
        troca = antes[-1]
        base = "C0" if troca.condicao == C0_FINAL else troca.condicao
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
