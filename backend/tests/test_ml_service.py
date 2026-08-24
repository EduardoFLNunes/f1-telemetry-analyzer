"""Teste ponta a ponta da integracao que ainda nao existe.

O subsistema roda offline e o backend nao o importa. `ml/service.py` e a
fronteira que uma integracao usaria, e este arquivo exercita esse caminho
inteiro -- telemetria crua no formato que o runtime grava, ate a saida que um
painel mostraria.

Dois niveis:

* **contrato** (sempre roda): monta um servico com uma referencia sintetica e
  verifica o caminho completo sobre uma volta fabricada. Nao depende de nada em
  `data/ml/`, entao vale em qualquer maquina.
* **artefatos reais** (roda se existirem): repete contra o tracado otimizado e
  o envelope de verdade. E pulado com mensagem quando `data/ml/` esta vazio,
  porque um teste que so passa na maquina de quem tem 11 GB nao e um teste.
"""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml import config
from ml.service import LapAnalysis, RacingLineService

ARTIFACTS = config.artifacts_root()
HAS_ARTIFACTS = (ARTIFACTS / "optimization" / "optimised_lateral.npy").exists() and (
    ARTIFACTS / "vehicle_envelope.json"
).exists()


def telemetry_from_lateral(service: RacingLineService, lateral, speed_kmh=200.0, hz=50.0):
    """Fabrica amostras no formato do `player.jsonl` para uma trajetoria dada.

    E o formato que o runtime grava de verdade, incluindo o aninhamento em
    `carPhysics.controls` -- se o servico deixar de achar os pedais ali, este
    teste quebra, que e o ponto.
    """
    track = service.track
    speed = speed_kmh / 3.6
    duration = track.length / speed
    count = int(duration * hz)
    elapsed = np.arange(count) / hz
    distance = np.mod(elapsed * speed, track.length)
    index = track.index_of(distance)
    world = track.to_world(distance, np.asarray(lateral, dtype=float)[index])

    samples = []
    for position in range(count):
        samples.append(
            {
                "type": "player",
                "timestamp": (1_700_000_000.0 + elapsed[position]) * 1000.0,
                "track": "vhe_interlagos",
                "sample": {
                    "lap": 7,
                    "lap_time": float(elapsed[position]),
                    "world_x": float(world[position, 0]),
                    "world_y": 0.0,
                    "world_z": float(world[position, 1]),
                    "speedKmh": speed_kmh,
                    "heading": 0.0,
                    "carPhysics": {
                        "controls": {
                            "throttle": 0.8,
                            "brake": 0.0,
                            "steerAngle": 0.0,
                            "gear": 5.0,
                            "rpm": 8000.0,
                        },
                        "motion": {"accG": {"lateral": 0.5, "longitudinal": 0.0}},
                        "environment": {"offTrack": False, "tyresOut": 0},
                    },
                },
            }
        )
    return samples


class ServiceContractTest(unittest.TestCase):
    """O caminho completo, com referencia sintetica -- roda em qualquer lugar."""

    @classmethod
    def setUpClass(cls):
        # A referencia sintetica e a propria centerline; basta para exercitar o
        # contrato, e mantem o teste independente de `data/ml/`.
        service = RacingLineService.__new__(RacingLineService)
        from ml.track.corners import detect_corners
        from ml.track.geometry import load_geometry
        from ml.track.microsectors import build_microsectors

        service.root = ARTIFACTS
        service.track = load_geometry()
        service.sectors = build_microsectors(service.track)
        service.corners = detect_corners(service.track)
        service._reference_lateral = np.zeros(service.track.size)
        service._target_time = 90.0
        service._reference_frame = None
        service._envelope = None
        cls.service = service

    @unittest.skipUnless(
        (config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE).exists(),
        "cache de geometria da pista ausente",
    )
    def test_a_clean_lap_is_accepted_and_compared(self):
        service = self.service
        lateral = 2.0 * np.sin(service.track.s / 150.0)
        samples = telemetry_from_lateral(service, lateral)

        analysis = service.analyse(samples)
        self.assertTrue(analysis.accepted, analysis.reasons)
        self.assertEqual(len(analysis.sectors), service.sectors.count)
        self.assertEqual(len(analysis.corners), len(service.corners))
        self.assertIsNotNone(analysis.delta_s)
        # A volta fabricada anda a 200 km/h constantes; a referencia foi
        # reescalada para 90 s. O delta tem de ser um numero finito e coerente.
        self.assertTrue(math.isfinite(analysis.delta_s))
        self.assertAlmostEqual(
            analysis.delta_s, analysis.lap_time_s - analysis.reference_time_s, places=6
        )

    @unittest.skipUnless(
        (config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE).exists(),
        "cache de geometria da pista ausente",
    )
    def test_the_api_payload_is_serialisable(self):
        import json

        lateral = np.zeros(self.service.track.size)
        analysis = self.service.analyse(telemetry_from_lateral(self.service, lateral))
        payload = analysis.to_api()
        json.dumps(payload)  # levanta se algo nao for serializavel
        self.assertIn("sectors", payload)
        self.assertIn("deltaSeconds", payload)

    @unittest.skipUnless(
        (config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE).exists(),
        "cache de geometria da pista ausente",
    )
    def test_a_lap_without_pedals_is_refused_with_a_reason(self):
        samples = telemetry_from_lateral(self.service, np.zeros(self.service.track.size))
        for sample in samples:
            sample["sample"].pop("carPhysics")
        analysis = self.service.analyse(samples)
        self.assertFalse(analysis.accepted)
        self.assertTrue(any("canais ausentes" in reason for reason in analysis.reasons))

    def test_no_samples_is_refused_not_crashed(self):
        analysis = self.service.analyse([])
        self.assertFalse(analysis.accepted)
        self.assertTrue(analysis.reasons)


@unittest.skipUnless(HAS_ARTIFACTS, "artefatos de data/ml ausentes; rode o pipeline antes")
class ServiceAgainstRealArtefactsTest(unittest.TestCase):
    """O mesmo caminho contra o tracado otimizado de verdade."""

    @classmethod
    def setUpClass(cls):
        cls.service = RacingLineService()

    def test_the_service_reports_itself_ready(self):
        self.assertTrue(self.service.ready, self.service.missing())

    def test_a_real_recorded_lap_flows_through(self):
        from ml.data.lap_store import load_store

        store = load_store()
        lap = store.lap(store.laps.iloc[0]["lap_id"])
        analysis = self.service.analyse(
            telemetry_from_lateral(self.service, lap["lateral"].to_numpy(dtype=float))
        )
        self.assertTrue(analysis.accepted, analysis.reasons)
        self.assertEqual(len(analysis.sectors), 60)
        deltas = [sector["deltaSeconds"] for sector in analysis.sectors]
        self.assertAlmostEqual(sum(deltas), analysis.delta_s, places=3)


if __name__ == "__main__":
    unittest.main()
