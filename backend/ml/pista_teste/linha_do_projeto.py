"""O arquivo da linha do projeto e o veredito do teste no jogo (pedido 50; ADR 0031, itens 2, 4.2 e 8).

* **o arquivo:** a curva da codificacao nova avaliada direto na estacao de
  cada ponto do arquivo original, sem passar pela grade de 2 m. O resto segue
  o escritor do pedido 47 (`linha_nova.montar_por_posicoes`): a altura, a
  normal, as laterais, a grade de vizinhos, os campos de geometria e a
  velocidade e os pedais do original na mesma estacao (item 8);
* **o veredito da meta (item 2):** a melhor volta valida da linha igual ou menor
  que a melhor volta valida do bloco de C0 logo antes **e** do bloco logo depois.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

import numpy as np

from . import linha_nova as N
from .ai_spline import AiSpline

SEMENTE = 50
MINIMO_DE_VALIDAS = 5
NAO_INFERIOR_S = 0.10


def montar_da_curva(original: AiSpline, track, codificacao, genes: np.ndarray) -> N.LinhaNova:
    """O `fast_lane.ai` da linha: a curva X/Z em cada estacao do original (ADR 0031, item 4.2)."""
    s = np.mod(N.estacoes(original, track), track.length)
    xz = codificacao.curva(np.asarray(genes, float), s)
    return N.montar_por_posicoes(original, xz, s)


def veredito_da_meta(linha: Sequence[float], c0_antes: Sequence[float], c0_depois: Sequence[float],
                     troca_pegou: bool = True) -> Dict[str, object]:
    """ADR 0031, item 2. Cada lista: os tempos (s) das voltas validas entre as 7 que contam do bloco."""
    linha, antes, depois = (np.asarray(x, float) for x in (linha, c0_antes, c0_depois))
    out = {"validas": {"linha": int(linha.size), "c0_antes": int(antes.size), "c0_depois": int(depois.size)},
           "melhor_s": {"linha": float(linha.min()) if linha.size else None,
                        "c0_antes": float(antes.min()) if antes.size else None,
                        "c0_depois": float(depois.min()) if depois.size else None}}
    if not troca_pegou:
        out["veredito"] = "fora do veredito: a troca nao pegou"
        return out
    poucas = [k for k, v in out["validas"].items() if v < MINIMO_DE_VALIDAS]
    if poucas:
        out["veredito"] = "nao conclusivo (voltas validas insuficientes: " + ", ".join(poucas) + ")"
        return out
    m = out["melhor_s"]
    out["falta_s"] = {"contra_c0_antes": m["linha"] - m["c0_antes"], "contra_c0_depois": m["linha"] - m["c0_depois"]}
    out["veredito"] = "meta atingida" if (m["linha"] <= m["c0_antes"] and m["linha"] <= m["c0_depois"]) else "meta nao atingida"
    return out


def diferenca_contra_os_vizinhos(linha: Sequence[float], c0_antes: Sequence[float], c0_depois: Sequence[float]) -> Optional[Dict[str, object]]:
    """So relatado (item 2): a diferenca das medianas contra os dois C0 vizinhos juntos, com o IC (semente 50)."""
    from .etapas import bootstrap_diferenca

    base = np.r_[np.asarray(c0_antes, float), np.asarray(c0_depois, float)]
    linha = np.asarray(linha, float)
    if not linha.size or not base.size:
        return None
    d = bootstrap_diferenca(linha, base, semente=SEMENTE)
    d["nao_inferior"] = bool(d["ic95_superior_s"] <= NAO_INFERIOR_S)
    return d
