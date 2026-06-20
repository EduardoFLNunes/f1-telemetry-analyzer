import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.telemetry_events import TelemetryEventBus  # noqa: E402


class TelemetryEventBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_scheduled_task_is_counted_until_subscribers_finish(self):
        bus = TelemetryEventBus()
        release = asyncio.Event()

        async def subscriber(_payload):
            await release.wait()

        bus.subscribe("opponents_frame", subscriber)
        future = bus.schedule("opponents_frame", {"cars": []}, asyncio.get_running_loop())
        await asyncio.sleep(0)

        pending = bus.snapshot()
        self.assertEqual(1, pending["pendingTasks"])
        self.assertEqual(1, pending["pendingByTopic"]["opponents_frame"])

        release.set()
        await asyncio.wrap_future(future)
        await asyncio.sleep(0)

        completed = bus.snapshot()
        self.assertEqual(0, completed["pendingTasks"])
        self.assertEqual({}, completed["pendingByTopic"])
        self.assertEqual(1, completed["scheduledTotal"])


if __name__ == "__main__":
    unittest.main()
