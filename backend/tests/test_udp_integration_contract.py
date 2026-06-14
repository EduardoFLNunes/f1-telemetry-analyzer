import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main
from core.telemetry.telemetry_reader_impl import (
    ACSharedMemoryReader,
    TelemetrySourceConfig,
    TelemetrySourceManager,
)


class UdpIntegrationContractTests(unittest.TestCase):
    def setUp(self):
        self.previous_source = backend_main.source_manager.active_source_name
        backend_main.opponents_buffer.clear()

    def tearDown(self):
        backend_main.source_manager.active_source_name = self.previous_source
        backend_main.opponents_buffer.clear()

    def test_assetto_player_reader_is_shared_memory_only(self):
        manager = TelemetrySourceManager(TelemetrySourceConfig(requested_source="assetto_corsa"))
        with patch.object(ACSharedMemoryReader, "connect", return_value=True):
            selected = manager.select_source("assetto_corsa")

        self.assertEqual(selected, "assetto_corsa")
        self.assertIsInstance(manager.reader, ACSharedMemoryReader)
        self.assertEqual(manager.player_source_name(), "shared_memory")

    def test_live_telemetry_contract_does_not_embed_opponents(self):
        backend_main.source_manager.active_source_name = "assetto_corsa"
        payload = asyncio.run(backend_main.get_live_telemetry(False, False))

        self.assertEqual(payload["playerSource"], "shared_memory")
        self.assertNotIn("opponents", payload)

    def test_live_opponents_contract_filters_player(self):
        backend_main.opponents_buffer.update_snapshot(
            [
                {"carId": 0, "isPlayer": True},
                {"carId": 2, "driverName": "Remote", "isMultiplayer": True},
            ],
            timestamp=100.0,
            player_car_id=0,
        )
        payload = asyncio.run(backend_main.get_live_opponents())

        self.assertEqual(payload["source"], "udp")
        self.assertEqual(payload["count"], 1)
        self.assertEqual([car["carId"] for car in payload["opponents"]], [2])
        self.assertTrue(payload["opponents"][0]["isMultiplayer"])

    def test_runtime_status_exposes_separate_sources(self):
        backend_main.source_manager.active_source_name = "assetto_corsa"
        payload = backend_main.runtime_status_payload()

        self.assertEqual(payload["telemetry"]["playerSource"], "shared_memory")
        self.assertEqual(payload["opponents"]["source"], "udp")
        self.assertEqual(payload["opponents"]["udpPort"], backend_main.opponents_config.port)


if __name__ == "__main__":
    unittest.main()
