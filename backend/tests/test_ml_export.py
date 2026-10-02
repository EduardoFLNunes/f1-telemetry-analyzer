"""A conversao de metros para progresso, que e onde este caminho pode mentir.

O ML indexa tudo por distancia na propria grade; o coach, pelo `p` do runtime.
Ha duas reguas no meio do caminho e as duas ja enganaram o exportador:

* o `p` do runtime e `distanceAlongTrack / total`, nao o indice do vertice sobre
  o total -- e a centerline nao e equidistante;
* os metros do runtime sao os da poligonal crua do cache, e os do ML sao os da
  centerline consertada, suavizada e reparametrizada de `load_geometry`.

Os testes usam pistas sinteticas em que cada uma dessas diferencas e grande,
porque uma conversao errada passaria despercebida numa pista uniforme e lisa.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml.export.coaching import build_targets, progress_to_distance  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402


def geometry_with_uneven_spacing(path: Path) -> float:
    """Uma reta aberta em que a primeira metade e amostrada duas vezes mais densa.

    Metade dos vertices cobre o primeiro terco da distancia, e o vetor `p` do
    cache e por indice, como o gravado pelo provider. O runtime nao usa esse
    vetor: o `p` dele e distancia sobre o total.
    """
    dense = np.linspace(0.0, 300.0, 100, endpoint=False)
    sparse = np.linspace(300.0, 900.0, 100)
    xs = np.concatenate([dense, sparse])
    payload = {
        "centerline": [{"x": float(x), "z": 0.0, "distance": float(x)} for x in xs],
        "p": [i / (len(xs) - 1) for i in range(len(xs))],
        "trackLength": 900.0,
        "closedLoop": False,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return 900.0


class ProgressToDistanceTest(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = Path(self._dir.name) / "geometria.json"
        self.length = geometry_with_uneven_spacing(self.path)

    def tearDown(self):
        self._dir.cleanup()

    def test_the_ends_are_anchored(self):
        s_of_p = progress_to_distance(self.path)
        self.assertAlmostEqual(float(s_of_p(0.0)), 0.0, places=6)
        self.assertAlmostEqual(float(s_of_p(1.0)), self.length, places=4)

    def test_progress_is_distance_not_the_vertex_index(self):
        # `ProjectionEngine` devolve `p = distanceAlongTrack / total`. O vetor
        # `p` do cache, por indice, poria `p = 0,5` a 300 m daqui.
        s_of_p = progress_to_distance(self.path)
        self.assertAlmostEqual(float(s_of_p(0.5)), 450.0, places=6)

    def test_the_mapping_is_monotone(self):
        s_of_p = progress_to_distance(self.path)
        values = s_of_p(np.linspace(0.0, 1.0, 200))
        self.assertTrue(np.all(np.diff(values) >= -1e-9))

    def test_a_cache_without_distance_falls_back_to_the_polyline(self):
        body = json.loads(self.path.read_text(encoding="utf-8"))
        for vertex in body["centerline"]:
            del vertex["distance"]
        self.path.write_text(json.dumps(body), encoding="utf-8")
        s_of_p = progress_to_distance(self.path)
        self.assertAlmostEqual(float(s_of_p(1.0)), self.length, places=4)
        self.assertAlmostEqual(float(s_of_p(0.5)), 450.0, places=4)

    def test_the_declared_length_overrides_the_polyline_sum(self):
        # O cache de Interlagos declara 4334,08 m e a poligonal soma 4332,32.
        # A ponta do mapeamento tem de bater com o que a grade do ML usa.
        s_of_p = progress_to_distance(self.path, track_length=1000.0)
        self.assertAlmostEqual(float(s_of_p(1.0)), 1000.0, places=4)


RADIUS_M = 150.0
HALF_WIDTH_M = 6.0


def wiggly_circuit(path: Path) -> dict:
    """Um circulo cuja primeira metade tem uma ondulacao que o ML apaga.

    A ondulacao (0,45 m de amplitude, 4 m de comprimento de onda) fica abaixo do
    limiar de defeito de `load_geometry`, entao nao e "consertada" -- e removida
    pelo passa baixo de 60 m. A poligonal crua da primeira metade fica mais
    longa que a centerline suavizada, e a segunda metade, lisa, nao: as duas
    reguas concordam na linha e se afastam no meio da volta, que e o formato do
    erro medido em Interlagos.

    O espacamento dos vertices tambem e desigual (1 m na metade ondulada, 3 m
    na lisa) e o vetor `p` e por indice, como no cache de verdade.
    """
    circumference = 2.0 * np.pi * RADIUS_M
    half = circumference / 2.0
    arc = np.concatenate([np.arange(0.0, half, 1.0), np.arange(half, circumference - 1.5, 3.0)])
    theta = arc / RADIUS_M
    envelope = np.where(theta < np.pi, np.sin(theta) ** 2, 0.0)
    radius = RADIUS_M + 0.45 * envelope * np.sin(2.0 * np.pi * arc / 4.0)

    centre = np.column_stack([radius * np.cos(theta), radius * np.sin(theta)])
    # Anti-horario: a esquerda aponta para dentro do circulo.
    normal = -np.column_stack([np.cos(theta), np.sin(theta)])
    base = np.column_stack([RADIUS_M * np.cos(theta), RADIUS_M * np.sin(theta)])
    left, right = base + normal * HALF_WIDTH_M, base - normal * HALF_WIDTH_M

    steps = np.linalg.norm(np.diff(centre, axis=0), axis=1)
    distance = np.concatenate([[0.0], np.cumsum(steps)])
    total = float(distance[-1] + np.linalg.norm(centre[-1] - centre[0]))

    def xz(points):
        return [{"x": float(a), "z": float(b)} for a, b in points]

    payload = {
        "trackName": "sintetica",
        "trackLength": total,
        "closedLoop": True,
        "centerline": [
            {"x": float(a), "z": float(b), "worldY": 0.0, "distance": float(d)}
            for (a, b), d in zip(centre, distance)
        ],
        "normals": xz(normal),
        "boundsLeft": xz(left),
        "boundsRight": xz(right),
        "p": [i / (len(centre) - 1) for i in range(len(centre))],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {"centre": centre, "distance": distance, "total": total}


class RuntimeProgressToMlGridTest(unittest.TestCase):
    """O `s(p)` que `build_targets` usa tem de ser o `s` da grade do ML."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        cls.path = Path(cls._dir.name) / "sintetica.json"
        cls.raw = wiggly_circuit(cls.path)
        cls.track = load_geometry(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def runtime_point(self, progress: float) -> np.ndarray:
        """Onde o runtime poe o carro que esta em `p`, sobre a poligonal crua."""
        closed_d = np.append(self.raw["distance"], self.raw["total"])
        closed_c = np.vstack([self.raw["centre"], self.raw["centre"][:1]])
        target = progress * self.raw["total"]
        return np.array([np.interp(target, closed_d, closed_c[:, axis]) for axis in (0, 1)])

    def ml_s(self, progress: float) -> float:
        s, _ = self.track.project(self.runtime_point(progress))
        return float(s[0])

    def test_the_two_rulers_really_disagree_here(self):
        # Sem isto o teste abaixo passaria ate com o mapeamento antigo. A regua
        # crua chega ~9,5 m a frente perto de p = 0,45; a tolerancia la e 0,5 m.
        raw_ruler = progress_to_distance(self.path, track_length=self.track.length)
        gaps = [abs(float(raw_ruler(p)) - self.ml_s(p)) for p in np.linspace(0.05, 0.95, 19)]
        self.assertGreater(max(gaps), 8.0)

    def test_progress_lands_on_the_ml_grid(self):
        s_of_p = progress_to_distance(self.path, track=self.track)
        for progress in np.linspace(0.05, 0.95, 19):
            with self.subTest(p=round(float(progress), 3)):
                self.assertAlmostEqual(float(s_of_p(progress)), self.ml_s(progress), delta=0.5)

    def test_the_ends_meet_the_line(self):
        s_of_p = progress_to_distance(self.path, track=self.track)
        self.assertAlmostEqual(float(s_of_p(0.0)), 0.0, delta=0.5)
        self.assertAlmostEqual(float(s_of_p(1.0)), self.track.length, delta=0.5)

    def test_build_targets_cuts_the_slices_on_the_ml_grid(self):
        # A volta de referencia a 1 m/s: o tempo de cada fatia e o comprimento
        # dela na grade do ML, entao um corte na regua errada aparece direto.
        frame = pd.DataFrame(
            {
                "s": self.track.s,
                "elapsed_s": self.track.s,
                "speed_kmh": np.full(self.track.size, 3.6),
                "lap_time_s": float(self.track.length),
            }
        )
        slices = 8
        with mock.patch("ml.export.coaching.reference_lap_frame", return_value=frame):
            targets = build_targets(
                self.track,
                np.zeros(self.track.size),
                envelope=None,
                track_name="sintetica",
                microsectors=slices,
                geometry_path=self.path,
            )
        edges = [0.0] + [self.ml_s(k / slices) for k in range(1, slices)] + [self.track.length]
        for index, (expected, got) in enumerate(zip(np.diff(edges), targets.seconds)):
            with self.subTest(slice=index):
                self.assertAlmostEqual(got, expected, delta=0.5)


ARTIFACT = BACKEND_DIR.parent / "data" / "ml" / "optimization" / "optimised_lateral.npy"


@unittest.skipUnless(ARTIFACT.exists(), "tracado otimizado ausente; rode o pipeline do ML")
class RealTrackExportTest(unittest.TestCase):
    """Contra a pista de verdade, quando os artefatos estao na maquina."""

    def test_the_splits_add_up_to_the_lap(self):
        from ml.export.coaching import build_targets
        from ml.optimization.vehicle_model import load_envelope
        from ml.track.geometry import load_geometry

        targets = build_targets(
            load_geometry(), np.load(ARTIFACT), load_envelope(), track_name="vhe_interlagos"
        )
        self.assertEqual(len(targets.seconds), 60)
        # A grade acaba um passo antes da linha; se o fecho do circuito nao for
        # somado, a ultima fatia sai curta e a soma nao fecha.
        self.assertAlmostEqual(sum(targets.seconds), targets.lap_seconds, delta=0.01)
        self.assertTrue(all(value > 0.0 for value in targets.seconds))

    def test_every_slice_reports_a_plausible_minimum_speed(self):
        from ml.export.coaching import build_targets
        from ml.optimization.vehicle_model import load_envelope
        from ml.track.geometry import load_geometry

        targets = build_targets(
            load_geometry(), np.load(ARTIFACT), load_envelope(), track_name="vhe_interlagos"
        )
        speeds = [value for value in targets.min_speed_kmh if value is not None]
        self.assertEqual(len(speeds), 60)
        self.assertGreater(min(speeds), 30.0)
        self.assertLess(max(speeds), 400.0)


if __name__ == "__main__":
    unittest.main()
