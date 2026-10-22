"""O texto de cada mensagem de radio (pedido 31, Parte B.1), montado uma vez, aqui.

E a escrita que a tela usava em `frontend/src/utils/radio.ts`, trazida para o
backend: o app do jogo, a tela Ao vivo e a tela Volta mostram o mesmo texto.

* **Portugues com acento,** numero com virgula, nomes tecnicos.
* **Microssetor contado a partir de 1** (o indice do coach e a partir de 0:
  `int(progresso x 60)`; o indice 2 e o microssetor 3). O indice interno nao muda.
* **A curva pelo nome tecnico** (C01 a C14) e o lado por extenso (ADR 0003).
* **Duas formas do mesmo numero:**
  - `titulo`, `texto` e `detalhe`: o cartao, com o numero completo;
  - `fala`: o que a voz diz, curta (cerca de 6 a 8 s com a voz a 1,4x).

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

Pedido 36 (Parte C): **todo numero falado tem a sua unidade.**

* o tempo perdido: abaixo de 1 s em decimos ("7 decimos"); de 1 s para cima em segundos,
  com uma casa ("1,2 segundo", "2,5 segundos") (`tempo_falado`);
* o tempo da volta: "1 minuto e 29,1 segundos"; a diferenca da volta: "4,2 segundos atras";
* a distancia: "46 metros", "1,8 metro" (`metros_falados`);
* a velocidade: "minima de 102 contra 128 quilometros por hora" (a unidade uma vez, no
  fim, para os dois numeros).

A unidade nunca sai da fala: quando nao cabe, sai primeiro a segunda causa, depois a
primeira, e por ultimo as palavras que dizem contra quem ("da IA"), nunca a unidade.
O numero que nao e medida (a curva, a volta, o microssetor) nao tem unidade.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence

MICROSSETORES = 60
LADO = {"esq": "esquerda", "dir": "direita"}
REFERENCIA_LONGA = {"volta_ia": "volta da IA", "minha_melhor": "sua melhor volta"}
# Pedido 35: o tempo maximo de cada fala, com a vinheta (o radio fica com a primeira que cabe):
# "cerca de" 6, 7 e 8 s, com 10% de folga. Pedido 36: a frase do coach sobe para 7,3 s, para a
# causa com a unidade caber ("Mínima de 64 contra 94 quilômetros por hora." passava de 6,6 s).
FALA_MAXIMA_S = {"coach": 7.3, "resumo": 7.7, "analise": 8.8, "teste": 8.8}
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


def tempo_falado(segundos: float) -> str:
    """O tempo, falado com a unidade (pedido 36): "7 decimos", "1,0 segundo", "2,5 segundos"."""
    a = abs(float(segundos))
    decimos = int(round(a * 10))
    if decimos < 10:
        if decimos <= 0:
            return "menos de 1 décimo"
        return f"{decimos} décimo{'s' if decimos != 1 else ''}"
    v = round(a, 1)
    return f"{decimal(v, 1)} segundo{'s' if v >= 2 else ''}"


def tempo_de_volta_falado(segundos: float) -> str:
    """O tempo da volta, falado (pedido 36): "1 minuto e 29,1 segundos"."""
    total = round(float(segundos), 1)
    m = int(total // 60)
    s = round(total - 60 * m, 1)
    seg = f"{decimal(s, 1)} segundo{'s' if s >= 2 else ''}"
    if m == 0:
        return seg
    return f"{m} minuto{'s' if m != 1 else ''} e {seg}"


def metros_falados(metros: float) -> str:
    """A distancia, falada (pedido 36): "46 metros"; abaixo de 2 m, com a virgula e no singular, "1,8 metro"."""
    v = round(abs(float(metros)), 1)
    return f"{decimal(v, 1)} metro" if v < 2 else f"{int(round(v))} metros"


def minima_falada(sua: float, ref: float) -> str:
    """As duas minimas, com a unidade uma vez, no fim (pedido 36)."""
    return f"Mínima de {int(round(sua))} contra {int(round(ref))} quilômetros por hora."


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
    alvo = FALA_ALVO.get(tipo or "", "da referência")
    if freada is not None and abs(freada) >= CORTE_FREADA_M:
        lado = "antes" if freada > 0 else "depois"
        base = f"Freia {metros_falados(freada)} {lado}"
        return {"medida": "freada", "valor": round(-freada, 1), "fala": f"{base} {alvo}.", "falaCurta": f"{base}."}
    ref, sua = _numero(ev.get("referenceMinSpeedKmh")), _numero(ev.get("yourMinSpeedKmh"))
    if ref is not None and sua is not None and abs(sua - ref) >= CORTE_MINIMA_KMH:
        fala = minima_falada(sua, ref)
        return {"medida": "minima", "valor": round(sua - ref, 1), "fala": fala, "falaCurta": fala}
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
    quanto = tempo_falado(perda)
    if curva:
        completa = f"{nome}, {curva.lado}: {quanto} {lado_da_perda} {alvo}."
    else:
        completa = f"{nome}: {quanto} {lado_da_perda} {alvo}."
    com_alvo = f"{nome}: {quanto} {lado_da_perda} {alvo}."
    curta = f"{nome}: {quanto} {lado_da_perda}."
    falas = []
    if causa:
        for f in (f"{completa} {causa['fala']}", f"{com_alvo} {causa['fala']}", f"{curta} {causa['fala']}",
                  f"{curta} {causa['falaCurta']}"):
            if f not in falas:
                falas.append(f)
    for f in (completa, com_alvo, curta):
        if f not in falas:
            falas.append(f)
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
    falado = tempo_de_volta_falado(tempo_s)
    abertura = f"Volta {volta}" if volta else "Volta"
    if referencia_s:
        dif = tempo_s - referencia_s
        texto = f"{com_sinal(dif, 3)} para a {rotulo} ({tempo_de_volta(referencia_s)})"
        lado = "atrás" if dif > 0 else "à frente"
        dif_alvo, dif_curta = f"{tempo_falado(dif)} {lado} {alvo}", f"{tempo_falado(dif)} {lado}"
        inteiras = [f"{abertura}: {falado}, {dif_alvo}.", f"{abertura}: {dif_alvo}.", f"{abertura}: {dif_curta}."]
    else:
        texto = "sem referência para comparar"
        inteiras = [f"{abertura}: {falado}."]
    perda_pior = _numero((pior or {}).get("perdaS"))
    tem_pior = bool(pior and pior.get("curva") and perda_pior is not None and perda_pior > 0)
    falas = []
    detalhe = None
    if tem_pior:
        lado_curva = f", {pior['lado']}" if pior.get("lado") else ""
        detalhe = f"mais perdeu na {pior['curva']}{lado_curva}: {com_sinal(perda_pior)}"
        nome = (_nome_falado(pior["curva"]) or pior["curva"]).lower()
        falas += [f"{f} Mais perdeu na {nome}: {tempo_falado(perda_pior)}." for f in inteiras]
    falas += [f for f in inteiras if f not in falas]
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


def _diferenca_falada(medida: str, valor: float, extra: Mapping[str, Any], alvo: str = "") -> str:
    """Uma diferenca da analise, falada como uma frase, no estilo da frase do coach, com a
    unidade (pedido 36): "Freia 46 metros antes da IA.", "Minima de 102 contra 128 quilometros
    por hora.". `alvo` ("da IA") diz contra quem; vazio, a forma curta. O tracado de 2 m para
    cima vai com o numero inteiro, mais curto de falar; o cartao continua com a decimal."""
    contra = f" {alvo}" if alvo else ""
    if medida == "freada":
        return f"Freia {metros_falados(valor)} {'antes' if valor < 0 else 'depois'}{contra}."
    if medida == "minima":
        return minima_falada(extra.get("sua", 0), extra.get("ref", 0))
    if medida == "acelerador":
        return f"Acelera {metros_falados(valor)} {'depois' if valor > 0 else 'antes'}{contra}."
    # "da IA" -> "que a IA"; "da sua melhor" -> "que a sua melhor"
    que = f" que a {alvo[3:] if alvo.startswith('da ') else alvo}" if alvo else ""
    return f"Passa {metros_falados(valor)} mais à {'esquerda' if valor > 0 else 'direita'}{que}."


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
        perdas = " · ".join(f"{decimal(p)} s" for p in c["perdas"])
        linhas.append(f"{c['curva']}, {c['lado']}: perde {decimal(c['perdaMedianaS'])} s por volta ({perdas})"
                      + (f"; {'; '.join(escritas)}" if escritas else ""))

    alvo = FALA_ALVO.get(tipo or "", "da referência")

    def trecho(c: Mapping[str, Any], quantas: int, com_alvo: bool = True) -> str:
        nome = _nome_falado(c["curva"]) or c["curva"]
        difs = {d["medida"]: d for d in c.get("diferencas") or []}
        ditas = [_diferenca_falada(m, difs[m]["valor"], difs[m], alvo if com_alvo else "")
                 for m in c.get("ditas", [])[:quantas] if m in difs]
        base = f"{nome}: perde {tempo_falado(c['perdaMedianaS'])} por volta."
        return base + (" " + " ".join(ditas) if ditas else "")

    # Da mais completa a mais curta: sai a segunda curva, a segunda causa, o "da IA", a abertura
    # e, por ultimo, a primeira causa. A unidade nunca sai.
    abertura = f"Análise das voltas {intervalo}."
    curta = f"Voltas {intervalo}."
    candidatas = []
    if len(curvas) > 1:
        candidatas.append(f"{abertura} {trecho(curvas[0], 2)} {trecho(curvas[1], 2)}")
        candidatas.append(f"{curta} {trecho(curvas[0], 1)} {trecho(curvas[1], 1)}")
    candidatas.append(f"{abertura} {trecho(curvas[0], 2)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 2)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 1)}")
    candidatas.append(f"{curta} {trecho(curvas[0], 1, com_alvo=False)}")
    candidatas.append(trecho(curvas[0], 1, com_alvo=False))
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
