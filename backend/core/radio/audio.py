"""O audio de cada mensagem (pedido 31, Parte B.3): a vinheta e a voz pt-BR do Windows, num WAV so.

* **A voz:** `voz.ps1`, pelo PowerShell do Windows, sem instalar nada. As vozes
  pt-BR deste Windows: Microsoft Daniel e Microsoft Maria (OneCore) e Microsoft
  Maria Desktop (SAPI 5). A escolhida e a `OneCore:Daniel`, a 1,25x (ver
  `docs/realidade_aumentada.md`).
* **A vinheta:** gerada aqui, por conta: um estalo curto de ruido e dois bipes
  descendo, como o clique de um radio. Nenhum som copiado de transmissao.
* **O arquivo:** `<pasta de dados>/data/radio/audio/<id>.wav`, mono, 16 bits,
  na taxa da voz. O silencio das pontas da voz e cortado.
"""
from __future__ import annotations

import array
import math
import os
import random
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Optional, Tuple

VOZ_PADRAO = "OneCore:Daniel"
VELOCIDADE_PADRAO = 1.25
SCRIPT_DA_VOZ = Path(__file__).with_name("voz.ps1")
LIMIAR_DE_SILENCIO = 500
TEMPO_LIMITE_S = 30


class VozIndisponivel(RuntimeError):
    pass


def vinheta(taxa: int) -> array.array:
    """O clique do radio: 25 ms de ruido, 40 ms de silencio e dois bipes curtos (1.400 e 1.050 Hz)."""
    rnd = random.Random(31)
    amostras = array.array("h")

    def bipe(freq: float, dur_s: float, amp: float) -> None:
        n = int(taxa * dur_s)
        for k in range(n):
            env = min(1.0, k / (0.004 * taxa), (n - k) / (0.008 * taxa))
            amostras.append(int(amp * env * math.sin(2 * math.pi * freq * k / taxa)))

    n_ruido = int(taxa * 0.025)
    for k in range(n_ruido):
        env = 1.0 - k / n_ruido
        amostras.append(int(9000 * env * (rnd.random() * 2 - 1)))
    amostras.extend([0] * int(taxa * 0.04))
    bipe(1400.0, 0.06, 7000)
    amostras.extend([0] * int(taxa * 0.02))
    bipe(1050.0, 0.07, 7000)
    amostras.extend([0] * int(taxa * 0.12))
    return amostras


def _ler_wav(caminho: Path) -> Tuple[int, array.array]:
    with wave.open(str(caminho), "rb") as w:
        if w.getsampwidth() != 2:
            raise VozIndisponivel(f"a voz gerou {w.getsampwidth() * 8} bits; esperado 16")
        taxa, canais, n = w.getframerate(), w.getnchannels(), w.getnframes()
        dados = array.array("h", w.readframes(n))
    if canais > 1:
        dados = array.array("h", (dados[k] for k in range(0, len(dados), canais)))
    return taxa, dados


def _cortar_silencio(dados: array.array, taxa: int) -> array.array:
    sons = [k for k, v in enumerate(dados) if abs(v) > LIMIAR_DE_SILENCIO]
    if not sons:
        return dados
    folga = int(taxa * 0.05)
    return dados[max(0, sons[0] - folga): min(len(dados), sons[-1] + folga)]


def falar(texto: str, destino: Path, voz: str = VOZ_PADRAO, velocidade: float = VELOCIDADE_PADRAO) -> float:
    """Grava `destino` (WAV) com a vinheta e a voz; devolve a duracao em segundos."""
    if sys.platform != "win32":
        raise VozIndisponivel("a voz do radio usa as vozes do Windows")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="radio_") as pasta:
        txt = Path(pasta) / "fala.txt"
        cru = Path(pasta) / "voz.wav"
        txt.write_text(texto, encoding="utf-8")
        comando = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                   str(SCRIPT_DA_VOZ), "-Texto", str(txt), "-Saida", str(cru), "-Voz", voz,
                   "-Velocidade", str(velocidade)]
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        try:
            r = subprocess.run(comando, capture_output=True, text=True, timeout=TEMPO_LIMITE_S, creationflags=flags)
        except (OSError, subprocess.TimeoutExpired) as erro:
            raise VozIndisponivel(f"a voz do Windows não respondeu: {erro}") from erro
        if r.returncode != 0 or not cru.exists():
            raise VozIndisponivel((r.stderr or r.stdout or f"código {r.returncode}").strip()[:300])
        taxa, fala = _ler_wav(cru)
    fala = _cortar_silencio(fala, taxa)
    tudo = vinheta(taxa)
    tudo.extend(fala)
    tudo.extend([0] * int(taxa * 0.15))
    temporario = destino.with_suffix(".tmp")
    with wave.open(str(temporario), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(tudo.tobytes())
    os.replace(temporario, destino)
    return len(tudo) / taxa


def vozes_disponiveis() -> list:
    """As vozes que o `voz.ps1` acha (para a tela Sistema e para o teste)."""
    if sys.platform != "win32":
        return []
    flags = 0x08000000
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                            str(SCRIPT_DA_VOZ), "-Voz", "listar"], capture_output=True, text=True,
                           timeout=TEMPO_LIMITE_S, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [linha.strip() for linha in (r.stdout or "").splitlines() if linha.strip()]


def duracao(caminho: Path) -> Optional[float]:
    try:
        with wave.open(str(caminho), "rb") as w:
            return w.getnframes() / w.getframerate()
    except (OSError, wave.Error):
        return None
