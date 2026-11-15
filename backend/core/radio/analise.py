"""A analise das voltas do radio (pedido 35, ADR 0021): onde o piloto perde tempo e o que faz diferente.

So le o que ja e medido; nenhuma conta de fisica nova:

* **a volta do piloto:** a grade que a volta ao vivo guarda, ponto a ponto da
  geometria oficial, com a projecao que o coach ja faz (`VoltaAoVivo`): o relogio
  desde a linha, a velocidade, os pedais e a posicao lateral. Os buracos entre dois
  pontos medidos sao preenchidos por interpolacao;
* **a referencia:** a volta escolhida na Coleta, do store v2 (as mesmas colunas);
* **as medidas por curva:** as do relatorio de evolucao (`ml.comparison.evolution`):
  - a perda no trecho da curva (do meio da reta anterior ao meio da seguinte);
  - o ponto de freada (o freio passa de 0,15, do apice anterior ao apice);
  - a minima dentro da curva;
  e, com os mesmos canais da grade (pedido 45, C.2), a velocidade no fim da curva e as partes da
  perda (`partes_da_perda`), para dizer onde e por que a curva perdeu (`causa_da_curva`);
  e duas montadas aqui com os mesmos canais da grade:
  - **a volta ao acelerador cheio:** o primeiro ponto, do apice ao fim do trecho, com
    o acelerador em `ACELERADOR_CHEIO` ou mais;
  - **o tracado:** a posicao lateral no ponto da minima da referencia.

Toda diferenca e "volta menos referencia": negativa na freada = freou antes; positiva
no acelerador = voltou ao acelerador depois; positiva no tracado = mais a esquerda
(a convencao do `ml`, ADR 0003). E sempre a diferenca medida contra uma volta real,
nunca um ganho prometido (ADR 0012).
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

# O acelerador "cheio": um pouco abaixo de 1, porque o pedal raramente fica em 1,00 exato.
ACELERADOR_CHEIO = 0.95
# Uma volta da grade so entra se o relogio foi medido em pelo menos esta fracao dos pontos.
COBERTURA_MINIMA = 0.90

# A analise (ADR 0021):
VOLTAS_POR_ANALISE = 3
CURVAS_POR_ANALISE = 2
VOLTAS_PERDIDAS_MINIMAS = 2          # a curva tem de ter sido perdida em 2 das 3 voltas
PERDA_QUE_CONTA_S = 0.0              # perdida = perda acima de zero contra a referencia
# Pedido 36 (decisao do Eduardo, 22/10): a volta em que uma curva perde mais que isto contra a
# referencia teve uma rodada ou uma saida de pista. Ela nao conta para a analise das voltas, e o
# resumo dela nao cita a curva. So uma regra do radio: o coach e o store nao mudam.
PERDA_DE_RODADA_S = 5.0


def teve_rodada(medidas) -> bool:
    """Alguma curva da volta perdeu mais de `PERDA_DE_RODADA_S` contra a referencia."""
    return any(float(m.get("perdaS") or 0.0) > PERDA_DE_RODADA_S for m in medidas or [])
DIFERENCAS_FALADAS_POR_CURVA = 2

# Os cortes de cada diferenca: abaixo deles, a diferenca esta dentro da variacao normal
# do proprio piloto de uma volta para outra, e nao e dita. Cada corte e a mediana do
# desvio-padrao volta a volta daquela medida, por curva e por sessao, nas voltas humanas
# do store v2 de 11/10 a 18/10 (pedido 35: 14,7 m, 7,7 km/h, 10,7 m e 1,76 m),
# arredondada. Na analise vale a mediana de 3 voltas, cujo ruido e menor que o de uma
# volta; o corte de uma volta inteira e, entao, conservador. Escrito em
# docs/realidade_aumentada.md.
CORTE_FREADA_M = 15.0
CORTE_MINIMA_KMH = 8.0
CORTE_ACELERADOR_M = 10.0
CORTE_TRACADO_M = 1.8
# Pedido 45 (C.2), registrado antes de rodar as sessoes. A velocidade no fim da curva e a mesma
# grandeza da minima, medida do mesmo jeito (a velocidade da grade, uma volta contra a outra, num
# ponto da curva): o que o corte da minima mede (a variacao normal da velocidade do piloto numa
# curva, de uma volta para outra) vale para ela. Por isso, o mesmo valor, sem um ajuste proprio.
CORTE_SAIDA_KMH = CORTE_MINIMA_KMH
# Pedido 45 (C.2): abaixo disto, nenhuma curva e citada: a voz arredonda para decimos, e menos de 1
# decimo nao diz nada. O tracado usa o corte que a analise ja tinha (CORTE_TRACADO_M).
PERDA_MINIMA_PARA_CITAR_S = 0.1


@dataclass
class Pista:
    """A geometria do ML (a mesma grade do store e da volta ao vivo) e os trechos das 14 curvas."""

    track: Any
    segmentos: List[Any]

    @classmethod
    def da_geometria(cls, track: Any) -> "Pista":
        from ml.comparison.evolution import corner_segments
        from ml.track.corners import detect_corners

        return cls(track=track, segmentos=corner_segments(track, detect_corners(track)))


def _serie(valores: Sequence[Optional[float]], interpolar: bool = True) -> np.ndarray:
    """Lista com buracos (None) -> serie completa: interpolada (ou segurando o ultimo valor)."""
    v = np.array([np.nan if x is None else float(x) for x in valores], dtype=float)
    ok = np.isfinite(v)
    if not ok.any():
        return v
    idx = np.arange(v.size)
    if interpolar:
        return np.interp(idx, idx[ok], v[ok])
    # Segura o ultimo valor medido (pedais: um buraco nao inventa um meio-termo).
    ultimo = np.maximum.accumulate(np.where(ok, idx, -1))
    primeiro = int(np.argmax(ok))
    ultimo[ultimo < 0] = primeiro
    return v[ultimo]


def cobertura(linhas: Dict[str, Sequence[Optional[float]]]) -> float:
    elapsed = linhas.get("elapsed") or []
    if not elapsed:
        return 0.0
    return sum(1 for x in elapsed if x is not None) / len(elapsed)


def grade(linhas: Dict[str, Sequence[Optional[float]]]) -> Dict[str, np.ndarray]:
    """As linhas da volta ao vivo (ou do store, com os nomes de la) como series completas."""
    nomes = {"elapsed": ("elapsed", "elapsedS"), "velocidade": ("velocidade", "velocidadeKmh"),
             "acelerador": ("acelerador",), "freio": ("freio",), "lateral": ("lateral", "lateralM")}
    out = {}
    for nome, chaves in nomes.items():
        valores = next((linhas[c] for c in chaves if c in linhas), None)
        if valores is None:
            raise ValueError(f"a volta nao tem a linha {nome}")
        out[nome] = _serie(valores, interpolar=nome not in ("acelerador", "freio"))
    return out


def _primeiro_acelerador_cheio(acelerador: np.ndarray, track: Any, inicio_s: float, fim_s: float) -> Optional[float]:
    from ml.comparison.lap_vs_reference import _window

    indices = _window(track, inicio_s, fim_s)
    cheio = np.flatnonzero(np.nan_to_num(acelerador[indices]) >= ACELERADOR_CHEIO)
    return float(track.s[indices[cheio[0]]]) if cheio.size else None


def medidas_da_volta(volta: Dict[str, np.ndarray], total: float, ref: Dict[str, np.ndarray], ref_total: float,
                     pista: Pista) -> List[Dict[str, Any]]:
    """Por curva: a perda e as quatro diferencas (volta menos referencia)."""
    from ml.comparison.evolution import braking_point, segment_time
    from ml.comparison.lap_vs_reference import _signed_distance, _window

    track = pista.track
    out = []
    for k, seg in enumerate(pista.segmentos):
        corner = seg.corner
        anterior = pista.segmentos[k - 1].corner.apex_s
        perda = segment_time(volta["elapsed"], total, track, seg) - segment_time(ref["elapsed"], ref_total, track, seg)
        freada_v = braking_point(volta["freio"], track, anterior, corner.apex_s)
        freada_r = braking_point(ref["freio"], track, anterior, corner.apex_s)
        dentro = _window(track, corner.start_s, corner.end_s)
        min_v = float(np.nanmin(volta["velocidade"][dentro]))
        min_r = float(np.nanmin(ref["velocidade"][dentro]))
        ponto_min_ref = int(dentro[int(np.nanargmin(ref["velocidade"][dentro]))])
        acel_v = _primeiro_acelerador_cheio(volta["acelerador"], track, corner.apex_s, seg.end_s)
        acel_r = _primeiro_acelerador_cheio(ref["acelerador"], track, corner.apex_s, seg.end_s)
        fim = int(track.index_of(corner.end_s))
        saida_v, saida_r = float(volta["velocidade"][fim]), float(ref["velocidade"][fim])
        out.append({
            "curva": corner.label[:3],
            "lado": "esquerda" if corner.label.endswith("esq") else "direita",
            "perdaS": round(float(perda), 3),
            "freadaM": round(_signed_distance(track, freada_v, freada_r), 1)
            if freada_v is not None and freada_r is not None else None,
            "minimaKmh": round(min_v - min_r, 1),
            "minimaSuaKmh": round(min_v, 1),
            "minimaRefKmh": round(min_r, 1),
            "aceleradorM": round(_signed_distance(track, acel_v, acel_r), 1)
            if acel_v is not None and acel_r is not None else None,
            "tracadoM": round(float(volta["lateral"][ponto_min_ref] - ref["lateral"][ponto_min_ref]), 2),
            "sDaCurva": round(float(corner.apex_s), 1),
            # Pedido 45 (C.2): a velocidade no fim da curva e as partes da perda.
            "saidaKmh": round(saida_v - saida_r, 1),
            "saidaSuaKmh": round(saida_v, 1),
            "saidaRefKmh": round(saida_r, 1),
            "trechos": partes_da_perda(track, seg, volta, total, ref, ref_total, freada_v, freada_r, ponto_min_ref),
        })
    return out


def partes_da_perda(track: Any, seg: Any, volta: Dict[str, np.ndarray], total: float, ref: Dict[str, np.ndarray],
                    ref_total: float, freada_v: Optional[float], freada_r: Optional[float],
                    ponto_min_ref: int) -> Dict[str, float]:
    """Pedido 45 (C.2): a perda da curva, dividida nas separacoes da diferenca acumulada do pedido 43.

    A diferenca acumulada (a sua volta menos a referencia, desde a entrada do trecho) comeca em zero e
    termina na perda da curva. As separacoes sao as de `replay.secoes`: a primeira freada, a minima da
    referencia e o fim da curva. As partes somam a perda:

    * `reta`: da entrada do trecho a primeira freada (o que veio da curva anterior: nao e causa desta);
    * `freada`: da primeira freada a minima da referencia;
    * `minima`: da minima da referencia ao fim da curva;
    * `saida`: do fim da curva ao fim do trecho.

    Sem freada nas duas voltas (uma curva de pe embaixo), a parte `freada` fica vazia.
    """
    from ml.comparison.evolution import time_at

    L = float(track.length)
    comprimento = float(np.mod(seg.end_s - seg.start_s, L))

    def desde_a_entrada(s: float) -> float:
        return min(float(np.mod(s - seg.start_s, L)), comprimento)

    def diferenca(d: float) -> float:
        def relogio(elapsed: np.ndarray, tot: float) -> float:
            t = float(np.mod(time_at(elapsed, tot, track, seg.start_s + d) - time_at(elapsed, tot, track, seg.start_s), tot))
            return t - tot if t > 0.9 * tot and d < comprimento else t
        return relogio(volta["elapsed"], total) - relogio(ref["elapsed"], ref_total)

    d_min = desde_a_entrada(float(track.s[ponto_min_ref]))
    d_fim = max(desde_a_entrada(float(seg.corner.end_s)), d_min)
    freadas = [desde_a_entrada(s) for s in (freada_v, freada_r) if s is not None]
    d_freada = min(min(freadas), d_min) if freadas else d_min
    no_freada, no_min, no_fim, no_total = diferenca(d_freada), diferenca(d_min), diferenca(d_fim), diferenca(comprimento)
    return {"reta": round(no_freada, 3), "freada": round(no_min - no_freada, 3), "minima": round(no_fim - no_min, 3),
            "saida": round(no_total - no_fim, 3)}


def causa_da_curva(medida: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pedido 45 (C.2): o trecho da curva com a maior parte da perda e a medida desse trecho, se ela
    passa do corte. `medida` fica None quando o trecho nao tem causa acima do corte (a voz diz so o
    trecho); None sem nenhum trecho que perdeu.

    * freada: o ponto de freada, antes ou depois da referencia;
    * minima: a minima abaixo da referencia; senao, o tracado no apice, por fora ou por dentro (ADR
      0003: positivo = mais a esquerda; numa curva a esquerda, mais a direita e por fora);
    * saida: a velocidade mais baixa no fim da curva.

    Uma minima ou uma saida mais rapidas que a referencia nao explicam uma perda: nao sao causa.
    """
    partes = medida.get("trechos") or {}
    candidatos = {k: float(partes.get(k) or 0.0) for k in ("freada", "minima", "saida")}
    trecho = max(candidatos, key=lambda k: candidatos[k])
    if candidatos[trecho] <= 0:
        return None
    out: Dict[str, Any] = {"trecho": trecho, "perdaTrechoS": round(candidatos[trecho], 3), "medida": None, "valor": None}
    if trecho == "freada":
        v = medida.get("freadaM")
        if v is not None and abs(float(v)) >= CORTE_FREADA_M:
            out.update(medida="freada", valor=float(v))
    elif trecho == "minima":
        v = medida.get("minimaKmh")
        lateral = medida.get("tracadoM")
        if v is not None and float(v) <= -CORTE_MINIMA_KMH:
            out.update(medida="minima", valor=float(v))
        elif lateral is not None and abs(float(lateral)) >= CORTE_TRACADO_M:
            a_esquerda = float(lateral) > 0
            por_dentro = a_esquerda == (medida.get("lado") == "esquerda")
            out.update(medida="tracado", valor=float(lateral), lado="dentro" if por_dentro else "fora")
    else:
        v = medida.get("saidaKmh")
        if v is not None and float(v) <= -CORTE_SAIDA_KMH:
            out.update(medida="saida", valor=float(v))
    return out


def curva_da_volta(medidas: Optional[Sequence[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    """Pedido 45 (C.2): a curva que mais perdeu, com a mesma perda da analise e da grade, e a causa.
    Abaixo de `PERDA_MINIMA_PARA_CITAR_S`, nenhuma curva e citada."""
    if not medidas:
        return None
    m = max(medidas, key=lambda x: x["perdaS"])
    if float(m["perdaS"]) < PERDA_MINIMA_PARA_CITAR_S:
        return None
    return {"curva": m["curva"], "lado": m["lado"], "perdaS": m["perdaS"], "causa": causa_da_curva(m),
            "sDaCurva": m.get("sDaCurva")}


def _mediana(valores: Sequence[Optional[float]]) -> Optional[float]:
    v = [float(x) for x in valores if x is not None]
    return statistics.median(v) if v else None


@dataclass
class Diferenca:
    medida: str          # freada | minima | acelerador | tracado
    valor: float         # mediana das 3 voltas (volta menos referencia)
    peso: float          # quantas vezes o corte
    extra: Dict[str, float] = field(default_factory=dict)


def diferencas_da_curva(medidas: Sequence[Dict[str, Any]]) -> List[Diferenca]:
    """As diferencas de uma curva nas 3 voltas (medianas), da que mais pesa para a que menos pesa."""
    out = []
    cortes = (("freada", "freadaM", CORTE_FREADA_M), ("minima", "minimaKmh", CORTE_MINIMA_KMH),
              ("acelerador", "aceleradorM", CORTE_ACELERADOR_M), ("tracado", "tracadoM", CORTE_TRACADO_M))
    for nome, chave, corte in cortes:
        valor = _mediana([m.get(chave) for m in medidas])
        if valor is None:
            continue
        extra = {}
        if nome == "minima":
            extra = {"sua": _mediana([m.get("minimaSuaKmh") for m in medidas]) or 0.0,
                     "ref": _mediana([m.get("minimaRefKmh") for m in medidas]) or 0.0}
        out.append(Diferenca(nome, float(valor), abs(float(valor)) / corte, extra))
    return sorted(out, key=lambda d: -d.peso)


def analisar(voltas: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """A analise de 3 voltas validas: ate 2 curvas, so as perdidas em 2 das 3, pela maior perda mediana.

    `voltas`: [{"volta": n, "medidas": medidas_da_volta(...)}] na ordem.
    """
    if len(voltas) < VOLTAS_POR_ANALISE:
        return {"curvas": []}
    tres = list(voltas)[-VOLTAS_POR_ANALISE:]
    por_curva: Dict[str, List[Dict[str, Any]]] = {}
    for v in tres:
        for m in v["medidas"]:
            por_curva.setdefault(m["curva"], []).append(m)
    candidatas = []
    for codigo, ms in por_curva.items():
        if len(ms) < VOLTAS_POR_ANALISE:
            continue
        perdas = [m["perdaS"] for m in ms]
        perdidas = sum(1 for p in perdas if p > PERDA_QUE_CONTA_S)
        mediana = statistics.median(perdas)
        if perdidas >= VOLTAS_PERDIDAS_MINIMAS and mediana > PERDA_QUE_CONTA_S:
            candidatas.append((mediana, codigo, ms, perdas, perdidas))
    candidatas.sort(key=lambda c: (-c[0], c[1]))
    curvas = []
    for mediana, codigo, ms, perdas, perdidas in candidatas[:CURVAS_POR_ANALISE]:
        diferencas = diferencas_da_curva(ms)
        ditas = [d for d in diferencas if d.peso >= 1.0][:DIFERENCAS_FALADAS_POR_CURVA]
        curvas.append({
            "curva": codigo,
            "lado": ms[0]["lado"],
            "perdaMedianaS": round(float(mediana), 3),
            "perdas": [round(float(p), 3) for p in perdas],
            "perdidaEm": perdidas,
            "diferencas": [{"medida": d.medida, "valor": round(d.valor, 2), "peso": round(d.peso, 2), **d.extra}
                           for d in diferencas],
            "ditas": [d.medida for d in ditas],
        })
    return {"voltas": [v["volta"] for v in tres], "curvas": curvas}
