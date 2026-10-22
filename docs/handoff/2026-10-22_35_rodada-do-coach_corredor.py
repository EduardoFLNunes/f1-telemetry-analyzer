"""O corredor da volta nova (1:26,875, 2026-10-21_20-30-54#0017), como na Parte A.2 do pedido 32.

As mesmas funcoes do store v2 e da conferencia da Coleta, so lendo: a volta crua e
limpa (`clean_lap`), alinhada na geometria oficial (`align_lap`) e passada pelos portoes
(`evaluate_lap`, com a fracao fora do corredor util). Para cada volta da sessao: os
portoes, os pneus fora e o `off_track` do jogo, a fracao fora do corredor e o maior
excesso (onde e para que lado).

Uso (na pasta backend): python corredor_21-10.py <saida.json>
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.radio.analise import Pista  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402
from ml.preprocessing.alignment import align_lap  # noqa: E402
from ml.preprocessing.cleaning import clean_lap  # noqa: E402
from ml.preprocessing.quality import evaluate_lap  # noqa: E402

REPO = Path("..").resolve()
SESSAO = "2026-10-21_20-30-54_vhe_interlagos"
track = carregar_geometria(REPO)
curvas = Pista.da_geometria(track).segmentos
low, high = track.corridor()


def curva_em(s: float) -> str:
    for seg in curvas:
        if seg.start_s <= s <= seg.end_s:
            return seg.corner.label[:3]
    return "reta"


saida = []
for lap in iter_laps(Session(session_id=SESSAO, directory=REPO / "data" / "recordings" / SESSAO, track="vhe_interlagos")):
    f = lap.frame
    cleaned, _ = clean_lap(f)
    if cleaned.empty or len(cleaned) < 4:
        continue
    aligned, alignment = align_lap(cleaned, track)
    q = evaluate_lap(aligned, track, alignment)
    s = aligned["s"].to_numpy(float)
    lat = aligned["lateral"].to_numpy(float)
    i = track.index_of(s)
    excesso = np.maximum(lat - high[i], low[i] - lat)       # positivo = fora; para que lado pelo sinal de lat
    fora = excesso > 0
    trechos = []
    if fora.any():
        # os trechos fora, do maior excesso para o menor
        borda = np.flatnonzero(np.diff(np.concatenate([[0], fora.astype(int), [0]])))
        for a, b in zip(borda[::2], borda[1::2]):
            k = a + int(np.argmax(excesso[a:b]))
            trechos.append({"deS": round(float(s[a]), 0), "ateS": round(float(s[b - 1]), 0),
                            "maiorExcessoM": round(float(excesso[k]), 2),
                            "lado": "esquerda" if lat[k] > 0 else "direita", "curva": curva_em(float(s[k]))})
        trechos.sort(key=lambda x: -x["maiorExcessoM"])
    tyres = f["tyres_out"].fillna(0) if "tyres_out" in f else None
    saida.append({
        "volta": lap.lap_id, "tempoS": round(float(f["lap_time_s"].max()), 3), "valida": bool(q.valid),
        "motivos": list(q.reasons), "amostras": int(len(f)),
        "pneusFora2ouMais": int((tyres >= 2).sum()) if tyres is not None else None,
        "pneusFora1ouMais": int((tyres >= 1).sum()) if tyres is not None else None,
        "offTrack": int(f["off_track"].fillna(False).astype(bool).sum()) if "off_track" in f else None,
        "foraDoCorredor": round(float(q.metrics.get("outside_corridor_fraction", np.nan)), 4),
        "trechosFora": trechos[:5],
    })
    v = saida[-1]
    print(v["volta"], v["tempoS"], "valida" if v["valida"] else "invalida", f"fora {100 * v['foraDoCorredor']:.1f}%",
          "pneus>=2:", v["pneusFora2ouMais"], "off:", v["offTrack"], v["trechosFora"][:2])
Path(sys.argv[1]).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
