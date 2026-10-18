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
        })
    return out


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
