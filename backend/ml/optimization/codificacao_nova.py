"""A codificacao nova da linha (pedido 50; ADR 0031, item 4).

A codificacao do pedido 46 (`representation.py`) e uma spline na **lateral**.
Somada a uma linha central que ondula, ela da uma linha que ondula no mundo; e o
escritor do pedido 47 interpolava a grade de 2 m em linha reta, com uma quina a
cada ponto. O raio do `fast_lane.ai` (o circulo por tres pontos vizinhos, a
1,57 m) pega essas quinas, e a IA freia nelas.

Aqui a linha e uma **spline cubica periodica no proprio plano X/Z**:

* cada gene e a lateral num ponto de controle; o ponto de controle no mundo e
  `P_j = c(s_j) + n(s_j) * g_j`;
* a curva e a spline periodica por esses pontos, com o parametro `u = s` (a
  distancia na linha central) e os nos nos pontos de controle. Ela tem a
  segunda derivada continua, entao a curvatura e continua;
* os pontos de controle sao mais densos nas curvas (item 4.1);
* a lateral na grade (o formato do projeto) e a projecao da curva na normal de
  cada ponto: `L_i = (Q(s_i) - c(s_i)) . n(s_i)`;
* o arquivo do jogo e a curva avaliada direto nas estacoes do arquivo original,
  sem passar pela grade (`ml.pista_teste.linha_do_projeto`).

A curva e linear nos genes, entao decodificar uma populacao e um produto de
matrizes e codificar (ajustar) e um `lstsq`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.interpolate import CubicSpline

from .. import config
from ..track.geometry import TrackGeometry, _closed_derivative, _smoothing_window
from ..track.trajectory import curvature as curvatura_do_projeto
from ..track.trajectory import world_path

# ADR 0031, itens 4.1, 4.4, 4.5 e 4.6.
MARGEM_DA_JANELA_M = 40.0
ESCADA = ((10.0, 25.0), (8.0, 20.0), (6.0, 15.0), (5.0, 12.5))
EMENDA_DA_VOLTA_M = 30.0
FRACAO_DO_RAIO = 0.90
FRACAO_DA_TAXA = 1.10
CONFERENCIA_DISTANCIA_M = 0.10
CONFERENCIA_PERCENTIL = 95.0
# Emenda do ADR 0031 (item 13, decisao do Eduardo de 12/11): 10%, e o C0 medido pela curvatura de 12 m.
CONFERENCIA_RAIO_RELATIVO = 0.10
JANELA_DA_CURVATURA_M = config.CURVATURE_SMOOTHING_M   # 12 m


# ---------------------------------------------------------- os pontos ---

def janelas_das_curvas(comprimento: float, curvas: Sequence[Tuple[float, float]],
                       margem_m: float = MARGEM_DA_JANELA_M) -> List[Tuple[float, float]]:
    """As janelas [inicio - margem, fim + margem] de cada curva, juntadas quando se tocam.

    `curvas`: (inicio_s, fim_s) de cada curva. Uma janela pode passar da linha de chegada;
    ela volta como (a, b) com `a` em [0, comprimento) e `b > a` (ate `a + comprimento`).
    """
    L = float(comprimento)
    brutas = []
    for ini, fim in curvas:
        extensao = np.mod(float(fim) - float(ini), L)
        a = np.mod(float(ini) - margem_m, L)
        brutas.append((a, a + extensao + 2.0 * margem_m))
    brutas.sort()
    juntas: List[List[float]] = []
    for a, b in brutas:
        if juntas and a <= juntas[-1][1]:
            juntas[-1][1] = max(juntas[-1][1], b)
        else:
            juntas.append([a, b])
    # A ultima pode alcancar a primeira dando a volta.
    if len(juntas) > 1 and juntas[-1][1] >= juntas[0][0] + L:
        juntas[0] = [juntas[-1][0], max(juntas[-1][1], juntas[0][1] + L)]
        juntas.pop()
    for j in juntas:
        if j[1] - j[0] >= L:
            raise ValueError("as janelas cobrem a volta inteira")
    return [(float(a), float(b)) for a, b in juntas]


def _dividir(a: float, b: float, passo: float) -> np.ndarray:
    """Os pontos de [a, b) em partes iguais, com o numero de partes arredondado para cima."""
    partes = max(int(np.ceil((b - a) / float(passo) - 1e-9)), 1)
    return a + (b - a) * np.arange(partes) / partes


def pontos_de_controle(comprimento: float, janelas: Sequence[Tuple[float, float]],
                       dentro_m: float, fora_m: float) -> np.ndarray:
    """O `s` de cada ponto de controle, em ordem, em [0, comprimento)."""
    L = float(comprimento)
    if not janelas:
        return _dividir(0.0, L, fora_m)
    pontos = []
    for i, (a, b) in enumerate(janelas):
        pontos.append(_dividir(a, b, dentro_m))
        proxima = janelas[(i + 1) % len(janelas)][0] + (L if i + 1 == len(janelas) else 0.0)
        if proxima > b + 1e-9:
            pontos.append(_dividir(b, proxima, fora_m))
    s = np.mod(np.concatenate(pontos), L)
    s = np.unique(np.round(s, 9))
    return s


def _base(control_s: np.ndarray, comprimento: float, u: np.ndarray) -> np.ndarray:
    """(len(u), genes): a spline periodica de cada ponto de controle sozinho, avaliada em `u`."""
    G = control_s.size
    estendido = np.concatenate([control_s, [control_s[0] + comprimento]])
    identidade = np.vstack([np.eye(G), np.eye(G)[:1]])
    spline = CubicSpline(estendido, identidade, bc_type="periodic", axis=0)
    inicio = float(control_s[0])
    return spline(inicio + np.mod(np.asarray(u, float) - inicio, comprimento))


# ------------------------------------------------------- a codificacao ---

@dataclass(frozen=True)
class CodificacaoNova:
    """A ponte entre os genes e a linha. Compativel com a busca (`evolve`, `build_population`, `mutate`)."""

    track: TrackGeometry
    control_s: np.ndarray       # (genes,)
    lower: np.ndarray           # (genes,) limite direito (negativo)
    upper: np.ndarray           # (genes,) limite esquerdo (positivo)
    base_grade: np.ndarray      # (grade, genes)
    c_ctrl: np.ndarray          # (genes, 2) a linha central nos pontos de controle
    n_ctrl: np.ndarray          # (genes, 2) a normal nos pontos de controle
    dentro_m: float = 10.0
    fora_m: float = 25.0

    @property
    def genes(self) -> int:
        return int(self.control_s.size)

    def base_em(self, u: np.ndarray) -> np.ndarray:
        return _base(self.control_s, self.track.length, u)

    def pontos(self, genes: np.ndarray) -> np.ndarray:
        """(genes, 2): os pontos de controle no mundo."""
        g = np.asarray(genes, float)
        return self.c_ctrl + self.n_ctrl * g[:, None]

    def curva(self, genes: np.ndarray, u: np.ndarray) -> np.ndarray:
        """(len(u), 2): a curva no plano X/Z, avaliada em `u` (o `s` da linha central)."""
        return self.base_em(u) @ self.pontos(genes)

    def _lateral_de(self, Q: np.ndarray) -> np.ndarray:
        t = self.track
        return np.sum((Q - t.points[None, :, :]) * t.normal[None, :, :], axis=-1)

    def decode(self, genome: np.ndarray) -> np.ndarray:
        """Genes -> a lateral na grade (a projecao da curva na normal de cada ponto). Sem clipar a lateral."""
        g = np.clip(np.asarray(genome, float), self.lower, self.upper)
        Q = self.base_grade @ self.pontos(g)
        return self._lateral_de(Q[None])[0]

    def decode_many(self, population: np.ndarray) -> np.ndarray:
        G = self.clip(np.atleast_2d(np.asarray(population, float)))
        Px = self.c_ctrl[None, :, 0] + self.n_ctrl[None, :, 0] * G
        Pz = self.c_ctrl[None, :, 1] + self.n_ctrl[None, :, 1] * G
        Q = np.stack([Px @ self.base_grade.T, Pz @ self.base_grade.T], axis=-1)
        return self._lateral_de(Q)

    def encode_pontos(self, xz: np.ndarray, u: np.ndarray, pesos: Optional[np.ndarray] = None) -> np.ndarray:
        """Os genes que melhor reproduzem os pontos `xz` (em `u`), por minimos quadrados no plano X/Z."""
        xz = np.asarray(xz, float)
        B = self.base_em(u)
        w = np.ones(len(xz)) if pesos is None else np.asarray(pesos, float)
        A = np.vstack([B * self.n_ctrl[None, :, 0], B * self.n_ctrl[None, :, 1]]) * np.r_[w, w][:, None]
        alvo = np.r_[xz[:, 0] - B @ self.c_ctrl[:, 0], xz[:, 1] - B @ self.c_ctrl[:, 1]] * np.r_[w, w]
        g, *_ = np.linalg.lstsq(A, alvo, rcond=None)
        return np.clip(g, self.lower, self.upper)

    def encode(self, lateral: np.ndarray, smoothness=None) -> np.ndarray:
        """Uma lateral na grade -> os genes (os alvos sao os pontos da grade no mundo)."""
        return self.encode_pontos(world_path(self.track, np.asarray(lateral, float)), self.track.s)

    def random(self, generator: np.random.Generator, count: int = 1) -> np.ndarray:
        return self.lower + generator.random((count, self.genes)) * (self.upper - self.lower)

    def clip(self, population: np.ndarray) -> np.ndarray:
        return np.clip(np.asarray(population, float), self.lower, self.upper)

    def com_limites(self, lower: np.ndarray, upper: np.ndarray) -> "CodificacaoNova":
        """A mesma codificacao com outros limites por gene (a regiao de confianca, item 6)."""
        lo = np.maximum(np.asarray(lower, float), self.lower)
        hi = np.minimum(np.asarray(upper, float), self.upper)
        if (lo > hi + 1e-12).any():
            raise ValueError("limites vazios em algum gene")
        return replace(self, lower=lo, upper=np.maximum(hi, lo))

    def vizinhanca(self, indice_da_grade: np.ndarray) -> np.ndarray:
        """Os genes cuja base pesa mais de 5% nos pontos da grade dados (para o reparo do corredor)."""
        pesos = np.abs(self.base_grade[np.asarray(indice_da_grade, int)])
        return np.unique(np.nonzero(pesos > 0.05)[1])

    def descricao(self) -> Dict[str, object]:
        esp = np.diff(np.r_[self.control_s, self.control_s[0] + self.track.length])
        return {"genes": self.genes, "dentro_m": self.dentro_m, "fora_m": self.fora_m,
                "espacamento_m": {"min": float(esp.min()), "p50": float(np.median(esp)), "max": float(esp.max())}}


def construir(track: TrackGeometry, curvas: Sequence[Tuple[float, float]], dentro_m: float, fora_m: float,
              car_half_width: float = config.CAR_HALF_WIDTH_M,
              kerb_allowance: float = config.KERB_ALLOWANCE_M) -> CodificacaoNova:
    """A codificacao para a pista, com as janelas das curvas e o par de espacamentos."""
    janelas = janelas_das_curvas(track.length, curvas)
    control_s = pontos_de_controle(track.length, janelas, dentro_m, fora_m)
    base_grade = _base(control_s, track.length, track.s)
    c_ctrl = track.to_world(control_s, np.zeros(control_s.size))
    n_ctrl = track.to_world(control_s, np.ones(control_s.size)) - c_ctrl
    n_ctrl = n_ctrl / np.linalg.norm(n_ctrl, axis=1, keepdims=True)
    low, high = track.corridor(car_half_width, kerb_allowance)
    # O limite de cada gene e o mais apertado da vizinhanca que ele governa (como no pedido 46): metade
    # do intervalo ate cada vizinho.
    G = control_s.size
    L = track.length
    ant = np.mod(control_s - np.roll(control_s, 1), L)
    pos = np.mod(np.roll(control_s, -1) - control_s, L)
    lower, upper = np.empty(G), np.empty(G)
    for j in range(G):
        meia_a = max(int(round(0.5 * ant[j] / track.step)), 0)
        meia_p = max(int(round(0.5 * pos[j] / track.step)), 0)
        i0 = int(track.index_of(control_s[j]))
        idx = np.mod(np.arange(i0 - meia_a, i0 + meia_p + 1), track.size)
        lower[j] = low[idx].max()
        upper[j] = high[idx].min()
    upper = np.maximum(upper, lower)
    return CodificacaoNova(track, control_s, lower, upper, base_grade, c_ctrl, n_ctrl, float(dentro_m), float(fora_m))


# ----------------------------------------------- curvatura e restricoes ---

def fora_da_emenda(track: TrackGeometry, margem_m: float = EMENDA_DA_VOLTA_M) -> np.ndarray:
    """Os pontos da grade a mais de `margem_m` da linha de chegada (item 4.4)."""
    return (track.s >= margem_m) & (track.s <= track.length - margem_m)


def curvatura_e_taxa(track: TrackGeometry, lateral: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(kappa, |dkappa/ds|) na grade, com a janela de 12 m do projeto (item 4.4)."""
    kappa = curvatura_do_projeto(track, np.asarray(lateral, float), smoothing_m=JANELA_DA_CURVATURA_M)
    janela = _smoothing_window(JANELA_DA_CURVATURA_M, track.step)
    taxa = np.abs(_closed_derivative(kappa, track.step, janela, order=3))
    return kappa, taxa


def mascaras_dos_trechos(track: TrackGeometry, trechos) -> List[np.ndarray]:
    """Os pontos da grade de cada trecho do ADR 0030 (`trechos`: objetos com `inicio_s` e `fim_s`)."""
    out = []
    for t in trechos:
        out.append((track.s >= t.inicio_s - 1e-9) & (track.s < t.fim_s - 1e-9))
    return out


def medidas_por_trecho(track: TrackGeometry, lateral: np.ndarray, trechos, sem_emenda: bool = True) -> Dict[str, np.ndarray]:
    """O menor raio (m) e a maior taxa (1/m^2) de cada trecho, pela curvatura de 12 m."""
    kappa, taxa = curvatura_e_taxa(track, lateral)
    ok = fora_da_emenda(track) if sem_emenda else np.ones(track.size, bool)
    raio, tx, onde = [], [], []
    for m in mascaras_dos_trechos(track, trechos):
        sel = m & ok
        k = np.abs(kappa[sel])
        i = int(np.argmax(k))
        raio.append(1.0 / max(float(k[i]), 1e-12))
        onde.append(float(track.s[sel][i]))
        tx.append(float(taxa[sel].max()))
    return {"raio_min_m": np.array(raio), "raio_min_em_s": np.array(onde), "taxa_max": np.array(tx)}


def limites_por_trecho(track: TrackGeometry, laterais: Sequence[np.ndarray], trechos) -> Dict[str, np.ndarray]:
    """Item 4.4: 90% do menor raio e 110% da maior taxa que as voltas usam em cada trecho."""
    raios, taxas = [], []
    for lat in laterais:
        m = medidas_por_trecho(track, lat, trechos)
        raios.append(m["raio_min_m"])
        taxas.append(m["taxa_max"])
    raios, taxas = np.array(raios), np.array(taxas)
    return {"raio_min_m": FRACAO_DO_RAIO * raios.min(axis=0), "taxa_max": FRACAO_DA_TAXA * taxas.max(axis=0),
            "menor_raio_das_voltas_m": raios.min(axis=0), "maior_taxa_das_voltas": taxas.max(axis=0),
            "voltas": int(len(laterais))}


def excesso_das_restricoes(medidas: Dict[str, np.ndarray], limites: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Por trecho, o excesso relativo (0 quando dentro): `kappa/kappa_lim - 1` e `taxa/taxa_lim - 1`."""
    k = 1.0 / medidas["raio_min_m"]
    k_lim = 1.0 / limites["raio_min_m"]
    return {"raio": np.maximum(k / k_lim - 1.0, 0.0),
            "taxa": np.maximum(medidas["taxa_max"] / limites["taxa_max"] - 1.0, 0.0)}


# ---------------------------------------------------------- conferencia ---

def raio_de_tres_pontos(xz: np.ndarray) -> np.ndarray:
    """O raio do arquivo do jogo (o circulo pelos pontos i-1, i e i+1, linha fechada)."""
    from ..pista_teste.linha_nova import geometria

    p = np.column_stack([xz[:, 0], np.zeros(len(xz)), xz[:, 1]])
    return geometria(p)["raio"]


def conferir_c0(cod: CodificacaoNova, xz_arquivo: np.ndarray, estacao_s: np.ndarray, raio_arquivo: np.ndarray,
                trechos, lateral_do_arquivo: np.ndarray = None) -> Dict[str, object]:
    """Item 4.5 com a emenda do item 13: a linha da IA codificada pelos pontos do arquivo, contra o proprio arquivo.

    A distancia e a do ponto codificado ate a polilinha do arquivo. O raio da conferencia e o da curvatura de
    12 m na grade (o C0 codificado e decodificado contra `lateral_do_arquivo`, a lateral do arquivo na grade).
    O raio de tres pontos do arquivo (o campo `raio`) contra o da curva nas mesmas estacoes so e relatado.
    """
    from ..pista_teste.linha_nova import _projetar_na_polilinha

    s = np.mod(np.asarray(estacao_s, float), cod.track.length)
    g = cod.encode_pontos(xz_arquivo, s)
    novo = cod.curva(g, s)
    _, _, d = _projetar_na_polilinha(novo, np.asarray(xz_arquivo, float))
    r_novo = raio_de_tres_pontos(novo)
    tres_pontos = []
    for t in trechos:
        m = (s >= t.inicio_s - 1e-9) & (s < t.fim_s - 1e-9)
        a, b = float(raio_arquivo[m].min()), float(r_novo[m].min())
        tres_pontos.append({"trecho": t.nome, "raio_original_m": a, "raio_codificado_m": b, "relativo": (b - a) / a})
    if lateral_do_arquivo is None:
        por_trecho = tres_pontos
    else:
        m0 = medidas_por_trecho(cod.track, lateral_do_arquivo, trechos)
        m1 = medidas_por_trecho(cod.track, cod.decode(g), trechos)
        por_trecho = [{"trecho": t.nome, "raio_original_m": float(a), "raio_codificado_m": float(b), "relativo": float((b - a) / a)}
                      for t, a, b in zip(trechos, m0["raio_min_m"], m1["raio_min_m"])]
    p = float(np.percentile(d, CONFERENCIA_PERCENTIL))
    rel = max(abs(x["relativo"]) for x in por_trecho)
    return {"linha": "C0 (o arquivo da IA)", "pontos": int(len(d)), "distancia_p50_m": float(np.median(d)),
            "distancia_p95_m": p, "distancia_max_m": float(d.max()),
            "fracao_ate_0_10_m": float(np.mean(d <= CONFERENCIA_DISTANCIA_M)),
            "raio_por_trecho": por_trecho, "maior_diferenca_relativa_do_raio": rel,
            "raio_de_tres_pontos_so_relatado": tres_pontos,
            "passa": bool(p <= CONFERENCIA_DISTANCIA_M and rel <= CONFERENCIA_RAIO_RELATIVO), "genes": g}


def conferir_volta(cod: CodificacaoNova, lateral: np.ndarray, trechos, nome: str) -> Dict[str, object]:
    """Item 4.5: uma volta gravada codificada pela lateral na grade, fora da emenda."""
    track = cod.track
    g = cod.encode(lateral)
    nova = cod.decode(g)
    ok = fora_da_emenda(track)
    d = np.abs(nova - np.asarray(lateral, float))[ok]
    m0 = medidas_por_trecho(track, lateral, trechos)
    m1 = medidas_por_trecho(track, nova, trechos)
    por_trecho = [{"trecho": t.nome, "raio_original_m": float(a), "raio_codificado_m": float(b), "relativo": float((b - a) / a)}
                  for t, a, b in zip(trechos, m0["raio_min_m"], m1["raio_min_m"])]
    p = float(np.percentile(d, CONFERENCIA_PERCENTIL))
    rel = max(abs(x["relativo"]) for x in por_trecho)
    return {"linha": nome, "pontos": int(ok.sum()), "distancia_p50_m": float(np.median(d)), "distancia_p95_m": p,
            "distancia_max_m": float(d.max()), "fracao_ate_0_10_m": float(np.mean(d <= CONFERENCIA_DISTANCIA_M)),
            "raio_por_trecho": por_trecho, "maior_diferenca_relativa_do_raio": rel,
            "passa": bool(p <= CONFERENCIA_DISTANCIA_M and rel <= CONFERENCIA_RAIO_RELATIVO), "genes": g}


# ------------------------------------------------------------- corredor ---

def reparar_corredor(cod: CodificacaoNova, genes: np.ndarray, vezes: int = 20) -> Tuple[np.ndarray, int]:
    """Item 4.7: traz para dentro os genes cuja vizinhanca cobre um ponto fora do corredor."""
    from ..track.trajectory import corridor_violation

    low, high = cod.track.corridor()
    g = cod.clip(np.asarray(genes, float).copy())
    for rodada in range(vezes + 1):
        lat = cod.decode(g)
        fora = corridor_violation(cod.track, lat)
        if not (fora > 0).any():
            return g, rodada
        if rodada == vezes:
            break
        passo = np.zeros(cod.genes)
        for i in np.flatnonzero(fora > 0):
            sinal = 1.0 if lat[i] < low[i] else -1.0
            for j in cod.vizinhanca([i]):
                if abs(fora[i] + 1e-3) > abs(passo[j]):
                    passo[j] = sinal * (fora[i] + 1e-3)
        g = cod.clip(g + passo)
    raise ValueError("a linha continua fora do corredor depois do reparo")
