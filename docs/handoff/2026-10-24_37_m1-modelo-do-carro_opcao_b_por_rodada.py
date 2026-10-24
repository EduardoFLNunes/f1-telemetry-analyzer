# Opcao (b), so diagnostico, so as 4 sessoes de treino de cada rodada: a regressao da secao 1.4
# com a complacencia dividida pela carga do eixo (que cresce com a aerodinamica):
#   vy = b*r + c_r*vx*a_y/n_r(v) + d          (vy + a*r)/vx = k_delta*(-steer) + c_f*a_y/n_f(v) + d
# com n_f, n_r por massa medidos nas cargas (w_f, kappa_L, f_aero da mesma rodada). Nada disto foi adotado.
import sys, json
sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
import numpy as np, pandas as pd
from ml.modelo_carro import dados as D, convencoes as C, geometria as Ge
from ml.scripts.m1_modelo_carro import grade_path
G = D.G
conv = C.Convencoes(**json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\modelo_carro\convencoes.json", encoding="utf-8"))["convencoes"])
grades = {s: pd.read_parquet(grade_path(s)) for s in D.SESSOES_M1}
rng = np.random.default_rng(37)
for test in D.SESSOES_M1:
    f = C.no_modelo(pd.concat([grades[s] for s in D.SESSOES_M1 if s != test], ignore_index=True), conv)
    geo = Ge.medir(f, bootstrap=1)
    v2 = f.vx.to_numpy() ** 2
    n_f = G * geo["w_f"] + geo["kappa_L"] * geo["f_aero"] * v2
    n_r = G * (1 - geo["w_f"]) + geo["kappa_L"] * (1 - geo["f_aero"]) * v2
    sel = ((f.a_y.abs() <= 0.5 * G) & (f.vx >= 10) & (f.B < 0.05)).to_numpy()
    vx, vy, r, a_y, st, lap = (f[c].to_numpy()[sel] for c in ("vx", "vy", "r", "a_y", "steer", "lap_id"))
    def fit(idx):
        cb = np.linalg.lstsq(np.column_stack([r[idx], vx[idx] * a_y[idx] / n_r[sel][idx], np.ones(idx.size)]), vy[idx], rcond=None)[0]
        b = cb[0]; L = b / geo["w_f"]; a = L - b
        ck = np.linalg.lstsq(np.column_stack([-st[idx], a_y[idx] / n_f[sel][idx], np.ones(idx.size)]), (vy[idx] + a * r[idx]) / vx[idx], rcond=None)[0]
        return b, L, ck[0]
    allidx = np.arange(vx.size)
    b, L, k = fit(allidx)
    laps = np.unique(lap); draws = []
    for _ in range(200):
        pick = rng.choice(laps, laps.size)
        idx = np.concatenate([np.flatnonzero(lap == p) for p in pick])
        draws.append(fit(idx))
    d = np.array(draws)
    ci = lambda i: (round(float(np.percentile(d[:, i], 2.5)), 3), round(float(np.percentile(d[:, i], 97.5)), 3))
    print(f"sem {test[:19]}: b={b:.3f} m {ci(0)}  L={L:.3f} m {ci(1)}  k_delta={k:.4f} rad ({np.degrees(k):.1f} graus) {ci(2)}")
