"""Borda da superficie da pista, medida nas camadas do cache (pedido 27; ADR 0025).

A superficie e a uniao de asfalto, zebra e pintura. As camadas estao em
coordenadas de mapa `(x, y)`, e no mundo `z = -y`. Em cada ponto dado, um raio
sai ao longo da normal, com passo de 0,05 m e ate 30 m, e a borda e o inicio do
primeiro trecho de ao menos 0,3 m fora da superficie: menos que isso e emenda
entre poligonos.

No asfalto, quem decide e a classificacao dos aneis, e nao a contagem par-impar:
o menor anel que contem o ponto diz se ali ha asfalto. A contagem so acerta
quando os aneis se aninham certinho. No cache de Interlagos, um `internal_hole`
pode ficar fora de qualquer anel externo ou dentro de outro buraco, e ai a
contagem da impar e o buraco vira pista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
from matplotlib.path import Path as MPath

MAX_RAY_M = 30.0
RAY_STEP_M = 0.05
# Menos que isto fora da superficie e emenda entre poligonos, nao borda.
MIN_GAP_M = 0.3


def to_world(points) -> np.ndarray:
    """Camadas do cache, em coordenadas de mapa (x, y), para o mundo (x, z = -y)."""
    out = np.array(points, dtype=float).reshape(-1, 2).copy()
    out[:, 1] = -out[:, 1]
    return out


def polyline_segments(points: np.ndarray, closed: bool) -> np.ndarray:
    """(n, 4) com (x0, z0, x1, z1) de cada segmento; fecha o anel se `closed`."""
    pts = np.asarray(points, dtype=float)
    if closed and len(pts) > 2 and not np.allclose(pts[0], pts[-1]):
        pts = np.vstack([pts, pts[:1]])
    if len(pts) < 2:
        return np.zeros((0, 4))
    return np.hstack([pts[:-1], pts[1:]])


@dataclass
class Layer:
    """Uma camada de poligonos: os segmentos e os caminhos para o teste de ponto.

    Sem `solid`, vale a regra par-impar. Com `solid`, os aneis vem do maior para o
    menor, cada um diz se e cheio ou buraco, e o menor anel que contem o ponto decide.
    """

    name: str
    segments: np.ndarray
    paths: List[MPath] = field(default_factory=list)
    solid: Optional[List[bool]] = None
    ring_segments: List[np.ndarray] = field(default_factory=list)

    def inside(self, points: np.ndarray) -> np.ndarray:
        if self.solid is not None:
            out = np.zeros(len(points), dtype=bool)
            for path, solid in zip(self.paths, self.solid):
                out[path.contains_points(points)] = solid
            return out
        count = np.zeros(len(points), dtype=int)
        for path in self.paths:
            count += path.contains_points(points).astype(int)
        return (count % 2) == 1

    def along_rays(self, origins: np.ndarray, directions: np.ndarray, samples: np.ndarray) -> np.ndarray:
        """(raios, amostras): dentro ou fora da camada ao longo de cada raio, a mesma leitura de `inside`."""
        out = np.zeros((len(origins), samples.size), dtype=bool)
        if self.solid is None:
            flags = self.inside(origins)
            for i, hits in enumerate(ray_hits(origins, directions, self.segments)):
                out[i] = profile(bool(flags[i]), hits, samples)
            return out
        for path, segments, solid in zip(self.paths, self.ring_segments, self.solid):
            starts = path.contains_points(origins)
            for i, hits in enumerate(ray_hits(origins, directions, segments)):
                if starts[i] or hits.size:
                    out[i, profile(bool(starts[i]), hits, samples)] = solid
        return out


def polygon_layer(name: str, rings: Iterable[np.ndarray]) -> Layer:
    rings = [np.asarray(r, dtype=float) for r in rings if len(r) >= 3]
    segments = np.vstack([polyline_segments(r, True) for r in rings]) if rings else np.zeros((0, 4))
    return Layer(name, segments, [MPath(r) for r in rings])


def ring_area(ring: np.ndarray) -> float:
    x, z = ring[:, 0], ring[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1))))


def asphalt_layer(loops: Iterable[Dict[str, object]]) -> Layer:
    """O asfalto pela classificacao dos aneis, do maior para o menor."""
    rings = [(to_world(loop["points"]), loop.get("classification") != "internal_hole")
             for loop in loops if len(loop["points"]) >= 3]
    rings.sort(key=lambda item: -ring_area(item[0]))
    segments = [polyline_segments(ring, True) for ring, _ in rings]
    return Layer("asfalto", np.vstack(segments) if segments else np.zeros((0, 4)), [MPath(ring) for ring, _ in rings],
                 [solid for _, solid in rings], segments)


def surface_layers(raw: Dict[str, object]) -> Tuple[Layer, Layer, Layer]:
    """Asfalto, zebra e pintura do cache, no mundo."""
    asphalt = asphalt_layer(raw["asphaltSurface"]["loops"])
    kerb = polygon_layer("zebra", [to_world(p["points"]) for p in raw["kerbGeometry"]["polygons"]])
    paint_rings = [to_world(ring) for poly in raw["markingGeometry"]["polygons"] for ring in poly["rings"]]
    return asphalt, kerb, polygon_layer("pintura", paint_rings)


def ray_hits(origins: np.ndarray, directions: np.ndarray, segments: np.ndarray,
             max_t: float = MAX_RAY_M, chunk: int = 64) -> List[np.ndarray]:
    """Para cada raio, as distancias (0 < t <= max_t) em que ele cruza algum segmento, em ordem."""
    out: List[np.ndarray] = []
    if len(segments) == 0:
        return [np.zeros(0) for _ in range(len(origins))]
    q, sv = segments[:, :2], segments[:, 2:] - segments[:, :2]
    for start in range(0, len(origins), chunk):
        o = origins[start:start + chunk][:, None, :]
        d = directions[start:start + chunk][:, None, :]
        den = d[..., 0] * sv[None, :, 1] - d[..., 1] * sv[None, :, 0]
        ok = np.abs(den) > 1e-12
        safe = np.where(ok, den, 1.0)
        diff = q[None, :, :] - o
        t = (diff[..., 0] * sv[None, :, 1] - diff[..., 1] * sv[None, :, 0]) / safe
        u = (diff[..., 0] * d[..., 1] - diff[..., 1] * d[..., 0]) / safe
        hit = ok & (t > 1e-9) & (t <= max_t) & (u >= 0) & (u < 1)
        for row in range(hit.shape[0]):
            out.append(np.sort(t[row][hit[row]]))
    return out


def profile(start_inside: bool, hits: np.ndarray, samples: np.ndarray) -> np.ndarray:
    """Dentro/fora da camada ao longo do raio, pela paridade dos cruzamentos ate cada amostra."""
    crossed = np.searchsorted(hits, samples, side="right")
    return np.logical_xor(bool(start_inside), (crossed % 2) == 1)


def first_exit(mask: np.ndarray, samples: np.ndarray, min_gap_m: float = MIN_GAP_M) -> Optional[float]:
    """Onde a superficie acaba: o inicio do primeiro trecho fora dela com ao menos `min_gap_m`.

    `None` se o raio nao sai dela ate o fim. Se ja comeca fora, a borda e 0.
    """
    step = float(samples[1] - samples[0]) if len(samples) > 1 else RAY_STEP_M
    need = max(int(np.ceil(min_gap_m / step)), 1)
    run = 0
    for k, inside in enumerate(mask):
        run = 0 if inside else run + 1
        if run >= need:
            return float(samples[k - need + 1])
    return None


def surface_edges(raw: Dict[str, object], points: np.ndarray, normal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(esquerda, direita): a distancia ate a borda da superficie em cada ponto, NaN onde o raio nao sai dela.

    `normal` aponta para a esquerda (ADR 0003).
    """
    points = np.asarray(points, dtype=float)
    normal = np.asarray(normal, dtype=float)
    samples = np.arange(0.0, MAX_RAY_M + RAY_STEP_M / 2, RAY_STEP_M)
    layers = surface_layers(raw)
    out = []
    for sign in (1.0, -1.0):
        surface = np.zeros((len(points), samples.size), dtype=bool)
        for layer in layers:
            surface |= layer.along_rays(points, sign * normal, samples)
        edge = np.full(len(points), np.nan)
        for i in range(len(points)):
            found = first_exit(surface[i], samples)
            if found is not None:
                edge[i] = found
        out.append(edge)
    return out[0], out[1]
