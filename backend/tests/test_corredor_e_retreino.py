"""O corredor novo e a regua do retreino (pedido 44; ADRs 0025 e 0026).

Tudo sintetico: uma reta falsa com asfalto e zebra, e uma tabela de voltas. Nada
de gravacao, store ou cache de verdade.
"""

from __future__ import annotations

import dataclasses
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.geometry.surface_edge import surface_edges  # noqa: E402
from ml import config  # noqa: E402
from ml.models import retreino as R  # noqa: E402
from ml.models.sequences import REFERENCE_TASK, TaskSpec, SequenceSet  # noqa: E402
from ml.track.geometry import TrackGeometry, corridor_fingerprint, with_surface_corridor  # noqa: E402

try:
    import torch  # noqa: F401
    TORCH = True
except ImportError:  # pragma: no cover
    TORCH = False


def straight_track(count: int = 201, step: float = 1.0) -> TrackGeometry:
    """Uma reta para +x. A normal aponta para a esquerda: (t_z, -t_x) = (0, -1) no mundo."""
    s = np.arange(count) * step
    tangent = np.column_stack([np.ones(count), np.zeros(count)])
    normal = np.column_stack([tangent[:, 1], -tangent[:, 0]])
    return TrackGeometry(
        name="reta", length=float(count * step), step=step, s=s, x=s.copy(), z=np.zeros(count),
        elevation=np.zeros(count), tangent=tangent, normal=normal, curvature=np.zeros(count),
        width_left=np.full(count, 5.0), width_right=np.full(count, 4.0),
        geometry_id="geo-teste", source_hash="",
    )


def rect_map(x0, x1, z0, z1):
    """Retangulo em coordenadas de mapa, onde y = -z."""
    return [[x0, -z0], [x1, -z0], [x1, -z1], [x0, -z1]]


def fake_cache(left_edge: float = -7.0, right_edge: float = 6.0, far: bool = False) -> dict:
    """Asfalto de z = -5 a z = +5 e zebra de cada lado. A esquerda da reta e z negativo."""
    kerbs = [{"points": rect_map(-10, 300, left_edge, -5.0)}, {"points": rect_map(-10, 300, 5.0, right_edge)}]
    loops = [{"points": rect_map(-10, 300, -5.0, 5.0), "classification": "external"}]
    if far:
        # A esquerda, de x = 150 em diante, a superficie segue alem do alcance do raio.
        loops.append({"points": rect_map(150, 300, -50.0, -7.0), "classification": "external"})
    return {"asphaltSurface": {"loops": loops}, "kerbGeometry": {"polygons": kerbs},
            "markingGeometry": {"polygons": [], "features": []}}


class SurfaceEdges(unittest.TestCase):
    def test_a_borda_e_a_da_superficie_com_a_zebra_nos_dois_lados(self):
        track = straight_track()
        left, right = surface_edges(fake_cache(), track.points, track.normal)
        self.assertTrue(np.allclose(left, 7.0, atol=0.051))
        self.assertTrue(np.allclose(right, 6.0, atol=0.051))

    def test_o_corredor_novo_so_muda_as_larguras(self):
        track = straight_track()
        new = with_surface_corridor(track, fake_cache())
        self.assertEqual(new.geometry_id, track.geometry_id)
        for name in ("s", "x", "z", "elevation", "tangent", "normal", "curvature"):
            self.assertTrue(np.array_equal(getattr(new, name), getattr(track, name)), name)
        self.assertNotEqual(new.corridor_id, track.corridor_id)
        points = np.array([[20.0, 1.5], [90.0, -3.0]])
        for a, b in zip(track.project(points), new.project(points)):
            self.assertTrue(np.array_equal(a, b))

    def test_onde_a_borda_falta_fica_a_de_hoje(self):
        track = straight_track()
        new = with_surface_corridor(track, fake_cache(far=True))
        far = track.s >= 160
        self.assertTrue(np.all(new.width_left[far] == track.width_left[far]))
        self.assertTrue(np.allclose(new.width_left[track.s < 140], 7.0, atol=0.051))

    def test_o_corredor_util_continua_com_o_mesmo_recuo(self):
        new = with_surface_corridor(straight_track(), fake_cache())
        low, high = new.corridor()
        margin = config.CAR_HALF_WIDTH_M - config.KERB_ALLOWANCE_M
        self.assertTrue(np.allclose(high, new.width_left - margin))
        self.assertTrue(np.allclose(low, -(new.width_right - margin)))


class CorridorId(unittest.TestCase):
    def test_mudar_a_meia_bitola_muda_o_corridor_id_e_nao_o_geometry_id(self):
        track = straight_track()
        before = track.corridor_id
        original = config.CAR_HALF_WIDTH_M
        try:
            config.CAR_HALF_WIDTH_M = original + 0.1
            self.assertNotEqual(track.corridor_id, before)
            self.assertEqual(track.geometry_id, "geo-teste")
        finally:
            config.CAR_HALF_WIDTH_M = original
        self.assertEqual(track.corridor_id, before)

    def test_entram_a_folga_as_larguras_e_a_geometria(self):
        left, right = np.full(5, 5.0), np.full(5, 4.0)
        base = corridor_fingerprint(left, right, "a", 1.0, 0.5)
        self.assertEqual(base, corridor_fingerprint(left.copy(), right.copy(), "a", 1.0, 0.5))
        self.assertNotEqual(base, corridor_fingerprint(left, right, "a", 1.0, 0.6))
        self.assertNotEqual(base, corridor_fingerprint(left + 0.01, right, "a", 1.0, 0.5))
        self.assertNotEqual(base, corridor_fingerprint(left, right, "b", 1.0, 0.5))

    def test_ruido_abaixo_do_milimetro_nao_muda_o_id(self):
        left, right = np.full(5, 5.0), np.full(5, 4.0)
        self.assertEqual(corridor_fingerprint(left, right, "a", 1.0, 0.5),
                         corridor_fingerprint(left + 1e-5, right, "a", 1.0, 0.5))


def lap_table() -> pd.DataFrame:
    rows = []
    laps = {"2026-10-04": (4, 3), "2026-10-05": (6, 0), "2026-10-09": (2, 0), "2026-10-10": (5, 0),
            "2026-10-22": (0, 1), "2026-11-01": (6, 0)}
    for session, (human, ai) in laps.items():
        for k in range(human + ai):
            rows.append({"lap_id": f"{session}#{k:04d}", "sessao": session, "gravacao": session,
                         "origem": "humano" if k < human else "ia", "origem_fonte": "indicador",
                         "fora_do_store": False, "lap_time_s": 90.0 + k})
    return pd.DataFrame(rows)


class Folds(unittest.TestCase):
    def test_nenhuma_rodada_vaza_e_toda_sessao_sai_uma_vez(self):
        table = lap_table()
        seen = []
        for session in R.session_order(table):
            fold = R.build_fold(table, session)
            R.assert_no_leak(fold, table)
            seen.extend(fold.test)
            sessions = table.set_index("lap_id")["sessao"]
            self.assertTrue(set(sessions.loc[list(fold.test)]) == {session})
            self.assertNotIn(session, set(sessions.loc[list(fold.train)]))
            self.assertNotIn(session, set(sessions.loc[list(fold.validation)]))
            self.assertEqual(len(fold.test) + len(fold.validation) + len(fold.train), len(table))
        self.assertEqual(sorted(seen), sorted(table["lap_id"]))

    def test_a_validacao_e_a_sessao_seguinte_sem_ia_e_fecha_o_ciclo(self):
        table = lap_table()
        self.assertEqual(R.build_fold(table, "2026-10-04").validation_sessions, ("2026-10-05",))
        # 22/10 tem IA: de 10/10 pula para 01/11. De 01/11, fecha o ciclo e pula 04/10, que tem IA.
        self.assertEqual(R.build_fold(table, "2026-10-10").validation_sessions, ("2026-11-01",))
        self.assertEqual(R.build_fold(table, "2026-11-01").validation_sessions, ("2026-10-05",))

    def test_a_validacao_soma_ao_menos_a_fracao_pedida(self):
        table = lap_table()
        fold = R.build_fold(table, "2026-10-05", min_fraction=0.30)
        self.assertEqual(fold.validation_sessions, ("2026-10-09", "2026-10-10"))
        self.assertGreaterEqual(len(fold.validation), 0.30 * (len(table) - len(fold.test)))

    def test_o_vazamento_e_detectado(self):
        table = lap_table()
        fold = R.build_fold(table, "2026-10-05")
        broken = dataclasses.replace(fold, train=fold.train + (fold.test[0],))
        with self.assertRaises(ValueError):
            R.assert_no_leak(broken, table)

    def test_so_entram_rotulos_que_nao_sao_do_detector(self):
        self.assertNotIn("detector", R.LABELLED_SOURCES)


class F1Line(unittest.TestCase):
    def line_file(self, folder: Path, size: int) -> Path:
        path = folder / "f1.csv"
        pd.DataFrame({
            "s": np.arange(size) * 1.0, "microsetor": 0, "lateral": np.linspace(-2, 2, size),
            "speed_kmh": 300.0, "brake": 1.0, "throttle": 1.0, "n_voltas": 37,
            "pouco_confiavel": [i < 40 for i in range(size)],
        }).to_csv(path, index=False)
        return path

    def test_so_a_posicao_e_lida_mesmo_se_o_arquivo_trouxer_mais(self):
        with tempfile.TemporaryDirectory() as folder:
            line = R.read_f1_line(self.line_file(Path(folder), 201))
        self.assertEqual(set(line.columns), {"lateral", "pouco_confiavel"})
        self.assertEqual(set(R.F1_READ_COLUMNS), {"lateral", "pouco_confiavel"})

    def test_a_faixa_pouco_confiavel_fica_fora(self):
        with tempfile.TemporaryDirectory() as folder:
            line = R.read_f1_line(self.line_file(Path(folder), 201))
        self.assertTrue(line["lateral"].iloc[:40].isna().all())
        self.assertTrue(line["lateral"].iloc[40:].notna().all())

    def sequences(self, repeat: int = 3) -> SequenceSet:
        track = straight_track()
        with tempfile.TemporaryDirectory() as folder:
            line = R.read_f1_line(self.line_file(Path(folder), track.size))
        context = {"fuel": 20.0, "tyre_wear": 100.0, "grip_index": 0.8}
        return R.f1_sequences(track, None, context, repeat, line=line,
                              task=dataclasses.replace(REFERENCE_TASK, window=32, stride=8))

    def test_velocidade_e_pedal_ficam_ausentes_nos_alvos(self):
        data = self.sequences()
        targets = dict(zip(data.target_columns, np.moveaxis(data.targets, -1, 0)))
        for channel in ("speed_kmh", "brake", "throttle"):
            self.assertTrue(np.isnan(targets[channel]).all(), channel)
        self.assertTrue(np.isfinite(targets["lateral"]).any())

    def test_nenhuma_entrada_de_pilotagem_e_a_perda_e_zero(self):
        data = self.sequences()
        for forbidden in ("speed_kmh", "brake", "throttle", "lateral"):
            self.assertNotIn(forbidden, data.input_columns)
        columns = list(data.input_columns)
        self.assertTrue((data.inputs[..., columns.index("lap_loss_s")] == 0).all())
        self.assertTrue((data.inputs[..., columns.index("sector_loss_s")] == 0).all())

    def test_o_peso_e_a_repeticao_das_janelas(self):
        once, thrice = self.sequences(1), self.sequences(3)
        self.assertEqual(len(thrice), 3 * len(once))

    def test_o_peso_e_a_mediana_de_voltas_por_sessao_de_treino(self):
        table = lap_table()
        train = table[table["sessao"].isin(["2026-10-04", "2026-10-05", "2026-10-09"])]["lap_id"].tolist()
        self.assertEqual(R.f1_repeat(table, train), 6)   # 7, 6 e 2 voltas

    @unittest.skipUnless(TORCH, "sem PyTorch")
    def test_a_perda_ignora_alvos_ausentes(self):
        import torch

        from ml.models.training import _masked_loss

        criterion = torch.nn.SmoothL1Loss(beta=0.5)
        prediction = torch.tensor([[1.0, 5.0], [2.0, 5.0]])
        target = torch.tensor([[1.5, float("nan")], [1.0, float("nan")]])
        loss = _masked_loss(criterion, prediction, target)
        self.assertTrue(torch.isfinite(loss))
        self.assertAlmostEqual(float(loss), float(criterion(torch.tensor([1.0, 2.0]), torch.tensor([1.5, 1.0]))))
        full = torch.tensor([[1.5, 4.0], [1.0, 6.0]])
        self.assertEqual(float(_masked_loss(criterion, prediction, full)), float(criterion(prediction, full)))

    @unittest.skipUnless(TORCH, "sem PyTorch")
    def test_a_f1_nao_toca_a_normalizacao(self):
        from ml.models.training import TrainConfig, train_model

        task = TaskSpec("t", ("a",), ("lateral", "speed_kmh"), window=8, stride=8)
        rng = np.random.default_rng(1)
        real = SequenceSet(rng.normal(5.0, 2.0, (16, 8, 1)).astype(np.float32),
                           rng.normal(0.0, 3.0, (16, 8, 2)).astype(np.float32),
                           np.array(["v"] * 16, dtype=object), np.zeros(16, dtype=int), ("a",), ("lateral", "speed_kmh"))
        target = np.full((4, 8, 2), np.nan, dtype=np.float32)
        target[..., 0] = 100.0
        extra = SequenceSet(np.full((4, 8, 1), 500.0, dtype=np.float32), target,
                            np.array(["f1"] * 4, dtype=object), np.zeros(4, dtype=int), ("a",), ("lateral", "speed_kmh"))
        settings = TrainConfig(epochs=2, patience=5, batch_size=8)
        plain = train_model(task, real, None, config=settings, verbose=False)
        mixed = train_model(task, real, None, config=settings, verbose=False, extra_train=extra)
        self.assertTrue(np.array_equal(plain.scaler.mean, mixed.scaler.mean))
        self.assertTrue(np.array_equal(plain.transform.mean, mixed.transform.mean))
        self.assertTrue(all(np.isfinite(h["train_loss"]) for h in mixed.history))


class Ruler(unittest.TestCase):
    def errors(self, model: float = 0.5, naive: float = 1.0, sessions: int = 6, bad: int = 0) -> pd.DataFrame:
        rows = []
        for k in range(sessions):
            for lap in range(2 + k):
                rows.append({"sessao": f"s{k}", "erro_modelo_m": naive * 1.5 if k < bad else model + 0.01 * lap,
                             "erro_ingenuo_m": naive})
        return pd.DataFrame(rows)

    def test_aprova_quando_todos_os_criterios_valem(self):
        result = R.criteria(self.errors())
        self.assertTrue(result["aprovado"])
        self.assertGreater(result["ic95_inf"], 0)
        self.assertEqual(result["sessoes_testaveis"], 6)

    def test_cada_criterio_reprova_sozinho(self):
        self.assertFalse(R.criteria(self.errors(model=0.9))["criterios"]["skill_minimo"])
        self.assertFalse(R.criteria(self.errors(sessions=4))["criterios"]["sessoes_testaveis"])
        two_bad = R.criteria(self.errors(sessions=6, bad=2))
        self.assertAlmostEqual(two_bad["fracao_de_sessoes_com_skill_positivo"], 4 / 6)
        self.assertFalse(two_bad["criterios"]["sessoes_com_skill_positivo"])

    def test_a_volta_pesa_igual_no_skill_agregado(self):
        errors = pd.DataFrame({"sessao": ["a", "a", "a", "b"], "erro_modelo_m": [0.0, 0.0, 0.0, 2.0],
                               "erro_ingenuo_m": [1.0, 1.0, 1.0, 1.0]})
        self.assertAlmostEqual(R.criteria(errors)["skill"], 1.0 - (2.0 / 4.0) / 1.0)

    def test_o_bootstrap_e_reprodutivel_e_soma_as_sessoes(self):
        weights = R.bootstrap_draws(5, draws=100, seed=7)
        self.assertTrue((weights.sum(axis=1) == 5).all())
        self.assertTrue(np.array_equal(weights, R.bootstrap_draws(5, draws=100, seed=7)))

    def test_a_f1_so_fica_com_ganho_e_limite_acima_de_zero(self):
        without = R.session_sums(self.errors(model=0.6))
        better = R.session_sums(self.errors(model=0.4))
        difference = R.paired_difference(better, without)
        self.assertGreater(difference["diferenca"], 0)
        self.assertTrue(R.f1_stays(difference))
        self.assertFalse(R.f1_stays(R.paired_difference(without, better)))
        self.assertFalse(R.f1_stays({"diferenca": 0.05, "ic95_inf": -0.01}))

    def test_o_pareamento_exige_as_mesmas_sessoes(self):
        with self.assertRaises(ValueError):
            R.paired_difference(R.session_sums(self.errors(sessions=5)), R.session_sums(self.errors(sessions=6)))


@unittest.skipUnless(TORCH, "sem PyTorch")
class ModelGuard(unittest.TestCase):
    def test_o_modelo_recusa_outro_corredor(self):
        from ml.models.reference_line import generate
        from ml.models.training import TrainedModel

        track = straight_track()
        trained = TrainedModel(model=None, config=None, scaler=None, transform=None, task_name="reference",
                               metadata={"corridor_id": "outro"})
        with self.assertRaises(ValueError):
            generate(trained, track)


if __name__ == "__main__":
    unittest.main()
