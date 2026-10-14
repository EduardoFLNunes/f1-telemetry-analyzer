"""Pedido 28, Parte B: o registro do que os modelos precisam, contra o store v2, a M1 e o gravador.

Nenhum dos dois lados pode sair do lugar sem um destes testes quebrar:

* toda coluna que o store v2 materializa esta no registro, e todo item do
  registro que diz produzir uma coluna aponta para uma coluna que existe;
* os canais obrigatorios da regra da M1 (docs/modelo_fisico_m0.md, secao 6)
  sao os do registro;
* todo item aponta para um campo que o gravador grava: a amostra passa pelo
  caminho real (adaptador -> leitor -> runtime -> gravador) ate o arquivo, e o
  registro le de volta o que foi escrito;
* a coluna do achatamento do ML que o item diz ter le o mesmo valor.
"""

from __future__ import annotations

import ctypes
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from core.assetto_adapter import AssettoAdapter, SPageFilePhysics  # noqa: E402
from core.coleta import requisitos  # noqa: E402
from core.coleta.requisitos import REQUISITOS, ler_caminho, valores  # noqa: E402
from core.live.runtime_state import RuntimeState  # noqa: E402
from core.projection.spatial_projection import ProjectionEngine  # noqa: E402
from core.recording.recording_models import RecordingConfig  # noqa: E402
from core.recording.session_recorder import SessionRecorder  # noqa: E402
from core.telemetry.telemetry_models import TelemetrySample, TrackPoint  # noqa: E402
from ml.data.lap_store import STORE_COLUMNS  # noqa: E402
from ml.data.samples import SAMPLE_COLUMNS, flatten  # noqa: E402
from tests.test_canais_fisicos import snapshot_bytes  # noqa: E402

INVENTORY = REPO / "docs" / "handoff" / "2026-10-04_canais-fisicos_inventario.json"
# Item do registro -> campo do inventario do pedido 18.
INVENTORY_FIELDS = {
    "throttle": "throttle",
    "brake": "brake",
    "steering": "steerAngle",
    "gear": "gear",
    "tyre_core_temp": "tyreCoreTemperature",
    "wheel_load": "wheelLoad",
    "wheel_slip": "wheelSlip",
    "tyre_pressure": "tyrePressure",
    "suspension_travel": "suspensionTravel",
    "acc_g": "accG",
}


def physical_columns():
    """`ml.data.store_v2.PHYSICAL_COLUMNS`, sem importar o store v2 (ele puxa o torch)."""
    source = (BACKEND / "ml" / "data" / "store_v2.py").read_text(encoding="utf-8")
    assert 'PHYSICAL_COLUMNS = tuple(' in source
    from ml.data import store_v2

    return tuple(store_v2.PHYSICAL_COLUMNS)


def recorded_line(tmp: Path):
    """Uma amostra pelo caminho real ate o `player.jsonl`, e o `metadata.json` da sessao."""
    adapter = AssettoAdapter()
    adapter.physics = SPageFilePhysics.from_buffer_copy(snapshot_bytes()[: ctypes.sizeof(SPageFilePhysics)])
    adapter.physics.tyreTempM[:] = [80.0, 81.0, 82.0, 83.0]
    adapter.physics.tyreTempO[:] = [70.0, 71.0, 72.0, 73.0]
    frame = adapter._normalize()
    sample = TelemetrySample.from_dict({
        **frame, "timestamp": 1_791_647_915_113.0, "worldPositionX": 100.0, "worldPositionY": 2.0,
        "worldPositionZ": -40.0, "lap": 3, "lapTime": 41.25, "sessionTime": 300.0,
    })
    state = RuntimeState()
    points = [TrackPoint(x=200.0 * math.cos(a), y=0.0, z=200.0 * math.sin(a), distance=200.0 * a, spline_t=a / (2.0 * math.pi))
              for a in [i * 2.0 * math.pi / 400 for i in range(400)]]
    state.projection_engine = ProjectionEngine(points, closed_loop=True)
    processed = state.update_car(sample)

    recorder = SessionRecorder(RecordingConfig(output_root=tmp, player_record_hz=60.0, source_sample_hz=60.0))
    recorder.start(track="vhe_interlagos", metadata={"source": "assetto_corsa", "carModel": "rss_formula_rss_3_v6_2026"})
    recorder.enqueue_player(processed, track="vhe_interlagos")
    status = recorder.stop()
    directory = Path(status.directory)
    line = json.loads((directory / "player.jsonl").read_text(encoding="utf-8").splitlines()[0])
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    return line, metadata


class RegistryAgainstStoreTest(unittest.TestCase):
    def test_every_store_v2_column_is_in_the_registry(self):
        store = set(STORE_COLUMNS) | set(physical_columns())
        registry = set(requisitos.colunas_store())
        self.assertEqual(sorted(store - registry), [], "colunas do store v2 sem item no registro")
        self.assertEqual(sorted(registry - store), [], "itens do registro apontando para colunas que o store nao tem")

    def test_the_m1_rule_is_the_registry_rule(self):
        # docs/modelo_fisico_m0.md, secao 6: guinada e velocidades no referencial do carro.
        self.assertEqual(set(requisitos.COLUNAS_M1), {"yaw_rate", "velocity_long", "velocity_lat"})
        self.assertTrue(set(requisitos.COLUNAS_M1) <= set(physical_columns()))
        self.assertEqual(requisitos.PREENCHIMENTO_M1, 0.95)
        self.assertEqual(set(requisitos.NOME_M1), set(requisitos.COLUNAS_M1))

    def test_the_sample_columns_exist_in_the_ml_reader(self):
        for item in REQUISITOS:
            for coluna in item.colunas_amostra:
                self.assertIn(coluna, SAMPLE_COLUMNS, f"{item.id}: {coluna}")

    def test_every_group_of_the_request_is_there(self):
        grupos = {item.grupo for item in REQUISITOS}
        self.assertTrue({"base", "origem", "limites", "m1"} <= grupos)
        ids = {item.id for item in REQUISITOS}
        for wanted in ("lap_time", "lap_number", "distance", "position", "speed", "throttle", "brake",
                       "steering", "gear", "rpm", "ai_controlled", "car_model", "track", "tyres_out",
                       "off_track", "yaw_rate", "velocity_long", "velocity_lat", "brake_temp", "brake_bias",
                       "tyre_core_temp", "tyre_temp_inner", "tyre_temp_middle", "tyre_temp_outer",
                       "wheel_load", "wheel_slip", "tyre_pressure", "suspension_travel", "acc_g", "clutch"):
            self.assertIn(wanted, ids)

    def test_ids_are_unique_and_usages_known(self):
        self.assertEqual(len({r.id for r in REQUISITOS}), len(REQUISITOS))
        for item in REQUISITOS:
            self.assertTrue(item.usos)
            self.assertTrue(set(item.usos) <= set(requisitos.USOS), item.id)
            self.assertIn(item.fonte, ("amostra", "envelope", "metadata"))
            self.assertTrue(0.0 < item.preenchimento_minimo <= 1.0)


class RegistryAgainstRecorderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.line, self.metadata = recorded_line(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_item_reads_a_value_from_what_was_written(self):
        sample = self.line["sample"]
        for item in REQUISITOS:
            for componente, valor in zip(item.componentes, valores(item, sample, self.line, self.metadata)):
                self.assertIsNotNone(valor, f"{item.id} ({componente.rotulo}): {componente.caminhos[0]} nao foi gravado")

    def test_the_first_path_is_the_one_the_current_recorder_writes(self):
        sample = self.line["sample"]
        for item in REQUISITOS:
            base = {"amostra": sample, "envelope": self.line, "metadata": self.metadata}[item.fonte]
            for componente in item.componentes:
                self.assertIsNotNone(ler_caminho(base, componente.caminhos[0]), f"{item.id}: {componente.caminhos[0]}")

    def test_the_ml_reader_sees_the_same_value(self):
        flat = flatten(self.line)
        sample = self.line["sample"]
        for item in REQUISITOS:
            for componente, valor in zip(item.componentes, valores(item, sample, self.line, self.metadata)):
                if not componente.coluna_amostra:
                    continue
                lido = flat.get(componente.coluna_amostra)
                self.assertIsNotNone(lido, f"{item.id}: {componente.coluna_amostra}")
                if isinstance(valor, bool):
                    self.assertEqual(bool(lido), valor, item.id)
                else:
                    self.assertAlmostEqual(float(lido), float(valor), places=4, msg=item.id)

    def test_the_new_channels_of_request_18_were_written(self):
        sample = self.line["sample"]
        self.assertAlmostEqual(valores(requisitos.POR_ID["yaw_rate"], sample)[0], 0.1462, places=3)
        self.assertAlmostEqual(valores(requisitos.POR_ID["velocity_long"], sample)[0], 53.4677, places=3)
        self.assertAlmostEqual(valores(requisitos.POR_ID["brake_temp"], sample)[0], 18.1902, places=3)
        self.assertEqual(valores(requisitos.POR_ID["car_model"], sample, metadata=self.metadata),
                         ["rss_formula_rss_3_v6_2026"])


class RangesTest(unittest.TestCase):
    def test_measured_ranges_follow_the_margin_rule(self):
        for item in REQUISITOS:
            if item.p1_p99 is None:
                continue
            p1, p99 = item.p1_p99
            self.assertLessEqual(item.faixa[0], p1, item.id)
            self.assertGreaterEqual(item.faixa[1], p99, item.id)
            margem = requisitos.MARGEM_DA_FAIXA * (p99 - p1)
            self.assertAlmostEqual(max(item.faixa[0], p1 - margem), item.faixa[0], places=3)

    @unittest.skipUnless(INVENTORY.exists(), "inventario do pedido 18 fora do repositorio")
    def test_the_copied_percentiles_are_the_inventory_ones(self):
        campos = json.loads(INVENTORY.read_text(encoding="utf-8"))["sessoes"]["2026-10-04"]["repositorio"]["campos"]
        for item_id, campo in INVENTORY_FIELDS.items():
            faixa = campos[campo]["faixa"]
            self.assertEqual(requisitos.POR_ID[item_id].p1_p99, (faixa["p1"], faixa["p99"]), item_id)
        medidos = {item.id for item in REQUISITOS if item.p1_p99 is not None}
        self.assertEqual(medidos, set(INVENTORY_FIELDS))

    def test_every_numeric_item_has_a_range_and_its_source(self):
        for item in REQUISITOS:
            if item.tipo == "numero":
                self.assertIsNotNone(item.faixa, item.id)
                self.assertLess(item.faixa[0], item.faixa[1], item.id)
            self.assertTrue(item.fonte_faixa, item.id)


if __name__ == "__main__":
    unittest.main()
