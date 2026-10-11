"""Pedido 28: a aba "Coleta de dados", sem o jogo e sem as gravacoes reais.

* a configuracao do app: o repositorio e a referencia do coach, e quem vale;
* o coach lendo o modelo e a geometria do repositorio configurado;
* a versao e o commit do app no `metadata.json`;
* o estado de cada canal ao vivo: ok, ausente, parado, fora da faixa e taxa baixa;
* a conferencia da sessao: o corte em voltas e o de `iter_laps`, o veredito da
  volta e o dos portoes, e o da sessao segue a regra da M1;
* o portao do box copiado e o do detector;
* a contagem oficial le o store v2 pelos nomes do `ml`.
"""

from __future__ import annotations

import dataclasses
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.assisted_analysis.official_geometry import geometry_path  # noqa: E402
from core.assisted_analysis.reference_model import build_reference_model, model_path  # noqa: E402
from core.assisted_analysis.service import AssistedAnalysisService  # noqa: E402
from core.coleta import ao_vivo, conferencia, oficial, origem_app  # noqa: E402
from core.coleta.ao_vivo import MonitorAoVivo  # noqa: E402
from core.coleta.configuracao import COACH_OFF, AppConfig, ConfigError  # noqa: E402
from core.coleta.requisitos import COLUNAS_M1  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402
from ml.export.geometry import official_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from tests.test_ml_pipeline import circular_track  # noqa: E402

RADIUS = 200.0
SPEED_MS = 20.0               # 72 km/h: uma volta de 62,8 s no circulo de 200 m
HZ = 50.0


# --------------------------------------------------------------- amostras ---

def envelope(t, theta, lap, lap_time, *, ai=False, yaw=True, local=True, off_track=False, brake_temp=True):
    x, z = RADIUS * math.cos(theta), RADIUS * math.sin(theta)
    wobble = 0.01 * math.sin(7.0 * t)
    physics = {
        "motion": {
            "speedKmh": SPEED_MS * 3.6 + 10 * wobble,
            "accG": {"lateral": 0.2 + wobble, "longitudinal": wobble, "vertical": 0.01 + wobble},
            "localVelocity": ({"x": 0.1 + wobble, "y": 0.0, "z": SPEED_MS + wobble} if local
                              else {"x": None, "y": None, "z": None}),
            "localAngularVelocity": ({"x": 0.0, "y": SPEED_MS / RADIUS + wobble, "z": 0.0} if yaw
                                     else {"x": None, "y": None, "z": None}),
        },
        "controls": {"throttle": 0.5, "brake": 0.0, "clutch": 1.0, "steerAngle": 0.1 + wobble,
                     "gear": 4.0, "rpm": 6000.0 + 100 * wobble, "isAIControlled": ai},
        "tyres": {"tyreCoreTemperature": [70.0 + wobble] * 4, "tyrePressure": [18.0 + wobble] * 4,
                  "tyreWear": [99.9] * 4, "wheelSlip": [0.05 + wobble] * 4, "wheelLoad": [2000.0 + wobble] * 4,
                  "estimatedGripIndex": [0.9] * 4, "tyreTempInner": [80.0 + wobble] * 4,
                  "tyreTempMiddle": [78.0 + wobble] * 4, "tyreTempOuter": [76.0 + wobble] * 4},
        "brakes": {"brakeTemp": [300.0 + wobble] * 4 if brake_temp else [None] * 4, "brakeBias": 0.55},
        "suspension": {"suspensionTravel": [0.04 + wobble / 10] * 4},
        "carState": {"fuel": 30.0 - t / 1000.0},
        "environment": {"tyresOut": 3 if off_track else 0, "offTrack": off_track},
    }
    sample = {
        "world_x": x, "world_y": 0.0, "world_z": z, "worldPosition": [x, 0.0, z],
        "speedKmh": SPEED_MS * 3.6 + 10 * wobble, "lap": lap, "lap_number": lap, "lap_time": lap_time,
        "sessionTime": t, "timestamp": 1.79e12 + t * 1000.0, "distanceAlongTrack": (theta % (2 * math.pi)) * RADIUS,
        "throttle": 0.5, "brake": 0.0, "steering": 0.1 + wobble, "gear": 4, "rpm": 6000.0,
        "carPhysics": physics,
    }
    return {"type": "player", "timestamp": sample["timestamp"], "track": "vhe_interlagos", "sessionTime": t,
            "sample": sample}


def drive(laps: float, **kwargs):
    """Envelopes de `laps` voltas, comecando na linha; `kwargs_por_volta` muda uma volta."""
    per_lap = kwargs.pop("per_lap", {})
    lap_seconds = 2 * math.pi * RADIUS / SPEED_MS
    out = []
    for i in range(int(laps * lap_seconds * HZ)):
        t = i / HZ
        lap = int(t // lap_seconds)
        options = {**kwargs, **per_lap.get(lap, {})}
        out.append(envelope(t, SPEED_MS * t / RADIUS, lap, t - lap * lap_seconds, **options))
    return out


def write_session(root: Path, envelopes, session_id="2026-10-11_10-00-00_vhe_interlagos", car="rss_formula_rss_3_v6_2026"):
    directory = root / session_id
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(json.dumps({
        "sessionId": session_id, "track": "vhe_interlagos",
        "metadata": {"carModel": car, "appVersion": "0.3.0-coleta-modelos", "appCommit": "abc"},
    }), encoding="utf-8")
    with (directory / "player.jsonl").open("w", encoding="utf-8") as handle:
        for item in envelopes:
            handle.write(json.dumps(item, separators=(",", ":")) + "\n")
    return directory


def geometria():
    track = circular_track()
    return conferencia.Geometria(track, build_microsectors(track), Path("circulo.json"), "teste")


# ---------------------------------------------------------- configuracao ---

class AppConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {}, clear=False)
        self.env.start()
        os.environ.pop("AT_COACH_REFERENCE", None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_defaults_come_from_the_repository_electron_passes(self):
        config = AppConfig(self.root, default_repository=self.root / "repo")
        self.assertEqual(config.repository(), (self.root / "repo", "AT_REPO_PATH"))
        self.assertEqual(config.reference(), ("volta_ia", "padrao"))
        self.assertEqual(config.coach_reference(), "volta_ia")

    def test_the_tab_saves_the_repository_and_the_reference(self):
        repo = self.root / "outro"
        repo.mkdir()
        config = AppConfig(self.root, default_repository=self.root / "repo")
        config.save({"repositorio": str(repo), "referenciaCoach": "minha_melhor"})
        again = AppConfig(self.root, default_repository=self.root / "repo")
        self.assertEqual(again.repository(), (repo.resolve(), "configuracao"))
        self.assertEqual(again.reference(), ("minha_melhor", "configuracao"))
        self.assertTrue((self.root / "data" / "configuracao" / "app.json").exists())

    def test_coach_off_means_no_reference(self):
        config = AppConfig(self.root)
        config.save({"referenciaCoach": COACH_OFF})
        self.assertIsNone(config.coach_reference())

    def test_invalid_values_are_refused(self):
        config = AppConfig(self.root)
        with self.assertRaises(ConfigError):
            config.save({"referenciaCoach": "qualquer"})
        with self.assertRaises(ConfigError):
            config.save({"repositorio": str(self.root / "nao-existe")})

    def test_the_variable_still_wins_in_the_development_app(self):
        config = AppConfig(self.root)
        config.save({"referenciaCoach": "minha_melhor"})
        os.environ["AT_COACH_REFERENCE"] = "volta_ia"
        self.assertEqual(config.reference(), ("volta_ia", "AT_COACH_REFERENCE"))
        self.assertTrue(config.to_api()["referenciaTravadaPelaVariavel"])

    def test_empty_value_goes_back_to_the_default(self):
        repo = self.root / "outro"
        repo.mkdir()
        config = AppConfig(self.root, default_repository=self.root / "repo")
        config.save({"repositorio": str(repo)})
        config.save({"repositorio": ""})
        self.assertEqual(config.repository()[1], "AT_REPO_PATH")


class CoachFromTheConfiguredRepositoryTest(unittest.TestCase):
    """O coach le o modelo e a geometria do repositorio configurado, so lendo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.data = Path(self.tmp.name) / "dados"
        self.data.mkdir()
        track = dataclasses.replace(circular_track(), geometry_id="geo-1")
        geometry = official_geometry(track, build_microsectors(track), "pista")
        frame = pd.DataFrame({"x": track.x, "z": track.z, "elapsed_s": np.linspace(0, 60, track.size),
                              "speed_kmh": 75.0, "brake": 0.0, "throttle": 1.0})
        from core.assisted_analysis.official_geometry import OfficialGeometry

        model = build_reference_model([("ref", 60.0, 3420, frame)], track="pista",
                                      geometry=OfficialGeometry.from_dict(geometry))
        path = model_path(self.repo, "pista")
        path.parent.mkdir(parents=True)
        model.save(path)
        geometry_path(self.repo, "pista").write_text(json.dumps(geometry), encoding="utf-8")
        self.before = sorted((p.name, p.stat().st_mtime) for p in path.parent.iterdir())
        self.config = AppConfig(self.data, default_repository=self.repo)
        self.service = AssistedAnalysisService.__new__(AssistedAnalysisService)
        self.service.coach_settings = self.config
        self.service.runtime_root = self.data
        self.service.repo_root = self.data
        os.environ.pop("AT_COACH_REFERENCE", None)

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_model_and_the_geometry_come_from_the_repository(self):
        self.assertIsNotNone(self.service._reference_model("pista"))
        self.assertEqual(self.service._official_geometry("pista").geometry_id, "geo-1")
        # Nada foi copiado para a pasta de dados, nem mudado no repositorio.
        self.assertFalse((self.data / "data" / "reference_models").exists())
        after = sorted((p.name, p.stat().st_mtime) for p in model_path(self.repo, "pista").parent.iterdir())
        self.assertEqual(after, self.before)

    def test_coach_off_and_no_repository_are_silent(self):
        self.config.save({"referenciaCoach": COACH_OFF})
        self.service.reload_coach()
        self.assertIsNone(self.service._reference_model("pista"))
        config = AppConfig(self.data / "outro")
        self.service.coach_settings = config
        self.service.reload_coach()
        self.assertIsNone(self.service._reference_model("pista"))
        self.assertIsNone(self.service._official_geometry("pista"))

    def test_the_tab_says_why_the_coach_is_silent(self):
        from core.coleta.estado import estado_do_coach

        ok = estado_do_coach(self.service, self.config, "pista")
        self.assertTrue(ok["ativo"], ok["motivoCalado"])
        self.assertTrue(ok["geometryIdBate"])
        geometry = json.loads(geometry_path(self.repo, "pista").read_text(encoding="utf-8"))
        geometry["geometry_id"] = "geo-2"
        geometry_path(self.repo, "pista").write_text(json.dumps(geometry), encoding="utf-8")
        self.service.reload_coach()
        calado = estado_do_coach(self.service, self.config, "pista")
        self.assertFalse(calado["ativo"])
        self.assertFalse(calado["geometryIdBate"])
        self.assertIn("geo-2", calado["motivoCalado"])

    def test_the_live_coach_asks_again_after_a_reset(self):
        from core.live.driving_coach import LiveDrivingCoach
        from tests.test_driving_coach import FakeBus

        calls = []
        coach = LiveDrivingCoach(FakeBus(), lambda track: calls.append(track) or object())
        coach._model_for("pista")
        coach._model_for("pista")
        coach.reset_model()
        coach._model_for("pista")
        self.assertEqual(len(calls), 2)


class AppIdentityTest(unittest.TestCase):
    def test_the_packaged_app_stamp_goes_to_the_metadata(self):
        env = {"AT_APP_VERSION": "0.3.0-coleta-modelos", "AT_APP_COMMIT": "a" * 40,
               "AT_APP_BUILD_DIRTY": "true", "AT_APP_PACKAGED": "true"}
        with mock.patch.dict(os.environ, env):
            identity = origem_app.app_identity(BACKEND.parent, refresh=True)
            fields = origem_app.metadata_fields(BACKEND.parent)
        origem_app.app_identity(BACKEND.parent, refresh=True)
        self.assertEqual(identity["fonte"], "build-info")
        self.assertEqual(fields, {"appVersion": "0.3.0-coleta-modelos", "appCommit": "a" * 40,
                                  "appCommitDirty": True, "appPackaged": True})

    def test_a_source_run_asks_git(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in ("AT_APP_VERSION", "AT_APP_COMMIT"):
                os.environ.pop(key, None)
            identity = origem_app.app_identity(BACKEND.parent, refresh=True)
        self.assertEqual(identity["fonte"], "git")
        self.assertFalse(identity["empacotado"])
        self.assertEqual(identity["versao"], json.loads((BACKEND.parent / "desktop" / "package.json")
                                                        .read_text(encoding="utf-8"))["version"])

    def test_the_recorder_metadata_keeps_the_old_fields(self):
        source = (BACKEND / "main.py").read_text(encoding="utf-8")
        self.assertIn('"carModel": source_manager.current_car_model()', source)
        self.assertIn("**origem_app.metadata_fields(BACKEND_DIR.parent)", source)


# ------------------------------------------------------------- ao vivo ---

class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def feed(monitor, clock, frames, hz=60.0):
    for frame in frames:
        clock.now += 1.0 / hz
        monitor.observar(frame)


class LiveChannelStateTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.monitor = MonitorAoVivo(gravando=lambda: True, relogio=self.clock)

    def frames(self, seconds=5.0, hz=60.0, **kwargs):
        frames = []
        for i in range(int(seconds * hz)):
            t = i / hz
            sample = envelope(t, SPEED_MS * t / RADIUS, 1, t, **kwargs)["sample"]
            frames.append(sample)
        return frames

    def item(self, state, item_id):
        return next(i for i in state["itens"] if i["id"] == item_id)

    def test_a_good_recording_is_ok(self):
        feed(self.monitor, self.clock, self.frames())
        state = self.monitor.estado({"carModel": "rss_formula_rss_3_v6_2026", "track": "vhe_interlagos"})
        bad = {i["id"]: i["estado"] for i in state["itens"] if i["estado"] != ao_vivo.OK}
        self.assertEqual(bad, {})
        self.assertAlmostEqual(self.item(state, "yaw_rate")["taxaHz"], 60.0, delta=0.5)
        self.assertIs(state["indicadorIA"], False)

    def test_missing(self):
        feed(self.monitor, self.clock, self.frames(yaw=False))
        state = self.monitor.estado()
        self.assertEqual(self.item(state, "yaw_rate")["estado"], ao_vivo.AUSENTE)
        self.assertEqual(self.item(state, "car_model")["estado"], ao_vivo.AUSENTE)
        self.assertEqual(next(g for g in state["grupos"] if g["id"] == "m1")["estado"], ao_vivo.AUSENTE)

    def test_stuck_with_the_car_moving(self):
        frames = self.frames()
        for frame in frames:
            frame["carPhysics"]["motion"]["localAngularVelocity"]["y"] = 0.1
            frame["carPhysics"]["controls"]["clutch"] = 0.0
        feed(self.monitor, self.clock, frames)
        state = self.monitor.estado()
        self.assertEqual(self.item(state, "yaw_rate")["estado"], ao_vivo.PARADO)
        # A embreagem em 0 com o carro andando e o defeito das gravacoes antigas.
        self.assertEqual(self.item(state, "clutch")["estado"], ao_vivo.PARADO)
        # A distribuicao dos freios e ajuste: constante e normal.
        self.assertEqual(self.item(state, "brake_bias")["estado"], ao_vivo.OK)

    def test_a_constant_clutch_at_one_is_not_stuck(self):
        feed(self.monitor, self.clock, self.frames())
        self.assertEqual(self.item(self.monitor.estado(), "clutch")["estado"], ao_vivo.OK)

    def test_stopped_car_is_not_stuck(self):
        frames = self.frames()
        for frame in frames:
            frame["speedKmh"] = 0.0
            frame["carPhysics"]["motion"]["localAngularVelocity"]["y"] = 0.0
        feed(self.monitor, self.clock, frames)
        self.assertEqual(self.item(self.monitor.estado(), "yaw_rate")["estado"], ao_vivo.OK)

    def test_out_of_range(self):
        frames = self.frames()
        for k, frame in enumerate(frames):
            frame["carPhysics"]["tyres"]["wheelLoad"][2] = 20000.0 + k
        feed(self.monitor, self.clock, frames)
        item = self.item(self.monitor.estado(), "wheel_load")
        self.assertEqual(item["estado"], ao_vivo.FORA_DA_FAIXA)
        self.assertEqual([c["estado"] for c in item["componentes"]], ["ok", "ok", "fora_da_faixa", "ok"])

    def test_low_rate(self):
        feed(self.monitor, self.clock, self.frames(hz=20.0), hz=20.0)
        state = self.monitor.estado()
        self.assertEqual(self.item(state, "speed")["estado"], ao_vivo.TAXA_BAIXA)
        self.assertAlmostEqual(self.item(state, "speed")["taxaHz"], 20.0, delta=0.5)

    def test_only_what_is_recorded_counts(self):
        monitor = MonitorAoVivo(gravando=lambda: False, relogio=self.clock)
        feed(monitor, self.clock, self.frames())
        state = monitor.estado()
        self.assertEqual(state["quadros"], 0)
        self.assertTrue(all(i["estado"] == ao_vivo.SEM_DADOS for i in state["itens"]))

    def test_the_window_forgets_old_frames(self):
        feed(self.monitor, self.clock, self.frames(yaw=False))
        feed(self.monitor, self.clock, self.frames())
        self.assertEqual(self.item(self.monitor.estado(), "yaw_rate")["estado"], ao_vivo.OK)


# --------------------------------------------------------- conferencia ---

class SessionCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.geo = geometria()

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, directory, chunk=None):
        session = conferencia.ConferenciaSessao(directory, self.geo)
        if chunk:
            while session.ler(limite_bytes=chunk):
                pass
        session.concluir()
        return session.to_api()

    def test_the_laps_are_the_ones_iter_laps_cuts(self):
        directory = write_session(self.root, drive(3.1))
        expected = [(lap.lap_id, lap.sample_count, lap.lap_number)
                    for lap in iter_laps(Session(directory.name, directory, "vhe_interlagos"))]
        for chunk in (None, 40_000):
            result = self.check(directory, chunk)
            got = [(v["lapId"], v["amostras"], v["voltaDoJogo"]) for v in result["voltas"]]
            self.assertEqual(got, expected, f"leitura em blocos de {chunk}")

    def test_reading_while_the_file_grows(self):
        envelopes = drive(2.1)
        directory = write_session(self.root, envelopes[:2000])
        session = conferencia.ConferenciaSessao(directory, self.geo)
        session.ler()
        with (directory / "player.jsonl").open("a", encoding="utf-8") as handle:
            text = "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in envelopes[2000:])
            handle.write(text[: len(text) // 2])
            handle.flush()
            session.ler()
            handle.write(text[len(text) // 2:])
        session.concluir()
        whole = self.check(write_session(self.root, envelopes, session_id="inteira"))
        self.assertEqual([(v["sequencia"], v["amostras"]) for v in session.to_api()["voltas"]],
                         [(v["sequencia"], v["amostras"]) for v in whole["voltas"]])

    def test_a_human_session_with_the_channels_counts(self):
        result = self.check(write_session(self.root, drive(3.1)))
        validas = [v for v in result["voltas"] if v["entraNoStore"]]
        self.assertEqual(len(validas), 3)
        self.assertTrue(all(v["tempo"].startswith("1:02,") for v in validas), [v["tempo"] for v in validas])
        verdict = result["veredito"]
        self.assertTrue(verdict["conta"], verdict["texto"])
        self.assertEqual(verdict["texto"], "Conta para a M1.")
        self.assertEqual(verdict["preenchimentoGrade"]["yaw_rate"], 1.0)

    def test_an_ai_lap_does_not_count(self):
        result = self.check(write_session(self.root, drive(3.1, per_lap={1: {"ai": True}})))
        verdict = result["veredito"]
        self.assertFalse(verdict["conta"])
        self.assertEqual(verdict["voltasComIA"], [1])
        self.assertIn("há volta com a IA no volante (#0001)", verdict["falta"])
        self.assertEqual(result["voltas"][1]["origem"], "ia")

    def test_without_the_yaw_rate_it_does_not_count(self):
        verdict = self.check(write_session(self.root, drive(3.1, yaw=False)))["veredito"]
        self.assertFalse(verdict["conta"])
        self.assertEqual(verdict["falta"], ["falta a guinada"])
        self.assertEqual(verdict["texto"], "Não conta para a M1: falta a guinada.")

    def test_old_recordings_miss_the_yaw_and_the_local_velocities(self):
        envelopes = drive(3.1, yaw=False, local=False)
        for item in envelopes:
            del item["sample"]["carPhysics"]["controls"]["isAIControlled"]
        verdict = self.check(write_session(self.root, envelopes))["veredito"]
        self.assertFalse(verdict["conta"])
        self.assertEqual(verdict["falta"], ["faltam a guinada e as velocidades no referencial do carro",
                                            "o indicador de IA não foi gravado"])

    def test_the_lap_verdict_is_the_gates_verdict(self):
        result = self.check(write_session(self.root, drive(3.1, per_lap={2: {"off_track": True}})))
        lap = result["voltas"][2]
        self.assertFalse(lap["valida"])
        self.assertTrue(any("fora de pista" in m for m in lap["motivos"]), lap["motivos"])
        last = result["voltas"][-1]
        self.assertTrue(any("curta demais" in m for m in last["motivos"]), last["motivos"])

    def test_the_fill_of_each_group_is_reported(self):
        result = self.check(write_session(self.root, drive(1.2, brake_temp=False)))
        lap = result["voltas"][0]
        self.assertEqual(lap["preenchimentoItens"]["brake_temp"], 0.0)
        self.assertEqual(lap["preenchimentoGrupos"]["m1"]["minimo"], 0.0)
        self.assertEqual(lap["preenchimentoGrupos"]["base"]["minimo"], 1.0)
        self.assertEqual(lap["preenchimentoItens"]["car_model"], 1.0)

    def test_the_result_is_written_outside_the_recordings(self):
        recordings = self.root / "data" / "recordings"
        directory = write_session(recordings, drive(1.2))
        service = conferencia.ServicoConferencia(self.root, recordings, repositorio=lambda: None,
                                                 estado_da_gravacao=lambda: {"recording": True, "directory": str(directory)})
        service.geometria = lambda: self.geo
        service.tick()
        service.estado_da_gravacao = lambda: {"recording": False, "directory": str(directory)}
        service.tick()
        saved = json.loads((self.root / "data" / "verificacoes" / f"{directory.name}.json").read_text(encoding="utf-8"))
        self.assertTrue(saved["final"])
        self.assertEqual([p.name for p in recordings.iterdir()], [directory.name])
        self.assertEqual(sorted(p.name for p in directory.iterdir()), ["metadata.json", "player.jsonl"])

    def test_ml_readers_do_not_see_the_checks_as_sessions(self):
        from ml.data.recordings import list_sessions

        recordings = self.root / "data" / "recordings"
        write_session(recordings, drive(0.2))
        conferencia.gravar({"sessao": "x"}, self.root / "data" / "verificacoes")
        self.assertEqual([s.session_id for s in list_sessions(recordings)], ["2026-10-11_10-00-00_vhe_interlagos"])

    def test_time_format(self):
        self.assertEqual(conferencia.formatar_tempo(84.828), "1:24,828")
        self.assertEqual(conferencia.formatar_tempo(5.0), "0:05,000")
        self.assertIsNone(conferencia.formatar_tempo(None))


class NewMetadataFieldsTest(unittest.TestCase):
    """C.4: com a versao e o commit no metadata.json, o inventario e o store v2 leem como antes."""

    def test_inventory_and_store_v2_still_read_the_session(self):
        from ml.data import store_v2
        from ml.data.inventory import read_session

        with tempfile.TemporaryDirectory() as tmp:
            directory = write_session(Path(tmp), drive(2.1))
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["metadata"]["appVersion"], "0.3.0-coleta-modelos")
            session = Session(directory.name, directory, "vhe_interlagos")
            track = circular_track()
            sectors = build_microsectors(track)
            rows = read_session(session, track, sectors)
            valid = [row["sequence"] for row in rows if row["valid"]]
            self.assertEqual(len(valid), 2)
            self.assertTrue(all(row["origem"] == "humano" for row in rows))
            material = store_v2.materialize_session(session, valid, track, sectors)
        self.assertEqual(material.car_model_recorded, "rss_formula_rss_3_v6_2026")
        self.assertEqual(sorted(material.laps), valid)
        self.assertIn("yaw_rate", material.laps[valid[0]]["channels"])


class PitGateCopyTest(unittest.TestCase):
    def test_the_copy_matches_the_detector(self):
        from ml.data.ai_detector import pit_lap

        track = circular_track()
        sectors = build_microsectors(track)
        rng = np.random.default_rng(28)
        for _ in range(40):
            grid = pd.DataFrame({"lateral": rng.normal(0, 8, track.size), "speed_kmh": rng.uniform(40, 250, track.size)})
            self.assertEqual(conferencia.pit_lap(grid, sectors), pit_lap(grid, sectors))


class OfficialCountTest(unittest.TestCase):
    def test_the_file_names_are_the_store_v2_ones(self):
        from ml.data import store_v2

        self.assertEqual(oficial.STORE_V2_FILENAME, store_v2.STORE_V2_FILENAME)
        self.assertEqual(oficial.STORE_V2_METADATA, store_v2.STORE_V2_METADATA)

    def test_count_from_a_synthetic_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            folder = repo / "data" / "ml"
            folder.mkdir(parents=True)
            grid = 10
            laps = [
                {"lap_id": "a#0001", "session_id": "a", "origem": "humano", "origem_fonte": "indicador"},
                {"lap_id": "a#0002", "session_id": "a", "origem": "humano", "origem_fonte": "indicador"},
                {"lap_id": "b#0001", "session_id": "b", "origem": "humano", "origem_fonte": "indicador"},
                {"lap_id": "b#0002", "session_id": "b", "origem": "ia", "origem_fonte": "indicador"},
                {"lap_id": "c#0001", "session_id": "c", "origem": "humano", "origem_fonte": "anotacao_sessao"},
            ]
            rows = []
            for lap in laps:
                for i in range(grid):
                    has = lap["session_id"] != "c"
                    rows.append({"lap_id": lap["lap_id"], "grid_index": i,
                                 **{c: (1.0 if has else np.nan) for c in COLUNAS_M1}})
            pd.DataFrame(rows).to_parquet(folder / oficial.STORE_V2_FILENAME)
            (folder / oficial.STORE_V2_METADATA).write_text(json.dumps({
                "grid_size": grid, "columns": list(COLUNAS_M1), "laps": laps, "construido_em": "x", "commit": "y"}),
                encoding="utf-8")
            result = oficial.contagem_oficial(repo)
        self.assertEqual(result["texto"], "1 de 5")
        self.assertEqual(result["sessoesQueContam"], ["a"])
        by = {s["sessao"]: s for s in result["sessoesComVoltasSuas"]}
        self.assertFalse(by["b"]["humana"])
        self.assertEqual(by["c"]["preenchimentoGrade"]["yaw_rate"], 0.0)

    def test_without_the_repository(self):
        self.assertFalse(oficial.contagem_oficial(None)["disponivel"])


if __name__ == "__main__":
    unittest.main()
