"""Pedido 20: o resumo do inventario nao chama o `duration_s` de tempo de volta.

O `duration_s` vai do primeiro ao ultimo ponto gravado da volta e nao e o tempo
de volta. O resumo o publicava como `lap_time_s` e `best_lap`, e dali ele foi
parar como tempo de volta em documentos (pedido 19).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from ml.data.inventory import summarise  # noqa: E402


def inventory():
    durations = [89.379, 93.004, 84.816, 300.0, 91.719]
    return pd.DataFrame({
        "lap_id": [f"s#{i:04d}" for i in range(5)],
        "session_id": ["s", "s", "t", "t", "t"],
        "driver_id": "player_1",
        "valid": [True, True, True, False, True],
        "reasons": ["", "", "", "volta longa demais", ""],
        "duration_s": durations,
        "sample_hz": [58.0, 57.5, 59.0, 40.0, 58.2],
        "speed_mean_kmh": [160.0] * 5,
        "coverage": [1.0] * 5,
    })


def keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from keys(value)


class SummaryTest(unittest.TestCase):
    def test_no_field_is_called_lap_time(self):
        summary = summarise(inventory())
        self.assertNotIn("lap_time_s", set(keys(summary)))
        self.assertNotIn("best_lap", summary)

    def test_the_duration_keeps_the_values_it_had(self):
        frame = inventory()
        valid = frame.loc[frame["valid"], "duration_s"].to_numpy(dtype=float)
        summary = summarise(frame)
        # Os mesmos numeros que saiam como `lap_time_s` antes do pedido 20.
        self.assertEqual(summary["duration_s"], {
            "min": float(valid.min()), "p10": float(np.percentile(valid, 10)), "median": float(np.median(valid)),
            "p90": float(np.percentile(valid, 90)), "max": float(valid.max()),
        })
        self.assertEqual(summary["shortest_duration_lap"],
                         {"lap_id": "s#0002", "duration_s": 84.816, "sample_hz": 59.0})


if __name__ == "__main__":
    unittest.main()
