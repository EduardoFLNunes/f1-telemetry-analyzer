"""O log de acesso sem as rotas pedidas varias vezes por segundo (pedido 36, Parte B.3).

O uvicorn escreve uma linha por pedido no log de acesso (`uvicorn.access`). A tela Ao
vivo pede os pontos novos da volta cerca de 28 vezes por segundo, e o app do jogo e a
tela pedem as mensagens do radio a cada 0,3 s: no teste de 21/10, o `logs/backend.log`
do repositorio chegou a 3,8 GB. Este filtro tira do log so os pedidos bem-sucedidos
dessas rotas; os erros (codigo 400 ou mais) e as outras rotas continuam.
"""
from __future__ import annotations

import logging

ROTAS_FREQUENTES = (
    "/api/live/volta/novos",     # a tela Ao vivo, ~28 por segundo (pedido 35)
    "/api/radio/mensagens",      # o app do jogo e a tela, a cada 0,3 s
)
LOGGER_DE_ACESSO = "uvicorn.access"


class SemPedidosFrequentes(logging.Filter):
    """Deixa de fora as linhas de acesso bem-sucedidas das `ROTAS_FREQUENTES`.

    O uvicorn passa (cliente, metodo, caminho com a consulta, versao, codigo) em `args`."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) < 5:
            return True
        caminho, codigo = str(args[2]), args[4]
        try:
            erro = int(codigo) >= 400
        except (TypeError, ValueError):
            erro = True
        if erro:
            return True
        rota = caminho.split("?", 1)[0]
        return rota not in ROTAS_FREQUENTES


_FILTRO = SemPedidosFrequentes()


def silenciar_rotas_frequentes() -> None:
    """Liga o filtro no log de acesso (uma vez; chamar de novo nao duplica)."""
    logger = logging.getLogger(LOGGER_DE_ACESSO)
    if _FILTRO not in logger.filters:
        logger.addFilter(_FILTRO)
