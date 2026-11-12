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


# ----------------------------------------------------- as duas linhas ---

class Medidores:
    """Os tres medidores do item 5, para prever o tempo de uma linha (a diferenca contra o C0 e o tempo)."""

    def __init__(self, b: Base):
        from ml.optimization.lap_time_model import simulate
        from ml.scripts.modelo1_final import medidor as medidor_do_46

        self.b = b
        self.simulate = simulate
        self.env = {"M-real": medidor_do_46("real")[0], "M-v2": medidor_do_46("m1v2")[0]}
        self.beta = np.load(raiz() / "beta_todas.npy")
        self.passo_trecho = trecho_de_cada_passo(b.track, b.trechos)
        med = _ler_json(raiz() / "medidor.json")
        self.escolhido = med["escolhido"]
        self.j0 = med["volta"]["C0"]["jogo_mediana_s"]
        self.base = {k: simulate(b.track, b.lateral_c0_47, e).step_time_s for k, e in self.env.items()}

    def prever(self, lateral: np.ndarray) -> Dict[str, dict]:
        out = {}
        for k, e in self.env.items():
            p = self.simulate(self.b.track, lateral, e).step_time_s
            out[k] = {"tempo_s": float(p.sum()), "contra_c0_s": float(p.sum() - self.base[k].sum())}
            if k == "M-real":
                d = float(np.sum(self.beta[self.passo_trecho] * (p - self.base[k])))
                out["M-cal"] = {"tempo_s": self.j0 + d, "contra_c0_s": d}
        return out


def _base_com_c0_do_47(b: Base) -> Base:
    """A lateral do C0 como o 47 e o medidor a usaram (`condicoes.linhas`), para a base dos medidores."""
    b.lateral_c0_47 = b.lateral_c0
    return b


def relatorio_da_linha(b: Base, cod, genes: np.ndarray, lateral: np.ndarray, limites: Dict[str, np.ndarray],
                       medidores: Medidores, shape) -> Dict[str, object]:
    """B.3: o tempo previsto pelos tres medidores, a distancia a linha da IA, o corredor, o raio e a taxa por trecho."""
    from ml.pista_teste import linha_do_projeto as LP
    from ml.scripts.modelo1_final import forma

    track = b.track
    med = CN.medidas_por_trecho(track, lateral, b.trechos)
    exc = CN.excesso_das_restricoes(med, limites)
    arquivo = LP.montar_da_curva(b.original, track, cod, genes).spline
    r3 = arquivo.campo("raio").astype(float)
    por_trecho = []
    for k, (t, m) in enumerate(zip(b.trechos, CN.mascaras_dos_trechos(track, b.trechos))):
        d = np.abs(lateral[m] - b.lateral_c0[m])
        ms = (b.estacao >= t.inicio_s - 1e-9) & (b.estacao < t.fim_s - 1e-9)
        por_trecho.append({"trecho": t.nome, "distancia_a_linha_da_ia_m": {"mediana": float(np.median(d)), "max": float(d.max())},
                           "raio_min_12m_m": float(med["raio_min_m"][k]), "raio_min_em_s": float(med["raio_min_em_s"][k]),
                           "raio_limite_m": float(limites["raio_min_m"][k]),
                           "taxa_max": float(med["taxa_max"][k]), "taxa_limite": float(limites["taxa_max"][k]),
                           "dentro_das_restricoes": bool(exc["raio"][k] == 0 and exc["taxa"][k] == 0),
                           "raio_min_do_arquivo_m": float(r3[ms].min()),
                           "raio_min_do_arquivo_em_s": float(b.estacao[ms][int(np.argmin(r3[ms]))])})
    return {"genes": int(cod.genes), "tempo_previsto": medidores.prever(lateral), "forma_e_corredor": forma(track, lateral, shape),
            "dentro_das_restricoes": bool(all(x["dentro_das_restricoes"] for x in por_trecho)), "por_trecho": por_trecho,
            "distancia_a_linha_da_ia_m": {"mediana": float(np.median(np.abs(lateral - b.lateral_c0))),
                                          "max": float(np.max(np.abs(lateral - b.lateral_c0)))}}


def _limites() -> Dict[str, np.ndarray]:
    r = _ler_json(raiz() / "conferencia.json")["restricoes"]["por_trecho"]
    return {"raio_min_m": np.array([x["raio_min_m"] for x in r]), "taxa_max": np.array([x["taxa_max"] for x in r])}


def _shape(b: Base, laterais):
    from ml.optimization.fitness import fit_shape_reference
    return fit_shape_reference(b.track, np.vstack(list(laterais.values())))


def l1(args) -> int:
    from ml.optimization import montagem as MO

    t0 = time.time()
    b = _base_com_c0_do_47(Base())
    track = b.track
    cod = b.codificacao()
    laterais47 = C.linhas(track, b.xz_c0)
    conta = _ler_json(_repo() / CONTA_DO_49)
    nomes = [t.nome for t in b.trechos]
    if conta["nomes_dos_trechos"] != nomes:
        raise SystemExit("PARADO: os trechos do conta.json do 49 nao sao os desta geometria.")
    medianas = {x: [r["mediana_s"] for r in conta["tempos"][x]] for x in ("C2", "C3", "C4")}
    escolha = MO.escolher_por_trecho(medianas, ["C2", "C3", "C4"])
    montada = MO.montar(track.s, track.length, b.trechos, escolha, laterais47)
    genes = cod.encode(montada["lateral"])
    genes, rodadas = CN.reparar_corredor(cod, genes)
    lateral = cod.decode(genes)
    limites = _limites()
    voltas, _, _ = b.voltas_rotuladas()
    shape = _shape(b, voltas)
    medidores = Medidores(b)
    rel = relatorio_da_linha(b, cod, genes, lateral, limites, medidores, shape)
    c0_nos_medidores = medidores.prever(b.lateral_c0)
    np.save(raiz() / "l1_genes.npy", genes)
    np.save(raiz() / "l1_lateral.npy", lateral)
    np.save(raiz() / "l1_montada_antes_da_codificacao.npy", montada["lateral"])
    payload = {**_cabecalho("B.3 (L1)", "python -m ml.scripts.linha_do_projeto l1", track),
               "codificacao": cod.descricao(),
               "escolha_por_trecho": [{"trecho": n, "linha": e, "mediana_no_jogo_s": float(medianas[e][k]),
                                       "c0_mediana_no_jogo_s": float(conta["tempos"]["C0"][k]["mediana_s"]),
                                       "contra_c0_s": float(medianas[e][k] - conta["tempos"]["C0"][k]["mediana_s"])}
                                      for k, (n, e) in enumerate(zip(nomes, escolha))],
               "soma_das_diferencas_contra_c0_s": float(sum(medianas[e][k] - conta["tempos"]["C0"][k]["mediana_s"]
                                                             for k, e in enumerate(escolha))),
               "emendas": montada["emendas"],
               "codificada_contra_montada_m": {"p50": float(np.median(np.abs(lateral - montada["lateral"]))),
                                               "p95": float(np.percentile(np.abs(lateral - montada["lateral"]), 95)),
                                               "max": float(np.max(np.abs(lateral - montada["lateral"])))},
               "reparo_do_corredor_rodadas": int(rodadas), "linha": rel, "c0_nos_medidores": c0_nos_medidores,
               "tempo_s": round(time.time() - t0, 1)}
    _json(raiz() / "l1.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_l1.json"), payload)
    print("escolha:", dict(zip(nomes, escolha)))
    print("soma das diferencas no jogo (teto):", round(payload["soma_das_diferencas_contra_c0_s"], 3))
    print("previsto:", {k: round(v["contra_c0_s"], 3) for k, v in rel["tempo_previsto"].items()})
    print("forma:", rel["forma_e_corredor"], "restricoes:", rel["dentro_das_restricoes"])
    if not rel["dentro_das_restricoes"]:
        print("PARADO: a L1 passa de um limite das restricoes (ADR 0031, item 4.4).")
        return 2
    return 0


def l2(args) -> int:
    from ml.features.performance import build_reference
    from ml.models.reference_line import generate
    from ml.models.training import load_model
    from ml.optimization.aptidao_do_projeto import AptidaoDoProjeto, regiao_nos_genes
    from ml.optimization.evolution import EvolutionConfig, evolve
    from ml.optimization.seed import composite_best_segments
    from ml.scripts.modelo1_final import GERACOES, LIMITE_H, POPULACAO, TempoEsgotado, _arquivo
    from ml import config
    from ml.track.microsectors import build_microsectors

    SEMENTE = 50
    t0 = time.time()
    b = _base_com_c0_do_47(Base())
    track = b.track
    cod = b.codificacao()
    g1 = np.load(raiz() / "l1_genes.npy")
    lat1 = cod.decode(g1)
    regiao = regiao_nos_genes(cod, g1)
    limites = _limites()
    voltas, tabela, src = b.voltas_rotuladas()
    shape = _shape(b, voltas)
    medidores = Medidores(b)
    escolhido = medidores.escolhido
    if escolhido == "M-cal":
        env = medidores.env["M-real"]
        pesos, base = medidores.beta[medidores.passo_trecho], medidores.base["M-real"]
    else:
        env, pesos, base = medidores.env[escolhido], None, None
    sectors = build_microsectors(track)
    ordenadas = list(voltas)
    referencia = build_reference(src.store, track, sectors, ordenadas)
    composta = composite_best_segments(track, sectors, voltas, referencia.best_lap_per_sector)
    lstm_root = config.artifacts_root() / "models" / "reference"
    lstm = generate(load_model(lstm_root), track, b.corners).lateral
    sementes = [g1, regiao.encode(composta), regiao.encode(lstm)] + [regiao.encode(voltas[k]) for k in ordenadas]
    rng = np.random.default_rng(SEMENTE)
    aleatorias = int(round(POPULACAO * 0.1))
    populacao = np.vstack(sementes[:POPULACAO - aleatorias] + list(regiao.random(rng, aleatorias)))
    avaliador = AptidaoDoProjeto(track, regiao, env, shape, b.trechos, limites, lat1, pesos, base)
    inicio = avaliador.evaluate(g1[None])
    print(f"L1 na aptidao: {float(inicio['cost'][0]):.3f} s (penalizacao {float(inicio['penalty_total'][0]):.3f} s)", flush=True)

    def progresso(texto):
        print(texto, flush=True)
        if time.time() - t0 > LIMITE_H * 3600:
            raise TempoEsgotado(f"passou de {LIMITE_H} h")

    cfg = EvolutionConfig(generations=GERACOES, population_size=POPULACAO, seed=SEMENTE)
    res = evolve(avaliador, regiao, populacao, cfg, progress=progresso)
    g2 = regiao.clip(res.best_genome)
    lat2 = regiao.decode(g2)
    final = avaliador.evaluate(g2[None])
    penal = {k.replace("penalty_", ""): float(v[0]) for k, v in final.items() if k.startswith("penalty_")}
    np.save(raiz() / "l2_genes.npy", g2)
    np.save(raiz() / "l2_lateral.npy", lat2)
    rel = relatorio_da_linha(b, cod, g2, lat2, limites, medidores, shape)
    payload = {**_cabecalho("B.3 (L2)", "python -m ml.scripts.linha_do_projeto l2", track),
               "codificacao": cod.descricao(), "medidor": escolhido,
               "config": {**cfg.to_dict(), "populacao_inicial_semente": SEMENTE, "aleatorias": aleatorias,
                          "sementes": ["L1", "composicao dos melhores trechos", "LSTM geradora"] + ordenadas[:POPULACAO - aleatorias - 3],
                          "regiao_de_confianca_m": 1.0},
               "lstm": [_arquivo(lstm_root / n) for n in ("model.json", "weights.pt")],
               "l1_na_aptidao_s": float(inicio["cost"][0]),
               "busca": {"geracoes": res.generations_run, "parada": res.stopped_by, "avaliacoes": res.evaluations,
                         "custo_inicial": res.initial_cost, "custo_final": res.best_cost, "historia": res.history},
               "penalizacoes_da_l2": penal, "sem_penalizacao": bool(final["penalty_total"][0] == 0.0),
               "afastamento_da_l1_m": {"max": float(np.max(np.abs(lat2 - lat1))), "p95": float(np.percentile(np.abs(lat2 - lat1), 95))},
               "linha": rel, "tempo_s": round(time.time() - t0, 1)}
    _json(raiz() / "l2.json", payload)
    if args.handoff:
        slim = {**payload, "busca": {k: v for k, v in payload["busca"].items() if k != "historia"}}
        _json(Path(str(args.handoff) + "_l2.json"), slim)
    print("L2:", round(res.best_cost, 3), "s;", res.stopped_by, res.generations_run, "geracoes; penalizacoes", penal)
    print("previsto:", {k: round(v["contra_c0_s"], 3) for k, v in rel["tempo_previsto"].items()})
    if not payload["sem_penalizacao"]:
        print("PARADO: a melhor da busca tem penalizacao (ADR 0031, item 7).")
        return 2
    return 0


def arquivos(args) -> int:
    """B.4: os `fast_lane.ai` da L1 e da L2, o manifesto a parte e a figura."""
    from ml.pista_teste import ai_spline as A
    from ml.pista_teste import linha_do_projeto as LP

    b = Base()
    track = b.track
    cod = b.codificacao()
    pasta = C.raiz_saida() / "linhas"
    manifesto = {"pedido": 50, "adr": "0031", "parte": "B.4", "commit": _cabecalho("", "", track)["commit"],
                 "comando": "python -m ml.scripts.linha_do_projeto arquivos",
                 "original": {"sha256": b.original_sha256, "pontos": b.original.n},
                 "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, "codificacao": cod.descricao(),
                 "condicoes": {}}
    splines = {}
    for nome in ("L1", "L2"):
        genes = np.load(raiz() / f"{nome.lower()}_genes.npy")
        ln = LP.montar_da_curva(b.original, track, cod, genes)
        dados = A.escrever(ln.spline)
        destino = pasta / nome / "fast_lane.ai"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
        relido = A.ler(destino)
        if not (A.escrever(relido) == dados and relido.n == b.original.n):
            raise SystemExit(f"PARADO: o arquivo da {nome} nao volta igual depois de relido.")
        iguais = all(np.array_equal(relido.campo(c), b.original.campo(c)) for c in ("velocidade", "acelerador", "freio"))
        manifesto["condicoes"][nome] = {"arquivo": destino, "bytes": len(dados), "sha256": A.sha256_arquivo(destino),
                                        "pontos": relido.n, "relido_igual": True,
                                        "velocidade_e_pedais_do_original": bool(iguais),
                                        "deslocamento_do_original_m": {"mediana": float(np.median(ln.deslocamento_m)),
                                                                       "max": float(ln.deslocamento_m.max())},
                                        "raio_do_arquivo_min_m": float(relido.campo("raio").min())}
        splines[nome] = relido
    _json(pasta / "linha_do_projeto.json", manifesto)
    if args.handoff:
        _json(Path(str(args.handoff) + "_arquivos.json"), manifesto)
        figura(b, {"L1": np.load(raiz() / "l1_lateral.npy"), "L2": np.load(raiz() / "l2_lateral.npy")},
               Path(str(args.handoff) + "_linhas.png"))
    for nome, item in manifesto["condicoes"].items():
        print(f"{nome}  {item['sha256']}  {item['bytes']} bytes")
    return 0


def figura(b: Base, laterais: Dict[str, np.ndarray], destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ml.track.trajectory import world_path

    track = b.track
    esq = track.points + track.normal * track.width_left[:, None]
    dir_ = track.points - track.normal * track.width_right[:, None]
    cores = {"C0 (linha da IA)": "#888888", "L1": "#d62728", "L2": "#1f77b4"}
    linhas = {"C0 (linha da IA)": b.lateral_c0, **laterais}
    tr = {t.nome: t for t in b.trechos}
    paineis = [("toda a pista", None), ("C06", (tr["C06"].inicio_s + 250, tr["C06"].fim_s + 20)),
               ("C09", (tr["C09"].inicio_s, tr["C09"].fim_s + 20)), ("C10", (tr["C10"].inicio_s, tr["C10"].fim_s + 20)),
               ("a subida dos boxes (s de 3.800 a 4.050 m)", (3800.0, 4050.0))]
    fig, axes = plt.subplots(1, 5, figsize=(26, 6.5), gridspec_kw={"width_ratios": [1.4, 1, 1, 1, 1]})
    for ax, (titulo, faixa) in zip(axes, paineis):
        ax.plot(esq[:, 0], esq[:, 1], color="#bbbbbb", lw=0.8)
        ax.plot(dir_[:, 0], dir_[:, 1], color="#bbbbbb", lw=0.8)
        for nome, lat in linhas.items():
            w = world_path(track, lat)
            ax.plot(np.r_[w[:, 0], w[0, 0]], np.r_[w[:, 1], w[0, 1]], color=cores[nome], lw=0.9 if faixa is None else 1.6, label=nome)
        if faixa is not None:
            sel = (track.s >= faixa[0]) & (track.s <= faixa[1])
            pts = np.vstack([esq[sel], dir_[sel]])
            ax.set_xlim(pts[:, 0].min() - 6, pts[:, 0].max() + 6)
            ax.set_ylim(pts[:, 1].min() - 6, pts[:, 1].max() + 6)
        ax.set_aspect("equal")
        ax.set_title(titulo, fontsize=10)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Z (m)")
        ax.grid(alpha=0.25)
    axes[0].legend(fontsize=8, loc="lower left")
    fig.suptitle("Interlagos: a linha da IA (C0) e as linhas do projeto L1 e L2 (pedido 50), com as bordas do corredor do pedido 44")
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)
