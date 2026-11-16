"""O que o engenheiro prepara antes do radio (pedido 52, Partes B e C; ADR 0033).

1. **O ruido de cada trecho** (ADR 0033, item 1): o desvio padrao amostral dos tempos do trecho nas 7
   voltas que contam do bloco 4 do pedido 50 (`trechos_s` do `_resultado.json`). Gravado em
   `data/reference_models/<pista>.ruido_por_trecho.json`, antes de o radio ser ligado.
2. **A conferencia da volta do modelo:** os pontos de cada trecho, os blocos de voz, as placas antes de
   cada freada (em ordem decrescente) e a frase de freie, de vire e de acelere de cada trecho (B.4).

Uso (na pasta backend): python -m core.engenheiro.preparar ruido <resultado.json do 50>
                        python -m core.engenheiro.preparar conferencia <saida.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from core.engenheiro import marcos as M
from core.engenheiro import regras as R

REPO = Path(__file__).resolve().parents[3]
PISTA = "vhe_interlagos"
FORMATO_DO_RUIDO = "ruido-por-trecho/1"
BLOCO_DO_RUIDO = "4"


def caminho_do_ruido(raiz: Path, pista: str = PISTA) -> Path:
    return Path(raiz) / "data" / "reference_models" / f"{pista}.ruido_por_trecho.json"


def encontrar_o_ruido(raizes, pista: str = PISTA) -> Optional[Dict[str, Any]]:
    for raiz in raizes:
        if not raiz:
            continue
        arq = caminho_do_ruido(Path(raiz), pista)
        if arq.exists():
            try:
                d = json.loads(arq.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if d.get("formato") == FORMATO_DO_RUIDO:
                return d
    return None


def ruido(resultado: Path) -> Dict[str, Any]:
    r = json.loads(Path(resultado).read_text(encoding="utf-8"))
    voltas = [v for v in r["voltas"][BLOCO_DO_RUIDO] if v.get("papel") == "conta" and v.get("valida")]
    if len(voltas) != 7:
        raise SystemExit(f"o bloco 4 tem {len(voltas)} voltas que contam, e nao 7")
    nomes = [t["trecho"] for t in r["por_trecho"]["L2"]]
    tempos = np.array([v["trechos_s"] for v in voltas], dtype=float)
    desvio = tempos.std(axis=0, ddof=1)
    return {
        "formato": FORMATO_DO_RUIDO, "pista": PISTA, "pedido": 52, "adr": "0033",
        "regra": "o desvio padrao amostral (ddof = 1) dos tempos do trecho nas 7 voltas que contam do bloco 4 do pedido 50 (a L2)",
        "origem": str(Path(resultado).as_posix()), "geometry_id": r.get("geometry_id"),
        "voltas": [{"sessao": v["sessao"], "sequencia": v["sequencia"], "tempo_s": v["tempo_s"]} for v in voltas],
        "trechos": [{"trecho": n, "ruidoS": round(float(d), 6), "medianaS": round(float(np.median(tempos[:, k])), 6)}
                    for k, (n, d) in enumerate(zip(nomes, desvio))],
    }


def volta_do_modelo():
    from core.assisted_analysis import volta_do_modelo as VM
    from core.radio.analise import grade
    dados = VM.encontrar([REPO], PISTA)
    if dados is None:
        raise SystemExit("sem o arquivo da volta do modelo")
    store = VM.como_volta_do_store(dados)
    return dados, grade(store), float(store["tempoS"])


def conferencia() -> Dict[str, Any]:
    from core.radio.janelas import carregar_geometria
    track = carregar_geometria(REPO)
    marcos = M.encontrar([REPO], PISTA)
    if marcos is None:
        raise SystemExit("sem o arquivo dos marcos")
    pontos_marcos = M.pontos_de_referencia(marcos["marcos"])
    dados, g, total = volta_do_modelo()
    L = float(track.length)
    trechos = R.trechos_da_pista(track)
    tempos = R.tempos_dos_trechos(g["elapsed"], total, track, trechos)
    pontos = [R.pontos_do_trecho(g, total, track, trechos, k) for k in range(len(trechos))]
    blocos = R.blocos_de_voz(g, total, track, trechos)
    # os conjuntos de placas (a mesma lado, a menos de 200 m uma da outra) e a freada da volta do modelo depois
    # da primeira placa de cada conjunto: os valores tem de cair ao longo da pista (200, 100, 50)
    placas = sorted([m for m in marcos["marcos"] if m["tipo"] == "placa"], key=lambda m: m["s"])
    conjuntos: List[List[Dict[str, Any]]] = []
    for m in placas:
        if conjuntos and conjuntos[-1][-1]["lado"] == m["lado"] and m["s"] - conjuntos[-1][-1]["s"] <= 200.0:
            conjuntos[-1].append(m)
        else:
            conjuntos.append([m])
    freadas = [(p["trecho"], p["freada"]) for p in pontos if p["freada"] is not None]
    antes_da_freada = []
    for c in conjuntos:
        valores = [m["valor"] for m in c]
        trecho, freada = min(freadas, key=lambda tf: (tf[1] - c[0]["s"]) % L)
        antes_da_freada.append({
            "placas": [{"s": m["s"], "valor": m["valor"], "lado": m["lado"],
                        "freadaMenosPlacaM": round(R._d(freada, m["s"], L), 1)} for m in c],
            "decrescente": all(a > b for a, b in zip(valores, valores[1:])),
            "freadaDepoisDaPrimeira": {"trecho": trecho, "s": round(freada, 1),
                                       "depoisDaPrimeiraM": round((freada - c[0]["s"]) % L, 1)}})
    frases = []
    for t, p in zip(trechos, pontos):
        linha = {"trecho": t.nome, "pontos": {k: (round(v, 1) if isinstance(v, float) else v) for k, v in p.items()}}
        # ADR 0033, emenda de 16/11, item 3: a referencia nao freia nem alivia: "sem tirar o pé", para qualquer causa
        if t.tem_curva and p.get("semTirarOPe"):
            f = R.frase_sem_tirar_o_pe(t.entrada_s, L)
            f["fala"] = R.fala_do_aviso(t.nome, f["frase"])
            f["escrita"] = R.escrita_do_aviso(t.nome, f["frase"])
            f["sPonto"] = round(float(t.entrada_s), 1)
            linha[R.SEM_TIRAR_O_PE] = f
            linha.update(freie=None, vire=None, acelere=None)
            frases.append(linha)
            continue
        for acao, chave in (("freie", "freada"), ("vire", "entrada"), ("acelere", "retomada")):
            s = p.get(chave)
            if s is None:
                linha[acao] = None
                continue
            f = R.frase_da_acao(acao, s, pontos_marcos, L)
            f["fala"] = R.fala_do_aviso(t.nome, f["frase"])
            f["escrita"] = R.escrita_do_aviso(t.nome, f["frase"])
            f["sPonto"] = round(float(s), 1)
            linha[acao] = f
        frases.append(linha)
    return {
        "pedido": 52, "geometry_id": track.geometry_id, "comprimentoM": round(L, 3),
        "voltaDoModelo": {"tempo_s": total, "origem": dados.get("origem"), "marca": dados.get("marca")},
        "trechos": [{"trecho": t.nome, "inicio": round(t.inicio_s, 1), "fim": round(t.fim_s, 1),
                     "tempoS": round(float(x), 4)} for t, x in zip(trechos, tempos)],
        "somaDosTrechosS": round(float(np.sum(tempos)), 5),
        "blocos": blocos, "placasAntesDaFreada": antes_da_freada, "frases": frases,
    }


def main(argv: List[str]) -> int:
    if argv[:1] == ["ruido"]:
        d = ruido(Path(argv[1]))
        saida = caminho_do_ruido(REPO)
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(saida)
        for t in d["trechos"]:
            print(f"  {t['trecho']:<11} ruido {t['ruidoS'] * 1000:6.1f} ms   mediana {t['medianaS']:.3f} s")
        return 0
    if argv[:1] == ["conferencia"]:
        d = conferencia()
        Path(argv[1]).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        print(argv[1])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
