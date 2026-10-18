"""Pedido 33: de onde vem o relogio de cada volta (cronometro do jogo ou relogio de parede)."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
dados = {}
for nome in ("novas.pkl", "antigas.pkl"):
    dados.update(pickle.load(open(AQUI / nome, "rb")))
difs = pd.read_pickle(AQUI / "difs.pkl").set_index("lap_id")

linhas = []
for sessao, voltas in dados.items():
    for seq, v in sorted(voltas.items()):
        if v["lap_id"] not in difs.index:
            continue
        a = v["alinhada"]
        lt = a["lap_time_s"].to_numpy(float)
        ts = a["timestamp_s"].to_numpy(float)
        el = a["elapsed_s"].to_numpy(float)
        d_lt = np.diff(lt)
        fonte = "jogo" if np.allclose(el, lt - np.nanmin(lt), atol=1e-9, equal_nan=True) else (
            "parede" if np.allclose(el, ts - np.nanmin(ts), atol=1e-9, equal_nan=True) else "outra")
        linhas.append({
            "lap_id": v["lap_id"], "dif_ms": round(difs.loc[v["lap_id"], "dif_store_ms"], 2), "fonte": fonte,
            "lt_recuos": int((d_lt < -1e-6).sum()), "pior_recuo_ms": round(1000 * float(d_lt.min()), 1),
            "lt_repetidos": int((d_lt == 0).sum()), "n": len(a),
        })
t = pd.DataFrame(linhas)
t["grupo"] = np.where(t.lap_id.str.startswith(("2026-10-15", "2026-10-17")), "novo", "antigo")
pd.set_option("display.width", 200)
print(t.groupby(["grupo", "fonte"]).agg(n=("dif_ms", "size"), med_abs=("dif_ms", lambda x: np.median(np.abs(x))),
                                        max_abs=("dif_ms", lambda x: np.abs(x).max())).to_string())
print()
print(t[np.abs(t.dif_ms) > 5].to_string())
print()
print(t[(t.fonte != "jogo")].to_string())
