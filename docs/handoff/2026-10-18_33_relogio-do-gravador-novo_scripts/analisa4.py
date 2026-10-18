"""Pedido 33: a diferenca e o tempo de percorrer os 1,46 m entre o s = 0 oficial e a linha do jogo?

previsto = g * (1/v_inicio - 1/v_fim), com g a distancia entre o s = 0 e a linha do
jogo e v a velocidade nas duas passagens. Primeiro nas 90 voltas das 8 sessoes, com
as amostras cruas; depois nas 676 do store, com a velocidade da grade.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
from ml.track.geometry import load_geometry  # noqa: E402

AQUI = Path(__file__).parent
GEOM = load_geometry()
L = GEOM.length
dados = {}
for nome in ("novas.pkl", "antigas.pkl"):
    dados.update(pickle.load(open(AQUI / nome, "rb")))
difs = pd.read_pickle(AQUI / "difs.pkl").set_index("lap_id")

# 1) a linha do jogo: s da passagem do cronometro por zero, em todas as voltas rapidas das 8 sessoes
linha = []
for sessao, voltas in dados.items():
    for seq, v in voltas.items():
        a = v.get("alinhada")
        if a is None or len(a) < 10 or a["speed_kmh"].iloc[0] < 100:
            continue
        linha.append(float(a["s"].iloc[0]) - float(a["speed_kmh"].iloc[0]) / 3.6 * float(a["lap_time_s"].iloc[0]))
g = float(np.median(linha))
print(f"linha do jogo: s = {g:.3f} m depois do s = 0 oficial (n={len(linha)}, desvio {np.std(linha):.3f} m)")


def v_na_passagem(a, alvo):
    u = np.maximum.accumulate(a["s_unwrapped"].to_numpy(float))
    sp = a["speed_kmh"].to_numpy(float) / 3.6
    perto = np.abs(u - alvo) <= 15
    return float(np.median(sp[perto])) if perto.any() else np.nan


rows = []
for sessao, voltas in dados.items():
    for seq, v in voltas.items():
        if v["lap_id"] not in difs.index:
            continue
        a = v["alinhada"]
        u0 = float(np.round(a["s_unwrapped"].iloc[0] / L) * L)
        vi, vf = v_na_passagem(a, u0), v_na_passagem(a, u0 + L)
        rows.append({"lap_id": v["lap_id"], "dif_ms": difs.loc[v["lap_id"], "dif_store_ms"],
                     "v_inicio_kmh": 3.6 * vi, "v_fim_kmh": 3.6 * vf,
                     "previsto_ms": 1000 * g * (1 / vi - 1 / vf)})
t = pd.DataFrame(rows)
t["resto_ms"] = t.dif_ms - t.previsto_ms
print("\n90 voltas, amostras cruas: correlacao", round(float(np.corrcoef(t.dif_ms, t.previsto_ms)[0, 1]), 4))
print(" |dif|  p99", round(float(np.percentile(np.abs(t.dif_ms), 99)), 2), " max", round(float(np.abs(t.dif_ms).max()), 2))
print(" |resto| p99", round(float(np.percentile(np.abs(t.resto_ms), 99)), 2), " max", round(float(np.abs(t.resto_ms).max()), 2),
      " mediana", round(float(np.median(np.abs(t.resto_ms))), 2))
print(t[np.abs(t.dif_ms) > 5].round(2).to_string())
t.to_pickle(AQUI / "modelo90.pkl")

# 2) as 676 do store, com a velocidade da propria grade nas duas pontas
meta = json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\laps_grid_v2_meta.json", encoding="utf-8"))
m = pd.DataFrame(meta["laps"])
m["dif_ms"] = 1000 * (m.lap_time_s - m.tempo_jogo_s)
grade = pq.read_table(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\laps_grid_v2.parquet",
                      columns=["lap_id", "grid_index", "speed_kmh"]).to_pandas()
n = int(grade.grid_index.max()) + 1
# grid_index 0 e o s = 0 tomado no fim da volta (a volta comeca 1,46 m depois);
# o inicio fica no grid_index 2 (s = 4 m) e o fim no ultimo (s = L - 2 m).
ini = grade[grade.grid_index == 2].set_index("lap_id").speed_kmh
fim = grade[grade.grid_index == n - 1].set_index("lap_id").speed_kmh
m["v_inicio_kmh"] = m.lap_id.map(ini)
m["v_fim_kmh"] = m.lap_id.map(fim)
m["previsto_ms"] = 1000 * g * (3.6 / m.v_inicio_kmh - 3.6 / m.v_fim_kmh)
m["resto_ms"] = m.dif_ms - m.previsto_ms
print("\n676 voltas do store: correlacao", round(float(np.corrcoef(m.dif_ms, m.previsto_ms)[0, 1]), 4))
for nome, col in (("|periodo - tempo do jogo|", "dif_ms"), ("|resto depois de tirar os 1,46 m|", "resto_ms")):
    x = np.abs(m[col])
    print(f" {nome}: mediana {np.median(x):.2f}  p99 {np.percentile(x, 99):.2f}  max {x.max():.2f}  acima de 5 ms: {(x > 5).sum()}")
print(m.loc[np.abs(m.dif_ms) > 5, ["lap_id", "dif_ms", "v_inicio_kmh", "v_fim_kmh", "previsto_ms", "resto_ms"]].round(2).to_string())
print("\nas maiores sobras:")
print(m.reindex(m.resto_ms.abs().sort_values(ascending=False).index)[["lap_id", "dif_ms", "v_inicio_kmh", "v_fim_kmh", "previsto_ms", "resto_ms"]].head(8).round(2).to_string())
m[["lap_id", "session_id", "dif_ms", "v_inicio_kmh", "v_fim_kmh", "previsto_ms", "resto_ms"]].to_pickle(AQUI / "modelo676.pkl")
