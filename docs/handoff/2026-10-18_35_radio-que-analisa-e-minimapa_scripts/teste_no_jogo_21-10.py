"""Pedido 35, Parte G (depois do aviso): a gravacao e o FPS do teste no jogo de 21/10.

* **Os blocos,** pelo log do backend (as linhas de acesso do uvicorn, intercaladas com as
  linhas datadas): a tela Ao vivo pede `/api/live/volta/novos` cerca de 28 vezes por
  segundo; com outra tela aberta, nao pede. Ao vivo de 20:31 a 21:03; outra tela de
  21:04 a 21:17. Os limites vao como argumentos.
* **A gravacao,** com as medidas do pedido 33 (`analisa5.py`): o intervalo pelo
  cronometro do jogo, as amostras repetidas, os buracos de 50 ms ou mais e o relogio do
  gravador contra o cronometro (p99). A sessao de 18/10 (antes deste pedido) entra como
  referencia.
* **O FPS do jogo,** pelas linhas `fps:` do app no log do CSP (a hora e o comeco do log
  mais o contador em ms, em hexadecimal), por bloco e pelos mapas ligados ou desligados.

Uso (na pasta backend): python teste_no_jogo_21-10.py <log do CSP> <saida.json>
"""
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from ml.data.recordings import Session, iter_laps  # noqa: E402

LOG, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
DIA = "2026-10-21"
BLOCOS = {"tela Ao vivo aberta": ("20:31:00", "21:03:30"), "tela Sessoes (outra tela)": ("21:04:00", "21:17:59")}


def momento(hhmmss: str) -> datetime:
    return datetime.strptime(f"{DIA} {hhmmss}", "%Y-%m-%d %H:%M:%S")


def medidas(c: pd.DataFrame) -> dict:
    mesma = c.seq.eq(c.seq.shift())
    d_cron = (1000 * c.lap_time_s).round().diff()
    d_rel = 1000 * c.timestamp_s.diff()
    d_xyz = np.hypot(c.x.diff(), c.z.diff())
    andando = (c.speed_kmh > 30) & (c.speed_kmh.shift() > 30)
    ok = mesma & d_cron.notna() & andando
    d_cron, d_rel, d_xyz = d_cron[ok], d_rel[ok], d_xyz[ok]
    rep = d_cron == 0
    andou = d_cron > 0
    return {
        "pares de amostras": int(ok.sum()),
        "intervalo mediano (ms)": float(d_cron[andou].median()),
        "intervalo p99 (ms)": float(np.percentile(d_cron[andou], 99)),
        "repetidas: mesmo cronometro e lugar (%)": round(100 * float((rep & (d_xyz < 1e-6)).mean()), 2),
        "cronometro parado e carro andou (%)": round(100 * float((rep & (d_xyz >= 1e-6)).mean()), 3),
        "buracos >= 50 ms (%)": round(100 * float((d_cron >= 50).mean()), 3),
        "maior buraco (ms)": float(d_cron.max()),
        "relogio do gravador - cronometro, p99 (ms)": round(float(np.percentile(np.abs((d_rel - d_cron)[andou]), 99)), 1),
    }


def amostras(pasta: Path) -> pd.DataFrame:
    partes = []
    for seq, lap in enumerate(iter_laps(Session(session_id=pasta.name, directory=pasta, track="vhe_interlagos"))):
        f = lap.frame
        if len(f) >= 50:
            partes.append(f[["lap_time_s", "timestamp_s", "x", "z", "speed_kmh"]].assign(seq=seq))
    return pd.concat(partes, ignore_index=True)


raiz = Path("..") / "data" / "recordings"
teste = amostras(raiz / "2026-10-21_20-30-54_vhe_interlagos")
# A hora de parede: o relogio do gravador ancorado no nome da pasta (20:30:54, a hora dos logs).
# O timestamp_s desta gravacao, convertido como hora UTC, da 3 h a mais; a ancora evita depender disso.
bruto = pd.to_datetime(teste.timestamp_s, unit="s")
quando = bruto - bruto.min() + datetime(2026, 10, 21, 20, 30, 53)   # a primeira amostra: 20:30:53
resultado = {"gravacao": {}, "fps": {}}
for nome, (a, b) in BLOCOS.items():
    dentro = (quando >= momento(a)) & (quando <= momento(b))
    bloco = teste[dentro]
    voltas = bloco.groupby("seq").lap_time_s.max()
    resultado["gravacao"][nome] = {"de": a, "ate": b, "voltas (inteiras ou em parte)": int(voltas.size), **medidas(bloco)}
resultado["gravacao"]["18/10, antes deste pedido (referencia)"] = medidas(amostras(raiz / "2026-10-18_12-38-44_vhe_interlagos"))

# O FPS: o log do CSP comeca com a hora; cada linha traz o contador em ms (hexadecimal).
texto = LOG.read_bytes().decode("utf-8", errors="replace")
inicio = re.search(r"date & time: (\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d):(\d{3})", texto)
t0 = datetime.strptime(f"{inicio.group(1)} {inicio.group(2)}", "%Y-%m-%d %H:%M:%S") + timedelta(milliseconds=int(inicio.group(3)))
linhas = []
for m in re.finditer(r"^\s*([0-9a-f]+)\s+M .*?fps: média ([\d,]+) \(mín (\d+), máx (\d+)\) em (\d+) s; minimapa ([a-z ]+); mapa aproximado ([a-z ]+)$",
                     texto, re.MULTILINE):
    hora = t0 + timedelta(milliseconds=int(m.group(1), 16))
    linhas.append({"hora": hora, "media": float(m.group(2).replace(",", ".")), "min": int(m.group(3)),
                   "max": int(m.group(4)), "minimapa": m.group(6).strip(), "aproximado": m.group(7).strip()})
fps = pd.DataFrame(linhas)
fps["bloco"] = "fora dos blocos"
for nome, (a, b) in BLOCOS.items():
    fps.loc[(fps.hora >= momento(a)) & (fps.hora <= momento(b)), "bloco"] = nome
fps["mapas"] = "minimapa " + fps.minimapa + " / aproximado " + fps.aproximado
for (bloco, mapas), g in fps.groupby(["bloco", "mapas"]):
    resultado["fps"].setdefault(bloco, {})[mapas] = {"janelas de 10 s": int(len(g)), "media": round(float(g.media.mean()), 1),
                                                     "mediana": round(float(g.media.median()), 1), "minimo": int(g["min"].min())}
for bloco, g in fps.groupby("bloco"):
    resultado["fps"][bloco]["todas"] = {"janelas de 10 s": int(len(g)), "media": round(float(g.media.mean()), 1),
                                        "mediana": round(float(g.media.median()), 1), "minimo": int(g["min"].min())}
resultado["fps_linhas"] = len(fps)
resultado["fps_de"], resultado["fps_ate"] = str(fps.hora.min()), str(fps.hora.max())
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(resultado, ensure_ascii=False, indent=1))
