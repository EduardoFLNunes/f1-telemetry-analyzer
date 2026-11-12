"""O Modelo 1 por trecho (pedido 49; ADR 0030): as regras como funcoes puras.

* `trechos`: um trecho por curva oficial (do fim da curva anterior ao fim dela)
  mais o da chegada, cobrindo a volta sem buraco e sem sobreposicao (item 1);
* `tempos_por_trecho`: o cronometro da volta na grade, nas fronteiras (item 1);
* `comparar` e `classificar`: a regra do ganho (item 3): a diferenca das
  medianas com o IC por bootstrap, o p-valor pela permutacao exata da diferenca
  das medias e o Holm entre os trechos;
* `medidas_da_execucao`: a frenagem, a minima, a marcha e a retomada (item 5);
* `curvatura_do_arquivo`, `rugosidade` e `media_por_microssetor`: a hipotese da
  curvatura (item 6);
* `rampa_do_freio` e `limite_de_linha`: as regras provisorias (item 7).

Nada aqui le gravacao nem arquivo: quem le e o script `ml.scripts.modelo1_por_trecho`.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

# ADR 0030.
REAMOSTRAGENS = 10_000
SEMENTE = 49
ALFA = 0.05
SOMA_TOLERANCIA_S = 0.005
TEMPO_REFEITO_TOLERANCIA_S = 0.001
FREIO_INICIO = 0.10
ACELERADOR_RETOMADA = 0.90
RAMPA_FRACAO = 0.90
RAMPA_MINIMO_DE_VOLTAS = 5
LIMITE_PERCENTIL = 90.0
JANELA_RUGOSIDADE_M = 20.0
MESMO_LUGAR_M = 4.0
NOME_DA_CHEGADA = "C14->linha"


@dataclass(frozen=True)
class Trecho:
    nome: str
    inicio_s: float
    fim_s: float
    entrada_s: float
    apice_s: Optional[float]
    saida_s: float
    tem_curva: bool

    def indices(self, track_s: np.ndarray, comprimento: float) -> np.ndarray:
        """Os pontos da grade do trecho: s em [inicio, fim)."""
        fim = self.fim_s if self.fim_s < comprimento - 1e-6 else comprimento
        return np.flatnonzero((track_s >= self.inicio_s - 1e-6) & (track_s < fim - 1e-6))

    def pontos_de_linha(self) -> Dict[str, float]:
        if self.tem_curva:
            return {"entrada": self.entrada_s, "apice": float(self.apice_s), "saida": self.saida_s}
        return {"entrada": self.inicio_s, "apice": 0.5 * (self.inicio_s + self.fim_s), "saida": self.fim_s}


def trechos(corners: Sequence, comprimento: float) -> List[Trecho]:
    """ADR 0030, item 1. `corners`: as curvas de `detect_corners`, em ordem de s, sem cruzar a linha."""
    cs = sorted(corners, key=lambda c: c.start_s)
    out: List[Trecho] = []
    inicio = 0.0
    for c in cs:
        if not (0.0 <= c.start_s <= c.apex_s <= c.end_s < comprimento):
            raise ValueError(f"a curva {c.label} cruza a linha ou esta fora da volta")
        nome = c.label[:3]
        out.append(Trecho(nome, float(inicio), float(c.end_s), float(c.start_s), float(c.apex_s), float(c.end_s), True))
        inicio = float(c.end_s)
    out.append(Trecho(NOME_DA_CHEGADA, float(inicio), float(comprimento), float(inicio), None, float(comprimento), False))
    conferir_cobertura(out, comprimento)
    return out


def conferir_cobertura(lista: Sequence[Trecho], comprimento: float) -> None:
    """Os trechos cobrem [0, comprimento] sem buraco e sem sobreposicao."""
    if not lista or abs(lista[0].inicio_s) > 1e-9 or abs(lista[-1].fim_s - comprimento) > 1e-6:
        raise ValueError("os trechos nao comecam na linha ou nao terminam nela")
    for a, b in zip(lista[:-1], lista[1:]):
        if abs(a.fim_s - b.inicio_s) > 1e-9:
            raise ValueError(f"buraco ou sobreposicao entre {a.nome} e {b.nome}")
    for t in lista:
        if not t.fim_s > t.inicio_s:
            raise ValueError(f"o trecho {t.nome} tem comprimento zero ou negativo")


def tempos_por_trecho(elapsed: np.ndarray, track_s: np.ndarray, tempo_da_volta: float,
                      lista: Sequence[Trecho]) -> np.ndarray:
    """O tempo de cada trecho pelo cronometro da volta na grade (o `elapsed_s` do `line_clock`)."""
    elapsed = np.asarray(elapsed, float)
    ok = np.isfinite(elapsed)
    bordas = np.interp([t.inicio_s for t in lista], np.asarray(track_s, float)[ok], elapsed[ok])
    bordas = np.r_[bordas, float(tempo_da_volta)]
    return np.diff(bordas)


def conferir_soma(tempos: np.ndarray, tempo_da_volta: float, tolerancia: float = SOMA_TOLERANCIA_S) -> float:
    """A diferenca entre a soma dos trechos e o tempo da volta; acima da tolerancia, para."""
    dif = float(np.sum(tempos) - tempo_da_volta)
    if not abs(dif) <= tolerancia:
        raise ValueError(f"a soma dos trechos difere do tempo da volta em {dif * 1000:.1f} ms")
    return dif


# ------------------------------------------------------------- item 3 ---

def bootstrap_mediana(a: Sequence[float], b: Sequence[float], reamostragens: int = REAMOSTRAGENS,
                      semente: int = SEMENTE) -> Dict[str, float]:
    """Mediana(a) - mediana(b), com o IC de 95% por bootstrap (um gerador novo a cada chamada)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    rng = np.random.default_rng(semente)
    ia = rng.integers(0, len(a), size=(reamostragens, len(a)))
    ib = rng.integers(0, len(b), size=(reamostragens, len(b)))
    difs = np.median(a[ia], axis=1) - np.median(b[ib], axis=1)
    return {"diferenca_s": float(np.median(a) - np.median(b)), "ic95_inferior_s": float(np.percentile(difs, 2.5)),
            "ic95_superior_s": float(np.percentile(difs, 97.5))}


def permutacao_exata(a: Sequence[float], b: Sequence[float]) -> float:
    """p-valor bilateral da diferenca das medias, com todas as divisoes das voltas entre os dois grupos."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    x = np.r_[a, b]
    n, total = len(a), float(np.sum(np.r_[a, b]))
    obs = abs(a.mean() - b.mean())
    combos = np.array(list(itertools.combinations(range(len(x)), n)), dtype=int)
    soma_a = x[combos].sum(axis=1)
    difs = np.abs(soma_a / n - (total - soma_a) / len(b))
    return float(np.mean(difs >= obs - 1e-12))


def holm(pvalores: Sequence[float], alfa: float = ALFA) -> np.ndarray:
    """Holm a `alfa`: True onde a hipotese nula e rejeitada."""
    p = np.asarray(pvalores, float)
    ordem = np.argsort(p, kind="stable")
    m = len(p)
    rejeita = np.zeros(m, dtype=bool)
    for k, i in enumerate(ordem):
        if p[i] <= alfa / (m - k):
            rejeita[i] = True
        else:
            break
    return rejeita


def comparar(x: np.ndarray, y: np.ndarray, nomes: Sequence[str], semente: int = SEMENTE,
             reamostragens: int = REAMOSTRAGENS) -> List[Dict[str, object]]:
    """X contra Y em cada trecho. `x`, `y`: [voltas, trechos]. O Holm e entre os trechos desta comparacao."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    out = []
    for j, nome in enumerate(nomes):
        d = bootstrap_mediana(x[:, j], y[:, j], reamostragens, semente)
        d["diferenca_das_medias_s"] = float(x[:, j].mean() - y[:, j].mean())
        d["p_permutacao"] = permutacao_exata(x[:, j], y[:, j])
        d["trecho"] = nome
        out.append(d)
    rej = holm([d["p_permutacao"] for d in out])
    for d, r in zip(out, rej):
        d["significativo_holm"] = bool(r)
        mesmo_sinal = np.sign(d["diferenca_s"]) == np.sign(d["diferenca_das_medias_s"]) != 0
        d["sentido"] = (("menor" if d["diferenca_s"] < 0 else "maior") if (r and mesmo_sinal) else "nenhum")
    return out


def classificar(contra_c0: Sequence[Dict[str, object]], contra_c0_final: Sequence[Dict[str, object]]) -> List[str]:
    """ADR 0030, item 3: ganho ou perda so com o mesmo sentido significativo contra o C0 e contra o C0 final."""
    out = []
    for a, b in zip(contra_c0, contra_c0_final):
        if a["sentido"] == "menor" and b["sentido"] == "menor":
            out.append("ganho")
        elif a["sentido"] == "maior" and b["sentido"] == "maior":
            out.append("perda")
        else:
            out.append("empate")
    return out


# ------------------------------------------------------------- item 5 ---

def _valor(canal: Optional[np.ndarray]) -> bool:
    return canal is not None and np.isfinite(np.asarray(canal, float)).any()


def inicio_da_frenagem(freio: np.ndarray, idx: np.ndarray, ate: int, limiar: float = FREIO_INICIO) -> Optional[int]:
    """O primeiro ponto de `idx` (ate a posicao `ate`, inclusive) com freio >= limiar e o anterior abaixo."""
    freio = np.nan_to_num(np.asarray(freio, float))
    janela = idx[: ate + 1]
    if not len(janela):
        return None
    anterior = (janela[0] - 1) % len(freio)
    on = np.r_[freio[anterior], freio[janela]] >= limiar
    subida = np.flatnonzero(on[1:] & ~on[:-1])
    return int(janela[subida[0]]) if subida.size else None


def medidas_da_execucao(canais: Dict[str, Optional[np.ndarray]], track_s: np.ndarray, comprimento: float,
                        trecho: Trecho) -> Dict[str, object]:
    """As medidas da execucao numa volta e num trecho (ADR 0030, item 5)."""
    s = np.asarray(track_s, float)
    idx = trecho.indices(s, comprimento)
    out: Dict[str, object] = {}
    freio = canais.get("brake")
    if not _valor(freio):
        out.update({"frenagem_inicio_s": "nao gravado", "freio_maximo": "nao gravado", "frenagem_ate_o_apice_m": "nao gravado"})
    else:
        f = np.nan_to_num(np.asarray(freio, float))
        if trecho.tem_curva:
            ate = int(np.searchsorted(s[idx], float(trecho.apice_s) - 1e-6))
            ate = min(ate, len(idx) - 1)
        else:
            ate = len(idx) - 1
        i0 = inicio_da_frenagem(f, idx, ate)
        if i0 is None:
            out.update({"frenagem_inicio_s": None, "freio_maximo": None, "frenagem_ate_o_apice_m": None})
        else:
            k0 = int(np.flatnonzero(idx == i0)[0])
            resto = idx[k0:]
            abaixo = np.flatnonzero(f[resto] < FREIO_INICIO)
            evento = resto[: abaixo[0]] if abaixo.size else resto
            out["frenagem_inicio_s"] = float(s[i0])
            out["freio_maximo"] = float(f[evento].max())
            out["frenagem_ate_o_apice_m"] = (float(trecho.apice_s) - float(s[i0])) if trecho.tem_curva else "sem curva"
    vel = canais.get("speed_kmh")
    if not _valor(vel):
        out.update({"velocidade_minima_kmh": "nao gravado", "velocidade_minima_s": "nao gravado"})
    else:
        v = np.asarray(vel, float)[idx]
        k = int(np.nanargmin(v))
        out.update({"velocidade_minima_kmh": float(v[k]), "velocidade_minima_s": float(s[idx[k]])})
    marcha = canais.get("gear")
    if not _valor(marcha):
        out.update({"marcha_minima": "nao gravado", "trocas": "nao gravado",
                    "marcha_minima_sem_neutro": "nao gravado", "trocas_sem_neutro": "nao gravado"})
    else:
        g = np.asarray(marcha, float)
        anterior = (idx[0] - 1) % len(g)
        seq = np.r_[g[anterior], g[idx]]
        trocas = [{"s": float(s[idx[k]]), "de": int(seq[k]), "para": int(seq[k + 1])}
                  for k in range(len(idx)) if np.isfinite(seq[k]) and np.isfinite(seq[k + 1]) and seq[k + 1] != seq[k]]
        out.update({"marcha_minima": int(np.nanmin(g[idx])), "trocas": trocas})
        out.update(_sem_neutro(g, idx, s))
    acel = canais.get("throttle")
    if not _valor(acel):
        out["retomada_s"] = "nao gravado"
    else:
        a = np.nan_to_num(np.asarray(acel, float))[idx]
        abaixo = np.flatnonzero(a < ACELERADOR_RETOMADA)
        if not abaixo.size:
            out["retomada_s"] = float(s[idx[0]])
        elif abaixo[-1] == len(idx) - 1:
            out["retomada_s"] = None
        else:
            out["retomada_s"] = float(s[idx[abaixo[-1] + 1]])
    return out


def _sem_neutro(g: np.ndarray, idx: np.ndarray, s: np.ndarray) -> Dict[str, object]:
    """Leitura acrescentada depois de ver os dados (pedido 49; so relatada, fora da regra do ADR 0030).

    O gravador guarda a marcha como `gear - 1` do jogo (-1 re, 0 neutro, 1 primeira), e o carro passa pelo
    neutro em cada troca (de 2 a 6 m na grade). Aqui o neutro e a re sao ignorados: a marcha minima e a menor
    marcha >= 1 do trecho, e uma troca `5 -> 0 -> 4` vira `5 -> 4`, no ponto em que a marcha 4 aparece.
    """
    n = len(g)
    validas = np.isfinite(g[idx]) & (g[idx] >= 1)
    minima = int(np.min(g[idx][validas])) if validas.any() else "sem dados"
    ultima = None
    k = int(idx[0]) - 1
    for _ in range(n):
        if np.isfinite(g[k % n]) and g[k % n] >= 1:
            ultima = int(g[k % n])
            break
        k -= 1
    trocas = []
    for i in idx:
        if np.isfinite(g[i]) and g[i] >= 1:
            if ultima is not None and int(g[i]) != ultima:
                trocas.append({"s": float(s[i]), "de": ultima, "para": int(g[i])})
            ultima = int(g[i])
    return {"marcha_minima_sem_neutro": minima, "trocas_sem_neutro": trocas}


NUMERICAS = ("frenagem_inicio_s", "freio_maximo", "frenagem_ate_o_apice_m", "velocidade_minima_kmh",
             "velocidade_minima_s", "marcha_minima", "retomada_s", "marcha_minima_sem_neutro")
NENHUMA_VOLTA = {"frenagem_inicio_s": "sem frenagem no trecho", "freio_maximo": "sem frenagem no trecho",
                 "frenagem_ate_o_apice_m": "sem frenagem no trecho", "retomada_s": "sem retomada no trecho"}


def _resumir_trocas(voltas: Sequence[Dict[str, object]], chave: str) -> Dict[str, object]:
    seqs = [tuple((t["de"], t["para"]) for t in v[chave]) for v in voltas if isinstance(v.get(chave), list)]
    if not seqs:
        return {"sequencia_mais_comum": "nao gravado" if voltas else "sem dados"}
    comum, n = Counter(seqs).most_common(1)[0]
    posicoes = [[t["s"] for t in v[chave]] for v in voltas
                if isinstance(v.get(chave), list) and tuple((t["de"], t["para"]) for t in v[chave]) == comum]
    return {"sequencia_mais_comum": [f"{a}->{b}" for a, b in comum], "voltas_com_ela": int(n),
            "s_mediano": [float(np.median([p[k] for p in posicoes])) for k in range(len(comum))]}


def resumir_medidas(voltas: Sequence[Dict[str, object]]) -> Dict[str, object]:
    """A mediana, o desvio (amostral) e quantas voltas tem cada medida; e a sequencia de trocas mais comum."""
    out: Dict[str, object] = {"voltas": len(voltas)}
    for nome in NUMERICAS:
        valores = [v.get(nome) for v in voltas]
        if valores and all(isinstance(x, str) for x in valores):
            out[nome] = {"mediana": valores[0], "desvio": None, "voltas_com_a_medida": 0}
            continue
        num = np.array([x for x in valores if isinstance(x, (int, float)) and not isinstance(x, bool)], float)
        vazio = NENHUMA_VOLTA.get(nome, "sem dados") if any(x is None for x in valores) else "sem dados"
        out[nome] = {"mediana": float(np.median(num)) if num.size else vazio,
                     "desvio": float(np.std(num, ddof=1)) if num.size > 1 else None,
                     "voltas_com_a_medida": int(num.size)}
    out["trocas"] = _resumir_trocas(voltas, "trocas")
    out["trocas_sem_neutro"] = _resumir_trocas(voltas, "trocas_sem_neutro")
    return out


# ------------------------------------------------------------- item 6 ---

def curvatura_do_arquivo(raio: np.ndarray, direcao: np.ndarray) -> np.ndarray:
    """kappa = direcao / raio, com os campos do arquivo; raio nao finito ou <= 0 da 0."""
    raio = np.asarray(raio, float)
    direcao = np.asarray(direcao, float)
    ok = np.isfinite(raio) & (raio > 0) & np.isfinite(direcao)
    out = np.zeros(len(raio))
    out[ok] = direcao[ok] / raio[ok]
    return out


def curvatura_de_tres_pontos(xz: np.ndarray) -> np.ndarray:
    """Curvatura com sinal do circulo por i-1, i, i+1 (linha fechada); serve aos testes."""
    p = np.asarray(xz, float)
    a, b, c = np.roll(p, 1, axis=0), p, np.roll(p, -1, axis=0)
    ab, bc, ca = np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)
    cruz = (b - a)[:, 0] * (c - b)[:, 1] - (b - a)[:, 1] * (c - b)[:, 0]
    den = ab * bc * ca
    return np.where(den > 0, 2.0 * cruz / np.where(den > 0, den, 1.0), 0.0)


def rugosidade(kappa: np.ndarray, estacao: np.ndarray, comprimento: float,
               janela_m: float = JANELA_RUGOSIDADE_M) -> np.ndarray:
    """Em cada ponto, a raiz da media de (segunda diferenca de kappa)^2 nos pontos a ate janela/2 de estacao."""
    k = np.asarray(kappa, float)
    d2 = np.roll(k, -1) - 2.0 * k + np.roll(k, 1)
    q = d2 ** 2
    s = np.mod(np.asarray(estacao, float), comprimento)
    ordem = np.argsort(s, kind="stable")
    ss, qq = s[ordem], q[ordem]
    ext_s = np.r_[ss - comprimento, ss, ss + comprimento]
    ext_q = np.r_[qq, qq, qq]
    acum = np.r_[0.0, np.cumsum(ext_q)]
    meia = 0.5 * janela_m
    lo = np.searchsorted(ext_s, s - meia - 1e-9, side="left")
    hi = np.searchsorted(ext_s, s + meia + 1e-9, side="right")
    n = np.maximum(hi - lo, 1)
    return np.sqrt((acum[hi] - acum[lo]) / n)


def media_por_microssetor(valores: np.ndarray, estacao: np.ndarray, bordas_s: np.ndarray, comprimento: float) -> np.ndarray:
    """A media dos valores dos pontos cuja estacao cai em cada microssetor."""
    s = np.mod(np.asarray(estacao, float), comprimento)
    qual = np.clip(np.searchsorted(np.asarray(bordas_s, float), s, side="right") - 1, 0, len(bordas_s) - 2)
    out = np.full(len(bordas_s) - 1, np.nan)
    for m in range(len(out)):
        sel = qual == m
        if sel.any():
            out[m] = float(np.mean(np.asarray(valores, float)[sel]))
    return out


# ------------------------------------------------------------- item 7 ---

def _cruzamento(s: np.ndarray, f: np.ndarray, k: int, limiar: float) -> float:
    """O s em que f cruza o limiar entre os pontos k-1 e k (interpolacao linear)."""
    if k <= 0 or f[k] == f[k - 1]:
        return float(s[k])
    t = (limiar - f[k - 1]) / (f[k] - f[k - 1])
    return float(s[k - 1] + np.clip(t, 0.0, 1.0) * (s[k] - s[k - 1]))


def rampa_do_freio(freio: np.ndarray, track_s: np.ndarray, comprimento: float, trecho: Trecho) -> Optional[float]:
    """A distancia entre o freio passar de 0,10 e chegar a 90% do maximo da frenagem (interpolada), ou None."""
    s_all = np.asarray(track_s, float)
    f_all = np.nan_to_num(np.asarray(freio, float))
    idx = trecho.indices(s_all, comprimento)
    if trecho.tem_curva:
        ate = min(int(np.searchsorted(s_all[idx], float(trecho.apice_s) - 1e-6)), len(idx) - 1)
    else:
        ate = len(idx) - 1
    i0 = inicio_da_frenagem(f_all, idx, ate)
    if i0 is None:
        return None
    k0 = int(np.flatnonzero(idx == i0)[0])
    anterior = (idx[0] - 1) % len(f_all)
    pts = np.r_[anterior, idx]
    # O s do ponto anterior ao trecho, continuo com o do trecho (o C01 comeca na linha).
    s = np.r_[s_all[idx[0]] - (s_all[1] - s_all[0]), s_all[idx]]
    f = f_all[pts]
    k = k0 + 1
    resto = np.arange(k, len(pts))
    abaixo = np.flatnonzero(f[resto] < FREIO_INICIO)
    fim = resto[abaixo[0]] if abaixo.size else len(pts)
    maximo = float(f[k:fim].max())
    alvo = RAMPA_FRACAO * maximo
    acima = np.flatnonzero(f[k:fim] >= alvo - 1e-12)
    k90 = k + int(acima[0])
    s10 = _cruzamento(s, f, k, FREIO_INICIO)
    s90 = _cruzamento(s, f, k90, alvo)
    return float(max(s90 - s10, 0.0))


def limite_de_linha(laterais: np.ndarray, pontos: Sequence[int], percentil: float = LIMITE_PERCENTIL) -> Dict[str, np.ndarray]:
    """Em cada ponto da grade: a mediana das laterais das voltas e o percentil das distancias a ela."""
    lat = np.asarray(laterais, float)[:, list(pontos)]
    med = np.nanmedian(lat, axis=0)
    dist = np.abs(lat - med[None, :])
    return {"mediana": med, "limite": np.nanpercentile(dist, percentil, axis=0)}


def acima_do_limite(mediana: np.ndarray, limite: np.ndarray, linha_ia: np.ndarray) -> np.ndarray:
    """A distancia da mediana do piloto a linha da IA passa do limite?"""
    return np.abs(np.asarray(mediana, float) - np.asarray(linha_ia, float)) > np.asarray(limite, float)


# ------------------------------------------------------------- Parte C ---

CHAVES_DA_REFERENCIA = ("pedido", "adr", "commit", "geometry_id", "corridor_id", "grade_m", "gravacoes", "arquivos",
                        "trechos", "aviso")
CHAVES_DO_TRECHO = ("trecho", "inicio_s", "fim_s", "pontos_de_linha_s", "linha_de_referencia", "execucao_da_ia",
                    "candidata", "provisorio")


def conferir_formato_da_referencia(payload: Dict[str, object], n_trechos: int = 15, com_lateral: bool = True) -> None:
    """O formato do JSON da Parte C (ADR 0030, item 9); levanta ValueError no primeiro problema."""
    for k in CHAVES_DA_REFERENCIA:
        if k not in payload:
            raise ValueError(f"falta a chave {k!r}")
    lista = payload["trechos"]
    if len(lista) != n_trechos:
        raise ValueError(f"esperava {n_trechos} trechos, vieram {len(lista)}")
    for t in lista:
        for k in CHAVES_DO_TRECHO:
            if k not in t:
                raise ValueError(f"o trecho {t.get('trecho')} nao tem {k!r}")
        if t["linha_de_referencia"]["linha"] != "C0":
            raise ValueError("a referencia de todo trecho e a linha da IA (C0) neste pedido")
        if com_lateral and len(t["linha_de_referencia"]["lateral_m"]) != len(t["linha_de_referencia"]["s"]):
            raise ValueError("a lateral e o s da referencia tem tamanhos diferentes")
        if t["candidata"] is not None and t["candidata"].get("marca") != "a validar no jogo":
            raise ValueError("a candidata precisa da marca 'a validar no jogo'")
        if t["provisorio"].get("marca") != "provisorio, sem confirmacao":
            raise ValueError("as propostas precisam da marca 'provisorio, sem confirmacao'")
    for a, b in zip(lista[:-1], lista[1:]):
        if abs(a["fim_s"] - b["inicio_s"]) > 1e-6:
            raise ValueError("os trechos da referencia tem buraco ou sobreposicao")
