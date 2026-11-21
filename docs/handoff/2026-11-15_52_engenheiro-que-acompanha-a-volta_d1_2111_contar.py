"""Pedido 52, D.1 da atualizacao de 21/11 (a curva de foco): junta as rodadas do radio fora do tempo real das 6
sessoes (em cadeia: cada rodada recebe o registro do engenheiro da anterior) e mede, contra a gravacao, o que o
piloto fez de fato. So leitura das gravacoes.

* **o foco:** as linhas `foco` (a curva, a volta do radio, o motivo da escolha ou da troca) e `conferencia`;
* **a ficha e o lembrete:** as linhas `ficha` e `lembrete` (a fala que comecou no `s_fala`); a fala comeca no
  `s_fala` mais a latencia de 0,1 s e acaba depois da duracao; a folga ate a acao do piloto naquela passagem (a
  regra da E.3, pelo tipo da ficha: a frenagem; de pe embaixo, a entrada; so um alivio, a primeira frenagem ou o
  primeiro alivio) e ate o ponto da ficha (o ponto de frenagem da referencia, ou a entrada);
* **a contagem de bipes:** em cada passagem pela curva de foco com frenagem, o instante em que o carro passa o
  ultimo bipe (o ponto de frenagem da referencia; fora do jogo, sem latencia) contra a frenagem do piloto
  naquela passagem (positivo: ele freou depois do bipe);
* **o feedback:** os cortes e as mensagens que mudaram de bloco contra a rodada sem o engenheiro;
* **os segundos de fala por volta, antes e depois desta emenda:** a soma das falas do engenheiro e do feedback,
  dividida pelas voltas da gravacao. "Antes" e a rodada da D.1 de 20/11 com o molde (b); na sessao de 21/11, que
  nao estava na D.1 de 20/11, e a sessao real (o codigo de 20/11 no jogo: o registro e as mensagens entregues).

Os instantes do registro fora do tempo real vem do campo `em` (o relogio do radio, que e o da gravacao menos `t0`,
em segundos inteiros).

Uso (na pasta backend): python <este arquivo> <pasta das rodadas de 21/11> <pasta das rodadas de 20/11> <saida.json>
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
from core.engenheiro import plano as P  # noqa: E402
from core.engenheiro import regras as R  # noqa: E402
from core.radio.janelas import carregar_geometria  # noqa: E402
from core.radio.texto import fala_tem_causa  # noqa: E402
from ml.data.recordings import Session, iter_laps  # noqa: E402

PASTA, PASTA_2011, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
REPO = Path("..").resolve()
SESSOES = {"2026-10-13": REPO / "recordings" / "2026-10-13_19-24-10_vhe_interlagos",
           "2026-10-18": REPO / "data" / "recordings" / "2026-10-18_12-38-44_vhe_interlagos",
           "2026-10-21": REPO / "data" / "recordings" / "2026-10-21_20-30-54_vhe_interlagos",
           "2026-11-12": REPO / "data" / "recordings" / "2026-11-12_22-57-03_vhe_interlagos",
           "2026-11-20": REPO / "data" / "recordings" / "2026-11-20_19-06-14_vhe_interlagos",
           "2026-11-21": REPO / "data" / "recordings" / "2026-11-21_18-10-46_vhe_interlagos"}
REAL_2111 = REPO / "data" / "radio" / "2026-11-21_18-10-46_vhe_interlagos"
FEEDBACK = ("coach", "resumo", "analise", "curva")
ACAO = {"frenagem": "freie", "pé embaixo": R.SEM_TIRAR_O_PE, "alívio": "vire"}
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
indice = {t.nome: k for k, t in enumerate(trechos)}


def _tipos_das_fichas():
    """O tipo da ficha de cada curva (frenagem, pe embaixo ou so um alivio): so da volta de referencia."""
    from core.assisted_analysis import volta_do_modelo as VM
    from core.engenheiro import ficha as F
    from core.engenheiro import marcos as M
    from core.radio.analise import grade

    st = VM.como_volta_do_store(VM.encontrar([REPO], "vhe_interlagos"))
    mc = M.encontrar([REPO], "vhe_interlagos")
    ref = {"grade": grade(st), "tempoS": float(st["tempoS"])}
    return {f["trecho"]: f["tipo"] for f in F.lista_de_fichas(ref, track, trechos, mc["marcos"], M.pontos_de_referencia(mc["marcos"]))}


TIPO = _tipos_das_fichas()


def carregar(pasta):
    for cache in (PASTA / f"{pasta.name}_projetada.npz", PASTA_2011 / f"{pasta.name}_projetada.npz"):
        if cache.exists():
            return np.load(cache)["q"]
    linhas = []
    for n, lap in enumerate(iter_laps(Session(session_id=pasta.name, directory=pasta, track="vhe_interlagos"))):
        f = lap.frame
        s, _ = track.project(np.c_[f["x"].to_numpy(float), f["z"].to_numpy(float)])
        linhas.append(np.c_[f["timestamp_s"].to_numpy(float), np.asarray(s, float), f["speed_kmh"].to_numpy(float),
                            np.nan_to_num(f["throttle"].to_numpy(float)), np.nan_to_num(f["brake"].to_numpy(float)),
                            np.full(len(f), n)])
    q = np.vstack(linhas)
    q = q[np.isfinite(q[:, 0])]
    np.savez(PASTA / f"{pasta.name}_projetada.npz", q=q)
    return q


class Sessao:
    def __init__(self, q, t0):
        ordem = np.argsort(q[:, 0])
        self.T, self.S, self.V, self.A, self.F, self.N = (q[ordem, 0] - t0, q[ordem, 1], q[ordem, 2], q[ordem, 3],
                                                          q[ordem, 4], q[ordem, 5].astype(int))

    def passou(self, alvo, desde, limite=120.0):
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

    def s_em(self, t):
        return float(self.S[min(int(np.searchsorted(self.T, t)), len(self.T) - 1)])

    def acao(self, trecho, acao, desde):
        """A acao do piloto na passagem do trecho cujo apice vem depois de `desde` (a regra da E.3, com o alivio de
        10 m ou mais da emenda de 21/11). Devolve (instante, tipo, instante do apice)."""
        k = indice[trecho]
        tr = trechos[k]
        t_ap = self.passou(float(tr.apice_s), desde)
        if t_ap is None:
            return None, None, None
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
            return self.passou(float(tr.entrada_s), ancora), "entrada", t_ap
        if acao == "freie" and self.F[idx[0]] >= R.FREIO_DA_FREADA:
            j = idx[0]
            while j > 0 and self.F[j - 1] >= R.FREIO_DA_FREADA:
                j -= 1
            return float(self.T[j]), "frenagem", t_ap
        freio = self.F[idx] >= R.FREIO_DA_FREADA
        h = np.flatnonzero(freio)
        if acao != "freie":
            # o primeiro alivio de 10 m ou mais (a emenda de 21/11, item 8)
            abaixo = self.A[idx] < R.ACELERADOR_DA_RETOMADA
            for j in range(len(idx)):
                if freio[j]:
                    break
                if abaixo[j] and (j == 0 or not abaixo[j - 1]):
                    fim = j
                    while fim + 1 < len(idx) and abaixo[fim + 1]:
                        fim += 1
                    if (self.S[idx[fim]] - self.S[idx[j]]) % L >= R.ALIVIO_MINIMO_M:
                        return float(self.T[idx[j]]), "alívio", t_ap
        if h.size:
            return float(self.T[idx[h[0]]]), "frenagem", t_ap
        return self.passou(float(tr.entrada_s), ancora), "entrada", t_ap


_ZERO = datetime.fromtimestamp(86400.0)          # o Windows nao aceita `timestamp()` perto de 1970


def t_de(linha):
    """O relogio do radio da linha (o `em`, em segundos inteiros; fora do tempo real, o da gravacao menos `t0`)."""
    return (datetime.fromisoformat(linha["em"]) - _ZERO).total_seconds() + 86400.0 if linha.get("em") else None


def resumo(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {"n": 0, "min": None, "mediana": None, "max": None}
    return {"n": len(xs), "min": round(min(xs), 2), "mediana": round(float(np.median(xs)), 2), "max": round(max(xs), 2)}


def chave(m):
    return (m.get("origem"), m.get("volta") or m.get("voltaDoCarro"), m.get("titulo"))


def feedback(ms):
    return [m for m in ms if m.get("origem") in FEEDBACK]


def falas_do_engenheiro_de_2011(reg):
    """As falas do engenheiro da emenda de 20/11 (uma por fala tocada: as linhas `aviso` com voz, pela fala e pelo t)."""
    vistas = {}
    for a in reg:
        if a.get("tipo") == "aviso" and a.get("voz") and a.get("fala"):
            vistas[(round(float(a.get("t") or 0.0), 2), a["fala"])] = float(a.get("duracaoS") or 0.0)
    return vistas


def segundos(eng, fb, voltas):
    e, f = sum(eng), sum(float(m.get("duracaoS") or 0.0) for m in fb)
    return {"voltasDaGravacao": voltas, "engenheiroS": round(e, 1), "feedbackS": round(f, 1),
            "porVolta": {"engenheiro": round(e / voltas, 1), "feedback": round(f / voltas, 1),
                         "total": round((e + f) / voltas, 1)}, "falasDoEngenheiro": len(eng)}


saida = {"regras": __doc__, "sessoes": {}}
for nome, pasta in SESSOES.items():
    arq = PASTA / f"{nome}_com.json"
    if not arq.exists():
        continue
    com = json.loads(arq.read_text(encoding="utf-8"))
    sem_arq = PASTA / f"{nome}_sem.json" if (PASTA / f"{nome}_sem.json").exists() else PASTA_2011 / f"{nome}_sem.json"
    sem = json.loads(sem_arq.read_text(encoding="utf-8"))
    q = carregar(pasta)
    ses = Sessao(q, float(com["t0"]))
    voltas = len(set(ses.N.tolist()))
    reg = com.get("registroDoEngenheiro") or []
    # o foco ao longo da sessao
    focos = [{"volta": x.get("volta"), "trecho": x.get("trecho"), "saiu": x.get("saiu"), "origem": x.get("origem"),
              "motivo": x.get("motivo"), "t": t_de(x)} for x in reg if x["tipo"] == "foco"]
    confs = [{"volta": x.get("volta"), "trecho": x.get("trecho"), "aplicada": x.get("aplicada"), "texto": x.get("texto"),
              "voltasEmFoco": x.get("voltasEmFoco")} for x in reg if x["tipo"] == "conferencia"]
    voltas_que_contam = [x.get("volta") for x in reg if x["tipo"] == "volta"]
    planos = [dict(x, t=t_de(x)) for x in reg if x["tipo"] == "plano"]
    # a ficha e o lembrete
    falas = []
    for x in reg:
        if x["tipo"] not in ("ficha", "lembrete") or not x.get("voz"):
            continue
        t = float(x.get("t") or 0.0)
        ini = t + P.LATENCIA_NO_JOGO_S
        fim = ini + float(x.get("duracaoS") or 0.0)
        acao = ACAO[TIPO[x["trecho"]]]
        t_acao, tipo, _ = ses.acao(x["trecho"], acao, ini)
        t_ponto = ses.passou(float(x["sPonto"]), ini) if x.get("sPonto") is not None else None
        falas.append({"tipo": x["tipo"], "volta": ses.volta(t), "trecho": x["trecho"], "tipoDaFicha": TIPO[x["trecho"]],
                      "fala": x.get("fala"),
                      "sFala": x.get("sFala"), "duracaoS": x.get("duracaoS"), "folgaPlanejadaS": x.get("folgaPlanejadaS"),
                      "ateASuaAcaoS": None if t_acao is None else round(t_acao - fim, 2), "aSuaAcao": tipo,
                      "ateOPontoS": None if t_ponto is None else round(t_ponto - fim, 2)})
    # a contagem de bipes: cada passagem pela curva de foco com frenagem, enquanto ela e o foco
    bipes = []
    for i, p in enumerate(planos):
        if not p.get("sBipes") or p["t"] is None:
            continue
        ate = planos[i + 1]["t"] if i + 1 < len(planos) and planos[i + 1]["t"] is not None else ses.T[-1]
        foco_saiu = next((f["t"] for f in focos if f["t"] is not None and f["t"] > p["t"] and f["t"] < ate), None)
        ate = foco_saiu or ate
        desde = p["t"]
        while desde < ate:
            t_b = ses.passou(float(p["sBipes"][-1]), desde)
            if t_b is None or t_b > ate:
                break
            t_f, tipo, t_ap = ses.acao(p["trecho"], "freie", t_b - 20.0)
            if t_f is not None and tipo == "frenagem" and abs(t_f - t_b) < 10:
                i_b = min(int(np.searchsorted(ses.T, t_b)), len(ses.T) - 1)
                i_f = min(int(np.searchsorted(ses.T, t_f)), len(ses.T) - 1)
                bipes.append({"volta": ses.volta(t_b), "trecho": p["trecho"], "sBipe": p["sBipes"][-1],
                              "aSuaFrenagemDepoisDoBipeS": round(t_f - t_b, 2),
                              "aSuaFrenagemDepoisDoBipeM": round(((ses.S[i_f] - ses.S[i_b] + L / 2) % L) - L / 2, 1)})
            desde = (t_ap or t_b) + 5.0
    # o feedback: os cortes e o que mudou de bloco contra a rodada sem o engenheiro
    antes = {}
    for m in feedback(sem["mensagens"]):
        antes.setdefault(chave(m), []).append(m)
    mudou, so_com = [], []
    for m in feedback(com["mensagens"]):
        lst = antes.get(chave(m)) or []
        if not lst:
            so_com.append({k: m.get(k) for k in ("origem", "volta", "titulo", "fala", "sCarro")})
            continue
        x = lst.pop(0)
        if x.get("voltaDoCarro") != m.get("voltaDoCarro") or abs(float(x.get("sCarro") or 0) - float(m.get("sCarro") or 0)) > 300:
            mudou.append({"origem": m["origem"], "volta": m.get("volta"), "titulo": m.get("titulo"),
                          "sem": {"voltaDoCarro": x.get("voltaDoCarro"), "sCarro": x.get("sCarro")},
                          "com": {"voltaDoCarro": m.get("voltaDoCarro"), "sCarro": m.get("sCarro")}})
    cortes = [{"cortada": c["cortada"], "pelaFala": c.get("pelaFala"), "restavaS": c.get("restavaS")} for c in reg if c["tipo"] == "corte"]
    # os segundos de fala por volta, antes e depois
    depois = segundos([float(f["duracaoS"] or 0.0) for f in falas], feedback(com["mensagens"]), voltas)
    if nome == "2026-11-21":
        real_reg = [json.loads(x) for x in REAL_2111.with_suffix(".engenheiro.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        real_msg = [json.loads(x) for x in REAL_2111.with_suffix(".jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        antes_s = segundos(list(falas_do_engenheiro_de_2011(real_reg).values()), feedback(real_msg), voltas)
        antes_s["origem"] = "a sessão real (o código de 20/11 no jogo)"
    else:
        b = json.loads((PASTA_2011 / f"{nome}_com_b.json").read_text(encoding="utf-8"))
        antes_s = segundos(list(falas_do_engenheiro_de_2011(b.get("registroDoEngenheiro") or []).values()),
                           feedback(b["mensagens"]), voltas)
        antes_s["origem"] = "a rodada da D.1 de 20/11, molde (b)"
    saida["sessoes"][nome] = {
        "voltasQueContam": voltas_que_contam, "focos": focos, "conferencias": confs,
        "fichas": [f for f in falas if f["tipo"] == "ficha"], "lembretes": [f for f in falas if f["tipo"] == "lembrete"],
        "folgaAteASuaAcaoS": resumo([f["ateASuaAcaoS"] for f in falas]),
        "folgaAteOPontoS": resumo([f["ateOPontoS"] for f in falas]),
        "folgaAbaixoDe3S": sum(1 for f in falas if f["ateASuaAcaoS"] is not None and f["ateASuaAcaoS"] < 3.0),
        "bipes": bipes, "frenagemDepoisDoUltimoBipeS": resumo([b["aSuaFrenagemDepoisDoBipeS"] for b in bipes]),
        "frenagemDepoisDoUltimoBipeM": resumo([b["aSuaFrenagemDepoisDoBipeM"] for b in bipes]),
        "planosSemFicha": Counter((p.get("ficha") or {}).get("motivo") for p in planos if (p.get("ficha") or {}).get("motivo")),
        "planosSemLembrete": Counter((p.get("lembrete") or {}).get("motivo") for p in planos if (p.get("lembrete") or {}).get("motivo")),
        "cortes": cortes,
        "feedback": {"sem": len(feedback(sem["mensagens"])), "com": len(feedback(com["mensagens"])), "mudaramDeBloco": mudou,
                     "soCom": so_com, "pendentesNoFim": {"sem": sem["pendentesNoFim"], "com": com["pendentesNoFim"]},
                     "comCausaNaVoz": {"sem": sum(1 for m in feedback(sem["mensagens"]) if fala_tem_causa(m.get("fala"))),
                                       "com": sum(1 for m in feedback(com["mensagens"]) if fala_tem_causa(m.get("fala")))}},
        "segundosDeFala": {"antes": antes_s, "depois": depois},
    }
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1, default=lambda o: dict(o)), encoding="utf-8")
for nome, d in saida["sessoes"].items():
    print(nome, "| contam", d["voltasQueContam"])
    for f in d["focos"]:
        print("   foco", f["volta"], f["trecho"], f.get("saiu"), f.get("origem"), f.get("motivo"))
    print("   conferencias", [(c["volta"], c["trecho"], c["aplicada"]) for c in d["conferencias"]])
    print("   fichas", len(d["fichas"]), "lembretes", len(d["lembretes"]), "| folga acao", d["folgaAteASuaAcaoS"],
          "<3s", d["folgaAbaixoDe3S"], "| ponto", d["folgaAteOPontoS"])
    print("   bipe->frenagem s", d["frenagemDepoisDoUltimoBipeS"], "m", d["frenagemDepoisDoUltimoBipeM"])
    print("   sem ficha", dict(d["planosSemFicha"]), "sem lembrete", dict(d["planosSemLembrete"]))
    print("   cortes", len(d["cortes"]), "| mudaram", len(d["feedback"]["mudaramDeBloco"]), "| fb", d["feedback"]["sem"],
          d["feedback"]["com"], "causa", d["feedback"]["comCausaNaVoz"], "| pend", d["feedback"]["pendentesNoFim"])
    print("   fala por volta antes", d["segundosDeFala"]["antes"]["porVolta"], "depois", d["segundosDeFala"]["depois"]["porVolta"])
