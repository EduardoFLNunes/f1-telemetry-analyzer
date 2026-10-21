"""A volta em andamento na grade da geometria oficial (pedido 31, Parte D): para a "Volta com fantasma" ao vivo.

Nao calcula posicao: le a projecao que o coach ja faz (`posicao_oficial`: `s`,
lateral e o relogio da volta desde a linha) e guarda, no ponto da grade de
`s`, a velocidade e os pedais do mesmo quadro. A tela Ao vivo desenha isso com
o mesmo componente da tela Volta.

Pedido 35 (Parte D): a tela nao recebe mais a volta inteira a cada leitura.
Cada ponto gravado ganha um numero de sequencia (`seq`), e `novos(versao, desde)`
devolve so os pontos gravados depois de `desde`, com a posicao atual do carro.
A volta inteira vem so na abertura da tela, numa volta nova (`versao` muda) ou se
a tela ficou para tras mais do que o registro guarda. A volta fechada fica
guardada (`ultima_fechada`), para o radio analisar as voltas (ADR 0021).
"""
from __future__ import annotations

import math
import threading
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

VOLTA_MINIMA_PARA_NOVA = 0.5  # `s` voltou mais de metade da pista: a volta recomecou na linha
LINHAS = ("elapsed", "velocidade", "acelerador", "freio", "lateral")
REGISTRO_DE_MUDANCAS = 4000      # pontos guardados para quem pede so os novos (mais de uma volta)


def _numero(valor: Any) -> Optional[float]:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


class VoltaAoVivo:
    def __init__(self, posicao: Callable[[], Optional[Dict[str, Any]]], pontos: Callable[[], Optional[int]]):
        self._posicao = posicao
        self._pontos = pontos
        self._lock = threading.Lock()
        self._n = 0
        self._comprimento: Optional[float] = None
        self._s_anterior: Optional[float] = None
        self._volta: Optional[float] = None
        self._versao = 0
        self._seq = 0
        self._mudancas: Deque[Tuple[int, int]] = deque(maxlen=REGISTRO_DE_MUDANCAS)   # (seq, indice)
        self._carro: Dict[str, Any] = {}
        self._fechada: Optional[Dict[str, Any]] = None
        self._zerar()

    def _zerar(self) -> None:
        self._linhas: Dict[str, List[Optional[float]]] = {nome: [None] * self._n for nome in LINHAS}
        self._indice: Optional[int] = None
        self._desde_a_linha = False
        self._mudancas.clear()

    def _fechar(self) -> None:
        """A volta acabou na linha: guarda o que ela mediu, para o radio analisar (pedido 35)."""
        if self._n and self._desde_a_linha:
            self._fechada = {
                "versao": self._versao,
                "volta": self._volta,
                "pontosDaGrade": self._n,
                "comprimentoM": self._comprimento,
                "linhas": {k: list(v) for k, v in self._linhas.items()},
            }

    def on_frame(self, frame: Any) -> None:
        if not isinstance(frame, dict):
            return
        pos = self._posicao()
        if not pos or pos.get("s") is None:
            return
        with self._lock:
            n = int(self._pontos() or 0)
            if n <= 0:
                return
            L = float(pos["comprimento"])
            if n != self._n or L != self._comprimento:
                self._n, self._comprimento = n, L
                self._zerar()
            s = float(pos["s"])
            if self._s_anterior is not None and self._s_anterior - s > VOLTA_MINIMA_PARA_NOVA * L:
                self._fechar()
                self._zerar()
                self._versao += 1
            self._s_anterior = s
            self._volta = pos.get("volta")
            self._desde_a_linha = bool(pos.get("desdeALinha"))
            k = min(int(s / (L / n)), n - 1)
            self._indice = k
            linhas = self._linhas
            linhas["elapsed"][k] = _numero(pos.get("tempoDaVolta"))
            linhas["lateral"][k] = _numero(pos.get("lateral"))
            velocidade = _numero(frame.get("speedKmh") if "speedKmh" in frame else frame.get("speed_kmh"))
            linhas["velocidade"][k] = velocidade
            linhas["acelerador"][k] = _numero(frame.get("throttle") if "throttle" in frame else frame.get("gas"))
            linhas["freio"][k] = _numero(frame.get("brake"))
            self._seq += 1
            self._mudancas.append((self._seq, k))
            self._carro = {"s": s, "indice": k, "velocidadeKmh": velocidade, "tempoDaVolta": linhas["elapsed"][k],
                           "seq": self._seq}

    def _cabecalho(self) -> Dict[str, Any]:
        return {
            "disponivel": True,
            "versao": self._versao,
            "seq": self._seq,
            "volta": self._volta,
            "desdeALinha": self._desde_a_linha,
            "comprimentoM": self._comprimento,
            "pontosDaGrade": self._n,
            "passoM": self._comprimento / self._n,
            "indice": self._indice,
            "s": self._s_anterior,
            "carro": dict(self._carro),
        }

    def estado(self) -> Dict[str, Any]:
        """A volta inteira (a abertura da tela e as voltas novas)."""
        with self._lock:
            if not self._n or self._indice is None:
                return {"disponivel": False, "motivo": "sem a projeção do coach: o jogo não está mandando quadros ou o coach não tem a geometria oficial"}
            return {**self._cabecalho(), "completa": True, "linhas": {k: list(v) for k, v in self._linhas.items()}}

    def novos(self, versao: Optional[int], desde: Optional[int]) -> Dict[str, Any]:
        """So os pontos gravados depois de `desde` na mesma volta; se nao der, a volta inteira."""
        with self._lock:
            if not self._n or self._indice is None:
                return {"disponivel": False, "motivo": "sem a projeção do coach: o jogo não está mandando quadros ou o coach não tem a geometria oficial"}
            antigo = self._mudancas[0][0] if self._mudancas else self._seq + 1
            if versao != self._versao or desde is None or desde < antigo - 1 or desde > self._seq:
                return {**self._cabecalho(), "completa": True, "linhas": {k: list(v) for k, v in self._linhas.items()}}
            indices = sorted({k for seq, k in self._mudancas if seq > desde})
            return {
                **self._cabecalho(),
                "completa": False,
                "pontos": {"indices": indices, **{nome: [self._linhas[nome][k] for k in indices] for nome in LINHAS}},
            }

    def ultima_fechada(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._fechada
