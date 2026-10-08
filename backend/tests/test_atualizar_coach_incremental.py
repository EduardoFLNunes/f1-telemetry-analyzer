"""Pedido 25: modo incremental do `atualizar_coach` (inventario e store v2 com cache por gravacao).

Tudo sintetico: gravacoes pequenas numa pista circular, em pastas temporarias.
Nenhum teste le as gravacoes reais nem grava nos caches reais.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from ml import config  # noqa: E402
from ml.data import session_cache as sc  # noqa: E402
from ml.data.recordings import Session  # noqa: E402
from ml.data.store_v2 import build_store_v2  # noqa: E402
from ml.scripts import build_lap_store_v2 as bsv2  # noqa: E402
from ml.scripts import report_lap_origin as rlo  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from tests.test_lap_origin import circular_track  # noqa: E402

SPEED = 40.0          # m/s
HZ = 60.0
# A volta da pista circular leva ~31 s; o resto dos portoes fica o padrao.
GATES = dataclasses.replace(config.DEFAULT_GATES, min_lap_seconds=10.0)
TRACK = dataclasses.replace(circular_track(), geometry_id="circulo-p25")
TABLES = ("lap_inventory.parquet", rlo.CLOCK_TABLE, rlo.SIGNALS_TABLE, rlo.GRID_TABLE)


def write_recording(directory: Path, laps: int, clock0: float, car: str = "carro_a") -> None:
    """`laps` voltas completas seguidas e um trecho curto no fim, com relogio de parede a partir de `clock0`."""
    length = TRACK.length
    lines = []
    clock = clock0
    spans = [(k + 1, k * length + 0.4, (k + 1) * length - 0.3) for k in range(laps)]
    spans.append((laps + 1, laps * length + 0.4, laps * length + 60.0))
    for number, start, end in spans:
        for value in np.arange(start, end, SPEED / HZ):
            theta = np.mod(value, length) / 200.0
            clock += (SPEED / HZ) / SPEED
            lines.append(json.dumps({"timestamp": clock * 1000.0, "track": "vhe_interlagos", "sample": {
                "lap": number, "lap_number": number, "lap_time": float(np.mod(value, length) / SPEED),
                "world_x": 200.0 * np.cos(theta), "world_z": 200.0 * np.sin(theta), "speedKmh": SPEED * 3.6,
                "carPhysics": {
                    "controls": {"throttle": 1.0, "brake": 0.0, "steerAngle": 0.1 * np.sin(value / 50.0),
                                 "gear": 4, "rpm": 7000.0},
                    "motion": {"accG": {"lateral": SPEED ** 2 / 200.0 / 9.81, "longitudinal": 0.0, "vertical": 1.0}},
                },
            }}))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "player.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "metadata.json").write_text(json.dumps({"metadata": {"carModel": car}}), encoding="utf-8")


class Workspace:
    """Uma pasta de gravacoes, uma saida do inventario e os dois caches, todos temporarios."""

    IDS = ("2026-10-06_10-00-00_vhe_interlagos", "2026-10-06_11-00-00_vhe_interlagos",
           "2026-10-07_09-00-00_vhe_interlagos")

    def __init__(self, sessions=3):
        self.root = Path(tempfile.mkdtemp(prefix="p25_"))
        self.recordings = self.root / "recordings"
        for i, sid in enumerate(self.IDS[:sessions]):
            write_recording(self.recordings / sid, laps=2 + i, clock0=1_790_000_000.0 + 10_000.0 * i)

    def sessions(self):
        return [Session(session_id=d.name, directory=d, track="vhe_interlagos")
                for d in sorted(self.recordings.iterdir()) if (d / "player.jsonl").exists()]

    def scan(self, name: str, mode=None, cache="cache_inv", track=TRACK, gates=GATES):
        out = self.root / name
        out.mkdir(parents=True, exist_ok=True)
        run = rlo.scan(out, track, mode=mode, sessions=self.sessions(), cache_dir=self.root / cache, gates=gates)
        return out, run

    def store(self, inventory: pd.DataFrame, mode=None, cache="cache_store"):
        sectors = build_microsectors(TRACK)
        materials = construction = None
        if mode is not None:
            materials, _, construction = bsv2.materials_from_cache(
                inventory, TRACK, sectors, self.sessions(), mode, self.root / cache)
        store, details = build_store_v2(inventory, track=TRACK, sessions=self.sessions(), sectors=sectors,
                                        materials=materials)
        return store, details, construction

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def tables(out: Path):
    return {name: pd.read_parquet(out / name) for name in TABLES}


def assert_same_tables(case, left: Path, right: Path):
    for name in TABLES:
        a, b = pd.read_parquet(left / name), pd.read_parquet(right / name)
        pd.testing.assert_frame_equal(a, b, check_exact=True, obj=name)


def assert_same_store(case, a, b):
    pd.testing.assert_frame_equal(a[0].frame, b[0].frame, check_exact=True, obj="store.frame")
    pd.testing.assert_frame_equal(a[0].laps, b[0].laps, check_exact=True, obj="store.laps")
    case.assertEqual(a[1].box_removed, b[1].box_removed)
    case.assertEqual(a[1].channels_by_lap, b[1].channels_by_lap)
    case.assertEqual(a[1].not_found, b[1].not_found)
    case.assertEqual(a[1].sessions, b[1].sessions)


class CountingReads:
    """Conta as leituras de sessao dos dois passos sem mudar o que elas fazem."""

    def __enter__(self):
        self.inventory, self.store = [], []
        real_inv, real_store = rlo.read_session_tables, bsv2.materialize_session

        def inv(session, *a, **k):
            self.inventory.append(session.session_id)
            return real_inv(session, *a, **k)

        def store(session, *a, **k):
            self.store.append(session.session_id)
            return real_store(session, *a, **k)

        self._patches = [mock.patch.object(rlo, "read_session_tables", inv),
                         mock.patch.object(bsv2, "materialize_session", store)]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


class InventoryCacheTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()

    def tearDown(self):
        self.ws.cleanup()

    def test_unchanged_sessions_are_not_read(self):
        self.ws.scan("a", mode="incremental")
        with CountingReads() as reads:
            out, run = self.ws.scan("b", mode="incremental")
        self.assertEqual(reads.inventory, [])
        self.assertEqual(run["modo"], "incremental")
        self.assertEqual(run["do_cache"], 3)
        assert_same_tables(self, self.ws.root / "a", out)

    def test_a_changed_session_is_read_again_and_a_missing_one_leaves(self):
        self.ws.scan("a", mode="incremental")
        target = self.ws.recordings / Workspace.IDS[1] / "player.jsonl"
        stat = target.stat()
        os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))      # so a data
        with CountingReads() as reads:
            self.ws.scan("b", mode="incremental")
        self.assertEqual(reads.inventory, [Workspace.IDS[1]])
        with target.open("a", encoding="utf-8") as handle:                             # o tamanho
            handle.write("\n")
        with CountingReads() as reads:
            self.ws.scan("c", mode="incremental")
        self.assertEqual(reads.inventory, [Workspace.IDS[1]])

        shutil.rmtree(self.ws.recordings / Workspace.IDS[2])
        with CountingReads() as reads:
            out, run = self.ws.scan("d", mode="incremental")
        self.assertEqual(reads.inventory, [])
        self.assertEqual(run["sumiram"], [Workspace.IDS[2]])
        self.assertNotIn(Workspace.IDS[2], set(pd.read_parquet(out / "lap_inventory.parquet")["session_id"]))
        manifest = json.loads((self.ws.root / "cache_inv" / sc.MANIFEST).read_text(encoding="utf-8"))
        self.assertNotIn(Workspace.IDS[2], manifest["sessoes"])
        full, _ = self.ws.scan("full", mode=None)
        assert_same_tables(self, full, out)

    def test_a_changed_global_key_reads_everything_and_says_why(self):
        self.ws.scan("a", mode="incremental")
        cases = {
            "geometria": dict(track=dataclasses.replace(TRACK, geometry_id="outra")),
            "portoes": dict(gates=dataclasses.replace(GATES, max_long_gaps=4)),
        }
        for word, kwargs in cases.items():
            with CountingReads() as reads:
                _, run = self.ws.scan("x", mode="incremental", **kwargs)
            self.assertEqual(len(reads.inventory), 3, word)
            self.assertEqual(run["modo"], "completo")
            self.assertIn(word, run["motivo"])
            self.ws.scan("a", mode="incremental")       # volta a chave de sempre (le tudo de novo)
        real = sc.code_hashes
        with mock.patch.object(sc, "code_hashes", lambda files: {**real(files), "ml/config.py": "mudou"}):
            with CountingReads() as reads:
                _, run = self.ws.scan("x", mode="incremental")
        self.assertEqual(len(reads.inventory), 3)
        self.assertIn("codigo: ml/config.py", run["motivo"])
        self.ws.scan("a", mode="incremental")
        with mock.patch.object(sc, "CACHE_FORMAT", sc.CACHE_FORMAT + 1):
            with CountingReads() as reads:
                _, run = self.ws.scan("x", mode="incremental")
        self.assertEqual(len(reads.inventory), 3)
        self.assertIn("formato do cache", run["motivo"])

    def test_a_broken_cache_is_rebuilt_whole(self):
        self.ws.scan("a", mode="incremental")
        broken = next((self.ws.root / "cache_inv").glob("*.pkl"))
        broken.write_bytes(b"isto nao e pickle")
        with CountingReads() as reads:
            out, run = self.ws.scan("b", mode="incremental")
        self.assertEqual(len(reads.inventory), 3)
        self.assertIn("nao abre", run["motivo"])
        assert_same_tables(self, self.ws.root / "a", out)

    def test_completo_reads_everything_and_rebuilds_the_cache(self):
        self.ws.scan("a", mode="incremental")
        with CountingReads() as reads:
            _, run = self.ws.scan("b", mode="completo")
        self.assertEqual(len(reads.inventory), 3)
        self.assertEqual(run["motivo"], "--completo")
        with CountingReads() as reads:
            self.ws.scan("c", mode="incremental")
        self.assertEqual(reads.inventory, [])

    def test_duplicates_between_a_cached_session_and_a_new_one_match_the_full_scan(self):
        ws = Workspace(sessions=2)
        try:
            ws.scan("a", mode="incremental")
            copy = ws.recordings / "2026-10-06_10-00-05_vhe_interlagos"      # a mesma gravacao, outro id
            shutil.copytree(ws.recordings / Workspace.IDS[0], copy)
            with CountingReads() as reads:
                out, _ = ws.scan("b", mode="incremental")
            self.assertEqual(reads.inventory, [copy.name])
            full, _ = ws.scan("full", mode=None)
            assert_same_tables(self, full, out)
            inventory = pd.read_parquet(out / "lap_inventory.parquet")
            self.assertGreater(int(inventory["duplicada_de"].notna().sum()), 0)
        finally:
            ws.cleanup()


class StoreCacheTest(unittest.TestCase):
    def setUp(self):
        self.ws = Workspace()
        out, _ = self.ws.scan("inv", mode=None)
        self.inventory = pd.read_parquet(out / "lap_inventory.parquet")
        self.assertGreater(int(self.inventory["valid"].sum()), 3)

    def tearDown(self):
        self.ws.cleanup()

    def test_a_changed_label_reaches_the_store_without_reading_again(self):
        self.ws.store(self.inventory, mode="incremental")
        changed = self.inventory.copy()
        lap_id = changed.loc[changed["valid"], "lap_id"].iloc[0]
        changed.loc[changed["lap_id"] == lap_id, "origem"] = "ia"
        changed.loc[changed["lap_id"] == lap_id, "origem_fonte"] = "anotacao"
        with CountingReads() as reads:
            store, details, construction = self.ws.store(changed, mode="incremental")
        self.assertEqual(reads.store, [])
        self.assertEqual(construction["sessoes_lidas"], [])
        row = store.laps.set_index("lap_id").loc[lap_id]
        self.assertEqual((row["origem"], row["origem_fonte"]), ("ia", "anotacao"))
        assert_same_store(self, (store, details), self.ws.store(changed, mode=None)[:2])

    def test_a_selected_lap_missing_from_the_cache_reads_the_session_again(self):
        partial = self.inventory.copy()
        lap_id = partial.loc[partial["valid"], "lap_id"].iloc[-1]
        session_id = lap_id.split("#")[0]
        partial.loc[partial["lap_id"] == lap_id, "valid"] = False
        self.ws.store(partial, mode="incremental")
        with CountingReads() as reads:
            store, details, _ = self.ws.store(self.inventory, mode="incremental")
        self.assertEqual(reads.store, [session_id])
        assert_same_store(self, (store, details), self.ws.store(self.inventory, mode=None)[:2])

    def test_the_recording_sha256_comes_from_the_cache_when_the_files_did_not_change(self):
        _, cache, _ = bsv2.materials_from_cache(self.inventory, TRACK, build_microsectors(TRACK),
                                                self.ws.sessions(), "incremental", self.ws.root / "cs")
        by_id = {s.session_id: s for s in self.ws.sessions()}
        first = bsv2.recording_entries(sorted(by_id), by_id, cache)
        expected = {sid: bsv2.file_entry(by_id[sid].player_stream) for sid in sorted(by_id)}
        self.assertEqual(first, expected)
        with mock.patch.object(bsv2, "file_entry", side_effect=AssertionError("nao devia reler")):
            self.assertEqual(bsv2.recording_entries(sorted(by_id), by_id, cache), expected)


class EndToEndTest(unittest.TestCase):
    """As tres rodadas da Parte D com 3 sessoes falsas: o incremental da o mesmo que o completo."""

    def test_three_rounds_match_the_full_path(self):
        ws = Workspace()
        try:
            full_out, _ = ws.scan("full", mode=None)
            full_inventory = pd.read_parquet(full_out / "lap_inventory.parquet")
            full_store = ws.store(full_inventory, mode=None)[:2]

            def round_(name):
                with CountingReads() as reads:
                    out, run = ws.scan(name, mode="incremental")
                    inventory = pd.read_parquet(out / "lap_inventory.parquet")
                    store, details, construction = ws.store(inventory, mode="incremental")
                assert_same_tables(self, full_out, out)
                assert_same_store(self, full_store, (store, details))
                return reads, run, construction

            reads, run, construction = round_("r1")                     # cache vazio
            self.assertEqual(len(reads.inventory), 3)
            self.assertEqual(len(reads.store), 3)
            self.assertTrue(run["cache_vazio_no_inicio"])
            reads, run, construction = round_("r2")                     # nada novo
            self.assertEqual((reads.inventory, reads.store), ([], []))
            newest = Workspace.IDS[2]                                   # sessao nova simulada
            self.assertTrue(sc.forget_session(ws.root / "cache_inv", newest))
            self.assertTrue(sc.forget_session(ws.root / "cache_store", newest))
            reads, run, construction = round_("r3")
            self.assertEqual((reads.inventory, reads.store), ([newest], [newest]))
            self.assertEqual(construction["sessoes_lidas"], [newest])
        finally:
            ws.cleanup()


class InstalledAppTest(unittest.TestCase):
    def test_no_cache_is_written_in_the_installed_app_folder(self):
        root = Path(tempfile.mkdtemp())
        try:
            with self.assertRaisesRegex(ValueError, "app instalado"):
                sc.SessionCache(root / sc.INSTALLED_APP_FOLDER / "data" / "cache", {"formato": 1})
            installed = config.installed_app_recordings_root()
            if installed is not None:
                with self.assertRaisesRegex(ValueError, "app instalado"):
                    sc.ensure_not_installed_app(Path(installed) / "cache")
            self.assertFalse((root / sc.INSTALLED_APP_FOLDER / "data" / "cache").exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_the_command_refuses_an_output_folder_in_the_installed_app(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location("atualizar_coach_p25", BACKEND / "tools" / "atualizar_coach.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        root = Path(tempfile.mkdtemp())
        try:
            target = root / sc.INSTALLED_APP_FOLDER / "origem"
            with mock.patch.object(module.report_lap_origin, "scan", side_effect=AssertionError("nao devia varrer")):
                self.assertEqual(module.main(["--saida", str(target)]), 2)
            self.assertFalse(target.exists())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_the_default_caches_live_in_the_repository(self):
        self.assertTrue(str(bsv2.DEFAULT_CACHE_DIR).startswith(str(config.artifacts_root())))
        sc.ensure_not_installed_app(bsv2.DEFAULT_CACHE_DIR)
        sc.ensure_not_installed_app(config.artifacts_root() / "origem" / rlo.CACHE_DIR)


class CodeKeyTest(unittest.TestCase):
    def test_the_code_lists_exist_and_cover_what_the_reading_imports(self):
        for name in sc.STORE_CODE:
            self.assertTrue((BACKEND / name).exists(), name)
        for folder in ("ml/preprocessing", "ml/track"):
            for path in sorted((BACKEND / folder).glob("*.py")):
                self.assertIn(f"{folder}/{path.name}", sc.INVENTORY_CODE)
        self.assertTrue(set(sc.INVENTORY_CODE) <= set(sc.STORE_CODE))
        for name in ("ml/data/store_v2.py", "ml/data/ai_detector.py", "ml/data/lap_store.py"):
            self.assertIn(name, sc.STORE_CODE)
        code = ("import sys, ml.data.inventory, ml.data.origin_signals, ml.data.session_cache;"
                "print('\\n'.join(sorted(m for m in sys.modules if m == 'ml' or m.startswith('ml.'))))")
        out = subprocess.run([sys.executable, "-c", code], cwd=str(BACKEND), capture_output=True, text=True,
                             timeout=120, check=True).stdout.split()
        listed = {name[:-3].replace("/", ".").replace(".__init__", "") for name in sc.INVENTORY_CODE}
        self.assertEqual(sorted(set(out) - listed), [])


if __name__ == "__main__":
    unittest.main()
