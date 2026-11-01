"""O replay da curva (pedido 36, Parte E): o que o engenheiro mostra quando fala de uma curva.

Para uma curva citada pelo radio (uma analise das voltas ou uma frase do coach com causa):

* **as duas linhas:** a sua volta e a volta de referencia, na geometria oficial (centro +
  normal x lateral, o mesmo tracado da tela Volta), da entrada a saida da curva, com o
  tempo de cada uma desde a mesma entrada e o pedal (o da tela Volta: 2 = freio, 1 =
  acelerador cheio, 0 = parcial). Os dois carros andam cada um no seu proprio tempo: a
  diferenca aparece sozinha, no quanto a referencia abre;
* **as duas freadas** (a regra do relatorio de evolucao, `braking_point`) e a distancia
  entre elas;
* **as duas minimas,** no ponto de cada uma, com o valor;
* **o tracado:** no ponto da minima da referencia, as duas posicoes e a distancia, com o
  lado por extenso (ADR 0003: positivo = mais a esquerda);
* **o tempo perdido na curva** (o trecho do relatorio de evolucao, a mesma perda da analise).

Sempre "voce" e "IA (referencia)", a diferenca medida contra uma volta real (ADR 0012).
So le as grades que o radio ja tem (a volta ao vivo e a referencia do store); nada de
fisica nova.

Pedido 43:

* **os numeros da voz no replay da frase do coach** (`voz`): os rotulos mostram os numeros
  que o coach disse (a freada, as minimas e o tempo, arredondados como no cartao), e as
  marcas ficam onde o coach mediu: as freadas nos inicios de frenagem que o coach guardou
  (`yourBrakeOnsetM`, `referenceBrakeOnsetM`) e as minimas no ponto mais lento de cada grade
  dentro do microssetor da fala (a mesma regra do coach: a menor velocidade do microssetor).
  O coach nao mede o tracado: o replay da frase nao tem tracado. A janela cresce, se preciso,
  para conter o microssetor da fala (o "trecho da fala") e as freadas do coach;
* **os dados dos visuais** (C.1 a C.3), na mesma rota: a velocidade das duas voltas em cada
  ponto, o passo da grade (a distancia desde a entrada e `indice x passoM`), a distancia de
  cada marca desde a entrada (`dM`) e as separacoes da diferenca acumulada (`secoes`). O
  tempo e o pedal ja vinham nas linhas.

Decisoes do Eduardo sobre a analise, no fechamento do pedido 43:

* **os rotulos usam os numeros do cartao** (`da_analise`: as medianas das 3 voltas). As marcas de
  freada e a seta do tracado medem o rotulo; as linhas, os carros e o pedal continuam os da volta
  mais perto da mediana;
* **a diferenca acumulada cobre o trecho inteiro da curva** (`diferencaNoTrecho`): comeca em zero na
  entrada do trecho e termina na perda da curva. A animacao nao muda.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

ANTES_DA_FREADA_M = 50.0     # a entrada: um pouco antes da primeira freada (ou do inicio da curva)
DEPOIS_DA_CURVA_M = 60.0     # a saida: um pouco depois do fim da curva
LIMIAR_DO_FREIO = 0.15       # o pedal, como a tela Volta (Fantasma.tsx)
ACELERADOR_CHEIO = 0.9
MICROSSETORES = 60           # os do coach (`texto.MICROSSETORES`)


def _pedal(freio: np.ndarray, acelerador: np.ndarray) -> np.ndarray:
    p = np.zeros(freio.size, dtype=int)
    p[np.nan_to_num(acelerador) >= ACELERADOR_CHEIO] = 1
    p[np.nan_to_num(freio) >= LIMIAR_DO_FREIO] = 2
    return p


def _posicoes(track: Any, lateral: np.ndarray, indices: np.ndarray) -> np.ndarray:
    x, z = np.asarray(track.x, dtype=float), np.asarray(track.z, dtype=float)
    normal = np.asarray(track.normal, dtype=float)
    lat = np.nan_to_num(lateral[indices])
    return np.column_stack([x[indices] + normal[indices, 0] * lat, z[indices] + normal[indices, 1] * lat])


def _tempos(elapsed: np.ndarray, indices: np.ndarray, total: float) -> np.ndarray:
    """O tempo desde a entrada da curva, ao longo da janela (com a volta da linha, se a janela cruzar o s = 0)."""
    t = np.asarray(elapsed, dtype=float)[indices].copy()
    for k in range(1, t.size):
        if t[k] < t[k - 1]:
            t[k:] += total
    return t - t[0]


def cobertura_na_curva(linhas_grade: Dict[str, np.ndarray], indices: Sequence[int]) -> float:
    """Fracao dos pontos da janela com o relogio medido (antes de interpolar)."""
    el = linhas_grade.get("elapsed")
    if el is None:
        return 0.0
    vals = [el[i] for i in indices]
    return sum(1 for v in vals if v is not None and v == v) / max(len(vals), 1)


def janela_da_curva(pista: Any, codigo: str, volta: Dict[str, np.ndarray], ref: Dict[str, np.ndarray]):
    """O segmento da curva e os indices da grade da entrada a saida; None se a curva nao existe."""
    from ml.comparison.evolution import braking_point
    from ml.comparison.lap_vs_reference import _window

    track = pista.track
    for k, seg in enumerate(pista.segmentos):
        if seg.corner.label[:3] != codigo:
            continue
        corner = seg.corner
        anterior = pista.segmentos[k - 1].corner.apex_s
        freada_v = braking_point(volta["freio"], track, anterior, corner.apex_s)
        freada_r = braking_point(ref["freio"], track, anterior, corner.apex_s)
        L = float(track.length)
        # a entrada: o que vier primeiro (contando para tras a partir do apice) entre o inicio da curva e as freadas
        recuos = [(corner.apex_s - s) % L for s in (corner.start_s, freada_v, freada_r) if s is not None]
        inicio = (corner.apex_s - max(recuos) - ANTES_DA_FREADA_M) % L
        fim = (corner.end_s + DEPOIS_DA_CURVA_M) % L
        return seg, k, _window(track, inicio, fim), freada_v, freada_r
    return None


def _estender(track: Any, indices: np.ndarray, pontos: Sequence[Optional[float]]) -> np.ndarray:
    """Pedido 43: a janela crescida para conter `pontos` (s, em metros), para tras ou para a frente."""
    from ml.comparison.lap_vs_reference import _signed_distance, _window

    inicio, fim = float(track.s[indices[0]]), float(track.s[indices[-1]])
    for s in pontos:
        if s is None:
            continue
        if _signed_distance(track, inicio, s) > 0:
            inicio = float(s)
        if _signed_distance(track, s, fim) > 0:
            fim = float(s)
    return _window(track, inicio, fim)


def _microssetor(track: Any, indice: int) -> np.ndarray:
    """Os pontos da grade dentro do microssetor `indice` do coach ([inicio, fim), em metros)."""
    L = float(track.length)
    inicio = int(indice) * L / MICROSSETORES
    dentro = np.mod(np.asarray(track.s, dtype=float) - inicio, L) < L / MICROSSETORES
    return np.flatnonzero(dentro)


def _numero(valor: Any) -> Optional[float]:
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if np.isfinite(n) else None


def _diferenca_no_trecho(track: Any, seg: Any, volta: Dict[str, np.ndarray], volta_total: float,
                         ref: Dict[str, np.ndarray], ref_total: float, entrada: float) -> Dict[str, Any]:
    """A diferenca acumulada no trecho da curva, ponto a ponto: zero na entrada do trecho e, no fim,
    a mesma conta de `segment_time` (a perda da curva). `entradaDoReplayM`: onde a entrada do replay
    fica nesse eixo (negativa se o replay comeca antes do trecho)."""
    from ml.comparison.lap_vs_reference import _signed_distance

    L = float(track.length)
    comprimento = float(np.mod(seg.end_s - seg.start_s, L))
    n = int(round(comprimento / float(track.step))) + 1
    distancias = np.linspace(0.0, comprimento, max(n, 2))

    def desde_a_entrada(elapsed: np.ndarray, total: float) -> np.ndarray:
        # A conta de `evolution.time_at` e `segment_time`, de uma vez: o relogio vai de 0 em s = 0 ao
        # periodo na linha, e o trecho que cruza a linha soma o fim e o comeco da mesma volta.
        xs = np.append(track.s, L)
        ys = np.append(np.asarray(elapsed, dtype=float), float(total))
        t = np.interp(np.mod(seg.start_s + distancias, L), xs, ys)
        t = np.mod(t - t[0], total)
        # um relogio que volta um pouco (a interpolacao) nao vira quase uma volta inteira
        t[:-1] = np.where(t[:-1] > 0.9 * total, t[:-1] - total, t[:-1])
        return t

    dif = desde_a_entrada(volta["elapsed"], volta_total) - desde_a_entrada(ref["elapsed"], ref_total)
    return {"comprimentoM": round(comprimento, 1), "passoM": round(float(distancias[1] - distancias[0]), 4),
            "entradaDoReplayM": round(_signed_distance(track, entrada, seg.start_s), 1),
            "valores": [round(float(v), 3) for v in dif]}


def janela_da_frase(pista: Any, codigo: str, volta: Dict[str, np.ndarray], ref: Dict[str, np.ndarray],
                    voz: Optional[Dict[str, Any]] = None):
    """A janela do replay (`janela_da_curva`); com a `voz` da frase do coach (pedido 43), as freadas
    sao as do coach e a janela cresce para conter o microssetor da fala e essas freadas."""
    janela = janela_da_curva(pista, codigo, volta, ref)
    indice = _numero((voz or {}).get("microsector"))
    if janela is None or voz is None or indice is None:
        return janela
    seg, k, indices, _, _ = janela
    track = pista.track
    L = float(track.length)
    # a freada e a distancia sao as do coach (os inicios de frenagem que ele guardou)
    freada_v, freada_r = _numero(voz.get("yourBrakeOnsetM")), _numero(voz.get("referenceBrakeOnsetM"))
    if freada_v is None or freada_r is None or _numero(voz.get("brakeDeltaM")) is None:
        freada_v = freada_r = None
    inicio, fim = int(indice) * L / MICROSSETORES, (int(indice) + 1) * L / MICROSSETORES
    return seg, k, _estender(track, indices, [inicio, fim, freada_v, freada_r]), freada_v, freada_r


def dados_da_curva(pista: Any, codigo: str, volta: Dict[str, np.ndarray], volta_total: float,
                   ref: Dict[str, np.ndarray], ref_total: float, numero_da_volta: Optional[int],
                   tipo: Optional[str], voz: Optional[Dict[str, Any]] = None,
                   da_analise: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """O replay de uma curva: as duas linhas com o tempo e o pedal, as freadas, as minimas,
    o tracado e a perda. `volta` e `ref` sao grades completas (`analise.grade`).

    `voz` (pedido 43, so na frase do coach): o `evidence` da frase (`microsector`,
    `lossSeconds`, `yourBrakeOnsetM`, `referenceBrakeOnsetM`, `brakeDeltaM`, `yourMinSpeedKmh`,
    `referenceMinSpeedKmh`). Os rotulos passam a ter os numeros da voz, e as marcas, os pontos
    onde o coach mediu.

    `da_analise` (so na analise): a curva de `analise.analisar`. Os rotulos passam a ter as medianas
    do cartao, e a marca da sua freada e a ponta da seta do tracado medem esses numeros."""
    from ml.comparison.evolution import segment_time
    from ml.comparison.lap_vs_reference import _signed_distance, _window

    janela = janela_da_frase(pista, codigo, volta, ref, voz)
    if janela is None:
        return None
    seg, _, indices, freada_v, freada_r = janela
    track = pista.track
    corner = seg.corner
    L = float(track.length)
    ev = voz or {}
    indice_da_fala = _numero(ev.get("microsector"))
    if voz is not None and indice_da_fala is not None:
        inicio_fala = int(indice_da_fala) * L / MICROSSETORES
        fim_fala = (int(indice_da_fala) + 1) * L / MICROSSETORES
    medianas = {d["medida"]: d for d in (da_analise or {}).get("diferencas") or []}
    if da_analise is not None:
        # A marca da sua freada a distancia do rotulo da freada da referencia (a mesma de sempre);
        # a janela cresce so se a marca cair antes dela. Sem a mediana, nem rotulo nem marca.
        mediana_freada = medianas.get("freada")
        if mediana_freada is not None and freada_r is not None:
            freada_v = float(np.mod(freada_r + float(mediana_freada["valor"]), L))
            indices = _estender(track, indices, [freada_v])
        else:
            freada_v = freada_r = None
    pos_v, pos_r = _posicoes(track, volta["lateral"], indices), _posicoes(track, ref["lateral"], indices)
    t_v, t_r = _tempos(volta["elapsed"], indices, volta_total), _tempos(ref["elapsed"], indices, ref_total)
    ped_v = _pedal(volta["freio"][indices], volta["acelerador"][indices])
    ped_r = _pedal(ref["freio"][indices], ref["acelerador"][indices])
    entrada = float(track.s[indices[0]])
    ultimo_d = float((indices.size - 1) * track.step)

    def distancia(s: float) -> float:
        """A distancia desde a entrada do replay, em metros, dentro da janela."""
        return round(min(max(float(np.mod(s - entrada, L)), 0.0), ultimo_d), 1)

    def linha(pos, t, ped):
        return [[round(float(a), 2), round(float(b), 2), round(float(c), 3), int(d)] for (a, b), c, d in zip(pos, t, ped)]

    def ponto(s: Optional[float], lateral: np.ndarray) -> Optional[Dict[str, Any]]:
        if s is None:
            return None
        i = np.array([int(track.index_of(s))])
        p = _posicoes(track, lateral, i)[0]
        return {"x": round(float(p[0]), 2), "z": round(float(p[1]), 2), "s": round(float(s), 1), "dM": distancia(s)}

    def minima(i: int, grade: Dict[str, np.ndarray], kmh: float) -> Dict[str, Any]:
        p = _posicoes(track, grade["lateral"], np.array([i]))[0]
        return {"x": round(float(p[0]), 2), "z": round(float(p[1]), 2), "kmh": kmh,
                "dM": distancia(float(track.s[i]))}

    dentro = _window(track, corner.start_s, corner.end_s)
    i_v = int(dentro[int(np.nanargmin(volta["velocidade"][dentro]))])
    i_r = int(dentro[int(np.nanargmin(ref["velocidade"][dentro]))])
    minimas: Optional[Dict[str, Any]] = {"voce": minima(i_v, volta, round(float(volta["velocidade"][i_v]), 1)),
                                         "referencia": minima(i_r, ref, round(float(ref["velocidade"][i_r]), 1))}
    # o tracado: no ponto da minima da referencia, a sua posicao e a dela
    tv = _posicoes(track, volta["lateral"], np.array([i_r]))[0]
    mr = _posicoes(track, ref["lateral"], np.array([i_r]))[0]
    dif_lateral = float(np.nan_to_num(volta["lateral"][i_r]) - np.nan_to_num(ref["lateral"][i_r]))
    tracado: Optional[Dict[str, Any]] = {
        "voce": [round(float(tv[0]), 2), round(float(tv[1]), 2)],
        "referencia": [round(float(mr[0]), 2), round(float(mr[1]), 2)],
        "distanciaM": round(abs(dif_lateral), 2),
        "lado": "esquerda" if dif_lateral > 0 else "direita",
    }
    # positivo = voce freou depois da referencia; negativo = antes
    distancia_das_freadas = (round(float(_signed_distance(track, freada_v, freada_r)), 1)
                             if freada_v is not None and freada_r is not None else None)
    da_fala = None
    if voz is not None and indice_da_fala is not None:
        # Os numeros da voz, arredondados como no cartao (`texto.mensagem_de_diferenca`): o
        # cliente so escreve, sem arredondar de novo (o `Math.round` do JS arredonda 16,5 para 17).
        delta = _numero(ev.get("brakeDeltaM"))
        distancia_das_freadas = float(-round(delta)) if delta is not None and freada_v is not None else None
        no_trecho = _microssetor(track, int(indice_da_fala))
        sua, dela = _numero(ev.get("yourMinSpeedKmh")), _numero(ev.get("referenceMinSpeedKmh"))
        if sua is not None and dela is not None and no_trecho.size:
            j_v = int(no_trecho[int(np.nanargmin(volta["velocidade"][no_trecho]))])
            j_r = int(no_trecho[int(np.nanargmin(ref["velocidade"][no_trecho]))])
            minimas = {"voce": minima(j_v, volta, float(round(sua))), "referencia": minima(j_r, ref, float(round(dela)))}
        else:
            minimas = None
        tracado = None   # o coach nao mede o lado
        perda_da_fala = _numero(ev.get("lossSeconds"))
        da_fala = {
            "microssetor": int(indice_da_fala) + 1,
            "inicioM": distancia(inicio_fala),
            "fimM": distancia(fim_fala),
            "perdaS": round(perda_da_fala, 2) if perda_da_fala is not None else None,
        }
    if da_analise is not None:
        # Os numeros do cartao, arredondados como ele (`texto._diferenca_escrita`).
        if freada_v is not None:
            distancia_das_freadas = float(round(float(medianas["freada"]["valor"])))
        mediana_minima = medianas.get("minima")
        if mediana_minima is not None and minimas is not None:
            minimas["voce"]["kmh"] = float(round(float(mediana_minima["sua"])))
            minimas["referencia"]["kmh"] = float(round(float(mediana_minima["ref"])))
        mediana_tracado = medianas.get("tracado")
        if mediana_tracado is not None:
            valor = float(mediana_tracado["valor"])
            ponta = float(np.nan_to_num(ref["lateral"][i_r])) + valor
            q = _posicoes(track, np.full(int(track.size), ponta), np.array([i_r]))[0]
            tracado = {"voce": [round(float(q[0]), 2), round(float(q[1]), 2)], "referencia": tracado["referencia"],
                       "distanciaM": float(f"{abs(valor):.1f}"), "lado": "esquerda" if valor > 0 else "direita"}
    perda = segment_time(volta["elapsed"], volta_total, track, seg) - segment_time(ref["elapsed"], ref_total, track, seg)
    freadas = {"voce": ponto(freada_v, volta["lateral"]), "referencia": ponto(freada_r, ref["lateral"]),
               "distanciaM": distancia_das_freadas}
    # As separacoes da diferenca acumulada (C.2): a primeira freada, a minima da referencia e o fim da curva.
    ds_freada = [f["dM"] for f in (freadas["voce"], freadas["referencia"]) if f]
    secoes = {"freadaM": min(ds_freada) if ds_freada else None,
              "minimaM": minimas["referencia"]["dM"] if minimas else None,
              "saidaM": distancia(corner.end_s)}
    return {
        "curva": codigo,
        "lado": "esquerda" if corner.label.endswith("esq") else "direita",
        "volta": numero_da_volta,
        "referencia": tipo,
        "rotuloDaReferencia": "IA (referência)" if tipo == "volta_ia" else "sua melhor (referência)",
        "perdaS": round(float(perda), 3),
        "linhas": {"voce": linha(pos_v, t_v, ped_v), "referencia": linha(pos_r, t_r, ped_r)},
        "duracaoS": round(float(max(t_v[-1], t_r[-1])), 3),
        "freadas": freadas,
        "minimas": minimas,
        "tracado": tracado,
        # Pedido 43: os visuais (a distancia de cada ponto e `indice x passoM`) e o trecho da fala.
        "passoM": round(float(track.step), 4),
        "velocidades": {"voce": [round(float(v), 1) for v in np.nan_to_num(volta["velocidade"][indices])],
                        "referencia": [round(float(v), 1) for v in np.nan_to_num(ref["velocidade"][indices])]},
        "secoes": secoes,
        "voz": da_fala,
        "diferencaNoTrecho": _diferenca_no_trecho(track, seg, volta, volta_total, ref, ref_total, entrada)
        if da_analise is not None else None,
    }


def volta_mais_perto_da_mediana(voltas: Sequence[Dict[str, Any]], curva: Dict[str, Any]) -> Optional[int]:
    """Na analise, a volta das 3 cuja perda na curva fica mais perto da mediana (o indice em `voltas`).

    `curva["perdas"]` vem na ordem das voltas analisadas."""
    perdas = list(curva.get("perdas") or [])
    if not perdas or len(perdas) != len(voltas):
        return None
    mediana = float(curva.get("perdaMedianaS", np.median(perdas)))
    return int(min(range(len(perdas)), key=lambda i: (abs(perdas[i] - mediana), i)))


def replay_da_analise(pista: Any, voltas: Sequence[Dict[str, Any]], analise: Dict[str, Any],
                      ref: Dict[str, np.ndarray], ref_total: float, tipo: Optional[str]) -> List[Dict[str, Any]]:
    """Uma curva por curva citada na analise, cada uma com a volta mais perto da mediana.

    `voltas`: as 3 voltas analisadas, cada uma com `grade` e `tempoS`."""
    out = []
    for curva in analise.get("curvas") or []:
        i = volta_mais_perto_da_mediana(voltas, curva)
        if i is None or voltas[i].get("grade") is None:
            continue
        d = dados_da_curva(pista, curva["curva"], voltas[i]["grade"], float(voltas[i]["tempoS"]), ref, ref_total,
                           voltas[i].get("volta"), tipo, da_analise=curva)
        if d is not None:
            out.append(d)
    return out
