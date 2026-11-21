"""O plano das falas do engenheiro (pedido 52; ADR 0033, decisoes do Eduardo de 20/11): funcoes puras, sem
estado, testadas com dados sinteticos. Vale para qualquer pista e qualquer trecho.

* **o perfil:** a volta de onde vem o tempo e a acao do piloto (a ultima volta que conta da sessao; antes dela,
  a "Sua melhor volta"; sem ela, a volta de referencia), tratada como um laco (o fim emenda no comeco);
* **os pedacos livres:** acelerador em 0,90 ou mais e freio abaixo de 0,15, no perfil;
* **a acao do piloto** em cada trecho, desde a saida do trecho anterior;
* **os dois candidatos** de cada aviso: os pedacos livres que acabam mais perto antes do ponto (o mais cedo entre
  a acao do piloto e o ponto dito);
* **o plano:** cada aviso no primeiro candidato em que cabe sozinho com a folga de 3,0 s (senao, no segundo); os
  avisos do mesmo pedaco em pares (no maximo dois por fala); as falas o mais tarde possivel, de tras para a
  frente, sem encostar uma na outra; a fala que nao cabe manda os avisos para o segundo candidato;
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
INTERVALO_ENTRE_FALAS_S = 0.3       # item 7
ESTIMATIVA_DO_PAR_S = 0.8           # item 7: o par antes de a voz medir (a soma das falas sozinhas mais isto)
ESTIMATIVA_DA_FALA_S = 3.5          # uma fala sozinha antes de a voz medir
TEMPO_DE_REACAO_AO_BIPE_S = 0.0     # item 9: nao confirmado (o ADR cita as fontes); o bipe soa no ponto
DEPOIS_DA_ACAO_M = 20.0             # item 10: a janela tira o aviso 20 m depois da acao
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
    cond = (freio[idx] >= R.FREIO_DA_FREADA) | (acel[idx] < R.ACELERADOR_DA_RETOMADA)
    hits = np.flatnonzero(cond)
    if hits.size:
        i = idx[hits[0]]
        return float(track.s[i]), ("frenagem" if freio[i] >= R.FREIO_DA_FREADA else "alívio")
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


def fala_do_par(numeros: Sequence[Optional[int]], frases: Sequence[str]) -> str:
    """"Seis: vire na zebra. Sete: freie na zebra." (o numero da curva por extenso)."""
    partes = []
    for n, f in zip(numeros, frases):
        nome = NUMEROS.get(int(n), str(n)) if n is not None else ""
        partes.append(f"{nome.capitalize()}: {f}." if nome else fala_sozinha(f))
    return " ".join(partes)


# ── o plano ──────────────────────────────────────────────────────────────

@dataclass
class Aviso:
    trecho: str
    numero: Optional[int]
    frase: str                 # a frase falada no molde, sem o ponto final
    s_acao: float              # a acao do piloto (no perfil)
    s_dito: float
    ordem: int
    candidatos: List[Dict[str, Any]] = field(default_factory=list)
    escolha: int = 0           # 0: o pedaco mais perto; 1: o segundo
    motivo: Optional[str] = None


def planejar(avisos: List[Aviso], perfil: Perfil, pedacos: Sequence[Dict[str, float]],
             duracao: Callable[[str], Optional[float]], max_rodadas: int = 10) -> List[Dict[str, Any]]:
    """O plano das falas (item 7). `duracao(texto)`: a duracao medida pela voz, ou None (vale a estimativa).
    Devolve as falas: o pedaco, o `s_fala`, o texto, a duracao, os avisos e a folga planejada de cada um.
    Os avisos que ficam fora recebem `motivo`."""
    L = perfil.L
    for a in avisos:
        a.candidatos = candidatos(perfil, pedacos, ponto_limite(perfil, a.s_acao, a.s_dito))
        a.escolha, a.motivo = 0, None

    def dur(texto: str, partes: Sequence[Aviso]) -> float:
        d = duracao(texto)
        if d is not None:
            return float(d)
        if len(partes) == 1:
            return ESTIMATIVA_DA_FALA_S
        soma = 0.0
        for p in partes:
            x = duracao(fala_sozinha(p.frase))
            soma += float(x) if x is not None else ESTIMATIVA_DA_FALA_S
        return soma + ESTIMATIVA_DO_PAR_S

    falas: List[Dict[str, Any]] = []
    for _ in range(max_rodadas):
        # 1. cada aviso no primeiro candidato em que cabe sozinho
        por_pedaco: Dict[int, List[Aviso]] = {}
        for a in avisos:
            if a.motivo is not None and a.escolha >= len(a.candidatos):
                continue
            d1 = dur(fala_sozinha(a.frase), [a])
            while a.escolha < len(a.candidatos) and not cabe_sozinha(a.candidatos[a.escolha], d1):
                a.escolha += 1
            if a.escolha >= len(a.candidatos):
                a.motivo = a.motivo or "não cabe em nenhum dos dois pedaços livres antes da ação"
                continue
            por_pedaco.setdefault(a.candidatos[a.escolha]["i"], []).append(a)
        # 2. em cada pedaco, os pares na ordem da pista e as falas de tras para a frente
        falas, mudou = [], False
        for i, lista in por_pedaco.items():
            p = pedacos[i]
            x = lambda s: perfil.dt(p["sIni"], s)                     # noqa: E731 (o tempo desde o comeco do pedaco)
            lista.sort(key=lambda a: x(ponto_limite(perfil, a.s_acao, a.s_dito)))
            grupos = [lista[j:j + 2] for j in range(0, len(lista), 2)]
            limite = float("inf")
            agendadas = []
            for g in reversed(grupos):
                pontos = [ponto_limite(perfil, a.s_acao, a.s_dito) for a in g]
                fim_do_pedaco = min(x(a.candidatos[a.escolha]["sFimEfetivo"]) for a in g)
                fim = min(fim_do_pedaco, min(x(pt) for pt in pontos) - FOLGA_MINIMA_S, limite) \
                    if len(g) else 0.0
                texto = fala_sozinha(g[0].frase) if len(g) == 1 else fala_do_par([a.numero for a in g], [a.frase for a in g])
                d = dur(texto, g)
                # a fala acaba em `fim`: o disparo e `fim - d - latencia`
                inicio = fim - d - LATENCIA_NO_JOGO_S
                if inicio < -1e-9:
                    for a in g:
                        a.escolha += 1
                        if a.escolha >= len(a.candidatos):
                            a.motivo = "não coube com as outras falas do pedaço livre"
                    mudou = True
                    continue
                limite = inicio - INTERVALO_ENTRE_FALAS_S
                s_fala = perfil.s_em(perfil.t(p["sIni"]) + inicio)
                agendadas.append({
                    "pedaco": [round(p["sIni"], 1), round(p["sFim"], 1)], "candidato": g[0].escolha + 1,
                    "sFala": round(s_fala, 1), "texto": texto, "duracaoS": round(d, 2),
                    "duracaoMedida": duracao(texto) is not None,
                    "trechos": [a.trecho for a in g],
                    "folgaS": {a.trecho: round(x(pt) - (inicio + LATENCIA_NO_JOGO_S + d), 2) for a, pt in zip(g, pontos)},
                })
            falas.extend(reversed(agendadas))
        if not mudou:
            break
    falas.sort(key=lambda f: f["sFala"])
    return falas


def s_da_janela(perfil: Perfil, pedacos: Sequence[Dict[str, float]], s_acao: float) -> float:
    """ADR 0033, emenda de 20/11, item 10: o aviso aparece desde o fim da acao anterior (o comeco do pedaco livre
    logo antes da acao do piloto); sem pedaco livre, 150 m antes da acao."""
    c = candidatos(perfil, pedacos, s_acao, quantos=1)
    if not c:
        return (float(s_acao) - 150.0) % perfil.L
    return float(c[0]["sIni"])
