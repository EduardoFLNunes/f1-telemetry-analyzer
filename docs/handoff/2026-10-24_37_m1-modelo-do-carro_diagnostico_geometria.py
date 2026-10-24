# Diagnostico (so as 4 sessoes de treino da rodada 1): por que b sai ~0, e o que acontece
# se L e k_delta forem ajustados junto com a fisica (b = w_f * L).
import sys, time, json
sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
import numpy as np, pandas as pd
from dataclasses import replace
from scipy.optimize import least_squares
from ml.modelo_carro import dados as D, convencoes as C, geometria as Ge, fisica as F, validacao as V
from ml.optimization.vehicle_model import fit_envelope
from ml.scripts.m1_modelo_carro import grade_path
conv = C.Convencoes(**json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\modelo_carro\convencoes.json", encoding="utf-8"))["convencoes"])
train = D.SESSOES_M1[1:]
frame = C.no_modelo(pd.concat([pd.read_parquet(grade_path(s)) for s in train], ignore_index=True), conv)
G=D.G
# 1) b por faixa de velocidade, regressao simples vy = b r + d (|a_y|<=0.5g, freio<0.05)
sel = (frame.a_y.abs()<=0.5*G)&(frame.vx>=10)&(frame.B<0.05)
out={}
for lo,hi in [(10,30),(30,45),(45,60),(60,90)]:
    s = sel&(frame.vx>=lo)&(frame.vx<hi)
    X=np.column_stack([frame.r[s],np.ones(s.sum())]); c=np.linalg.lstsq(X,frame.vy[s],rcond=None)[0]
    out[f"{lo}-{hi} m/s"]={"n":int(s.sum()),"inclinacao_vy_r":float(c[0]),"r_desvio":float(frame.r[s].std())}
print("vy contra r por faixa:", json.dumps(out,indent=0))
# 2) vy/vx contra a_y em curvas (deriva no centro de referencia), por faixa
for lo,hi in [(15,30),(30,45),(45,60)]:
    s=(frame.vx>=lo)&(frame.vx<hi)&(frame.B<0.05)&(frame.a_y.abs()>0.3*G)
    k=np.polyfit(frame.a_y[s], frame.vy[s]/frame.vx[s],1)
    print(f"beta contra a_y {lo}-{hi}: inclinacao {k[0]:.5f} rad/(m/s2), n={s.sum()}")
geo = Ge.medir(frame, bootstrap=0) if False else None
store = pd.read_parquet(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\laps_grid_v2.parquet", columns=["lap_id","speed_kmh","lateral_g","longitudinal_g","throttle","brake"])
laps = frame["lap_id"].unique()
env = fit_envelope(store[store["lap_id"].isin(laps)], source_laps=len(laps))
sigma = frame[["vx","vy","r"]].std().to_numpy()
P = V.passos(frame)
w_f=0.4277
base = F.Parametros(m=648, kappa_L=0.00301, w_f=w_f, f_aero=0.442, h_L=0.135, b=1.45, L=3.4, k_delta=0.3, brake_bias=0.55, env_speed=env.speed_mps, env_traction=env.traction)
names=[n for n,*_ in F.AJUSTADOS]+["L","k_delta"]
lo=np.array([x[2] for x in F.AJUSTADOS]+[2.8,0.05]); hi=np.array([x[3] for x in F.AJUSTADOS]+[3.8,1.5]); st=np.array([x[4] for x in F.AJUSTADOS]+[3.3,0.3])
def mk(th): return base.com(th[:7], L=float(th[7]), b=float(w_f*th[7]), k_delta=float(th[8]))
def res(th): return ((F.passo(P.S0,P.U,mk(th))-P.S1)/sigma).ravel()
t0=time.time(); r=least_squares(res,st,bounds=(lo,hi),x_scale=np.maximum(np.abs(st),1e-3),max_nfev=400)
p=mk(r.x); print("ajuste com L e k_delta livres", round(time.time()-t0), "s", dict(zip(names,np.round(r.x,4))))
print("erro 1 passo", F.erro_um_passo(p,P.S0,P.U,P.S1,sigma), "persistencia", np.sqrt(np.mean(((P.S0-P.S1)/sigma)**2)))
e1=np.sqrt(np.mean(((F.passo(P.S0,P.U,p)-P.S1)/sigma)**2,axis=0)); e0=np.sqrt(np.mean(((P.S0-P.S1)/sigma)**2,axis=0)); print("por grandeza 1 passo R1",e1,"R0",e0)
cs=V.casos(frame,conv)
r1,_=F.malha_aberta(cs.S0,cs.U,p); r0=F.persistencia(cs.S0,20)
for name,h in V.HORIZONTES.items():
    a=V.erro_combinado(r1,cs.S,sigma,h); b=V.erro_combinado(r0,cs.S,sigma,h); print(name,"R1",round(a,4),"R0",round(b,4),"skill",round(V.skill(a,b),3), {k:round(v['rmse'],3) for k,v in V.por_grandeza(r1,cs.S,h).items()}, {k:round(v['rmse'],3) for k,v in V.por_grandeza(r0,cs.S,h).items()})
