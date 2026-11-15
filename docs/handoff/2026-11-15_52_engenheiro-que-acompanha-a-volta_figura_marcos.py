"""Pedido 52, Parte B.3: os marcos sobre a pista (a geometria oficial com as bordas do corredor).

O `map.png` da pista nao foi lido: ele fica fora da excecao de leitura do pedido (so os dois kn5).
A pista e desenhada pela propria geometria oficial (a linha central e as bordas).

Uso (na pasta backend): python <este arquivo> <saida.png>
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, ".")
from core.radio.janelas import carregar_geometria  # noqa: E402

REPO = Path("..").resolve()
track = carregar_geometria(REPO)
d = json.loads((REPO / "data" / "reference_models" / "vhe_interlagos.marcos.json").read_text(encoding="utf-8"))
P = np.c_[track.x, track.z]
N = np.asarray(track.normal)
esq = P + N * np.asarray(track.width_left)[:, None]
dire = P - N * np.asarray(track.width_right)[:, None]
fig, ax = plt.subplots(figsize=(14, 12), dpi=110)
for borda in (esq, dire):
    ax.plot(np.r_[borda[:, 0], borda[0, 0]], np.r_[borda[:, 1], borda[0, 1]], color="#555", lw=0.8)
ax.plot(P[:, 0], P[:, 1], color="#bbb", lw=0.5, ls="--")
cores = {"placa": "#d62728", "placa_drs": "#1f77b4", "passarela": "#9467bd", "portico": "#000000", "posto": "#2ca02c"}
for m in d["marcos"]:
    if m["tipo"] == "zebra":
        s = np.arange(m["s"], m["s"] + m["comprimentoM"] + 1e-6, 2.0)
        lat = np.full(s.shape, m["lateralM"])
        w = track.to_world(s, lat)
        ax.plot(w[:, 0], w[:, 1], color="#ff7f0e", lw=2.2, alpha=0.8)
        continue
    x, z = m["x"], m["z"]
    if m["tipo"] in ("passarela", "portico"):
        k = int(track.index_of(m["s"]))
        a, b = P[k] + N[k] * 16, P[k] - N[k] * 16
        ax.plot([a[0], b[0]], [a[1], b[1]], color=cores[m["tipo"]], lw=3)
    ax.plot(x, z, "o", color=cores[m["tipo"]], ms=6)
    rot = {"placa": str(m.get("valor")), "placa_drs": "DRS", "passarela": "passarela", "portico": "pórtico",
           "posto": "posto"}[m["tipo"]]
    ax.annotate(f"{rot} ({m['s']:.0f})", (x, z), fontsize=7, xytext=(4, 4), textcoords="offset points",
                color=cores[m["tipo"]])
for label, cor in [("placa de freada", "#d62728"), ("placa do DRS", "#1f77b4"), ("passarela", "#9467bd"),
                   ("pórtico", "#000000"), ("posto de bandeira", "#2ca02c"), ("zebra", "#ff7f0e")]:
    ax.plot([], [], color=cor, lw=3, label=label)
ax.legend(loc="lower left")
ax.set_aspect("equal")
ax.set_title(f"Os marcos da pista (pedido 52): {len(d['marcos'])} marcos na geometria {d['geometry_id']}")
ax.set_xlabel("x (m)")
ax.set_ylabel("z (m)")
fig.tight_layout()
fig.savefig(sys.argv[1])
print(sys.argv[1])
