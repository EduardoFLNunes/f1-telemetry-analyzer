# A geometria medida pela regra registrada (1.4), em cada rodada, so com as 4 sessoes de treino.
import sys, json
sys.path.insert(0, r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\backend")
import pandas as pd
from ml.modelo_carro import dados as D, convencoes as C, geometria as Ge
from ml.scripts.m1_modelo_carro import grade_path
conv = C.Convencoes(**json.load(open(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml\modelo_carro\convencoes.json", encoding="utf-8"))["convencoes"])
grades = {s: pd.read_parquet(grade_path(s)) for s in D.SESSOES_M1}
out = {}
for test in D.SESSOES_M1:
    frame = C.no_modelo(pd.concat([grades[s] for s in D.SESSOES_M1 if s != test], ignore_index=True), conv)
    out[f"sem {test[:19]}"] = Ge.medir(frame)
json.dump(out, open(sys.argv[1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for k, v in out.items():
    u = v["incerteza_bootstrap"]
    print(k, {n: round(v[n], 4) for n in ("m", "kappa_L", "w_f", "f_aero", "h_L", "b", "L", "k_delta")},
          "IC b", round(u["b"]["p2_5"], 2), round(u["b"]["p97_5"], 2), "IC L", round(u["L"]["p2_5"], 2), round(u["L"]["p97_5"], 2))
