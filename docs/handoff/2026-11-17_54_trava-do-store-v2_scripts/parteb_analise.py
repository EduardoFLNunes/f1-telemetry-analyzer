import json
import sys

import numpy as np
import pandas as pd

csv, meta_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
df = pd.read_csv(csv)
REG = 1.463
df = df[np.isfinite(df["linha_m"])]
df["dif_m"] = df["linha_m"] - REG
df["v_ms"] = df["v_kmh"] / 3.6
df["atraso_ms"] = np.where(df["v_ms"] > 0, 1000 * df["dif_m"] / df["v_ms"], np.nan)
df["data"] = df["sessao"].str.slice(0, 10)
df["ia"] = df["ia_frac"] >= 0.999
df["copia"] = df["pista"].astype(str).str.contains("teste_m1")

meta = json.load(open(meta_path, encoding="utf-8"))
print("meta keys:", [k for k in meta.keys()][:40])

g = df.groupby("sessao")
tab = pd.DataFrame({
    "data": g["data"].first(), "pasta": g["pasta"].first(), "pista": g["pista"].first(),
    "app": g["app"].first(), "empacotado": g["app_empacotado"].first(),
    "voltas": g.size(), "voltas_ia": g["ia"].sum(),
    "mediana_m": g["linha_m"].median(), "desvio_m": g["linha_m"].std(ddof=0),
    "v_mediana_kmh": g["v_kmh"].median(), "atraso_mediano_ms": g["atraso_ms"].median(),
}).sort_values("data")
tab["fora"] = (tab["mediana_m"] - REG).abs() > 0.10
pd.set_option("display.width", 250, "display.max_rows", 300, "display.max_columns", 30)
print(tab[tab["voltas"] >= 3].round(3).to_string())
tab.round(4).to_csv(out)

# A data exata: ultima que passa e primeira que reprova (sessoes com >= 3 voltas, pista original).
orig = tab[(tab["voltas"] >= 3) & (~tab["pista"].astype(str).str.contains("teste_m1"))]
print("\nultimas 8 da pista original:")
print(orig.tail(12).round(3).to_string())

# Antes e depois da instalacao do CSP 0.3.1 (31/10 19:52), por grupo.
df["depois_csp"] = df["sessao"] > "2026-10-31_19-52"
for (dep, cop, ia), sub in df.groupby(["depois_csp", "copia", "ia"]):
    print(f"depois_csp={dep} copia={cop} ia={ia}: n={len(sub)} mediana={sub.linha_m.median():.3f} m "
          f"desvio={sub.linha_m.std(ddof=0):.3f} atraso={sub.atraso_ms.median():.2f} ms v={sub.v_kmh.median():.0f}")
for (dep, app), sub in df.groupby(["depois_csp", "app"]):
    print(f"depois_csp={dep} app={app}: n={len(sub)} sessoes={sub.sessao.nunique()} mediana={sub.linha_m.median():.3f}")
for (dep, pasta), sub in df.groupby(["depois_csp", "pasta"]):
    print(f"depois_csp={dep} pasta={pasta}: n={len(sub)} sessoes={sub.sessao.nunique()} mediana={sub.linha_m.median():.3f}")

# O discriminador: a diferenca cresce com a velocidade? (espaco: constante em m; tempo: constante em ms)
for dep in (False, True):
    sub = df[(df["depois_csp"] == dep) & (df["v_kmh"] > 100)]
    b, a = np.polyfit(sub["v_ms"], sub["linha_m"], 1)
    lo = sub[sub.v_kmh < sub.v_kmh.quantile(0.25)]
    hi = sub[sub.v_kmh > sub.v_kmh.quantile(0.75)]
    print(f"\ndepois_csp={dep}: linha = {a:.3f} + {b * 1000:.2f} ms x v  (n={len(sub)}, v de {sub.v_kmh.min():.0f} a "
          f"{sub.v_kmh.max():.0f} km/h); quartil lento v={lo.v_kmh.median():.0f} linha={lo.linha_m.median():.3f}; "
          f"quartil rapido v={hi.v_kmh.median():.0f} linha={hi.linha_m.median():.3f}")
# Diferenca entre depois e antes, por faixa de velocidade.
bins = [100, 200, 230, 250, 265, 400]
df["faixa"] = pd.cut(df["v_kmh"], bins)
piv = df[df.v_kmh > 100].pivot_table(index="faixa", columns="depois_csp", values="linha_m", aggfunc=["median", "count"],
                                     observed=True)
print("\npor faixa de velocidade:\n", piv.round(3).to_string())
