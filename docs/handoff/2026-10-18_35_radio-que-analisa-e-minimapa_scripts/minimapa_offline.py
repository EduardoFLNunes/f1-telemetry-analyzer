"""Pedido 35, Parte E/F: a conta do minimapa do jogo, portada do Lua, numa sessao gravada.

O app do jogo nao roda fora do jogo (nao ha Lua aqui). Este script repete, linha a linha,
as contas de `radio_engenheiro.lua`:

* o fantasma pelo tempo: tempo da referencia = cronometro do jogo + `tempoNaLinhaDoJogoS`,
  sobre os pontos `[x, z, t]` que a rota `/api/radio/minimapa` manda (`fantasmaEm`);
* a diferenca ao vivo: o tempo do carro menos o da referencia no ponto dela mais perto do
  carro, projetado no segmento, com a busca na vizinhanca do ultimo ponto
  (`tempoDaReferenciaPerto`);
* o fantasma so depois da primeira passagem pela linha (`acompanharAVolta`).

E compara com a conta da grade (a da tela Volta): o s do carro pela linha central oficial
(o ponto mais perto) e o tempo da referencia nesse s, pela grade do store.

Uso (na pasta backend): python minimapa_offline.py <pasta da sessao> <saida.json> [<minimapa.json>]
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.getcwd())

from core.assisted_analysis.reference_model import DriverReferenceModel, model_path  # noqa: E402
from core.leitura.arquivos import LeitorDoStore  # noqa: E402
from core.radio import minimapa  # noqa: E402
from core.radio.analise import Pista  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

REPO = Path(os.getcwd()).parent
PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SESSAO = PASTA.name
DIFERENCA_MAXIMA_S = 20
LONGE_DA_REFERENCIA_M = 60

track = carregar_geometria(REPO)
pista = Pista.da_geometria(track)
modelo = DriverReferenceModel.load(model_path(REPO, "vhe_interlagos"))
ref_id = str(modelo.reference_lap_id)
volta_ref = LeitorDoStore().ler_volta(REPO, ref_id)
linha_m = minimapa.linha_do_jogo_m(REPO)
mm = minimapa.montar(track, pista.segmentos, volta_ref, modelo.reference_kind, None, linha_m)
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(json.dumps(mm, separators=(",", ":")), encoding="utf-8")
ref = mm["referencia"]
pontos = ref["pontos"]
na_linha = ref["tempoNaLinhaDoJogoS"]

# ── o Lua, linha a linha ──────────────────────────────────────────────────
estado = {"iFantasma": 1, "iCarro": None}


def fantasma_em(t_ref):
    n = len(pontos)
    i = estado["iFantasma"]
    if i < 1 or i >= n or pontos[i - 1][2] > t_ref:
        i = 1
    while i < n - 1 and pontos[i][2] <= t_ref:
        i += 1
    estado["iFantasma"] = i
    a, b = pontos[i - 1], pontos[i]
    u = 0.0
    if b[2] > a[2]:
        u = max(0.0, min(1.0, (t_ref - a[2]) / (b[2] - a[2])))
    return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u


def melhor_entre(x, z, de, ate):
    melhor, tempo, indice = math.inf, None, None
    for i in range(de, ate + 1):
        p, q = pontos[i - 1], pontos[i]
        dx, dz = q[0] - p[0], q[1] - p[1]
        l2 = dx * dx + dz * dz
        u = 0.0
        if l2 > 0:
            u = max(0.0, min(1.0, ((x - p[0]) * dx + (z - p[1]) * dz) / l2))
        ex, ez = p[0] + dx * u - x, p[1] + dz * u - z
        d2 = ex * ex + ez * ez
        if d2 < melhor:
            melhor, tempo, indice = d2, p[2] + (q[2] - p[2]) * u, i
    return melhor, tempo, indice


def tempo_da_referencia_perto(x, z):
    n = len(pontos)
    d2, tempo, indice = math.inf, None, None
    if estado["iCarro"]:
        d2, tempo, indice = melhor_entre(x, z, max(1, estado["iCarro"] - 8), min(n - 1, estado["iCarro"] + 25))
    if d2 > 30 * 30:
        d2, tempo, indice = melhor_entre(x, z, 1, n - 1)
    estado["iCarro"] = indice
    if d2 > LONGE_DA_REFERENCIA_M ** 2:
        return None
    return tempo


# ── a conta da grade (a tela Volta) ──────────────────────────────────────
centro = cKDTree(np.column_stack([track.x, track.z]))
s_grade = np.asarray(track.s, dtype=float)
el = np.array([np.nan if v is None else float(v) for v in volta_ref["elapsedS"]], dtype=float)
ok = np.isfinite(el)
el = np.interp(np.arange(el.size), np.arange(el.size)[ok], el[ok])
fantasma_grade_xy = None

sessao = Session(session_id=SESSAO, directory=PASTA, track="vhe_interlagos")
voltas_vistas, desde_a_linha = None, False
amostras, por_volta, fantasmas = [], {}, []
for lap in iter_laps(sessao):
    for d in lap.frame.to_dict("records"):
        x, z, tv, nv = d.get("x"), d.get("z"), d.get("lap_time_s"), d.get("lap_number")
        if x is None or z is None or tv is None or nv is None or x != x or z != z or tv != tv:
            continue
        x, z, tv, nv = float(x), float(z), float(tv), int(nv)
        if voltas_vistas is not None and nv > voltas_vistas:
            desde_a_linha = True
            estado["iFantasma"] = 1
        voltas_vistas = nv
        if not desde_a_linha or d.get("ai_controlled"):
            continue
        t_carro = tv + na_linha
        fx, fz = fantasma_em(t_carro)
        t_ref = tempo_da_referencia_perto(x, z)
        dist, k = centro.query([x, z])
        s = s_grade[k]
        dif_grade = t_carro - float(np.interp(s, s_grade, el))
        # o fantasma ao longo da pista: o s do ponto do app contra o s da referencia neste tempo, pela grade
        s_f = float(np.interp(min(t_carro, el[-1]), el, s_grade))
        s_app = s_grade[centro.query([fx, fz])[1]]
        erro_fantasma = abs((s_app - s_f + track.length / 2) % track.length - track.length / 2)
        if t_ref is None:
            continue
        dif_app = t_carro - t_ref
        if abs(dif_app) >= DIFERENCA_MAXIMA_S:
            continue
        perto_da_emenda = min(s, track.length - s) < 5.0   # a grade emenda no s = 0; o app nao usa a grade
        amostras.append((nv, s, dif_app, dif_grade, erro_fantasma, perto_da_emenda, float(dist)))
        por_volta[nv] = (tv, s, dif_app, dif_grade)

todas = np.array([[v[2], v[3], v[4], v[5]] for v in amostras])
a = todas[todas[:, 3] == 0]
dif = np.abs(a[:, 0] - a[:, 1])
fim = {}
for nv, (tv, s, dapp, dgr) in sorted(por_volta.items()):
    fim[nv] = {"cronometroNoUltimoQuadroS": round(tv, 3), "sNoUltimoQuadroM": round(float(s), 1),
               "diferencaDoAppS": round(dapp, 3), "diferencaDaGradeS": round(dgr, 3)}
resultado = {
    "sessao": SESSAO,
    "referencia": {"tipo": ref["tipo"], "lapId": ref["lapId"], "tempoS": ref["tempoS"],
                   "tempoNaLinhaDoJogoS": na_linha, "linhaDoJogoM": mm["linhaDoJogoM"], "pontos": len(pontos)},
    "pistaPontosPorBorda": len(mm["pista"]["esquerda"]),
    "amostrasComparadas": int(len(a)),
    "amostrasAMenosDe5mDoS0ForaDaComparacao": int((todas[:, 3] == 1).sum()),
    "appMenosGradeS": {"mediana": round(float(np.median(dif)), 4), "p95": round(float(np.percentile(dif, 95)), 4),
                       "maximo": round(float(dif.max()), 4)},
    "fantasmaAoLongoDaPistaContraGradeM": {"mediana": round(float(np.median(a[:, 2])), 2),
                             "p95": round(float(np.percentile(a[:, 2], 95)), 2)},
    # onde o app e a grade se afastam mais de 0,5 s: a distancia do carro a linha central diz se e fora da pista
    "acimaDe0_5s": [{"volta": v[0], "sM": round(float(v[1]), 1), "appS": round(v[2], 3), "gradeS": round(v[3], 3),
                     "carroALinhaCentralM": round(v[6], 1)} for v in amostras
                    if not v[5] and abs(v[2] - v[3]) > 0.5][:40],
    "quantasAcimaDe0_5s": sum(1 for v in amostras if not v[5] and abs(v[2] - v[3]) > 0.5),
    "fimDeCadaVolta": fim,
}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in resultado.items() if k != "fimDeCadaVolta"}, ensure_ascii=False))
