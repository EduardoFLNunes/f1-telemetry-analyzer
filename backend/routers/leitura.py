"""Rotas de leitura das telas Sessoes, Volta e Evolucao (pedido 30).

So leem arquivos que ja existem na pasta do repositorio configurada na Coleta de
dados (`main.app_config.coach_root()`); nenhuma calcula um numero novo. O que
cada uma le esta em `core/leitura/arquivos.py`.
"""
import asyncio

from fastapi import APIRouter

import main
from core.leitura import arquivos

router = APIRouter()
leitor_do_store = arquivos.LeitorDoStore()


def _raiz():
    return main.app_config.coach_root()


@router.get("/api/evolucao/resumo")
async def get_evolucao_resumo():
    return await asyncio.to_thread(arquivos.ler_resumo, _raiz())


@router.get("/api/evolucao/sessoes/{sessao}")
async def get_evolucao_sessao(sessao: str):
    return await asyncio.to_thread(arquivos.ler_sessao, _raiz(), sessao)


@router.get("/api/coach/referencias")
async def get_coach_referencias():
    return await asyncio.to_thread(arquivos.ler_referencias, _raiz())


@router.get("/api/store/voltas/{lap_id}")
async def get_store_volta(lap_id: str):
    return await asyncio.to_thread(leitor_do_store.ler_volta, _raiz(), lap_id)


@router.get("/api/geometria/oficial")
async def get_geometria_oficial():
    return await asyncio.to_thread(arquivos.ler_geometria, _raiz())
