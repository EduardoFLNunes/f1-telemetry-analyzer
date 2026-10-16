"""Aba "Coleta de dados" (pedido 28): o registro do que os modelos precisam e a conferencia da gravacao.

So le: nenhuma rota muda gravacao, store, modelo ou criterio. A unica escrita e
a configuracao do app (repositorio e referencia do coach) e a conferencia de
cada sessao, em `data/verificacoes/`, fora da pasta de gravacoes.

O estado do backend e da conexao com o jogo continua em `/api/runtime/status` e
`/api/recording/status`; a aba le essas rotas como estao.
"""
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

import main
from core.coleta import requisitos
from core.coleta.configuracao import ConfigError
from core.coleta.estado import carro_e_pista, espaco_em_disco, estado_do_coach
from core.coleta.oficial import contagem_oficial
from core.coleta.origem_app import app_identity
from core.coleta.anotacao import ARQUIVO as ANOTACOES, AnotacaoRecusada, anotar, ler_anotacoes
from core.coleta.rodada_coach import RodadaDoCoach

router = APIRouter(prefix="/api/coleta")


@router.get("/requisitos")
async def get_requisitos():
    return requisitos.registro_api()


def _antes() -> Dict[str, Any]:
    recording = main.recording_runtime.status().to_api() if main.recording_runtime else {}
    pasta = main.recording_config_from_env(main.RUNTIME_ROOT).output_root
    return {
        "app": app_identity(main.BACKEND_DIR.parent),
        "backend": {"servico": main.BACKEND_SERVICE_NAME, "versao": main.BACKEND_PHASE_VERSION,
                    "pastaDeDados": str(main.RUNTIME_ROOT), "pastaDeRecursos": str(main.RESOURCE_ROOT)},
        "gravacao": {**espaco_em_disco(pasta), "gravando": bool(recording.get("recording")),
                     "sessao": recording.get("sessionId")},
        "jogo": {
            "fonte": main.source_manager.get_active_source_name(),
            "captura": main.capture_gate_status(),
            **carro_e_pista(main.source_manager.current_car_model(), main.current_recording_track()),
        },
        "coach": estado_do_coach(main.assisted_analysis_service, main.app_config),
        "configuracao": main.app_config.to_api(),
        "conferencia": {
            "geometria": (lambda g: g.to_api() if g else None)(main.coleta_conferencia.geometria()),
            "pastaDasVerificacoes": str(main.coleta_conferencia.pasta),
            "pastasDeGravacao": [{"pasta": str(p), "origem": o} for p, o in main.coleta_conferencia.pastas_de_gravacao()],
        },
    }


@router.get("/antes")
async def get_antes():
    return await asyncio.to_thread(_antes)


@router.get("/ao-vivo")
async def get_ao_vivo():
    extras = {"carModel": main.source_manager.current_car_model(), "track": main.current_recording_track()}
    recording = main.recording_runtime.status().to_api() if main.recording_runtime else {}
    estado = await asyncio.to_thread(main.coleta_monitor.estado, extras)
    estado["gravando"] = bool(recording.get("recording"))
    estado["sessao"] = recording.get("sessionId")
    estado["gravador"] = {
        "amostrasEscritas": recording.get("playerSamplesWritten"),
        "descartadas": recording.get("playerSamplesDropped"),
        "fila": recording.get("queueSize"),
        "taxaDaUltimaVoltaHz": recording.get("lastPersistedLapEffectiveHz"),
    }
    return estado


@router.get("/configuracao")
async def get_configuracao():
    return main.app_config.to_api()


@router.put("/configuracao")
async def put_configuracao(payload: Dict[str, Any] = Body(...)):
    try:
        main.app_config.save(payload or {})
    except ConfigError as error:
        raise HTTPException(status_code=400, detail=str(error))
    main.reload_coach()
    return {"configuracao": main.app_config.to_api(),
            "coach": await asyncio.to_thread(estado_do_coach, main.assisted_analysis_service, main.app_config)}


@router.get("/sessao-atual")
async def get_sessao_atual():
    resultado = await asyncio.to_thread(main.coleta_conferencia.sessao_atual)
    return {"resultado": resultado}


@router.get("/verificacoes")
async def list_verificacoes():
    return {"verificacoes": await asyncio.to_thread(main.coleta_conferencia.listar),
            "pasta": str(main.coleta_conferencia.pasta)}


@router.get("/verificacoes/{session_id}")
async def get_verificacao(session_id: str):
    return await asyncio.to_thread(main.coleta_conferencia.estado, session_id)


@router.post("/verificacoes/{session_id}")
async def post_verificacao(session_id: str):
    resultado = await asyncio.to_thread(main.coleta_conferencia.solicitar, session_id)
    if resultado.get("estado") == "nao_encontrada":
        raise HTTPException(status_code=404, detail=f"Sessão {session_id} não encontrada nas pastas de gravação.")
    return resultado


@router.get("/m1/oficial")
async def get_m1_oficial():
    return await asyncio.to_thread(contagem_oficial, main.app_config.coach_root())


# ---------------------------------------------------------------- pedido 32 ---
# O botao do coach e a anotacao "Todas as voltas foram minhas", na tela Sessoes.

_rodada: Optional[RodadaDoCoach] = None


def _gravando() -> bool:
    recording = main.recording_runtime.status().to_api() if main.recording_runtime else {}
    return bool(recording.get("recording"))


def rodada_do_coach() -> RodadaDoCoach:
    global _rodada
    if _rodada is None:
        _rodada = RodadaDoCoach(
            repositorio=main.app_config.coach_root,
            gravando=_gravando,
            pasta_de_logs=main.RUNTIME_ROOT / "data" / "coach_rodadas",
            recarregar_coach=main.reload_coach,
        )
    return _rodada


@router.get("/coach/rodada")
async def get_rodada_do_coach():
    return await asyncio.to_thread(rodada_do_coach().estado)


@router.post("/coach/rodada")
async def post_rodada_do_coach():
    try:
        return await asyncio.to_thread(rodada_do_coach().iniciar)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error))


@router.get("/anotacoes")
async def get_anotacoes():
    repo = main.app_config.coach_root()
    if repo is None:
        return {"disponivel": False, "motivo": "o repositório não está configurado", "anotacoes": []}
    return {"disponivel": True, "arquivo": str(repo / ANOTACOES), "anotacoes": await asyncio.to_thread(ler_anotacoes, repo)}


@router.post("/anotacoes/{session_id}")
async def post_anotacao(session_id: str):
    repo = main.app_config.coach_root()
    if repo is None:
        raise HTTPException(status_code=409, detail="o repositório não está configurado (aba Coleta de dados)")
    conferencia = await asyncio.to_thread(main.coleta_conferencia.ler_salvo, session_id)
    try:
        return await asyncio.to_thread(anotar, repo, session_id, conferencia)
    except AnotacaoRecusada as error:
        raise HTTPException(status_code=409, detail=str(error))
