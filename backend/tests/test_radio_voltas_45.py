"""Pedido 45, Parte B: o numero da volta (um so) e o erro do WebSocket."""
import asyncio

import pytest

from core.live.volta_ao_vivo import VoltaAoVivo
from core.websocket_server import ConnectionManager


class _Bus:
    def schedule(self, *a, **k):
        pass


class _Lenta:
    """Um cliente de WebSocket que demora: dois envios ao mesmo tempo disputam a trava."""

    def __init__(self):
        self.enviados = 0

    async def send_text(self, _):
        await asyncio.sleep(0.01)
        self.enviados += 1


def test_a_trava_do_envio_nasce_no_laco_que_envia_e_nao_ao_importar():
    # No modulo, o gerente nasce fora de qualquer laco (o `manager` global); no Python 3.9 um
    # `asyncio.Lock()` criado ali guarda outro laco, e a disputa dava "attached to a different loop".
    gerente = ConnectionManager()
    gerente.active_connections.append(_Lenta())
    gerente.send_timeout_seconds = 2.0

    async def dois_envios():
        await asyncio.gather(gerente.broadcast({"type": "a"}), gerente.broadcast({"type": "b"}),
                             gerente.broadcast({"type": "c"}))

    asyncio.run(dois_envios())          # um laco novo, como o do uvicorn
    assert gerente.active_connections[0].enviados == 3
    asyncio.run(dois_envios())          # e outro: a trava acompanha o laco
    assert gerente.active_connections[0].enviados == 6


def _volta_ao_vivo(pos):
    return VoltaAoVivo(lambda: pos, lambda: 100)


def test_a_volta_fechada_tem_o_numero_de_antes_da_passagem():
    pos = {"s": 10.0, "comprimento": 100.0, "lateral": 0.0, "volta": 9, "tempoDaVolta": 1.0, "desdeALinha": True}
    v = _volta_ao_vivo(pos)
    for s in (10.0, 60.0, 99.0):
        pos["s"] = s
        v.on_frame({"speedKmh": 100.0})
    # o contador do jogo ja adiantou no quadro da passagem: a volta que fechou continua a 9
    pos.update(s=1.0, volta=10)
    v.on_frame({"speedKmh": 100.0})
    assert v.ultima_fechada()["volta"] == 9


def test_o_coach_numera_a_volta_pelo_contador_no_meio_dela():
    from core.live import driving_coach as dc

    coach = dc.LiveDrivingCoach(_Bus(), model_provider=lambda _: None)
    coach._last_progress = 0.2
    coach._numero_no_meio = None
    # antes do meio da volta, vale o contador do quadro
    assert coach._numero_da_volta({"lap_number": 9}) == 9
    coach._numero_no_meio = 9.0
    # depois do meio, o contador pode adiantar perto da linha: a volta continua a 9
    assert coach._numero_da_volta({"lap_number": 10}) == 9
    # uma volta nova na linha esquece o numero
    coach._start_lap(10.0, 0, 0.0, 0.0, at_line=True)
    assert coach._numero_no_meio is None
    assert coach._numero_da_volta({"lap_number": 10}) == 10


@pytest.mark.parametrize("progresso,esperado", [(0.1, None), (0.7, 5.0)])
def test_recomecar_fora_da_linha_guarda_o_numero_so_depois_do_meio(progresso, esperado):
    from core.live import driving_coach as dc

    coach = dc.LiveDrivingCoach(_Bus(), model_provider=lambda _: None)
    coach._start_lap(5.0, 3, 0.0, progresso)
    assert coach._numero_no_meio == esperado
