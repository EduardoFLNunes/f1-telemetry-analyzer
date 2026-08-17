import asyncio
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys

import pandas as pd
from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main as backend_main  # noqa: E402
from core.assisted_analysis.service import AssistedAnalysisService  # noqa: E402
from core.assisted_analysis.validation_fixture_factory import write_phase14_1_validation_recording  # noqa: E402
from core.cache.track_cache import TrackCache  # noqa: E402
from core.external_references import (  # noqa: E402
    ExternalReferenceError,
    ExternalReferenceNormalizer,
    ExternalReferenceRepository,
    FastF1ReferenceProvider,
)
from core.live.runtime_state import RuntimeState  # noqa: E402
from core.telemetry.telemetry_buffer import TelemetryBuffer  # noqa: E402


def _telemetry_fixture():
    return pd.DataFrame(
        {
            "Time": [0.0, 1.0, 2.0, 3.0],
            "Distance": [0.0, 100.0, 220.0, 340.0],
            "Speed": [275.0, 170.0, 140.0, 230.0],
            "Throttle": [100.0, 0.0, 20.0, 100.0],
            "Brake": [0.0, 100.0, 40.0, 0.0],
            "RPM": [11200.0, 9400.0, 8800.0, 10800.0],
            "nGear": [7, 4, 3, 6],
            "X": [0.0, 100.0, 180.0, 300.0],
            "Y": [0.0, 20.0, 60.0, 100.0],
        }
    )


def _make_service(repo_root: Path, repository: ExternalReferenceRepository) -> AssistedAnalysisService:
    return AssistedAnalysisService(
        repo_root,
        TelemetryBuffer(max_size=5000),
        RuntimeState(),
        TrackCache(str(repo_root / "data" / "cache" / "tracks")),
        external_reference_repository=repository,
    )


class ExternalReferenceTests(unittest.TestCase):
    def test_normalizer_converts_fastf1_fixture_to_internal_model(self):
        reference = ExternalReferenceNormalizer().normalize_fastf1_telemetry(
            _telemetry_fixture(),
            year=2024,
            event="Brazil",
            session="Q",
            driver="VER",
            team="Red Bull Racing",
            lap_number=12,
            lap_time=70.1,
        )

        self.assertEqual("FASTF1", reference.metadata.source)
        self.assertEqual("EXTERNAL_F1", reference.metadata.reference_type)
        self.assertEqual("UNCALIBRATED", reference.metadata.calibration_status)
        self.assertEqual("LIMITED", reference.metadata.comparable_to_assetto)
        self.assertEqual(4, len(reference.samples))
        self.assertAlmostEqual(1.0, reference.samples[-1].progress)
        self.assertAlmostEqual(1.0, reference.samples[0].throttle)
        self.assertAlmostEqual(1.0, reference.samples[1].brake)

    def test_repository_persists_and_lists_external_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = ExternalReferenceRepository(root)
            reference = ExternalReferenceNormalizer().normalize_fastf1_telemetry(
                _telemetry_fixture(),
                year=2024,
                event="Brazil",
                session="Q",
                driver="VER",
            )
            repository.save(reference)

            listed = repository.list_references()
            loaded = repository.get(reference.metadata.reference_id)
            self.assertEqual(1, len(listed))
            self.assertIsNotNone(loaded)
            self.assertEqual(reference.metadata.reference_id, loaded.metadata.reference_id)
            self.assertFalse("samples" in listed[0])

    def test_repository_starts_even_where_it_cannot_write(self):
        # The packaged app installed under Program Files cannot write inside its
        # own directory. Creating this repository used to raise there, and the
        # backend died on import before serving a request.
        with tempfile.TemporaryDirectory() as tmp:
            blocked = Path(tmp) / "not_a_directory"
            blocked.write_text("a file where a directory would have to go", encoding="utf-8")

            repository = ExternalReferenceRepository(Path(tmp), data_dir=blocked / "external_references")

            self.assertEqual([], repository.list_references())
            self.assertIsNone(repository.get("qualquer"))
            self.assertIsNone(repository.select_best_for_track("interlagos"))

    def test_repository_writes_where_it_is_told_and_not_beside_the_code(self):
        # main.py points this at the runtime root; nothing may land under the
        # resource root, which is the read-only install directory when packaged.
        with tempfile.TemporaryDirectory() as tmp:
            resource_root = Path(tmp) / "resources"
            runtime_root = Path(tmp) / "runtime"
            resource_root.mkdir()
            runtime_root.mkdir()

            repository = ExternalReferenceRepository(
                resource_root,
                data_dir=runtime_root / "data" / "external_references",
            )
            reference = ExternalReferenceNormalizer().normalize_fastf1_telemetry(
                _telemetry_fixture(),
                year=2024,
                event="Brazil",
                session="Q",
                driver="VER",
            )
            repository.save(reference)

            written = list((runtime_root / "data" / "external_references").glob("*.json"))
            self.assertEqual(1, len(written))
            self.assertEqual([], list(resource_root.rglob("*.json")))

    def test_backend_keeps_written_data_out_of_the_install_directory(self):
        """The wiring that broke, checked the way the packaged app is started.

        In development both roots are the repository, so asserting on paths here
        proves nothing -- the bug only appears once the resource root is a
        read-only install and the runtime root is somewhere in the user profile.
        So this boots `main` in a subprocess with the two roots apart, exactly as
        `desktop_backend_runner` does, and asks it where it would write.
        """
        with tempfile.TemporaryDirectory() as tmp:
            resource_root = Path(tmp) / "resources"
            runtime_root = Path(tmp) / "runtime"
            resource_root.mkdir()
            runtime_root.mkdir()

            script = (
                "import json, main;"
                "print(json.dumps({"
                "'references': str(main.external_reference_repository.data_dir),"
                "'fastf1': str(main.fastf1_reference_provider.cache_dir),"
                "'trackCache': str(main.TRACK_CACHE_DIR),"
                "}))"
            )
            environment = dict(os.environ)
            environment["AT_BACKEND_RESOURCE_ROOT"] = str(resource_root)
            environment["AT_BACKEND_RUNTIME_ROOT"] = str(runtime_root)
            environment.pop("AT_BACKEND_REPO_ROOT", None)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=str(BACKEND_DIR),
                env=environment,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(0, result.returncode, msg=result.stderr[-2000:])
            written = json.loads(result.stdout.strip().splitlines()[-1])

            for name, directory in written.items():
                self.assertTrue(
                    Path(directory).is_relative_to(runtime_root),
                    msg=f"{name} escreve fora do runtime root: {directory}",
                )
                self.assertFalse(
                    Path(directory).is_relative_to(resource_root),
                    msg=f"{name} escreve dentro da instalacao: {directory}",
                )

    def test_fastf1_provider_fails_safely_without_session_data(self):
        class FakeCache:
            @staticmethod
            def enable_cache(_path):
                return None

        class FakeSession:
            def load(self, **_kwargs):
                raise RuntimeError("network unavailable and cache empty")

        class FakeFastF1:
            Cache = FakeCache

            @staticmethod
            def get_session(_year, _event, _session):
                return FakeSession()

        with tempfile.TemporaryDirectory() as tmp:
            provider = FastF1ReferenceProvider(Path(tmp), fastf1_module=FakeFastF1)
            with self.assertRaises(ExternalReferenceError) as ctx:
                provider.import_reference(year=2024, event="Brazil", session="Q", force=True)
            self.assertIn("FastF1 reference unavailable", str(ctx.exception))

    def test_assisted_analysis_keeps_internal_reference_and_adds_external_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = write_phase14_1_validation_recording(root)
            repository = ExternalReferenceRepository(root)
            external = ExternalReferenceNormalizer().normalize_fastf1_telemetry(
                pd.DataFrame(
                    {
                        "Time": list(range(24)),
                        "Distance": [index * 52.0 for index in range(24)],
                        "Speed": [250, 242, 220, 180, 145, 150, 190, 238] * 3,
                        "Throttle": [100, 80, 0, 0, 20, 60, 100, 100] * 3,
                        "Brake": [0, 20, 100, 80, 0, 0, 0, 0] * 3,
                        "X": list(range(24)),
                        "Y": [0.0] * 24,
                    }
                ),
                year=2024,
                event="Brazil",
                session="Q",
                driver="VER",
            )
            repository.save(external)
            service = _make_service(root, repository)

            without_external = service.analyze_lap(fixture.target_lap_id, force=True)
            with_external = service.analyze_lap(
                fixture.target_lap_id,
                include_external_reference=True,
                force=True,
            )

            self.assertIsNone(without_external["analysis"]["externalReference"])
            context = with_external["analysis"]["externalReference"]
            self.assertTrue(context["available"])
            self.assertEqual("EXTERNAL_F1", context["metadata"]["referenceType"])
            self.assertEqual("relative_lap_progress", context["normalization"]["basis"])
            self.assertGreaterEqual(len(context["macroCornerContext"]), 1)
            self.assertEqual(fixture.reference_lap_id, with_external["analysis"]["reference"]["lapId"])

    def test_external_reference_endpoint_rejects_unavailable_event(self):
        class FailingProvider:
            def import_reference(self, **_kwargs):
                raise ExternalReferenceError("FastF1 reference unavailable for 2024 Missing Q")

        previous_provider = backend_main.fastf1_reference_provider
        backend_main.fastf1_reference_provider = FailingProvider()
        try:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(
                    backend_main.import_external_fastf1_reference(
                        {"year": 2024, "event": "Missing", "session": "Q", "force": True}
                    )
                )
            self.assertEqual(400, ctx.exception.status_code)
            self.assertIn("FastF1 reference unavailable", str(ctx.exception.detail))
        finally:
            backend_main.fastf1_reference_provider = previous_provider


if __name__ == "__main__":
    unittest.main()
