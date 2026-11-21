"""Pedido 52 (ADR 0033, emenda de 20/11, item 9; emenda de 21/11, item 12): gera os bipes do engenheiro.

* `radio_engenheiro/bipe.wav`: os dois primeiros bipes da contagem, um tom de 2.000 Hz;
* `radio_engenheiro/bipe_agudo.wav`: o ultimo bipe, no ponto de frenagem, mais agudo, um tom de 3.000 Hz.

Os dois com 0,25 s e 10 ms de subida e de descida: diferentes da vinheta do radio (um estalo de ruido e dois bipes
descendo, 1.400 e 1.050 Hz) e da voz. Gerados pelo codigo, sem som copiado.

Uso: python gerar_bipe.py
"""
import array
import math
import wave
from pathlib import Path

TAXA = 22050
DURACAO_S = 0.25
RAMPA_S = 0.010
AMPLITUDE = 0.55
BIPES = {"bipe.wav": 2000.0, "bipe_agudo.wav": 3000.0}


def gerar(nome: str, frequencia_hz: float) -> Path:
    amostras = array.array("h")
    n = int(TAXA * DURACAO_S)
    rampa = int(TAXA * RAMPA_S)
    for i in range(n):
        env = min(1.0, i / rampa, (n - 1 - i) / rampa)
        amostras.append(int(AMPLITUDE * env * 32767 * math.sin(2 * math.pi * frequencia_hz * i / TAXA)))
    destino = Path(__file__).resolve().parent / "radio_engenheiro" / nome
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(amostras.tobytes())
    print(destino, frequencia_hz, "Hz", n / TAXA, "s")
    return destino


if __name__ == "__main__":
    for nome, f in BIPES.items():
        gerar(nome, f)
