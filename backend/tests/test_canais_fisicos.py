"""Pedido 18 (ADR 0017, M0): a pagina de fisica alinhada com o AC1 e os canais novos gravados.

O retrato salvo da memoria compartilhada (data/debug/ac_shared_memory_full_inventory.json,
lido com a estrutura antiga) e o que mostra o desalinhamento: os mesmos bytes,
lidos com a estrutura corrigida, dao freios a 18,19 °C, a embreagem em 1,0, a
distribuicao de frenagem em 0,55 e uma velocidade longitudinal igual a speedKmh / 3,6.
"""

from __future__ import annotations

import ctypes
import sys
import unittest
from ctypes import c_float, c_int
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.assetto_adapter import AssettoAdapter, SPageFilePhysics  # noqa: E402
from core.car_physics import build_player_car_physics  # noqa: E402
from core.telemetry.telemetry_models import TelemetrySample  # noqa: E402

# A estrutura como estava antes do pedido 18, do kersCurrentKJ em diante.
_PREFIX = [field for field in SPageFilePhysics._fields_ if field[0] != "kersCurrentKJ"]
_PREFIX = _PREFIX[: [name for name, _ in _PREFIX].index("drsAvailable")]
OLD_SUFFIX = [
    ("kersCurrentVK", c_float),
    ("visualTyreDamage", c_float * 4),
    ("elecSystemsOverlap", c_int),
    ("ersFuelDiff", c_float),
    ("diffPa", c_int),
    ("tyreTempI", c_float * 4),
    ("tyreTempM", c_float * 4),
    ("tyreTempO", c_float * 4),
    ("isAIControlled", c_int),
    ("tyreContactPoint", c_float * 4 * 3),
    ("tyreContactNormal", c_float * 4 * 3),
    ("tyreContactHeading", c_float * 4 * 3),
    ("brakeTemp", c_float * 4),
    ("clutch", c_float),
]


class OldPhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = _PREFIX + OLD_SUFFIX


def snapshot_bytes() -> bytes:
    """Os valores do retrato salvo, escritos na estrutura antiga."""
    old = OldPhysics()
    old.speedKmh = 192.5050811767578
    old.visualTyreDamage[:] = [0.0, 0.0, 18.190166473388672, 18.190166473388672]
    old.elecSystemsOverlap = 1100055926
    old.ersFuelDiff = 18.190166473388672
    old.diffPa = 1065353216
    old.tyreTempI[:] = [73.59599304199219, 98.47428894042969, 78.94895935058594, 92.21526336669922]
    old.isAIControlled = 1
    old.brakeTemp[:] = [0.550000011920929, -0.6903559565544128, -0.39052021503448486, 53.46775436401367]
    old.localAngularVel[:] = [-0.03680453449487686, 0.14621564745903015, -0.0457758791744709]
    return bytes(old) + bytes(max(0, ctypes.sizeof(SPageFilePhysics) - ctypes.sizeof(OldPhysics)))


class PhysicsPageTest(unittest.TestCase):
    def setUp(self):
        self.page = SPageFilePhysics.from_buffer_copy(snapshot_bytes()[: ctypes.sizeof(SPageFilePhysics)])

    def test_the_snapshot_reads_as_assetto_corsa_1(self):
        self.assertTrue(all(abs(v - 18.1902) < 1e-3 for v in self.page.brakeTemp))
        self.assertAlmostEqual(self.page.clutch, 1.0)
        self.assertAlmostEqual(self.page.brakeBias, 0.55, places=5)
        # A norma da velocidade no referencial do carro e a velocidade do carro.
        norm = sum(v * v for v in self.page.localVelocity) ** 0.5
        self.assertAlmostEqual(norm * 3.6, self.page.speedKmh, places=2)
        self.assertEqual(self.page.isAIControlled, 1)
        self.assertAlmostEqual(self.page.tyreTempI[1], 98.4743, places=3)

    def test_the_fields_before_the_fix_did_not_move(self):
        for name in ("speedKmh", "tyreCoreTemp", "wheelLoad", "heading", "rideHeight", "localAngularVel",
                     "tyreTempI", "tyreTempM", "tyreTempO", "isAIControlled"):
            self.assertEqual(getattr(SPageFilePhysics, name).offset, getattr(OldPhysics, name).offset, name)


class RecordedChannelsTest(unittest.TestCase):
    def frame(self):
        adapter = AssettoAdapter()
        adapter.physics = SPageFilePhysics.from_buffer_copy(snapshot_bytes()[: ctypes.sizeof(SPageFilePhysics)])
        adapter.physics.tyreTempM[:] = [80.0, 81.0, 82.0, 83.0]
        adapter.physics.tyreTempO[:] = [70.0, 71.0, 72.0, 73.0]
        return adapter._normalize()

    def test_the_adapter_exports_the_new_channels(self):
        frame = self.frame()
        self.assertEqual(len(frame["tyre_temp_inner"]), 4)
        self.assertAlmostEqual(frame["brake_temp"][0], 18.1902, places=3)
        self.assertAlmostEqual(frame["brake_bias"], 0.55, places=5)
        self.assertAlmostEqual(frame["local_velocity"]["z"], 53.4677, places=3)
        self.assertAlmostEqual(frame["local_angular_velocity"]["y"], 0.1462, places=3)
        self.assertAlmostEqual(frame["clutch"], 1.0)

    def test_the_recorded_block_carries_them(self):
        frame = self.frame()
        sample = TelemetrySample.from_dict({**frame, "timestamp": 1.0, "worldPositionX": 0.0,
                                            "worldPositionY": 0.0, "worldPositionZ": 0.0})
        physics = build_player_car_physics(sample, [sample])
        self.assertEqual(physics["tyres"]["tyreTempMiddle"], [80.0, 81.0, 82.0, 83.0])
        self.assertEqual(physics["tyres"]["tyreTempOuter"], [70.0, 71.0, 72.0, 73.0])
        self.assertAlmostEqual(physics["brakes"]["brakeTemp"][3], 18.1902, places=3)
        self.assertAlmostEqual(physics["brakes"]["brakeBias"], 0.55, places=5)
        self.assertAlmostEqual(physics["motion"]["localVelocity"]["z"], 53.4677, places=3)
        self.assertAlmostEqual(physics["motion"]["localAngularVelocity"]["y"], 0.1462, places=3)

    def test_a_source_without_them_records_none(self):
        sample = TelemetrySample.from_dict({"timestamp": 1.0, "worldPositionX": 0.0, "worldPositionY": 0.0,
                                            "worldPositionZ": 0.0})
        physics = build_player_car_physics(sample, [sample])
        self.assertEqual(physics["brakes"]["brakeTemp"], [None, None, None, None])
        self.assertIsNone(physics["motion"]["localVelocity"]["z"])
        self.assertEqual(physics["tyres"]["tyreTempInner"], [None, None, None, None])


class ReaderTest(unittest.TestCase):
    def test_the_shared_memory_reader_carries_the_new_channels_to_the_recorded_block(self):
        """O caminho real: adaptador -> leitor -> amostra -> bloco gravado."""
        from core.telemetry.telemetry_reader_impl import ACSharedMemoryReader

        reader = ACSharedMemoryReader()
        frame = RecordedChannelsTest().frame()
        frame.update({"x": 120.0, "z": -40.0, "packet_id": 7})
        reader.connect = lambda: True
        reader.adapter.poll = lambda: frame
        sample = reader.read_sample()
        self.assertIsNotNone(sample)
        physics = build_player_car_physics(sample, [sample])
        self.assertAlmostEqual(physics["brakes"]["brakeBias"], 0.55, places=5)
        self.assertEqual(physics["tyres"]["tyreTempOuter"], [70.0, 71.0, 72.0, 73.0])
        self.assertAlmostEqual(physics["motion"]["localAngularVelocity"]["y"], 0.1462, places=3)
        self.assertAlmostEqual(physics["controls"]["clutch"], 1.0)


if __name__ == "__main__":
    unittest.main()
