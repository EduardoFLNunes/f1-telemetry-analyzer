"""As regras do engenheiro (pedido 52, ADR 0033): funcoes puras, sem estado, testadas com dados sinteticos.

* os 15 trechos (ADR 0030) e o tempo de cada um;
* os pontos da referencia de cada trecho: a freada (freio acima de 0,15), a entrada e a retomada;
* a causa do engenheiro a partir da causa do radio do 45 (`analise.causa_da_curva`);
* a frase, pelo marco de menor custo (a janela, o custo, o bonus, o empate e o arredondamento);
* os blocos de voz da volta do modelo e o `s_fala` de cada aviso;
* a conferencia da dica.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from core.radio.analise import CORTE_ACELERADOR_M, causa_da_curva

# ADR 0033, item 4
JANELA_FREIE_M = (150.0, 60.0)        # o marco ate 150 m antes do ponto ou ate 60 m depois
JANELA_VIRE_M = (80.0, 40.0)          # vire e acelere
PESO_DEPOIS = 1.5
BONUS_PLACA_M = 15.0                  # para frear
BONUS_ZEBRA_M = 10.0                  # o comeco ou o fim de uma zebra, para virar e acelerar
NO_MARCO_M = 5.0                      # |d| abaixo disto: "na placa de 100"
ARREDONDAR_M = 5.0
# ADR 0033, item 5
FOLGA_ANTES_DA_FREADA_S = 1.0
# ADR 0033, emenda de 16/11, item 1: as retas longas sao os blocos de voz de pelo menos o maior limite do
# feedback (7,3, 8,0 e 8,8 s)
RETA_LONGA_S = 8.8
# ADR 0033, item 8
APLICADA_FREADA_M = 10.0
APLICADA_MINIMA_KMH = 5.0
APLICADA_RETOMADA_M = 10.0
# ADR 0033, item 6: a volta lenta
VOLTA_LENTA_S = 5.0
# As medidas (ADR 0030, item 5; o relatorio de evolucao)
FREIO_DA_FREADA = 0.15
ACELERADOR_DA_RETOMADA = 0.90

# Decisao do Eduardo de 16/11 (ADR 0033, emenda, item 3): o trecho em que a referencia nao freia nem alivia
SEM_TIRAR_O_PE = "sem tirar o pé"

ACAO_DA_CAUSA = {"freada cedo": "freie", "freada tarde": "freie", "mínima baixa": "vire",
                 "traçado por fora": "vire", "traçado por dentro": "vire", "acelerador tarde": "acelere"}


# ── os trechos ───────────────────────────────────────────────────────────

def trechos_da_pista(track) -> List[Any]:
    """Os 15 trechos do ADR 0030, na geometria oficial."""
    from ml.pista_teste.por_trecho import trechos
    from ml.track.corners import detect_corners

    return trechos(detect_corners(track), float(track.length))


def numero_da_curva(nome: str) -> Optional[int]:
    return int(nome[1:3]) if nome.startswith("C") and nome[1:3].isdigit() and "->" not in nome else None


def tempo_em(elapsed: np.ndarray, total: float, track, s: float) -> float:
    """O relogio da volta em `s` (de 0 em s = 0 ao tempo da volta na linha)."""
    xs = np.append(np.asarray(track.s, float), float(track.length))
    ys = np.append(np.asarray(elapsed, float), float(total))
    ok = np.isfinite(ys)
    return float(np.interp(float(s) % float(track.length), xs[ok], ys[ok]))


def tempos_dos_trechos(elapsed: np.ndarray, total: float, track, trechos: Sequence[Any]) -> np.ndarray:
    """O tempo de cada trecho: o relogio no fim menos no comeco (ADR 0030); a soma e o tempo da volta."""
    bordas = [tempo_em(elapsed, total, track, t.inicio_s) for t in trechos] + [float(total)]
    bordas[0] = 0.0 if trechos[0].inicio_s == 0.0 else bordas[0]
    return np.diff(np.asarray(bordas, float))


def s_no_tempo(elapsed: np.ndarray, total: float, track, t: float) -> float:
    """O `s` em que o relogio da volta vale `t` (o inverso de `tempo_em`)."""
    xs = np.append(np.asarray(track.s, float), float(track.length))
    ys = np.append(np.asarray(elapsed, float), float(total))
    ok = np.isfinite(ys)
    t = float(t) % float(total)
    return float(np.interp(t, ys[ok], xs[ok])) % float(track.length)


# ── os pontos da referencia ──────────────────────────────────────────────

def _janela(track, de: float, ate: float) -> np.ndarray:
    from ml.comparison.lap_vs_reference import _window
    return _window(track, de, ate)


def ponto_de_freada(freio: np.ndarray, track, de: float, apice: float) -> Optional[float]:
    """Onde o freio passa de 0,15, de `de` ao apice (a regra do relatorio de evolucao e do 45)."""
    from ml.comparison.evolution import braking_point
    return braking_point(np.asarray(freio, float), track, float(de) % float(track.length), apice)


def inicio_da_busca_da_freada(trechos: Sequence[Any], k: int) -> float:
    """ADR 0033, emenda de 16/11, item 4: a busca da freada comeca na saida do trecho anterior
    (`pontos_de_linha_s.saida`; antes da C01, o fim do trecho da chegada, que e a linha)."""
    anterior = trechos[k - 1] if k > 0 else trechos[-1]
    return float(anterior.pontos_de_linha()["saida"])


def retomada(acelerador: np.ndarray, track, trecho) -> Optional[float]:
    """ADR 0030, item 5: o primeiro ponto do trecho a partir do qual o acelerador fica em 0,90 ou mais ate o fim."""
    s = np.asarray(track.s, float)
    idx = trecho.indices(s, float(track.length))
    if not len(idx):
        return None
    a = np.nan_to_num(np.asarray(acelerador, float))[idx]
    abaixo = np.flatnonzero(a < ACELERADOR_DA_RETOMADA)
    if not abaixo.size:
        return float(s[idx[0]])
    if abaixo[-1] == len(idx) - 1:
        return None
    return float(s[idx[abaixo[-1] + 1]])


def sem_tirar_o_pe(acelerador: np.ndarray, track, trecho) -> bool:
    """ADR 0033, emenda de 16/11, item 3: o acelerador em 0,90 ou mais do comeco ao fim do trecho."""
    idx = trecho.indices(np.asarray(track.s, float), float(track.length))
    if not len(idx):
        return False
    return bool(np.all(np.nan_to_num(np.asarray(acelerador, float))[idx] >= ACELERADOR_DA_RETOMADA))


def acelerador_minimo(acelerador: np.ndarray, track, trecho) -> Optional[float]:
    idx = trecho.indices(np.asarray(track.s, float), float(track.length))
    return float(np.nanmin(np.asarray(acelerador, float)[idx])) if len(idx) else None


def minima_da_curva(velocidade: np.ndarray, track, trecho) -> Optional[float]:
    """A minima dentro da curva (do inicio ao fim dela), a mesma janela da minima do 45."""
    if not trecho.tem_curva:
        return None
    v = np.asarray(velocidade, float)[_janela(track, trecho.entrada_s, trecho.saida_s)]
    return float(np.nanmin(v)) if np.isfinite(v).any() else None


def pontos_do_trecho(grade: Dict[str, np.ndarray], total: float, track, trechos: Sequence[Any], k: int) -> Dict[str, Any]:
    """Os pontos de um trecho numa volta: a freada, a entrada, a retomada, a minima e a velocidade na freada."""
    t = trechos[k]
    freada = ponto_de_freada(grade["freio"], track, inicio_da_busca_da_freada(trechos, k), t.apice_s) if t.tem_curva else None
    ret = retomada(grade["acelerador"], track, t)
    v = np.asarray(grade["velocidade"], float)
    return {
        "trecho": t.nome,
        "freada": freada,
        "entrada": float(t.entrada_s) if t.tem_curva else None,
        "retomada": ret,
        "minimaKmh": minima_da_curva(v, track, t),
        "velocidadeNaFreadaKmh": float(v[int(track.index_of(freada))]) if freada is not None else None,
        "semTirarOPe": sem_tirar_o_pe(grade["acelerador"], track, t),
        "aceleradorMinimo": acelerador_minimo(grade["acelerador"], track, t),
    }


# ── a causa ──────────────────────────────────────────────────────────────

def causa_do_engenheiro(medida: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """ADR 0033, item 1: a causa do 45 (a parte da perda que mais perdeu, acima do corte) como causa do engenheiro.
    None: sem causa acima do corte (o trecho fica na lista so com a perda)."""
    if not medida:
        return None
    c = causa_da_curva(medida)
    if not c:
        return None
    if c["trecho"] == "freada" and c.get("medida") == "freada":
        causa = "freada cedo" if float(c["valor"]) < 0 else "freada tarde"
        return {"causa": causa, "acao": "freie", "valor": float(c["valor"]), "unidade": "m"}
    if c["trecho"] == "minima" and c.get("medida") == "minima":
        return {"causa": "mínima baixa", "acao": "vire", "valor": float(c["valor"]), "unidade": "km/h"}
    if c["trecho"] == "minima" and c.get("medida") == "tracado":
        return {"causa": f"traçado por {c.get('lado') or 'fora'}", "acao": "vire", "valor": float(c["valor"]), "unidade": "m"}
    if c["trecho"] == "saida":
        a = medida.get("aceleradorM")
        if a is not None and float(a) >= CORTE_ACELERADOR_M:
            return {"causa": "acelerador tarde", "acao": "acelere", "valor": float(a), "unidade": "m"}
    return None


# ── a frase ──────────────────────────────────────────────────────────────

def _d(s_ponto: float, s_marco: float, L: float) -> float:
    """O ponto menos o marco, pelo caminho mais curto na volta (positivo: o marco vem antes)."""
    return (float(s_ponto) - float(s_marco) + L / 2) % L - L / 2


def arredondar_5(metros: float) -> int:
    return int(math.floor(abs(metros) / ARREDONDAR_M + 0.5) * ARREDONDAR_M)


def _artigo(nome: str) -> Tuple[str, str]:
    """("na", "da") ou ("no", "do"), pelo genero do nome do marco."""
    feminino = nome.startswith(("placa", "passarela"))
    return ("na", "da") if feminino else ("no", "do")


def escolher_marco(acao: str, s_ponto: float, pontos: Sequence[Dict[str, Any]], L: float) -> Optional[Dict[str, Any]]:
    """O marco de menor custo na janela da acao, ou None (ADR 0033, item 4)."""
    antes, depois = JANELA_FREIE_M if acao == "freie" else JANELA_VIRE_M
    melhor = None
    for p in pontos:
        d = _d(s_ponto, p["sMarco"], L)
        if (d >= 0 and d > antes) or (d < 0 and -d > depois):
            continue
        custo = d if d >= 0 else PESO_DEPOIS * (-d)
        if acao == "freie" and p["tipo"] == "placa":
            custo -= BONUS_PLACA_M
        if acao in ("vire", "acelere") and p["tipo"] == "zebra":
            custo -= BONUS_ZEBRA_M
        chave = (round(custo, 6), float(p["sMarco"]))
        if melhor is None or chave < melhor[0]:
            melhor = (chave, p, d, custo)
    if melhor is None:
        return None
    _, p, d, custo = melhor
    return {"marco": p, "d": float(d), "custo": float(custo)}


def frase_da_acao(acao: str, s_ponto: float, pontos: Sequence[Dict[str, Any]], L: float) -> Dict[str, Any]:
    """A frase de uma acao num ponto: o texto, o marco, o `d` e o ponto dito. Sem marco na janela: `marco` None."""
    escolha = escolher_marco(acao, s_ponto, pontos, L)
    if escolha is None:
        return {"acao": acao, "frase": f"{acao} no ponto marcado", "marco": None, "d": None,
                "sDito": float(s_ponto) % L, "comMarco": False}
    p, d = escolha["marco"], escolha["d"]
    nome = p["nome"]
    no, do = _artigo(nome)
    if abs(d) < NO_MARCO_M:
        texto, s_dito = f"{acao} {no} {nome}", float(p["sMarco"])
    else:
        m = arredondar_5(d)
        texto = f"{acao} {m} metros {'depois' if d > 0 else 'antes'} {do} {nome}"
        s_dito = (float(p["sMarco"]) + (m if d > 0 else -m)) % L
    return {"acao": acao, "frase": texto, "marco": {k: p.get(k) for k in ("id", "tipo", "valor", "lado", "ponta", "sMarco", "nome")},
            "d": round(float(d), 1), "custo": round(escolha["custo"], 1), "sDito": round(s_dito, 1), "comMarco": True}


def frase_sem_tirar_o_pe(s_entrada: float, L: float) -> Dict[str, Any]:
    """ADR 0033, emenda de 16/11, item 3: "sem tirar o pé", sem marco e sem metros (o ponto e o inicio da curva)."""
    return {"acao": SEM_TIRAR_O_PE, "frase": SEM_TIRAR_O_PE, "marco": None, "d": None,
            "sDito": round(float(s_entrada) % L, 1), "comMarco": False}


def fala_do_aviso(trecho: str, frase: str) -> str:
    """O molde curto da voz (ADR 0033, emenda de 16/11, item 2): so a frase, sem "Curva N:" e sem a vinheta:
    "Freie 10 metros depois da placa de 100."."""
    return f"{frase[0].upper()}{frase[1:]}."


def escrita_do_aviso(trecho: str, frase: str) -> str:
    """O cartao do radio e a janela do jogo continuam com "Curva N: <frase>"."""
    n = numero_da_curva(trecho)
    return f"Curva {n}: {frase}" if n is not None else f"{frase[0].upper()}{frase[1:]}"


# ── os blocos de voz ─────────────────────────────────────────────────────

def primeira_acao(pontos: Dict[str, Any], L: float) -> Optional[float]:
    """A freada ou a entrada, a que vier antes na volta (a freada pode estar antes do comeco do trecho)."""
    f, e = pontos.get("freada"), pontos.get("entrada")
    if f is None or e is None:
        return None if f is None and e is None else float(f if f is not None else e)
    # andando para a frente a partir da freada, a entrada chega em menos de meia volta: a freada vem antes
    return float(f) if (float(e) - float(f)) % L < L / 2 else float(e)


def blocos_de_voz(grade: Dict[str, np.ndarray], total: float, track, trechos: Sequence[Any]) -> List[Dict[str, Any]]:
    """ADR 0033, item 5: da retomada do trecho anterior (com curva) a 1,0 s antes da primeira acao do trecho."""
    el = np.asarray(grade["elapsed"], float)
    curvas = [k for k, t in enumerate(trechos) if t.tem_curva]
    pts = {k: pontos_do_trecho(grade, total, track, trechos, k) for k in curvas}
    blocos = []
    for j, k in enumerate(curvas):
        anterior = curvas[j - 1]
        inicio = pts[anterior]["retomada"]
        acao = primeira_acao(pts[k], float(track.length))
        bloco = {"trecho": trechos[k].nome, "antes": trechos[k].nome, "depoisDe": trechos[anterior].nome,
                 "inicio": inicio, "acao": acao}
        if inicio is None or acao is None:
            blocos.append({**bloco, "fim": None, "duracaoS": None, "motivo": "sem retomada no trecho anterior" if inicio is None else "sem ação"})
            continue
        L = float(track.length)
        if (acao - inicio) % L > L / 2:
            blocos.append({**bloco, "fim": None, "duracaoS": None,
                           "motivo": "a primeira ação vem antes da retomada do trecho anterior"})
            continue
        t_ini = tempo_em(el, total, track, inicio)
        t_acao = tempo_em(el, total, track, acao)
        dur_ate_acao = (t_acao - t_ini) % total
        dur = dur_ate_acao - FOLGA_ANTES_DA_FREADA_S
        if dur <= 0:
            blocos.append({**bloco, "fim": None, "duracaoS": round(dur, 2), "motivo": "a primeira ação vem menos de 1,0 s depois da retomada"})
            continue
        fim = s_no_tempo(el, total, track, t_acao - FOLGA_ANTES_DA_FREADA_S)
        blocos.append({**bloco, "fim": round(fim, 1), "duracaoS": round(dur, 2), "motivo": None,
                       "comprimentoM": round((fim - inicio) % float(track.length), 1)})
    return blocos


def s_fala(s_freada: float, v_kmh: float, t_frase: float, L: float) -> float:
    """`s_fala = s_freada − v × (t_frase + 1,0 s)`, com `v` em m/s (ADR 0033, item 5)."""
    return (float(s_freada) - float(v_kmh) / 3.6 * (float(t_frase) + FOLGA_ANTES_DA_FREADA_S)) % L


def dentro_do_bloco(s: float, bloco: Dict[str, Any], L: float) -> bool:
    if bloco.get("fim") is None or bloco.get("inicio") is None:
        return False
    comp = (float(bloco["fim"]) - float(bloco["inicio"])) % L
    return (float(s) - float(bloco["inicio"])) % L <= comp


def bloco_do_trecho(blocos: Sequence[Dict[str, Any]], trecho: str) -> Optional[Dict[str, Any]]:
    return next((b for b in blocos if b["trecho"] == trecho and b.get("fim") is not None), None)


# ── a conferencia ────────────────────────────────────────────────────────

def conferir(item: Dict[str, Any], pontos_da_volta: Dict[str, Any], L: float) -> Dict[str, Any]:
    """ADR 0033, item 8. `item`: a dica (acao, sDito, refMinimaKmh); `pontos_da_volta`: `pontos_do_trecho` da volta."""
    acao = item["acao"]
    if acao == "freie":
        v = pontos_da_volta.get("freada")
        if v is None:
            return {"aplicada": None, "valor": None, "motivo": "sem freada na volta"}
        dif = _d(v, item["sDito"], L)
        return {"aplicada": abs(dif) <= APLICADA_FREADA_M, "valor": round(float(v), 1), "difM": round(dif, 1)}
    if acao == "vire":
        v, ref = pontos_da_volta.get("minimaKmh"), item.get("refMinimaKmh")
        if v is None or ref is None:
            return {"aplicada": None, "valor": None, "motivo": "sem a mínima"}
        dif = float(v) - float(ref)
        return {"aplicada": abs(dif) <= APLICADA_MINIMA_KMH, "valor": round(float(v), 1), "difKmh": round(dif, 1)}
    if acao == SEM_TIRAR_O_PE:
        cheio, minimo = pontos_da_volta.get("semTirarOPe"), pontos_da_volta.get("aceleradorMinimo")
        if cheio is None or minimo is None:
            return {"aplicada": None, "valor": None, "motivo": "sem o acelerador no trecho"}
        return {"aplicada": bool(cheio), "valor": round(float(minimo), 2)}
    if acao == "acelere":
        v = pontos_da_volta.get("retomada")
        if v is None:
            return {"aplicada": None, "valor": None, "motivo": "sem retomada no trecho"}
        dif = _d(v, item["sDito"], L)
        return {"aplicada": abs(dif) <= APLICADA_RETOMADA_M, "valor": round(float(v), 1), "difM": round(dif, 1)}
    return {"aplicada": None, "valor": None, "motivo": "sem ação"}


def texto_da_conferencia(item: Dict[str, Any], conf: Dict[str, Any], L: float) -> str:
    """"C01: freou 2 metros depois da placa de 100; dito: 10 metros depois" (a lista inteira, na volta lenta)."""
    trecho = item["trecho"]
    if conf.get("aplicada") is None:
        return f"{trecho}: {conf.get('motivo') or 'sem medida'}"
    if item["acao"] == SEM_TIRAR_O_PE:
        if conf["aplicada"]:
            return f"{trecho}: sem tirar o pé"
        return f"{trecho}: tirou o pé (acelerador a {float(conf['valor']) * 100:.0f}%)"
    if item["acao"] == "vire":
        return (f"{trecho}: mínima {conf['valor']:.0f} km/h, referência {float(item['refMinimaKmh']):.0f} km/h"
                .replace(".", ","))
    verbo = "freou" if item["acao"] == "freie" else "acelerou"
    marco = item.get("marco")
    if not marco:
        return f"{trecho}: {verbo} a {abs(conf['difM']):.0f} m do ponto marcado".replace(".", ",")
    nome = marco["nome"]
    _, do = _artigo(nome)

    def onde(s: float) -> str:
        d = _d(s, marco["sMarco"], L)
        if abs(d) < 1:
            return f"{'na' if do == 'da' else 'no'} {nome}"
        return f"{abs(d):.0f} m {'depois' if d > 0 else 'antes'} {do} {nome}"

    return f"{trecho}: {verbo} {onde(conf['valor'])}; dito: {onde(item['sDito'])}"
