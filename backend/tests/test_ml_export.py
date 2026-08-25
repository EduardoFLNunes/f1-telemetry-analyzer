"""A conversao de metros para progresso, que e onde este caminho pode mentir.

O ML indexa tudo por distancia; o coach, por `p`. O `p` do runtime e o indice da
amostra da centerline sobre o total, e a centerline nao e equidistante -- em
Interlagos os passos vao de 1,4 a 5,0 m. Converter por regra de tres desloca os
alvos em ate 25 m, um terco de microsetor.

O teste principal aqui usa uma pista sintetica com espacamento propositalmente
desigual, porque uma conversao errada passaria despercebida numa pista uniforme.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml.export.coaching import progress_to_distance  # noqa: E402


def geometry_with_uneven_spacing(path: Path) -> float:
    """Uma reta em que a primeira metade e amostrada duas vezes mais densa.

    Metade das amostras cobre o primeiro terco da distancia. Entao `p = 0,5`
    cai em um terco da pista, e nao na metade -- que e exatamente a diferenca
    que a conversao precisa respeitar.
    """
    dense = np.linspace(0.0, 300.0, 100, endpoint=False)
    sparse = np.linspace(300.0, 900.0, 100)
    xs = np.concatenate([dense, sparse])
    payload = {
        "centerline": [{"x": float(x), "z": 0.0} for x in xs],
        "p": [i / (len(xs) - 1) for i in range(len(xs))],
        "trackLength": 900.0,
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

    def test_the_middle_of_the_index_is_not_the_middle_of_the_track(self):
        # Metade das amostras cobre um terco da pista. Uma conversao por regra
        # de tres devolveria 450 m aqui, e os alvos sairiam do lugar.
        s_of_p = progress_to_distance(self.path)
        middle = float(s_of_p(0.5))
        self.assertLess(middle, 400.0)
        self.assertAlmostEqual(middle, 300.0, delta=15.0)

    def test_the_mapping_is_monotone(self):
        s_of_p = progress_to_distance(self.path)
        values = s_of_p(np.linspace(0.0, 1.0, 200))
        self.assertTrue(np.all(np.diff(values) >= -1e-9))

    def test_a_cache_without_p_falls_back_to_the_sample_index(self):
        body = json.loads(self.path.read_text(encoding="utf-8"))
        del body["p"]
        self.path.write_text(json.dumps(body), encoding="utf-8")
        s_of_p = progress_to_distance(self.path)
        self.assertAlmostEqual(float(s_of_p(1.0)), self.length, places=4)
        self.assertAlmostEqual(float(s_of_p(0.5)), 300.0, delta=15.0)

    def test_the_declared_length_overrides_the_polyline_sum(self):
        # O cache de Interlagos declara 4334,08 m e a poligonal soma 4332,32.
        # A ponta do mapeamento tem de bater com o que a grade do ML usa.
        s_of_p = progress_to_distance(self.path, track_length=1000.0)
        self.assertAlmostEqual(float(s_of_p(1.0)), 1000.0, places=4)


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
