"""A referencia por trecho do Modelo 1 (pedido 49, Parte C; ADR 0030, item 9).

    python -m ml.scripts.referencia_por_trecho [--handoff PREFIXO]

Le `data/modelo1_por_trecho/conta.json` (a Parte B, `ml.scripts.modelo1_por_trecho`)
e escreve `data/modelo1_por_trecho/referencia_por_trecho.json`, fora do git
porque deriva do `fast_lane.ai` do jogo. Com `--handoff`, um resumo sem a
lateral ponto a ponto vai para `<PREFIXO>_referencia.json`.

Por trecho: os limites, a linha de referencia (a linha da IA, C0, em todos os
trechos neste pedido), a execucao da IA nela, a candidata (quando houver, "a
validar no jogo") e as propostas provisorias ("provisorio, sem confirmacao").
**O coach nao le este arquivo.**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml.pista_teste import por_trecho as PT  # noqa: E402
from ml.scripts.modelo1_por_trecho import _json, indice, raiz_saida  # noqa: E402

AVISO = ("Referencia por trecho do Modelo 1 (pedido 49; ADR 0030). O coach nao le este arquivo. A referencia de todo "
         "trecho e a linha da IA (C0); uma candidata so vira referencia depois de vencer num teste novo no jogo; "
         "as propostas provisorias dependem da confirmacao do Eduardo (decisoes 3 e 5 do desenho).")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def montar(conta: dict, track, com_lateral: bool = True) -> dict:
    nomes = conta["nomes_dos_trechos"]
    trechos = [PT.Trecho(t["trecho"], t["inicio_s"], t["fim_s"], t["pontos_de_linha_s"]["entrada"],
                         t["pontos_de_linha_s"]["apice"] if t["trecho"] != PT.NOME_DA_CHEGADA else None,
                         t["pontos_de_linha_s"]["saida"], t["trecho"] != PT.NOME_DA_CHEGADA) for t in conta["trechos"]]
    lat = {k: np.asarray(v, float) for k, v in conta["lateral_da_linha"].items()}
    candidatas = {(c["trecho"], c["linha"]): c for c in conta["candidatas"]}
    lista = []
    for j, (t, info) in enumerate(zip(trechos, conta["trechos"])):
        idx = t.indices(track.s, track.length)
        pontos = info["pontos_de_linha_s"]
        ref = {"linha": "C0", "descricao": "a linha da IA (o fast_lane.ai original), projetada na grade",
               "lateral_nos_pontos_de_linha_m": {k: float(lat["C0"][indice(track, s)]) for k, s in pontos.items()}}
        if com_lateral:
            ref.update({"s": track.s[idx].tolist(), "lateral_m": lat["C0"][idx].tolist()})
        else:
            ref["pontos_na_grade"] = int(len(idx))
        cand = None
        achadas = [candidatas[(t.nome, x)] for x in ("C3", "C4") if (t.nome, x) in candidatas]
        if achadas:
            melhor = min(achadas, key=lambda c: c["ganho_contra_c0_s"])
            x = melhor["linha"]
            comp0 = conta["comparacoes"][f"{x} contra C0"][j]
            compf = conta["comparacoes"][f"{x} contra C0 final"][j]
            cand = {"linha": x, "marca": "a validar no jogo",
                    "ganho_contra_c0_s": comp0["diferenca_s"], "ic95_contra_c0_s": [comp0["ic95_inferior_s"], comp0["ic95_superior_s"]],
                    "p_contra_c0": comp0["p_permutacao"],
                    "ganho_contra_c0_final_s": compf["diferenca_s"], "ic95_contra_c0_final_s": [compf["ic95_inferior_s"], compf["ic95_superior_s"]],
                    "p_contra_c0_final": compf["p_permutacao"],
                    "outras_candidatas": [c["linha"] for c in achadas if c is not melhor],
                    "lateral_nos_pontos_de_linha_m": {k: float(lat[x][indice(track, s)]) for k, s in pontos.items()}}
            if com_lateral:
                cand["lateral_m"] = lat[x][idx].tolist()
        eu = conta["eduardo"]["linha"][j]
        prov = {"marca": "provisorio, sem confirmacao",
                "frenagem_traduzida_s": eu["frenagem_traduzida_s"], "frenagem_da_ia_s": eu["ia_frenagem_inicio_s"],
                "rampa_do_freio_m": eu["rampa_do_freio_m"], "voltas_com_frenagem": eu["voltas_com_frenagem"],
                "limite_de_linha": {k: {"s": p["s"], "limite_m": p["limite_m"], "mediana_do_eduardo_m": p["minha_mediana_m"]}
                                    for k, p in eu["pontos"].items()}}
        lista.append({"trecho": t.nome, "inicio_s": t.inicio_s, "fim_s": t.fim_s, "pontos_de_linha_s": pontos,
                      "linha_de_referencia": ref,
                      "execucao_da_ia": {"linha": "C0", "voltas": conta["execucao"]["C0"][j]["resumo"]["voltas"],
                                         "medidas": conta["execucao"]["C0"][j]["resumo"],
                                         "tempo_do_trecho": {k: conta["tempos"]["C0"][j][k] for k in ("mediana_s", "desvio_s", "iqr_s")}},
                      "candidata": cand, "provisorio": prov})
    return lista


def main(argv=None) -> int:
    from ml.data.store_v2 import git_commit
    from ml.track.geometry import load_corridor_geometry

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--handoff", help="prefixo do resumo de handoff")
    args = parser.parse_args(argv)
    caminho = raiz_saida() / "conta.json"
    conta = json.loads(caminho.read_text(encoding="utf-8"))
    track = load_corridor_geometry()
    if conta["geometry_id"] != track.geometry_id or conta["corridor_id"] != track.corridor_id:
        raise SystemExit("PARADO: a conta foi feita com outra geometria.")
    base = {"pedido": 49, "adr": "docs/decisoes/0030-modelo1-por-trecho.md", "commit": git_commit(),
            "commit_da_conta": conta["commit"], "comando": "python -m ml.scripts.referencia_por_trecho",
            "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, "grade_m": float(track.step),
            "gravacoes": {"copia_da_pista": conta["entradas"]["gravacoes_da_copia"],
                          "voltas_humano": conta["entradas"]["voltas_humano"]},
            "arquivos": {"conta": {"arquivo": caminho, "sha256": _sha256(caminho)},
                         "resultado_47": conta["entradas"]["resultado_47"], "linhas": conta["entradas"]["linhas"]},
            "aviso": AVISO}
    completo = {**base, "trechos": montar(conta, track, com_lateral=True)}
    PT.conferir_formato_da_referencia(completo)
    _json(raiz_saida() / "referencia_por_trecho.json", completo)
    if args.handoff:
        resumo = {**base, "trechos": montar(conta, track, com_lateral=False)}
        PT.conferir_formato_da_referencia(resumo, com_lateral=False)
        _json(Path(str(args.handoff) + "_referencia.json"), resumo)
    cand = [(t["trecho"], t["candidata"]["linha"]) for t in completo["trechos"] if t["candidata"]]
    print(f"{len(completo['trechos'])} trechos; candidatas: {cand or 'nenhuma'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
