"""Borda da superficie da pista, medida nas camadas do cache (pedido 27; ADR 0025).

A superficie e a uniao de asfalto, zebra e pintura. As camadas estao em
coordenadas de mapa `(x, y)`, e no mundo `z = -y`. Em cada ponto dado, um raio
sai ao longo da normal, com passo de 0,05 m e ate 30 m, e a borda e o inicio do
primeiro trecho de ao menos 0,3 m fora da superficie: menos que isso e emenda
entre poligonos.
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
    """Uma camada de poligonos (regra par-impar): os segmentos e os caminhos para o teste de ponto."""

    name: str
    segments: np.ndarray
    paths: List[MPath] = field(default_factory=list)

    def inside(self, points: np.ndarray) -> np.ndarray:
        """Par-impar: dentro se o ponto cai num numero impar de aneis (furos inclusos)."""
        count = np.zeros(len(points), dtype=int)
        for path in self.paths:
            count += path.contains_points(points).astype(int)
        return (count % 2) == 1


def polygon_layer(name: str, rings: Iterable[np.ndarray]) -> Layer:
    rings = [np.asarray(r, dtype=float) for r in rings if len(r) >= 3]
    segments = np.vstack([polyline_segments(r, True) for r in rings]) if rings else np.zeros((0, 4))
    return Layer(name, segments, [MPath(r) for r in rings])


def surface_layers(raw: Dict[str, object]) -> Tuple[Layer, Layer, Layer]:
    """Asfalto, zebra e pintura do cache, no mundo."""
    asphalt = polygon_layer("asfalto", [to_world(loop["points"]) for loop in raw["asphaltSurface"]["loops"]])
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
    flags = [layer.inside(points) for layer in layers]
    out = []
    for sign in (1.0, -1.0):
        hits = [ray_hits(points, sign * normal, layer.segments) for layer in layers]
        edge = np.full(len(points), np.nan)
        for i in range(len(points)):
            surface = np.zeros(samples.size, dtype=bool)
            for k in range(len(layers)):
                surface |= profile(bool(flags[k][i]), hits[k][i], samples)
            found = first_exit(surface, samples)
            if found is not None:
                edge[i] = found
        out.append(edge)
    return out[0], out[1]
