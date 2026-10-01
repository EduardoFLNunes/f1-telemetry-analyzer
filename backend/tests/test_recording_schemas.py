"""Regressao sobre amostras reais das tres geracoes de formato do gravador.

As fixtures em `fixtures/recording_schemas/` sao linhas copiadas sem alteracao
de `data/recordings/<sessao>/player.jsonl` -- uma acelerando, uma freando e uma
virando, de cada sessao:

* `may_top_level`      2026-05-26_19-06-59  pedais so no topo, sem `carPhysics`
* `june_top_level`     2026-06-14_12-23-46  idem (a sessao que a doc dava como "sem pedais")
* `june_both`          2026-06-20_13-13-02  topo e `carPhysics.controls`
* `august_nested_only` 2026-08-09_19-20-59  so `carPhysics.controls`, sem `lateralOffset`
* `august_both`        2026-08-16_03-30-14  topo e `carPhysics.controls`

Antes desta correcao, o leitor do `ml` devolvia `None` nos dois arquivos de
topo e o do runtime devolvia acelerador zero no `august_nested_only`.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.assisted_analysis.utils import normalize_lap_dataframe
from core.projection.lateral_offset import (
    RECORDED_OFFSET_POSITIVE_SIDE,
    signed_lateral_offset,
    tangent_and_normal,
    to_left_positive,
)
from core.telemetry.channels import driver_inputs, input_schema
from ml.data.samples import flatten

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "recording_schemas"

# Esquema esperado de cada arquivo -- medido nas sessoes inteiras, nao so nas
# tres linhas copiadas.
EXPECTED_SCHEMA = {
    "may_top_level": "top_level",
    "june_top_level": "top_level",
    "june_both": "both",
    "august_nested_only": "nested",
    "august_both": "both",
}
ROLES = ("throttle", "brake", "steer")


def load(name):
    lines = (FIXTURES / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def runtime_rows(envelopes):
    """O que `LapDataLoader._flatten_recording_sample` monta antes de normalizar."""
    rows = []
    for envelope in envelopes:
        sample = dict(envelope["sample"])
        sample.setdefault("timestamp", envelope.get("timestamp"))
        sample.setdefault("sessionTime", envelope.get("sessionTime"))
        rows.append(sample)
    return pd.DataFrame(rows)


class SchemaDetectionTest(unittest.TestCase):
    def test_every_fixture_is_the_schema_its_session_uses(self):
        for name, expected in EXPECTED_SCHEMA.items():
            for envelope in load(name):
                self.assertEqual(input_schema(envelope), expected, name)


class DriverInputsTest(unittest.TestCase):
    def test_pedals_are_found_in_every_schema(self):
        for name in EXPECTED_SCHEMA:
            throttle_row, brake_row, steer_row = load(name)
            self.assertGreater(driver_inputs(throttle_row)["throttle"], 0.9, name)
            self.assertGreater(driver_inputs(brake_row)["brake"], 0.5, name)
            self.assertGreater(abs(driver_inputs(steer_row)["steering"]), 0.1, name)
            for row in (throttle_row, brake_row, steer_row):
                values = driver_inputs(row)
                for channel in ("throttle", "brake", "steering", "gear", "rpm"):
                    self.assertIsNotNone(values[channel], f"{name}: {channel}")

    def test_both_places_agree_where_both_exist(self):
        for name in ("june_both", "august_both"):
            for envelope in load(name):
                sample = envelope["sample"]
                controls = sample["carPhysics"]["controls"]
                self.assertEqual(sample["throttle"], controls["throttle"])
                self.assertEqual(sample["steering"], controls["steerAngle"])
                self.assertEqual(driver_inputs(envelope)["throttle"], controls["throttle"])

    def test_missing_channel_is_none_and_not_zero(self):
        self.assertIsNone(driver_inputs({"sample": {"lap": 1}})["throttle"])
        self.assertEqual(driver_inputs({"throttle": 0.0})["throttle"], 0.0)


class BothReadersAgreeTest(unittest.TestCase):
    def test_ml_flatten_reads_what_the_shared_rule_reads(self):
        for name in EXPECTED_SCHEMA:
            for envelope in load(name):
                row = flatten(envelope)
                shared = driver_inputs(envelope)
                for channel in ("throttle", "brake", "clutch", "steering", "gear", "rpm"):
                    self.assertEqual(row[channel], shared[channel], f"{name}: {channel}")

    def test_runtime_normalizer_reads_nested_only_sessions(self):
        for name in EXPECTED_SCHEMA:
            envelopes = load(name)
            frame = normalize_lap_dataframe(runtime_rows(envelopes))
            self.assertGreater(frame.loc[0, "throttle"], 0.9, name)
            self.assertGreater(frame.loc[1, "brake"], 0.5, name)
            self.assertGreater(abs(frame.loc[2, "steering"]), 0.1, name)
            expected = [driver_inputs(e)["throttle"] for e in envelopes]
            np.testing.assert_allclose(frame["throttle"].to_numpy(), expected, err_msg=name)


class LateralSignTest(unittest.TestCase):
    def test_recorded_offset_enters_ml_with_the_sign_flipped(self):
        for name in EXPECTED_SCHEMA:
            for envelope in load(name):
                recorded = envelope["sample"].get("lateralOffset")
                row = flatten(envelope)
                if recorded is None:
                    self.assertIsNone(row["lateral_recorded"], name)
                else:
                    self.assertEqual(row["lateral_recorded"], -recorded, name)

    def test_the_two_projections_put_the_same_point_on_opposite_signs(self):
        # O mesmo ponto, o mesmo segmento: o runtime e o `ml` discordam no
        # sinal por construcao, e `to_left_positive` e a ponte.
        from tests.test_ml_pipeline import circular_track

        track = circular_track()
        index = 40
        start, end = track.points[index], track.points[index + 1]
        middle = 0.5 * (start + end)
        point = middle + 2.5 * track.normal[index]   # 2,5 m para o lado +normal do ml

        _, ml_lateral = track.project(point[None, :])
        _, runtime_normal = tangent_and_normal(end - start)
        runtime_offset = signed_lateral_offset(point, middle, runtime_normal)

        self.assertAlmostEqual(float(ml_lateral[0]), 2.5, places=2)
        self.assertAlmostEqual(runtime_offset, -2.5, places=2)
        self.assertAlmostEqual(to_left_positive(runtime_offset), float(ml_lateral[0]), places=2)
        self.assertEqual(RECORDED_OFFSET_POSITIVE_SIDE, "right")


if __name__ == "__main__":
    unittest.main()
