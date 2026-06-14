import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.websocket_server import TelemetryBroadcaster


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


if __name__ == "__main__":
    unittest.main()
