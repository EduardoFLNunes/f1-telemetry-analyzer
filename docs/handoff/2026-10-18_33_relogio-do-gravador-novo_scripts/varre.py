"""Pedido 33, Parte A: varre sessoes e guarda, por volta, o que precisa para o diagnostico.

Uso: python varre.py <saida.pkl> <session_dir> [<session_dir> ...]
So le as gravacoes.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")

from ml.data.recordings import Session, iter_laps  # noqa: E402
from ml.data.store_v2 import game_lap_time  # noqa: E402
from ml.preprocessing.alignment import align_lap  # noqa: E402
from ml.preprocessing.cleaning import clean_lap  # noqa: E402
from ml.preprocessing.resampling import lap_time_from_grid, resample_lap  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

GEOM = load_geometry()
COLS = ["timestamp_s", "lap_number", "lap_time_s", "x", "z", "speed_kmh", "s_recorded"]

saida = Path(sys.argv[1])
resultado = {}
for pasta in sys.argv[2:]:
    pasta = Path(pasta)
    sessao = Session(session_id=pasta.name, directory=pasta, track="vhe_interlagos")
    voltas = {}
    anterior = None
    for lap in iter_laps(sessao):
        f = lap.frame
        cru = f[[c for c in COLS if c in f.columns]].copy()
        info = {"lap_id": lap.lap_id, "sequence": lap.sequence, "lap_number": lap.lap_number,
                "n": len(f), "cru": cru}
        try:
            cleaned, _ = clean_lap(f)
            aligned, _ = align_lap(cleaned, GEOM)
            grid = resample_lap(aligned, GEOM, line_clock=True)
            info["periodo_s"] = lap_time_from_grid(grid)
            info["alinhada"] = aligned[["s", "s_unwrapped", "elapsed_s", "speed_kmh", "lap_time_s", "timestamp_s"]].copy()
        except Exception as erro:  # volta curta, parada, etc.
            info["erro"] = repr(erro)
        if anterior is not None:
            voltas[anterior.sequence]["tempo_jogo_s"] = game_lap_time(anterior, lap, GEOM)
        voltas[lap.sequence] = info
        anterior = lap
    resultado[pasta.name] = voltas
    print(pasta.name, len(voltas), "voltas", flush=True)

with saida.open("wb") as h:
    pickle.dump(resultado, h)
