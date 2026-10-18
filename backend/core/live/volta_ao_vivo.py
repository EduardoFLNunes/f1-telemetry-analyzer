"""A volta em andamento na grade da geometria oficial (pedido 31, Parte D): para a "Volta com fantasma" ao vivo.

Nao calcula posicao: le a projecao que o coach ja faz (`posicao_oficial`: `s`,
lateral e o relogio da volta desde a linha) e guarda, no ponto da grade de
`s`, a velocidade e os pedais do mesmo quadro. A tela Ao vivo desenha isso com
o mesmo componente da tela Volta.
"""
from __future__ import annotations

import math
import threading
from typing import Any, Callable, Dict, List, Optional

VOLTA_MINIMA_PARA_NOVA = 0.5  # `s` voltou mais de metade da pista: a volta recomecou na linha


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
        self._zerar()

    def _zerar(self) -> None:
        self._linhas: Dict[str, List[Optional[float]]] = {
            nome: [None] * self._n for nome in ("elapsed", "velocidade", "acelerador", "freio", "lateral")
        }
        self._indice: Optional[int] = None
        self._desde_a_linha = False

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
            linhas["velocidade"][k] = _numero(frame.get("speedKmh") if "speedKmh" in frame else frame.get("speed_kmh"))
            linhas["acelerador"][k] = _numero(frame.get("throttle") if "throttle" in frame else frame.get("gas"))
            linhas["freio"][k] = _numero(frame.get("brake"))

    def estado(self) -> Dict[str, Any]:
        with self._lock:
            if not self._n or self._indice is None:
                return {"disponivel": False, "motivo": "sem a projeção do coach: o jogo não está mandando quadros ou o coach não tem a geometria oficial"}
            return {
                "disponivel": True,
                "versao": self._versao,
                "volta": self._volta,
                "desdeALinha": self._desde_a_linha,
                "comprimentoM": self._comprimento,
                "pontosDaGrade": self._n,
                "passoM": self._comprimento / self._n,
                "indice": self._indice,
                "s": self._s_anterior,
                "linhas": {k: list(v) for k, v in self._linhas.items()},
            }
