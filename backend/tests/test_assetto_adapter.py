import unittest
from pathlib import Path
import sys
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core import assetto_adapter
from core.assetto_adapter import AssettoAdapter


class AssettoAdapterSafetyTests(unittest.TestCase):
    def test_missing_shared_memory_does_not_create_named_mmap(self):
        adapter = AssettoAdapter()

        with patch.object(assetto_adapter, "_existing_ac_shared_memory_tags", return_value=None), \
             patch.object(assetto_adapter.mmap, "mmap") as mmap_mock:
            connected = adapter.connect()

        self.assertFalse(connected)
        mmap_mock.assert_not_called()

    def test_requires_all_assetto_shared_memory_pages(self):
        with patch.object(
            assetto_adapter,
            "_existing_shared_memory_tag",
            side_effect=["Local\\acpmf_physics", None, "Local\\acpmf_static"],
        ):
            tags = assetto_adapter._existing_ac_shared_memory_tags()

        self.assertIsNone(tags)

    def test_resolves_all_existing_assetto_shared_memory_pages(self):
        with patch.object(
            assetto_adapter,
            "_existing_shared_memory_tag",
            side_effect=lambda name: f"Local\\{name}",
        ):
            tags = assetto_adapter._existing_ac_shared_memory_tags()

        self.assertEqual(
            tags,
            {
                "physics": "Local\\acpmf_physics",
                "graphics": "Local\\acpmf_graphics",
                "static": "Local\\acpmf_static",
            },
        )


if __name__ == "__main__":
    unittest.main()
