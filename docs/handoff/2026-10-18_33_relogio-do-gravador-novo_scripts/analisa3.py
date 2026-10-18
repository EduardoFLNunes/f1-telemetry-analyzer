"""Pedido 33: as amostras perto da linha, uma a uma, e a decomposicao do periodo."""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
from ml.preprocessing.resampling import LINE_WINDOW_M  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

AQUI = Path(__file__).parent
GEOM = load_geometry()
L = GEOM.length
dados = {}
for nome in ("novas.pkl", "antigas.pkl"):
    dados.update(pickle.load(open(AQUI / nome, "rb")))
difs = pd.read_pickle(AQUI / "difs.pkl").set_index("lap_id")
pd.set_option("display.width", 220)
pd.set_option("display.max_rows", 500)


def tabela(v, ponta, n=14):
    """As amostras de uma ponta da volta: cronometro, relogio, s, intervalo."""
    cru = v["cru"].reset_index(drop=True)
    a = v["alinhada"].reset_index(drop=True)
    s, _ = GEOM.project_sequence(cru[["x", "z"]].to_numpy(float))
    t = pd.DataFrame({
        "relogio_ms": 1000 * cru["timestamp_s"],
        "cron_ms": 1000 * cru["lap_time_s"],
        "volta": cru["lap_number"].astype(int),
        "s_m": s,
        "x": cru["x"], "z": cru["z"],
        "v_kmh": cru["speed_kmh"],
    })
    t["d_relogio_ms"] = t.relogio_ms.diff()
    t["d_cron_ms"] = t.cron_ms.diff()
    t["d_s_m"] = np.mod(t.s_m.diff() + L / 2, L) - L / 2
    # velocidade implicita pelo cronometro: anda d_s em d_cron
    t["v_pelo_cron"] = 3.6 * t.d_s_m / (t.d_cron_ms / 1000)
    t = t.tail(n) if ponta == "fim" else t.head(n)
    t = t.drop(columns=["x", "z"])
    t["relogio_ms"] = t.relogio_ms - t.relogio_ms.iloc[0]   # relativo a primeira linha da tabela
    return t


def cruzamentos(v):
    """As estimativas de cada amostra para as duas passagens por s = 0 (como crossing_time)."""
    a = v["alinhada"]
    u = np.maximum.accumulate(a["s_unwrapped"].to_numpy(float))
    t = a["elapsed_s"].to_numpy(float)
    sp = a["speed_kmh"].to_numpy(float) / 3.6
    first = float(np.round(u[0] / L) * L)
    out = {}
    for nome, alvo in (("inicio", first), ("fim", first + L)):
        perto = (np.abs(u - alvo) <= LINE_WINDOW_M) & (sp > 1)
        est = t[perto] + (alvo - u[perto]) / sp[perto]
        out[nome] = (est, u[perto] - alvo)
    return out


alvos = sys.argv[1:]
for lap_id in alvos:
    sessao, seq = lap_id.split("#")
    seq = int(seq)
    voltas = dados[sessao]
    v, seguinte, anterior = voltas[seq], voltas.get(seq + 1), voltas.get(seq - 1)
    print("=" * 100)
    print(lap_id, "dif do store:", round(difs.loc[lap_id, "dif_store_ms"], 2), "ms;  periodo", round(v["periodo_s"], 4),
          " tempo do jogo", round(v["tempo_jogo_s"], 4))
    c = cruzamentos(v)
    for nome in ("inicio", "fim"):
        est, dist = c[nome]
        print(f"  passagem do {nome}: {len(est)} amostras na janela; estimativas (ms, relativas a mediana):",
              np.round(1000 * (est - np.median(est)), 1).tolist())
    print("\n  -- inicio da volta (fim da anterior e comeco desta) --")
    if anterior is not None:
        print(tabela(anterior, "fim", 6).round(2).to_string())
    print(tabela(v, "inicio", 10).round(2).to_string())
    print("\n  -- fim da volta (fim desta e comeco da seguinte) --")
    print(tabela(v, "fim", 12).round(2).to_string())
    if seguinte is not None:
        print(tabela(seguinte, "inicio", 6).round(2).to_string())
