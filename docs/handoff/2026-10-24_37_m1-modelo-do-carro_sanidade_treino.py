# Sanidade da fisica so nas sessoes de treino da rodada 1 (a 1a sessao fica de fora e nao e lida).
import sys, time, json
sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
import numpy as np, pandas as pd
from ml.modelo_carro import dados as D, convencoes as C, geometria as Ge, fisica as F, validacao as V
from ml.optimization.vehicle_model import fit_envelope
from ml.scripts.m1_modelo_carro import grade_path
conv = C.Convencoes(**json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\modelo_carro\convencoes.json", encoding="utf-8"))["convencoes"])
train = D.SESSOES_M1[1:]
frame = C.no_modelo(pd.concat([pd.read_parquet(grade_path(s)) for s in train], ignore_index=True), conv)
geo = Ge.medir(frame)
print(json.dumps({k: v for k, v in geo.items() if k != "incerteza_bootstrap"}, indent=1, default=float))
print(json.dumps(geo["incerteza_bootstrap"], indent=1))
store = pd.read_parquet(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\laps_grid_v2.parquet", columns=["lap_id","speed_kmh","lateral_g","longitudinal_g","throttle","brake"])
laps = frame["lap_id"].unique()
env = fit_envelope(store[store["lap_id"].isin(laps)], source_laps=len(laps))
print(env.describe())
sigma = frame[["vx","vy","r"]].std().to_numpy()
print("sigma", sigma)
P = V.passos(frame)
print("passos", len(P), pd.Series(P.regime).value_counts().to_dict())
base = F.Parametros(m=geo["m"], kappa_L=geo["kappa_L"], w_f=geo["w_f"], f_aero=geo["f_aero"], h_L=geo["h_L"], b=geo["b"], L=geo["L"],
                    k_delta=geo["k_delta"], brake_bias=geo["brake_bias"], env_speed=env.speed_mps, env_traction=env.traction)
t0=time.time()
fit = F.ajustar_fisica(base, P.S0, P.U, P.S1, sigma)
print("ajuste", time.time()-t0, "s", fit.erro_um_passo, fit.sem_transferencia, fit.com_transferencia, fit.no_limite, fit.params.transferencia)
print({n: getattr(fit.params, n) for n,*_ in F.AJUSTADOS})
# persistencia no 1 passo
print("R0 1 passo", np.sqrt(np.mean(((P.S0-P.S1)/sigma)**2)))
cs = V.casos(frame, conv)
print("casos treino", len(cs))
r1,_ = F.malha_aberta(cs.S0, cs.U[:, :20], fit.params)
r0 = F.persistencia(cs.S0, 20)
for name,h in V.HORIZONTES.items():
    e1=V.erro_combinado(r1,cs.S,sigma,h); e0=V.erro_combinado(r0,cs.S,sigma,h)
    print(name, "R1", e1, "R0", e0, "skill R1 vs R0", V.skill(e1,e0), V.por_grandeza(r1,cs.S,h))
