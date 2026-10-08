"""Testes do traçado de referência da F1 na época 2023–25 (pedido 24, Parte C; ADR 0019).

Sintéticos e sem internet: o manifesto é montado à mão e as linhas são
vetores conhecidos. O caminho da classificação de 2024 está testado em
`test_f1_voltas_secas.py`, com o módulo FastF1 falso.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.external import f1_reference  # noqa: E402

GRID = 200


def record(year, session, driver, etapa="escolhida", aceita=True, a_parte=None):
    out = {"chave": f"{year}_{session}_{driver}", "ano": year, "sessao": session, "piloto": driver, "etapa": etapa,
           "criterio": {"aceita": aceita}}
    if a_parte:
        out["a_parte"] = a_parte
    return out


class EraSelectionTest(unittest.TestCase):
    def test_only_accepted_dry_laps_of_2023_to_2025_enter(self):
        records = [
            record(2019, "Qualifying", "HAM"),
            record(2021, "Qualifying", "VER"),
            record(2022, "Qualifying", "LEC"),
            record(2023, "Qualifying", "SAI"),
            record(2023, "Sprint Shootout", "PER"),
            record(2024, "Sprint Qualifying", "RUS"),
            record(2024, "Qualifying", "NOR", etapa="composto", a_parte="volta de chuva, fora da faixa seca"),
            record(2025, "Qualifying", "PIA"),
            record(2025, "Sprint Qualifying", "ANT", aceita=False),     # recusada no criterio por volta
            record(2025, "Qualifying", "GAS", etapa="nao_e_a_melhor_do_piloto", aceita=False),
        ]
        chosen = f1_reference.era_laps(records)
        self.assertEqual([r["chave"] for r in chosen],
                         ["2023_Qualifying_SAI", "2023_Sprint Shootout_PER", "2024_Sprint Qualifying_RUS",
                          "2025_Qualifying_PIA"])

    def test_the_rain_lap_never_enters_even_if_its_alignment_passed(self):
        rain = record(2024, "Qualifying", "NOR", etapa="escolhida", a_parte="volta de chuva, fora da faixa seca")
        self.assertEqual(f1_reference.era_laps([rain]), [])


class ReferenceTest(unittest.TestCase):
    def test_pointwise_median_with_equal_weight_per_lap(self):
        laterals = np.array([
            [1.0, 10.0, -2.0],
            [2.0, 20.0, -1.0],
            [3.0, 30.0, 0.0],
            [9.0, 0.0, 5.0],
        ])
        np.testing.assert_allclose(f1_reference.reference_line(laterals), [2.5, 15.0, -0.5])

    def test_a_session_with_more_laps_weighs_more_because_each_lap_weighs_the_same(self):
        # Sessao A com 3 voltas em 0, sessao B com 1 volta em 10: a mediana das 4 voltas e 0.
        laterals = np.vstack([np.zeros(GRID)] * 3 + [np.full(GRID, 10.0)])
        np.testing.assert_allclose(f1_reference.reference_line(laterals), 0.0)

    def test_amplitude_between_session_medians(self):
        laterals = np.vstack([np.zeros(GRID), np.full(GRID, 0.2), np.full(GRID, -0.1), np.full(GRID, 0.4)])
        amplitude = f1_reference.session_amplitude(laterals, ["a", "a", "b", "c"])
        np.testing.assert_allclose(amplitude, 0.4 - (-0.1))

    def test_unreliable_flags_from_pedido_23_labels(self):
        flags = f1_reference.unreliable_flags(["MS04 (217-289 m)", "MS19 (1300-1372 m)", "MS60 (4262-4334 m)"], 60)
        self.assertEqual(list(np.flatnonzero(flags)), [3, 18, 59])


class CoherenceTest(unittest.TestCase):
    def test_each_condition_rejects_alone_and_the_borders_pass(self):
        self.assertTrue(f1_reference.coherence_verdict(0.10, 0.30)["entra"])
        median_only = f1_reference.coherence_verdict(0.11, 0.20)
        self.assertFalse(median_only["entra"])
        self.assertFalse(median_only["mediana_ok"])
        self.assertTrue(median_only["p90_ok"])
        p90_only = f1_reference.coherence_verdict(0.05, 0.31)
        self.assertFalse(p90_only["entra"])
        self.assertTrue(p90_only["mediana_ok"])
        self.assertFalse(p90_only["p90_ok"])

    def _era(self, odd):
        """Tres sessoes em 0 (duas voltas cada) e uma sessao `x` com a linha `odd`."""
        laterals = np.vstack([np.zeros(GRID)] * 6 + [odd, odd])
        sessions = ["a", "a", "b", "b", "c", "c", "x", "x"]
        return f1_reference.coherence(laterals, sessions)

    def test_session_on_the_border_enters(self):
        verdict = self._era(np.full(GRID, 0.10))["x"]
        self.assertAlmostEqual(verdict["mediana_m"], 0.10)
        self.assertTrue(verdict["entra"])

    def test_session_off_in_median_is_left_out(self):
        verdict = self._era(np.full(GRID, 0.12))["x"]
        self.assertFalse(verdict["mediana_ok"])
        self.assertTrue(verdict["p90_ok"])
        self.assertFalse(verdict["entra"])

    def test_session_off_only_in_p90_is_left_out(self):
        odd = np.full(GRID, 0.05)
        odd[: int(0.2 * GRID)] = 0.6        # 20% dos pontos longe: mediana ok, p90 nao
        verdict = self._era(odd)["x"]
        self.assertTrue(verdict["mediana_ok"])
        self.assertFalse(verdict["p90_ok"])
        self.assertFalse(verdict["entra"])
        others = self._era(odd)
        self.assertTrue(all(others[key]["entra"] for key in ("a", "b", "c")))

    def test_a_lone_session_cannot_be_checked(self):
        verdict = f1_reference.coherence(np.zeros((2, GRID)), ["a", "a"])["a"]
        self.assertFalse(verdict["entra"])


if __name__ == "__main__":
    unittest.main()
