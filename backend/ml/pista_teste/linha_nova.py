"""A linha nova num `fast_lane.ai` (pedido 47, A.4 e A.6; ADR 0029).

Uma linha do Modelo 1 e um deslocamento lateral na grade de 2 m da geometria
do projeto. Ela vira um `fast_lane.ai` com **o mesmo numero de pontos do
original**, e cada ponto `i` fica na mesma estacao da pista que o ponto `i`
original:

* **a estacao:** o ponto original `i` e projetado (em sequencia) na linha
  central do projeto, o que da `s_i`; o ponto novo e a linha nova em `s_i`. O
  ponto 0 continua no mesmo lugar ao longo da pista, o sentido e o mesmo e a
  linha fecha sozinha (o ultimo ponto antecede o primeiro);
* **a altura:** a do ponto mais proximo da linha original (projetado no
  segmento, com a altura interpolada nele);
* **a distancia:** o comprimento 3D acumulado a partir do ponto 0;
* **os campos de geometria** saem da linha nova, pelas formulas que reproduzem o
  arquivo original (`conferir_formulas`): o vetor para a frente e a direcao a
  partir do ponto anterior; a inclinacao e o Y dele; o comprimento e o
  segmento 3D ate o ponto anterior; o raio e o raio do circulo pelos pontos
  `i-1`, `i` e `i+1` em X/Z; a direcao e o lado da curva;
* **a normal** e a da superficie: vem do ponto mais proximo da linha original,
  como a altura. A **cambagem** sai dela: `direcao * (normal . esquerda)`;
* **as laterais:** as bordas da pista ficam no mesmo lugar (as do arquivo
  original: o ponto mais a lateral, na esquerda dele) e a distancia muda: e a
  distancia da linha nova ate a borda, na esquerda e na direita dela;
* **a velocidade, o acelerador e o freio:** os do ponto original da mesma
  estacao (a regra do ADR 0029, igual para C1 a C4);
* **`ObsoleteLatG` e a marca:** 0, como no original;
* **a grade:** recalculada para a linha nova (`ai_spline.construir_grade`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from .ai_spline import COL, AiSpline, construir_grade

RAIO_MAXIMO_M = 1.0e7


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n > 0, n, 1.0)


def esquerda_xz(frente: np.ndarray) -> np.ndarray:
    """A esquerda no plano X/Z: `(fz, -fx)`, a mesma convencao da normal da geometria do projeto."""
    f = _unit(np.asarray(frente, float)[:, [0, 2]])
    return np.column_stack([f[:, 1], -f[:, 0]])


def bordas(spline: AiSpline) -> Tuple[np.ndarray, np.ndarray]:
    """(esquerda, direita): as bordas da pista no arquivo, em X/Z."""
    pos = spline.pos[:, [0, 2]].astype(float)
    esq = esquerda_xz(spline.extras[:, COL["frente_x"]:COL["frente_z"] + 1])
    return (pos + esq * spline.campo("lateral_esquerda")[:, None].astype(float),
            pos - esq * spline.campo("lateral_direita")[:, None].astype(float))


# ------------------------------------------------------------ geometria ---

def geometria(pos: np.ndarray) -> Dict[str, np.ndarray]:
    """Os campos de geometria de uma linha fechada (n, 3), pelas formulas do arquivo original."""
    p = np.asarray(pos, float)
    anterior = np.roll(p, 1, axis=0)
    seguinte = np.roll(p, -1, axis=0)
    seg = p - anterior
    comprimento = np.linalg.norm(seg, axis=1)
    frente = _unit(seg)
    a, b, c = anterior[:, [0, 2]], p[:, [0, 2]], seguinte[:, [0, 2]]
    ab = np.linalg.norm(b - a, axis=1)
    bc = np.linalg.norm(c - b, axis=1)
    ca = np.linalg.norm(a - c, axis=1)
    cruz = (b - a)[:, 0] * (c - b)[:, 1] - (b - a)[:, 1] * (c - b)[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        raio = ab * bc * ca / (2.0 * np.abs((b - a)[:, 0] * (c - a)[:, 1] - (b - a)[:, 1] * (c - a)[:, 0]))
    raio = np.where(np.isfinite(raio), np.minimum(raio, RAIO_MAXIMO_M), RAIO_MAXIMO_M)
    direcao = -np.sign(cruz)
    for i in np.flatnonzero(direcao == 0):          # trecho exatamente reto: o lado do ponto anterior
        direcao[i] = direcao[i - 1] if direcao[i - 1] != 0 else 1.0
    return {"frente": frente, "inclinacao": frente[:, 1], "comprimento": comprimento, "raio": raio, "direcao": direcao}


def _projetar_na_polilinha(q: np.ndarray, poli: np.ndarray, vizinhos: int = 8):
    """Para cada ponto q (X/Z), o segmento fechado mais proximo de `poli`: (indice inicial, t, distancia)."""
    from scipy.spatial import cKDTree

    n = len(poli)
    _, near = cKDTree(poli).query(q, k=min(vizinhos, n))
    near = np.atleast_2d(near)
    starts = np.concatenate([np.mod(near - 1, n), near], axis=1)
    p0 = poli[starts]
    seg = poli[np.mod(starts + 1, n)] - p0
    l2 = np.maximum(np.sum(seg * seg, axis=-1), 1e-12)
    t = np.clip(np.sum((q[:, None, :] - p0) * seg, axis=-1) / l2, 0.0, 1.0)
    d = np.linalg.norm(q[:, None, :] - (p0 + seg * t[..., None]), axis=-1)
    best = np.argmin(d, axis=1)
    rows = np.arange(len(q))
    return starts[rows, best], t[rows, best], d[rows, best]


def _distancia_ate_a_borda(pos_xz: np.ndarray, direcao_xz: np.ndarray, borda: np.ndarray) -> np.ndarray:
    """Distancia, ao longo de `direcao_xz`, do ponto ate a polilinha fechada `borda` (a intersecao mais proxima).

    Quando o raio nao cruza a borda perto (o que so acontece se o ponto ja
    estiver fora dela), usa a distancia ao segmento mais proximo, com sinal
    negativo: o ponto esta alem da borda.
    """
    from scipy.spatial import cKDTree

    n = len(borda)
    tree = cKDTree(borda)
    out = np.empty(len(pos_xz))
    for i, (p, u) in enumerate(zip(pos_xz, direcao_xz)):
        cand = tree.query_ball_point(p, r=60.0)
        melhor = np.inf
        for j in cand:
            for k in (j - 1, j):
                a, b = borda[k % n], borda[(k + 1) % n]
                e = b - a
                den = u[0] * (-e[1]) - u[1] * (-e[0])
                if abs(den) < 1e-12:
                    continue
                rhs = a - p
                lam = (rhs[0] * (-e[1]) - rhs[1] * (-e[0])) / den
                mu = (u[0] * rhs[1] - u[1] * rhs[0]) / den
                if -1e-9 <= mu <= 1 + 1e-9 and 0.0 <= lam < melhor:
                    melhor = lam
        if np.isfinite(melhor):
            out[i] = melhor
        else:
            _, _, d = _projetar_na_polilinha(p[None, :], borda)
            out[i] = -float(d[0])
    return out


@dataclass
class LinhaNova:
    spline: AiSpline
    estacao_s: np.ndarray       # s de cada ponto na geometria do projeto
    deslocamento_m: np.ndarray  # distancia em X/Z de cada ponto novo ao ponto original da mesma estacao


def estacoes(original: AiSpline, track) -> np.ndarray:
    """O `s` de cada ponto original na linha central do projeto (projecao em sequencia)."""
    s, _ = track.project_sequence(original.pos[:, [0, 2]].astype(float))
    return s


def montar(original: AiSpline, track, lateral: np.ndarray) -> LinhaNova:
    """O `fast_lane.ai` de uma linha lateral do Modelo 1, pelas regras do modulo (ADR 0029)."""
    lateral = np.asarray(lateral, float)
    if lateral.shape != (track.size,) or not np.isfinite(lateral).all():
        raise ValueError("a linha precisa de um valor finito por ponto da grade da geometria")
    s = estacoes(original, track)
    lat = np.interp(np.mod(s, track.length), np.r_[track.s, track.length], np.r_[lateral, lateral[0]])
    xz = track.to_world(s, lat)
    return montar_por_posicoes(original, xz, s)


def montar_por_posicoes(original: AiSpline, xz: np.ndarray, s: np.ndarray = None) -> LinhaNova:
    """O arquivo novo a partir das posicoes X/Z dos pontos (uma por ponto original, na mesma ordem)."""
    n = original.n
    xz = np.asarray(xz, float)
    if xz.shape != (n, 2):
        raise ValueError(f"precisa de {n} pontos, um por ponto original")
    orig_xz = original.pos[:, [0, 2]].astype(float)
    i0, t, _ = _projetar_na_polilinha(xz, orig_xz)
    i1 = (i0 + 1) % n
    altura = original.pos[i0, 1] * (1 - t) + original.pos[i1, 1] * t
    normal = _unit(original.extras[i0, COL["normal_x"]:COL["normal_z"] + 1] * (1 - t)[:, None]
                   + original.extras[i1, COL["normal_x"]:COL["normal_z"] + 1] * t[:, None])
    pos = np.column_stack([xz[:, 0], altura, xz[:, 1]]).astype(np.float32)
    g = geometria(pos)
    esq_nova = esquerda_xz(g["frente"])
    borda_esq, borda_dir = bordas(original)
    # Uma linha do corredor do pedido 44 pode passar alguns centimetros alem da
    # borda da IA (o corredor e mais largo). Ali a lateral fica em 0: a borda
    # passa a ser a propria linha (ADR 0029; no maximo 8 cm nas linhas C1 a C4).
    lat_esq = np.maximum(_distancia_ate_a_borda(xz, esq_nova, borda_esq), 0.0)
    lat_dir = np.maximum(_distancia_ate_a_borda(xz, -esq_nova, borda_dir), 0.0)
    esq3 = np.column_stack([esq_nova[:, 0], np.zeros(n), esq_nova[:, 1]])
    extras = original.extras.astype(np.float64).copy()          # velocidade, acelerador e freio ficam
    extras[:, COL["obsolete_lat_g"]] = 0.0
    extras[:, COL["marca"]] = 0.0
    extras[:, COL["raio"]] = g["raio"]
    extras[:, COL["lateral_esquerda"]] = lat_esq
    extras[:, COL["lateral_direita"]] = lat_dir
    extras[:, COL["direcao"]] = g["direcao"]
    extras[:, COL["normal_x"]:COL["normal_z"] + 1] = normal
    extras[:, COL["cambagem"]] = g["direcao"] * np.sum(normal * esq3, axis=1)
    extras[:, COL["comprimento"]] = g["comprimento"]
    extras[:, COL["frente_x"]:COL["frente_z"] + 1] = g["frente"]
    extras[:, COL["inclinacao"]] = g["inclinacao"]
    seg = np.linalg.norm(np.diff(pos.astype(float), axis=0), axis=1)
    dist = np.r_[0.0, np.cumsum(seg)].astype(np.float32)
    nova = original.copia()
    nova.pos = pos
    nova.dist = dist
    nova.idx = np.arange(n, dtype=np.int32)
    nova.extras = extras.astype(np.float32)
    if original.tem_grade:
        g0 = original.grade
        nova.grade = construir_grade(pos, vizinhos=g0.vizinhos, densidade=g0.densidade)
    return LinhaNova(nova, np.asarray(s if s is not None else np.full(n, np.nan), float),
                     np.linalg.norm(xz - orig_xz, axis=1))


def conferir_formulas(original: AiSpline) -> Dict[str, Dict[str, float]]:
    """As regras aplicadas as posicoes do proprio original, contra os campos gravados nele (A.4).

    O ultimo ponto fica fora: no arquivo de Interlagos ele traz um comprimento de
    8,3 m e uma direcao de 0,1, que nao saem da geometria (sobra da gravacao).
    """
    refeito = montar_por_posicoes(original, original.pos[:, [0, 2]].astype(float)).spline
    m = slice(1, original.n - 1)
    out = {}
    for nome in ("raio", "lateral_esquerda", "lateral_direita", "cambagem", "direcao", "normal_x", "normal_y",
                 "normal_z", "comprimento", "frente_x", "frente_y", "frente_z", "inclinacao"):
        a = refeito.campo(nome)[m].astype(float)
        b = original.campo(nome)[m].astype(float)
        e = np.abs(a - b)
        row = {"erro_mediano": float(np.median(e)), "erro_p95": float(np.percentile(e, 95)), "erro_max": float(e.max())}
        if nome == "raio":
            rel = e / np.abs(b)
            row.update(erro_relativo_mediano=float(np.median(rel)), erro_relativo_p95=float(np.percentile(rel, 95)))
        if nome == "direcao":
            row["iguais"] = float(np.mean(a == b))
        out[nome] = row
    e = np.abs(refeito.dist.astype(float) - original.dist.astype(float))
    out["distancia"] = {"erro_mediano": float(np.median(e)), "erro_p95": float(np.percentile(e, 95)), "erro_max": float(e.max())}
    e = np.abs(refeito.pos[:, 1].astype(float) - original.pos[:, 1].astype(float))
    out["altura"] = {"erro_max": float(e.max())}
    return out
