"""A rota da linha de corrida nao trava o laco do servidor (pedido 40, Parte D.7).

O defeito (inventario da dashboard, secao 2.G): `/api/live/racing-line` e `async` e
chamava o calculo, sincrono, direto no laco. Com o mapa da depuracao aberto, ela e
pedida a cada 6 s e travava o servidor por 1 a 1,8 s (medido em
`docs/mapa_dashboard_e_coach.md`), o tempo em que o coletor nao le amostras.

Aqui o calculo e trocado por um que dorme 0,4 s, e um relogio no mesmo laco mede o
maior intervalo entre os seus tiques enquanto a rota responde.
"""
import asyncio
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402,F401  (os routers fazem `import main`)
from routers import live  # noqa: E402

CALCULO_S = 0.4


def calculo_lento(*args, **kwargs):
    time.sleep(CALCULO_S)
    return {"status": "success"}


class RotaDaLinhaDeCorridaTests(unittest.TestCase):
    def maior_intervalo_do_laco(self):
        async def cenario():
            tiques = []
            fim = asyncio.Event()

            async def relogio():
                while not fim.is_set():
                    tiques.append(time.perf_counter())
                    await asyncio.sleep(0.02)

            tarefa = asyncio.create_task(relogio())
            await asyncio.sleep(0.05)
            resposta = await live.get_live_racing_line(microSectors=50, includeVisualLine=True, includeComparison=True)
            await asyncio.sleep(0.05)
            fim.set()
            await tarefa
            return resposta, max(b - a for a, b in zip(tiques, tiques[1:]))

        with patch.object(live, "live_racing_line_payload", calculo_lento):
            return asyncio.run(cenario())

    def test_o_laco_continua_rodando_durante_o_calculo(self):
        resposta, intervalo = self.maior_intervalo_do_laco()
        self.assertEqual(resposta, {"status": "success"})
        self.assertLess(intervalo, CALCULO_S / 2, f"o laco ficou parado {intervalo:.2f} s")


if __name__ == "__main__":
    unittest.main()
