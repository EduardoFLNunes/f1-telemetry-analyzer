"""Pedido 52, E.3: a leitura da sessao do teste (2026-11-20_19-06-14) e as opcoes para todo aviso sair pela voz a
tempo. So leitura: a gravacao, o registro do radio e do engenheiro, o log do CSP, a lista reproduzida fora do
tempo real (`_radio_offline.py` nesta sessao) e as duracoes medidas (`_e3_falas_curtas.json`).

1. **Cada aviso:** a hora em que o carro passou o `s_fala` (o aviso aparece na janela nesse quadro: a lista ja
   esta no jogo e o app desenha pelo `s` do carro), a voz ou o motivo, a entrega no radio, a hora em que o jogo
   tocou ("voz: url tocou" no log do CSP), a latencia (tocou menos passou o `s_fala`) e a folga real ate a acao
   do piloto naquela passagem. **A acao do piloto** num trecho e buscada desde a saida do trecho anterior (a regra
   do engenheiro, ADR 0033, emenda, itens 4 e 10) ate o apice: para "freie", a frenagem (freio de 0,15 ou mais;
   uma pisada em andamento na saida conta desde o comeco); para "vire", a primeira frenagem ou o primeiro alivio
   (acelerador abaixo de 0,90); sem nenhum dos dois, e para "sem tirar o pe", a entrada da curva.
2. **As opcoes,** nas voltas completas da sessao (a de saida fica fora): em cada trecho com aviso, o "pedaco
   livre" do piloto antes da acao (acelerador em 0,90 ou mais e freio abaixo de 0,15, desde a acao anterior) e a
   folga = a acao menos o fim da fala. A fala cabe se a folga for de pelo menos 1,0 s (ADR 0033, item 5).

Uso (na pasta backend): python <este arquivo> <pasta da sessao> <custom_shaders_patch.log> <sessao_com.json>
  <falas_curtas.json> <saida.json>
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

PASTA, LOG, OFFLINE, FALAS, SAIDA = (Path(x) for x in sys.argv[1:6])
REPO = Path("..").resolve()
RADIO = REPO / "data" / "radio" / PASTA.name
track = carregar_geometria(REPO)
L = float(track.length)
trechos = R.trechos_da_pista(track)
por_nome = {t.nome: t for t in trechos}
MARGEM_S = R.FOLGA_ANTES_DA_FREADA_S          # 1,0 s

# ── a gravacao, no relogio local (o gravador esta 3 h adiantado) ─────────
meta = json.loads((PASTA / "metadata.json").read_text(encoding="utf-8"))
inicio_local = datetime.fromisoformat(meta["startedAt"]).timestamp()
linhas = []
voltas_raw = []
for lap in iter_laps(Session(session_id=PASTA.name, directory=PASTA, track="vhe_interlagos")):
    f = lap.frame
    s, _ = track.project(np.c_[f["x"].to_numpy(float), f["z"].to_numpy(float)])
    bloco = np.c_[f["timestamp_s"].to_numpy(float), np.asarray(s, float), f["speed_kmh"].to_numpy(float),
                  np.nan_to_num(f["throttle"].to_numpy(float)), np.nan_to_num(f["brake"].to_numpy(float)),
                  np.full(len(f), len(voltas_raw)), f["lap_time_s"].to_numpy(float)]
    linhas.append(bloco)
    voltas_raw.append(float(f["lap_time_s"].max()))
Q = np.vstack(linhas)
Q = Q[np.argsort(Q[:, 0])]
DESLOC = round((Q[0, 0] - inicio_local) / 3600.0) * 3600.0
Q[:, 0] -= DESLOC
T, SS, V, ACEL, FREIO, VOLTA = Q[:, 0], Q[:, 1], Q[:, 2], Q[:, 3], Q[:, 4], Q[:, 5].astype(int)


def hora(t):
    return datetime.fromtimestamp(t).strftime("%H:%M:%S.%f")[:-4]


def passou(s_alvo, desde_t, ate_m=L / 2):
    """O instante em que o carro passa `s_alvo` pela primeira vez depois de `desde_t` (interpolado)."""
    i0 = int(np.searchsorted(T, desde_t))
    for i in range(max(i0, 1), len(T)):
        a, b = SS[i - 1], SS[i]
        anda = (b - a) % L
        if anda > 200:            # salto (boxes, reinicio)
            continue
        falta = (s_alvo - a) % L
        if falta <= anda and anda > 0:
            k = falta / anda
            return float(T[i - 1] + k * (T[i] - T[i - 1]))
        if (s_alvo - a) % L > ate_m and (a - s_alvo) % L < 5:
            pass
    return None


def passagens(s_alvo):
    """Todos os instantes em que o carro passa `s_alvo` na sessao."""
    out, t = [], float(T[0])
    while True:
        x = passou(s_alvo, t)
        if x is None:
            return out
        out.append(x)
        t = x + 5.0


def ocorrencias(nome, acao):
    """Cada passagem do carro pelo trecho: a ancora (a saida do trecho anterior), o apice e a acao do piloto."""
    k = [x.nome for x in trechos].index(nome)
    trecho = trechos[k]
    out = []
    for t0 in passagens(R.inicio_da_busca_da_freada(trechos, k) % L):
        t_ap = passou(float(trecho.apice_s), t0)
        if t_ap is None or t_ap - t0 > 40:
            continue
        idx = np.flatnonzero((T >= t0) & (T <= t_ap))
        i_acao, tipo = None, None
        if acao != R.SEM_TIRAR_O_PE and idx.size:
            if acao == "freie" and FREIO[idx[0]] >= R.FREIO_DA_FREADA:
                j = idx[0]
                while j > 0 and FREIO[j - 1] >= R.FREIO_DA_FREADA:
                    j -= 1
                i_acao, tipo = j, "frenagem"
            else:
                cond = FREIO[idx] >= R.FREIO_DA_FREADA
                if acao != "freie":
                    cond = cond | (ACEL[idx] < R.ACELERADOR_DA_RETOMADA)
                hits = np.flatnonzero(cond)
                if hits.size:
                    i_acao = idx[hits[0]]
                    tipo = "frenagem" if FREIO[i_acao] >= R.FREIO_DA_FREADA else "alívio"
        if i_acao is not None:
            t_acao, s_acao = float(T[i_acao]), float(SS[i_acao])
        else:
            t_acao, s_acao, tipo = passou(float(trecho.entrada_s), t0), float(trecho.entrada_s), "entrada"
        if t_acao is None:
            continue
        out.append({"ancora": t0, "apice": t_ap, "t": t_acao, "s": s_acao, "tipo": tipo,
                    "volta": int(VOLTA[min(int(np.searchsorted(T, t_acao)), len(T) - 1)])})
    return out


def acao_do_piloto(nome, acao, t_fala):
    """A passagem do trecho cujo apice vem depois do aviso aparecer."""
    oc = next((o for o in ocorrencias(nome, acao) if o["apice"] > t_fala), None)
    return (None, None, None) if oc is None else (oc["t"], oc["s"], oc["tipo"])


# ── o registro, a lista e o log ──────────────────────────────────────────
reg = [json.loads(x) for x in (RADIO.with_name(RADIO.name + ".engenheiro.jsonl")).read_text(encoding="utf-8").splitlines() if x.strip()]
entregues = [json.loads(x) for x in (RADIO.with_name(RADIO.name + ".jsonl")).read_text(encoding="utf-8").splitlines() if x.strip()]
offline = json.loads(OFFLINE.read_text(encoding="utf-8"))
lista = {i["trecho"]: i for i in offline["engenheiro"]["lista"]}
texto = LOG.read_text(encoding="utf-8", errors="replace")
m = re.search(r"date & time: (\d{4})\.(\d{2})\.(\d{2})/(\d{2}):(\d{2}):(\d{2})\.(\d{3})", texto)
t_log = datetime(*[int(x) for x in m.groups()[:6]], int(m.group(7)) * 1000).timestamp()
tocou = [t_log + int(ms) / 1000.0 for ms in re.findall(r"^\s*(\d+)\s+M .*\[radio_engenheiro\] voz: url tocou", texto, re.M)]
falhou = re.findall(r"\[radio_engenheiro\] voz: falhou[^\n]*", texto)
audios = {p.name for p in (REPO / "data" / "radio" / "audio").glob("*_aviso_*.wav")}

# ── 1. cada aviso ────────────────────────────────────────────────────────
import hashlib  # noqa: E402

avisos = []
for r in reg:
    if r["tipo"] != "aviso":
        continue
    item = lista[r["trecho"]]
    t_em = datetime.fromisoformat(r["em"]).timestamp()
    t_fala = passou(float(r["sFala"]), t_em - 3.0)
    t_dito = passou(float(item["sDito"]), t_fala) if t_fala else None
    t_acao, s_acao, tipo = acao_do_piloto(r["trecho"], item["acao"], t_fala) if t_fala else (None, None, None)
    a = {"trecho": r["trecho"], "acao": item["acao"], "frase": item["frase"], "voltaDaGravacao": int(VOLTA[np.searchsorted(T, t_fala)]),
         "apareceuEm": hora(t_fala), "sFala": r["sFala"], "vKmh": r["velocidadeKmh"], "voz": r["voz"],
         "motivo": r["porqueSoNaJanela"], "sDito": item["sDito"],
         "ateOPontoDitoS": round(t_dito - t_fala, 2) if t_dito else None,
         "acaoDoPiloto": tipo, "sAcaoDoPiloto": None if s_acao is None else round(s_acao, 1),
         "ateASuaAcaoS": round(t_acao - t_fala, 2) if t_acao else None}
    if r["voz"]:
        nome = hashlib.sha1(R.fala_do_aviso(r["trecho"], item["frase"]).encode("utf-8")).hexdigest()[:12]
        a["vozGerada"] = any(n.endswith(f"_aviso_{nome}.wav") for n in audios)
        ent = next((e for e in entregues if e.get("origem") == "aviso" and e.get("curva") == r["trecho"]
                    and abs(datetime.fromisoformat(e["entregueEm"]).timestamp() - t_em) <= 2), None)
        a["entregue"] = ent is not None and {"id": ent["id"], "em": ent["entregueEm"][11:]}
        t_toque = next((t for t in tocou if 0 <= t - t_fala <= 15), None)
        a["tocouNoJogo"] = hora(t_toque) if t_toque else None
        if t_toque:
            fim = t_toque + float(item["duracaoS"])
            a["latenciaS"] = round(t_toque - t_fala, 2)
            a["sNoToque"] = round(float(np.interp(t_toque, T, np.unwrap(SS, period=L)) % L), 1)
            a["sNoFimDaFala"] = round(float(np.interp(fim, T, np.unwrap(SS, period=L)) % L), 1)
            a["fimDaFalaAteASuaAcaoS"] = round(t_acao - fim, 2) if t_acao else None
            a["fimDaFalaAteOPontoDitoS"] = round(t_dito - fim, 2) if t_dito else None
    avisos.append(a)

# ── 2. os pedacos livres e as opcoes ─────────────────────────────────────
falas = json.loads(FALAS.read_text(encoding="utf-8"))["falas"]
com_aviso = [n for n in ["C01", "C02", "C04", "C05", "C06", "C07", "C09", "C11", "C12"]]
DUR_HOJE = {n: float(lista[n]["duracaoS"]) for n in com_aviso}
CURTA = {"freie": falas["curta_freie_placa"]["1.4"], "vire": falas["curta_vire_zebra"]["1.4"],
         "acelere": falas["curta_acelere_zebra"]["1.4"], R.SEM_TIRAR_O_PE: falas["hoje_sem_tirar"]["1.4"]}
CURTA_17 = {"freie": falas["curta_freie_placa"]["1.7"], "vire": falas["curta_vire_zebra"]["1.7"],
            "acelere": falas["curta_acelere_zebra"]["1.7"], R.SEM_TIRAR_O_PE: falas["hoje_sem_tirar"]["1.7"]}
FATOR_17 = np.mean([falas[k]["1.7"] / falas[k]["1.4"] for k in falas])
LAT_HOJE = 0.45           # a C01 desta sessao, sem cartao na frente (a C04 teve 2,0 s, pela fila do cartao)
LAT_LOCAL = 0.10          # o aviso disparado no jogo pelo s do carro, com o audio ja baixado (estimativa)
BIPE_S = 0.25

voltas_completas = list(range(1, len(voltas_raw) - 1))      # sem a de saida (0) e sem a ultima (incompleta)


def pedacos():
    """Os pedacos livres da sessao inteira (atravessam a linha): (t_ini, t_fim, s_ini, s_fim)."""
    livre = (ACEL >= R.ACELERADOR_DA_RETOMADA) & (FREIO < R.FREIO_DA_FREADA) & (V > 30)
    out, ini = [], None
    for j, ok in enumerate(livre):
        salto = j > 0 and (T[j] - T[j - 1] > 1.0 or (SS[j] - SS[j - 1]) % L > 200)
        if ini is not None and (not ok or salto or j == len(livre) - 1):
            if T[j - 1] - T[ini] > 0.05:
                out.append((float(T[ini]), float(T[j - 1]), float(SS[ini]), float(SS[j - 1])))
            ini = None
        if ok and ini is None:
            ini = j
    return out


PEDACOS = pedacos()


def acoes_da_volta(volta):
    """Para cada trecho com aviso: a acao do piloto na volta e o pedaco livre logo antes dela."""
    out = {}
    for n in com_aviso:
        oc = next((o for o in ocorrencias(n, lista[n]["acao"]) if o["volta"] == volta), None)
        if oc is None:
            continue
        antes = [p for p in PEDACOS if p[1] <= oc["t"] + 0.05 and p[1] >= oc["t"] - 120]
        livre = antes[-1] if antes and oc["t"] - antes[-1][1] < 0.3 else None
        out[n] = {"t": oc["t"], "s": oc["s"], "tipo": oc["tipo"], "livre": livre,
                  "livreS": round(livre[1] - livre[0], 2) if livre else 0.0,
                  "livreDesdeS": None if livre is None else round(livre[2], 1), "pcs": antes}
    return out


ACOES = {v: acoes_da_volta(v) for v in voltas_completas}


def opcao(nome, dur, lat, regra="proprio", grupos=None, max_folga=None, max_pedacos=None):
    """Conta, em cada volta, os trechos com aviso cuja fala cabe e a folga (a acao menos o fim da fala).
    regra: "proprio" (o pedaco livre logo antes da acao), "antes" (qualquer pedaco livre anterior na volta, o
    mais perto que caiba, um aviso por vez: os pedacos ocupados nao recebem outro por cima)."""
    por_volta = []
    for v, acoes in ACOES.items():
        ocupado = {}
        res = {}
        for n in com_aviso:
            if n not in acoes:
                continue
            a = acoes[n]
            d = dur[n] if isinstance(dur, dict) else dur(n)
            cand = [a["livre"]] if regra == "proprio" else list(reversed(a["pcs"]))
            if max_pedacos is not None:
                cand = cand[:max_pedacos]
            for p in cand:
                if p is None:
                    continue
                ini = max(p[0], ocupado.get(p, p[0])) + lat
                fim = ini + d
                if fim <= p[1] and a["t"] - fim >= MARGEM_S and (max_folga is None or a["t"] - fim <= max_folga):
                    res[n] = round(a["t"] - fim, 2)
                    ocupado[p] = fim + 0.3
                    break
        por_volta.append({"volta": v, "comVoz": len(res), "trechos": res})
    todas = [f for x in por_volta for f in x["trechos"].values()]
    return {"opcao": nome, "porVolta": por_volta,
            "trechosComVozPorVolta": [x["comVoz"] for x in por_volta],
            "folgaS": {"min": min(todas) if todas else None, "mediana": float(np.median(todas)) if todas else None,
                       "max": max(todas) if todas else None}}


opcoes = [
    opcao("A. hoje, sem a regra do bloco do modelo nem a de 'a referência freia' (o pedaço livre do piloto)", DUR_HOJE, LAT_HOJE),
    opcao("B. A + o aviso disparado no jogo, com o áudio já baixado (latência 0,1 s)", DUR_HOJE, LAT_LOCAL),
    opcao("C. B + a fala curta (verbo e marco: 'Freie no cem, mais dez.')", lambda n: CURTA[lista[n]["acao"]], LAT_LOCAL),
    opcao("D. C + a voz a 1,7x", lambda n: CURTA_17[lista[n]["acao"]], LAT_LOCAL),
    opcao("E. B + avisar mais cedo (o pedaço livre anterior mais perto que caiba)", DUR_HOJE, LAT_LOCAL, regra="antes"),
    opcao("F. C + avisar mais cedo", lambda n: CURTA[lista[n]["acao"]], LAT_LOCAL, regra="antes"),
    opcao("E20. E, com no máximo 20 s entre o fim da fala e a ação", DUR_HOJE, LAT_LOCAL, regra="antes", max_folga=20.0),
    opcao("F20. F, com no máximo 20 s entre o fim da fala e a ação", lambda n: CURTA[lista[n]["acao"]], LAT_LOCAL, regra="antes", max_folga=20.0),
    opcao("H. C + juntar com a curva anterior (só os dois pedaços livres mais perto)", lambda n: CURTA[lista[n]["acao"]], LAT_LOCAL,
          regra="antes", max_pedacos=2),
]
# G. o bipe no ponto: nao precisa de pedaco livre (nao e fala); vale em todo trecho com acao, com a folga escolhida
opcoes.append({"opcao": "G. o bipe (0,25 s) no jogo, 1,0 s antes da sua ação, junto com a marca",
               "trechosComVozPorVolta": [len(a) for a in ACOES.values()], "folgaS": {"min": 1.0, "mediana": 1.0, "max": 1.0},
               "porVolta": [{"volta": v, "comVoz": len(a), "trechos": {n: 1.0 for n in a}} for v, a in ACOES.items()]})

# a lista nas retas longas: quantos avisos curtos cabem em cada reta, por volta
retas = []
for v, acoes in ACOES.items():
    for n in ("C01", "C04"):
        if n in acoes and acoes[n]["livre"]:
            p = acoes[n]["livre"]
            cabe = (p[1] - p[0]) - LAT_LOCAL - MARGEM_S
            retas.append({"volta": v, "reta": "boxes" if n == "C01" else "oposta", "livreS": round(p[1] - p[0], 2),
                          "avisosCurtos": int(max(0, cabe) // (np.mean(list(CURTA.values())) + 0.4)),
                          "avisosCurtos17": int(max(0, cabe) // (np.mean(list(CURTA_17.values())) + 0.4))})

# o tempo entre as acoes, por trecho e por volta (o pedido: "entre a acao anterior e a proxima frenagem"):
# o pedaco livre (desde a acao anterior acabar) e desde o comeco da acao da curva anterior (as 14 curvas)
curvas = [x.nome for x in trechos if x.tem_curva]
TODAS = {n: ocorrencias(n, lista.get(n, {}).get("acao") or "vire") for n in curvas}
entre = []
for n in com_aviso:
    linha = {"trecho": n}
    ant = curvas[curvas.index(n) - 1]
    for v, acoes in ACOES.items():
        a = acoes.get(n)
        if a is not None:
            prev = [o["t"] for o in TODAS[ant] if o["t"] < a["t"] - 0.05]
            a["desdeAAnteriorS"] = round(a["t"] - prev[-1], 2) if prev else None
        linha[f"volta{v}"] = None if a is None else {"livreS": a["livreS"], "livreDesde": a["livreDesdeS"], "acao": a["tipo"],
                                                       "sAcao": round(a["s"], 1), "desdeAAcaoDaCurvaAnteriorS": a["desdeAAnteriorS"]}
    entre.append(linha)

saida = {"sessao": PASTA.name, "deslocamentoDoRelogioS": DESLOC, "voltas": [{"volta": i, "tempoS": t} for i, t in enumerate(voltas_raw)],
         "avisos": avisos, "vozTocouNoJogo": [hora(t) for t in tocou], "vozFalhou": falhou,
         "entreAcoes": entre, "opcoes": opcoes, "retasLongas": retas,
         "latencias": {"hoje": LAT_HOJE, "local": LAT_LOCAL}, "fator17": round(float(FATOR_17), 3)}
SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
for a in avisos:
    print(a)
print("tocou", saida["vozTocouNoJogo"], "falhou", falhou)
for e in entre:
    print(e)
for o in opcoes:
    print(o["opcao"], "|", o["trechosComVozPorVolta"], o["folgaS"])
    for x in o["porVolta"]:
        print("     ", x)
for r in retas:
    print(r)
