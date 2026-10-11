"""Pedido 27: corredor do modelo x pista desenhada (camadas do cache).

Tudo sintetico: uma reta de 100 m ao longo de x, com a linha central em z = 0
e a esquerda em +z (ADR 0003). As camadas sao escritas como no cache, em
coordenadas de mapa (x, y), com z = -y no mundo.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.scripts import conferir_corredor as cc  # noqa: E402

SAMPLES = np.arange(0.0, cc.MAX_RAY_M + cc.RAY_STEP_M / 2, cc.RAY_STEP_M)


def rect_map(x0, x1, z0, z1):
    """Retangulo no mundo [x0, x1] x [z0, z1], escrito em coordenadas de mapa (y = -z)."""
    return [[x0, -z0], [x1, -z0], [x1, -z1], [x0, -z1]]


def line_map(x0, x1, z):
    return [[x, -z] for x in np.linspace(x0, x1, 11)]


def raw_track(right_stripe=True, transversal=True):
    """Asfalto de z = -4,2 a +5,2; zebra a esquerda de +5,2 a +6,5; faixas em +5 e -4."""
    features = [{"id": "esq", "kind": "limite", "closed": False, "points": line_map(-10, 110, 5.0)}]
    if right_stripe:
        features.append({"id": "dir", "kind": "limite", "closed": False, "points": line_map(-10, 110, -4.0)})
    if transversal:
        # A linha de largada: um retangulo fechado atravessando a pista em x = 50.
        features.append({"id": "largada", "kind": "limite", "closed": True,
                         "points": [[49.8, 6.0], [50.2, 6.0], [50.2, -6.0], [49.8, -6.0], [49.8, 6.0]]})
    features.append({"id": "box", "kind": "boxes", "closed": False, "points": line_map(-10, 110, 2.0)})
    return {
        "asphaltSurface": {"loops": [{"points": rect_map(-10, 110, -4.2, 5.2), "classification": "external"}]},
        "kerbGeometry": {"polygons": [{"points": rect_map(-10, 110, 5.2, 6.5)}]},
        "markingGeometry": {"polygons": [], "features": features},
    }


CENTRE = np.column_stack([np.arange(0.0, 101.0, 2.0), np.zeros(51)])
S = CENTRE[:, 0]


class CoordinatesTest(unittest.TestCase):
    def test_map_layers_go_to_the_world_with_z_minus_y(self):
        world = cc.to_world([[3.0, 4.0], [-1.0, -2.5]])
        np.testing.assert_allclose(world, [[3.0, -4.0], [-1.0, 2.5]])

    def test_the_converted_asphalt_contains_the_centre_line(self):
        layers = cc.load_layers(raw_track(), CENTRE, S, 2.0)
        self.assertTrue(layers.asphalt.inside(CENTRE).all())
        # Lido com z = y, o mesmo retangulo fica de -5,2 a +4,2 e ainda contem z = 0: o
        # teste e que +5 (a faixa) caia dentro com z = -y e fora com z = y.
        self.assertTrue(layers.asphalt.inside(np.array([[50.0, 5.0]]))[0])
        wrong = cc.polygon_layer("z=y", [np.array(rect_map(-10, 110, -4.2, 5.2))])
        self.assertFalse(wrong.inside(np.array([[50.0, 5.0]]))[0])


class TransversalTest(unittest.TestCase):
    def test_a_limit_line_across_the_centre_is_left_out(self):
        layers = cc.load_layers(raw_track(), CENTRE, S, 2.0)
        self.assertEqual([t["id"] for t in layers.transversals], ["largada"])
        # A reta falsa fecha o laco voltando por cima de si mesma, e a volta cruza a
        # faixa de novo; o cruzamento da ida esta em 50 m.
        self.assertTrue(any(abs(s - 50.0) < 0.5 for s in layers.transversals[0]["s_m"]))
        self.assertEqual(len(layers.stripe_lines), 2)          # as duas laterais; `boxes` nao conta

    def test_the_transversal_does_not_stop_the_ray(self):
        layers = cc.load_layers(raw_track(), CENTRE, S, 2.0)
        origin = np.array([[50.0, 0.0]])
        left = cc.ray_hits(origin, np.array([[0.0, 1.0]]), layers.stripes)[0]
        self.assertAlmostEqual(float(left[0]), 5.0, places=6)


class RayTest(unittest.TestCase):
    def measure(self, corridor_m, side="esquerda", right_stripe=True):
        layers = cc.load_layers(raw_track(right_stripe=right_stripe), CENTRE, S, 2.0)
        origin = np.array([[30.0, 0.0]])
        direction = np.array([[0.0, 1.0]]) if side == "esquerda" else np.array([[0.0, -1.0]])
        flags = {layer.name: bool(layer.inside(origin)[0]) for layer in (layers.asphalt, layers.kerb, layers.paint)}
        hits = {layer.name: cc.ray_hits(origin, direction, layer.segments)[0]
                for layer in (layers.asphalt, layers.kerb, layers.paint)}
        stripes = cc.ray_hits(origin, direction, layers.stripes)[0]
        return cc.measure_side(flags, hits, stripes, corridor_m, SAMPLES)

    def test_the_normal_meets_the_stripe_on_each_side(self):
        left = self.measure(5.0, "esquerda")
        right = self.measure(4.0, "direita")
        self.assertAlmostEqual(left.stripe_m, 5.0, places=6)
        self.assertAlmostEqual(right.stripe_m, 4.0, places=6)
        self.assertAlmostEqual(left.surface_edge_m, 6.5, delta=cc.RAY_STEP_M)
        self.assertAlmostEqual(left.asphalt_edge_m, 5.2, delta=cc.RAY_STEP_M)
        self.assertTrue(left.kerb_between)
        self.assertAlmostEqual(right.surface_edge_m, 4.2, delta=cc.RAY_STEP_M)
        self.assertFalse(right.kerb_between)

    def test_no_stripe_on_a_side(self):
        right = self.measure(3.0, "direita", right_stripe=False)
        self.assertIsNone(right.stripe_m)
        self.assertEqual(right.klass, cc.NO_STRIPE)
        self.assertEqual(right.sub, "antes da borda")          # 3,0 m contra a borda em 4,2 m

    def test_each_class(self):
        self.assertEqual(self.measure(5.3).klass, cc.COINCIDE)
        self.assertEqual(self.measure(6.0).klass, cc.WIDER_ON_TRACK)       # sobre a zebra
        self.assertEqual(self.measure(8.0).klass, cc.WIDER_OFF_TRACK)      # alem da zebra
        self.assertEqual(self.measure(4.0).klass, cc.NARROWER)
        self.assertAlmostEqual(self.measure(8.0).deviation_m, 3.0, places=6)
        self.assertAlmostEqual(self.measure(8.0).useful_m, 7.5, places=6)

    def test_classify_on_the_borders(self):
        self.assertEqual(cc.classify(5.5, 5.0, 6.0, True)[0], cc.COINCIDE)
        self.assertEqual(cc.classify(4.5, 5.0, 6.0, True)[0], cc.COINCIDE)
        self.assertEqual(cc.classify(5.6, 5.0, 6.0, True)[0], cc.WIDER_ON_TRACK)
        self.assertEqual(cc.classify(5.6, 5.0, 6.0, False)[0], cc.WIDER_OFF_TRACK)
        self.assertEqual(cc.classify(4.4, 5.0, 6.0, True)[0], cc.NARROWER)
        self.assertEqual(cc.classify(6.2, None, 6.0, False)[1], "coincide com a borda")
        self.assertEqual(cc.classify(7.0, None, 6.0, False)[1], "alem da borda")

    def test_a_stripe_beyond_the_surface_belongs_to_another_stretch(self):
        raw = raw_track(right_stripe=False)
        # Uma faixa de outro trecho da pista, 15 m a direita, depois da grama.
        raw["markingGeometry"]["features"].append(
            {"id": "outro", "kind": "limite", "closed": False, "points": line_map(-10, 110, -15.0)})
        layers = cc.load_layers(raw, CENTRE, S, 2.0)
        origin, direction = np.array([[30.0, 0.0]]), np.array([[0.0, -1.0]])
        flags = {layer.name: bool(layer.inside(origin)[0]) for layer in (layers.asphalt, layers.kerb, layers.paint)}
        hits = {layer.name: cc.ray_hits(origin, direction, layer.segments)[0]
                for layer in (layers.asphalt, layers.kerb, layers.paint)}
        side = cc.measure_side(flags, hits, cc.ray_hits(origin, direction, layers.stripes)[0], 4.0, SAMPLES)
        self.assertIsNone(side.stripe_m)
        self.assertAlmostEqual(side.stripe_raw_m, 15.0, places=6)
        self.assertEqual(side.klass, cc.NO_STRIPE)

    def test_a_short_seam_is_not_an_edge(self):
        mask = np.ones(SAMPLES.size, dtype=bool)
        mask[100:104] = False          # 0,2 m fora: emenda entre poligonos
        mask[200:] = False             # a borda de verdade, em 10 m
        self.assertAlmostEqual(cc.first_exit(mask, SAMPLES), 10.0, places=6)


class OptionsTest(unittest.TestCase):
    def side(self, corridor, stripe, surface, asphalt):
        return cc.SideMeasure(corridor, corridor - 0.5, stripe, stripe, surface, asphalt, None, True,
                              cc.COINCIDE, None, None)

    def test_each_option_moves_only_the_width(self):
        measures = {"esquerda": [self.side(6.0, 5.0, 6.5, 5.2), self.side(6.0, None, 6.5, 5.2)],
                    "direita": [self.side(4.0, None, None, None), self.side(4.0, 4.0, 4.2, 4.2)]}
        edges = cc.option_edges(measures)
        np.testing.assert_allclose(edges[cc.OPTION_KEEP]["esquerda"], [5.5, 5.5])
        # Faixa onde ha; sem faixa, a borda do asfalto; sem nenhuma das duas, a largura de hoje.
        np.testing.assert_allclose(edges[cc.OPTION_STRIPE]["esquerda"], [4.5, 4.7])
        np.testing.assert_allclose(edges[cc.OPTION_STRIPE]["direita"], [3.5, 3.5])
        np.testing.assert_allclose(edges[cc.OPTION_SURFACE]["esquerda"], [6.0, 6.0])
        np.testing.assert_allclose(edges[cc.OPTION_SURFACE]["direita"], [3.5, 3.7])

    def test_the_profile_finds_where_most_samples_are_out(self):
        offsets = np.concatenate([np.full(40, -0.6), np.full(40, 0.1), np.full(40, 0.6)])
        out = np.concatenate([np.zeros(40, bool), np.r_[np.ones(10, bool), np.zeros(30, bool)], np.ones(40, bool)])
        profile = cc.edge_profile(offsets, out)
        self.assertEqual(profile["limiar_50pct_m"], 0.5)
        row = next(r for r in profile["faixas"] if r["de_m"] == 0.0)
        self.assertEqual((row["amostras"], row["pneus_fora_pct"]), (40, 25.0))


class ChannelTest(unittest.TestCase):
    def test_the_stream_says_which_channels_were_recorded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "player.jsonl"
            path.write_text('{"sample": {"carPhysics": {"environment": {"roadTemp": 30}}}}\n'
                            '{"sample": {"carPhysics": {"environment": {"tyresOut": 0, "roadTemp": 30}}}}\n',
                            encoding="utf-8")
            self.assertEqual(cc.stream_has(path, ("tyresOut", "offTrack")), {"tyresOut": True, "offTrack": False})


class RunsTest(unittest.TestCase):
    def test_runs_close_the_loop(self):
        labels = ["a", "a", "b", "b", "a"]
        self.assertEqual(cc.runs(labels), [(2, 3, "b"), (4, 1, "a")])
        self.assertEqual(cc.indices_of(4, 1, 5), [4, 0, 1])

    def test_side_text_spells_the_side(self):
        self.assertEqual(cc.side_text("direita", 1.2, cc.WIDER_OFF_TRACK), "1,20 m além da faixa, para a direita")
        self.assertEqual(cc.side_text("esquerda", -0.8, cc.NARROWER), "0,80 m antes da faixa, do lado esquerdo")


if __name__ == "__main__":
    unittest.main()
