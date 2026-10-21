"""Pedido 35, Parte C: quanto cada medida da analise varia de uma volta para outra do proprio piloto.

As voltas humanas do store v2 das sessoes de 11/10 a 18/10, medidas contra a volta da IA
com `core.radio.analise.medidas_da_volta` (as mesmas funcoes do radio). Por sessao e por
curva, o desvio-padrao de cada medida entre as voltas; depois a mediana por medida.
Uso (na pasta backend): python variacao_das_medidas.py <saida.json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, ".")
from core.radio.analise import Pista, grade, medidas_da_volta  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

REPO = Path("..").resolve()
meta = json.load(open(REPO / "data/ml/laps_grid_v2_meta.json", encoding="utf-8"))
laps = pd.DataFrame(meta["laps"])
modelo = json.load(open(REPO / "data/reference_models/vhe_interlagos.json", encoding="utf-8"))
ref_id = modelo["references"]["volta_ia"]["lap_id"] if "references" in modelo else modelo["reference_lap_id"]
sessoes = ["2026-10-11_14-19-52", "2026-10-13_19-24-10", "2026-10-15_23-24-50", "2026-10-17_01-02-22",
           "2026-10-17_16-17-08", "2026-10-18_12-38-44"]
escolhidas = laps[laps.session_id.str[:19].isin(sessoes) & (laps.origem == "humano")]
ids = list(escolhidas.lap_id) + [ref_id]
tabela = pq.read_table(REPO / "data/ml/laps_grid_v2.parquet",
                       columns=["lap_id", "grid_index", "elapsed_s", "speed_kmh", "throttle", "brake", "lateral"],
                       filters=[("lap_id", "in", ids)]).to_pandas()
track = load_geometry(REPO / "data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json")
pista = Pista.da_geometria(track)


def da_tabela(lap_id):
    t = tabela[tabela.lap_id == lap_id].sort_values("grid_index")
    return grade({"elapsed": t.elapsed_s.tolist(), "velocidade": t.speed_kmh.tolist(), "acelerador": t.throttle.tolist(),
                  "freio": t.brake.tolist(), "lateral": t.lateral.tolist()})


tempos = laps.set_index("lap_id").lap_time_s
ref = da_tabela(ref_id)
linhas = []
for lap_id, sid in zip(escolhidas.lap_id, escolhidas.session_id):
    for m in medidas_da_volta(da_tabela(lap_id), float(tempos[lap_id]), ref, float(tempos[ref_id]), pista):
        linhas.append({"sessao": sid[:19], "volta": lap_id, **m})
d = pd.DataFrame(linhas)
medidas = {"freadaM": "freada (m)", "minimaKmh": "minima (km/h)", "aceleradorM": "acelerador cheio (m)",
           "tracadoM": "tracado (m)", "perdaS": "perda (s)"}
desvios = d.groupby(["sessao", "curva"])[list(medidas)].std()
resumo = {nome: {"mediana_do_desvio": round(float(desvios[c].median()), 2),
                 "p75_do_desvio": round(float(desvios[c].quantile(0.75)), 2)}
          for c, nome in medidas.items()}
diferenca_mediana = d.groupby("curva")[list(medidas)].median().round(2)
saida = {"voltas": int(d.volta.nunique()), "sessoes": sessoes, "referencia": ref_id,
         "variacao_volta_a_volta": resumo, "diferenca_mediana_por_curva": diferenca_mediana.to_dict(orient="index")}
Path(sys.argv[1]).write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(resumo, ensure_ascii=False, indent=1))
print(diferenca_mediana.to_string())
