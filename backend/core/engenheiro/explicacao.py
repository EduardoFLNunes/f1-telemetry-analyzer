"""O engenheiro que ensina (pedido 52; ADR 0033, decisoes do Eduardo de 22/11): funcoes puras, sem estado,
testadas com dados sinteticos. Vale para qualquer pista e qualquer trecho.

* **as medidas de cada curva** (item 1), de uma passagem (a da volta de referencia ou a do piloto): a chegada, a
  frenagem, o ponto de virar, a frenagem reta, o trecho sem pedal, a minima, o apice, o acelerador cheio, a saida e
  a curva seguinte;
* **os textos** nos tres niveis (item 3): iniciante (a explicacao longa), amador (resumida) e pro (tecnica), pelos
  limites das palavras do item 2 (a frase se adapta sozinha quando a volta de referencia muda);
* **a analise depois da curva** (item 4): as diferencas da passagem do piloto acima dos limites, na ordem do tempo
  que cada fase custou contra a referencia, e o texto nos tres niveis;
* **o treino** (item 7): o relatorio de X voltas, o volume (o tempo de fala) e a orientacao.

Os pedais da IA dizem onde e quando, nunca com quanta forca (ADR 0032, item 5); a marcha fica fora.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import plano as P
from . import regras as R

NIVEIS = ("iniciante", "amador", "pro")
NIVEL_PADRAO = "amador"
ESCOPOS = ("uma", "algumas", "inteira")
TREINO_PADRAO = 5

# item 1
ANTES_DA_FRENAGEM_M = 20.0
ANTES_DA_ENTRADA_M = 50.0
VIRAR_M = 1.0                      # o carro se move 1 m para dentro
RETA_M = 1.0                       # menos de 1 m de lado durante a frenagem
FREIO = 0.15
ACELERADOR_SOLTO = 0.10
DEPOIS_DA_SAIDA_M = 100.0
# item 2: os limites das palavras
QUASE_NA_PLACA_M = 15.0
LOGO_DEPOIS_DA_PLACA_M = 40.0
NO_COMECO_DA_ZEBRA_M = 10.0
ZEBRA_PERTO_M = 40.0
ROLAR_M = 15.0
PERTO_DA_BORDA_M = 3.0
ACELERE_CEDO_M = 15.0
PISTA_TODA_M = 1.5
# item 4: os limites da analise
DIF_FRENAGEM_M = R.APLICADA_FREADA_M
DIF_VIRAR_M = 10.0
DIF_MINIMA_KMH = R.APLICADA_MINIMA_KMH
DIF_APICE_M = 1.0
DIF_ACELERADOR_M = 10.0
DIF_SAIDA_M = 1.0
MAXIMO_DE_DIFERENCAS = 2
DEPOIS_DA_SAIDA_PARA_ANALISAR_M = 30.0
# item 7
PALAVRAS_POR_S = 2.5
FEMININO = {1: "uma", 2: "duas"}           # "duas voltas lentas"
VOLTA_LENTA_S = 60.0
VOLTAS_LENTAS_S = 180.0


def _entre(a: float, b: float, s: float, L: float) -> bool:
    a, b, s = a % L, b % L, s % L
    return a <= s <= b if a <= b else (s >= a or s <= b)


def _janela(track, a: float, b: float) -> np.ndarray:
    """Os indices da grade de `a` a `b`, na ordem da pista (pela linha, se preciso)."""
    s = np.asarray(track.s, float)
    L = float(track.length)
    a, b = a % L, b % L
    if a <= b:
        return np.flatnonzero((s >= a) & (s <= b))
    return np.concatenate([np.flatnonzero(s >= a), np.flatnonzero(s <= b)])


def _d(s1: float, s2: float, L: float) -> float:
    """s1 - s2 na volta, de -L/2 a L/2."""
    return ((float(s1) - float(s2) + L / 2) % L) - L / 2


def _m5(x: float) -> int:
    return int(5 * round(float(x) / 5.0))


def _nome(n: Optional[int], trecho: str) -> str:
    return P.NUMEROS.get(int(n), str(n)) if n is not None else trecho


def _cap(texto: str) -> str:
    return f"{texto[0].upper()}{texto[1:]}" if texto else texto


# ── as medidas (item 1) ───────────────────────────────────────────────────

def medidas_da_curva(grade: Dict[str, np.ndarray], track, trechos: Sequence[Any], k: int, lado: Optional[str],
                     marcos: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """As medidas da curva `k` numa passagem. `lado`: o lado da curva (esquerda ou direita). None: sem curva, ou a
    passagem nao tem os dados da curva."""
    from core.radio.analise import freada_desde

    t = trechos[k]
    if not t.tem_curva or lado is None:
        return None
    L = float(track.length)
    s = np.asarray(track.s, float)
    v = np.asarray(grade["velocidade"], float)
    acel = np.asarray(grade["acelerador"], float)
    freio = np.asarray(grade["freio"], float)
    lat = np.asarray(grade["lateral"], float)
    esq = np.asarray(getattr(track, "width_left", np.full(s.size, 6.0)), float)
    dir_ = np.asarray(getattr(track, "width_right", np.full(s.size, 6.0)), float)
    dentro = 1.0 if lado == "esquerda" else -1.0
    busca = R.inicio_da_busca_da_freada(trechos, k)
    toda = _janela(track, busca, float(t.saida_s) + DEPOIS_DA_SAIDA_M)
    if not len(toda) or not np.all(np.isfinite(v[toda])) or not np.all(np.isfinite(lat[toda])):
        return None
    freio = np.nan_to_num(freio)
    acel = np.nan_to_num(acel)
    i = lambda x: int(track.index_of(float(x) % L))  # noqa: E731
    freada = freada_desde(freio, track, busca, float(t.apice_s))
    out: Dict[str, Any] = {"trecho": t.nome, "lado": lado, "freada": None if freada is None else round(float(freada), 1)}
    # a chegada
    s0 = (float(freada) - ANTES_DA_FRENAGEM_M) if freada is not None else (float(t.entrada_s) - ANTES_DA_ENTRADA_M)
    lat0 = float(lat[i(s0)])
    meia = esq[i(s0)] if lat0 > 0 else dir_[i(s0)]
    out["chegada"] = ("esquerda" if lat0 > 0 else "direita") if abs(lat0) >= 0.5 * float(meia) else "meio"
    out["lateralNaChegada"] = round(lat0, 2)
    # a frenagem
    if freada is not None:
        jf = _janela(track, float(freada), float(t.apice_s))
        pisado = jf[freio[jf] >= FREIO]
        fim = float(s[pisado[-1]]) if len(pisado) else float(freada)
        out.update(vFreadaKmh=round(float(v[i(freada)]), 1), fimDaFrenagem=round(fim, 1),
                   vFimDaFrenagemKmh=round(float(v[i(fim)]), 1), frenagemM=round((fim - float(freada)) % L, 1),
                   reta=abs(float(lat[i(fim)]) - float(lat[i(freada)])) < RETA_M)
    # o ponto de virar
    de = float(freada) if freada is not None else float(t.entrada_s) - ANTES_DA_ENTRADA_M
    jv = _janela(track, de, float(t.apice_s))
    mov = (lat[jv] - lat0) * dentro
    vira = jv[np.flatnonzero(mov >= VIRAR_M)]
    out["virar"] = round(float(s[vira[0]]), 1) if len(vira) else round(float(t.entrada_s), 1)
    # a minima
    jm = _janela(track, float(t.entrada_s) - ANTES_DA_ENTRADA_M, float(t.saida_s))
    im = jm[int(np.argmin(v[jm]))]
    out.update(minimaKmh=round(float(v[im]), 1), sMinima=round(float(s[im]), 1))
    # o trecho sem pedal, entre a frenagem (ou o ponto de virar) e a minima
    jr = _janela(track, float(out.get("fimDaFrenagem") or out["virar"]), float(out["sMinima"]))
    solto = (freio[jr] < FREIO) & (acel[jr] < ACELERADOR_SOLTO)
    maior = corrida = 0
    for b in solto:
        corrida = corrida + 1 if b else 0
        maior = max(maior, corrida)
    passo = L / float(len(s))
    out["semPedalM"] = round(maior * passo, 1)
    # o apice: o ponto mais perto da borda de dentro
    ja = _janela(track, float(t.entrada_s), float(t.saida_s))
    borda_dentro = esq[ja] if lado == "esquerda" else dir_[ja]
    dist = borda_dentro - lat[ja] * dentro
    ia = int(np.argmin(dist))
    out.update(sApice=round(float(s[ja[ia]]), 1), apiceDaBordaM=round(float(dist[ia]), 2),
               vApiceKmh=round(float(v[ja[ia]]), 1))
    # o acelerador cheio, depois da minima
    jc = _janela(track, float(out["sMinima"]), float(t.saida_s) + DEPOIS_DA_SAIDA_M)
    cheio = jc[np.flatnonzero(acel[jc] >= R.ACELERADOR_DA_RETOMADA)]
    out["aceleradorCheio"] = round(float(s[cheio[0]]), 1) if len(cheio) else None
    # a saida: o ponto mais perto da borda de fora
    js = _janela(track, float(out["sMinima"]), float(t.saida_s) + DEPOIS_DA_SAIDA_M)
    borda_fora = dir_[js] if lado == "esquerda" else esq[js]
    fora = borda_fora + lat[js] * dentro
    iss = int(np.argmin(fora))
    out.update(sSaida=round(float(s[js[iss]]), 1), saidaDaBordaM=round(float(fora[iss]), 2))
    # os marcos perto: as placas da frenagem e a zebra de dentro do ponto de virar
    out["placas"] = sorted([{"s": float(m["s"]), "valor": m["valor"]} for m in marcos
                            if m.get("tipo") == "placa" and m.get("valor") is not None
                            and _entre(busca, float(t.apice_s), float(m["s"]), L)], key=lambda p: (p["s"] - busca) % L)
    zebras = [m for m in marcos if m.get("tipo") == "zebra" and m.get("lado") == lado]
    perto = sorted(zebras, key=lambda z: abs(_d(out["virar"], float(z["s"]), L)))
    out["zebraDoVirar"] = None
    if perto and abs(_d(out["virar"], float(perto[0]["s"]), L)) <= ZEBRA_PERTO_M:
        out["zebraDoVirar"] = {"s": float(perto[0]["s"]), "d": round(_d(out["virar"], float(perto[0]["s"]), L), 1)}
    return out


def tipo_da_curva(grade: Dict[str, np.ndarray], track, trechos: Sequence[Any], k: int) -> Optional[str]:
    """A regra da ficha de 21/11: com frenagem, de pe embaixo ou com um alivio."""
    from core.radio.analise import freada_desde

    t = trechos[k]
    if not t.tem_curva:
        return None
    freio = np.nan_to_num(np.asarray(grade["freio"], float))
    if freada_desde(freio, track, R.inicio_da_busca_da_freada(trechos, k), float(t.apice_s)) is not None:
        return "frenagem"
    idx = _janela(track, float(t.entrada_s) - ANTES_DA_ENTRADA_M, float(t.apice_s))
    if R.tem_alivio(grade["acelerador"], track, idx) or float(freio[idx].max()) >= 0.10:
        return "alívio"
    return "pé embaixo"


# ── os textos nos tres niveis (itens 2 e 3) ───────────────────────────────

def _onde_frear(m: Dict[str, Any], L: float, pontos: Sequence[Dict[str, Any]] = ()) -> Dict[str, str]:
    """"quase na placa de 100", "entre a placa de 200 e a de 100", "logo depois da placa de 50" ou, sem placa que
    sirva, o marco mais perto no molde (b) (a regra da ficha de 21/11, item 6)."""
    f = float(m["freada"])
    antes = [p for p in m["placas"] if _d(f, p["s"], L) >= 0]
    depois = [p for p in m["placas"] if _d(f, p["s"], L) < 0]
    a = max(antes, key=lambda p: p["s"]) if antes else None
    b = min(depois, key=lambda p: _d(p["s"], f, L)) if depois else None
    if b is not None and _d(b["s"], f, L) <= QUASE_NA_PLACA_M:
        x = _m5(_d(b["s"], f, L))
        return {"longo": f"quase na placa de {b['valor']}", "curto": f"quase no {b['valor']}",
                "pro": f"a {max(x, 5)} do {b['valor']}"}
    if a is not None and _d(f, a["s"], L) <= LOGO_DEPOIS_DA_PLACA_M and b is None:
        x = _m5(_d(f, a["s"], L))
        return {"longo": f"logo depois da placa de {a['valor']}", "curto": f"logo depois do {a['valor']}",
                "pro": f"{max(x, 5)} depois do {a['valor']}"}
    if a is not None and b is not None:
        return {"longo": f"entre a placa de {a['valor']} e a de {b['valor']}", "curto": f"entre o {a['valor']} e o {b['valor']}",
                "pro": f"{_m5(_d(f, a['s'], L))} depois do {a['valor']}"}
    if b is not None:
        x = _m5(_d(b["s"], f, L))
        return {"longo": f"{x} metros antes da placa de {b['valor']}", "curto": f"{x} antes do {b['valor']}",
                "pro": f"{x} antes do {b['valor']}"}
    fr = R.frase_da_acao("freie", f, list(pontos), L)
    texto = P.frase_falada("freie", fr.get("marco"), fr.get("d"), "b", fr["frase"])
    onde = texto[len("freie "):] if texto.startswith("freie ") else texto
    return {"longo": onde, "curto": onde, "pro": onde}


def _onde_virar(m: Dict[str, Any]) -> Dict[str, str]:
    z = m.get("zebraDoVirar")
    lado = m["lado"]
    if z is None:
        return {"longo": "no ponto de entrada", "curto": "no ponto de entrada", "pro": "entrada"}
    d = float(z["d"])
    if abs(d) <= NO_COMECO_DA_ZEBRA_M:
        return {"longo": f"no começo da zebra da {lado}", "curto": "no começo da zebra", "pro": "entrada na zebra"}
    x = _m5(abs(d))
    rel = "antes" if d < 0 else "depois"
    return {"longo": f"uns {x} metros {rel} do começo da zebra da {lado}", "curto": f"{x} {rel} da zebra",
            "pro": f"entrada {x} {rel} da zebra"}


def _apice(m: Dict[str, Any]) -> Dict[str, str]:
    d = float(m["apiceDaBordaM"])
    if d < 0:
        return {"longo": "em cima da zebra de dentro", "curto": "na zebra", "pro": "ápice na zebra"}
    if d <= PERTO_DA_BORDA_M:
        return {"longo": "perto da borda de dentro", "curto": "perto da borda",
                "pro": "colado na borda" if d < 0.5 else f"a {_meio_metro(d)} da borda"}
    return {"longo": f"a uns {round(d)} metros da borda de dentro", "curto": f"a {round(d)} metros da borda",
            "pro": f"a {round(d)} metros da borda"}


def _meio_metro(d: float) -> str:
    x = round(float(d) * 2) / 2
    inteiro = int(x)
    nomes = {0: "zero", 1: "um", 2: "dois", 3: "três"}
    base = nomes.get(inteiro, str(inteiro))
    return f"{base} e meio" if x - inteiro >= 0.5 else (f"{base} metro" if inteiro == 1 else f"{base} metros")


def _acelere(m: Dict[str, Any], L: float) -> Dict[str, Any]:
    if m.get("aceleradorCheio") is None:
        return {"cedo": False, "longo": "acelere na saída", "curto": "acelere na saída", "pro": "gás na saída", "depoisM": None}
    depois = _d(float(m["aceleradorCheio"]), float(m["sMinima"]), L)
    cedo = depois <= ACELERE_CEDO_M
    return {"cedo": cedo, "depoisM": round(depois, 1),
            "longo": "acelere cedo" if cedo else "acelere depois da mínima, quando o carro já estiver apontado,",
            "curto": "acelere cedo" if cedo else "acelere depois da mínima",
            "pro": "gás cheio na mínima" if depois < 2.5 else f"gás cheio {_m5(depois)} metros depois da mínima"}


def _saida(m: Dict[str, Any]) -> Dict[str, str]:
    d = float(m["saidaDaBordaM"])
    if d <= PISTA_TODA_M:
        return {"longo": "use a pista toda na saída", "curto": "abra na saída", "pro": "saída na borda"}
    return {"longo": f"saia a uns {round(d)} metros da borda de fora", "curto": f"saída a {round(d)} da borda",
            "pro": f"saída a {round(d)} metros da borda"}


def _seguinte(tipo: Optional[str], n_seguinte: Optional[int]) -> Optional[str]:
    if tipo is None or n_seguinte is None:
        return None
    nome = P.NUMEROS.get(int(n_seguinte), str(n_seguinte))
    return {"pé embaixo": f"a {nome} é de pé embaixo", "frenagem": f"a {nome} vem logo e tem frenagem",
            "alívio": f"a {nome} pede só um alívio"}[tipo]


def textos_da_curva(m: Dict[str, Any], numero: Optional[int], tipo: str, seguinte: Optional[str], L: float,
                    pontos: Sequence[Dict[str, Any]] = ()) -> Dict[str, str]:
    """Os textos da curva nos tres niveis (item 3). `tipo`: frenagem, pe embaixo ou alivio (a regra da ficha);
    `seguinte`: o pedaco da curva seguinte ("a cinco e de pe embaixo")."""
    nome = _nome(numero, m["trecho"])
    lado = m["lado"]
    chegada = {"meio": "pelo meio da pista", "esquerda": "pelo lado esquerdo", "direita": "pelo lado direito"}[m["chegada"]]
    ap, sa = _apice(m), _saida(m)
    ac = _acelere(m, L)
    v5 = _m5(m["minimaKmh"])
    if tipo == "frenagem" and m.get("freada") is not None:
        fr, vi = _onde_frear(m, L, pontos), _onde_virar(m)
        forte = "forte e reto " if m.get("reta") else "forte "
        rolar = m["semPedalM"] >= ROLAR_M
        ini = [f"Curva {nome}, à {lado}.", f"Venha {chegada}.", f"Freie {forte}{fr['longo']}.",
               f"Solte o freio e vire {vi['longo']}."]
        ini.append(f"Deixe o carro rolar sem acelerar até uns {v5} por hora, {ap['longo']}." if rolar else
                   f"Leve o carro até uns {v5} por hora, {ap['longo']}.")
        ini.append(f"{_cap(ac['longo'])} e {sa['longo']}" + (f", porque {seguinte}." if seguinte else "."))
        curta = {"meio": "pelo meio", "esquerda": "pela esquerda", "direita": "pela direita"}[m["chegada"]]
        ama = (f"{_cap(nome)}: {curta}, "
               f"freie {'forte ' if m.get('reta') else ''}{fr['curto']}, vire {vi['curto']}, mínima de {v5}, "
               f"{ac['curto']} e {sa['curto']}.")
        segundos = round(m["semPedalM"] / max(float(m["minimaKmh"]) / 3.6, 1.0), 1)
        pro = (f"{_cap(nome)}: frenagem {fr['pro']}, {'reta, ' if m.get('reta') else ''}de {_m5(m['vFreadaKmh'])} para "
               f"{_m5(m['vFimDaFrenagemKmh'])} em {_m5(m['frenagemM'])} metros. {_cap(vi['pro'])}"
               + (f", {segundos:.0f} segundo{'s' if segundos >= 1.5 else ''} de rolagem".replace(".", ",") if rolar else "")
               + f", mínima {round(m['minimaKmh'])} {ap['pro']}. {_cap(ac['pro'])}, {sa['pro']}.")
    elif tipo == "pé embaixo":
        ini = [f"Curva {nome}, à {lado}.", f"Venha {chegada}.", "Ela é de pé embaixo: não freie nem alivie.",
               f"Passe a uns {_m5(_velocidade_no_apice(m))} por hora, {ap['longo']}, e {sa['longo']}" + (f"; {seguinte}." if seguinte else ".")]
        ama = f"{_cap(nome)}: pé embaixo, {ap['curto']}, {sa['curto']}."
        pro = f"{_cap(nome)}: pé embaixo, {ap['pro']}, {sa['pro']}."
    else:
        ini = [f"Curva {nome}, à {lado}.", f"Venha {chegada}.", "Só alivie o acelerador antes de virar, sem frear.",
               f"Deixe a velocidade cair até uns {v5} por hora, {ap['longo']}.",
               f"{_cap(ac['longo'])} e {sa['longo']}" + (f", porque {seguinte}." if seguinte else ".")]
        ama = f"{_cap(nome)}: só um alívio, mínima de {v5}, {ac['curto']} e {sa['curto']}."
        pro = f"{_cap(nome)}: alívio, mínima {round(m['minimaKmh'])} {ap['pro']}. {_cap(ac['pro'])}, {sa['pro']}."
    return {"iniciante": " ".join(ini), "amador": ama, "pro": pro}


def _velocidade_no_apice(m: Dict[str, Any]) -> float:
    return float(m.get("vApiceKmh") or m["minimaKmh"])


# ── a analise depois da curva (item 4) ────────────────────────────────────

def _tempo(grade: Dict[str, np.ndarray], track, a: float, b: float) -> Optional[float]:
    """O tempo de `a` a `b` numa passagem (a grade pode ter buracos fora dela)."""
    el = np.asarray(grade["elapsed"], float)
    s = np.asarray(track.s, float)
    L = float(track.length)

    def t(x):
        j = int(track.index_of(float(x) % L))
        return float(el[j]) if np.isfinite(el[j]) else None

    ta, tb = t(a), t(b)
    if ta is None or tb is None:
        return None
    dt = tb - ta
    return dt if dt >= 0 else None


def diferencas(ref: Dict[str, Any], pas: Dict[str, Any], g_ref: Dict[str, np.ndarray], g_pas: Dict[str, np.ndarray],
               track, trechos: Sequence[Any], k: int) -> List[Dict[str, Any]]:
    """As diferencas da passagem acima dos limites do item 4, na ordem do tempo que cada fase custou (a comparacao
    por fase do Modelo 2, ADR 0023): da busca da frenagem ao ponto de virar, do ponto de virar a minima e da minima a
    saida, todos pelos pontos da referencia."""
    L = float(track.length)
    busca = R.inicio_da_busca_da_freada(trechos, k)
    fases = {"entrada": (busca, ref["virar"]), "meio": (ref["virar"], ref["sMinima"]),
             "saida": (ref["sMinima"], float(trechos[k].saida_s))}
    custo = {}
    for nome, (a, b) in fases.items():
        tp, tr = _tempo(g_pas, track, a, b), _tempo(g_ref, track, a, b)
        custo[nome] = None if tp is None or tr is None else round(tp - tr, 3)
    out: List[Dict[str, Any]] = []
    if ref.get("freada") is not None and pas.get("freada") is not None:
        d = _d(pas["freada"], ref["freada"], L)
        if abs(d) >= DIF_FRENAGEM_M:
            out.append({"fase": "frenagem", "trechoDaFase": "entrada", "valor": round(d, 1)})
    d = _d(pas["virar"], ref["virar"], L)
    if abs(d) >= DIF_VIRAR_M:
        out.append({"fase": "virar", "trechoDaFase": "entrada", "valor": round(d, 1)})
    d = float(pas["minimaKmh"]) - float(ref["minimaKmh"])
    if abs(d) >= DIF_MINIMA_KMH:
        out.append({"fase": "minima", "trechoDaFase": "meio", "valor": round(d, 1), "suaKmh": pas["minimaKmh"],
                    "refKmh": ref["minimaKmh"]})
    d = float(pas["apiceDaBordaM"]) - float(ref["apiceDaBordaM"])
    if abs(d) >= DIF_APICE_M:
        out.append({"fase": "apice", "trechoDaFase": "meio", "valor": round(d, 2), "suaM": pas["apiceDaBordaM"],
                    "refM": ref["apiceDaBordaM"]})
    if ref.get("aceleradorCheio") is not None and pas.get("aceleradorCheio") is not None:
        d = _d(pas["aceleradorCheio"], ref["aceleradorCheio"], L)
        if abs(d) >= DIF_ACELERADOR_M:
            out.append({"fase": "acelerador", "trechoDaFase": "saida", "valor": round(d, 1)})
    d = float(pas["saidaDaBordaM"]) - float(ref["saidaDaBordaM"])
    if abs(d) >= DIF_SAIDA_M:
        out.append({"fase": "saida", "trechoDaFase": "saida", "valor": round(d, 2), "suaM": pas["saidaDaBordaM"],
                    "refM": ref["saidaDaBordaM"]})
    for x in out:
        x["custoS"] = custo.get(x["trechoDaFase"])
    out.sort(key=lambda x: -(x["custoS"] if x["custoS"] is not None else -1e9))
    return out


def _frase_da_diferenca(x: Dict[str, Any], nivel: str) -> str:
    f, v = x["fase"], x["valor"]
    m = _m5(abs(v)) or 5
    if nivel == "iniciante" and f == "minima":
        return f"fez a mínima de {round(x['suaKmh'])}, contra {round(x['refKmh'])} da referência"
    if nivel == "iniciante" and f == "apice" and float(x["suaM"]) >= 0 and v < 0:
        return "passou com o ápice por dentro demais"
    if nivel == "iniciante" and f == "saida":
        return "não usou a pista toda na saída" if v > 0 else "saiu mais aberto que a referência"
    if f == "frenagem":
        if nivel == "pro":
            return f"freio {'menos' if v < 0 else 'mais'} {round(abs(v))} metros"
        return f"freou {m} metros {'cedo' if v < 0 else 'tarde'}"
    if f == "virar":
        if nivel == "pro":
            return f"entrada {'menos' if v < 0 else 'mais'} {round(abs(v))} metros"
        return f"virou {m} metros {'cedo' if v < 0 else 'tarde'}"
    if f == "minima":
        if nivel == "pro":
            return f"mínima {'menos' if v < 0 else 'mais'} {round(abs(v))}"
        return f"mínima {round(x['suaKmh'])} contra {round(x['refKmh'])}"
    if f == "apice":
        if float(x["suaM"]) < 0:
            return "ápice na zebra" if nivel == "pro" else "subiu na zebra de dentro"
        if v < 0:
            return "ápice por dentro demais"
        return f"ápice {round(abs(v))} metros longe" if nivel == "pro" else "passou longe da borda de dentro"
    if f == "acelerador":
        if nivel == "pro":
            return f"gás {'menos' if v < 0 else 'mais'} {round(abs(v))} metros"
        return f"acelerou {m} metros {'cedo' if v < 0 else 'tarde'}"
    if v > 0:
        return f"saída {round(abs(v), 1)} metros por dentro".replace(".", ",") if nivel == "pro" else "não usou a pista toda na saída"
    return "saída mais aberta que a referência"


def _conselho(x: Dict[str, Any], textos_ref_curva: Dict[str, Any]) -> str:
    f, v = x["fase"], x["valor"]
    if f == "frenagem":
        return f"deixe para frear {textos_ref_curva['frear']}" if v < 0 else f"freie mais cedo, {textos_ref_curva['frear']}"
    if f == "virar":
        return f"vire {textos_ref_curva['virar']}"
    if f == "minima":
        return (f"leve mais velocidade para dentro: a mínima é uns {_m5(x['refKmh'])}" if x["valor"] < 0
                else f"tire um pouco mais de velocidade: a mínima é uns {_m5(x['refKmh'])}")
    if f == "apice":
        return f"passe {textos_ref_curva['apice']}"
    if f == "acelerador":
        return "acelere mais cedo" if v > 0 else "espere o carro apontar antes de acelerar"
    return "use a pista toda na saída"


def texto_da_analise(difs: Sequence[Dict[str, Any]], numero: Optional[int], trecho: str, nivel: str,
                     ref: Dict[str, Any], L: float, pontos: Sequence[Dict[str, Any]] = ()) -> Optional[str]:
    """A analise da passagem nos tres niveis. None: sem diferenca acima dos limites."""
    if not difs:
        return None
    nome = _nome(numero, trecho)
    if nivel in ("amador", "pro"):
        partes = [_frase_da_diferenca(x, nivel) for x in difs[:MAXIMO_DE_DIFERENCAS]]
        return f"{_cap(nome)}: {', '.join(partes)}."
    guia = {"frear": _onde_frear(ref, L, pontos)["longo"] if ref.get("freada") is not None else "antes de virar",
            "virar": _onde_virar(ref)["longo"], "apice": _apice(ref)["longo"]}
    partes = [_frase_da_diferenca(x, "iniciante") for x in difs]
    if len(partes) == 1:
        corpo = partes[0]
    else:
        corpo = ", ".join(partes[:-1]) + " e " + partes[-1]
    # o conselho vai para a maior diferenca que e um erro (sair mais aberto que a referencia nao e)
    erro = next((x for x in difs if not (x["fase"] == "saida" and x["valor"] < 0)), None)
    if erro is None:
        return f"Na {nome}, você {corpo}."
    return f"Na {nome}, você {corpo}. Na próxima, {_conselho(erro, guia)}."


# ── o treino (item 7) ────────────────────────────────────────────────────

def duracao_estimada(texto: str) -> float:
    return len(str(texto).split()) / PALAVRAS_POR_S


def relatorio_do_treino(analises: Dict[str, List[List[Dict[str, Any]]]], voltas: int) -> List[Dict[str, Any]]:
    """As curvas com diferenca em metade ou mais das voltas; cada fase com a mediana das voltas em que apareceu; na
    ordem do tempo perdido (a soma das medianas do custo)."""
    out = []
    for trecho, por_volta in analises.items():
        com = [d for d in por_volta if d]
        if not com or len(com) * 2 < max(voltas, 1):
            continue
        fases: Dict[str, List[Dict[str, Any]]] = {}
        for difs in com:
            for x in difs:
                fases.setdefault(x["fase"], []).append(x)
        medianas = []
        for fase, xs in fases.items():
            if len(xs) * 2 < len(com):
                continue
            base = dict(xs[0])
            for campo in ("valor", "custoS", "suaKmh", "refKmh", "suaM", "refM"):
                vals = [float(x[campo]) for x in xs if x.get(campo) is not None]
                if vals:
                    base[campo] = round(float(np.median(vals)), 2)
            base["voltas"] = len(xs)
            medianas.append(base)
        if not medianas:
            continue
        medianas.sort(key=lambda x: -(x.get("custoS") or 0.0))
        out.append({"trecho": trecho, "voltasComDiferenca": len(com), "diferencas": medianas,
                    "custoS": round(sum(max(x.get("custoS") or 0.0, 0.0) for x in medianas), 3)})
    out.sort(key=lambda c: -c["custoS"])
    return out


def orientacao(volume_s: float) -> Dict[str, Any]:
    """Item 7: ate 60 s, uma volta lenta; ate 180 s, N voltas lentas; mais, volta lenta e boxes."""
    if volume_s <= VOLTA_LENTA_S:
        return {"tipo": "uma volta lenta", "voltasLentas": 1, "texto": "Fim do treino. Dê uma volta lenta."}
    if volume_s <= VOLTAS_LENTAS_S:
        n = int(math.ceil(volume_s / VOLTA_LENTA_S))
        return {"tipo": "voltas lentas", "voltasLentas": n,
                "texto": f"Fim do treino. Dê {FEMININO.get(n, P.NUMEROS.get(n, str(n)))} voltas lentas."}
    return {"tipo": "volta lenta e boxes", "voltasLentas": 1, "texto": "Fim do treino. Dê uma volta lenta e entre nos boxes."}
