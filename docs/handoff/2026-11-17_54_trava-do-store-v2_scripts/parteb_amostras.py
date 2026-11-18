"""Pedido 54, B.3: as amostras em volta da passagem pela linha, numa sessao que passa e numa que reprova."""
import sys

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\backend")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml.data.recordings import iter_laps, list_all_sessions  # noqa: E402
from ml.preprocessing.alignment import align_lap  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

track = load_geometry()
L = track.length
wanted = sys.argv[1:]
sessions = {s.session_id: s for s in list_all_sessions(incluir_pistas_de_teste=True)}
for sid in wanted:
    laps = list(iter_laps(sessions[sid]))
    shown = 0
    for prev, lap in zip(laps, laps[1:]):
        tail, head = prev.frame.tail(4), lap.frame.head(5)
        if head["speed_kmh"].iloc[0] < 200:
            continue
        both = pd.concat([tail, head], ignore_index=True)
        aligned, _ = align_lap(both, track)
        if len(aligned) != len(both):
            continue
        s = aligned["s"].to_numpy(float)
        s = np.where(s > L / 2, s - L, s)
        t = both["timestamp_s"].to_numpy(float)
        timer = both["lap_time_s"].to_numpy(float)
        v = both["speed_kmh"].to_numpy(float) / 3.6
        print(f"\n{sid}  volta {prev.lap_number} -> {lap.lap_number}")
        print("   dt_ms   volta  cronometro_s      s_m   v_kmh   s - v*cron (m)")
        for i in range(len(both)):
            mark = "*" if i == len(tail) else " "
            print(f" {mark}{1000 * (t[i] - t[len(tail)]):7.1f}  {int(both['lap_number'].iloc[i]):5d}  {timer[i]:11.3f}  "
                  f"{s[i]:7.3f}  {3.6 * v[i]:6.1f}  {s[i] - v[i] * timer[i]:8.3f}")
        shown += 1
        if shown == 2:
            break
