"""Pedido 52, D.1 da atualizacao de 20/11: junta as rodadas do radio fora do tempo real (sem o engenheiro e com os
moldes a, b e c) das 5 sessoes e mede, contra a gravacao, o que o piloto fez de fato.

* **os avisos:** as linhas `aviso` do registro do engenheiro (a fala que comecou no `s_fala`, ou a janela que
  mostrou o aviso no `sJanela`); a volta e a da gravacao no instante do aviso;
* **a folga real:** a fala comeca no `s_fala` mais a latencia de 0,1 s (a estimativa do ADR; fora do jogo nao ha
  como medir a do jogo) e acaba depois da duracao; a folga ate a acao do piloto e o tempo entre esse fim e a acao
  dele naquela passagem (a regra da E.3: desde a saida do trecho anterior ate o apice; "freie": a frenagem;
  "vire": a primeira frenagem ou o primeiro alivio; sem nenhum dos dois, e "sem tirar o pe", a entrada; "acelere":
  a volta ao acelerador de 0,90 ou mais depois do apice); a folga ate o ponto dito, o tempo ate o carro passar nele;
* **as falas com dois avisos;**
* **o bipe:** o carro passa o ponto dito (o tempo de reacao e 0 s); a distancia e o tempo ate a acao do piloto
  (positivo: o bipe vem antes da acao);
* **o feedback:** os cortes (linhas `corte`) e as mensagens que mudaram de bloco contra a rodada sem o engenheiro
  (a mesma origem, volta e titulo; mais de 300 m de diferenca no `s` do carro ou outra volta).

Uso (na pasta backend): python <este arquivo> <pasta das rodadas> <saida.json>
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.engenheiro import plano as P  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from core.radio.texto import fala_tem_causa  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
REPO = Path("..").resolve()
SESSOES = {"2026-10-13": REPO / "recordings" / "2026-10-13_19-24-10_vhe_interlagos",
           "2026-10-18": REPO / "data" / "recordings" / "2026-10-18_12-38-44_vhe_interlagos",
           "2026-10-21": REPO / "data" / "recordings" / "2026-10-21_20-30-54_vhe_interlagos",
           "2026-11-12": REPO / "data" / "recordings" / "2026-11-12_22-57-03_vhe_interlagos",
           "2026-11-20": REPO / "data" / "recordings" / "2026-11-20_19-06-14_vhe_interlagos"}
VARIANTES = ("a", "b", "c")
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
indice = {t.nome: k for k, t in enumerate(trechos)}


def carregar(pasta):
    cache = PASTA / f"{pasta.name}_projetada.npz"
    if cache.exists():
        z = np.load(cache)
        return z["q"]
    linhas = []
    for n, lap in enumerate(iter_laps(Session(session_id=pasta.name, directory=pasta, track="vhe_interlagos"))):
        f = lap.frame
        s, _ = track.project(np.c_[f["x"].to_numpy(float), f["z"].to_numpy(float)])
        linhas.append(np.c_[f["timestamp_s"].to_numpy(float), np.asarray(s, float), f["speed_kmh"].to_numpy(float),
                            np.nan_to_num(f["throttle"].to_numpy(float)), np.nan_to_num(f["brake"].to_numpy(float)),
                            np.full(len(f), n)])
    q = np.vstack(linhas)
    q = q[np.isfinite(q[:, 0])]
    np.savez(cache, q=q)
    return q


class Sessao:
    def __init__(self, q, t0):
        self.T = q[:, 0] - t0
        ordem = np.argsort(self.T)
        self.T, self.S, self.V, self.A, self.F, self.N = (q[ordem, 0] - t0, q[ordem, 1], q[ordem, 2], q[ordem, 3],
                                                          q[ordem, 4], q[ordem, 5].astype(int))

    def passou(self, alvo, desde, limite=60.0):
        i0 = max(int(np.searchsorted(self.T, desde)), 1)
        for i in range(i0, len(self.T)):
            if self.T[i] - desde > limite:
                return None
            a, b = self.S[i - 1], self.S[i]
            anda = (b - a) % L
            if anda > 200 or anda <= 0:
                continue
            falta = (alvo - a) % L
            if falta <= anda:
                return float(self.T[i - 1] + falta / anda * (self.T[i] - self.T[i - 1]))
        return None

    def volta(self, t):
        return int(self.N[min(int(np.searchsorted(self.T, t)), len(self.T) - 1)])

    def acao(self, trecho, acao, desde):
        """A acao do piloto na passagem do trecho cujo apice vem depois de `desde`."""
        k = indice[trecho]
        tr = trechos[k]
        t_ap = self.passou(float(tr.apice_s), desde)
        if t_ap is None:
            return None, None
        # a ancora: a ultima passagem pela saida do trecho anterior nos 30 s antes do apice (a mesma passagem)
        ancora = None
        t = t_ap - 30.0
        while True:
            x = self.passou(R.inicio_da_busca_da_freada(trechos, k) % L, t, limite=30.0)
            if x is None or x > t_ap:
                break
            ancora, t = x, x + 0.5
        ancora = max(desde, t_ap - 30.0) if ancora is None else ancora
        idx = np.flatnonzero((self.T >= ancora) & (self.T <= t_ap))
        if acao == R.SEM_TIRAR_O_PE or not idx.size:
            return self.passou(float(tr.entrada_s), ancora), "entrada"
        if acao == "acelere":
            t_fim = self.passou(float(tr.fim_s) % L, t_ap) or t_ap + 10
            j = np.flatnonzero((self.T >= t_ap) & (self.T <= t_fim) & (self.A >= R.ACELERADOR_DA_RETOMADA))
            return (float(self.T[j[0]]), "acelerador") if j.size else (None, None)
        if acao == "freie" and self.F[idx[0]] >= R.FREIO_DA_FREADA:
            j = idx[0]
            while j > 0 and self.F[j - 1] >= R.FREIO_DA_FREADA:
                j -= 1
            return float(self.T[j]), "frenagem"
        cond = self.F[idx] >= R.FREIO_DA_FREADA
        if acao != "freie":
            cond = cond | (self.A[idx] < R.ACELERADOR_DA_RETOMADA)
        h = np.flatnonzero(cond)
        if h.size:
            return float(self.T[idx[h[0]]]), "frenagem" if self.F[idx[h[0]]] >= R.FREIO_DA_FREADA else "alívio"
        return self.passou(float(tr.entrada_s), ancora), "entrada"


def acao_da_frase(frase):
    if not frase:
        return None
    if frase.startswith(R.SEM_TIRAR_O_PE):
        return R.SEM_TIRAR_O_PE
    return frase.split()[0]


def resumo(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "min": None, "mediana": None, "max": None}
    return {"n": len(xs), "min": round(min(xs), 2), "mediana": round(float(np.median(xs)), 2), "max": round(max(xs), 2)}


def chave(m):
    return (m.get("origem"), m.get("volta") or m.get("voltaDoCarro"), m.get("titulo"))


saida = {"regras": __doc__, "sessoes": {}}
for nome, pasta in SESSOES.items():
    sem = json.loads((PASTA / f"{nome}_sem.json").read_text(encoding="utf-8"))
    q = carregar(pasta)
    porv = {}
    for v in VARIANTES:
        arq = PASTA / f"{nome}_com_{v}.json"
        if not arq.exists():
            continue
        com = json.loads(arq.read_text(encoding="utf-8"))
        ses = Sessao(q, float(com["t0"]))
        reg = com.get("registroDoEngenheiro") or []
        avisos = [x for x in reg if x["tipo"] == "aviso"]
        cortes = [x for x in reg if x["tipo"] == "corte"]
        por_volta = {}
        motivos = Counter()
        folga_acao, folga_dito, bipe_t, bipe_m, juntas = [], [], [], [], set()
        lista_folgas = []
        for a in avisos:
            t = float(a.get("t") or 0.0)
            n = ses.volta(t)
            pv = por_volta.setdefault(n, {"comAviso": set(), "comVoz": set()})
            pv["comAviso"].add(a["trecho"])
            acao = acao_da_frase(a.get("frase"))
            if a["voz"]:
                pv["comVoz"].add(a["trecho"])
                if a.get("falaJunta"):
                    juntas.add((round(t, 2), a.get("fala")))
                ini = t + P.LATENCIA_NO_JOGO_S
                fim = ini + float(a.get("duracaoS") or 0.0)
                t_acao, tipo = ses.acao(a["trecho"], acao, ini)
                t_dito = ses.passou(float(a["sDito"]), ini) if a.get("sDito") is not None else None
                fa = None if t_acao is None else round(t_acao - fim, 2)
                fd = None if t_dito is None else round(t_dito - fim, 2)
                folga_acao.append(fa)
                folga_dito.append(fd)
                lista_folgas.append({"volta": n, "trecho": a["trecho"], "fala": a.get("fala"), "duracaoS": a.get("duracaoS"),
                                     "folgaPlanejadaS": a.get("folgaPlanejadaS"), "ateASuaAcaoS": fa, "aSuaAcao": tipo,
                                     "ateOPontoDitoS": fd})
            else:
                motivos[a.get("porqueSoNaJanela") or "?"] += 1
            if a.get("bipe") is not None:
                t_b = ses.passou(float(a["bipe"]), t)
                t_acao, _ = ses.acao(a["trecho"], acao, t)
                if t_b is not None and t_acao is not None:
                    bipe_t.append(round(t_acao - t_b, 2))
                    i_b = min(int(np.searchsorted(ses.T, t_b)), len(ses.T) - 1)
                    i_a = min(int(np.searchsorted(ses.T, t_acao)), len(ses.T) - 1)
                    bipe_m.append(round(((ses.S[i_a] - ses.S[i_b] + L / 2) % L) - L / 2, 1))
        # o feedback que mudou de bloco (contra a rodada sem o engenheiro)
        fb = lambda ms: [m for m in ms if m["origem"] in ("coach", "resumo", "analise", "curva")]  # noqa: E731
        antes = {}
        for m in fb(sem["mensagens"]):
            antes.setdefault(chave(m), []).append(m)
        mudou, so_com = [], []
        for m in fb(com["mensagens"]):
            lst = antes.get(chave(m)) or []
            if not lst:
                so_com.append({k: m.get(k) for k in ("origem", "volta", "titulo", "fala", "sCarro")})
                continue
            x = lst.pop(0)
            if x.get("voltaDoCarro") != m.get("voltaDoCarro") or abs(float(x.get("sCarro") or 0) - float(m.get("sCarro") or 0)) > 300:
                mudou.append({"origem": m["origem"], "volta": m.get("volta"), "titulo": m.get("titulo"),
                              "sem": {"voltaDoCarro": x.get("voltaDoCarro"), "sCarro": x.get("sCarro"), "fala": x.get("fala")},
                              "com": {"voltaDoCarro": m.get("voltaDoCarro"), "sCarro": m.get("sCarro"), "fala": m.get("fala")}})
        so_sem = [{k: m.get(k) for k in ("origem", "volta", "titulo", "fala")} for r in antes.values() for m in r]
        porv[v] = {
            "porVolta": {str(n): {"comAviso": sorted(x["comAviso"]), "comVoz": sorted(x["comVoz"]),
                                  "semVoz": sorted(x["comAviso"] - x["comVoz"])} for n, x in sorted(por_volta.items())},
            "avisosComVoz": sum(1 for a in avisos if a["voz"]), "avisosSoNaJanela": sum(1 for a in avisos if not a["voz"]),
            "motivosSemVoz": dict(motivos),
            "folgaAteASuaAcaoS": resumo(folga_acao), "folgaAteOPontoDitoS": resumo(folga_dito),
            "folgaAbaixoDe3S": sum(1 for x in folga_acao if x is not None and x < 3.0),
            "falasComDoisAvisos": len(juntas), "exemplosDeFalasComDois": sorted({f for _, f in juntas})[:8],
            "bipeAteASuaAcaoS": resumo(bipe_t), "bipeAteASuaAcaoM": resumo(bipe_m),
            "cortes": [{"cortada": c["cortada"], "pelaFala": c.get("pelaFala"), "restavaS": c.get("restavaS")} for c in cortes],
            "feedback": {"sem": len(fb(sem["mensagens"])), "com": len(fb(com["mensagens"])), "mudaramDeBloco": mudou,
                         "soSem": so_sem, "soCom": so_com, "pendentesNoFim": {"sem": sem["pendentesNoFim"], "com": com["pendentesNoFim"]},
                         "comCausaNaVoz": {"sem": sum(1 for m in fb(sem["mensagens"]) if fala_tem_causa(m.get("fala"))),
                                           "com": sum(1 for m in fb(com["mensagens"]) if fala_tem_causa(m.get("fala")))}},
            "folgas": lista_folgas,
        }
    saida["sessoes"][nome] = porv
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
for nome, porv in saida["sessoes"].items():
    for v, d in porv.items():
        print(nome, v, "| voz", d["avisosComVoz"], "janela", d["avisosSoNaJanela"], dict(d["motivosSemVoz"]),
              "| folga acao", d["folgaAteASuaAcaoS"], "<3s", d["folgaAbaixoDe3S"], "| dito", d["folgaAteOPontoDitoS"],
              "| pares", d["falasComDoisAvisos"], "| bipe", d["bipeAteASuaAcaoS"], d["bipeAteASuaAcaoM"],
              "| cortes", len(d["cortes"]), "| mudaram", len(d["feedback"]["mudaramDeBloco"]),
              "| fb", d["feedback"]["sem"], d["feedback"]["com"], "causa", d["feedback"]["comCausaNaVoz"],
              "| pend", d["feedback"]["pendentesNoFim"])
