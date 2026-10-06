"""A forma da linha da F1 real na grade da pista (pedido 22; ADR 0018).

A volta importada pelo FastF1 (`data/external_references/*.json`) vem nas
coordenadas do FastF1, sem calibracao (`UNCALIBRATED`). Este modulo a leva para
a mesma grade de 2 m das voltas do store v2, como `lateral(s)` (ADR 0003,
positivo a esquerda), e mede o quanto ela sai do corredor oficial.

**So a posicao entra.** Velocidade, pedais, marcha, rotacao, tempo e a
distancia que o FastF1 integra da velocidade sao de outro carro (ADR 0018) e
nao sao lidos: `load_xy` devolve so `x` e `y`.

Os passos:

1. **unidade** -- o perimetro da volta comparado com o comprimento da
   geometria oficial (`infer_unit`);
2. **alinhamento rigido com escala unica** -- rotacao, translacao, uma escala
   e, se precisar, espelhamento, ajustados contra a linha central oficial. Uma
   busca inicial por Procrustes (Umeyama) casa as duas linhas pela fracao do
   comprimento, em todos os deslocamentos ciclicos, com e sem espelho; o ICP
   refina com o ponto mais proximo da linha central. Nada deforma a linha:
   deformar esconderia o erro;
3. **grade** -- `project_sequence` nas amostras alinhadas e interpolacao linear
   em `s` entre elas, como `resample_lap` faz com as voltas do jogo;
4. **erro** -- o excesso sobre o corredor de `ml.track`
   (`corridor_violation`: largura medida mais a folga de zebra, menos a
   meia-bitola), 0 dentro dele.

O criterio foi fixado no pedido 22, antes de rodar: o alinhamento so e aceito
para uso futuro se a fracao de pontos da grade fora do corredor for de no
maximo 10% e o p95 do excesso, de no maximo 1 m.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..preprocessing.alignment import unwrap_distance
from ..preprocessing.resampling import _interp_circular
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors
from ..track.trajectory import corridor_violation

# Criterio do pedido 22, fixado antes de rodar. Medido na grade (2167 pontos).
MAX_OUTSIDE_FRACTION = 0.10
MAX_EXCESS_P95_M = 1.0

# Metros por unidade de cada candidata. O FastF1 documenta a posicao em 1/10 m;
# a unidade e confirmada pelos proprios dados (`infer_unit`), nao assumida.
UNIT_CANDIDATES: Dict[str, float] = {"m": 1.0, "dm": 0.1, "cm": 0.01, "pe": 0.3048}

# Pontos de cada linha na busca inicial (~8,7 m entre eles em Interlagos).
INITIAL_POINTS = 500

# O FastF1 tem poucas amostras: 633 numa volta de 83 s, com buracos de ate ~57 m
# numa reta. Os 60 m de `project_sequence`, pensados para o gravador a 20 Hz,
# ficariam no limite; 150 m ainda separam trechos que correm lado a lado, que
# estao a centenas de metros um do outro em `s`.
F1_MAX_STEP_M = 150.0

ICP_MAX_ITERATIONS = 200
ICP_TOLERANCE_M = 1e-6


# ---------------------------------------------------------------- leitura ---

def load_xy(path: Path) -> Tuple[np.ndarray, Dict[str, object]]:
    """(N, 2) com `x` e `y` das amostras, na ordem gravada, e a identificacao da volta.

    Le so a posicao. Nenhum outro canal da amostra sai daqui (ADR 0018).
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    samples = raw.get("samples") or []
    points = np.array(
        [[float(sample["x"]), float(sample["y"])] for sample in samples if "x" in sample and "y" in sample],
        dtype=float,
    )
    if len(points) != len(samples) or len(points) < 10 or not np.isfinite(points).all():
        raise ValueError(f"{path}: amostras sem x/y finitos ({len(points)} de {len(samples)})")
    meta = raw.get("metadata") or {}
    identity = {
        key: meta.get(key)
        for key in ("referenceId", "source", "year", "event", "session", "driver", "team",
                    "lapNumber", "track", "calibrationStatus", "sampleCount")
    }
    return points, identity


# ---------------------------------------------------------------- etapa 1 ---

def segment_lengths(points: np.ndarray) -> np.ndarray:
    """Comprimento de cada segmento do poligono fechado (o ultimo volta ao primeiro ponto)."""
    closed = np.vstack([points, points[:1]])
    return np.linalg.norm(np.diff(closed, axis=0), axis=1)


def infer_unit(points: np.ndarray, track_length: float) -> Dict[str, object]:
    """A unidade de `x`/`y`: a candidata que leva o perimetro mais perto da pista oficial."""
    perimeter = float(segment_lengths(points).sum())
    ratio = perimeter / float(track_length)
    unit = min(UNIT_CANDIDATES, key=lambda name: abs(math.log(perimeter * UNIT_CANDIDATES[name] / track_length)))
    metres = UNIT_CANDIDATES[unit]
    return {
        "perimetro_unidades": perimeter,
        "unidades_por_metro_da_pista": ratio,
        "unidade": unit,
        "metros_por_unidade": metres,
        "perimetro_m": perimeter * metres,
    }


def spacing_summary(lengths: np.ndarray) -> Dict[str, float]:
    lengths = np.asarray(lengths, dtype=float)
    return {
        "mediana": float(np.median(lengths)),
        "p95": float(np.percentile(lengths, 95)),
        "max": float(lengths.max()),
    }


# ---------------------------------------------------------------- etapa 2 ---

@dataclass(frozen=True)
class Similarity:
    """`destino = escala * R(rotacao) * E * origem + translacao`.

    `E` e o espelho `y -> -y` quando `mirrored`, e a identidade senao. A rotacao
    e aplicada depois do espelho.
    """

    scale: float
    rotation_rad: float
    translation: np.ndarray
    mirrored: bool = False

    @property
    def rotation_deg(self) -> float:
        return math.degrees(self.rotation_rad)

    @property
    def matrix(self) -> np.ndarray:
        c, s = math.cos(self.rotation_rad), math.sin(self.rotation_rad)
        return np.array([[c, -s], [s, c]])

    def apply(self, points: np.ndarray) -> np.ndarray:
        source = mirror(points) if self.mirrored else np.asarray(points, dtype=float)
        return self.scale * source @ self.matrix.T + np.asarray(self.translation, dtype=float)


def mirror(points: np.ndarray) -> np.ndarray:
    out = np.array(points, dtype=float, copy=True)
    out[:, 1] = -out[:, 1]
    return out


def umeyama(source: np.ndarray, target: np.ndarray, weights: Optional[np.ndarray] = None,
            fixed_scale: Optional[float] = None) -> Similarity:
    """Semelhanca propria (sem espelho) que leva `source` a `target` em minimos quadrados.

    Umeyama (1991), com pesos: uma escala, uma rotacao e uma translacao, em
    forma fechada pela SVD da covariancia cruzada. Com `fixed_scale`, a escala
    fica presa nesse valor e so rotacao e translacao sao ajustadas (a rotacao
    otima nao depende da escala; a translacao usa a escala presa). E a variante
    V1 do pedido 23.
    """
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    w = np.ones(len(source)) if weights is None else np.asarray(weights, dtype=float)
    w = w / w.sum()
    mu_s = w @ source
    mu_t = w @ target
    a = source - mu_s
    b = target - mu_t
    covariance = (b * w[:, None]).T @ a
    variance = float(np.sum(w * np.sum(a * a, axis=1)))
    u, d, vt = np.linalg.svd(covariance)
    sign = np.eye(2)
    if np.linalg.det(u) * np.linalg.det(vt) < 0:
        sign[1, 1] = -1.0
    rotation = u @ sign @ vt
    if fixed_scale is None:
        scale = float(np.trace(np.diag(d) @ sign)) / variance
    else:
        scale = float(fixed_scale)
    translation = mu_t - scale * rotation @ mu_s
    return Similarity(scale, math.atan2(rotation[1, 0], rotation[0, 0]), translation, False)


def fit_similarity(source: np.ndarray, target: np.ndarray, weights: Optional[np.ndarray],
                   mirrored: bool, fixed_scale: Optional[float] = None) -> Similarity:
    """Umeyama com o espelho escolhido antes: o espelho nao e decidido pela SVD."""
    fitted = umeyama(mirror(source) if mirrored else source, target, weights, fixed_scale)
    return replace(fitted, mirrored=bool(mirrored))


def weighted_rms(residual: np.ndarray, weights: Optional[np.ndarray] = None) -> float:
    residual = np.asarray(residual, dtype=float)
    squared = np.sum(residual**2, axis=1) if residual.ndim > 1 else residual**2
    w = np.ones(len(squared)) if weights is None else np.asarray(weights, dtype=float)
    return float(math.sqrt(np.sum(w * squared) / np.sum(w)))


def arc_weights(points: np.ndarray) -> np.ndarray:
    """Peso de cada amostra: metade dos dois segmentos que encostam nela.

    As amostras do FastF1 sao uniformes no tempo, entao ficam mais densas nas
    curvas lentas. Com este peso cada metro de pista pesa o mesmo no ajuste,
    como na grade em que o erro e medido.
    """
    lengths = segment_lengths(points)
    return 0.5 * (lengths + np.roll(lengths, 1))


def resample_by_fraction(points: np.ndarray, count: int) -> np.ndarray:
    """`count` pontos uniformes no comprimento do poligono fechado, a partir do primeiro."""
    closed = np.vstack([points, points[:1]])
    cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths(points))])
    targets = np.arange(int(count)) * cumulative[-1] / int(count)
    return np.column_stack([np.interp(targets, cumulative, closed[:, axis]) for axis in (0, 1)])


def initial_alignment(source: np.ndarray, centre: np.ndarray,
                      count: int = INITIAL_POINTS) -> Tuple[Similarity, Dict[str, object]]:
    """Procrustes com correspondencia pela fracao do comprimento.

    As duas linhas sao reamostradas em `count` pontos uniformes no comprimento.
    O ponto inicial de cada uma e arbitrario (a largada do FastF1 nao e o `s = 0`
    do jogo), entao todos os deslocamentos ciclicos sao testados, com e sem
    espelho, e fica o de menor erro quadratico. Os dois sentidos de percurso ja
    batem: as amostras estao na ordem da volta e `s` cresce no sentido da prova.
    """
    src = resample_by_fraction(source, count)
    cen = resample_by_fraction(centre, count)
    best: Optional[Tuple[float, Similarity, int]] = None
    per_mirror: Dict[str, float] = {}
    for mirrored in (False, True):
        flipped = mirror(src) if mirrored else src
        best_here = math.inf
        for shift in range(int(count)):
            target = np.roll(cen, -shift, axis=0)
            fitted = umeyama(flipped, target)
            rms = weighted_rms(fitted.apply(flipped) - target)
            best_here = min(best_here, rms)
            if best is None or rms < best[0]:
                best = (rms, replace(fitted, mirrored=mirrored), shift)
        per_mirror["com_espelho" if mirrored else "sem_espelho"] = best_here
    assert best is not None
    rms, similarity, shift = best
    return similarity, {
        "pontos": int(count),
        "rms_m": rms,
        "melhor_rms_m": per_mirror,
        "deslocamento_ciclico": int(shift),
    }


def refine_icp(source: np.ndarray, track: TrackGeometry, start: Similarity,
               weights: Optional[np.ndarray] = None,
               max_iterations: int = ICP_MAX_ITERATIONS,
               tolerance_m: float = ICP_TOLERANCE_M,
               max_step_m: float = F1_MAX_STEP_M,
               fixed_scale: Optional[float] = None) -> Tuple[Similarity, Dict[str, object]]:
    """ICP ponto-a-curva contra a linha central, com o espelho da busca inicial.

    A cada passo, cada amostra alinhada e casada com o pe da perpendicular na
    linha central (`project_sequence`, que usa a ordem da volta para nao cair no
    trecho vizinho), e a semelhanca e reajustada nesses pares. Para quando
    nenhuma amostra anda mais que `tolerance_m` entre dois passos. Com
    `fixed_scale`, a escala fica presa (variante V1 do pedido 23).
    """
    similarity = start
    moved = similarity.apply(source)
    converged = False
    iteration = 0
    last_shift = math.inf
    for iteration in range(1, int(max_iterations) + 1):
        s_hat, _ = track.project_sequence(moved, max_step_m=max_step_m)
        foot = track.to_world(s_hat, np.zeros_like(s_hat))
        similarity = fit_similarity(source, foot, weights, similarity.mirrored, fixed_scale)
        updated = similarity.apply(source)
        last_shift = float(np.max(np.linalg.norm(updated - moved, axis=1)))
        moved = updated
        if last_shift < tolerance_m:
            converged = True
            break
    _, lateral = track.project_sequence(moved, max_step_m=max_step_m)
    return similarity, {
        "iteracoes": int(iteration),
        "convergiu": converged,
        "ultimo_deslocamento_m": last_shift,
        "rms_ate_linha_central_m": weighted_rms(lateral, weights),
    }


def align(source: np.ndarray, track: TrackGeometry,
          weights: Optional[np.ndarray] = None) -> Tuple[Similarity, Dict[str, object]]:
    """Busca inicial e ICP. `source` ja em metros ou em qualquer unidade: a escala e livre."""
    if weights is None:
        weights = arc_weights(source)
    start, initial = initial_alignment(source, track.points)
    final, icp = refine_icp(source, track, start, weights)
    return final, {"busca_inicial": initial, "icp": icp}


def with_scale(similarity: Similarity, source: np.ndarray, scale: float) -> Similarity:
    """A mesma rotacao e espelho com outra escala, mantendo onde o centroide de `source` cai.

    Ponto de partida do ICP de escala fixa (V1): trocar so a escala, sem mexer
    na translacao, levaria a linha para longe da pista, porque a origem do
    sistema do FastF1 fica a quilometros dela.
    """
    centroid = np.asarray(source, dtype=float).mean(axis=0, keepdims=True)
    anchor = similarity.apply(centroid)[0]
    probe = replace(similarity, scale=float(scale), translation=np.zeros(2))
    return replace(probe, translation=anchor - probe.apply(centroid)[0])


def align_fixed_scale(source: np.ndarray, track: TrackGeometry, start: Similarity, scale: float,
                      weights: Optional[np.ndarray] = None) -> Tuple[Similarity, Dict[str, object]]:
    """V1 do pedido 23: rotacao, translacao e espelho, com a escala presa em `scale`.

    O espelho e a rotacao de partida vem do metodo principal (`start`); o ICP
    contra a linha central reajusta so rotacao e translacao.
    """
    if weights is None:
        weights = arc_weights(source)
    return refine_icp(source, track, with_scale(start, source, scale), weights, fixed_scale=scale)


def refine_icp_session(sources: Sequence[np.ndarray], track: TrackGeometry, start: Similarity,
                       max_iterations: int = ICP_MAX_ITERATIONS,
                       tolerance_m: float = ICP_TOLERANCE_M,
                       max_step_m: float = F1_MAX_STEP_M) -> Tuple[Similarity, Dict[str, object]]:
    """V2 do pedido 23: uma semelhanca so para varias voltas da mesma sessao.

    O mesmo ICP de `refine_icp`, com uma diferenca: a cada passo, cada volta e
    projetada na linha central na sua propria ordem (`project_sequence` por
    volta, porque a continuidade vale dentro da volta), e uma unica semelhanca
    e ajustada com os pares de todas as voltas juntos. Cada amostra pesa pelo
    comprimento de linha que representa (`arc_weights` de cada volta), entao as
    voltas pesam quase igual. Supoe que as posicoes da sessao estao num mesmo
    sistema de coordenadas.
    """
    sources = [np.asarray(source, dtype=float) for source in sources]
    stacked = np.vstack(sources)
    weights = np.concatenate([arc_weights(source) for source in sources])
    similarity = start
    moved = [similarity.apply(source) for source in sources]
    converged = False
    iteration = 0
    last_shift = math.inf
    for iteration in range(1, int(max_iterations) + 1):
        feet = []
        for points in moved:
            s_hat, _ = track.project_sequence(points, max_step_m=max_step_m)
            feet.append(track.to_world(s_hat, np.zeros_like(s_hat)))
        similarity = fit_similarity(stacked, np.vstack(feet), weights, similarity.mirrored)
        updated = [similarity.apply(source) for source in sources]
        last_shift = float(max(np.max(np.linalg.norm(new - old, axis=1)) for new, old in zip(updated, moved)))
        moved = updated
        if last_shift < tolerance_m:
            converged = True
            break
    laterals = [track.project_sequence(points, max_step_m=max_step_m)[1] for points in moved]
    return similarity, {
        "voltas": len(sources),
        "iteracoes": int(iteration),
        "convergiu": converged,
        "ultimo_deslocamento_m": last_shift,
        "rms_ate_linha_central_m": weighted_rms(np.concatenate(laterals), weights),
    }


# ---------------------------------------------------------------- etapa 3 ---

@dataclass(frozen=True)
class GridLine:
    """A linha alinhada nas amostras e na grade."""

    s: np.ndarray               # (N,) `s` de cada amostra
    lateral: np.ndarray         # (N,) lateral de cada amostra, positivo a esquerda
    s_unwrapped: np.ndarray     # (N,) `s` sem o salto da linha de chegada
    grid_lateral: np.ndarray    # (grade,) lateral em cada ponto da grade
    coverage: float             # fracao da volta entre a primeira e a ultima amostra
    backward_steps: int


def project_to_grid(track: TrackGeometry, points: np.ndarray,
                    max_step_m: float = F1_MAX_STEP_M) -> GridLine:
    """Amostras ja alinhadas (world X/Z) -> lateral na grade da pista.

    A interpolacao e linear em `s`, fechando o laco na linha de chegada, a mesma
    de `resample_lap`. Interpolar em `s` e nao em X/Z segue a curva da pista
    entre duas amostras distantes, em vez de cortar pela corda.
    """
    s_values, lateral = track.project_sequence(np.asarray(points, dtype=float), max_step_m=max_step_m)
    unwrapped = unwrap_distance(s_values, track.length)
    steps = np.diff(unwrapped)
    positions = np.maximum.accumulate(unwrapped)
    start = float(positions[0])
    targets = start + np.mod(track.s - start, track.length)
    grid = _interp_circular(targets, positions, lateral, float(lateral[0]), start + track.length)
    return GridLine(
        s=s_values,
        lateral=lateral,
        s_unwrapped=unwrapped,
        grid_lateral=grid,
        coverage=float(unwrapped[-1] - unwrapped[0]) / track.length,
        backward_steps=int((steps < 0).sum()),
    )


# ---------------------------------------------------------------- etapa 4 ---

def excess_on_grid(track: TrackGeometry, grid_lateral: np.ndarray) -> np.ndarray:
    """Metros fora do corredor de `ml.track`, ponto a ponto da grade (0 dentro)."""
    return corridor_violation(track, grid_lateral)


def excess_at_samples(track: TrackGeometry, s_values: np.ndarray, lateral: np.ndarray) -> np.ndarray:
    """O mesmo excesso nas amostras medidas, com o corredor interpolado em `s`."""
    low, high = track.corridor()
    low_s = np.interp(s_values, track.s, low, period=track.length)
    high_s = np.interp(s_values, track.s, high, period=track.length)
    return np.maximum(np.maximum(low_s - lateral, lateral - high_s), 0.0)


def excess_summary(excess: np.ndarray) -> Dict[str, float]:
    excess = np.asarray(excess, dtype=float)
    outside = excess > 0.0
    return {
        "pontos": int(excess.size),
        "pontos_fora": int(outside.sum()),
        "fracao_fora": float(outside.mean()),
        "mediana_m": float(np.median(excess)),
        "p95_m": float(np.percentile(excess, 95)),
        "max_m": float(excess.max()),
        "mediana_so_dos_pontos_fora_m": float(np.median(excess[outside])) if outside.any() else 0.0,
    }


def worst_sectors(sectors: Microsectors, excess: np.ndarray, top: int = 5) -> List[Dict[str, object]]:
    """Os microsetores de maior excesso maximo (desempate pelo excesso medio)."""
    rows = []
    for sector in range(sectors.count):
        values = np.asarray(excess, dtype=float)[sectors.index == sector]
        rows.append({
            "microsetor": sector,
            "rotulo": sectors.label(sector),
            "inicio_m": float(sectors.edges_s[sector]),
            "fim_m": float(sectors.edges_s[sector + 1]),
            "excesso_max_m": float(values.max()),
            "excesso_medio_m": float(values.mean()),
            "fracao_fora": float((values > 0.0).mean()),
        })
    rows.sort(key=lambda row: (-row["excesso_max_m"], -row["excesso_medio_m"]))
    return rows[: int(top)]


def verdict(summary: Dict[str, float],
            max_fraction: float = MAX_OUTSIDE_FRACTION,
            max_p95_m: float = MAX_EXCESS_P95_M) -> Dict[str, object]:
    """Aceito so se as duas condicoes do pedido 22 valem; nada e ajustado depois."""
    fraction_ok = summary["fracao_fora"] <= max_fraction
    p95_ok = summary["p95_m"] <= max_p95_m
    accepted = bool(fraction_ok and p95_ok)
    return {
        "aceito": accepted,
        "veredito": "aceito" if accepted else "não aceito",
        "fracao_fora": summary["fracao_fora"],
        "fracao_fora_max": max_fraction,
        "fracao_ok": bool(fraction_ok),
        "p95_m": summary["p95_m"],
        "p95_max_m": max_p95_m,
        "p95_ok": bool(p95_ok),
    }


# ---------------------------------------------------------------- etapa 5 ---

def sector_median_difference(sectors: Microsectors, line: np.ndarray,
                             laps_lateral: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Diferenca lateral mediana por microsetor entre `line` e a mediana das voltas.

    A linha mediana e a mediana ponto a ponto da grade; a diferenca e
    `line - mediana`, positiva quando a linha passa mais a esquerda. Devolve
    (diferenca por microsetor, linha mediana na grade).
    """
    median_line = np.median(np.asarray(laps_lateral, dtype=float), axis=0)
    difference = np.asarray(line, dtype=float) - median_line
    per_sector = np.array([float(np.median(difference[sectors.index == k])) for k in range(sectors.count)])
    return per_sector, median_line


def difference_summary(per_sector: Sequence[float]) -> Dict[str, float]:
    values = np.abs(np.asarray(per_sector, dtype=float))
    return {
        "mediana_abs_m": float(np.median(values)),
        "p90_abs_m": float(np.percentile(values, 90)),
        "max_abs_m": float(values.max()),
        "microsetor_do_max": int(np.argmax(values)),
    }
