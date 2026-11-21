"""O plano das falas do engenheiro (pedido 52; ADR 0033, decisoes do Eduardo de 20/11 e de 21/11): funcoes puras,
sem estado, testadas com dados sinteticos. Vale para qualquer pista e qualquer trecho.

* **o perfil:** a volta de onde vem o tempo e a acao do piloto (a ultima volta que conta da sessao; antes dela,
  a "Sua melhor volta"; sem ela, a volta de referencia), tratada como um laco (o fim emenda no comeco);
* **os pedacos livres:** acelerador em 0,90 ou mais e freio abaixo de 0,15, no perfil;
* **a acao do piloto** em cada trecho, desde a saida do trecho anterior;
* **a ficha** da curva de foco (21/11, item 9): no pedaco livre que contem o fim da reta longa antes dela, 3,0 s
  antes do fim do pedaco e do ponto da curva, o mais tarde possivel;
* **o lembrete** (21/11, item 11): no pedaco livre logo antes da curva de foco, com a folga de 3,0 s;
* **a contagem de bipes** (21/11, item 12): tres pontos, o ultimo no ponto de frenagem, a 0,5 s um do outro;
* **o molde** da fala: (a), (b) ou (c).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import regras as R

# ADR 0033, emenda de 20/11
LATENCIA_NO_JOGO_S = 0.1            # item 2: uma estimativa, a ser medida no teste
FOLGA_MINIMA_S = 3.0                # item 6
ESTIMATIVA_DA_FALA_S = 3.5          # o lembrete antes de a voz medir
ESTIMATIVA_DA_FICHA_S = 8.0         # a ficha antes de a voz medir (as fichas de Interlagos: 5,4 a 11 s)
# ADR 0033, emenda de 21/11, item 12: a contagem de tres bipes; o intervalo nao confirmado (o ADR diz por que)
INTERVALO_DA_CONTAGEM_S = 0.5
BIPES_DA_CONTAGEM = 3
MOLDES = ("a", "b", "c")
MOLDE_PADRAO = "b"             # ADR 0033, a decisao de 20/11 sobre o molde: o Eduardo escolheu o (b) ouvindo

NUMEROS = {1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco", 6: "seis", 7: "sete", 8: "oito", 9: "nove",
           10: "dez", 11: "onze", 12: "doze", 13: "treze", 14: "catorze", 15: "quinze", 16: "dezesseis",
           17: "dezessete", 18: "dezoito", 19: "dezenove", 20: "vinte"}


# ── o perfil ─────────────────────────────────────────────────────────────

class Perfil:
    """O tempo de uma volta em cada `s`, como um laco."""

    def __init__(self, grade: Dict[str, np.ndarray], total: float, track, origem: str):
        self.grade, self.total, self.track, self.origem = grade, float(total), track, origem
        self.L = float(track.length)
        self.el = np.asarray(grade["elapsed"], float)

    def t(self, s: float) -> float:
        return R.tempo_em(self.el, self.total, self.track, float(s) % self.L)

    def dt(self, s1: float, s2: float) -> float:
        """O tempo andando para a frente de `s1` a `s2` (0 a uma volta)."""
        return (self.t(s2) - self.t(s1)) % self.total

    def s_em(self, t: float) -> float:
        return R.s_no_tempo(self.el, self.total, self.track, float(t) % self.total)


def pedacos_livres(grade: Dict[str, np.ndarray], track) -> List[Dict[str, float]]:
    """Os pedacos livres do perfil (acelerador em 0,90 ou mais e freio abaixo de 0,15), como um laco: o que
    acaba na linha emenda no que comeca nela."""
    s = np.asarray(track.s, float)
    livre = ((np.nan_to_num(np.asarray(grade["acelerador"], float)) >= R.ACELERADOR_DA_RETOMADA)
             & (np.nan_to_num(np.asarray(grade["freio"], float)) < R.FREIO_DA_FREADA))
    if livre.all():
        return [{"sIni": 0.0, "sFim": float(track.length) - 1e-6}]
    corridas = []
    i = 0
    n = len(livre)
    while i < n:
        if livre[i]:
            j = i
            while j + 1 < n and livre[j + 1]:
                j += 1
            corridas.append([i, j])
            i = j + 1
        else:
            i += 1
    if len(corridas) > 1 and corridas[0][0] == 0 and corridas[-1][1] == n - 1:
        primeiro = corridas.pop(0)
        corridas[-1] = [corridas[-1][0], primeiro[1] + n]
    return [{"sIni": float(s[a % n]), "sFim": float(s[b % n])} for a, b in corridas]


# ── a acao do piloto ─────────────────────────────────────────────────────

def acao_do_piloto(grade: Dict[str, np.ndarray], track, trechos: Sequence[Any], k: int, acao: str
                   ) -> Optional[Tuple[float, str]]:
    """ADR 0033, emenda de 20/11, item 5: o `s` da acao do piloto no trecho e o tipo, buscada desde a saida do
    trecho anterior ate o apice. None: "acelere" sem a volta ao acelerador."""
    from core.radio.analise import freada_desde
    from ml.comparison.lap_vs_reference import _window

    t = trechos[k]
    L = float(track.length)
    if not t.tem_curva:
        return None
    if acao == R.SEM_TIRAR_O_PE:
        return float(t.entrada_s), "entrada"
    acel = np.nan_to_num(np.asarray(grade["acelerador"], float))
    freio = np.nan_to_num(np.asarray(grade["freio"], float))
    if acao == "acelere":
        r = R.retomada(acel, track, t)
        if r is not None:
            return float(r), "retomada"
        idx = _window(track, float(t.apice_s), float(t.fim_s) % L)
        cheio = np.flatnonzero(acel[idx] >= R.ACELERADOR_DA_RETOMADA)
        return (float(track.s[idx[cheio[0]]]), "acelerador") if cheio.size else None
    de = R.inicio_da_busca_da_freada(trechos, k) % L
    if acao == "freie":
        f = freada_desde(freio, track, de, float(t.apice_s))
        if f is not None:
            return float(f), "frenagem"
    idx = _window(track, de, float(t.apice_s))
    # a primeira frenagem, ou o comeco do primeiro alivio de 10 m ou mais (emenda de 21/11, item 8)
    passo = L / float(len(track.s))
    minimo = max(1, int(round(R.ALIVIO_MINIMO_M / passo)))
    abaixo = acel[idx] < R.ACELERADOR_DA_RETOMADA
    for j in range(len(idx)):
        if freio[idx[j]] >= R.FREIO_DA_FREADA:
            return float(track.s[idx[j]]), "frenagem"
        if abaixo[j] and (j == 0 or not abaixo[j - 1]) and bool(np.all(abaixo[j:j + minimo])) and j + minimo <= len(idx):
            return float(track.s[idx[j]]), "alívio"
    return float(t.entrada_s), "entrada"


def ponto_limite(perfil: Perfil, s_acao: float, s_dito: float) -> float:
    """O mais cedo, no tempo do perfil, entre a acao do piloto e o ponto dito (item 6)."""
    return float(s_acao) if perfil.dt(s_acao, s_dito) <= perfil.dt(s_dito, s_acao) else float(s_dito)


def candidatos(perfil: Perfil, pedacos: Sequence[Dict[str, float]], s_ponto: float, quantos: int = 2
               ) -> List[Dict[str, Any]]:
    """Os pedacos livres que acabam mais perto antes de `s_ponto`, do mais perto para tras. Os tempos sao
    relativos ao ponto (negativos: antes dele). Um pedaco que contem o ponto acaba nele."""
    L = perfil.L
    out = []
    for i, p in enumerate(pedacos):
        comp = (p["sFim"] - p["sIni"]) % L
        contem = (s_ponto - p["sIni"]) % L <= comp
        fim_ef = float(s_ponto) if contem else p["sFim"]
        rel_fim = 0.0 if contem else -perfil.dt(p["sFim"], s_ponto)
        rel_ini = rel_fim - perfil.dt(p["sIni"], fim_ef)
        out.append({"i": i, "sIni": p["sIni"], "sFim": p["sFim"], "sFimEfetivo": fim_ef, "relIni": rel_ini,
                    "relFim": rel_fim})
    out.sort(key=lambda c: -c["relFim"])
    return out[:quantos]


def cabe_sozinha(c: Dict[str, Any], duracao: float) -> bool:
    fim = min(c["relFim"], -FOLGA_MINIMA_S)
    return fim - duracao - LATENCIA_NO_JOGO_S >= c["relIni"] - 1e-9


# ── o molde da fala ──────────────────────────────────────────────────────

def frase_falada(acao: str, marco: Optional[Dict[str, Any]], d: Optional[float], molde: str, frase_a: str) -> str:
    """A frase no molde (ADR 0033, emenda de 20/11, item 8), sem o ponto final e em minusculas.
    (a) "freie 10 metros depois da placa de 100"; (b) "freie 10 depois do 100"; (c) "freie no 100, mais 10".
    So as placas perdem "placa de"; os outros marcos guardam o nome e o lado."""
    if molde == "a" or acao == R.SEM_TIRAR_O_PE or not marco:
        return frase_a
    nome = marco["nome"]
    placa = marco.get("tipo") == "placa" and marco.get("valor") is not None
    if placa:
        nome, no, do = str(marco["valor"]), "no", "do"
    else:
        no, do = R._artigo(nome)
    if d is None or abs(float(d)) < R.NO_MARCO_M:
        return f"{acao} {no} {nome}"
    m = R.arredondar_5(float(d))
    if molde == "b":
        return f"{acao} {m} {'depois' if d > 0 else 'antes'} {do} {nome}"
    return f"{acao} {no} {nome}, {'mais' if d > 0 else 'menos'} {m}"


def fala_sozinha(frase: str) -> str:
    return f"{frase[0].upper()}{frase[1:]}."


# ── a ficha, o lembrete e a contagem (ADR 0033, emenda de 21/11) ─────────

def candidato(perfil: Perfil, pedacos: Sequence[Dict[str, float]], s_ponto: float, i: int) -> Optional[Dict[str, Any]]:
    """O pedaco livre `i` visto do ponto (os tempos relativos ao ponto, negativos antes dele)."""
    return next((c for c in candidatos(perfil, pedacos, s_ponto, quantos=len(pedacos)) if c["i"] == i), None)


def pedaco_com(perfil: Perfil, pedacos: Sequence[Dict[str, float]], s: float) -> Optional[int]:
    """O pedaco livre que contem `s` (ou, sem nenhum, o que acaba mais perto antes dele)."""
    c = candidatos(perfil, pedacos, s, quantos=1)
    return c[0]["i"] if c else None


def reta_longa_antes(retas_longas: Sequence[Dict[str, Any]], s_ponto: float, L: float) -> Optional[Dict[str, Any]]:
    """Item 9: a reta longa (um bloco de 8,8 s ou mais na volta do modelo) que vem primeiro antes do ponto: a de
    fim mais perto para tras."""
    if not retas_longas:
        return None
    return min(retas_longas, key=lambda b: (float(s_ponto) - float(b["fim"])) % L)


def planejar_a_ficha(perfil: Perfil, pedacos: Sequence[Dict[str, float]], reta: Optional[Dict[str, Any]],
                     s_ponto: float, duracao: float) -> Dict[str, Any]:
    """Item 9: a ficha no pedaco livre do perfil que contem o fim da reta longa; ela acaba 3,0 s antes do fim do
    pedaco (a acao seguinte) e do ponto da curva de foco, e comeca o mais tarde possivel. Devolve {sFala,
    duracaoS, folgaS, folgaAoFimDoPedacoS, pedaco} ou {motivo}."""
    if reta is None:
        return {"motivo": "sem reta longa na pista"}
    i = pedaco_com(perfil, pedacos, float(reta["fim"]))
    c = candidato(perfil, pedacos, s_ponto, i) if i is not None else None
    if c is None:
        return {"motivo": "sem pedaço livre na reta longa"}
    fim = float(c["relFim"]) - FOLGA_MINIMA_S
    inicio = fim - float(duracao) - LATENCIA_NO_JOGO_S
    if inicio < float(c["relIni"]) - 1e-9:
        return {"motivo": "a ficha não cabe na reta longa", "pedaco": i}
    return {"sFala": round(perfil.s_em(perfil.t(s_ponto) + inicio), 1), "duracaoS": round(float(duracao), 2),
            "folgaS": round(-fim, 2), "folgaAoFimDoPedacoS": round(float(c["relFim"]) - fim, 2), "pedaco": i,
            "relInicioS": round(inicio, 2)}


def planejar_o_lembrete(perfil: Perfil, pedacos: Sequence[Dict[str, float]], s_ponto: float, duracao: float,
                        pedaco_da_ficha: Optional[int]) -> Dict[str, Any]:
    """Item 11: o lembrete no pedaco livre logo antes do ponto, o mais tarde possivel, com a folga de 3,0 s. No
    mesmo pedaco da ficha, fica so a ficha. Devolve {sFala, duracaoS, folgaS, pedaco} ou {motivo}."""
    c = candidatos(perfil, pedacos, s_ponto, quantos=1)
    if not c:
        return {"motivo": "sem pedaço livre antes da curva"}
    c = c[0]
    if pedaco_da_ficha is not None and c["i"] == pedaco_da_ficha:
        return {"motivo": "a ficha já é dita neste pedaço livre", "pedaco": c["i"]}
    if not cabe_sozinha(c, duracao):
        return {"motivo": "o lembrete não cabe no pedaço livre antes da curva", "pedaco": c["i"]}
    fim = min(float(c["relFim"]), -FOLGA_MINIMA_S)
    inicio = fim - float(duracao) - LATENCIA_NO_JOGO_S
    return {"sFala": round(perfil.s_em(perfil.t(s_ponto) + inicio), 1), "duracaoS": round(float(duracao), 2),
            "folgaS": round(-fim, 2), "pedaco": c["i"], "relInicioS": round(inicio, 2)}


def pontos_da_contagem(perfil: Perfil, s_freada: float, intervalo: float = INTERVALO_DA_CONTAGEM_S,
                       n: int = BIPES_DA_CONTAGEM) -> List[float]:
    """Item 12: os `s` dos bipes, pelo tempo do perfil: o ultimo no ponto de frenagem; os outros `intervalo` e
    2 x `intervalo` antes dele."""
    t = perfil.t(s_freada)
    return [round(perfil.s_em(t - (n - 1 - j) * float(intervalo)), 1) for j in range(n - 1)] + [round(float(s_freada) % perfil.L, 1)]
