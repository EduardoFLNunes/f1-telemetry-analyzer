"""Confere o corredor do modelo contra a faixa de limite pintada e o sinal de pneus fora do jogo (pedido 27).

    python -m ml.scripts.conferir_corredor [--saida data/ml/corredor] [--sem-voltas-cruas]

So mede e relata. Nada muda: geometria, corredor, `config`, modelos, caches,
coach e store ficam como estao, e o `geometry_id` nao muda. O cache da pista e
as gravacoes sao so lidos.

O corredor e a faixa lateral `[-width_right, +width_left]` de `load_geometry`,
medida a partir da linha central oficial ao longo da normal (positivo a
esquerda, ADR 0003); o corredor util e esse menos 0,5 m de cada lado
(`TrackGeometry.corridor`: meia-bitola de 1,0 m menos a folga de zebra de
0,5 m). A pista desenhada vem das camadas do proprio cache:

* `asphaltSurface.loops` -- o asfalto, com `external` e `internal_hole`, sem as
  faixas de pintura e de zebra;
* `kerbGeometry.polygons` -- as zebras;
* `markingGeometry.polygons` -- a area pintada, e `markingGeometry.features` --
  as linhas de pintura, das classes `limite`, `boxes` e `servico`.

As camadas estao em coordenadas de mapa `(x, y)`, e no mundo `z = -y`
(`to_world`). "Sobre a pista" e a uniao de asfalto, zebra e pintura.

Em cada ponto da grade, de cada lado, um raio sai da linha central ao longo da
normal e mede, ate 30 m:

* a faixa `limite` mais proxima, sem as faixas transversais (as que cruzam a
  linha central: largada e outras linhas pintadas atravessadas);
* a borda da superficie (asfalto, zebra ou pintura) e a borda do asfalto (sem
  zebra), cada uma no primeiro trecho de ao menos 0,3 m fora dela;
* se ha zebra entre a faixa e a borda da superficie.

Uma faixa so conta se estiver ate 1 m alem da borda da superficie: mais longe
que isso, ela e de outro trecho da pista e o lado fica "sem faixa".

Para a Parte F, o script tambem mede, sem implementar nada, onde o `tyres_out`
do jogo passa a marcar pneus fora em relacao a faixa e a borda da superficie, e
quantas amostras cada opcao de corredor poria do lado errado desse sinal.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

from ml import config  # noqa: E402

LEFT, RIGHT = "esquerda", "direita"
SIDES = (LEFT, RIGHT)

# Medicao ao longo da normal.
MAX_RAY_M = 30.0
RAY_STEP_M = 0.05
# Um trecho fora da superficie mais curto que isto e emenda entre poligonos, nao borda.
MIN_GAP_M = 0.3
# Uma faixa alem da borda da superficie por mais que isto e de outro trecho da pista.
STRIPE_BEYOND_EDGE_M = 1.0
# Classes (pedido 27, Parte B): "coincide" ate esta distancia da faixa.
COINCIDE_M = 0.5

COINCIDE = "coincide"
WIDER_ON_TRACK = "mais largo, com pista"
WIDER_OFF_TRACK = "mais largo, fora da pista"
NARROWER = "mais estreito"
NO_STRIPE = "sem faixa"
CLASSES = (COINCIDE, WIDER_ON_TRACK, WIDER_OFF_TRACK, NARROWER, NO_STRIPE)
# Subclasses de "sem faixa": o corredor contra a borda da superficie (asfalto ou zebra).
NO_STRIPE_SUB = ("coincide com a borda", "alem da borda", "antes da borda")

# Parte D: encostado na borda do corredor util.
TOUCH_M = 0.1

# Parte F: as opcoes de corredor, medidas contra o sinal do jogo (nada e implementado).
OPTION_KEEP = "1. manter como esta"
OPTION_STRIPE = "2. faixa limite (borda do asfalto onde nao ha faixa)"
OPTION_SURFACE = "3. borda da superficie (asfalto, zebra e pintura)"
OPTIONS = (OPTION_KEEP, OPTION_STRIPE, OPTION_SURFACE)
# Perfil do sinal: distancia do centro do carro ate cada referencia, + = alem dela.
PROFILE_BINS_M = np.round(np.arange(-1.5, 3.01, 0.25), 2)


# ------------------------------------------------------------------- camadas ---

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


def segment_crossings(segments: np.ndarray, other: np.ndarray) -> np.ndarray:
    """Para cada segmento de `segments`, se ele cruza algum de `other` (os dois (n, 4))."""
    out = np.zeros(len(segments), dtype=bool)
    q, sv = other[:, :2], other[:, 2:] - other[:, :2]
    for k, seg in enumerate(segments):
        p, r = seg[:2], seg[2:] - seg[:2]
        den = r[0] * sv[:, 1] - r[1] * sv[:, 0]
        ok = np.abs(den) > 1e-12
        safe = np.where(ok, den, 1.0)
        t = ((q[:, 0] - p[0]) * sv[:, 1] - (q[:, 1] - p[1]) * sv[:, 0]) / safe
        u = ((q[:, 0] - p[0]) * r[1] - (q[:, 1] - p[1]) * r[0]) / safe
        out[k] = bool(np.any(ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)))
    return out


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


@dataclass
class TrackLayers:
    asphalt: Layer
    kerb: Layer
    paint: Layer
    stripes: np.ndarray                     # (n, 4) segmentos das faixas `limite` que contam
    stripe_lines: List[np.ndarray]          # as faixas `limite` que contam, para as figuras
    transversals: List[Dict[str, object]]   # as faixas `limite` que cruzam a linha central
    other_lines: List[np.ndarray]           # `boxes` e `servico`, so para as figuras


def load_layers(raw: Dict[str, object], centre: np.ndarray, s_values: np.ndarray, step: float) -> TrackLayers:
    """As camadas do cache no mundo. `centre` e a linha central da grade, fechada no laco."""
    asphalt = polygon_layer("asfalto", [to_world(loop["points"]) for loop in raw["asphaltSurface"]["loops"]])
    kerb = polygon_layer("zebra", [to_world(p["points"]) for p in raw["kerbGeometry"]["polygons"]])
    paint_rings = [to_world(ring) for poly in raw["markingGeometry"]["polygons"] for ring in poly["rings"]]
    paint = polygon_layer("pintura", paint_rings)
    centre_segments = polyline_segments(centre, True)
    stripes, stripe_lines, transversals, others = [], [], [], []
    for feature in raw["markingGeometry"]["features"]:
        points = to_world(feature["points"])
        segments = polyline_segments(points, bool(feature.get("closed")))
        if feature.get("kind") != "limite":
            others.append(points)
            continue
        crossing = transversal_positions(segments, centre_segments, s_values, step)
        if crossing:
            transversals.append({"id": feature.get("id"), "s_m": crossing, "pontos": int(len(points)),
                                 "fechada": bool(feature.get("closed"))})
            continue
        stripes.append(segments)
        stripe_lines.append(points)
    return TrackLayers(asphalt, kerb, paint, np.vstack(stripes) if stripes else np.zeros((0, 4)),
                       stripe_lines, transversals, others)


def transversal_positions(segments: np.ndarray, centre_segments: np.ndarray, s_values: np.ndarray,
                          step: float) -> List[float]:
    """Onde a faixa cruza a linha central (em metros de `s`); vazio se nao cruza."""
    out = []
    q, sv = centre_segments[:, :2], centre_segments[:, 2:] - centre_segments[:, :2]
    for seg in segments:
        p, r = seg[:2], seg[2:] - seg[:2]
        den = r[0] * sv[:, 1] - r[1] * sv[:, 0]
        ok = np.abs(den) > 1e-12
        safe = np.where(ok, den, 1.0)
        t = ((q[:, 0] - p[0]) * sv[:, 1] - (q[:, 1] - p[1]) * sv[:, 0]) / safe
        u = ((q[:, 0] - p[0]) * r[1] - (q[:, 1] - p[1]) * r[0]) / safe
        for k in np.flatnonzero(ok & (t >= 0) & (t <= 1) & (u >= 0) & (u <= 1)):
            out.append(round(float(s_values[k % len(s_values)] + u[k] * step), 1))
    return sorted(set(out))


# --------------------------------------------------------------------- raios ---

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


@dataclass
class SideMeasure:
    corridor_m: float
    useful_m: float
    stripe_m: Optional[float]
    stripe_raw_m: Optional[float]    # a primeira faixa ate 30 m, sem a regra da borda (so para conferir)
    surface_edge_m: Optional[float]
    asphalt_edge_m: Optional[float]
    kerb_between: Optional[bool]
    on_surface_at_corridor: bool
    klass: str
    sub: Optional[str]
    deviation_m: Optional[float]     # corredor - faixa (com faixa) ou corredor - borda (sem faixa); + = mais largo


def classify(corridor_m: float, stripe_m: Optional[float], surface_edge_m: Optional[float],
             on_surface_at_corridor: bool) -> Tuple[str, Optional[str], Optional[float]]:
    """A classe da Parte B do pedido 27 para um lado de um ponto."""
    if stripe_m is not None:
        deviation = corridor_m - stripe_m
        if abs(deviation) <= COINCIDE_M:
            return COINCIDE, None, deviation
        if deviation > 0:
            return (WIDER_ON_TRACK if on_surface_at_corridor else WIDER_OFF_TRACK), None, deviation
        return NARROWER, None, deviation
    if surface_edge_m is None:
        return NO_STRIPE, None, None
    deviation = corridor_m - surface_edge_m
    if abs(deviation) <= COINCIDE_M:
        return NO_STRIPE, NO_STRIPE_SUB[0], deviation
    return NO_STRIPE, NO_STRIPE_SUB[1] if deviation > 0 else NO_STRIPE_SUB[2], deviation


def measure_side(origin_flags: Dict[str, bool], hits: Dict[str, np.ndarray], stripe_hits: np.ndarray,
                 corridor_m: float, samples: np.ndarray) -> SideMeasure:
    """As medidas de um lado de um ponto, a partir dos cruzamentos do raio com cada camada."""
    asphalt = profile(origin_flags["asfalto"], hits["asfalto"], samples)
    kerb = profile(origin_flags["zebra"], hits["zebra"], samples)
    paint = profile(origin_flags["pintura"], hits["pintura"], samples)
    surface = asphalt | kerb | paint
    road = asphalt | paint
    surface_edge = first_exit(surface, samples)
    asphalt_edge = first_exit(road, samples)
    limit = (surface_edge if surface_edge is not None else MAX_RAY_M) + STRIPE_BEYOND_EDGE_M
    valid = stripe_hits[stripe_hits <= limit]
    stripe = float(valid[0]) if valid.size else None
    stripe_raw = float(stripe_hits[0]) if stripe_hits.size else None
    kerb_between = None
    if stripe is not None:
        end = surface_edge if surface_edge is not None else MAX_RAY_M
        lo, hi = sorted((stripe, end))
        window = (samples >= lo) & (samples <= hi)
        kerb_between = bool(kerb[window].any())
    k = int(np.clip(np.searchsorted(samples, corridor_m), 0, len(samples) - 1))
    on_surface = bool(surface[k]) if corridor_m <= samples[-1] else False
    klass, sub, deviation = classify(corridor_m, stripe, surface_edge, on_surface)
    return SideMeasure(corridor_m, corridor_m - (config.CAR_HALF_WIDTH_M - config.KERB_ALLOWANCE_M),
                       stripe, stripe_raw, surface_edge, asphalt_edge, kerb_between, on_surface, klass, sub,
                       deviation)


def measure_track(track, layers: TrackLayers) -> Dict[str, List[SideMeasure]]:
    """Mede os dois lados de cada ponto da grade."""
    samples = np.arange(0.0, MAX_RAY_M + RAY_STEP_M / 2, RAY_STEP_M)
    origins = track.points
    flags = {layer.name: layer.inside(origins) for layer in (layers.asphalt, layers.kerb, layers.paint)}
    out: Dict[str, List[SideMeasure]] = {}
    for side, sign, widths in ((LEFT, 1.0, track.width_left), (RIGHT, -1.0, track.width_right)):
        directions = sign * track.normal
        hits = {layer.name: ray_hits(origins, directions, layer.segments)
                for layer in (layers.asphalt, layers.kerb, layers.paint)}
        stripe_hits = ray_hits(origins, directions, layers.stripes)
        out[side] = [
            measure_side({name: bool(flags[name][i]) for name in flags},
                         {name: hits[name][i] for name in hits}, stripe_hits[i], float(widths[i]), samples)
            for i in range(track.size)
        ]
    return out


def nearest_stripe_distance(points: np.ndarray, segments: np.ndarray, chunk: int = 256) -> np.ndarray:
    """Distancia de cada ponto ate o segmento de faixa mais proximo, em qualquer direcao."""
    out = np.full(len(points), np.inf)
    if len(segments) == 0:
        return out
    a, b = segments[:, :2], segments[:, 2:]
    ab = b - a
    length_sq = np.maximum(np.sum(ab * ab, axis=1), 1e-12)
    for start in range(0, len(points), chunk):
        p = points[start:start + chunk][:, None, :]
        t = np.clip(np.sum((p - a[None]) * ab[None], axis=2) / length_sq[None], 0.0, 1.0)
        nearest = a[None] + t[..., None] * ab[None]
        out[start:start + chunk] = np.min(np.linalg.norm(p - nearest, axis=2), axis=1)
    return out


# ------------------------------------------------------------------- trechos ---

def runs(labels: Sequence[str]) -> List[Tuple[int, int, str]]:
    """Trechos de pontos seguidos com o mesmo rotulo, fechando o laco: (inicio, fim inclusive, rotulo)."""
    n = len(labels)
    if n == 0:
        return []
    starts = [i for i in range(n) if labels[i] != labels[i - 1]]
    if not starts:
        return [(0, n - 1, labels[0])]
    out = []
    for k, start in enumerate(starts):
        end = (starts[(k + 1) % len(starts)] - 1) % n
        out.append((start, end, labels[start]))
    return out


def indices_of(start: int, end: int, n: int) -> List[int]:
    return list(range(start, end + 1)) if end >= start else list(range(start, n)) + list(range(0, end + 1))


def side_text(side: str, deviation: float, klass: str) -> str:
    """O desvio com o lado por extenso (ADR 0003): "1,20 m além da faixa, para a direita"."""
    value = f"{abs(deviation):.2f}".replace(".", ",")
    reference = "da borda" if klass == NO_STRIPE else "da faixa"
    if deviation > 0:
        return f"{value} m além {reference}, para a {side}"
    return f"{value} m antes {reference}, do lado {'esquerdo' if side == LEFT else 'direito'}"


def segments_table(track, measures: Dict[str, List[SideMeasure]], min_length_m: float = 0.0) -> List[Dict[str, object]]:
    """Trechos de cada lado e classe (subclasse incluida em "sem faixa"), com o maior desvio."""
    out = []
    n = track.size
    for side in SIDES:
        labels = [m.klass + (f" ({m.sub})" if m.sub else "") for m in measures[side]]
        for start, end, label in runs(labels):
            idx = indices_of(start, end, n)
            length = len(idx) * track.step
            if length < min_length_m:
                continue
            deviations = [measures[side][i].deviation_m for i in idx if measures[side][i].deviation_m is not None]
            worst = max(deviations, key=abs) if deviations else None
            klass = measures[side][idx[0]].klass
            out.append({
                "lado": side,
                "classe": label,
                "inicio_m": round(float(track.s[start]), 1),
                "fim_m": round(float(track.s[end] + track.step), 1),
                "comprimento_m": round(length, 1),
                "maior_desvio_m": None if worst is None else round(float(worst), 2),
                "maior_desvio_texto": None if worst is None else side_text(side, worst, klass),
            })
    return out


def class_shares(measures: Dict[str, List[SideMeasure]]) -> Dict[str, Dict[str, float]]:
    out = {}
    for side in SIDES:
        labels = [m.klass for m in measures[side]]
        subs = [m.sub for m in measures[side] if m.klass == NO_STRIPE]
        total = len(labels)
        out[side] = {k: round(100.0 * labels.count(k) / total, 2) for k in CLASSES}
        out[side]["sem faixa, por subclasse"] = {
            str(k): round(100.0 * subs.count(k) / total, 2) for k in (*NO_STRIPE_SUB, None) if subs.count(k)}
    return out


# ------------------------------------------------------------ parte C: jogo ---

def stream_has(path: Path, keys: Sequence[str], max_lines: int = 2000) -> Dict[str, bool]:
    """Se as primeiras linhas do fluxo gravado trazem cada chave (o gravador escreve todas em toda amostra)."""
    found = {key: False for key in keys}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for number, line in enumerate(handle):
            for key in keys:
                found[key] = found[key] or f'"{key}"' in line
            if all(found.values()) or number >= max_lines:
                break
    return found


def channel_sessions(sessions, laps: pd.DataFrame) -> List[Dict[str, object]]:
    """Parte C.1: as sessoes cujo fluxo traz `tyresOut` ou `offTrack`, com a pasta e as voltas do store v2."""
    roots = {str(path): name for name, path in config.recordings_roots().items()}
    out = []
    for session in sessions:
        found = stream_has(session.player_stream, ("tyresOut", "offTrack"))
        if not any(found.values()):
            continue
        folder = next((name for path, name in roots.items() if str(session.directory).startswith(path)), "?")
        mine = laps[laps["session_id"] == session.session_id]
        out.append({"sessao": session.session_id, "pasta": folder, "tyresOut": found["tyresOut"],
                    "offTrack": found["offTrack"], "voltas_no_store_v2": int(len(mine)),
                    "por_origem": {str(k): int(v) for k, v in mine["origem"].value_counts().items()}})
    return out


def option_edges(measures: Dict[str, List[SideMeasure]]) -> Dict[str, Dict[str, np.ndarray]]:
    """A borda do corredor util de cada opcao da Parte F, de cada lado, como distancia a partir da linha central.

    Todas usam a mesma regra de hoje para o corredor util (largura - meia-bitola +
    folga de zebra); muda so a largura. Onde a referencia da opcao falta, fica a
    largura de hoje.
    """
    shrink = config.CAR_HALF_WIDTH_M - config.KERB_ALLOWANCE_M

    def first(*values):
        return next(v for v in values if v is not None)

    bases = {
        OPTION_KEEP: lambda m: m.corridor_m,
        OPTION_STRIPE: lambda m: first(m.stripe_m, m.asphalt_edge_m, m.corridor_m),
        OPTION_SURFACE: lambda m: first(m.surface_edge_m, m.corridor_m),
    }
    return {name: {side: np.array([base(m) - shrink for m in measures[side]]) for side in SIDES}
            for name, base in bases.items()}


def edge_profile(offsets: np.ndarray, out_flags: np.ndarray, bins: np.ndarray = PROFILE_BINS_M) -> Dict[str, object]:
    """Fracao das amostras com `tyres_out` >= 2 por distancia ate uma referencia (+ = alem dela).

    `limiar_50pct_m` e o inicio da primeira faixa de distancia em que a maioria
    das amostras ja tem pneus fora.
    """
    rows, threshold = [], None
    for a, b in zip(bins[:-1], bins[1:]):
        sel = (offsets >= a) & (offsets < b)
        n = int(sel.sum())
        pct = round(100.0 * float(out_flags[sel].mean()), 1) if n else None
        rows.append({"de_m": float(a), "ate_m": float(b), "amostras": n, "pneus_fora_pct": pct})
        if threshold is None and pct is not None and n >= 30 and pct >= 50.0:
            threshold = float(a)
    return {"faixas": rows, "limiar_50pct_m": threshold}


def option_changes(measures: Dict[str, List[SideMeasure]],
                   edges: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, object]:
    """Quanto a borda do corredor util de cada opcao se afasta da de hoje (+ = mais largo), de cada lado."""
    out = {}
    for name in OPTIONS[1:]:
        out[name] = {}
        for side in SIDES:
            delta = edges[name][side] - edges[OPTION_KEEP][side]
            out[name][side] = {
                "mediana_m": float(np.median(delta)), "p10_m": float(np.percentile(delta, 10)),
                "p90_m": float(np.percentile(delta, 90)),
                "mais_largo_que_0_5m_pct": float(100 * np.mean(delta > 0.5)),
                "mais_estreito_que_0_5m_pct": float(100 * np.mean(delta < -0.5)),
            }
    for side in SIDES:
        out[OPTION_STRIPE][side]["pontos_pela_borda_do_asfalto"] = sum(
            1 for m in measures[side] if m.stripe_m is None and m.asphalt_edge_m is not None)
        out[OPTION_STRIPE][side]["pontos_sem_referencia"] = sum(
            1 for m in measures[side] if m.stripe_m is None and m.asphalt_edge_m is None)
        out[OPTION_SURFACE][side]["pontos_sem_referencia"] = sum(1 for m in measures[side] if m.surface_edge_m is None)
    return out


def tyres_out_check(track, measures, store, lap_ids: Sequence[str], sessions,
                    edges: Optional[Dict[str, Dict[str, np.ndarray]]] = None) -> Dict[str, object]:
    """Cruza, amostra a amostra, a posicao do centro do carro com o corredor util e o `tyres_out` do jogo."""
    from ml.data.recordings import iter_laps
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap

    low, high = track.corridor()
    by_session: Dict[str, set] = {}
    for lap_id in lap_ids:
        sid, seq = lap_id.split("#")
        by_session.setdefault(sid, set()).add(int(seq))
    available = {s.session_id: s for s in sessions}
    per_point = {side: {"amostras": np.zeros(track.size, int), "pneus_fora": np.zeros(track.size, int),
                        "largo_demais": np.zeros(track.size, int), "estreito_demais": np.zeros(track.size, int),
                        "voltas_largo": [set() for _ in range(track.size)],
                        "voltas_estreito": [set() for _ in range(track.size)]} for side in SIDES}
    used, missing = [], []
    # Quanto as amostras "estreito demais" passam da borda util, e quanto as "largo demais" ficam dentro dela.
    beyond = {side: [] for side in SIDES}
    margin = {side: [] for side in SIDES}
    # Cada amostra do lado em que o carro esta: ponto da grade, distancia do centro ate a linha central, pneus fora.
    kept = {side: {"idx": [], "towards": [], "out": []} for side in SIDES}
    for sid, sequences in sorted(by_session.items()):
        session = available.get(sid)
        if session is None:
            missing.extend(f"{sid}#{q:04d}" for q in sorted(sequences))
            continue
        for lap in iter_laps(session):
            if lap.sequence not in sequences:
                continue
            frame, _ = clean_lap(lap.frame)
            if "tyres_out" not in frame.columns or frame["tyres_out"].isna().all():
                missing.append(lap.lap_id)
                continue
            aligned, _ = align_lap(frame, track)
            aligned = aligned.dropna(subset=["s", "lateral"])
            if aligned.empty:
                missing.append(lap.lap_id)
                continue
            used.append(lap.lap_id)
            idx = track.index_of(aligned["s"].to_numpy(dtype=float))
            lateral = aligned["lateral"].to_numpy(dtype=float)
            tyres = aligned["tyres_out"].fillna(0).to_numpy(dtype=float)
            inside = (lateral >= low[idx]) & (lateral <= high[idx])
            for side, mask_side in ((LEFT, lateral >= 0), (RIGHT, lateral < 0)):
                rec = per_point[side]
                np.add.at(rec["amostras"], idx[mask_side], 1)
                np.add.at(rec["pneus_fora"], idx[mask_side & (tyres >= 2)], 1)
                wide = mask_side & inside & (tyres >= 2)
                narrow = mask_side & ~inside & (tyres < 2)
                np.add.at(rec["largo_demais"], idx[wide], 1)
                np.add.at(rec["estreito_demais"], idx[narrow], 1)
                towards = lateral if side == LEFT else -lateral
                useful = high[idx] if side == LEFT else -low[idx]
                beyond[side].extend((towards - useful)[narrow].tolist())
                margin[side].extend((useful - towards)[wide].tolist())
                kept[side]["idx"].append(idx[mask_side])
                kept[side]["towards"].append(towards[mask_side])
                kept[side]["out"].append(tyres[mask_side] >= 2)
                for i in np.unique(idx[wide]):
                    rec["voltas_largo"][i].add(lap.lap_id)
                for i in np.unique(idx[narrow]):
                    rec["voltas_estreito"][i].add(lap.lap_id)
    sections = []
    for side in SIDES:
        rec = per_point[side]
        for key, label in (("largo_demais", "dentro do corredor util e tyres_out >= 2 (corredor largo demais)"),
                           ("estreito_demais", "fora do corredor util e tyres_out < 2 (corredor estreito demais)")):
            flags = ["sim" if v > 0 else "nao" for v in rec[key]]
            laps_key = "voltas_largo" if key == "largo_demais" else "voltas_estreito"
            for start, end, value in runs(flags):
                if value != "sim":
                    continue
                idx = indices_of(start, end, track.size)
                classes = pd.Series([measures[side][i].klass for i in idx]).value_counts()
                laps = set().union(*[rec[laps_key][i] for i in idx])
                sections.append({
                    "lado": side, "situacao": label,
                    "inicio_m": round(float(track.s[start]), 1), "fim_m": round(float(track.s[end] + track.step), 1),
                    "amostras": int(sum(rec[key][i] for i in idx)), "voltas": len(laps),
                    "classe_parte_b": str(classes.index[0]), "classes_parte_b": {str(k): int(v) for k, v in classes.items()},
                })
    def stats(values):
        values = np.asarray(values, dtype=float)
        if values.size == 0:
            return None
        return {"mediana_m": float(np.median(values)), "p90_m": float(np.percentile(values, 90)), "max_m": float(values.max())}

    totals = {side: {**{k: int(per_point[side][k].sum()) for k in ("amostras", "pneus_fora", "largo_demais", "estreito_demais")},
                     "estreito_demais_alem_da_borda_util": stats(beyond[side]),
                     "largo_demais_dentro_da_borda_util": stats(margin[side])}
              for side in SIDES}

    # Onde o jogo passa a dizer "pneus fora": o perfil do sinal contra a faixa, a
    # borda da superficie e a borda util de hoje; e quantas amostras cada opcao da
    # Parte F poria do lado errado do sinal.
    profiles, options = {}, {}
    for side in SIDES:
        if not kept[side]["idx"]:
            continue
        idx = np.concatenate(kept[side]["idx"])
        towards = np.concatenate(kept[side]["towards"])
        out = np.concatenate(kept[side]["out"])
        references = {
            "faixa": np.array([np.nan if m.stripe_m is None else m.stripe_m for m in measures[side]]),
            "borda da superficie": np.array([np.nan if m.surface_edge_m is None else m.surface_edge_m
                                             for m in measures[side]]),
            "borda util de hoje": np.array([m.useful_m for m in measures[side]]),
        }
        profiles[side] = {}
        for name, ref in references.items():
            offsets = towards - ref[idx]
            ok = np.isfinite(offsets)
            profiles[side][name] = edge_profile(offsets[ok], out[ok])
        for name, edge in (edges or {}).items():
            inside = towards <= edge[side][idx]
            options.setdefault(name, {})[side] = {
                "largo_demais": int(np.sum(inside & out)),
                "estreito_demais": int(np.sum(~inside & ~out)),
                "fora_do_corredor_util": int(np.sum(~inside)),
            }
    return {"voltas_usadas": used, "voltas_sem_canal": missing, "totais": totals, "trechos": sections,
            "perfil_do_sinal": profiles, "opcoes_da_parte_f": options}


# ------------------------------------------------------- parte D: trajetorias ---

def trajectory_check(track, measures, lateral: np.ndarray) -> Dict[str, object]:
    """Nos trechos "mais largo, fora da pista" e "mais estreito": encostados na borda util e alem da faixa."""
    out = {}
    for klass in (WIDER_OFF_TRACK, NARROWER):
        row = {}
        for side, sign in ((LEFT, 1.0), (RIGHT, -1.0)):
            idx = [i for i, m in enumerate(measures[side]) if m.klass == klass]
            towards = sign * lateral[idx] if idx else np.zeros(0)
            useful = np.array([measures[side][i].useful_m for i in idx])
            stripe = np.array([measures[side][i].stripe_m for i in idx], dtype=float)
            limit = stripe - (config.CAR_HALF_WIDTH_M - config.KERB_ALLOWANCE_M)
            row[side] = {
                "pontos_da_classe": len(idx),
                "encostados_na_borda_util": int(np.sum(np.abs(useful - towards) <= TOUCH_M)) if idx else 0,
                "alem_da_faixa_mais_folga": int(np.sum(towards > limit)) if idx else 0,
            }
        out[klass] = row
    return out


# -------------------------------------------------------------------- figura ---

def figure_windows(track, segments: List[Dict[str, object]], count: int = 8, margin_m: float = 30.0) -> List[Dict[str, object]]:
    """Os trechos de maior desvio, sem repetir o mesmo lugar."""
    candidates = [s for s in segments if s["maior_desvio_m"] is not None and s["classe"] != COINCIDE]
    candidates.sort(key=lambda s: -abs(s["maior_desvio_m"]))
    chosen: List[Dict[str, object]] = []
    for seg in candidates:
        centre = (seg["inicio_m"] + seg["fim_m"]) / 2.0
        if any(abs(centre - (c["inicio_m"] + c["fim_m"]) / 2.0) < 80.0 for c in chosen):
            continue
        chosen.append(seg)
        if len(chosen) == count:
            break
    return [{**seg, "janela": (max(seg["inicio_m"] - margin_m, 0.0), seg["fim_m"] + margin_m)} for seg in chosen]


def draw_figure(path: Path, track, layers: TrackLayers, raw, windows, ai_laps: np.ndarray, my_laps: np.ndarray) -> Path:
    n = len(windows)
    cols = 2 if n > 1 else 1
    rows = int(np.ceil(n / cols)) if n else 1
    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 6.2 * rows))
    axes = np.atleast_1d(axes).ravel()
    loops = raw["asphaltSurface"]["loops"]
    for ax, window in zip(axes, windows):
        ax.set_facecolor("#cfe3c4")
        for loop in loops:
            pts = to_world(loop["points"])
            colour = "#cfe3c4" if loop.get("classification") == "internal_hole" else "#8d8d93"
            ax.fill(pts[:, 0], pts[:, 1], color=colour, zorder=1 if colour != "#cfe3c4" else 2, linewidth=0)
        for poly in raw["kerbGeometry"]["polygons"]:
            pts = to_world(poly["points"])
            ax.fill(pts[:, 0], pts[:, 1], color="#d9534f", alpha=0.8, zorder=3, linewidth=0)
        # A pintura so como contorno: um anel de limite fechado em volta do circuito
        # tem contorno de fora e de dentro, e preencher cada um cobriria a pista.
        for poly in raw["markingGeometry"]["polygons"]:
            for ring in poly["rings"]:
                pts = to_world(ring)
                ax.plot(pts[:, 0], pts[:, 1], color="white", linewidth=0.8, zorder=4)
        for line in layers.stripe_lines:
            ax.plot(line[:, 0], line[:, 1], color="black", linewidth=0.9, zorder=5)
        a, b = window["janela"]
        inside = (track.s >= a) & (track.s <= b)
        idx = np.flatnonzero(inside)
        for lap in ai_laps:
            xy = track.to_world(track.s[idx], lap[idx])
            ax.plot(xy[:, 0], xy[:, 1], color="#2f7bd6", linewidth=0.6, alpha=0.6, zorder=6)
        for lap in my_laps:
            xy = track.to_world(track.s[idx], lap[idx])
            ax.plot(xy[:, 0], xy[:, 1], color="#2e9d3f", linewidth=0.6, alpha=0.5, zorder=6)
        for widths, sign in ((track.width_left, 1.0), (track.width_right, -1.0)):
            edge = track.to_world(track.s[idx], sign * widths[idx])
            ax.plot(edge[:, 0], edge[:, 1], color="#ff7f0e", linewidth=1.6, linestyle="--", zorder=7)
        span = np.vstack([track.to_world(track.s[idx], track.width_left[idx] + 3.0),
                          track.to_world(track.s[idx], -track.width_right[idx] - 3.0)])
        pad = 4.0
        ax.set_xlim(span[:, 0].min() - pad, span[:, 0].max() + pad)
        ax.set_ylim(span[:, 1].min() - pad, span[:, 1].max() + pad)
        ax.set_aspect("equal")
        dev = window["maior_desvio_texto"] or ""
        ax.set_title(f"s = {a:.0f} a {b:.0f} m — lado {window['lado']}: {window['classe']}\n{dev}", fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes[n:]:
        ax.axis("off")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color="#8d8d93", label="asfalto"),
        plt.Rectangle((0, 0), 1, 1, color="#d9534f", alpha=0.8, label="zebra"),
        plt.Line2D([], [], color="black", linewidth=1.0, label="faixa de limite pintada"),
        plt.Line2D([], [], color="#ff7f0e", linewidth=1.6, linestyle="--", label="borda do corredor (width_left/right)"),
        plt.Line2D([], [], color="#2f7bd6", linewidth=1.0, label="voltas da IA (04/10)"),
        plt.Line2D([], [], color="#2e9d3f", linewidth=1.0, label="suas voltas (equipamento atual)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, frameon=False)
    fig.suptitle("Corredor do modelo x pista desenhada: trechos de maior desvio (pedido 27)", fontsize=12)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


# --------------------------------------------------------------------- fluxo ---

def _r(value, digits=3):
    if value is None:
        return None
    return round(float(value), digits)


def run(out_dir: Path, raw_laps: bool = True) -> Dict[str, object]:
    from ml.comparison import evolution as ev
    from ml.data.recordings import list_all_sessions
    from ml.data.store_v2 import git_commit, load_store_v2
    from ml.scripts.alinhar_fastf1 import labelled_ai_laps
    from ml.track.geometry import load_geometry

    track = load_geometry()
    if track.geometry_id != "0ed16f0dd2225990" or track.size != 2167:
        raise SystemExit(f"PARADO: a geometria e {track.geometry_id} com {track.size} pontos.")
    raw_path = config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    centre_closed = np.vstack([track.points, track.points[:1]])
    layers = load_layers(raw, centre_closed, track.s, track.step)

    # A.2: a conversao z = -y poe a linha central sobre o asfalto?
    centre_on = {
        "z_igual_menos_y": float(layers.asphalt.inside(track.points).mean()),
        "z_igual_y": float(polygon_layer("asfalto_z_y", [np.array(l["points"], float) for l in raw["asphaltSurface"]["loops"]])
                           .inside(track.points).mean()),
    }
    on_surface_centre = (layers.asphalt.inside(track.points) | layers.kerb.inside(track.points)
                         | layers.paint.inside(track.points))
    # A medida do Cowork em 10/10: da borda do corredor ate a faixa mais proxima, em qualquer direcao.
    cowork = {}
    for side, sign, widths in ((LEFT, 1.0, track.width_left), (RIGHT, -1.0, track.width_right)):
        edge = track.to_world(track.s, sign * widths)
        distance = nearest_stripe_distance(edge, layers.stripes)
        cowork[side] = {"mediana_m": float(np.median(distance)), "acima_de_1m_pct": float(100 * np.mean(distance > 1.0)),
                        "max_m": float(distance.max()), "s_do_max_m": float(track.s[int(np.argmax(distance))])}

    measures = measure_track(track, layers)
    shares = class_shares(measures)
    segments = segments_table(track, measures)
    edges = option_edges(measures)

    # Trajetorias para a Parte D e as figuras.
    store = load_store_v2(track=track)
    ai_ids = labelled_ai_laps(store.laps)["lap_id"].tolist()
    my_ids = ev.driver_laps(store.laps)["lap_id"].tolist()
    lateral = lambda lap_id: store.lap(lap_id)["lateral"].to_numpy(dtype=float)  # noqa: E731
    ai_laps = np.vstack([lateral(i) for i in ai_ids]) if ai_ids else np.zeros((0, track.size))
    my_laps = np.vstack([lateral(i) for i in my_ids]) if my_ids else np.zeros((0, track.size))

    coach = json.loads((config.repo_root() / "data" / "reference_models" / "vhe_interlagos.json").read_text(encoding="utf-8"))
    trajectories: Dict[str, Dict[str, object]] = {}
    for kind in ("volta_ia", "minha_melhor"):
        lap_id = (coach.get("references", {}).get(kind) or {}).get("lap_id")
        if lap_id and lap_id in set(store.laps["lap_id"]):
            trajectories[f"coach {kind}"] = {"origem": f"store v2, {lap_id}", "lateral": lateral(lap_id),
                                             "geometria": track.geometry_id}
    optimised = config.artifacts_root() / "optimization" / "optimised_lateral.npy"
    if optimised.exists():
        trajectories["algoritmo evolutivo (melhor individuo)"] = {
            "origem": str(optimised), "lateral": np.load(optimised),
            "geometria": "nao registrada; gravado em 24/08, antes da regravacao do cache de 25/08"}
    f1 = config.artifacts_root() / "externo" / "f1_referencia" / "referencia_2023_25.csv"
    if f1.exists():
        trajectories["referencia da F1 2023-25 (ADR 0019)"] = {
            "origem": str(f1), "lateral": pd.read_csv(f1)["lateral"].to_numpy(dtype=float), "geometria": track.geometry_id}
    part_d = {name: {"origem": t["origem"], "geometria": t["geometria"],
                     **trajectory_check(track, measures, np.asarray(t["lateral"], dtype=float))}
              for name, t in trajectories.items()}

    # Parte C: as voltas humano e ia com o canal do jogo.
    part_c = None
    if raw_laps:
        sessions = list_all_sessions()
        wanted = store.laps[store.laps["origem"].isin(["humano", "ia"])]["lap_id"].tolist()
        part_c = tyres_out_check(track, measures, store, wanted, sessions, edges)
        with_channel = channel_sessions(sessions, store.laps)
        part_c["onde_o_canal_existe"] = {"sessoes_de_interlagos": len(sessions),
                                         "sessoes_com_o_canal": len(with_channel), "sessoes": with_channel}

    out_dir.mkdir(parents=True, exist_ok=True)
    windows = figure_windows(track, segments)
    figure = draw_figure(out_dir / "corredor_x_pintura.png", track, layers, raw, windows, ai_laps, my_laps)

    per_point = []
    for i in range(track.size):
        row = {"i": i, "s": round(float(track.s[i]), 1)}
        for side, key in ((LEFT, "esq"), (RIGHT, "dir")):
            m = measures[side][i]
            row.update({
                f"corredor_{key}": _r(m.corridor_m), f"util_{key}": _r(m.useful_m), f"faixa_{key}": _r(m.stripe_m),
                f"faixa_bruta_{key}": _r(m.stripe_raw_m),
                f"borda_superficie_{key}": _r(m.surface_edge_m), f"borda_asfalto_{key}": _r(m.asphalt_edge_m),
                f"zebra_entre_{key}": m.kerb_between, f"classe_{key}": m.klass, f"subclasse_{key}": m.sub,
                f"desvio_{key}": _r(m.deviation_m),
            })
        per_point.append(row)
    pd.DataFrame(per_point).to_csv(out_dir / "corredor_por_ponto.csv", index=False)

    result = {
        "pedido": "docs/prompts/2026-10-10_27_corredor-x-pintura.md",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "geometria": {"geometry_id": track.geometry_id, "pontos": track.size, "comprimento_m": track.length,
                      "cache": str(raw_path)},
        "regras": {
            "raio_max_m": MAX_RAY_M, "passo_do_raio_m": RAY_STEP_M, "vao_minimo_m": MIN_GAP_M,
            "faixa_ate_alem_da_borda_m": STRIPE_BEYOND_EDGE_M, "coincide_m": COINCIDE_M,
            "corredor_util": "largura - (meia-bitola 1,0 m - folga de zebra 0,5 m)",
            "transversal": "faixa `limite` que cruza a linha central",
            "desvio": "corredor - faixa (com faixa) ou corredor - borda da superficie (sem faixa); + = corredor mais largo",
        },
        "conferencias": {
            "linha_central_sobre_o_asfalto": centre_on,
            "linha_central_sobre_a_pista_z_menos_y": float(on_surface_centre.mean()),
            "medida_do_cowork_borda_ate_faixa_mais_proxima": cowork,
            "faixa_bruta_descartada_pela_regra_da_borda": {
                side: int(sum(1 for m in measures[side] if m.stripe_m is None and m.stripe_raw_m is not None))
                for side in SIDES},
            "faixas_transversais": layers.transversals,
            "faixas_limite_usadas": len(layers.stripe_lines),
        },
        "parte_b": {"classes_pct": shares, "trechos": segments, "metadado_do_cache": raw["metadata"].get("builtFromLimits")},
        "parte_c": part_c,
        "parte_d": part_d,
        "parte_f": {
            "regra": "mesma regra do corredor util de hoje (largura - 0,5 m); muda so a largura; onde falta a referencia, fica a de hoje",
            "mudanca_da_borda_util": option_changes(measures, edges),
            "contra_o_sinal_do_jogo": None if part_c is None else part_c["opcoes_da_parte_f"],
        },
        "figura": {"arquivo": str(figure), "quadros": windows},
        "por_ponto": per_point,
    }
    (out_dir / "resumo.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "corredor")
    parser.add_argument("--sem-voltas-cruas", action="store_true", help="pula a Parte C (le gravacoes)")
    args = parser.parse_args(argv)
    try:
        result = run(args.saida, raw_laps=not args.sem_voltas_cruas)
    except SystemExit as stop:
        print(stop)
        return 2
    print(json.dumps(result["parte_b"]["classes_pct"], ensure_ascii=False, indent=1))
    print(json.dumps(result["conferencias"]["linha_central_sobre_o_asfalto"], indent=1))
    print(f"-> {args.saida / 'resumo.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
