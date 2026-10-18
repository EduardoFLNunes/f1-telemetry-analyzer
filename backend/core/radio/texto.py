"""O texto de cada mensagem de radio (pedido 31, Parte B.1), montado uma vez, aqui.

E a escrita que a tela usava em `frontend/src/utils/radio.ts`, trazida para o
backend: o app do jogo, a tela Ao vivo e a tela Volta mostram o mesmo texto.

* **Portugues com acento,** numero com virgula, nomes tecnicos.
* **Microssetor contado a partir de 1** (o indice do coach e a partir de 0:
  `int(progresso x 60)`; o indice 2 e o microssetor 3). O indice interno nao muda.
* **A curva pelo nome tecnico** (C01 a C14) e o lado por extenso (ADR 0003).
* **Duas formas do mesmo numero:**
  - `titulo`, `texto` e `detalhe`: o cartao, com o numero completo;
  - `fala`: o que a voz diz, curta (cerca de 4 a 6 s com a fala a 1,25x).

So escreve o que o coach ja decidiu: a frase, a perda, a freada e a minima vem
do `evidence` do evento, sem conta nova.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

MICROSSETORES = 60
LADO = {"esq": "esquerda", "dir": "direita"}
REFERENCIA_LONGA = {"volta_ia": "volta da IA", "minha_melhor": "sua melhor volta"}
FALA_ALVO = {"volta_ia": "da IA", "minha_melhor": "da sua melhor"}


@dataclass(frozen=True)
class CurvaDaPista:
    """Uma curva na geometria oficial: o nome, o lado e o trecho (do meio da reta ao meio da seguinte)."""

    codigo: str          # C01
    lado: str            # esquerda | direita
    inicio_m: float      # a curva em si (fora dela e reta)
    fim_m: float
    trecho_inicio_m: float
    trecho_fim_m: float


def _numero(valor: Any) -> Optional[float]:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if n == n and abs(n) != float("inf") else None


def decimal(valor: float, casas: int = 2) -> str:
    """0,31 (com `casas` casas e virgula)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def com_sinal(segundos: float, casas: int = 2) -> str:
    sinal = "+" if segundos > 0 else "−" if segundos < 0 else ""
    return f"{sinal}{decimal(abs(segundos), casas)} s"


def tempo_de_volta(segundos: float) -> str:
    """M:SS,mmm."""
    m = int(segundos // 60)
    s = segundos - 60 * m
    return f"{m}:{'0' if s < 10 else ''}{decimal(s, 3)}"


def microssetor_para_o_piloto(indice: int) -> int:
    """Indice do coach (a partir de 0) -> numero que o piloto ve (a partir de 1)."""
    return int(indice) + 1


def s_do_fim_do_microssetor(indice: int, comprimento: float) -> float:
    """Onde o microssetor termina, na geometria oficial: ali o coach fecha a medida e fala."""
    return (int(indice) + 1) * comprimento / MICROSSETORES


def curva_do_ponto(curvas: Sequence[CurvaDaPista], s: float, comprimento: float) -> Optional[CurvaDaPista]:
    """A curva cujo trecho contem `s` (os trechos cobrem a volta inteira)."""
    x = s % comprimento
    for c in curvas:
        a, b = c.trecho_inicio_m, c.trecho_fim_m
        if (a <= b and a <= x < b) or (a > b and (x >= a or x < b)):
            return c
    return None


def _clausula_da_freada(tipo: Optional[str], delta_m: float) -> str:
    metros = abs(round(delta_m))
    lado = "depois" if delta_m > 0 else "antes"
    if tipo == "minha_melhor":
        return "na sua melhor volta você freou no mesmo ponto" if metros < 1 else f"na sua melhor volta você freou {metros} m {lado}"
    quem = "a IA" if tipo == "volta_ia" else "a referência"
    return f"{quem} freia no mesmo ponto que você" if metros < 1 else f"{quem} freia {metros} m {lado} de você"


def _clausula_da_minima(tipo: Optional[str], ref_kmh: float, sua_kmh: float) -> str:
    ref, sua = round(ref_kmh), round(sua_kmh)
    if tipo == "volta_ia":
        return f"mínima da IA {ref} km/h, a sua {sua} km/h"
    if tipo == "minha_melhor":
        return f"mínima na sua melhor volta {ref} km/h, agora {sua} km/h"
    return f"mínima na referência {ref} km/h, a sua {sua} km/h"


def mensagem_de_diferenca(evento: Mapping[str, Any], curvas: Sequence[CurvaDaPista],
                          comprimento: float) -> Optional[Dict[str, Any]]:
    """Uma frase de diferenca do coach (`coaching_event`) como mensagem de radio; None sem os numeros."""
    ev = evento.get("evidence") if isinstance(evento.get("evidence"), Mapping) else None
    if not ev:
        return None
    indice = _numero(ev.get("microsector"))
    sua = _numero(ev.get("yourSeconds"))
    ref = _numero(ev.get("referenceSeconds"))
    if ref is None:
        ref = _numero(ev.get("bestSeconds"))
    perda = _numero(ev.get("lossSeconds"))
    if perda is None and sua is not None and ref is not None:
        perda = sua - ref
    if indice is None or sua is None or ref is None or perda is None:
        return None
    tipo = ev.get("referenceKind") if isinstance(ev.get("referenceKind"), str) else None
    rotulo = ev.get("referenceLabel") if isinstance(ev.get("referenceLabel"), str) and ev.get("referenceLabel") else (
        REFERENCIA_LONGA.get(tipo or "", "referência"))
    s = s_do_fim_do_microssetor(int(indice), comprimento)
    curva = curva_do_ponto(curvas, s - 1.0, comprimento)
    numero = microssetor_para_o_piloto(int(indice))
    onde = f"{curva.codigo}, {curva.lado}" if curva else f"microssetor {numero}"
    partes = [f"{decimal(sua)} s contra {decimal(ref)} s"]
    freada = _numero(ev.get("brakeDeltaM"))
    if freada is not None:
        partes.append(_clausula_da_freada(tipo, freada))
    min_ref, min_sua = _numero(ev.get("referenceMinSpeedKmh")), _numero(ev.get("yourMinSpeedKmh"))
    if min_ref is not None and min_sua is not None:
        partes.append(_clausula_da_minima(tipo, min_ref, min_sua))
    alvo = FALA_ALVO.get(tipo or "", "da referência")
    lado_da_perda = "atrás" if perda > 0 else "à frente"
    nome_falado = f"Curva {int(curva.codigo[1:])}, {curva.lado}" if curva else f"Microssetor {numero}"
    return {
        "origem": "coach",
        "titulo": onde,
        "texto": f"{com_sinal(perda)} para a {rotulo} no microssetor {numero}",
        "detalhe": " · ".join(partes),
        "fala": f"{nome_falado}: {decimal(abs(perda))} {lado_da_perda} {alvo}.",
        "microssetor": numero,
        "curva": curva.codigo if curva else None,
        "s": round(s, 1),
        "perdaS": round(perda, 3),
        "volta": int(_numero(evento.get("lap_number")) or 0) or None,
    }


def mensagem_de_resumo(volta: Optional[int], tempo_s: float, referencia_s: Optional[float],
                       tipo: Optional[str]) -> Dict[str, Any]:
    """O resumo na linha de chegada: o tempo da volta e a diferenca para a referencia escolhida."""
    rotulo = REFERENCIA_LONGA.get(tipo or "", "referência")
    alvo = FALA_ALVO.get(tipo or "", "da referência")
    m = int(tempo_s // 60)
    s = tempo_s - 60 * m
    falado = f"{m} minuto{'s' if m != 1 else ''} e {decimal(s, 1)}"
    if referencia_s:
        dif = tempo_s - referencia_s
        texto = f"{com_sinal(dif, 3)} para a {rotulo} ({tempo_de_volta(referencia_s)})"
        fala_dif = f" {decimal(abs(dif))} {'atrás' if dif > 0 else 'à frente'} {alvo}."
    else:
        texto, fala_dif = "sem referência para comparar", ""
    return {
        "origem": "resumo",
        "titulo": f"Volta {volta}: {tempo_de_volta(tempo_s)}" if volta else f"Volta: {tempo_de_volta(tempo_s)}",
        "texto": texto,
        "detalhe": None,
        "fala": f"Volta {volta}, {falado}.{fala_dif}" if volta else f"Volta em {falado}.{fala_dif}",
        "microssetor": None,
        "curva": None,
        "s": 0.0,
        "perdaS": round(tempo_s - referencia_s, 3) if referencia_s else None,
        "volta": volta,
        "tempoS": round(tempo_s, 3),
    }


def mensagem_de_teste() -> Dict[str, Any]:
    return {
        "origem": "teste",
        "titulo": "Rádio de teste",
        "texto": "Se você está vendo e ouvindo isto no jogo, o rádio funciona.",
        "detalhe": "mensagem mandada pela tela Sistema",
        "fala": "Teste do rádio. Se você me ouve, está tudo certo.",
        "microssetor": None,
        "curva": None,
        "s": None,
        "perdaS": None,
        "volta": None,
    }
