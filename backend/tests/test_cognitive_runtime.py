import unittest
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.cognitive_runtime import CognitiveRuntime
from core.telemetry_events import DRIVER_COG_STATE, PROCESSED_FRAME, event_bus


class CognitiveRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_emits_cognitive_state_from_processed_frame(self):
        runtime = CognitiveRuntime(min_interval_seconds=0.0)
        events = []

        async def collect(payload):
            events.append(payload)

        event_bus.subscribe(DRIVER_COG_STATE, collect)
        try:
            await runtime.on_frame(
                {
                    "timestamp": 42.0,
                    "throttle": 0.75,
                    "brake": 0.0,
                    "steering": 0.2,
                }
            )
        finally:
            event_bus.unsubscribe(DRIVER_COG_STATE, collect)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], DRIVER_COG_STATE)
        self.assertEqual(events[0]["timestamp"], 42.0)
        self.assertIn("confidence", events[0]["metrics"])
        self.assertIn("aggression", events[0]["metrics"])
        self.assertIn("smoothness", events[0]["metrics"])
        self.assertIsInstance(events[0]["state"], str)

    def test_start_stop_subscribes_processed_frames(self):
        runtime = CognitiveRuntime()
        runtime.start()
        try:
            self.assertIn(runtime.on_frame, event_bus.subscribers[PROCESSED_FRAME])
        finally:
            runtime.stop()

        self.assertNotIn(runtime.on_frame, event_bus.subscribers.get(PROCESSED_FRAME, []))


if __name__ == "__main__":
    unittest.main()
