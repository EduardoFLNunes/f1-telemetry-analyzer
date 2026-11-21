"""Pedido 52 (ADR 0033, emenda de 20/11, item 9): gera o bipe do engenheiro, `radio_engenheiro/bipe.wav`.

Um tom so, de 2.000 Hz, com 0,25 s e 10 ms de subida e de descida: diferente da vinheta do radio (um estalo de
ruido e dois bipes descendo, 1.400 e 1.050 Hz) e da voz. Gerado pelo codigo, sem som copiado.

Uso: python gerar_bipe.py
"""
import array
import math
import wave
from pathlib import Path

TAXA = 22050
DURACAO_S = 0.25
FREQUENCIA_HZ = 2000.0
RAMPA_S = 0.010
AMPLITUDE = 0.55

amostras = array.array("h")
n = int(TAXA * DURACAO_S)
rampa = int(TAXA * RAMPA_S)
for i in range(n):
    env = min(1.0, i / rampa, (n - 1 - i) / rampa)
    amostras.append(int(AMPLITUDE * env * 32767 * math.sin(2 * math.pi * FREQUENCIA_HZ * i / TAXA)))
destino = Path(__file__).resolve().parent / "radio_engenheiro" / "bipe.wav"
with wave.open(str(destino), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(TAXA)
    w.writeframes(amostras.tobytes())
print(destino, n / TAXA, "s")
