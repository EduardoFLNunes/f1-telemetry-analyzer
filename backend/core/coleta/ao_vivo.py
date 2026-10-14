"""O que esta sendo gravado agora, item a item do registro (pedido 28, Parte D.2).

O monitor guarda os quadros dos ultimos segundos que o gravador recebeu -- so
enquanto a gravacao esta aberta, que e o que vai para o disco -- e so faz conta
quando a aba pergunta. Para cada item: o estado (ok, ausente, parado, fora da
faixa, taxa baixa), a taxa real em Hz e o ultimo valor.

* **ausente:** nenhum quadro da janela tem o valor;
* **taxa baixa:** os quadros com valor chegam a menos de `TAXA_MINIMA_HZ`;
* **parado:** o valor nao muda com o carro andando (acima de
  `VELOCIDADE_ANDANDO_KMH`), nos itens que deveriam mudar; na embreagem, so o
  zero constante, que e o defeito das gravacoes antigas;
* **fora da faixa:** mais de `FORA_DA_FAIXA_TOLERADO` dos valores fora da faixa
  do registro.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Mapping, Optional, Tuple

from .requisitos import (
    FORA_DA_FAIXA_TOLERADO,
    GRUPOS,
    JANELA_AO_VIVO_S,
    REQUISITOS,
    TAXA_MINIMA_HZ,
    VELOCIDADE_ANDANDO_KMH,
    Requisito,
    fora_da_faixa,
    valor_componente,
)

OK = "ok"
AUSENTE = "ausente"
PARADO = "parado"
FORA_DA_FAIXA = "fora_da_faixa"
TAXA_BAIXA = "taxa_baixa"
SEM_DADOS = "sem_dados"

ROTULOS = {
    OK: "ok",
    AUSENTE: "ausente",
    PARADO: "parado",
    FORA_DA_FAIXA: "fora da faixa",
    TAXA_BAIXA: "taxa baixa",
    SEM_DADOS: "sem dados",
}
# Do pior para o melhor: o estado de um grupo e o pior dos seus itens.
GRAVIDADE = (AUSENTE, TAXA_BAIXA, PARADO, FORA_DA_FAIXA, SEM_DADOS, OK)

# Abaixo disso a janela e curta demais para medir taxa ou dizer "parado".
JANELA_MINIMA_S = 1.0
QUADROS_ANDANDO_MINIMOS = 30


def _numero(valor: Any) -> Optional[float]:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _instante_s(quadro: Mapping[str, Any], recebido: float) -> float:
    """O instante do quadro: o `timestamp` do jogo (ms), ou a hora em que chegou."""
    valor = _numero(quadro.get("timestamp"))
    if valor is None:
        return recebido
    return valor / 1000.0 if valor > 100_000_000_000.0 else valor


def _velocidade(quadro: Mapping[str, Any]) -> Optional[float]:
    valor = _numero(quadro.get("speedKmh"))
    if valor is None:
        fisica = quadro.get("carPhysics") if isinstance(quadro.get("carPhysics"), Mapping) else {}
        movimento = fisica.get("motion") if isinstance(fisica.get("motion"), Mapping) else {}
        valor = _numero(movimento.get("speedKmh"))
    return valor


def estado_do_componente(item: Requisito, serie: List[Tuple[float, Any, Optional[float]]]) -> Dict[str, Any]:
    """Estado de um componente numa janela: `serie` e [(instante_s, valor, velocidade_kmh)]."""
    if not serie:
        return {"estado": SEM_DADOS, "taxaHz": None, "preenchimento": None, "foraDaFaixa": None, "ultimo": None}
    com_valor = [(t, v, s) for t, v, s in serie if v is not None]
    preenchimento = len(com_valor) / len(serie)
    ultimo = com_valor[-1][1] if com_valor else None
    if not com_valor:
        return {"estado": AUSENTE, "taxaHz": 0.0, "preenchimento": 0.0, "foraDaFaixa": None, "ultimo": None}

    inicio, fim = serie[0][0], serie[-1][0]
    duracao = fim - inicio
    taxa = (len(com_valor) - 1) / duracao if duracao >= JANELA_MINIMA_S and len(com_valor) > 1 else None
    fora = None
    if item.tipo == "numero" and item.faixa is not None:
        fora = sum(1 for _, v, _ in com_valor if fora_da_faixa(item, v)) / len(com_valor)

    estado = OK
    if taxa is not None and taxa < TAXA_MINIMA_HZ:
        estado = TAXA_BAIXA
    elif item.parado and item.tipo == "numero" and duracao >= JANELA_MINIMA_S:
        andando = [v for _, v, s in com_valor if s is not None and s > VELOCIDADE_ANDANDO_KMH]
        if len(andando) >= QUADROS_ANDANDO_MINIMOS:
            constante = max(andando) == min(andando)
            if item.parado == "varia" and constante:
                estado = PARADO
            elif item.parado == "zero" and constante and andando[0] == 0.0:
                estado = PARADO
    if estado == OK and fora is not None and fora > FORA_DA_FAIXA_TOLERADO:
        estado = FORA_DA_FAIXA
    return {
        "estado": estado,
        "taxaHz": round(taxa, 1) if taxa is not None else None,
        "preenchimento": round(preenchimento, 4),
        "foraDaFaixa": round(fora, 4) if fora is not None else None,
        "ultimo": ultimo,
    }


def pior(estados: List[str]) -> str:
    for estado in GRAVIDADE:
        if estado in estados:
            return estado
    return SEM_DADOS


class MonitorAoVivo:
    """Janela dos quadros gravados. `on_frame` so guarda; a conta e feita em `estado()`."""

    def __init__(self, gravando: Callable[[], bool] = lambda: True, janela_s: float = JANELA_AO_VIVO_S,
                 relogio: Callable[[], float] = time.monotonic):
        self.gravando = gravando
        self.janela_s = float(janela_s)
        self.relogio = relogio
        self._quadros: Deque[Tuple[float, Mapping[str, Any]]] = deque()
        self._lock = threading.Lock()

    async def on_frame(self, frame: Mapping[str, Any]) -> None:
        self.observar(frame)

    def observar(self, frame: Mapping[str, Any]) -> None:
        if not isinstance(frame, Mapping):
            return
        try:
            if not self.gravando():
                return
        except Exception:
            return
        agora = self.relogio()
        with self._lock:
            self._quadros.append((agora, frame))
            self._descartar(agora)

    def _descartar(self, agora: float) -> None:
        limite = agora - self.janela_s
        while self._quadros and self._quadros[0][0] < limite:
            self._quadros.popleft()

    def limpar(self) -> None:
        with self._lock:
            self._quadros.clear()

    def estado(self, extras: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        """O estado de cada item e de cada grupo. `extras`: `carModel` e `track` do runtime."""
        extras = extras or {}
        agora = self.relogio()
        with self._lock:
            self._descartar(agora)
            quadros = list(self._quadros)
        instantes = [_instante_s(q, recebido) for recebido, q in quadros]
        velocidades = [_velocidade(q) for _, q in quadros]

        itens: List[Dict[str, Any]] = []
        for item in REQUISITOS:
            if item.fonte == "amostra":
                componentes = []
                for componente in item.componentes:
                    serie = [(t, valor_componente(item, componente, q), v)
                             for t, (_, q), v in zip(instantes, quadros, velocidades)]
                    componentes.append({"rotulo": componente.rotulo, **estado_do_componente(item, serie)})
            else:
                chave = "carModel" if item.id == "car_model" else "track"
                valor = extras.get(chave)
                valor = str(valor).strip() if valor not in (None, "") else None
                if not quadros:
                    estado = SEM_DADOS
                else:
                    estado = OK if valor else AUSENTE
                componentes = [{"rotulo": "", "estado": estado, "taxaHz": None,
                                "preenchimento": None, "foraDaFaixa": None, "ultimo": valor}]
            estado_item = pior([c["estado"] for c in componentes])
            taxas = [c["taxaHz"] for c in componentes if c["taxaHz"] is not None]
            itens.append({
                "id": item.id,
                "nome": item.nome,
                "grupo": item.grupo,
                "unidade": item.unidade,
                "tipo": item.tipo,
                "estado": estado_item,
                "estadoRotulo": ROTULOS[estado_item],
                "taxaHz": min(taxas) if taxas else None,
                "componentes": componentes,
                "valorEsperado": item.valor_esperado,
                "obrigatorioM1": item.obrigatorio_m1,
            })

        grupos = []
        for gid, nome in GRUPOS:
            estados = [i["estado"] for i in itens if i["grupo"] == gid]
            grupo = pior(estados) if estados else SEM_DADOS
            grupos.append({"id": gid, "nome": nome, "estado": grupo, "estadoRotulo": ROTULOS[grupo]})

        ia = next(i for i in itens if i["id"] == "ai_controlled")["componentes"][0]["ultimo"]
        duracao = (instantes[-1] - instantes[0]) if len(instantes) > 1 else 0.0
        return {
            "quadros": len(quadros),
            "janelaS": self.janela_s,
            "duracaoS": round(duracao, 3),
            "taxaHz": round((len(quadros) - 1) / duracao, 1) if duracao >= JANELA_MINIMA_S else None,
            "indicadorIA": ia,
            "itens": itens,
            "grupos": grupos,
        }
