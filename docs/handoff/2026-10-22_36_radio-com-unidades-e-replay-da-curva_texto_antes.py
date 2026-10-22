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

Pedido 35 (ADR 0021):

* **a frase do coach diz a causa principal na voz** (`causa_principal`): a freada,
  quando a diferenca do ponto de freada passa do corte; senao a minima, quando passa
  do dela (os cortes da analise, `core/radio/analise.py`);
* **o resumo diz a curva em que a volta mais perdeu,** com a perda;
* **a analise das voltas** (`mensagem_de_analise`), a cada 3 voltas validas;
* **cada mensagem traz as falas em ordem, da mais completa a mais curta** (`falas`), e
  o tempo maximo (`falaMaxS`): o radio gera o audio e fica com a primeira que cabe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

MICROSSETORES = 60
LADO = {"esq": "esquerda", "dir": "direita"}
REFERENCIA_LONGA = {"volta_ia": "volta da IA", "minha_melhor": "sua melhor volta"}
# Pedido 35: o tempo maximo de cada fala, com a vinheta (o radio fica com a primeira que cabe):
# "cerca de" 6, 7 e 8 s, com 10% de folga.
FALA_MAXIMA_S = {"coach": 6.6, "resumo": 7.7, "analise": 8.8, "teste": 8.8}
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


def _nome_falado(codigo: Optional[str]) -> Optional[str]:
    return f"Curva {int(codigo[1:])}" if codigo and codigo[1:].isdigit() else None


def causa_principal(ev: Mapping[str, Any], tipo: Optional[str]) -> Optional[Dict[str, Any]]:
    """A causa principal de uma frase do coach, para a voz (pedido 35), ou None.

    A freada, quando a diferenca do ponto de freada passa de `CORTE_FREADA_M`; senao a
    minima, quando passa de `CORTE_MINIMA_KMH`. Abaixo dos dois, a diferenca esta dentro
    da variacao normal do piloto de uma volta para outra, e a voz nao diz causa.
    `brakeDeltaM` do coach e "freada da referencia menos a sua": positivo = voce freou antes.
    """
    from .analise import CORTE_FREADA_M, CORTE_MINIMA_KMH

    freada = _numero(ev.get("brakeDeltaM"))
    if freada is not None and abs(freada) >= CORTE_FREADA_M:
        metros = int(round(abs(freada)))
        lado = "antes" if freada > 0 else "depois"
        return {"medida": "freada", "valor": round(-freada, 1), "fala": f"Freia {metros} metros {lado}."}
    ref, sua = _numero(ev.get("referenceMinSpeedKmh")), _numero(ev.get("yourMinSpeedKmh"))
    if ref is not None and sua is not None and abs(sua - ref) >= CORTE_MINIMA_KMH:
        return {"medida": "minima", "valor": round(sua - ref, 1),
                "fala": f"Mínima {int(round(sua))} contra {int(round(ref))}."}
    return None


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
    nome = _nome_falado(curva.codigo) if curva else f"Microssetor {numero}"
    causa = causa_principal(ev, tipo)
    if curva:
        completa = f"{nome}, {curva.lado}: {decimal(abs(perda))} {lado_da_perda} {alvo}."
    else:
        completa = f"{nome}: {decimal(abs(perda))} {lado_da_perda} {alvo}."
    curta = f"{nome}: {decimal(abs(perda))} {lado_da_perda}."
    mais_curta = f"{nome}: {decimal(abs(perda), 1)} {lado_da_perda}."
    falas = [f"{completa} {causa['fala']}", f"{curta} {causa['fala']}", f"{mais_curta} {causa['fala']}"] if causa else []
    falas += [completa, curta]
    return {
        "origem": "coach",
        "titulo": onde,
        "texto": f"{com_sinal(perda)} para a {rotulo} no microssetor {numero}",
        "detalhe": " · ".join(partes),
        "fala": falas[0],
        "falas": falas,
        "falaMaxS": FALA_MAXIMA_S["coach"],
        "causa": causa,
        "microssetor": numero,
        "curva": curva.codigo if curva else None,
        "s": round(s, 1),
        "perdaS": round(perda, 3),
        "volta": int(_numero(evento.get("lap_number")) or 0) or None,
    }


def mensagem_de_resumo(volta: Optional[int], tempo_s: float, referencia_s: Optional[float],
                       tipo: Optional[str], pior: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """O resumo na linha de chegada: o tempo da volta, a diferenca para a referencia escolhida e,
    desde o pedido 35, a curva em que a volta mais perdeu (`pior`: curva, lado e perda)."""
    rotulo = REFERENCIA_LONGA.get(tipo or "", "referência")
    alvo = FALA_ALVO.get(tipo or "", "da referência")
    volta = int(volta) if _numero(volta) is not None else None
    m = int(tempo_s // 60)
    s = tempo_s - 60 * m
    falado = f"{m} minuto{'s' if m != 1 else ''} e {decimal(s, 1)}"
    curto = f"{m} e {decimal(s, 1)}"
    if referencia_s:
        dif = tempo_s - referencia_s
        texto = f"{com_sinal(dif, 3)} para a {rotulo} ({tempo_de_volta(referencia_s)})"
        lado = "atrás" if dif > 0 else "à frente"
        fala_dif, fala_dif_curta = f" {decimal(abs(dif))} {lado} {alvo}.", f" {decimal(abs(dif), 1)} {lado}."
    else:
        texto, fala_dif, fala_dif_curta = "sem referência para comparar", "", ""
    abertura = f"Volta {volta}" if volta else "Volta"
    perda_pior = _numero((pior or {}).get("perdaS"))
    tem_pior = bool(pior and pior.get("curva") and perda_pior is not None and perda_pior > 0)
    falas = []
    detalhe = None
    if tem_pior:
        lado_curva = f", {pior['lado']}" if pior.get("lado") else ""
        detalhe = f"mais perdeu na {pior['curva']}{lado_curva}: {com_sinal(perda_pior)}"
        nome = (_nome_falado(pior["curva"]) or pior["curva"]).lower()
        falas += [f"{abertura}, {falado}.{fala_dif} Mais perdeu na {nome}: {decimal(perda_pior, 1)}.",
                  f"{abertura}: {curto},{fala_dif_curta[:-1]}. Mais perdeu na {nome}: {decimal(perda_pior, 1)}.",
                  f"{abertura},{fala_dif_curta[:-1]}. Mais perdeu na {nome}: {decimal(perda_pior, 1)}."]
    falas += [f"{abertura}, {falado}.{fala_dif}", f"{abertura}, {curto}.{fala_dif_curta}"]
    return {
        "origem": "resumo",
        "titulo": f"Volta {volta}: {tempo_de_volta(tempo_s)}" if volta else f"Volta: {tempo_de_volta(tempo_s)}",
        "texto": texto,
        "detalhe": detalhe,
        "fala": falas[0],
        "falas": falas,
        "falaMaxS": FALA_MAXIMA_S["resumo"],
        "piorCurva": dict(pior) if tem_pior else None,
        "microssetor": None,
        "curva": pior["curva"] if tem_pior else None,
        "s": 0.0,
        "perdaS": round(tempo_s - referencia_s, 3) if referencia_s else None,
        "volta": volta,
        "tempoS": round(tempo_s, 3),
    }


def _diferenca_falada(medida: str, valor: float, extra: Mapping[str, Any]) -> str:
    """Uma diferenca da analise, falada como uma frase, no estilo da frase do coach
    ("Freia 54 metros antes.", "Minima 64 contra 94."; fechamento do pedido 35)."""
    if medida == "freada":
        return f"Freia {int(round(abs(valor)))} metros {'antes' if valor < 0 else 'depois'}."
    if medida == "minima":
        return f"Mínima {int(round(extra.get('sua', 0)))} contra {int(round(extra.get('ref', 0)))}."
    if medida == "acelerador":
        return f"Acelera {int(round(abs(valor)))} metros {'depois' if valor > 0 else 'antes'}."
    # Abaixo de 2 m, com a virgula e no singular ("1,8 metro"); de 2 m para cima, o numero inteiro,
    # mais curto de falar ("8 metros"). O cartao continua com a decimal.
    metros = round(abs(valor), 1)
    quanto = f"{decimal(metros, 1)} metro" if metros < 2 else f"{int(round(metros))} metros"
    return f"Passa {quanto} mais à {'esquerda' if valor > 0 else 'direita'}."


def _diferenca_escrita(medida: str, valor: float, extra: Mapping[str, Any]) -> str:
    if medida == "freada":
        return f"freada {int(round(abs(valor)))} m {'antes' if valor < 0 else 'depois'}"
    if medida == "minima":
        return f"mínima {int(round(extra.get('sua', 0)))} contra {int(round(extra.get('ref', 0)))} km/h"
    if medida == "acelerador":
        return f"acelerador cheio {int(round(abs(valor)))} m {'depois' if valor > 0 else 'antes'}"
    return f"traçado {decimal(abs(valor), 1)} m mais à {'esquerda' if valor > 0 else 'direita'}"


def mensagem_de_analise(analise: Mapping[str, Any], tipo: Optional[str],
                        referencia_lap_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A analise das 3 ultimas voltas validas (pedido 35, ADR 0021); None sem curva para dizer.

    Sempre a diferenca medida contra uma volta real (ADR 0012), nunca um ganho prometido.
    O cartao mostra as curvas com todos os numeros; a voz, as diferencas que mais pesam
    (`ditas`, as que passam do corte, no maximo 2 por curva).
    """
    curvas = list(analise.get("curvas") or [])
    voltas = [int(v) for v in analise.get("voltas") or [] if _numero(v) is not None]
    if not curvas or len(voltas) < 2:
        return None
    rotulo = REFERENCIA_LONGA.get(tipo or "", "referência")
    seguidas = voltas == list(range(voltas[0], voltas[0] + len(voltas)))
    intervalo = f"{voltas[0]} a {voltas[-1]}" if seguidas else ", ".join(str(v) for v in voltas[:-1]) + f" e {voltas[-1]}"
    linhas = []
    for c in curvas:
        escritas = [_diferenca_escrita(d["medida"], d["valor"], d) for d in c.get("diferencas") or []]
        perdas = " · ".join(decimal(p) for p in c["perdas"])
        linhas.append(f"{c['curva']}, {c['lado']}: perde {decimal(c['perdaMedianaS'])} s por volta ({perdas})"
                      + (f"; {'; '.join(escritas)}" if escritas else ""))

    def trecho(c: Mapping[str, Any], quantas: int) -> str:
        nome = _nome_falado(c["curva"]) or c["curva"]
        difs = {d["medida"]: d for d in c.get("diferencas") or []}
        ditas = [_diferenca_falada(m, difs[m]["valor"], difs[m]) for m in c.get("ditas", [])[:quantas] if m in difs]
        base = f"{nome}: {decimal(c['perdaMedianaS'], 1)} por volta."
        return base + (" " + " ".join(ditas) if ditas else "")

    abertura = f"Análise das voltas {intervalo}."
    curta = f"Voltas {intervalo}."
    candidatas = []
    if len(curvas) > 1:
        candidatas.append(f"{abertura} {trecho(curvas[0], 2)} {trecho(curvas[1], 2)}")
        candidatas.append(f"{curta} {trecho(curvas[0], 1)} {trecho(curvas[1], 1)}")
    candidatas.append(f"{abertura} {trecho(curvas[0], 2)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 2)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 1)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 0)}")
    falas = []
    for f in candidatas:
        if f not in falas:
            falas.append(f)
    principal = curvas[0]
    texto = " · ".join(f"{c['curva']} perde {decimal(c['perdaMedianaS'])} s por volta" for c in curvas)
    return {
        "origem": "analise",
        "titulo": f"Análise das voltas {intervalo}",
        "texto": f"{texto}, contra a {rotulo}",
        "detalhe": " | ".join(linhas),
        "linhas": linhas,
        "fala": falas[0],
        "falas": falas,
        "falaMaxS": FALA_MAXIMA_S["analise"],
        "microssetor": None,
        "curva": principal["curva"],
        "s": None,
        "perdaS": principal["perdaMedianaS"],
        "volta": voltas[-1],
        "voltasAnalisadas": voltas,
        "curvasDaAnalise": curvas,
        "referencia": {"tipo": tipo, "volta": referencia_lap_id},
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
