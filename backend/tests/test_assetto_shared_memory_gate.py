import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main
from core.assetto_adapter import AssettoAdapter
from core.assetto_shared_memory_gate import shared_memory_gate_status
from core.debug.ac_shared_memory_full_inventory import build_ac_shared_memory_full_inventory
from core.telemetry.telemetry_reader_impl import (
    ACSharedMemoryReader,
    TelemetrySourceConfig,
    TelemetrySourceManager,
)


BLOCKED_GATE = {
    "enabled": True,
    "allowed": False,
    "processRunning": False,
    "processNames": ["acs.exe"],
    "pages": {"checked": False, "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"], "available": {}, "missing": []},
    "reason": "waiting_for_assetto_corsa_process",
}

PAGES_MISSING_GATE = {
    "enabled": True,
    "allowed": False,
    "processRunning": True,
    "processNames": ["acs.exe"],
    "pages": {
        "checked": True,
        "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
        "available": {},
        "missing": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
        "ready": False,
    },
    "reason": "waiting_for_assetto_corsa_shared_memory_pages",
}

STALE_PAGES_GATE = {
    "enabled": True,
    "allowed": False,
    "processRunning": False,
    "processNames": ["acs.exe"],
    "pages": {
        "checked": True,
        "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
        "available": {"acpmf_physics": "Local\\acpmf_physics"},
        "missing": [],
        "ready": True,
    },
    "static": {"checked": False, "ready": False},
    "reason": "stale_assetto_corsa_shared_memory_without_process",
}

STATIC_MISSING_GATE = {
    "enabled": True,
    "allowed": False,
    "processRunning": True,
    "processNames": ["acs.exe"],
    "pages": {
        "checked": True,
        "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
        "available": {
            "acpmf_physics": "Local\\acpmf_physics",
            "acpmf_graphics": "Local\\acpmf_graphics",
            "acpmf_static": "Local\\acpmf_static",
        },
        "missing": [],
        "ready": True,
    },
    "static": {"checked": True, "ready": False, "reason": "static_page_has_no_session_data"},
    "reason": "waiting_for_assetto_corsa_static_data",
}


class AssettoSharedMemoryGateTests(unittest.TestCase):
    def test_reader_returns_only_new_shared_memory_packets(self):
        reader = ACSharedMemoryReader()
        reader.connected = True
        reader.adapter.is_connected = True
        reader.connect = Mock(return_value=True)
        frame = {
            "packet_id": 10,
            "x": 12.0,
            "y": 0.0,
            "z": 34.0,
            "speed": 20.0,
        }
        reader.adapter.poll = Mock(side_effect=[frame, frame, {**frame, "packet_id": 11}])

        self.assertIsNotNone(reader.read_sample())
        self.assertIsNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())

    def test_reader_falls_back_to_payload_when_packet_id_is_missing_or_stuck(self):
        reader = ACSharedMemoryReader()
        reader.connected = True
        reader.adapter.is_connected = True
        reader.connect = Mock(return_value=True)
        frame = {
            "packet_id": 10,
            "x": 12.0,
            "y": 0.0,
            "z": 34.0,
            "speed": 20.0,
            "lap_time": 1.0,
        }
        frame_without_id = {key: value for key, value in frame.items() if key != "packet_id"}
        reader.adapter.poll = Mock(side_effect=[
            frame,
            {**frame, "speed": 21.0},
            frame_without_id,
            frame_without_id,
            {**frame_without_id, "speed": 22.0},
        ])

        self.assertIsNotNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())
        self.assertIsNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())

    def test_reader_accepts_packet_restart_and_small_physics_changes(self):
        reader = ACSharedMemoryReader()
        reader.connected = True
        reader.adapter.is_connected = True
        reader.connect = Mock(return_value=True)
        frame = {
            "packet_id": 99,
            "x": 12.0,
            "y": 0.0,
            "z": 34.0,
            "speed": 70.0,
            "heading": 1.0,
            "lat_g": 0.4,
            "lap_time": 10.0,
        }
        reader.adapter.poll = Mock(side_effect=[
            frame,
            {**frame, "packet_id": 0},
            {**frame, "packet_id": 0, "heading": 1.001},
            {**frame, "packet_id": 0, "lat_g": 0.401},
        ])

        self.assertIsNotNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())
        self.assertIsNotNone(reader.read_sample())

    def test_gate_reports_stale_pages_when_process_is_absent(self):
        pages_ready = {
            "checked": True,
            "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
            "available": {"acpmf_static": "Local\\acpmf_static"},
            "missing": [],
            "ready": True,
        }

        with patch(
            "core.assetto_shared_memory_gate.assetto_corsa_process_running",
            return_value=False,
        ), patch(
            "core.assetto_shared_memory_gate.shared_memory_pages_status",
            return_value=pages_ready,
        ):
            status = shared_memory_gate_status()

        self.assertFalse(status["allowed"])
        self.assertFalse(status["processRunning"])
        self.assertEqual(status["reason"], "stale_assetto_corsa_shared_memory_without_process")

    def test_gate_blocks_running_process_until_shared_memory_pages_exist(self):
        missing_pages = {
            "checked": True,
            "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
            "available": {"acpmf_physics": "Local\\acpmf_physics"},
            "missing": ["acpmf_graphics", "acpmf_static"],
            "ready": False,
        }

        with patch(
            "core.assetto_shared_memory_gate.assetto_corsa_process_running",
            return_value=True,
        ), patch(
            "core.assetto_shared_memory_gate.shared_memory_pages_status",
            return_value=missing_pages,
        ):
            status = shared_memory_gate_status()

        self.assertFalse(status["allowed"])
        self.assertTrue(status["processRunning"])
        self.assertEqual(status["reason"], "waiting_for_assetto_corsa_shared_memory_pages")
        self.assertEqual(status["pages"]["missing"], ["acpmf_graphics", "acpmf_static"])

    def test_gate_blocks_until_static_session_data_is_valid(self):
        pages_ready = {
            "checked": True,
            "required": ["acpmf_physics", "acpmf_graphics", "acpmf_static"],
            "available": {
                "acpmf_physics": "Local\\acpmf_physics",
                "acpmf_graphics": "Local\\acpmf_graphics",
                "acpmf_static": "Local\\acpmf_static",
            },
            "missing": [],
            "ready": True,
        }
        static_waiting = {"checked": True, "ready": False, "reason": "static_page_has_no_session_data"}

        with patch(
            "core.assetto_shared_memory_gate.assetto_corsa_process_running",
            return_value=True,
        ), patch(
            "core.assetto_shared_memory_gate.shared_memory_pages_status",
            return_value=pages_ready,
        ), patch(
            "core.assetto_shared_memory_gate.shared_memory_static_status",
            return_value=static_waiting,
        ):
            status = shared_memory_gate_status()

        self.assertFalse(status["allowed"])
        self.assertEqual(status["reason"], "waiting_for_assetto_corsa_static_data")
        self.assertEqual(status["static"]["reason"], "static_page_has_no_session_data")

    def test_adapter_does_not_open_mmap_before_assetto_process(self):
        adapter = AssettoAdapter()

        with patch(
            "core.assetto_adapter.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
        ), patch("mmap.mmap", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(adapter.connect())

        self.assertFalse(adapter.is_connected)

    def test_adapter_does_not_open_mmap_for_stale_pages_without_process(self):
        adapter = AssettoAdapter()

        with patch(
            "core.assetto_adapter.shared_memory_gate_status",
            return_value=STALE_PAGES_GATE,
        ), patch("mmap.mmap", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(adapter.connect())

        self.assertFalse(adapter.is_connected)

    def test_adapter_does_not_open_mmap_before_shared_memory_pages_exist(self):
        adapter = AssettoAdapter()

        with patch(
            "core.assetto_adapter.shared_memory_gate_status",
            return_value=PAGES_MISSING_GATE,
        ), patch("mmap.mmap", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(adapter.connect())

        self.assertFalse(adapter.is_connected)

    def test_adapter_does_not_open_mmap_before_static_data_exists(self):
        adapter = AssettoAdapter()

        with patch(
            "core.assetto_adapter.shared_memory_gate_status",
            return_value=STATIC_MISSING_GATE,
        ), patch("mmap.mmap", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(adapter.connect())

        self.assertFalse(adapter.is_connected)

    def test_reader_does_not_touch_adapter_before_assetto_process(self):
        reader = ACSharedMemoryReader()

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
        ), patch.object(reader.adapter, "connect", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(reader.connect())

        self.assertFalse(reader.connected)
        self.assertEqual(reader.latest_shared_memory_gate_status["reason"], "waiting_for_assetto_corsa_process")

    def test_reader_does_not_touch_adapter_before_shared_memory_pages_exist(self):
        reader = ACSharedMemoryReader()

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=PAGES_MISSING_GATE,
        ), patch.object(reader.adapter, "connect", side_effect=AssertionError("mmap should not be opened")):
            self.assertFalse(reader.connect())

        self.assertFalse(reader.connected)
        self.assertEqual(
            reader.latest_shared_memory_gate_status["reason"],
            "waiting_for_assetto_corsa_shared_memory_pages",
        )

    def test_auto_source_stays_mock_until_assetto_process_is_running(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="auto"))

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
        ), patch("core.assetto_adapter.AssettoAdapter.connect", side_effect=AssertionError("mmap should not be opened")):
            selected = manager.select_source("auto")

        self.assertEqual(selected, "mock")
        self.assertEqual(manager.get_active_source_name(), "mock")
        self.assertFalse(manager.ac_available)

    def test_explicit_assetto_source_reports_process_gate(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="assetto_corsa"))

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
        ), patch("core.assetto_adapter.AssettoAdapter.connect", side_effect=AssertionError("mmap should not be opened")):
            with self.assertRaisesRegex(RuntimeError, "Assetto Corsa is not running"):
                manager.select_source("assetto_corsa")

    def test_explicit_assetto_source_reports_stale_pages_gate(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="assetto_corsa"))

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=STALE_PAGES_GATE,
        ), patch("core.assetto_adapter.AssettoAdapter.connect", side_effect=AssertionError("mmap should not be opened")):
            with self.assertRaisesRegex(RuntimeError, "stale Assetto Corsa shared memory pages"):
                manager.select_source("assetto_corsa")

    def test_explicit_assetto_source_reports_pages_gate(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="assetto_corsa"))

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=PAGES_MISSING_GATE,
        ), patch("core.assetto_adapter.AssettoAdapter.connect", side_effect=AssertionError("mmap should not be opened")):
            with self.assertRaisesRegex(RuntimeError, "shared memory pages are not ready"):
                manager.select_source("assetto_corsa")

    def test_explicit_assetto_source_reports_static_data_gate(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="assetto_corsa"))

        with patch(
            "core.telemetry.telemetry_reader_impl.shared_memory_gate_status",
            return_value=STATIC_MISSING_GATE,
        ), patch("core.assetto_adapter.AssettoAdapter.connect", side_effect=AssertionError("mmap should not be opened")):
            with self.assertRaisesRegex(RuntimeError, "static telemetry is not ready"):
                manager.select_source("assetto_corsa")

    def test_debug_inventory_respects_process_gate(self):
        with patch(
            "core.debug.ac_shared_memory_full_inventory.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
        ), patch("mmap.mmap", side_effect=AssertionError("mmap should not be opened")):
            inventory = build_ac_shared_memory_full_inventory()

        self.assertEqual(inventory["shared_memory_gate"]["reason"], "waiting_for_assetto_corsa_process")
        self.assertFalse(inventory["current_snapshot"]["connection_status"])

    def test_live_source_endpoint_does_not_stop_runtime_when_gate_blocks(self):
        class DummyRuntime:
            stopped = False

            def stop(self):
                self.stopped = True

        previous_runtime = backend_main.telemetry_runtime
        dummy_runtime = DummyRuntime()
        backend_main.telemetry_runtime = dummy_runtime
        try:
            with patch("main.shared_memory_gate_status", return_value=BLOCKED_GATE):
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(backend_main.set_live_source("assetto_corsa"))
            self.assertEqual(error.exception.status_code, 400)
            self.assertFalse(dummy_runtime.stopped)
            self.assertIs(backend_main.telemetry_runtime, dummy_runtime)
        finally:
            backend_main.telemetry_runtime = previous_runtime

    def test_live_source_endpoint_does_not_stop_runtime_when_stale_pages_gate_blocks(self):
        class DummyRuntime:
            stopped = False

            def stop(self):
                self.stopped = True

        previous_runtime = backend_main.telemetry_runtime
        dummy_runtime = DummyRuntime()
        backend_main.telemetry_runtime = dummy_runtime
        try:
            with patch("main.shared_memory_gate_status", return_value=STALE_PAGES_GATE):
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(backend_main.set_live_source("assetto_corsa"))
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("Stale Assetto Corsa shared memory pages", str(error.exception.detail))
            self.assertFalse(dummy_runtime.stopped)
            self.assertIs(backend_main.telemetry_runtime, dummy_runtime)
        finally:
            backend_main.telemetry_runtime = previous_runtime

    def test_live_source_endpoint_does_not_stop_runtime_when_pages_gate_blocks(self):
        class DummyRuntime:
            stopped = False

            def stop(self):
                self.stopped = True

        previous_runtime = backend_main.telemetry_runtime
        dummy_runtime = DummyRuntime()
        backend_main.telemetry_runtime = dummy_runtime
        try:
            with patch("main.shared_memory_gate_status", return_value=PAGES_MISSING_GATE):
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(backend_main.set_live_source("assetto_corsa"))
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("shared memory pages are not ready", str(error.exception.detail))
            self.assertFalse(dummy_runtime.stopped)
            self.assertIs(backend_main.telemetry_runtime, dummy_runtime)
        finally:
            backend_main.telemetry_runtime = previous_runtime

    def test_live_source_endpoint_does_not_stop_runtime_when_static_gate_blocks(self):
        class DummyRuntime:
            stopped = False

            def stop(self):
                self.stopped = True

        previous_runtime = backend_main.telemetry_runtime
        dummy_runtime = DummyRuntime()
        backend_main.telemetry_runtime = dummy_runtime
        try:
            with patch("main.shared_memory_gate_status", return_value=STATIC_MISSING_GATE):
                with self.assertRaises(HTTPException) as error:
                    asyncio.run(backend_main.set_live_source("assetto_corsa"))
            self.assertEqual(error.exception.status_code, 400)
            self.assertIn("static telemetry is not ready", str(error.exception.detail))
            self.assertFalse(dummy_runtime.stopped)
            self.assertIs(backend_main.telemetry_runtime, dummy_runtime)
        finally:
            backend_main.telemetry_runtime = previous_runtime


if __name__ == "__main__":
    unittest.main()
