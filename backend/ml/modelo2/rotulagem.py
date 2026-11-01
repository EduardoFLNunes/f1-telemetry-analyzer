"""O kit de rotulagem dos 5 detectores (secao 1.9) e a precisao e a revocacao depois.

O kit mostra a posicao na pista e os tracos de pedal, volante, velocidade e
guinada, com as fronteiras das fases. Ele esconde o estado do detector e a
origem da volta (IA ou piloto): os dois ficam no gabarito, fora do git.
"""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from .detectores import APLICA, NAO_APLICA, NC, Lap
from .fases import CornerPhases, ahead, window
from ..track.geometry import TrackGeometry

DETECTORS = ("F4", "F5", "M6", "E2", "E3")
PER_DETECTOR = 24
PER_STATE = 8
SEED = 38

QUESTIONS = {
    "F4": ("Soltura progressiva do freio",
           "O freio é solto de forma gradual no fim da frenagem (uma rampa), sem um degrau em que ele cai de uma vez?"),
    "F5": ("Trail braking",
           "O freio continua aplicado (mesmo pouco) depois que o volante começa a virar, e vai diminuindo enquanto o volante aumenta?"),
    "M6": ("Retomada do acelerador",
           "O acelerador volta depois da velocidade mínima, sem o volante voltar a crescer e sem alívio (acelera, solta e acelera de novo)?"),
    "E2": ("Subesterço",
           "No meio da curva, o carro pede mais volante do que a curva pede (a frente escorrega: volante grande para pouca guinada)?"),
    "E3": ("Sobresterço",
           "A traseira escorrega: a guinada passa do que o volante pede, ou aparece contraesterço?"),
}


def select(states: pd.DataFrame, detector: str, rng: np.random.Generator) -> pd.DataFrame:
    d = states[states["detector"] == detector]
    if detector in ("E2", "E3"):
        d = d[d["motivo"].isna() | ~d["motivo"].fillna("").str.startswith("sem guinada")]
        d = d[~d["motivo"].fillna("").str.contains("sem velocidades|sem o evento|sem referencia")]
    chosen = []
    for state in (APLICA, NAO_APLICA, NC):
        pool = d[d["estado"] == state]
        ai, mine = pool[pool["origem"] == "ia"], pool[pool["origem"] != "ia"]
        n_ai = min(len(ai), PER_STATE // 3)
        pick_ai = ai.sample(n=n_ai, random_state=int(rng.integers(1 << 30))) if n_ai else ai.iloc[:0]
        n_mine = min(len(mine), PER_STATE - n_ai)
        pick_mine = mine.sample(n=n_mine, random_state=int(rng.integers(1 << 30))) if n_mine else mine.iloc[:0]
        chosen.append(pd.concat([pick_ai, pick_mine]))
    chosen = pd.concat(chosen)
    if len(chosen) < PER_DETECTOR:
        rest = d.drop(chosen.index)
        extra = rest.sample(n=min(len(rest), PER_DETECTOR - len(chosen)), random_state=int(rng.integers(1 << 30)))
        chosen = pd.concat([chosen, extra])
    return chosen.sample(frac=1.0, random_state=int(rng.integers(1 << 30)))


def _poly(xs, ys, x0, x1, y0, y1, w, h, top, colour, width=1.4):
    pts = []
    for x, y in zip(xs, ys):
        if not np.isfinite(y):
            continue
        px = (x - x0) / (x1 - x0) * w
        py = top + h - (y - y0) / (y1 - y0) * h if y1 > y0 else top + h / 2
        pts.append(f"{px:.1f},{py:.1f}")
    return f'<polyline fill="none" stroke="{colour}" stroke-width="{width}" points="{" ".join(pts)}"/>'


def trace_svg(lap: Lap, track: TrackGeometry, cp: CornerPhases, previous: CornerPhases) -> str:
    start = float(np.mod(min(cp.b, cp.a) - 60.0, track.length)) if cp.b != cp.a else float(np.mod(cp.a - 120.0, track.length))
    start = previous.apice if ahead(track, previous.apice, cp.a) < ahead(track, start, cp.a) else start
    end = float(np.mod(cp.e + 100.0, track.length))
    idx = window(track, start, end)
    x = np.arange(idx.size) * track.step
    W, rowh, gap = 760, 70, 16
    rows = [("freio (vermelho) e acelerador (verde), 0 a 1", [("brake", "#c0392b"), ("throttle", "#27ae60")], (0, 1)),
            ("volante para dentro da curva, dividido pelo maior da curva", [("_steer", "#2c3e50")], None),
            ("velocidade, km/h", [("speed_kmh", "#8e44ad")], None),
            ("guinada, rad/s (para dentro da curva)", [("_yaw", "#d35400")], None)]
    steer = lap.a("steer")
    dpk = np.nanmax(np.abs(steer[window(track, cp.a, cp.e)])) if steer is not None else np.nan
    series = {"_steer": None if steer is None else -steer[idx] * cp.direcao / dpk,
              "_yaw": None if lap.a("yaw_rate") is None else lap.a("yaw_rate")[idx] * cp.direcao}
    parts = []
    H = len(rows) * (rowh + gap) + 20
    for r, (label, lines, rng) in enumerate(rows):
        top = r * (rowh + gap) + 14
        parts.append(f'<text x="2" y="{top - 3}" font-size="10" fill="#555">{html.escape(label)}</text>')
        parts.append(f'<rect x="0" y="{top}" width="{W}" height="{rowh}" fill="none" stroke="#ddd"/>')
        values = []
        for name, colour in lines:
            v = series.get(name) if name.startswith("_") else (None if lap.a(name) is None else lap.a(name)[idx])
            values.append((v, colour))
        finite = np.concatenate([v[np.isfinite(v)] for v, _ in values if v is not None] or [np.array([0.0])])
        lo, hi = rng if rng else (float(np.min(finite)), float(np.max(finite)))
        if hi - lo < 1e-6:
            hi = lo + 1.0
        for v, colour in values:
            if v is None:
                parts.append(f'<text x="{W/2}" y="{top + rowh/2}" font-size="11" fill="#999" text-anchor="middle">sem o canal</text>')
                continue
            parts.append(_poly(x, v, 0, max(x[-1], 1), lo, hi, W, rowh, top, colour))
        if lo < 0 < hi:
            y0 = top + rowh - (0 - lo) / (hi - lo) * rowh
            parts.append(f'<line x1="0" x2="{W}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="#bbb" stroke-dasharray="2,3"/>')
    for name, s in (("frenagem", cp.b), ("entrada", cp.a), ("meio", cp.m1), ("saida", cp.m2), ("reta", cp.e)):
        off = ahead(track, start, s)
        if off <= x[-1]:
            px = off / max(x[-1], 1) * W
            parts.append(f'<line x1="{px:.1f}" x2="{px:.1f}" y1="10" y2="{H - 14}" stroke="#3498db" stroke-dasharray="4,3"/>')
            parts.append(f'<text x="{px + 2:.1f}" y="{H - 2}" font-size="10" fill="#3498db">{name}</text>')
    return f'<svg viewBox="0 0 {W} {H}" width="100%" style="max-width:{W}px">{"".join(parts)}</svg>'


def map_svg(track: TrackGeometry, cp: CornerPhases) -> str:
    x, z = track.x, -track.z
    x0, x1, z0, z1 = x.min(), x.max(), z.min(), z.max()
    size = 170
    sc = size / max(x1 - x0, z1 - z0)
    def pts(ix):
        return " ".join(f"{(x[i]-x0)*sc:.1f},{(z[i]-z0)*sc:.1f}" for i in ix)
    corner = window(track, cp.b, cp.e)
    return (f'<svg viewBox="-4 -4 {size+8} {size+8}" width="{size}" height="{size}">'
            f'<polyline fill="none" stroke="#bbb" stroke-width="2" points="{pts(range(track.size))}"/>'
            f'<polyline fill="none" stroke="#c0392b" stroke-width="4" points="{pts(corner)}"/></svg>')


def build_kit(states: pd.DataFrame, laps: Dict[str, Lap], track: TrackGeometry, phases: Sequence[CornerPhases],
              out_html: Path, out_csv: Path, out_key: Path) -> Dict[str, object]:
    rng = np.random.default_rng(SEED)
    cp_by = {cp.curva: cp for cp in phases}
    cards, key, rows = [], [], []
    summary = {}
    for det in DETECTORS:
        chosen = select(states, det, rng)
        title, question = QUESTIONS[det]
        cards.append(f'<h2 id="{det}">{det}: {html.escape(title)}</h2><p class="q">{html.escape(question)}</p>')
        summary[det] = {"passagens": int(len(chosen)), "por_estado": chosen["estado"].value_counts().to_dict(),
                        "ia": int((chosen["origem"] == "ia").sum())}
        for n, (_, r) in enumerate(chosen.iterrows(), start=1):
            pid = f"{det}-{n:02d}"
            cp = cp_by[r["curva"]]
            previous = phases[cp.k - 1]
            lap = laps[r["lap_id"]]
            cards.append(
                f'<div class="card"><div class="head"><b>{pid}</b> · curva {html.escape(cp.curva)} '
                f'({"esquerda" if cp.direcao > 0 else "direita"}) · trecho de {cp.b:.0f} m a {cp.e + 100:.0f} m</div>'
                f'<div class="row">{map_svg(track, cp)}<div class="tr">{trace_svg(lap, track, cp, previous)}</div></div></div>')
            key.append({"id": pid, "detector": det, "lap_id": r["lap_id"], "curva": r["curva"], "origem": r["origem"],
                        "estado": r["estado"], "valor_regra": r["valor_regra"]})
            rows.append({"id": pid, "detector": det, "curva": r["curva"], "rotulo": "", "observacao": ""})
    page = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kit de rotulagem</title><style>
body{{font-family:system-ui,sans-serif;margin:16px;max-width:1000px;color:#222;background:#fff}}
.card{{border:1px solid #ddd;border-radius:6px;padding:8px;margin:10px 0}} .head{{margin-bottom:6px}}
.row{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-start}} .tr{{flex:1;min-width:300px}}
.q{{background:#f4f6f8;padding:8px;border-left:4px solid #3498db}}
</style></head><body>
<h1>Kit de rotulagem: 5 detectores, {sum(s['passagens'] for s in summary.values())} passagens</h1>
<p>Para cada passagem, olhe os traços e responda à pergunta do detector com <b>aplica</b>, <b>nao aplica</b> ou <b>nao sei</b>,
na coluna <code>rotulo</code> de <code>{html.escape(out_csv.name)}</code> (na mesma pasta). A coluna <code>observacao</code> é livre.
O kit não mostra o que o detector respondeu nem se a volta é sua ou da IA. As linhas azuis são as fronteiras das fases (frenagem, entrada, meio, saída e reta seguinte).
O volante está dividido pelo maior volante da curva e virado para dentro da curva (positivo = virando para dentro).</p>
{''.join(cards)}</body></html>"""
    out_html.write_text(page, encoding="utf-8")
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "detector", "curva", "rotulo", "observacao"])
        writer.writeheader()
        writer.writerows(rows)
    out_key.write_text(json.dumps(key, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return summary


def precision_recall(labels_csv: Path, key_json: Path) -> Dict[str, object]:
    """Precisao e revocacao de "aplica", nas passagens com rotulo aplica ou nao aplica e estado conclusivo."""
    labels = pd.read_csv(labels_csv, dtype=str).fillna("")
    key = pd.DataFrame(json.loads(key_json.read_text(encoding="utf-8")))
    merged = key.merge(labels[["id", "rotulo"]], on="id")
    norm = merged["rotulo"].str.strip().str.lower().str.replace("ã", "a").str.replace(" ", "_")
    merged["rotulo_n"] = norm.map({"aplica": APLICA, "nao_aplica": NAO_APLICA, "nao_sei": "nao_sei"}).fillna("vazio")
    out = {}
    for det, g in merged.groupby("detector"):
        used = g[g["rotulo_n"].isin([APLICA, NAO_APLICA]) & (g["estado"] != NC)]
        tp = int(((used["estado"] == APLICA) & (used["rotulo_n"] == APLICA)).sum())
        fp = int(((used["estado"] == APLICA) & (used["rotulo_n"] == NAO_APLICA)).sum())
        fn = int(((used["estado"] == NAO_APLICA) & (used["rotulo_n"] == APLICA)).sum())
        out[det] = {"usadas": int(len(used)), "vp": tp, "fp": fp, "fn": fn,
                    "precisao": None if tp + fp == 0 else round(tp / (tp + fp), 3),
                    "revocacao": None if tp + fn == 0 else round(tp / (tp + fn), 3),
                    "nao_sei": int((g["rotulo_n"] == "nao_sei").sum()),
                    "detector_nao_conclusivo": int((g["estado"] == NC).sum()),
                    "sem_rotulo": int((g["rotulo_n"] == "vazio").sum())}
    return out
