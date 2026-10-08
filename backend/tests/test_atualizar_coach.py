"""Pedido 15, Parte C: atualizar o coach com um comando.

* a regra das sessoes novas sem anotacao (indicador ate a IA ligar, a volta em
  que ela liga e `misturada`, depois o detector);
* os rotulos versionados de 04/10, volta a volta, e a trava quando nao batem;
* o backup do modelo e a ordem dos passos do comando.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import pandas as pd

from ml.data import origin
from ml.scripts import detector_ia

BACKEND = Path(__file__).resolve().parents[1]


def load_command():
    spec = importlib.util.spec_from_file_location("atualizar_coach", BACKEND / "tools" / "atualizar_coach.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory_rows(session_id, indicators, *, equipment=origin.CURRENT_EQUIPMENT):
    return pd.DataFrame({
        "lap_id": [f"{session_id}#{i:04d}" for i in range(len(indicators))],
        "session_id": session_id,
        "sequence": range(len(indicators)),
        "origem_indicador": indicators,
        "origem": indicators,
        "origem_fonte": origin.SOURCE_INDICATOR,
        "equipamento": equipment,
        "duration_s": 90.0,
    })


class UnannotatedRuleTest(unittest.TestCase):
    def test_the_rule(self):
        self.assertEqual(origin.unannotated_origin("humano", None), ("humano", "indicador"))
        self.assertEqual(origin.unannotated_origin("misturada", None), ("misturada", "indicador"))
        for verdict in ("humano", "ia", "misturada"):
            self.assertEqual(origin.unannotated_origin("ia", verdict), (verdict, "detector"))
        self.assertEqual(origin.unannotated_origin("ia", "desconhecida"), ("desconhecida", None))
        self.assertEqual(origin.unannotated_origin("ia", None), ("desconhecida", None))
        self.assertEqual(origin.unannotated_origin("desconhecida", None), ("desconhecida", None))

    def test_a_new_session_before_and_after_the_ai_turns_on(self):
        # O piloto anda duas voltas, liga a IA na terceira, e o indicador fica travado depois.
        new = inventory_rows("2026-10-05_20-00-00_vhe_interlagos",
                             ["humano", "humano", "misturada", "ia", "ia", "ia", "ia"])
        verdicts = {
            new["lap_id"][3]: {"origem_detector": "ia", "motivo": "sinais concordam", "linha": "ia"},
            new["lap_id"][4]: {"origem_detector": "humano", "motivo": "sinais concordam", "linha": "humano"},
            new["lap_id"][5]: {"origem_detector": "desconhecida", "motivo": "linha indefinida", "linha": "desconhecida"},
            # a volta 6 nao tem grade: o detector nao diz nada
        }
        asked = []

        def classify(lap_id, row):
            asked.append(lap_id)
            return verdicts.get(lap_id)

        annotated = inventory_rows("2026-10-04_02-24-04_vhe_interlagos", ["ia"])
        annotated["origem"], annotated["origem_fonte"] = "misturada", origin.SOURCE_ANNOTATION
        old = inventory_rows("2026-06-19_23-24-46_vhe_interlagos", ["desconhecida", "ia"],
                             equipment=origin.PREVIOUS_EQUIPMENT)
        frame = pd.concat([annotated, old, new], ignore_index=True)
        out = origin.label_unannotated(frame, set(annotated["lap_id"]), classify).set_index("lap_id")

        got = [(out.at[i, "origem"], out.at[i, "origem_fonte"]) for i in new["lap_id"]]
        self.assertEqual(got, [
            ("humano", "indicador"), ("humano", "indicador"), ("misturada", "indicador"),
            ("ia", "detector"), ("humano", "detector"), ("desconhecida", None), ("desconhecida", None),
        ])
        self.assertEqual(out.at[new["lap_id"][4], "motivo_detector"], "sinais concordam")
        # o detector so e consultado nas voltas que o indicador da como ia
        self.assertEqual(asked, list(new["lap_id"][3:]))
        # a anotada e as do equipamento anterior nao mudam
        self.assertEqual(out.at[annotated["lap_id"][0], "origem"], "misturada")
        self.assertEqual(list(out.loc[old["lap_id"], "origem"]), ["desconhecida", "ia"])


class LapLabelsTest(unittest.TestCase):
    def inventory_from_file(self):
        labels = detector_ia.lap_labels()
        return pd.DataFrame({
            "lap_id": labels["lap_id"],
            "session_id": labels["lap_id"].str.split("#").str[0],
            "sequence": labels["lap_id"].str.split("#").str[1].astype(int),
            "lap_number": labels["volta_jogo"].astype(float),
            "game_lap_number": labels["volta_jogo"].astype(float),
        })

    def test_the_versioned_file_agrees_with_the_drivers_annotations(self):
        labels = detector_ia.lap_labels()
        self.assertEqual(len(labels), 53)
        self.assertEqual(detector_ia.check_lap_labels(self.inventory_from_file(), labels, detector_ia.annotations()), [])
        self.assertEqual(labels["origem"].value_counts().to_dict(), {"humano": 32, "ia": 17, "misturada": 4})

    def test_a_later_session_on_the_same_day_does_not_inherit_the_annotations(self):
        inventory = self.inventory_from_file()
        later = pd.DataFrame({"lap_id": ["2026-10-04_21-00-00_vhe_interlagos#0000"],
                              "session_id": ["2026-10-04_21-00-00_vhe_interlagos"], "sequence": [0],
                              "lap_number": [1.0], "game_lap_number": [1.0]})
        rows = detector_ia.labelled_session(pd.concat([inventory, later], ignore_index=True))
        self.assertEqual(len(rows), 53)
        self.assertNotIn(later["lap_id"][0], set(rows["lap_id"]))
        first = rows.set_index("lap_id").loc["2026-10-04_02-24-04_vhe_interlagos#0007"]
        self.assertEqual((first["parte"], first["volta_jogo"], first["origem_anotada"]), (1, 8.0, "misturada"))

    def test_it_stops_when_the_inventory_was_cut_differently(self):
        inventory = self.inventory_from_file()
        labels = detector_ia.lap_labels()
        notes = detector_ia.annotations()
        self.assertTrue(detector_ia.check_lap_labels(inventory.iloc[1:], labels, notes))
        extra = inventory.iloc[:1].assign(lap_id="2026-10-04_02-24-04_vhe_interlagos#0099", sequence=99)
        self.assertTrue(detector_ia.check_lap_labels(pd.concat([inventory, extra]), labels, notes))
        shifted = inventory.assign(game_lap_number=inventory["game_lap_number"] + 1)
        self.assertTrue(detector_ia.check_lap_labels(shifted, labels, notes))
        with self.assertRaises(SystemExit):
            detector_ia.labelled_session(inventory.iloc[1:])


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.command = load_command()
        self.tmp = Path(tempfile.mkdtemp())

    def test_backup_copies_the_model_with_date_and_time(self):
        model = self.tmp / "vhe_interlagos.json"
        self.assertIsNone(self.command.backup_model(model))
        model.write_text("{}", encoding="utf-8")
        now = datetime(2026, 10, 4, 22, 15, 0)
        copy = self.command.backup_model(model, now)
        self.assertEqual(copy, self.tmp / "backup" / "vhe_interlagos.2026-10-04_22-15-00.antes-de-atualizar.json")
        self.assertEqual(copy.read_text(encoding="utf-8"), "{}")
        with self.assertRaises(SystemExit):
            self.command.backup_model(model, now)

    def test_it_never_writes_the_installed_apps_model(self):
        installed = self.tmp / "Automobilista Telemetria" / "data" / "reference_models" / "vhe_interlagos.json"
        self.assertEqual(self.command.main(["--sem-varrer", "--modelo", str(installed)]), 2)

    def test_the_steps_run_in_order(self):
        calls = []
        out_dir = self.tmp / "origem"
        model = self.tmp / "vhe_interlagos.json"
        model.write_text("{}", encoding="utf-8")
        c = self.command

        def scan(directory, track, mode=None):
            calls.append("inventario")
            directory.mkdir(parents=True, exist_ok=True)
            inventory_rows("2026-10-05_20-00-00_vhe_interlagos", ["humano"]).to_parquet(
                directory / "lap_inventory.parquet", index=False)

        def apply(directory, track, json_path, promote=False):
            calls.append(("rotulos", promote))
            return {"sessao_rotulada_aplicada": {"voltas": 53, "origem": {}}, "sessoes_novas_sem_anotacao": []}

        class Train:
            @staticmethod
            def main(args):
                calls.append(("treino", args[args.index("--saida") + 1], (model.parent / "backup").exists()))
                return 0

        class Loaded:
            @staticmethod
            def load(path):
                calls.append("resumo")
                return object()

        c.load_geometry = lambda: None
        c.report_lap_origin.scan, original_scan = scan, c.report_lap_origin.scan
        c.detector_ia.apply, original_apply = apply, c.detector_ia.apply
        original_store = c.build_lap_store_v2.main

        def store_v2(args):
            calls.append(("store v2", args[args.index("--inventario") + 1].endswith("lap_inventory.parquet")))
            return 0

        c.build_lap_store_v2.main = store_v2
        try:
            c._evolution_script = lambda: type("E", (), {"PANEL_FILENAME": "painel.html", "main": staticmethod(
                lambda args: calls.append(("evolucao", args[args.index("--modelo") + 1])) or 0)})
            c._train_script = lambda: Train
            c.DriverReferenceModel = Loaded
            c.summary = lambda m, inv: {"referencias": {}, "referencia_padrao": "volta_ia",
                                        "voltas_por_origem": {"equipamento_atual": {}, "equipamento_atual_por_fonte": {},
                                                              "todas": {}},
                                        "voltas_do_piloto_no_modelo": 0,
                                        "limiar_s": {"mediana": 0, "min": 0, "max": 0, "microsetores_no_minimo": 0},
                                        "foco_inicial": {}}
            import contextlib
            import io

            printed = io.StringIO()
            with contextlib.redirect_stdout(printed):
                code = c.main(["--saida", str(out_dir), "--modelo", str(model), "--resumo", str(self.tmp / "r.json")])
        finally:
            c.report_lap_origin.scan = original_scan
            c.detector_ia.apply = original_apply
            c.build_lap_store_v2.main = original_store
        self.assertEqual(code, 0)
        self.assertEqual(calls, ["inventario", ("rotulos", False), ("treino", str(model), True), "resumo",
                                 ("store v2", True), ("evolucao", str(model))])
        # Pedido 17: no fim, o caminho do painel.
        last = printed.getvalue().strip().splitlines()[-1]
        self.assertTrue(last.startswith("painel da evolucao: "))
        self.assertTrue(last.endswith("painel.html"))
        self.assertTrue((self.tmp / "r.json").exists())

    def test_a_failed_training_stops_the_command(self):
        c = self.command
        out_dir = self.tmp / "origem"
        out_dir.mkdir()
        inventory_rows("2026-10-05_20-00-00_vhe_interlagos", ["humano"]).to_parquet(
            out_dir / "lap_inventory.parquet", index=False)
        c.load_geometry = lambda: None
        original_apply = c.detector_ia.apply
        c.detector_ia.apply = lambda *a, **k: {"sessao_rotulada_aplicada": {"voltas": 53, "origem": {}},
                                               "sessoes_novas_sem_anotacao": []}
        try:
            c._train_script = lambda: type("T", (), {"main": staticmethod(lambda args: 2)})
            code = c.main(["--sem-varrer", "--saida", str(out_dir), "--modelo", str(self.tmp / "m.json")])
        finally:
            c.detector_ia.apply = original_apply
        self.assertEqual(code, 2)

    def test_a_failed_store_v2_check_stops_before_the_evolution_report(self):
        c = self.command
        out_dir = self.tmp / "origem"
        out_dir.mkdir()
        inventory_rows("2026-10-05_20-00-00_vhe_interlagos", ["humano"]).to_parquet(
            out_dir / "lap_inventory.parquet", index=False)
        model = self.tmp / "m.json"
        model.write_text("{}", encoding="utf-8")
        reached = []
        c.load_geometry = lambda: None
        original_apply, original_store = c.detector_ia.apply, c.build_lap_store_v2.main
        c.detector_ia.apply = lambda *a, **k: {"sessao_rotulada_aplicada": {"voltas": 53, "origem": {}},
                                               "sessoes_novas_sem_anotacao": []}
        c.build_lap_store_v2.main = lambda args: 2
        try:
            c._train_script = lambda: type("T", (), {"main": staticmethod(lambda args: 0)})
            c.DriverReferenceModel = type("L", (), {"load": staticmethod(lambda path: object())})
            c.summary = lambda m, inv: {"referencias": {}, "referencia_padrao": "volta_ia",
                                        "voltas_por_origem": {"equipamento_atual": {}, "equipamento_atual_por_fonte": {},
                                                              "todas": {}},
                                        "voltas_do_piloto_no_modelo": 0,
                                        "limiar_s": {"mediana": 0, "min": 0, "max": 0, "microsetores_no_minimo": 0},
                                        "foco_inicial": {}}
            c._evolution_script = lambda: reached.append("evolucao")
            code = c.main(["--sem-varrer", "--saida", str(out_dir), "--modelo", str(model),
                           "--resumo", str(self.tmp / "r.json")])
        finally:
            c.detector_ia.apply, c.build_lap_store_v2.main = original_apply, original_store
        self.assertEqual(code, 2)
        self.assertEqual(reached, [])


if __name__ == "__main__":
    unittest.main()
