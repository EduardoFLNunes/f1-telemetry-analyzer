"""O radio do engenheiro (pedido 31, Parte B.4).

* `GET /api/radio/mensagens?desde=<id>&instancia=<inst>`: as mensagens entregues
  depois de `id`, para o app do jogo e a tela Ao vivo. Uma instancia diferente
  (o backend reiniciou) devolve todas.
* `GET /api/radio/audio/{id}`: o WAV da mensagem (vinheta e voz).
* `POST /api/radio/teste`: uma mensagem de teste, entregue na hora, so pela tela
  Sistema, para conferir o radio sem andar no jogo.
* `GET /api/radio/estado`: as janelas, a voz e o que esta esperando.
* `GET /api/radio/minimapa`: a pista simplificada, a volta de referencia e as curvas da
  ultima analise, para o minimapa do app do jogo (pedido 35, Parte E).
* `GET /api/live/volta`: a volta em andamento inteira (pedido 31, Parte D).
* `GET /api/live/volta/novos?versao=<v>&desde=<seq>`: so os pontos novos e a posicao
  do carro (pedido 35, Parte D); a volta inteira so numa volta nova.
"""
import asyncio
import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

import main

router = APIRouter(prefix="/api/radio")
router_ao_vivo = APIRouter(prefix="/api/live")


def _radio():
    if main.radio_do_engenheiro is None:
        raise HTTPException(status_code=503, detail="o rádio ainda não está pronto")
    return main.radio_do_engenheiro


@router.get("/mensagens")
async def get_mensagens(desde: int = 0, instancia: Optional[str] = None):
    return _radio().desde(desde, instancia)


@router.get("/audio/{id_}")
async def get_audio(id_: int):
    arquivo = _radio().arquivo_do_audio(id_)
    if arquivo is None or not arquivo.exists():
        raise HTTPException(status_code=404, detail="mensagem sem áudio")
    return FileResponse(str(arquivo), media_type="audio/wav", filename=f"radio_{id_}.wav")


@router.post("/teste")
async def post_teste():
    return await asyncio.to_thread(_radio().teste)


@router.get("/estado")
async def get_estado():
    return await asyncio.to_thread(_radio().estado)


def _minimapa():
    from core.radio import minimapa

    radio = _radio()
    with radio._lock:
        radio._pista()
        geometria = radio._geometria
    if geometria is None:
        return {"disponivel": False, "motivo": "sem a geometria oficial no repositório configurado"}
    ref = main._referencia_do_radio()
    volta = main._volta_de_referencia_do_radio()
    return minimapa.montar(geometria.track, geometria.segmentos, volta, ref.get("tipo"), radio.ultima_analise(),
                           minimapa.linha_do_jogo_m(main.app_config.coach_root()))


@router.get("/minimapa")
async def get_minimapa():
    """Pedido 35, Parte E: o que o minimapa do jogo baixa uma vez (e de novo quando a `versao` muda)."""
    return _json(await asyncio.to_thread(_minimapa))


def _json(dado: Any) -> Response:
    """Pedido 35: direto pelo `json`, sem o `jsonable_encoder` do FastAPI. Numa volta inteira
    (5 linhas de 2.167 pontos) ele custava ~10 ms de processador por resposta; assim, ~2 ms."""
    return Response(content=json.dumps(dado, ensure_ascii=False, separators=(",", ":")),
                    media_type="application/json")


@router_ao_vivo.get("/volta")
async def get_volta_ao_vivo():
    """A volta em andamento na grade oficial (pedido 31, Parte D), para o fantasma da tela Ao vivo."""
    if main.volta_ao_vivo is None:
        return {"disponivel": False, "motivo": "a volta ao vivo ainda não está pronta"}
    return _json(main.volta_ao_vivo.estado())


@router_ao_vivo.get("/volta/novos")
async def get_volta_novos(versao: Optional[int] = None, desde: Optional[int] = None):
    """Pedido 35, Parte D: so os pontos gravados depois de `desde` e a posicao do carro."""
    if main.volta_ao_vivo is None:
        return {"disponivel": False, "motivo": "a volta ao vivo ainda não está pronta"}
    return _json(main.volta_ao_vivo.novos(versao, desde))
