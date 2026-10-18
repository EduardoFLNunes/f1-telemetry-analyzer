"""Pedido 33: reproduz a diferenca do store e mostra as amostras perto da linha."""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
from ml.track.geometry import load_geometry  # noqa: E402

AQUI = Path(__file__).parent
GEOM = load_geometry()
L = GEOM.length
meta = json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\laps_grid_v2_meta.json", encoding="utf-8"))
store = {d["lap_id"]: d for d in meta["laps"]}

dados = {}
for nome in ("novas.pkl", "antigas.pkl"):
    dados.update(pickle.load(open(AQUI / nome, "rb")))

linhas = []
for sessao, voltas in dados.items():
    for seq, v in sorted(voltas.items()):
        if v["lap_id"] not in store:
            continue
        st = store[v["lap_id"]]
        linhas.append({
            "lap_id": v["lap_id"], "seq": seq,
            "dif_store_ms": 1000 * (st["lap_time_s"] - st["tempo_jogo_s"]),
            "dif_agora_ms": 1000 * (v.get("periodo_s", np.nan) - (v.get("tempo_jogo_s") or np.nan)),
        })
t = pd.DataFrame(linhas)
print("voltas do store nas 8 sessoes:", len(t), " reproduz (|dif|<0.01 ms):", int((np.abs(t.dif_store_ms - t.dif_agora_ms) < 0.01).sum()))

# Onde fica a linha do jogo: o s da primeira amostra de cada volta (depois do cronometro zerar)
ss = []
for sessao, voltas in dados.items():
    for seq, v in voltas.items():
        a = v.get("alinhada")
        if a is None or len(a) < 10:
            continue
        cru = v["cru"]
        primeira_lt = cru["lap_time_s"].iloc[0]
        ss.append({"sessao": sessao[:19], "seq": seq, "s0": float(a["s"].iloc[0]), "lt0_ms": 1000 * primeira_lt,
                   "v0": float(a["speed_kmh"].iloc[0])})
s0 = pd.DataFrame(ss)
s0 = s0[s0.v0 > 150]
print("s da primeira amostra da volta (carro rapido):")
print(s0.groupby("sessao").agg(n=("s0", "size"), s0_med=("s0", "median"), lt0_med_ms=("lt0_ms", "median"),
                               s_menos_v_lt=("s0", lambda x: 0)).to_string())
s0["linha_m"] = s0.s0 - s0.v0 / 3.6 * s0.lt0_ms / 1000
print("posicao estimada da linha do jogo (s0 - v*lap_time0):", s0.linha_m.describe().round(2).to_dict())
t.to_pickle(AQUI / "difs.pkl")
