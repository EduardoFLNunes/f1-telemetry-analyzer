"""Geometria de Interlagos como grade uniforme em distancia.

A geometria em cache (`data/cache/tracks/*.json`) e a mesma que o runtime usa
para projetar o carro: reconstruida por raycast sobre a malha do proprio jogo,
2680 vertices para 4334,08 m. Ela vem espacada de forma irregular (~1,62 m em
media) e e isso que este modulo resolve -- todo o resto do pipeline trabalha
sobre uma grade de passo fixo, que e o que permite somar, comparar e cruzar
voltas ponto a ponto.

Convencao de coordenadas, herdada do cache e verificada contra as gravacoes:

* o plano e o world X/Z do jogo (`world_x`, `world_z` das amostras);
* `normal` aponta para a **esquerda** da pista (medido: `boundsLeft` cai em
  +normal, `boundsRight` em -normal);
* portanto o offset lateral `L` e positivo a esquerda da centerline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.signal import savgol_filter
from scipy.spatial import cKDTree

from .. import config


def _unit(vectors: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vectors, axis=-1, keepdims=True)
    return vectors / np.where(norm > 1e-12, norm, 1.0)


def _closed_derivative(values: np.ndarray, step: float, window: int, order: int) -> np.ndarray:
    """Derivada suavizada de uma serie que fecha em si mesma.

    Savitzky-Golay em vez de diferenca finita crua porque a segunda derivada da
    centerline e a curvatura, e a centerline vem de raycast sobre a malha do
    jogo: ela tem ruido de reconstrucao da ordem do centimetro. Derivar isso
    duas vezes num passo de 2 m produz curvas de raio 3,7 m em Interlagos, onde
    a curva mais fechada de verdade (a Juncao) tem raio de ~25 m.

    `mode="wrap"` fecha o laco: sem ele o filtro extrapola nas pontas e inventa
    uma curva na linha de chegada.
    """
    return savgol_filter(
        values, window_length=window, polyorder=order, deriv=1, delta=step, axis=0, mode="wrap"
    )


def _smoothing_window(smoothing_m: float, step: float) -> int:
    """Janela impar do filtro, em pontos, para um comprimento em metros."""
    window = int(round(float(smoothing_m) / float(step)))
    window += 1 - (window % 2)          # o filtro exige janela impar
    return max(window, 5)               # 5 pontos e o minimo para polyorder 3


@dataclass(frozen=True)
class TrackGeometry:
    """Centerline reamostrada em passo fixo, com tudo que depende de `s`."""

    name: str
    length: float
    step: float
    s: np.ndarray             # (N,)   distancia acumulada, 0 <= s < length
    x: np.ndarray             # (N,)   world X
    z: np.ndarray             # (N,)   world Z
    elevation: np.ndarray     # (N,)   world Y da centerline
    tangent: np.ndarray       # (N, 2) unitario, sentido de percurso
    normal: np.ndarray        # (N, 2) unitario, aponta para a esquerda
    curvature: np.ndarray     # (N,)   1/m, positivo = curva para a esquerda
    width_left: np.ndarray    # (N,)   centerline -> borda esquerda, em metros
    width_right: np.ndarray   # (N,)   centerline -> borda direita, em metros

    def __post_init__(self) -> None:
        object.__setattr__(self, "_tree", cKDTree(np.column_stack([self.x, self.z])))

    # ------------------------------------------------------------- basicos ---

    @property
    def size(self) -> int:
        return int(self.s.size)

    @property
    def points(self) -> np.ndarray:
        """(N, 2) -- a centerline no plano world X/Z."""
        return np.column_stack([self.x, self.z])

    def width(self) -> np.ndarray:
        return self.width_left + self.width_right

    def index_of(self, s_values) -> np.ndarray:
        """Indice da grade para distancias arbitrarias (com wrap na linha)."""
        wrapped = np.mod(np.asarray(s_values, dtype=float), self.length)
        return np.clip((wrapped / self.step).astype(int), 0, self.size - 1)

    # ----------------------------------------------------------- geometria ---

    def to_world(self, s_values, lateral) -> np.ndarray:
        """(s, L) -> (x, z) no world. `lateral` positivo desloca para a esquerda.

        Interpola entre pontos da grade em vez de arredondar para o mais
        proximo. O arredondamento custava ate meio passo -- 1 m -- e a ida e
        volta `to_world` -> `project` nao fechava: um `s` de 100 m voltava como
        98 m, o que estragaria qualquer medida de ponto de frenagem.
        """
        s_values = np.atleast_1d(np.asarray(s_values, dtype=float))
        lateral = np.atleast_1d(np.asarray(lateral, dtype=float))

        position = np.mod(s_values, self.length) / self.step
        lower = np.floor(position).astype(int) % self.size
        upper = (lower + 1) % self.size
        weight = (position - np.floor(position))[:, None]

        base = self.points[lower] * (1.0 - weight) + self.points[upper] * weight
        normal = _unit(self.normal[lower] * (1.0 - weight) + self.normal[upper] * weight)
        return base + normal * lateral[:, None]

    def corridor(
        self,
        car_half_width: float = config.CAR_HALF_WIDTH_M,
        kerb_allowance: float = config.KERB_ALLOWANCE_M,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Faixa de `L` que uma trajetoria pode ocupar, em cada ponto da grade.

        Retorna (limite_direito, limite_esquerdo), com o direito negativo. O
        recuo e a meia-bitola do carro: `L` e a posicao do centro do carro, e um
        centro exatamente na borda ja pos metade do carro fora dela. A folga de
        zebra entra porque as voltas limpas medidas usam zebra de verdade.
        """
        margin = float(car_half_width) - float(kerb_allowance)
        left = np.maximum(self.width_left - margin, 0.0)
        right = np.maximum(self.width_right - margin, 0.0)
        return -right, left

    # ----------------------------------------------------------- projecao ----

    def project(self, points, neighbours: int = 12) -> Tuple[np.ndarray, np.ndarray]:
        """Projeta pontos world X/Z na centerline. Retorna (s, L).

        Independente por ponto: nao usa continuidade nenhuma. Onde a pista corre
        paralela a si mesma (reta dos boxes e retorno) um ponto isolado pode cair
        no trecho errado -- use `project_sequence` para uma volta inteira.
        """
        query = np.atleast_2d(np.asarray(points, dtype=float))
        s_hat, lateral, distance = self._candidates(query, neighbours)
        rows = np.arange(query.shape[0])
        best = np.argmin(distance, axis=1)
        return s_hat[rows, best], lateral[rows, best]

    def _candidates(self, query: np.ndarray, neighbours: int):
        """Projeta cada ponto nos segmentos vizinhos. Tudo com forma (M, C)."""
        tree = object.__getattribute__(self, "_tree")
        k = int(min(neighbours, self.size))
        _, neighbour_idx = tree.query(query, k=k)
        neighbour_idx = np.atleast_2d(neighbour_idx)
        # Cada vizinho i abre dois segmentos candidatos: (i-1, i) e (i, i+1).
        starts = np.concatenate(
            [np.mod(neighbour_idx - 1, self.size), neighbour_idx], axis=1
        )

        ends = np.mod(starts + 1, self.size)
        p0 = self.points[starts]                       # (M, C, 2)
        segment = self.points[ends] - p0
        length_sq = np.sum(segment * segment, axis=-1)
        length_sq = np.where(length_sq > 1e-12, length_sq, 1.0)

        delta = query[:, None, :] - p0
        t = np.clip(np.sum(delta * segment, axis=-1) / length_sq, 0.0, 1.0)
        residual = delta - segment * t[..., None]

        # A normal do segmento, e nao a do vertice: e ela que da o sinal certo
        # de `L` quando o ponto cai no meio de um segmento.
        normal = _unit(np.stack([segment[..., 1], -segment[..., 0]], axis=-1))
        lateral = np.sum(residual * normal, axis=-1)
        s_hat = np.mod(self.s[starts] + t * self.step, self.length)
        return s_hat, lateral, np.linalg.norm(residual, axis=-1)

    def project_sequence(
        self, points, neighbours: int = 12, max_step_m: float = 60.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Projeta uma sequencia ordenada, usando continuidade para desempatar.

        A projecao independente erra em dois lugares de Interlagos: onde a reta
        dos boxes corre ao lado do retorno, e no proprio pit lane. Um ponto ali
        tem dois trechos de pista a distancias parecidas e o mais proximo nao e
        sempre o certo. Como as amostras vem em ordem temporal, o candidato que
        continua de onde o anterior parou e o candidato certo.

        `max_step_m` e o quanto o carro pode avancar entre duas amostras: a 300
        km/h e 20 Hz (o piso do pipeline) sao 4,2 m, entao 60 m cobre buracos de
        amostragem sem deixar a projecao pular meia pista.
        """
        query = np.atleast_2d(np.asarray(points, dtype=float))
        count = query.shape[0]
        if count == 0:
            return np.zeros(0), np.zeros(0)

        s_hat, lateral, distance = self._candidates(query, neighbours)
        rows = np.arange(count)
        best = np.argmin(distance, axis=1)

        out_s = np.empty(count)
        out_l = np.empty(count)

        # Semente: o ponto que menos duvida deixa, ou seja, aquele cuja melhor
        # projecao esta mais perto da centerline.
        seed = int(np.argmin(distance[rows, best]))
        out_s[seed] = s_hat[seed, best[seed]]
        out_l[seed] = lateral[seed, best[seed]]

        def choose(i: int, previous_s: float, forward: bool) -> None:
            travelled = (
                np.mod(s_hat[i] - previous_s, self.length)
                if forward
                else np.mod(previous_s - s_hat[i], self.length)
            )
            plausible = travelled <= max_step_m
            if plausible.any():
                pick = int(np.argmin(np.where(plausible, distance[i], np.inf)))
            else:
                # Carro parado, andando para tras, ou buraco longo de gravacao:
                # sem continuidade utilizavel, vale o mais proximo.
                pick = int(np.argmin(distance[i]))
            out_s[i] = s_hat[i, pick]
            out_l[i] = lateral[i, pick]

        previous = out_s[seed]
        for i in range(seed + 1, count):
            choose(i, previous, forward=True)
            previous = out_s[i]

        previous = out_s[seed]
        for i in range(seed - 1, -1, -1):
            choose(i, previous, forward=False)
            previous = out_s[i]

        return out_s, out_l


# ------------------------------------------------------------ carregamento ---

def _half_widths(
    centre: np.ndarray, normal: np.ndarray, left: np.ndarray, right: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    width_left = np.sum((left - centre) * normal, axis=1)
    width_right = -np.sum((right - centre) * normal, axis=1)
    return np.abs(width_left), np.abs(width_right)


def _defect_mask(
    centre: np.ndarray,
    distances: np.ndarray,
    tolerance: float,
    baseline_m: float = 30.0,
    closing: int = 8,
    dilate: int = 2,
) -> np.ndarray:
    """Marca os trechos em que a centerline pula para o lado.

    O defeito e da reconstrucao, nao da pista. O raycast que gera a centerline
    procura, em cada estacao, o intervalo de superficie que contem a linha de
    IA; em alguns lugares ele pega um intervalo diferente e o ponto medio salta
    varios metros de lado. As bordas saltam junto -- da para ver o degrau nas
    duas ao mesmo tempo -- e o que sai e um "Z" de 20 m no meio de uma reta.

    Depois de duas derivadas esse Z vira uma curva de raio 0,4 m. O simulador
    freava ate 22 km/h numa reta a 230 e devolvia voltas de 117 s onde o piloto
    faz 84,8.

    O criterio e o desvio em relacao a propria centerline suavizada numa janela
    de 30 m. Ele separa bem porque o defeito e localizado e a pista nao: o p95
    do desvio e 0,16 m e os defeitos chegam a 4,07 m.

    Medido em Interlagos: 10 regioes, 108 m de 4332 m (2,5% da pista), todas em
    trechos que a pista faz praticamente reta -- o que e o que torna o conserto
    por interpolacao confiavel.

    Duas alternativas mais simples foram tentadas e falharam:

    * **desvio perpendicular vertice a vertice** -- pega o pico de um vertice so
      e nao o degrau que dura 20 m;
    * **suavizar a centerline inteira** -- os degraus tem ~20 m de largura e a
      curva mais fechada da pista tem 16 m de raio, entao nao existe janela que
      apague um sem cortar a outra.
    """
    spacing = float(np.median(np.diff(distances)))
    window = _smoothing_window(baseline_m, spacing)
    baseline = savgol_filter(centre, window_length=window, polyorder=3, axis=0, mode="wrap")
    mask = np.linalg.norm(centre - baseline, axis=1) > tolerance

    # Fecha as ilhas de vertices sadios dentro de uma regiao defeituosa antes de
    # dilatar. Elas existem -- na regiao de s = 3877..3894 dois vertices ficavam
    # abaixo do limiar no meio de dez acima -- e nao sao geometria: sao os
    # pontos em que o degrau cruza a linha suavizada. Deixados de fora, a
    # interpolacao e obrigada a passar por eles e reproduz o proprio degrau,
    # so que agora em forma de "S": no reparo anterior sobrava uma curva de
    # raio 21 m onde o carro passa a 265 km/h.
    #
    # O fechamento so preenche vaos *entre* defeitos ja detectados, entao
    # aumenta-lo nao cria regiao nova. 8 passos cobrem vaos de ate ~26 m, que e
    # o que separa os dois ombros de uma mesma falha de reconstrucao (as regioes
    # de s = 744..764 e s = 796..816 sao a mesma coisa). Medido: o custo de
    # representacao da melhor volta cai de +4,25 s para +1,58 s, e o valor
    # converge -- 8, 12 e 16 dao o mesmo resultado.
    steps = max(int(closing), 0)
    if steps:
        grown = mask.copy()
        for _ in range(steps):
            grown = grown | np.roll(grown, 1) | np.roll(grown, -1)
        for _ in range(steps):
            grown = grown & np.roll(grown, 1) & np.roll(grown, -1)
        mask = grown

    for _ in range(max(int(dilate), 0)):
        mask = mask | np.roll(mask, 1) | np.roll(mask, -1)
    return mask


def _repair_defects(
    centre: np.ndarray, distances: np.ndarray, mask: np.ndarray, total: float
) -> np.ndarray:
    """Reconstroi os vertices defeituosos a partir da geometria boa em volta.

    Interpolacao monotona (PCHIP) sobre os vertices sadios, avaliada nas
    distancias dos defeituosos. E cirurgico de proposito: 0,4% da pista e
    refeito e 99,6% fica byte a byte como o cache entregou.

    Duas alternativas mais simples foram tentadas e falharam:

    * **projetar o vertice ruim na corda entre os vizinhos** -- os defeitos vem
      em par, entao o vizinho de um defeito e o outro defeito, e oito iteracoes
      depois a grade ainda tinha viradas de 43 graus;
    * **suavizar a centerline inteira** -- os defeitos tem ~15 m de largura e a
      curva mais fechada da pista tem 16 m de raio, entao nao existe janela que
      apague um sem cortar a outra.

    PCHIP e nao spline cubica comum porque a cubica oscila ao atravessar um vao,
    e uma oscilacao no conserto e o mesmo defeito com outro nome.
    """
    if not mask.any():
        return centre

    good = ~mask
    if good.sum() < 8:
        return centre

    # Estende o percurso para os dois lados para o conserto ver a pista fechada
    # e nao duas pontas soltas.
    extended_d = np.concatenate([distances[good] - total, distances[good], distances[good] + total])
    extended_p = np.vstack([centre[good], centre[good], centre[good]])

    repaired = centre.copy()
    for axis in (0, 1):
        interpolator = PchipInterpolator(extended_d, extended_p[:, axis])
        repaired[mask, axis] = interpolator(distances[mask])
    return repaired


def _clean_centerline(
    centre: np.ndarray, distances: np.ndarray, tolerance: float, total: float, rounds: int = 3
) -> Tuple[np.ndarray, int]:
    """Detecta e conserta em rodadas, ate nao sobrar defeito.

    Uma rodada so nao basta porque o detector usa a propria centerline suavizada
    como referencia, e a suavizacao de um degrau e puxada pelo degrau: os
    vertices no ombro do defeito ficam abaixo do limiar na primeira passagem e
    aparecem na segunda, quando o miolo ja foi consertado.

    O laco converge -- cada rodada so pode marcar menos -- e para sozinho quando
    a mascara sai vazia.
    """
    points = centre.copy()
    repaired = 0
    for _ in range(max(int(rounds), 1)):
        mask = _defect_mask(points, distances, tolerance)
        if not mask.any():
            break
        points = _repair_defects(points, distances, mask, total)
        repaired += int(mask.sum())
    return points, repaired


def _arc_length(points: np.ndarray, total: float) -> np.ndarray:
    """Distancia acumulada ao longo do poligono fechado, reescalada para `total`.

    A reescala existe para o `s` daqui continuar sendo o mesmo `s` do resto do
    aplicativo. Descartar vertices encurta o poligono em alguns centimetros;
    manter o comprimento de pista publicado em 4334,08 m e o que preserva a
    comparabilidade com o `distanceAlongTrack` que o runtime grava.
    """
    steps = np.linalg.norm(np.diff(np.vstack([points, points[:1]]), axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(steps)])
    scale = float(total) / float(cumulative[-1])
    return cumulative[:-1] * scale


def _resample_closed(
    distances: np.ndarray, values: np.ndarray, total_length: float, grid: np.ndarray
) -> np.ndarray:
    """Interpola valores dados em distancias irregulares para a grade uniforme.

    A pista fecha, entao o primeiro ponto e repetido no fim em `total_length`:
    sem isso a interpolacao entre o ultimo vertice e a linha de chegada vira
    extrapolacao constante.
    """
    closed_d = np.concatenate([distances, [total_length]])
    closed_v = np.concatenate([values, values[:1]], axis=0)
    if closed_v.ndim == 1:
        return np.interp(grid, closed_d, closed_v)
    return np.column_stack(
        [np.interp(grid, closed_d, closed_v[:, col]) for col in range(closed_v.shape[1])]
    )


def load_geometry(
    path: Optional[Path] = None,
    step: Optional[float] = None,
    curvature_smoothing_m: float = config.CURVATURE_SMOOTHING_M,
    centerline_smoothing_m: float = config.CENTERLINE_SMOOTHING_M,
) -> TrackGeometry:
    """Le o cache de geometria de pista e devolve a grade uniforme."""
    geometry_path = (
        Path(path) if path else config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE
    )
    if not geometry_path.exists():
        raise FileNotFoundError(
            f"geometria de pista nao encontrada em {geometry_path}. "
            "Ela e gerada pelo backend a partir dos arquivos do Assetto Corsa."
        )
    raw = json.loads(geometry_path.read_text(encoding="utf-8"))

    centerline = raw["centerline"]
    centre = np.array([[p["x"], p["z"]] for p in centerline], dtype=float)
    elevation = np.array([p.get("worldY") or 0.0 for p in centerline], dtype=float)
    normals = _unit(np.array([[n["x"], n["z"]] for n in raw["normals"]], dtype=float))
    left = np.array([[p["x"], p["z"]] for p in raw["boundsLeft"]], dtype=float)
    right = np.array([[p["x"], p["z"]] for p in raw["boundsRight"]], dtype=float)

    total_length = float(raw["trackLength"])
    width_left, width_right = _half_widths(centre, normals, left, right)
    distances = np.array([p["distance"] for p in centerline], dtype=float)
    centre, _ = _clean_centerline(
        centre, distances, config.CENTERLINE_SPIKE_TOLERANCE_M, total_length
    )

    count = config.grid_size(total_length, step)
    used_step = total_length / count
    grid = np.arange(count, dtype=float) * used_step

    grid_centre = _resample_closed(distances, centre, total_length, grid)
    grid_elevation = _resample_closed(distances, elevation, total_length, grid)
    grid_left = _resample_closed(distances, width_left, total_length, grid)
    grid_right = _resample_closed(distances, width_right, total_length, grid)
    # Guarda a linha antes da suavizacao: e contra ela que as larguras foram
    # medidas, e e o deslocamento entre as duas que redistribui a faixa util.
    unsmoothed_centre = grid_centre.copy()

    # Passa baixo na propria linha, depois do conserto cirurgico. O conserto
    # tira os degraus de metros; sobram ondulacoes de centimetros que a
    # reconstrucao por raycast deixa em todo lugar e que nenhum detector de
    # defeito pega, porque nao sao defeito -- sao a resolucao da malha. Elas nao
    # importariam se nao fossem derivadas duas vezes: 8 cm de ondulacao a cada
    # 24 m sao um raio de 21 m, e o simulador freia num raio de 21 m.
    if centerline_smoothing_m > 0:
        window = _smoothing_window(centerline_smoothing_m, used_step)
        grid_centre = savgol_filter(
            grid_centre, window_length=window, polyorder=3, axis=0, mode="wrap"
        )

    # Reparametriza por comprimento de arco real. O `distance` do cache mede o
    # poligono de 2680 vertices; a grade de 2167 pontos tem outro comprimento
    # de percurso, e sem esta passagem `s` deixa de ser comprimento de arco --
    # que e a premissa de todo o resto do pipeline.
    measured = _arc_length(grid_centre, total_length)
    grid_centre = _resample_closed(measured, grid_centre, total_length, grid)
    grid_elevation = _resample_closed(measured, grid_elevation, total_length, grid)
    grid_left = _resample_closed(measured, grid_left, total_length, grid)
    grid_right = _resample_closed(measured, grid_right, total_length, grid)
    unsmoothed_centre = _resample_closed(measured, unsmoothed_centre, total_length, grid)

    # Tangente, normal e curvatura saem da propria grade, e nao interpoladas do
    # cache: assim a curvatura da centerline e a curvatura de uma trajetoria
    # candidata do algoritmo evolutivo sao medidas do mesmo jeito, e comparaveis.
    # A grade e parametrizada por comprimento de arco, entao |dr/ds| = 1 e a
    # curvatura e simplesmente a componente normal da segunda derivada.
    window = _smoothing_window(curvature_smoothing_m, used_step)
    derivative = _closed_derivative(grid_centre, used_step, window, order=3)
    tangent = _unit(derivative)
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    second = _closed_derivative(tangent, used_step, window, order=3)
    curvature = np.sum(second * normal, axis=1)

    # A faixa util e redistribuida, e nao remedida. Suavizar a linha de
    # referencia a desloca lateralmente em relacao a linha contra a qual as
    # larguras foram medidas; o que essa mudanca faz e mover a divisao entre
    # esquerda e direita, nunca a largura total da pista.
    #
    # Projetar as bordas no frame novo -- que foi a primeira tentativa -- nao
    # preserva a largura: nas regioes consertadas o frame gira, e a projecao
    # devolvia meia-largura de 18 m numa pista de 14 m. O corredor entao
    # autorizava o otimizador a passar fora do asfalto em 48 pontos.
    offset = np.sum((grid_centre - unsmoothed_centre) * normal, axis=1)
    grid_left = np.maximum(grid_left - offset, 0.0)
    grid_right = np.maximum(grid_right + offset, 0.0)

    return TrackGeometry(
        name=str(raw.get("trackName", "unknown")),
        length=total_length,
        step=used_step,
        s=grid,
        x=grid_centre[:, 0],
        z=grid_centre[:, 1],
        elevation=grid_elevation,
        tangent=tangent,
        normal=normal,
        curvature=curvature,
        width_left=grid_left,
        width_right=grid_right,
    )
