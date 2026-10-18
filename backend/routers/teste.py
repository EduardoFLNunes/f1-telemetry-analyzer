"""Rotas so de teste (pedido 35, Parte D.1): tocar uma gravacao no caminho ao vivo, sem o jogo.

Respondem 404 sem `AT_TESTE_REPRODUTOR=1` (`core/teste/reprodutor.py`).
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

from core.teste import reprodutor as rep
from core.telemetry.telemetry_models import TelemetrySample

router = APIRouter(prefix="/api/teste")
_reprodutor: Optional[rep.Reprodutor] = None


def _exigir() -> None:
    if not rep.ligado():
        raise HTTPException(status_code=404, detail="so de teste: ligue com AT_TESTE_REPRODUTOR=1")


def _novo(loop: asyncio.AbstractEventLoop) -> rep.Reprodutor:
    import main

    def processar(amostra: Dict[str, Any], pista: Optional[str]) -> None:
        # O mesmo que o laco do jogo faz com uma amostra (core/live/telemetry_runtime.py). A amostra
        # gravada ja e o quadro processado: `x`/`z` estao na convencao do mapa (z com o sinal trocado) e
        # `speed` em m/s. O leitor do jogo entrega a posicao do mundo e a velocidade em km/h; aqui tambem.
        dados = dict(amostra)
        mundo = amostra.get("worldPosition")
        if isinstance(mundo, (list, tuple)) and len(mundo) == 3:
            dados["worldPositionX"], dados["worldPositionY"], dados["worldPositionZ"] = (float(v) for v in mundo)
        elif amostra.get("world_x") is not None and amostra.get("world_z") is not None:
            dados["worldPositionX"], dados["worldPositionZ"] = float(amostra["world_x"]), float(amostra["world_z"])
            dados["worldPositionY"] = float(amostra.get("world_y") or 0.0)
        if amostra.get("speedKmh") is not None:
            dados["speed"] = float(amostra["speedKmh"])
        sample = TelemetrySample.from_dict(dados)
        main.player_reliability.observe(sample)
        main.telemetry_buffer.add_sample(sample)
        frame = main.runtime_state.update_car(sample)
        if frame:
            if pista:
                frame["track"] = pista      # sem o jogo, o quadro nao traz a pista
            main.event_bus.schedule("processed_frame", frame, loop)

    return rep.Reprodutor(processar)


def _calar_a_fonte_do_backend() -> None:
    """Sem o jogo, o backend isolado le a fonte simulada (mock): os quadros dela se misturariam aos da
    gravacao no barramento. O laco de leitura para enquanto a gravacao toca e volta no `parar`."""
    import main

    if main.telemetry_runtime is not None:
        main.telemetry_runtime.stop()
        main.telemetry_runtime = None


def _religar_a_fonte_do_backend(loop: asyncio.AbstractEventLoop) -> None:
    import main

    if main.telemetry_runtime is None:
        main.telemetry_runtime = main.build_telemetry_runtime()
        main.telemetry_runtime.start(loop)


@router.post("/reproduzir")
async def reproduzir(corpo: Dict[str, Any] = Body(...)):
    _exigir()
    global _reprodutor
    if _reprodutor is None:
        _reprodutor = _novo(asyncio.get_running_loop())
    _calar_a_fonte_do_backend()
    return _reprodutor.tocar(Path(str(corpo.get("arquivo"))), int(corpo.get("desdeVolta") or 0),
                             int(corpo["ateVolta"]) if corpo.get("ateVolta") is not None else None,
                             float(corpo.get("velocidade") or 1.0), float(corpo.get("desdeTempoS") or 0.0))


@router.post("/parar")
async def parar():
    _exigir()
    estado = _reprodutor.parar() if _reprodutor is not None else {"tocando": False}
    _religar_a_fonte_do_backend(asyncio.get_running_loop())
    return estado


@router.get("/estado")
async def estado():
    _exigir()
    return _reprodutor.estado if _reprodutor is not None else {"tocando": False}
