import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.geometry.track_geometry_provider import resolve_geometry_resource_root


class TrackGeometryResourceRootTests(unittest.TestCase):
    def test_uses_packaged_resource_root_when_configured(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch.dict(os.environ, {"AT_BACKEND_RESOURCE_ROOT": temporary_dir}):
                self.assertEqual(
                    resolve_geometry_resource_root(),
                    Path(temporary_dir).resolve(),
                )

    def test_falls_back_to_repository_root(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AT_BACKEND_RESOURCE_ROOT", None)
            root = resolve_geometry_resource_root()

        self.assertTrue((root / "backend").is_dir())
        self.assertTrue((root / "frontend").is_dir())


if __name__ == "__main__":
    unittest.main()
