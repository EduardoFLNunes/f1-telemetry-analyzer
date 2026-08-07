import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import assetto_shared_memory_gate as gate  # noqa: E402


class GateStatusCacheTests(unittest.TestCase):
    """Probing the game process shells out to `tasklist`.

    The desktop UI polls endpoints that read the gate every few seconds, and
    those handlers are async, so an uncached probe blocks the event loop hard
    enough to stall /api/health and make Electron's startup health check time
    out. These tests pin the memoization that prevents that.
    """

    def setUp(self):
        gate.reset_gate_status_cache()
        self.addCleanup(gate.reset_gate_status_cache)

    def test_repeated_calls_probe_the_process_only_once(self):
        with patch.object(gate, "assetto_corsa_process_running", return_value=False) as probe:
            for _ in range(25):
                gate.shared_memory_gate_status()

        self.assertEqual(probe.call_count, 1, "repeated polls must reuse the memoized status")

    def test_cached_payload_is_equivalent_across_calls(self):
        with patch.object(gate, "assetto_corsa_process_running", return_value=False):
            first = gate.shared_memory_gate_status()
            second = gate.shared_memory_gate_status()

        self.assertEqual(first, second)
        self.assertFalse(first["allowed"])

    def test_callers_cannot_mutate_the_cache(self):
        with patch.object(gate, "assetto_corsa_process_running", return_value=False):
            first = gate.shared_memory_gate_status()
            first["allowed"] = "tampered"
            second = gate.shared_memory_gate_status()

        self.assertNotEqual(second["allowed"], "tampered")

    def test_force_refresh_bypasses_the_cache(self):
        with patch.object(gate, "assetto_corsa_process_running", return_value=False) as probe:
            gate.shared_memory_gate_status()
            gate.shared_memory_gate_status(force_refresh=True)

        self.assertEqual(probe.call_count, 2)

    def test_reset_forces_the_next_call_to_probe_again(self):
        with patch.object(gate, "assetto_corsa_process_running", return_value=False) as probe:
            gate.shared_memory_gate_status()
            gate.reset_gate_status_cache()
            gate.shared_memory_gate_status()

        self.assertEqual(probe.call_count, 2)

    def test_zero_ttl_disables_caching(self):
        with patch.dict("os.environ", {gate._GATE_CACHE_TTL_ENV: "0"}):
            with patch.object(gate, "assetto_corsa_process_running", return_value=False) as probe:
                gate.shared_memory_gate_status()
                gate.shared_memory_gate_status()

        self.assertEqual(probe.call_count, 2)

    def test_state_change_is_picked_up_after_the_ttl_expires(self):
        with patch.dict("os.environ", {gate._GATE_CACHE_TTL_ENV: "0"}):
            with patch.object(gate, "assetto_corsa_process_running", return_value=False):
                self.assertFalse(gate.shared_memory_gate_status()["allowed"])
            with patch.object(gate, "assetto_corsa_process_running", return_value=True), \
                 patch.object(gate, "shared_memory_pages_status", return_value={"ready": True, "available": {"acpmf_static": "acpmf_static"}}), \
                 patch.object(gate, "shared_memory_static_status", return_value={"checked": True, "ready": True}):
                self.assertTrue(gate.shared_memory_gate_status()["allowed"])


if __name__ == "__main__":
    unittest.main()
