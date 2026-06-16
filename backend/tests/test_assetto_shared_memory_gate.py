import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main
from core.assetto_adapter import AssettoAdapter
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
    "reason": "waiting_for_assetto_corsa_process",
}


class AssettoSharedMemoryGateTests(unittest.TestCase):
    def test_adapter_does_not_open_mmap_before_assetto_process(self):
        adapter = AssettoAdapter()

        with patch(
            "core.assetto_adapter.shared_memory_gate_status",
            return_value=BLOCKED_GATE,
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


if __name__ == "__main__":
    unittest.main()
