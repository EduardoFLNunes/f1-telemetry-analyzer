"""Pedido 54, Parte B.1: a linha do jogo volta a volta, em todas as sessoes de Interlagos (so leitura).

Mesma medida do store v2 (`store_v2.game_line_position` e `line_speeds`, na volta limpa e alinhada),
feita nas primeiras HEAD amostras de cada volta crua, o que basta para a passagem do comeco.
Saida: um CSV por volta e um JSON por sessao.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47\backend")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data.recordings import iter_laps, list_all_sessions  # noqa: E402
from ml.data.store_v2 import game_line_position, line_speeds  # noqa: E402
from ml.preprocessing.alignment import align_lap  # noqa: E402
from ml.preprocessing.cleaning import clean_lap  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

HEAD = 240                      # 4 s a 60 Hz
OUT = Path(sys.argv[1])
only = set(sys.argv[2:])        # opcional: so estas sessoes

track = load_geometry()
roots = config.recordings_roots()
sessions = list_all_sessions(incluir_pistas_de_teste=True)
rows = []
started = time.time()
for k, s in enumerate(sorted(sessions, key=lambda s: s.session_id)):
    if only and s.session_id not in only:
        continue
    meta = s.metadata() or {}
    m = meta.get("metadata") or {}
    folder = next((name for name, root in roots.items() if str(s.directory).startswith(str(root))), "?")
    n = 0
    for lap in iter_laps(s):
        head = lap.frame.head(HEAD)
        try:
            cleaned, _ = clean_lap(head)
            aligned, _ = align_lap(cleaned, track)
        except Exception as exc:  # noqa: BLE001
            continue
        pos = game_line_position(aligned, track.length)
        if pos is None:
            continue
        v0, _ = line_speeds(aligned, track.length)
        ai = head["ai_controlled"].astype(float).mean() if "ai_controlled" in head else np.nan
        rows.append({
            "sessao": s.session_id, "pasta": folder, "pista": s.track, "lap_id": lap.lap_id,
            "sequencia": lap.sequence, "linha_m": pos, "v_kmh": v0, "ia_frac": ai,
            "app": m.get("appVersion"), "app_empacotado": m.get("appPackaged"), "app_commit": m.get("appCommit"),
            "inicio": meta.get("startedAt"), "hz": meta.get("playerRecordHz"), "carro": m.get("carModel"),
            "track_cache": m.get("trackCache"),
        })
        n += 1
    print(f"[{k + 1}/{len(sessions)}] {s.session_id}: {n} voltas medidas ({time.time() - started:.0f} s)", flush=True)

df = pd.DataFrame(rows)
df.to_csv(OUT, index=False)
print("->", OUT, len(df))
