"""Pedido 52, E.3: a leitura da sessao do teste no jogo (2026-11-20_19-06-14), so leitura da gravacao.

* as voltas da gravacao projetadas na geometria oficial (`track.project`): o relogio da volta em cada `s`;
* em cada volta e em cada trecho com curva, os pontos do piloto pela regra do engenheiro (ADR 0033 e a emenda):
  a frenagem (da saida do trecho anterior ao apice, com a pisada em andamento desde o comeco), a entrada (o
  inicio da curva) e a retomada (acelerador em 0,90 ou mais ate o fim do trecho);
* entre a acao anterior e a proxima: do apice da curva anterior ao apice da curva, o ultimo pedaco "livre"
  (acelerador em 0,90 ou mais e freio abaixo de 0,15); a acao seguinte e o primeiro ponto depois dele (a
  frenagem, se o freio passa de 0,15 em ate 20 m, ou o alivio). Sem pedaco livre, as curvas sao emendadas (0 s);
* o relogio da gravacao esta 3 h adiantado (o gravador, no backlog): a hora certa e a do `startedAt` da sessao;
* as vozes tocadas no jogo (o log do CSP, "voz: url tocou"), com o `s` do carro no comeco e no fim.

Uso (na pasta backend): python <este arquivo> <pasta da sessao> <custom_shaders_patch.log> <saida.json>
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.engenheiro import regras as R  # noqa: E402
from core.radio.analise import freada_desde  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

PASTA, LOG, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
REPO = Path("..").resolve()
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
S = np.asarray(track.s, float)

sessao = Session(session_id=PASTA.name, directory=PASTA, track="vhe_interlagos")
_meta = json.loads((PASTA / "metadata.json").read_text(encoding="utf-8"))
_inicio = datetime.fromisoformat(_meta["startedAt"]).timestamp()
quadros = []
voltas = []
for lap in iter_laps(sessao):
    f = lap.frame
    xz = np.c_[f["x"].to_numpy(float), f["z"].to_numpy(float)]
    s, lat = track.project(xz)
    quadros.append(np.c_[f["timestamp_s"].to_numpy(float), np.asarray(s, float), f["speed_kmh"].to_numpy(float)])
    voltas.append({"n": len(voltas), "frame": f, "s": np.asarray(s, float), "lat": np.asarray(lat, float)})
todos = np.vstack(quadros)
todos = todos[np.argsort(todos[:, 0])]
DESLOCAMENTO = round((todos[0, 0] - _inicio) / 3600.0) * 3600.0     # o relogio da gravacao menos a hora local
todos[:, 0] -= DESLOCAMENTO


def s_no_instante(t):
    i = int(np.clip(np.searchsorted(todos[:, 0], t), 1, len(todos) - 1))
    a, b = todos[i - 1], todos[i]
    k = (t - a[0]) / max(b[0] - a[0], 1e-9)
    ds = ((b[1] - a[1] + L / 2) % L) - L / 2
    return float((a[1] + k * ds) % L), float(a[2] + k * (b[2] - a[2]))


def grade_da_volta(v):
    """O relogio da volta, a velocidade, o freio e o acelerador na grade da pista (s de 0 a L), so para voltas
    que passam pela pista inteira; None se faltar um pedaco."""
    f = v["frame"]
    t = f["lap_time_s"].to_numpy(float)
    s = v["s"].copy()
    # desenrola: no comeco da volta o s pode estar perto de L (antes da linha)
    s[(s > L / 2) & (t < 5.0)] -= L
    ordem = np.argsort(t)
    t, s = t[ordem], s[ordem]
    ok = np.isfinite(s) & np.isfinite(t)
    t, s = t[ok], s[ok]
    if s.min() > 30 or s.max() < L - 30:
        return None
    sm = np.maximum.accumulate(s)
    _, unico = np.unique(sm, return_index=True)
    el = np.interp(S, sm[unico], t[unico])
    g = {"elapsed": el}
    for nome, col in (("velocidade", "speed_kmh"), ("freio", "brake"), ("acelerador", "throttle")):
        y = f[col].to_numpy(float)[ordem][ok]
        g[nome] = np.interp(S, sm[unico], y[unico])
    g["total"] = float(t.max())
    return g


def entre_acoes(g, k):
    """O ultimo pedaco livre entre o apice anterior e o apice da curva; a acao seguinte e o tempo dele."""
    from ml.comparison.lap_vs_reference import _window
    t, ant = trechos[k], trechos[curvas[curvas.index(k) - 1]]
    idx = _window(track, ant.apice_s, t.apice_s)
    livre = (np.nan_to_num(g["acelerador"][idx]) >= R.ACELERADOR_DA_RETOMADA) & (np.nan_to_num(g["freio"][idx]) < R.FREIO_DA_FREADA)
    if not livre.any():
        return None, None, None, 0.0
    fim = int(np.flatnonzero(livre)[-1])
    inicio = fim
    while inicio > 0 and livre[inicio - 1]:
        inicio -= 1
    if fim + 1 >= len(idx):
        return float(S[idx[inicio]]), None, "sem ação antes do ápice", None
    acao = float(S[idx[fim + 1]])
    perto = idx[fim + 1: fim + 1 + int(20 / track.step) + 1]
    tipo = "frenagem" if (np.nan_to_num(g["freio"][perto]) >= R.FREIO_DA_FREADA).any() else "alívio"
    dt = (R.tempo_em(g["elapsed"], g["total"], track, acao) - R.tempo_em(g["elapsed"], g["total"], track, float(S[idx[inicio]]))) % g["total"]
    return float(S[idx[inicio]]), acao, tipo, float(dt)


def primeira_acao(g, k, retomada_anterior):
    """A frenagem do trecho; sem ela, o primeiro alivio (acelerador abaixo de 0,90) depois da retomada anterior e
    antes do apice; sem ele, a entrada."""
    t = trechos[k]
    fr = freada_desde(g["freio"], track, R.inicio_da_busca_da_freada(trechos, k), t.apice_s)
    if fr is not None:
        return fr, "frenagem"
    if retomada_anterior is not None:
        from ml.comparison.lap_vs_reference import _window
        idx = _window(track, retomada_anterior, t.apice_s)
        abaixo = np.flatnonzero(np.nan_to_num(g["acelerador"][idx]) < R.ACELERADOR_DA_RETOMADA)
        if abaixo.size:
            return float(S[idx[abaixo[0]]]), "alívio"
    return float(t.entrada_s), "entrada"


curvas = [k for k, t in enumerate(trechos) if t.tem_curva]
resultado = {"sessao": PASTA.name, "deslocamentoDoRelogioS": DESLOCAMENTO, "voltas": [], "vozes": []}
for v in voltas:
    g = grade_da_volta(v)
    f = v["frame"]
    linha = {"volta": v["n"], "tempoS": round(float(f["lap_time_s"].max()), 3),
             "inicio": datetime.fromtimestamp(float(f["timestamp_s"].iloc[0]) - DESLOCAMENTO).strftime("%H:%M:%S"),
             "fim": datetime.fromtimestamp(float(f["timestamp_s"].iloc[-1]) - DESLOCAMENTO).strftime("%H:%M:%S"),
             "completa": g is not None, "trechos": []}
    if g is not None:
        ret = {k: R.retomada(g["acelerador"], track, trechos[k]) for k in curvas}
        for j, k in enumerate(curvas):
            ant = curvas[j - 1]
            ra = ret[ant]
            acao, tipo = primeira_acao(g, k, ra)
            item = {"trecho": trechos[k].nome, "retomadaAnterior": None if ra is None else round(ra, 1),
                    "acao": round(acao, 1), "tipoDaAcao": tipo,
                    "vNaAcaoKmh": round(float(g["velocidade"][int(track.index_of(acao))]), 1)}
            if ra is not None and (acao - ra) % L < L / 2:
                dt = (R.tempo_em(g["elapsed"], g["total"], track, acao) - R.tempo_em(g["elapsed"], g["total"], track, ra)) % g["total"]
                item["entreAcoesS"] = round(float(dt), 2)
            else:
                item["entreAcoesS"] = None
                item["porque"] = "sem retomada no trecho anterior" if ra is None else "a ação vem antes da retomada anterior"
            li, la, lt, ldt = entre_acoes(g, k)
            item["livreDesde"] = None if li is None else round(li, 1)
            item["proximaAcao"] = None if la is None else round(la, 1)
            item["tipoDaProxima"] = lt
            item["livreS"] = None if ldt is None else round(ldt, 2)
            if la is not None:
                item["vNaProximaKmh"] = round(float(g["velocidade"][int(track.index_of(la))]), 1)
            linha["trechos"].append(item)
        linha["_g"] = g
    resultado["voltas"].append(linha)

# as vozes tocadas no jogo
texto = LOG.read_text(encoding="utf-8", errors="replace")
m = re.search(r"date & time: (\d{4})\.(\d{2})\.(\d{2})/(\d{2}):(\d{2}):(\d{2})\.(\d{3})", texto)
inicio_log = datetime(*[int(x) for x in m.groups()[:6]], int(m.group(7)) * 1000).timestamp()
for ms in re.findall(r"^\s*(\d+)\s+M .*\[radio_engenheiro\] voz: url tocou", texto, re.M):
    t = inicio_log + int(ms) / 1000.0
    s, v = s_no_instante(t)
    resultado["vozes"].append({"tocouEm": datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-3], "t": t,
                               "sCarro": round(s, 1), "vKmh": round(v, 1)})
gs = {x["volta"]: x.pop("_g") for x in resultado["voltas"] if "_g" in x}
resultado["_grades"] = gs
np.save(SAIDA.with_suffix(".npy"), {"grades": gs, "quadros": todos}, allow_pickle=True)
resultado.pop("_grades")
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
for x in resultado["voltas"]:
    print(x["volta"], x["tempoS"], x["inicio"], x["fim"], "completa" if x["completa"] else "incompleta")
    for i in x["trechos"]:
        print("   ", i["trecho"], "livre", i["livreDesde"], "->", i["proximaAcao"], i["tipoDaProxima"], i["livreS"], "s |", i["acao"], i["tipoDaAcao"])
for vz in resultado["vozes"]:
    print("voz", vz["tocouEm"], vz["sCarro"], vz["vKmh"])
