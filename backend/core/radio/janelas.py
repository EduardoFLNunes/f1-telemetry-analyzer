"""As janelas de radio (pedido 31, Parte B.2): onde a mensagem pode ser entregue.

Uma janela e um trecho da geometria oficial fora das 14 curvas, como um
engenheiro que nao fala na freada (ADR 0020, decisao 4):

* cada curva e o trecho em que a pista curva (`ml.track.corners.detect_corners`),
  com uma margem antes dela para a freada e uma depois para a saida;
* o que sobra, com pelo menos `JANELA_MINIMA_M`, e janela.

A posicao do carro e a projecao na geometria oficial que o coach ja faz
(`LiveDrivingCoach.posicao_oficial`). Nenhum calculo novo de posicao.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .texto import LADO, CurvaDaPista

MARGEM_ANTES_DA_CURVA_M = 120.0   # a freada
MARGEM_DEPOIS_DA_CURVA_M = 30.0   # a saida, ainda acelerando com o volante virado
JANELA_MINIMA_M = 80.0
CACHE_DA_PISTA = "vhe_interlagos_gp_kn5_surface_interval_geometry.json"

Janela = Tuple[float, float]


def curvas_da_geometria(track) -> List[CurvaDaPista]:
    """As 14 curvas e os trechos delas, pelas mesmas funcoes do relatorio de evolucao."""
    from ml.comparison.evolution import corner_segments
    from ml.track.corners import detect_corners

    corners = detect_corners(track)
    out = []
    for seg in corner_segments(track, corners):
        rotulo = seg.corner.label  # C01-esq
        out.append(CurvaDaPista(
            codigo=rotulo[:3], lado=LADO.get(rotulo[4:], rotulo[4:]),
            inicio_m=float(seg.corner.start_s), fim_m=float(seg.corner.end_s),
            trecho_inicio_m=float(seg.start_s), trecho_fim_m=float(seg.end_s),
        ))
    return out


def carregar_geometria(repositorio: Optional[Path]):
    """A geometria do ML (a mesma grade do store e da volta ao vivo) do repositorio configurado, ou None."""
    if repositorio is None:
        return None
    from ml.track.geometry import load_geometry

    cache = Path(repositorio) / "data" / "cache" / "tracks" / CACHE_DA_PISTA
    if not cache.exists():
        return None
    return load_geometry(cache)


def carregar_curvas(repositorio: Optional[Path]) -> Tuple[List[CurvaDaPista], Optional[float]]:
    """As curvas da geometria oficial do repositorio configurado, e o comprimento da volta."""
    track = carregar_geometria(repositorio)
    if track is None:
        return [], None
    return curvas_da_geometria(track), float(track.length)


def tempo_que_resta(janelas: Sequence[Janela], s: float, comprimento: float, velocidade_kmh: Optional[float]) -> float:
    """Pedido 35: quanto tempo o carro ainda fica na janela em que esta, na velocidade de agora (0 fora dela)."""
    janela = dentro(janelas, s, comprimento)
    if janela is None or not velocidade_kmh or velocidade_kmh <= 1.0:
        return 0.0
    restante_m = (janela[1] - (s % comprimento)) % comprimento
    return restante_m / (velocidade_kmh / 3.6)


def janelas_de_radio(curvas: Sequence[CurvaDaPista], comprimento: float,
                     antes: float = MARGEM_ANTES_DA_CURVA_M, depois: float = MARGEM_DEPOIS_DA_CURVA_M,
                     minima: float = JANELA_MINIMA_M) -> List[Janela]:
    """Os trechos fora das curvas (com as margens), de pelo menos `minima` metros, em ordem de `s`."""
    if not curvas or not comprimento:
        return []
    L = float(comprimento)
    # Marca, num passo de 1 m, o que esta ocupado por curva + margens (a pista e fechada).
    ocupado = bytearray(int(L) + 1)
    for c in curvas:
        a = (c.inicio_m - antes) % L
        b = (c.fim_m + depois) % L
        n = int(round(((b - a) % L)))
        for k in range(n + 1):
            ocupado[int((a + k) % L)] = 1
    janelas: List[Janela] = []
    k = 0
    n = len(ocupado)
    while k < n:
        if ocupado[k]:
            k += 1
            continue
        inicio = k
        while k < n and not ocupado[k]:
            k += 1
        janelas.append((float(inicio), float(min(k, L))))
    # Junta a que termina na linha com a que comeca nela (a reta dos boxes cruza s = 0).
    if len(janelas) > 1 and janelas[0][0] == 0.0 and janelas[-1][1] >= L - 1.0:
        primeira = janelas.pop(0)
        ultima = janelas.pop()
        janelas.append((ultima[0], primeira[1]))
    def tamanho(j: Janela) -> float:
        return (j[1] - j[0]) % L if j[1] != j[0] else L
    return [j for j in janelas if tamanho(j) >= minima]


def dentro(janelas: Sequence[Janela], s: float, comprimento: float) -> Optional[Janela]:
    """A janela em que `s` esta, ou None."""
    x = s % comprimento
    for a, b in janelas:
        if (a <= b and a <= x < b) or (a > b and (x >= a or x < b)):
            return (a, b)
    return None
