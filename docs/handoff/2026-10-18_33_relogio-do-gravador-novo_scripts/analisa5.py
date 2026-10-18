"""Pedido 33, A.1, A.3 e A.5: intervalo entre amostras e coerencia entre tempo e posicao, sessao a sessao.

O cronometro e a posicao vem da pagina grafica do jogo (iCurrentTime e carCoordinates);
a velocidade, os pedais e o resto da fisica, da pagina de fisica, lida antes
(core/assetto_adapter.py). Aqui:

* o intervalo pelo cronometro (o relogio do jogo), as amostras repetidas e os buracos;
* a coerencia entre o cronometro e a posicao de cada amostra: o deslocamento no
  mundo contra a velocidade vezes o intervalo;
* o atraso entre as duas paginas: o deslocamento d que melhor alinha a velocidade da
  fisica com a velocidade que sai das posicoes e do cronometro.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).parent
dados = {}
for nome in ("novas.pkl", "antigas.pkl", "hoje.pkl"):
    dados.update(pickle.load(open(AQUI / nome, "rb")))

APP = {
    "2026-06-14_12-23-46": "0.1.x (jun)", "2026-08-19_20-58-36": "0.1.7", "2026-10-05_20-33-47": "0.1.7",
    "2026-10-11_14-19-52": "0.1.7", "2026-10-13_19-24-10": "0.1.7",
    "2026-10-15_23-24-50": "0.3.0 (repositorio)", "2026-10-17_01-02-22": "0.3.0 (repositorio)",
    "2026-10-17_16-17-08": "0.4.0 (pacote)", "2026-10-18_12-38-44": "develop + radio (repositorio)",
}


def atraso_da_fisica(c):
    """Atraso (ms) que melhor alinha a velocidade da fisica com a das posicoes.

    Positivo: a fisica mostra o que a pagina grafica so mostra d ms depois (a fisica
    esta adiantada). Ajusta tambem a escala (o speedKmh e o caminho no mundo diferem
    ~0,7% pela geometria).
    """
    resultados = []
    for _, volta in c.groupby("seq"):
        t = volta.lap_time_s.to_numpy(float)
        x, z = volta.x.to_numpy(float), volta.z.to_numpy(float)
        v = volta.speed_kmh.to_numpy(float) / 3.6
        dt = np.diff(t)
        boa = dt > 0
        if boa.sum() < 200:
            continue
        tm = (t[1:] + t[:-1])[boa] / 2
        vg = np.hypot(np.diff(x), np.diff(z))[boa] / dt[boa]
        unico = np.concatenate([[True], np.diff(t) > 0])   # a fisica nos instantes do cronometro, sem repetidas
        tf, vf = t[unico], v[unico]
        resultados.append((tm, vg, tf, vf))
    if not resultados:
        return np.nan
    melhor, menor = np.nan, np.inf
    for d_ms in np.arange(-40, 41, 1):
        erro = []
        for tm, vg, tf, vf in resultados:
            vp = np.interp(tm + d_ms / 1000, tf, vf)
            escala = np.sum(vg * vp) / np.sum(vp * vp)
            erro.append(np.sum((vg - escala * vp) ** 2))
        total = float(np.sum(erro))
        if total < menor:
            melhor, menor = d_ms, total
    return -melhor


linhas = []
for sessao, voltas in sorted(dados.items()):
    partes = [v["cru"].assign(seq=seq) for seq, v in sorted(voltas.items()) if len(v["cru"]) >= 50]
    c = pd.concat(partes, ignore_index=True)
    mesma = c.seq.eq(c.seq.shift())
    d_cron = (1000 * c.lap_time_s).round().diff()
    d_rel = 1000 * c.timestamp_s.diff()
    d_xyz = np.hypot(c.x.diff(), c.z.diff())
    v_media = (c.speed_kmh + c.speed_kmh.shift()) / 2 / 3.6
    andando = (c.speed_kmh > 30) & (c.speed_kmh.shift() > 30)
    ok = mesma & d_cron.notna() & andando
    d_cron, d_rel, d_xyz, v_media = d_cron[ok], d_rel[ok], d_xyz[ok], v_media[ok]
    rep = d_cron == 0
    andou = d_cron > 0
    erro_ms = 1000 * (d_xyz[andou] - v_media[andou] * d_cron[andou] / 1000) / v_media[andou]
    rapido = c[c.speed_kmh > 30]
    linhas.append({
        "sessao": sessao[:19], "app": APP.get(sessao[:19], "?"), "pares de amostras": int(ok.sum()),
        "intervalo mediano (ms)": float(d_cron[andou].median()),
        "intervalo multiplo de 3 ms (%)": round(100 * float((np.mod(d_cron[andou], 3) == 0).mean()), 1),
        "intervalo p1 / p99 (ms)": f"{np.percentile(d_cron[andou], 1):.0f} / {np.percentile(d_cron[andou], 99):.0f}",
        "repetidas: mesmo cronometro e lugar (%)": round(100 * float((rep & (d_xyz < 1e-6)).mean()), 2),
        "cronometro parado e carro andou (%)": round(100 * float((rep & (d_xyz >= 1e-6)).mean()), 3),
        "buracos >= 50 ms (%)": round(100 * float((d_cron >= 50).mean()), 3),
        "maior buraco (ms)": float(d_cron.max()),
        "tempo x posicao: |erro| p99 (ms)": round(float(np.percentile(np.abs(erro_ms), 99)), 2),
        "tempo x posicao: acima de 3 ms (%)": round(100 * float((np.abs(erro_ms) > 3).mean()), 3),
        "relogio do gravador - cronometro, p99 (ms)": round(float(np.percentile(np.abs((d_rel - d_cron)[andou]), 99)), 1),
        "fisica adiantada sobre posicao e tempo (ms)": atraso_da_fisica(rapido),
    })

t = pd.DataFrame(linhas)
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 40)
print(t.set_index("sessao").T.to_string())
t.to_csv(AQUI / "intervalos_por_sessao.csv", index=False)
