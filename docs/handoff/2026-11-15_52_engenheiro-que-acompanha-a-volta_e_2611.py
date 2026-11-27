"""Pedido 52, Atualizacao de 26/11, item 1: a leitura do teste no jogo de 26/11 (a sessao 2026-11-26_21-49-14, a
primeira depois da instalacao do app do jogo 0.10.0). So leitura da gravacao, do registro do engenheiro, das
mensagens do radio e de uma copia do log do CSP.

* **cada fala do engenheiro** (as linhas `ficha` e `lembrete`): o tipo, a curva, o `s` do comeco e quantos segundos
  e metros antes da acao dessa curva ela acabou. A acao e a do piloto naquela passagem, na gravacao (a frenagem;
  sem frenagem, a entrada); a fala comeca no `t` do registro mais a latencia medida no log do CSP (ou 0,1 s) e acaba
  depois da duracao;
* **o que foi dito depois de cada curva** (as linhas `analise` e `analise da volta`) e se a mensagem chegou a ser
  entregue pelo radio (as mensagens com origem `engenheiro` no `<sessao>.jsonl`);
* **o relogio:** a gravacao esta 3 h adiantada (o `startedAt` da sessao da a hora certa).

Uso (na pasta backend): python <este arquivo> <pasta da sessao> <registro .engenheiro.jsonl> <mensagens .jsonl>
  <log do CSP> <saida.json>
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.engenheiro import regras as R  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

PASTA, REG, MSG, LOG, SAIDA = (Path(a) for a in sys.argv[1:6])
REPO = Path("..").resolve()
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
indice = {t.nome: k for k, t in enumerate(trechos)}

meta = json.loads((PASTA / "metadata.json").read_text(encoding="utf-8"))
inicio = datetime.fromisoformat(meta["startedAt"]).timestamp()
linhas = []
for n, lap in enumerate(iter_laps(Session(session_id=PASTA.name, directory=PASTA, track="vhe_interlagos"))):
    f = lap.frame
    s, _ = track.project(np.c_[f["x"].to_numpy(float), f["z"].to_numpy(float)])
    linhas.append(np.c_[f["timestamp_s"].to_numpy(float), np.asarray(s, float), np.nan_to_num(f["brake"].to_numpy(float)),
                        f["speed_kmh"].to_numpy(float), np.full(len(f), n)])
q = np.vstack(linhas)
q = q[np.isfinite(q[:, 0])]
q = q[np.argsort(q[:, 0])]
DESLOCAMENTO = round((q[0, 0] - inicio) / 3600.0) * 3600.0
T, S, F, V = q[:, 0] - DESLOCAMENTO, q[:, 1], q[:, 2], q[:, 3]


def passou(alvo, desde, limite=120.0):
    i0 = max(int(np.searchsorted(T, desde)), 1)
    for i in range(i0, len(T)):
        if T[i] - desde > limite:
            return None
        a, b = S[i - 1], S[i]
        anda = (b - a) % L
        if anda > 200 or anda <= 0:
            continue
        if (alvo - a) % L <= anda:
            return float(T[i - 1] + (alvo - a) % L / anda * (T[i] - T[i - 1]))
    return None


def s_em(t):
    return float(S[min(int(np.searchsorted(T, t)), len(T) - 1)])


def acao(trecho, desde):
    """A frenagem do piloto na passagem seguinte da curva (desde a saida do trecho anterior); sem frenagem, a entrada."""
    k = indice[trecho]
    tr = trechos[k]
    t_ap = passou(float(tr.apice_s), desde)
    if t_ap is None:
        return None, None
    t_busca = passou(R.inicio_da_busca_da_freada(trechos, k) % L, max(desde, t_ap - 40.0))
    t_busca = t_busca if t_busca is not None and t_busca < t_ap else max(desde, t_ap - 30.0)
    idx = np.flatnonzero((T >= t_busca) & (T <= t_ap) & (F >= R.FREIO_DA_FREADA))
    if idx.size:
        j = idx[0]
        while j > 0 and F[j - 1] >= R.FREIO_DA_FREADA:
            j -= 1
        return float(T[j]), "frenagem"
    return passou(float(tr.entrada_s), t_busca), "entrada"


# a latencia medida no log do CSP: "tocou X s depois do disparo"
texto_log = LOG.read_text(encoding="utf-8", errors="replace")
latencias = [float(x.replace(",", ".")) for x in re.findall(r"tocou ([0-9]+,[0-9]+) s depois do disparo", texto_log)]
latencia = float(np.median(latencias)) if latencias else 0.1
bipes_no_log = re.findall(r"engenheiro: bipe (\d) de (\d)[^\n]*? (C\d\d) em s=([0-9,]+)", texto_log)

reg = [json.loads(x) for x in REG.read_text(encoding="utf-8").splitlines() if x.strip()]
msgs = [json.loads(x) for x in MSG.read_text(encoding="utf-8").splitlines() if x.strip()]
falas = []
for x in reg:
    if x["tipo"] not in ("ficha", "lembrete"):
        continue
    t0 = float(x["t"]) + latencia
    fim = t0 + float(x["duracaoS"] or 0.0)
    ta, tipo = acao(x["trecho"], t0)
    falas.append({"tipo": x["tipo"], "curva": x["trecho"], "voz": x["voz"], "porqueCalada": x.get("porqueCalada"),
                  "sComeco": x["sCarro"], "duracaoS": x["duracaoS"], "fala": x["fala"],
                  "aSuaAcao": tipo, "acabouAntesDaAcaoS": None if ta is None else round(ta - fim, 2),
                  "acabouAntesDaAcaoM": None if ta is None else round((s_em(ta) - s_em(fim)) % L, 1),
                  "metrosDoComecoAteACurva": round((float(trechos[indice[x["trecho"]]].entrada_s) - float(x["sCarro"])) % L, 1)})
entregues = [m for m in msgs if m.get("origem") == "engenheiro"]
depois = [{"volta": x.get("volta"), "curva": x["trecho"], "tipo": x["tipo"], "texto": x.get("texto"),
           "entregue": any(m.get("fala") == x.get("texto") for m in entregues)}
          for x in reg if x["tipo"] in ("analise", "analise da volta")]
resultado = {"sessao": PASTA.name, "latenciaMedianaS": round(latencia, 3), "latencias": latencias,
             "bipesNoLog": [{"bipe": int(a), "de": int(b), "curva": c, "s": float(d.replace(",", "."))} for a, b, c, d in bipes_no_log],
             "falas": falas, "depoisDaCurva": depois, "mensagensDoRadio": [
                 {"em": m["entregueEm"][11:19], "origem": m["origem"], "volta": m.get("voltaDoCarro"), "sCarro": m.get("sCarro"),
                  "titulo": m["titulo"], "fala": m.get("fala"), "duracaoS": m.get("duracaoS")} for m in msgs],
             "registro": [{k: v for k, v in x.items() if k not in ("sessao", "perdas", "lista", "diferencas", "medidas")} for x in reg]}
SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
print("latencia", latencia, latencias)
for f in falas:
    print(f["tipo"], f["curva"], "voz", f["voz"], "s", f["sComeco"], "dur", f["duracaoS"], "| antes da acao", f["acabouAntesDaAcaoS"], "s",
          f["acabouAntesDaAcaoM"], "m |", f["metrosDoComecoAteACurva"], "m ate a entrada")
for d in depois:
    print("depois", d["volta"], d["curva"], d["tipo"], d["entregue"], "|", d["texto"])
print("bipes no log", len(resultado["bipesNoLog"]))
