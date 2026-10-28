"""A rota das frases do coach acha a gravacao nas mesmas pastas que o `ml` le (pedido 40, Parte D.2).

O defeito (pedido 30, achado 2): `/api/analysis/coach/lap/{id}` so procurava a
gravacao em `data/recordings` do repositorio e da raiz do backend. Uma volta gravada
na pasta configurada (`TELEMETRY_RECORDING_DIR`) ou na do app instalado
(`%APPDATA%/Automobilista Telemetria/data/recordings`) dava 404.

Agora ela procura tambem nessas duas, com a regra de nome repetido do
`list_all_sessions`: a mesma sessao em duas pastas e um erro, porque nao da para saber
sozinho qual das copias vale.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.assisted_analysis.service import AssistedAnalysisService
from core.cache.track_cache import TrackCache
from core.live.runtime_state import RuntimeState
from core.telemetry.telemetry_buffer import TelemetryBuffer

SESSAO = "2026-10-27_20-00-00_vhe_interlagos"


def gravar_sessao(pasta: Path) -> None:
    sessao = pasta / SESSAO
    sessao.mkdir(parents=True)
    linhas = []
    for i in range(40):
        t = i * 0.5
        amostra = {
            "lap_number": 2, "lap": 2, "lap_time": t, "sessionTime": t, "speedKmh": 100.0, "speed": 27.8,
            "throttle": 1.0, "brake": 0.0, "steering": 0.0, "gear": 4, "rpm": 8000,
            "x": float(i), "y": 0.0, "z": 0.0, "world_x": float(i), "world_z": 0.0,
            "s": float(i * 14), "distanceAlongTrack": float(i * 14), "p": i / 40.0, "spline_t": i / 40.0,
        }
        linhas.append(json.dumps({"type": "player", "timestamp": 1_800_000_000_000 + t * 1000,
                                  "track": "vhe_interlagos", "sessionTime": t, "sample": amostra}))
    (sessao / "player.jsonl").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    (sessao / "metadata.json").write_text(json.dumps({"track": "vhe_interlagos"}), encoding="utf-8")


class RotaDoCoachAchaAGravacaoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        raiz = Path(temp.name)
        self.repo = raiz / "repo"
        self.runtime = raiz / "runtime"
        self.configurada = raiz / "configurada"
        self.appdata = raiz / "appdata"
        self.instalado = self.appdata / "Automobilista Telemetria" / "data" / "recordings"
        for pasta in (self.repo / "data" / "recordings", self.runtime, self.configurada, self.instalado):
            pasta.mkdir(parents=True, exist_ok=True)
        ambiente = patch.dict(os.environ, {"TELEMETRY_RECORDING_DIR": str(self.configurada), "APPDATA": str(self.appdata)})
        ambiente.start()
        self.addCleanup(ambiente.stop)

    def servico(self):
        return AssistedAnalysisService(
            self.repo, TelemetryBuffer(max_size=100), RuntimeState(), TrackCache(cache_dir=str(self.runtime / "cache")),
            runtime_root=self.runtime,
        )

    def carregar(self):
        return self.servico().loader.load_lap(f"rec__{SESSAO}__2")

    def test_acha_na_pasta_configurada(self):
        gravar_sessao(self.configurada)
        descritor, df = self.carregar()
        self.assertEqual(descritor.lap_number, 2)
        self.assertEqual(len(df), 40)

    def test_acha_na_pasta_do_app_instalado(self):
        gravar_sessao(self.instalado)
        descritor, df = self.carregar()
        self.assertEqual(len(df), 40)

    def test_continua_achando_no_repositorio(self):
        gravar_sessao(self.repo / "data" / "recordings")
        descritor, df = self.carregar()
        self.assertEqual(len(df), 40)

    def test_nome_repetido_em_duas_pastas_e_erro(self):
        gravar_sessao(self.configurada)
        gravar_sessao(self.instalado)
        with self.assertRaises(ValueError) as erro:
            self.carregar()
        self.assertIn("compare as duas", str(erro.exception))

    def test_sem_a_gravacao_continua_nao_achando(self):
        with self.assertRaises(FileNotFoundError):
            self.carregar()


if __name__ == "__main__":
    unittest.main()
