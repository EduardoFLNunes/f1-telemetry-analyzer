import asyncio
import json
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.websocket_server import TelemetryBroadcaster, split_live_frame


class _BlockingManager:
    def __init__(self):
        self.messages = []
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def broadcast(self, message):
        self.messages.append(message)
        if len(self.messages) == 1:
            self.started.set()
            await self.release.wait()


class TelemetryBroadcasterTests(unittest.IsolatedAsyncioTestCase):
    def test_live_frame_omits_heavy_physics_and_projection_debug(self):
        frame = {
            "timestamp": 123,
            "speed": 42,
            "carPhysics": {"tyres": {"wheelLoad": [1, 2, 3, 4]}},
            "projectionDebug": {"candidateCount": 10},
        }

        live, detail = split_live_frame(frame)

        self.assertEqual({"timestamp": 123, "speed": 42}, live)
        self.assertEqual(frame["carPhysics"], detail["carPhysics"])
        self.assertNotIn("carPhysics", live)
        self.assertNotIn("projectionDebug", live)
        self.assertIn("carPhysics", frame)
        full_size = len(json.dumps(frame, separators=(",", ":")))
        live_size = len(json.dumps(live, separators=(",", ":")))
        self.assertLess(live_size, full_size)

    async def test_keeps_only_latest_frame_while_client_is_slow(self):
        manager = _BlockingManager()
        broadcaster = TelemetryBroadcaster(manager, subscribe=False, frame_hz=1000)

        await broadcaster.on_frame({"sequence": 1})
        await asyncio.wait_for(manager.started.wait(), timeout=1)
        await broadcaster.on_frame({"sequence": 2})
        await broadcaster.on_frame({"sequence": 3})
        manager.release.set()

        for _ in range(100):
            if len(manager.messages) >= 2:
                break
            await asyncio.sleep(0.005)

        self.assertEqual([item["data"]["sequence"] for item in manager.messages], [1, 3])

    async def test_piggybacks_opponents_on_active_telemetry_sender(self):
        manager = _BlockingManager()
        broadcaster = TelemetryBroadcaster(manager, subscribe=False, frame_hz=1000)
        broadcaster.opponents_interval = 0

        await broadcaster.on_frame({"sequence": 1})
        await asyncio.wait_for(manager.started.wait(), timeout=1)
        await broadcaster.on_opponents({"cars": [{"carId": 2}]})

        self.assertIsNone(broadcaster._opponents_sender_task)
        manager.release.set()
        await broadcaster._frame_sender_task

        self.assertEqual([item["type"] for item in manager.messages], ["telemetry", "opponents"])

    async def test_sends_detailed_physics_on_separate_low_frequency_message(self):
        manager = _BlockingManager()
        manager.release.set()
        broadcaster = TelemetryBroadcaster(
            manager,
            subscribe=False,
            frame_hz=1000,
            detail_hz=1000,
        )

        await broadcaster.on_frame({"timestamp": 1, "speed": 10, "carPhysics": {"rpm": 7000}})
        await broadcaster._frame_sender_task

        self.assertEqual([item["type"] for item in manager.messages], ["telemetry", "telemetry_detail"])
        self.assertNotIn("carPhysics", manager.messages[0]["data"])
        self.assertEqual({"rpm": 7000}, manager.messages[1]["data"]["carPhysics"])


if __name__ == "__main__":
    unittest.main()
