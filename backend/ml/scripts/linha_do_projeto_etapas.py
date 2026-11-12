"""As etapas do pedido 50 que vem depois da conferencia (ADR 0031): o medidor, a L1, a L2 e os arquivos."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict

import numpy as np

from ml.optimization import codificacao_nova as CN
from ml.optimization import medidor_calibrado as MC
from ml.pista_teste import condicoes as C
from ml.scripts.linha_do_projeto import CONTA_DO_49, Base, _cabecalho, _json, _ler_json, raiz

RESULTADO_DO_47 = "docs/handoff/2026-11-07_47_linha-gerada-no-jogo_resultado.json"
LINHAS_DO_47 = ("C1", "C2", "C3", "C4")


def _repo() -> Path:
    from ml import config
    return config.repo_root()


def trecho_de_cada_passo(track, trechos) -> np.ndarray:
    out = np.full(track.size, -1, int)
    for k, m in enumerate(CN.mascaras_dos_trechos(track, trechos)):
        out[m] = k
    if (out < 0).any():
        raise SystemExit("PARADO: um ponto da grade sem trecho.")
    return out


def tempos_do_jogo(b: Base, sectors) -> Dict[str, dict]:
    """Por condicao do 47: as medianas por trecho (do `_conta.json` do 49) e por microssetor (refeitas das gravacoes)."""
    from ml.pista_teste.etapas import tempos_por_microssetor
    from ml.scripts.modelo1_por_trecho import carregar_voltas_do_teste

    conta = _ler_json(_repo() / CONTA_DO_49)
    resultado = _ler_json(_repo() / RESULTADO_DO_47)
    teste = carregar_voltas_do_teste(b.track, resultado)
    out = {}
    for cond, voltas in conta["voltas"].items():
        trecho = np.array([v["tempos_por_trecho_s"] for v in voltas], float)
        micro = []
        for v in teste["voltas"][cond]:
            ms = tempos_por_microssetor(v["grid"], b.track, sectors, v["tempo_s"])
            if abs(ms.sum() - v["tempo_s"]) > 0.005:
                raise SystemExit(f"PARADO: os microssetores da volta {v['id']} nao somam o tempo dela.")
            micro.append(ms)
        if len(micro) != len(trecho):
            raise SystemExit(f"PARADO: {cond}: {len(micro)} voltas refeitas e {len(trecho)} no conta.json do 49.")
        out[cond] = {"voltas": len(trecho), "trecho_mediana": np.median(trecho, axis=0),
                     "micro_mediana": np.median(np.array(micro), axis=0), "volta_mediana": float(np.median(trecho.sum(axis=1)))}
    return out, teste["arquivos"]


def medidor(args) -> int:
    from ml.optimization.lap_time_model import simulate
    from ml.optimization.vehicle_model import load_envelope
    from ml.scripts.modelo1_final import medidor as medidor_do_46
    from ml.track.microsectors import build_microsectors

    t0 = time.time()
    b = Base()
    track = b.track
    sectors = build_microsectors(track)
    passo_trecho = trecho_de_cada_passo(track, b.trechos)
    K = len(b.trechos)
    jogo, arquivos = tempos_do_jogo(b, sectors)
    laterais = C.linhas(track, b.xz_c0)

    env_real, desc_real = medidor_do_46("real")
    env_v2, desc_v2 = medidor_do_46("m1v2")
    envelopes = {"M-real": env_real, "M-v2": env_v2}
    passos = {nome: {x: simulate(track, laterais[x], env).step_time_s for x in ("C0",) + LINHAS_DO_47}
              for nome, env in envelopes.items()}

    dJ_trecho = {x: jogo[x]["trecho_mediana"] - jogo["C0"]["trecho_mediana"] for x in LINHAS_DO_47}
    dJ_micro = {x: jogo[x]["micro_mediana"] - jogo["C0"]["micro_mediana"] for x in LINHAS_DO_47}
    dS_trecho = {nome: {x: MC.diferenca_por_grupo(p[x], p["C0"], passo_trecho, K) for x in LINHAS_DO_47}
                 for nome, p in passos.items()}

    previsto_micro = {}
    for nome in envelopes:
        previsto_micro[nome] = {x: MC.diferenca_por_grupo(passos[nome][x], passos[nome]["C0"], sectors.index, sectors.count)
                                for x in LINHAS_DO_47}
    betas_fora = MC.deixar_uma_de_fora(dJ_trecho, dS_trecho["M-real"], LINHAS_DO_47)
    previsto_micro["M-cal"] = {x: MC.diferenca_por_grupo(passos["M-real"][x], passos["M-real"]["C0"], sectors.index,
                                                         sectors.count, MC.pesos_por_passo(betas_fora[x], passo_trecho))
                               for x in LINHAS_DO_47}
    beta_todas = MC.ajustar_beta(dJ_trecho, dS_trecho["M-real"], LINHAS_DO_47)

    candidatos = {nome: MC.spearman_juntos(previsto_micro[nome], dJ_micro, LINHAS_DO_47) for nome in ("M-real", "M-cal", "M-v2")}
    escolhido = MC.escolher(candidatos)

    J0 = jogo["C0"]["volta_mediana"]
    volta = {}
    for x in ("C0",) + LINHAS_DO_47:
        linha = {"jogo_mediana_s": jogo[x]["volta_mediana"], "jogo_contra_c0_s": jogo[x]["volta_mediana"] - J0}
        for nome in envelopes:
            linha[f"{nome}_s"] = float(passos[nome][x].sum())
            linha[f"{nome}_contra_c0_s"] = float(passos[nome][x].sum() - passos[nome]["C0"].sum())
        if x != "C0":
            linha["M-cal_fora_contra_c0_s"] = float(np.sum(betas_fora[x] * dS_trecho["M-real"][x]))
            linha["M-cal_fora_s"] = J0 + linha["M-cal_fora_contra_c0_s"]
        volta[x] = linha

    payload = {**_cabecalho("B.2", "python -m ml.scripts.linha_do_projeto medidor", track),
               "candidatos": {"M-real": desc_real, "M-v2": {k: v for k, v in desc_v2.items() if k != "envelope"},
                              "M-cal": "M-real com uma escala por trecho, pela origem, em [0, 2] (ADR 0031, item 5.2)"},
               "linhas_do_47": {"fonte": "ml.pista_teste.condicoes.linhas", "base": "C0 (o primeiro bloco)",
                                "c0_final_mediana_s": jogo["C0 final"]["volta_mediana"],
                                "voltas": {k: v["voltas"] for k, v in jogo.items()}},
               "gravacoes_lidas": arquivos,
               "spearman": candidatos, "escolhido": escolhido,
               "beta": {"todas": {t.nome: float(beta_todas[k]) for k, t in enumerate(b.trechos)},
                        "deixando_de_fora": {x: {t.nome: float(v[k]) for k, t in enumerate(b.trechos)} for x, v in betas_fora.items()}},
               "por_trecho": {t.nome: {"jogo": {x: float(dJ_trecho[x][k]) for x in LINHAS_DO_47},
                                       **{nome: {x: float(dS_trecho[nome][x][k]) for x in LINHAS_DO_47} for nome in envelopes}}
                              for k, t in enumerate(b.trechos)},
               "por_microssetor": {"jogo": dJ_micro, "previsto": previsto_micro},
               "volta": volta, "tempo_s": round(time.time() - t0, 1)}
    _json(raiz() / "medidor.json", payload)
    np.save(raiz() / "beta_todas.npy", beta_todas)
    if args.handoff:
        _json(Path(str(args.handoff) + "_medidor.json"), payload)
    for nome, r in candidatos.items():
        print(f"{nome:7s} rho {r['rho']:+.3f} (p {r['p']:.2g})  " + "  ".join(f"{x} {v['rho']:+.2f}" for x, v in r["por_linha"].items()))
    print("escolhido:", escolhido)
    for x, v in volta.items():
        print(x, {k: round(val, 3) for k, val in v.items()})
    return 0


def l1(args) -> int:
    raise SystemExit("PARADO: a L1 depende da codificacao nova, e a conferencia do item 4.5 nao passou (ADR 0031, item 4.6).")


def l2(args) -> int:
    raise SystemExit("PARADO: a L2 depende da L1.")


def arquivos(args) -> int:
    raise SystemExit("PARADO: os arquivos dependem da L1 e da L2.")
