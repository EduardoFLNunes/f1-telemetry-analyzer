"""Toca uma gravacao real em tempo real no caminho ao vivo, sem o jogo (pedido 35, Parte D.1). So de teste.

Liga so com `AT_TESTE_REPRODUTOR=1` (a rota `/api/teste/*` responde 404 sem ela),
e e para a pasta isolada dos testes, nunca para o app que grava.

Faz, amostra a amostra e no ritmo do relogio do gravador, o mesmo que o laco do
jogo faz (`core/live/telemetry_runtime.py`): `TelemetrySample` da amostra,
`runtime_state.update_car` e o quadro no barramento (`processed_frame`), pelo
mesmo `event_bus.schedule`. A unica diferenca e o nome da pista: sem o jogo, o
quadro nao traz a pista, e o reprodutor poe a da gravacao (`track`), que e o que
o coach usaria com o jogo aberto (`current_recording_track`).

O caminho ao vivo nao muda: o reprodutor so chama o que o jogo chamaria.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

VARIAVEL = "AT_TESTE_REPRODUTOR"


def ligado() -> bool:
    return os.environ.get(VARIAVEL) == "1"


class Reprodutor:
    def __init__(self, processar: Callable[[Dict[str, Any], Optional[str]], None]):
        """`processar(amostra, pista)` faz o que o laco do jogo faz com uma amostra."""
        self._processar = processar
        self._thread: Optional[threading.Thread] = None
        self._parar = threading.Event()
        self.estado: Dict[str, Any] = {"tocando": False}

    def tocar(self, arquivo: Path, desde_volta: int = 0, ate_volta: Optional[int] = None,
              velocidade: float = 1.0, desde_tempo_s: float = 0.0) -> Dict[str, Any]:
        self.parar()
        arquivo = Path(arquivo)
        if not arquivo.exists():
            return {"tocando": False, "erro": f"nao achei {arquivo}"}
        self._parar.clear()
        self.estado = {"tocando": True, "arquivo": str(arquivo), "amostras": 0, "volta": None}
        self._thread = threading.Thread(target=self._laco, args=(arquivo, desde_volta, ate_volta, velocidade,
                                                                      desde_tempo_s),
                                        daemon=True, name="teste-reprodutor")
        self._thread.start()
        return dict(self.estado)

    def parar(self) -> Dict[str, Any]:
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.estado["tocando"] = False
        return dict(self.estado)

    def _laco(self, arquivo: Path, desde_volta: int, ate_volta: Optional[int], velocidade: float,
              desde_tempo_s: float) -> None:
        inicio_real = inicio_gravado = None
        try:
            with arquivo.open("r", encoding="utf-8", errors="replace") as entrada:
                for linha in entrada:
                    if self._parar.is_set():
                        break
                    try:
                        envelope = json.loads(linha)
                    except ValueError:
                        continue
                    amostra = envelope.get("sample") if isinstance(envelope, dict) else None
                    if not isinstance(amostra, dict):
                        continue
                    volta = amostra.get("lap") or amostra.get("lap_number")
                    if volta is None or int(volta) < desde_volta:
                        continue
                    if inicio_real is None and int(volta) == desde_volta and \
                            float(amostra.get("lap_time") or 0.0) < desde_tempo_s:
                        continue
                    if ate_volta is not None and int(volta) > ate_volta:
                        break
                    gravado = float(envelope.get("timestamp") or amostra.get("timestamp") or 0.0) / 1000.0
                    if inicio_real is None:
                        inicio_real, inicio_gravado = time.perf_counter(), gravado
                    espera = (gravado - inicio_gravado) / max(velocidade, 1e-3) - (time.perf_counter() - inicio_real)
                    if espera > 0:
                        time.sleep(espera)
                    self._processar(amostra, envelope.get("track"))
                    self.estado["amostras"] += 1
                    self.estado["volta"] = int(volta)
        finally:
            self.estado["tocando"] = False
