"""Pedido 54: as sessoes aceitas com margem na checagem da linha do jogo (dados sinteticos).

A regra (docs/store_v2_e_evolucao.md, emenda de 17/11): uma sessao fora da
tolerancia de 0,10 m e aceita com margem quando a mediana, volta a volta, de
1000 x (mediana da sessao - 1,463 m) / v (a velocidade na passagem do comeco da
volta) fica em ate 2,0 ms em modulo.
"""

import unittest

import pandas as pd

from ml.data import store_checks

NORMAL = [1.45, 1.46, 1.47, 1.46, 1.47]       # perto dos 1,463 m


def laps(sessions):
    """{sessao: (posicoes da linha, velocidade na passagem do comeco em km/h)} -> voltas."""
    rows = []
    for session, (values, speed) in sessions.items():
        speeds = speed if isinstance(speed, list) else [speed] * len(values)
        for i, (value, v) in enumerate(zip(values, speeds)):
            rows.append({"lap_id": f"{session}#{i:04d}", "session_id": session, "linha_do_jogo_m": value,
                         "v_linha_inicio_kmh": v})
    return pd.DataFrame(rows)


def base():
    """Sessoes dentro da tolerancia, para a mediana de todas ficar perto de 1,463 m."""
    return {f"ok{i}": (NORMAL, 260.0) for i in range(6)}


class AceitaComMargemTest(unittest.TestCase):
    def test_sessao_dentro_da_tolerancia_passa_sem_margem(self):
        check = store_checks.check_game_line(laps(base()))
        self.assertTrue(check["passou"], check["motivos"])
        self.assertEqual(check["aceitas_com_margem"], [])
        self.assertEqual(check["margem_ms"], 2.0)
        self.assertTrue(all(s["dentro"] for s in check["sessoes"].values()))

    def test_fora_da_tolerancia_com_efeito_ate_2_ms_depois_da_linha(self):
        # 1,580 - 1,463 = +0,117 m a 260 km/h (72,2 m/s): +1,62 ms.
        sessions = {**base(), "depois": ([1.57, 1.58, 1.59, 1.58], 260.0)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertTrue(check["passou"], check["motivos"])
        entry = check["sessoes"]["depois"]
        self.assertFalse(entry["dentro"])
        self.assertTrue(entry["aceita_com_margem"])
        self.assertAlmostEqual(entry["efeito_ms"], 1000 * 0.117 / (260 / 3.6), delta=0.01)
        [item] = check["aceitas_com_margem"]
        self.assertEqual(item["sessao"], "depois")
        self.assertAlmostEqual(item["diferenca_m"], 0.117, delta=0.001)
        self.assertGreater(item["efeito_ms"], 0)
        self.assertEqual((item["voltas"], item["decisao"]), (4, "2026-11-17"))
        self.assertIn("aceita com margem", check["avisos_aceitas_com_margem"][0])
        self.assertIn("+0.117 m", check["avisos_aceitas_com_margem"][0])

    def test_fora_da_tolerancia_com_efeito_ate_2_ms_antes_da_linha(self):
        # 1,345 - 1,463 = -0,118 m a 260 km/h: -1,63 ms (para baixo tambem vale).
        sessions = {**base(), "antes": ([1.34, 1.345, 1.35], 260.0)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertTrue(check["passou"], check["motivos"])
        [item] = check["aceitas_com_margem"]
        self.assertEqual(item["sessao"], "antes")
        self.assertLess(item["efeito_ms"], 0)
        self.assertLessEqual(abs(item["efeito_ms"]), 2.0)

    def test_efeito_e_a_mediana_volta_a_volta_com_a_velocidade_de_cada_uma(self):
        # A mesma diferenca de +0,140 m; velocidades de 240, 260 e 280 km/h: a mediana e a de 260.
        sessions = {**base(), "s": ([1.603, 1.603, 1.603], [240.0, 260.0, 280.0])}
        check = store_checks.check_game_line(laps(sessions))
        self.assertAlmostEqual(check["sessoes"]["s"]["efeito_ms"], 1000 * 0.140 / (260 / 3.6), delta=0.01)

    def test_efeito_acima_de_2_ms_reprova(self):
        # +0,117 m a 150 km/h (41,7 m/s): +2,81 ms. A mesma diferenca que passa a 260 km/h reprova aqui.
        sessions = {**base(), "lenta": ([1.57, 1.58, 1.59], 150.0)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertFalse(check["passou"])
        self.assertEqual(check["aceitas_com_margem"], [])
        self.assertFalse(check["sessoes"]["lenta"]["aceita_com_margem"])
        self.assertTrue(check["motivos"][0].startswith("lenta:"), check["motivos"])
        self.assertIn("acima de 2.0 ms", check["motivos"][0])

    def test_diferenca_maior_reprova_na_mesma_velocidade(self):
        # +0,167 m a 260 km/h: +2,31 ms.
        sessions = {**base(), "longe": ([1.62, 1.63, 1.64], 260.0)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertFalse(check["passou"])
        self.assertGreater(check["sessoes"]["longe"]["efeito_ms"], 2.0)

    def test_sem_velocidade_na_linha_reprova(self):
        sessions = {**base(), "sem_v": ([1.57, 1.58, 1.59], None)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertFalse(check["passou"])
        self.assertIn("sem a velocidade", check["motivos"][0])

    def test_a_mediana_de_todas_continua_sendo_conferida(self):
        # Todas as sessoes aceitas com margem, mas a mediana de todas fora da tolerancia: reprova.
        sessions = {f"s{i}": ([1.57, 1.58, 1.59], 260.0) for i in range(3)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertFalse(check["passou"])
        self.assertTrue(check["motivos"][0].startswith("a mediana das voltas da primeira epoca"), check["motivos"])
        self.assertEqual(len(check["aceitas_com_margem"]), 3)

    def test_o_meta_leva_a_lista_e_a_margem(self):
        sessions = {**base(), "depois": ([1.57, 1.58, 1.59, 1.58], 260.0), "antes": ([1.34, 1.345, 1.35], 260.0)}
        meta = store_checks.margin_meta({"linha_do_jogo": store_checks.check_game_line(laps(sessions))})
        self.assertEqual(set(meta), {"sessoes_aceitas_com_margem", "margem_linha_do_jogo_ms", "linha_do_jogo_regimes"})
        self.assertEqual(meta["margem_linha_do_jogo_ms"], 2.0)
        self.assertEqual(sorted(i["sessao"] for i in meta["sessoes_aceitas_com_margem"]), ["antes", "depois"])
        for item in meta["sessoes_aceitas_com_margem"]:
            self.assertEqual(set(item), {"sessao", "mediana_m", "diferenca_m", "efeito_ms", "voltas", "decisao"})

    def test_o_construtor_grava_as_chaves_no_meta(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "ml" / "scripts" / "build_lap_store_v2.py").read_text(
            encoding="utf-8")
        self.assertIn("store_checks.margin_meta(result[\"checagens\"])", source)


ANTES = "2026-10-24_13-43-32_vhe_interlagos"        # antes de 31/10 19:52: 1,463 m
DEPOIS = "2026-11-12_22-57-03_vhe_interlagos"       # depois: 1,601 m (emenda de 18/11)


def dated(prefix, values, speed=260.0, n=1):
    """Sessoes com data no session_id: prefix e a data e hora, com `n` sessoes de nomes diferentes."""
    return {f"{prefix}_s{i}": (values, speed) for i in range(n)}


class DuasEpocasTest(unittest.TestCase):
    """Emenda de 18/11: 1,463 m antes de 31/10/2026 19:52 e 1,601 m a partir dai, pela data do session_id."""

    def test_a_epoca_vem_da_data_e_hora_do_comeco_da_sessao(self):
        self.assertEqual(store_checks.regime_of(ANTES)["registrada_m"], 1.463)
        self.assertEqual(store_checks.regime_of("2026-10-31_19-51-59_vhe_interlagos")["registrada_m"], 1.463)
        self.assertEqual(store_checks.regime_of("2026-10-31_19-52-00_vhe_interlagos")["registrada_m"], 1.601)
        self.assertEqual(store_checks.regime_of(DEPOIS)["registrada_m"], 1.601)
        self.assertEqual(store_checks.regime_of("s1")["registrada_m"], 1.463)       # sem data: a primeira
        self.assertIn("nao confirmada", store_checks.regime_of(DEPOIS)["causa"])

    def test_cada_sessao_contra_o_valor_da_sua_epoca(self):
        sessions = {**dated("2026-10-24_13-43-32", NORMAL, n=3), **dated("2026-11-12_22-57-03", [1.59, 1.60, 1.61], n=3)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertTrue(check["passou"], check["motivos"])
        self.assertEqual(check["aceitas_com_margem"], [])                  # 1,60 m depois de 31/10 passa sem margem
        self.assertEqual(check["sessoes"]["2026-11-12_22-57-03_s0"]["registrada_m"], 1.601)
        self.assertEqual(check["sessoes"]["2026-10-24_13-43-32_s0"]["registrada_m"], 1.463)
        self.assertEqual([r["voltas_medidas"] for r in check["regimes"]], [15, 9])

    def test_a_linha_velha_depois_de_31_10_fica_fora_da_tolerancia_da_epoca_nova(self):
        # 1,48 m numa sessao de 12/11: -0,121 m contra 1,601 m; a 260 km/h, -1,68 ms, aceita com margem.
        sessions = {**dated("2026-11-12_22-57-03", [1.60, 1.60, 1.61], n=3), "2026-11-13_10-00-00_x": ([1.47, 1.48, 1.49], 260.0)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertTrue(check["passou"], check["motivos"])
        [item] = check["aceitas_com_margem"]
        self.assertEqual(item["sessao"], "2026-11-13_10-00-00_x")
        self.assertAlmostEqual(item["diferenca_m"], -0.121, delta=0.001)
        self.assertLess(item["efeito_ms"], 0)

    def test_a_mediana_de_cada_epoca_e_conferida(self):
        # As tres sessoes da epoca nova a 1,72 m reprovam pela mediana da epoca (e pelo efeito, a 260 km/h).
        sessions = {**dated("2026-10-24_13-43-32", NORMAL, n=3), **dated("2026-11-12_22-57-03", [1.71, 1.72, 1.73], n=3)}
        check = store_checks.check_game_line(laps(sessions))
        self.assertFalse(check["passou"])
        self.assertTrue(any(m.startswith("a mediana das voltas desde 2026-10-31_19-52-00") for m in check["motivos"]),
                        check["motivos"])

    def test_o_meta_leva_as_duas_epocas(self):
        meta = store_checks.margin_meta({"linha_do_jogo": store_checks.check_game_line(laps(base()))})
        regimes = meta["linha_do_jogo_regimes"]
        self.assertEqual([(r["desde"], r["registrada_m"]) for r in regimes],
                         [(None, 1.463), ("2026-10-31_19-52-00", 1.601)])
        for item in regimes:
            self.assertEqual(set(item), {"desde", "registrada_m", "origem", "causa"})


if __name__ == "__main__":
    unittest.main()
