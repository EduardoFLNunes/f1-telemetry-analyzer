"""O gravador abre uma sessao nova quando o contador de voltas do jogo volta (pedido 40, Parte D.1).

O defeito (pedido 29, achado 1): em `2026-10-04_02-24-04`, a sessao recomecou e o
contador de voltas foi de 14 para 1 um quadro *antes* de o relogio da volta zerar.
`_should_rotate` exigia as duas coisas no mesmo quadro, nunca as via juntas, e a
segunda passagem continuou no mesmo arquivo: a "volta 5" do gravador ficou com uma
passagem de 85,107 s e outra, 46 min depois, de 89,388 s.

O formato do arquivo nao muda: o corte e a sessao nova que o gravador ja abria
(pasta nova), so que agora ela abre.
"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from core.recording.recording_models import RecordingConfig
from core.recording.recording_runtime import RecordingRuntime
from core.telemetry_events import TelemetryEventBus

GRAVACAO_DE_04_10 = (
    Path(__file__).resolve().parents[2]
    / "data" / "recordings" / "2026-10-04_02-24-04_vhe_interlagos" / "player.jsonl"
)
# O reinicio esta na linha 125.041 do arquivo (contador 14 -> 1).
LINHA_DO_REINICIO = 125_041


def quadro(volta, relogio):
    return {
        "lap_number": volta,
        "sessionTime": relogio,
        "trackName": "vhe_interlagos",
        "speed": 50.0,
        "timestamp": relogio,
    }


class GravadorCortaReinicioTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.raiz = Path(temp.name)
        config = RecordingConfig(
            output_root=self.raiz, enabled=True, auto_start=True, player_record_hz=60.0, source_sample_hz=60.0
        )
        self.runtime = RecordingRuntime(
            config=config,
            track_provider=lambda: "vhe_interlagos",
            metadata_provider=lambda: {},
            bus=TelemetryEventBus(),
            capture_gate=lambda: {"allowed": True, "reason": None},
        )
        self.addCleanup(self.runtime.stop)
        self.runtime.start()

    def tocar(self, quadros):
        for q in quadros:
            asyncio.run(self.runtime.on_player_frame(q))

    def sessoes(self):
        return sorted(p.name for p in self.raiz.iterdir() if p.is_dir())

    def test_contador_volta_antes_do_relogio_abre_sessao_nova(self):
        # Como em 04/10: o contador cai com o relogio ainda correndo; o relogio zera no quadro seguinte.
        self.tocar([quadro(14, 264.678), quadro(14, 264.699), quadro(1, 264.717), quadro(1, 264.717), quadro(1, 0.468)])
        self.assertEqual(len(self.sessoes()), 2)

    def test_contador_e_relogio_juntos_abrem_sessao_nova(self):
        self.tocar([quadro(6, 80.0), quadro(6, 80.02), quadro(1, 0.01)])
        self.assertEqual(len(self.sessoes()), 2)

    def test_contador_que_cai_uma_volta_tambem_corta(self):
        # 6 -> 5: a regra antiga pedia uma queda de pelo menos 2 voltas.
        self.tocar([quadro(6, 30.0), quadro(5, 0.2)])
        self.assertEqual(len(self.sessoes()), 2)

    def test_voltas_normais_ficam_numa_sessao(self):
        # A volta nova: o relogio zera e o contador sobe um quadro depois (o atraso do jogo).
        self.tocar([quadro(1, 89.0), quadro(1, 0.006), quadro(2, 0.018), quadro(2, 50.0), quadro(2, 89.1), quadro(3, 0.01)])
        self.assertEqual(len(self.sessoes()), 1)

    @unittest.skipUnless(GRAVACAO_DE_04_10.exists(), "a gravacao de 04/10 so existe na maquina do Eduardo")
    def test_gravacao_de_04_10(self):
        quadros = []
        with GRAVACAO_DE_04_10.open("r", encoding="utf-8") as arquivo:
            for numero, linha in enumerate(arquivo, start=1):
                if numero < LINHA_DO_REINICIO - 40:
                    continue
                if numero > LINHA_DO_REINICIO + 40:
                    break
                envelope = json.loads(linha)
                amostra = envelope["sample"]
                quadros.append(quadro(amostra["lap_number"], envelope["sessionTime"]))
        self.assertEqual([q["lap_number"] for q in quadros[38:41]], [14, 14, 1], "o trecho do reinicio mudou de lugar")
        self.tocar(quadros)
        sessoes = self.sessoes()
        self.assertEqual(len(sessoes), 2)
        self.runtime.stop_recording()
        voltas = []
        for sessao in sessoes:
            with (self.raiz / sessao / "player.jsonl").open(encoding="utf-8") as arquivo:
                voltas.append({json.loads(l)["sample"]["lap_number"] for l in arquivo if l.strip()})
        self.assertEqual(voltas, [{14}, {1}])


if __name__ == "__main__":
    unittest.main()
