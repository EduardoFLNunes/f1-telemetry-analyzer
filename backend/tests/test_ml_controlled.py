"""Sessao controlada (Fase 2c): plano, casamento de voltas, execucao e efeitos.

A sessao sintetica tem efeitos conhecidos: frear 10 m mais cedo custa 40 ms,
mudar a linha custa 20 ms, sem interacao, e cada volta tem 20 ms de ruido.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.validation import controlled as ct

BRAKING_COST_S = 0.040
LINE_COST_S = 0.020
NOISE_S = 0.020
BASE_S = 14.0


def synthetic_session(seed=0, plan=None, interaction=0.0, braking_done=-10.0, inward_done=2.0, direction=-1):
    """Voltas gravadas que seguem o plano, com medidas e tempo da janela."""
    plan = plan if plan is not None else ct.make_plan(seed=2026)
    rng = np.random.default_rng(seed)
    rows = []
    for i, row in plan.iterrows():
        code = row["condicao"]
        early = code in ("B", "D")
        inside = code in ("C", "D")
        time = BASE_S + 0.004 * row["bloco"] + rng.normal(0, NOISE_S)
        time += BRAKING_COST_S * early + LINE_COST_S * inside + interaction * (early and inside)
        rows.append(
            {
                "lap_id": f"S#{i + 1:04d}",
                "sequence": i + 1,
                "lap_number": i + 2,
                "valid": True,
                "reasons": "",
                "tempo_janela_s": time,
                "braking_point_s": 2620.0 + braking_done * early + rng.normal(0, 1.0),
                "lateral_entry_m": 1.0 + direction * inward_done * inside + rng.normal(0, 0.2),
                "lateral_apex_m": -3.0 + direction * inward_done * inside + rng.normal(0, 0.2),
                "lateral_exit_m": 2.0 + rng.normal(0, 0.2),
                "throttle_point_s": 2740.0 + rng.normal(0, 2.0),
            }
        )
    laps = pd.DataFrame(rows)
    # Volta de saida dos boxes, que os gates rejeitam.
    out_lap = {"lap_id": "S#0000", "sequence": 0, "lap_number": 1, "valid": False, "reasons": "faltam 900 m de pista"}
    return pd.concat([pd.DataFrame([out_lap]), laps], ignore_index=True)


def analyse(laps, plan, invalid=(), direction=-1, start=None):
    matched = ct.match_laps(laps[["lap_id", "sequence", "lap_number", "valid", "reasons"]], plan, invalid, start=start)
    matched = matched.merge(laps.drop(columns=["sequence", "lap_number", "valid", "reasons"]), on="lap_id")
    measured = matched[matched["condicao"] != ct.WARMUP]
    effects = ct.estimate_effects(
        measured["tempo_janela_s"].to_numpy(), measured["condicao"].to_numpy(), measured["bloco"].to_numpy()
    )
    return matched, ct.execution_check(matched, direction), effects


def inside(effect, value):
    low, high = effect["ic95_s"]
    return low <= value <= high


class PlanTest(unittest.TestCase):
    def test_same_seed_same_plan_and_other_seed_other_order(self):
        a, b = ct.make_plan(seed=2026), ct.make_plan(seed=2026)
        pd.testing.assert_frame_equal(a, b)
        self.assertFalse(a["condicao"].equals(ct.make_plan(seed=7)["condicao"]))
        self.assertEqual(list(a.columns), list(ct.PLAN_COLUMNS))
        self.assertTrue((a["semente"] == 2026).all())

    def test_every_block_has_the_four_conditions_once(self):
        plan = ct.make_plan(seed=2026, laps_per_condition=8, warmup=5)
        self.assertEqual(len(plan), 5 + 32)
        self.assertEqual((plan["condicao"] == ct.WARMUP).sum(), 5)
        for block, group in plan[plan["bloco"] > 0].groupby("bloco"):
            self.assertEqual(sorted(group["condicao"]), ["A", "B", "C", "D"], block)
        self.assertEqual(plan["ordem"].tolist(), list(range(1, 38)))

    def test_orders_differ_between_blocks(self):
        plan = ct.make_plan(seed=2026)
        orders = {tuple(g["condicao"]) for _, g in plan[plan["bloco"] > 0].groupby("bloco")}
        self.assertGreater(len(orders), 1)

    def test_text_version_lists_every_lap(self):
        text = ct.plan_text(ct.make_plan(seed=2026))
        self.assertIn("semente 2026", text)
        self.assertIn("REPITA A MESMA CONDICAO", text)
        self.assertEqual(text.count("  volta "), 37)

    def test_unknown_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            ct.make_plan(conditions=("A", "E"))
        with self.assertRaises(ValueError):
            ct.make_plan(curve="Curva inexistente")


class EffectRecoveryTest(unittest.TestCase):
    def test_known_effects_fall_inside_the_intervals(self):
        plan = ct.make_plan(seed=2026)
        _, _, effects = analyse(synthetic_session(seed=1, plan=plan), plan)
        self.assertTrue(inside(effects["frenagem"], BRAKING_COST_S), effects["frenagem"])
        self.assertTrue(inside(effects["linha"], LINE_COST_S), effects["linha"])
        self.assertTrue(inside(effects["interacao"], 0.0), effects["interacao"])
        self.assertTrue(inside(effects["D_menos_A"], BRAKING_COST_S + LINE_COST_S))
        # Com 20 ms de ruido e 16 contra 16 voltas, o efeito de 40 ms nao inclui zero.
        self.assertGreater(effects["frenagem"]["ic95_s"][0], 0.0)

    def test_intervals_have_their_nominal_coverage(self):
        # IC pela t com os graus de liberdade do residuo: 32 voltas - 4 condicoes
        # - 7 blocos = 21. Em 1000 sessoes o erro-padrao da cobertura e 0,7
        # ponto, entao 93-97 % e o nominal com folga de ~3 erros-padrao.
        plan = ct.make_plan(seed=2026)
        measured = plan[plan["condicao"] != ct.WARMUP]
        truth = {"frenagem": BRAKING_COST_S, "linha": LINE_COST_S, "interacao": 0.0}
        hits = dict.fromkeys(truth, 0)
        runs = 1000
        for seed in range(runs):
            times = synthetic_session(seed=seed, plan=plan)["tempo_janela_s"].to_numpy()[1:][len(plan) - len(measured):]
            effects = ct.estimate_effects(times, measured["condicao"].to_numpy(), measured["bloco"].to_numpy())
            self.assertEqual(effects["_modelo"]["graus_de_liberdade"], 21)
            for name, value in truth.items():
                hits[name] += inside(effects[name], value)
        for name in truth:
            self.assertGreater(hits[name] / runs, 0.93, name)
            self.assertLess(hits[name] / runs, 0.97, name)

    def test_an_interaction_is_detected(self):
        plan = ct.make_plan(seed=2026)
        _, _, effects = analyse(synthetic_session(seed=3, plan=plan, interaction=0.080), plan)
        self.assertTrue(inside(effects["interacao"], 0.080))
        self.assertGreater(effects["interacao"]["ic95_s"][0], 0.0)

    def test_an_incomplete_block_still_fits(self):
        plan = ct.make_plan(seed=2026)
        laps = synthetic_session(seed=4, plan=plan)
        matched = ct.match_laps(laps[["lap_id", "sequence", "lap_number", "valid", "reasons"]], plan)
        matched = matched.merge(laps[["lap_id", "tempo_janela_s"]], on="lap_id")
        measured = matched[matched["condicao"] != ct.WARMUP].iloc[:-1]   # ultima volta perdida
        effects = ct.estimate_effects(
            measured["tempo_janela_s"].to_numpy(), measured["condicao"].to_numpy(), measured["bloco"].to_numpy()
        )
        self.assertTrue(inside(effects["frenagem"], BRAKING_COST_S))


class ExecutionCheckTest(unittest.TestCase):
    def test_executed_as_asked(self):
        plan = ct.make_plan(seed=2026)
        _, execution, _ = analyse(synthetic_session(seed=5, plan=plan), plan)
        self.assertAlmostEqual(execution["B"]["frenagem_vs_A_m"], -10.0, delta=1.5)
        self.assertAlmostEqual(execution["C"]["para_dentro_vs_A_m"]["entry"], 2.0, delta=0.3)
        self.assertFalse(any(e["longe_do_pedido"] for e in execution.values()))

    def test_far_from_the_request_is_said_clearly(self):
        plan = ct.make_plan(seed=2026)
        laps = synthetic_session(seed=6, plan=plan, braking_done=-3.0, inward_done=0.5)
        _, execution, _ = analyse(laps, plan)
        self.assertTrue(execution["B"]["longe_do_pedido"])
        self.assertTrue(execution["D"]["longe_do_pedido"])
        self.assertIn("frenagem", " ".join(execution["B"]["observacoes"]))
        self.assertIn("linha", " ".join(execution["C"]["observacoes"]))

    def test_inward_follows_the_corner_direction(self):
        plan = ct.make_plan(seed=2026)
        # Curva a esquerda: para dentro e lateral positivo.
        laps = synthetic_session(seed=7, plan=plan, direction=+1)
        _, execution, _ = analyse(laps, plan, direction=+1)
        self.assertGreater(execution["C"]["para_dentro_vs_A_m"]["entry"], 1.5)


class MatchingTest(unittest.TestCase):
    def setUp(self):
        self.plan = ct.make_plan(seed=2026)
        self.laps = synthetic_session(seed=8, plan=self.plan)
        self.table = self.laps[["lap_id", "sequence", "lap_number", "valid", "reasons"]]

    def test_out_lap_rejected_by_gates_is_skipped(self):
        matched = ct.match_laps(self.table, self.plan)
        self.assertEqual(len(matched), len(self.plan))
        self.assertEqual(matched["lap_id"].iloc[0], "S#0001")

    def test_lap_count_mismatch_stops_with_the_lap_list(self):
        short = self.table.iloc[:-1]
        with self.assertRaises(ct.PlanMismatchError) as caught:
            ct.match_laps(short, self.plan)
        message = str(caught.exception)
        self.assertIn("37 voltas", message)
        self.assertIn("36 voltas", message)
        self.assertIn("Nada foi casado", message)
        self.assertIn("S#0000", message)            # lista cada volta, com o motivo
        self.assertIn("faltam 900 m", message)

    def test_the_lap_list_shows_what_the_driver_saw(self):
        table = self.table.iloc[:-1].copy()
        table["lap_time_s"] = 85.0 + np.arange(len(table)) * 0.1
        table["clock"] = [f"20:{i // 60:02d}:{i % 60:02d}" for i in range(len(table))]
        table.loc[table.index[0], "lap_time_s"] = np.nan          # volta sem cronometro
        with self.assertRaises(ct.PlanMismatchError) as caught:
            ct.match_laps(table, self.plan)
        message = str(caught.exception)
        self.assertIn("(volta 2 no jogo, tempo 1:25.100, as 20:00:01)", message)
        self.assertIn("(volta 1 no jogo, as 20:00:00)", message)

    def test_a_declared_invalid_lap_is_removed_and_the_rest_matches(self):
        extra = pd.DataFrame(
            [{"lap_id": "S#9999", "sequence": 10.5, "lap_number": 99, "valid": True, "reasons": ""}]
        )
        table = pd.concat([self.table, extra], ignore_index=True)
        with self.assertRaises(ct.PlanMismatchError):
            ct.match_laps(table, self.plan)                      # sem anotar, nao bate
        matched = ct.match_laps(table, self.plan, invalid=[99])  # anotada, bate
        self.assertNotIn("S#9999", set(matched["lap_id"]))

    def test_invalid_lap_with_a_repeated_game_number_is_not_guessed(self):
        table = self.table.copy()
        table.loc[table.index[-1], "lap_number"] = table["lap_number"].iloc[5]
        with self.assertRaises(ct.PlanMismatchError) as caught:
            ct.match_laps(table, self.plan, invalid=[int(table["lap_number"].iloc[5])])
        self.assertIn("mais de uma vez", str(caught.exception))


def with_warmup(laps, plan, warmup):
    """A mesma sessao medida, gravada com `warmup` voltas de aquecimento.

    As voltas medidas sao identicas (mesmos tempos e medidas); so muda quantas
    voltas livres vieram antes delas. Numeracao do jogo e ordem refeitas.
    """
    out_lap = laps.iloc[[0]]
    plan_warmup = int((plan["condicao"] == ct.WARMUP).sum())
    template = laps.iloc[1]
    measured = laps.iloc[1 + plan_warmup :]
    free = pd.DataFrame([template] * warmup)
    recorded = pd.concat([out_lap, free, measured], ignore_index=True)
    recorded["sequence"] = np.arange(len(recorded))
    recorded["lap_number"] = np.arange(len(recorded)) + 1
    recorded["lap_id"] = [f"W#{i:04d}" for i in range(len(recorded))]
    first_measured = 1 + warmup
    return recorded, int(recorded["lap_number"].iloc[first_measured])


class StartLapTest(unittest.TestCase):
    """Inicio pela volta anotada pelo piloto (pedido 10)."""

    def setUp(self):
        self.plan = ct.make_plan(seed=2026, warmup=5)
        self.laps = synthetic_session(seed=12, plan=self.plan)

    def test_four_five_and_seven_warmup_laps_give_the_same_result(self):
        results = []
        for warmup in (4, 5, 7):
            recorded, start = with_warmup(self.laps, self.plan, warmup)
            matched, execution, effects = analyse(recorded, self.plan, start=start)
            self.assertEqual(len(matched), 32, warmup)
            self.assertEqual(matched["condicao"].tolist(), self.plan.loc[self.plan["condicao"] != ct.WARMUP, "condicao"].tolist())
            results.append((effects["frenagem"]["estimativa_s"], effects["linha"]["estimativa_s"], execution["B"]["frenagem_vs_A_m"]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])

    def test_without_start_a_different_warmup_still_stops(self):
        recorded, _ = with_warmup(self.laps, self.plan, 7)
        with self.assertRaises(ct.PlanMismatchError) as caught:
            analyse(recorded, self.plan)
        self.assertIn("--inicio", str(caught.exception))

    def test_start_that_does_not_exist_stops_clearly(self):
        recorded, _ = with_warmup(self.laps, self.plan, 5)
        with self.assertRaises(ct.PlanMismatchError) as caught:
            analyse(recorded, self.plan, start=999)
        message = str(caught.exception)
        self.assertIn("999", message)
        self.assertIn("nao existe na gravacao", message)

    def test_start_with_a_repeated_game_number_is_not_guessed(self):
        recorded, start = with_warmup(self.laps, self.plan, 5)
        recorded.loc[2, "lap_number"] = start
        with self.assertRaises(ct.PlanMismatchError) as caught:
            analyse(recorded, self.plan, start=start)
        self.assertIn("aparece 2 vezes", str(caught.exception))

    def test_measured_laps_are_still_counted_strictly(self):
        recorded, start = with_warmup(self.laps, self.plan, 5)
        with self.assertRaises(ct.PlanMismatchError) as caught:
            analyse(recorded.iloc[:-1], self.plan, start=start)
        self.assertIn("31 voltas aproveitaveis", str(caught.exception))
        self.assertIn("32 voltas medidas", str(caught.exception))

    def test_an_invalid_lap_after_start_is_skipped_and_one_before_is_ignored(self):
        recorded, start = with_warmup(self.laps, self.plan, 5)
        extra = recorded.iloc[[10]].copy()
        extra["sequence"] = 10.5
        extra["lap_number"] = 500
        extra["lap_id"] = "W#extra"
        recorded = pd.concat([recorded, extra], ignore_index=True)
        matched, _, _ = analyse(recorded, self.plan, invalid=[2, 500], start=start)
        self.assertNotIn("W#extra", set(matched["lap_id"]))
        self.assertEqual(len(matched), 32)

    def test_plan_text_asks_for_the_first_lap_of_block_1(self):
        text = ct.plan_text(self.plan)
        line = "ANOTE o numero no jogo desta volta (primeira do bloco 1): ____"
        self.assertEqual(text.count(line), 1)
        self.assertLess(text.index("BLOCO 1"), text.index(line))
        self.assertLess(text.index(line), text.index("BLOCO 2"))


class EstimatorComparisonTest(unittest.TestCase):
    def test_contrasts_and_bands(self):
        plan = ct.make_plan(seed=2026)
        _, _, effects = analyse(synthetic_session(seed=9, plan=plan), plan)
        perfect = {c: (effects[f"{c}_menos_A"]["estimativa_s"], -1.0, 1.0) for c in "BCD"}
        wrong = {c: (0.0, -0.001, 0.001) for c in "BCD"}
        out = ct.compare_with_estimators(effects, {"perfeito": perfect, "zero": wrong}, {"B": True})
        self.assertAlmostEqual(out["perfeito"]["frenagem"]["erro_s"], 0.0, places=9)
        self.assertAlmostEqual(out["perfeito"]["interacao"]["erro_s"], 0.0, places=9)
        self.assertTrue(out["perfeito"]["B_menos_A"]["medido_dentro_da_faixa"])
        self.assertFalse(out["zero"]["D_menos_A"]["medido_dentro_da_faixa"])
        self.assertTrue(out["zero"]["B_menos_A"]["fora_da_distribuicao"])

    def test_condition_differences_are_x_minus_a(self):
        plan = ct.make_plan(seed=2026)
        matched, _, _ = analyse(synthetic_session(seed=10, plan=plan), plan)
        diff = ct.condition_differences(matched)
        self.assertAlmostEqual(diff["B"][0], -10.0, delta=1.5)    # frenagem
        self.assertAlmostEqual(diff["C"][1], -2.0, delta=0.3)     # entrada, curva a direita


if __name__ == "__main__":
    unittest.main()
