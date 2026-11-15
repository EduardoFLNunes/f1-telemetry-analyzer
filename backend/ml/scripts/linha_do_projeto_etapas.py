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

    def prever_por_trecho(self, lateral: np.ndarray) -> Dict[str, np.ndarray]:
        """A diferenca contra o C0 em cada trecho, por medidor (o M-cal com o beta do trecho)."""
        K = len(self.b.trechos)
        out = {}
        for k, e in self.env.items():
            p = self.simulate(self.b.track, lateral, e).step_time_s
            d = np.bincount(self.passo_trecho, weights=p - self.base[k], minlength=K)
            out[k] = d
            if k == "M-real":
                out["M-cal"] = d * self.beta
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


# ------------------------------------------- a conferencia entre as sessoes ---

# ADR 0031, item 3: os blocos sao as trocas do registro depois do commit do ADR (3f777af4, 12/11 09:39:42).
DESDE = "2026-11-12T09:39:42"


def conferencia(args) -> int:
    """So a conferencia da troca, entre as sessoes no jogo. **Nao calcula nem mostra nenhum tempo.**

    Cada gravacao vai para o bloco da ultima troca antes dela (`registro.blocos`); em cada bloco, os papeis das
    voltas (saida, primeira lancada, as 7 que contam) e a troca que pegou: a mediana da distancia das posicoes
    das voltas que contam ate a linha da condicao, contra ate a linha original.
    """
    from datetime import datetime

    from ml.data.recordings import iter_laps
    from ml.pista_teste import ai_spline as A
    from ml.pista_teste import etapas as E
    from ml.pista_teste import linha_nova as N
    from ml.pista_teste import registro as R
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.track.geometry import load_corridor_geometry

    saida = C.raiz_saida()
    pasta = saida / "linhas"
    m47 = _ler_json(pasta / "linhas.json")
    m50 = _ler_json(pasta / "linha_do_projeto.json")
    esperado = {"C0": m47["condicoes"]["C0"]["sha256"], **{k: v["sha256"] for k, v in m50["condicoes"].items()}}
    for k in ("L1", "L2"):
        if A.sha256_arquivo(pasta / k / "fast_lane.ai") != esperado[k]:
            raise SystemExit(f"PARADO: o arquivo da {k} nao bate com o linha_do_projeto.json.")
    linhas_xz = {k: A.ler(pasta / k / "fast_lane.ai").pos[:, [0, 2]].astype(float) for k in ("C0", "L1", "L2")}
    sha_original_agora = A.sha256_arquivo(C.fast_lane_original())
    trocas = R.ler(saida / "registro.csv") if (saida / "registro.csv").exists() else []
    lista = R.blocos(trocas, datetime.fromisoformat(DESDE))
    track = load_corridor_geometry()
    sessoes = E.sessoes_da_copia()
    inicios = {s.session_id: E._inicio(s) for s in sessoes}
    atrib = R.atribuir_aos_blocos({k: v for k, v in inicios.items() if v is not None}, lista, esperado)
    bloco_da = {a["sessao"]: a for a in atrib}
    por_bloco = {}
    for sessao in sessoes:
        a = bloco_da.get(sessao.session_id)
        if a is None or a["bloco"] is None:
            continue
        laps = list(iter_laps(sessao))
        for i, lap in enumerate(laps):
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, track)
            ai = lap.frame["ai_controlled"] if "ai_controlled" in lap.frame else None
            ordem = float(lap.frame["timestamp_s"].iloc[0]) if "timestamp_s" in lap.frame else float(i)
            por_bloco.setdefault(a["bloco"], []).append({
                "sessao": sessao.session_id, "sequencia": lap.sequence, "ordem": ordem, "primeira": i == 0,
                "interrompida": i == len(laps) - 1 and alignment.coverage < E.COBERTURA_MINIMA,
                "ia_dirigiu": bool(ai is not None and ai.fillna(False).astype(bool).all()),
                "xz": aligned[["x", "z"]].to_numpy(float) if len(aligned) else np.zeros((0, 2))})
    blocos_out = []
    for b in lista:
        voltas = por_bloco.get(b.numero, [])
        objs = [R.VoltaNaCondicao(v["sessao"], v["sequencia"], v["ordem"], v["primeira"], v["interrompida"]) for v in voltas]
        R.papeis(b.condicao, objs)
        papel = {(o.sessao, o.sequencia): o.papel for o in objs}
        contam = [v for v in voltas if papel[(v["sessao"], v["sequencia"])] == "conta"]
        item = {"bloco": b.numero, "condicao": b.condicao, "troca": b.hora.isoformat(),
                "gravacoes": sorted({v["sessao"] for v in voltas}),
                "voltas_por_papel": {p: sum(papel[(v["sessao"], v["sequencia"])] == p for v in voltas)
                                     for p in ("saida", "primeira lancada", "conta", "alem das que contam", "interrompida")},
                "que_contam_com_a_ia_dirigindo": sum(v["ia_dirigiu"] for v in contam)}
        pts = [v["xz"] for v in contam if len(v["xz"])]
        if pts:
            p = np.vstack(pts)
            d_linha = float(np.median(N._projetar_na_polilinha(p, linhas_xz[b.condicao])[2]))
            d_orig = float(np.median(N._projetar_na_polilinha(p, linhas_xz["C0"])[2]))
            item.update(mediana_ate_a_linha_da_condicao_m=d_linha, mediana_ate_a_linha_original_m=d_orig,
                        troca_pegou=True if b.condicao == "C0" else bool(d_linha < d_orig))
        blocos_out.append(item)
    payload = {"pedido": 50, "parte": "D.3 entre as sessoes (sem tempos)", "commit": _cabecalho("", "", track)["commit"],
               "comando": f"python -m ml.scripts.linha_do_projeto conferencia-sessao --rotulo {args.rotulo}",
               "desde": DESDE, "original_intacto": m47["original"]["sha256"] == sha_original_agora,
               "atribuicao": [{**a, "inicio": a["inicio"].isoformat()} for a in atrib if a["bloco"] is not None],
               "gravacoes_fora_dos_blocos": sum(1 for a in atrib if a["bloco"] is None), "blocos": blocos_out}
    _json(raiz() / f"conferencia_{args.rotulo}.json", payload)
    print("original intacto:", payload["original_intacto"])
    print("blocos no registro desde", DESDE, ":", len(lista), "| gravacoes fora dos blocos:", payload["gravacoes_fora_dos_blocos"])
    for item in blocos_out:
        extra = ""
        if "troca_pegou" in item:
            extra = (f"  ate a linha da condicao {item['mediana_ate_a_linha_da_condicao_m']:.2f} m, ate a original "
                     f"{item['mediana_ate_a_linha_original_m']:.2f} m, troca pegou: {item['troca_pegou']}")
        print(f"bloco {item['bloco']} {item['condicao']}: {item['voltas_por_papel']} (IA dirigindo em "
              f"{item['que_contam_com_a_ia_dirigindo']}){extra}")
    return 0


# ------------------------------------------------------- parte E: resultado ---

VOLTA_0013_S = 84.829163


def _voltas_dos_blocos(b: Base, lista, atrib, sessoes, sectors, pit_xz):
    """Cada volta das gravacoes dos blocos, refeita pelo caminho do 47, com a validade (ADR 0029, item 5)."""
    from ml.data.recordings import iter_laps
    from ml.data.store_v2 import game_lap_time
    from ml.pista_teste import etapas as E
    from ml.pista_teste import por_trecho as PT
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.preprocessing.resampling import lap_time_from_grid, resample_lap

    track = b.track
    bloco_da = {a["sessao"]: a for a in atrib}
    por_bloco = {bl.numero: [] for bl in lista}
    for sessao in sessoes:
        a = bloco_da.get(sessao.session_id)
        if a is None or a["bloco"] is None:
            continue
        laps = list(iter_laps(sessao))
        for i, lap in enumerate(laps):
            cleaned, _ = clean_lap(lap.frame)
            aligned, alignment = align_lap(cleaned, track)
            grid = resample_lap(aligned, track, line_clock=True)
            seguinte = laps[i + 1] if i + 1 < len(laps) else None
            tempo = float(lap_time_from_grid(grid))
            v = {"sessao": sessao.session_id, "sequencia": int(lap.sequence), "volta_do_jogo": lap.lap_number,
                 "bloco": a["bloco"], "condicao": a["condicao"], "tempo_s": tempo,
                 "tempo_jogo_s": game_lap_time(lap, seguinte, track),
                 "inicio_s": float(lap.frame["timestamp_s"].iloc[0]) if "timestamp_s" in lap.frame else float(i),
                 "primeira_da_gravacao": i == 0,
                 "interrompida": i == len(laps) - 1 and alignment.coverage < E.COBERTURA_MINIMA}
            v.update(E.validade(track, sectors, lap.frame, aligned, alignment, grid, pit_xz))
            v["xz"] = aligned[["x", "z"]].to_numpy(float) if len(aligned) else np.zeros((0, 2))
            if v["valida"] and np.isfinite(tempo):
                t = PT.tempos_por_trecho(grid["elapsed_s"].to_numpy(float), track.s, tempo, b.trechos)
                v["soma_menos_tempo_s"] = PT.conferir_soma(t, tempo)
                v["trechos_s"] = t
                v["microssetores_s"] = E.tempos_por_microssetor(grid, track, sectors, tempo)
                v["canais"] = {k: (grid[k].to_numpy(float) if k in grid else None)
                               for k in ("brake", "throttle", "gear", "speed_kmh", "lateral")}
            por_bloco[a["bloco"]].append(v)
    for numero, voltas in por_bloco.items():
        cond = next(bl.condicao for bl in lista if bl.numero == numero)
        from ml.pista_teste import registro as R
        objs = [R.VoltaNaCondicao(v["sessao"], v["sequencia"], v["inicio_s"], v["primeira_da_gravacao"], v["interrompida"])
                for v in voltas]
        R.papeis(cond, objs)
        papel = {(o.sessao, o.sequencia): o.papel for o in objs}
        for v in voltas:
            v["papel"] = papel[(v["sessao"], v["sequencia"])]
        voltas.sort(key=lambda v: v["inicio_s"])
    return por_bloco


def _contam_validas(voltas):
    return [v for v in voltas if v["papel"] == "conta" and v["valida"]]


def resultado(args) -> int:
    """Parte E (ADR 0031): a conferencia, as voltas e os tempos, o veredito da meta, por trecho e os medidores."""
    from datetime import datetime

    from ml.pista_teste import ai_spline as A
    from ml.pista_teste import etapas as E
    from ml.pista_teste import linha_do_projeto as LP
    from ml.pista_teste import linha_nova as N
    from ml.pista_teste import por_trecho as PT
    from ml.pista_teste import registro as R
    from ml.track.microsectors import build_microsectors

    t0 = time.time()
    b = _base_com_c0_do_47(Base())
    track = b.track
    sectors = build_microsectors(track)
    nomes = [t.nome for t in b.trechos]
    saida = C.raiz_saida()
    pasta = saida / "linhas"
    m47 = _ler_json(pasta / "linhas.json")
    m50 = _ler_json(pasta / "linha_do_projeto.json")
    esperado = {"C0": m47["condicoes"]["C0"]["sha256"], **{k: v["sha256"] for k, v in m50["condicoes"].items()}}
    for k in ("L1", "L2"):
        if A.sha256_arquivo(pasta / k / "fast_lane.ai") != esperado[k]:
            raise SystemExit(f"PARADO: o arquivo da {k} nao bate com o linha_do_projeto.json.")
    linhas_xz = {k: A.ler(pasta / k / "fast_lane.ai").pos[:, [0, 2]].astype(float) for k in ("C0", "L1", "L2")}
    original = C.fast_lane_original()
    sha_agora = A.sha256_arquivo(original)
    copia_ai = C.pasta_do_jogo() / "content" / "tracks" / C.PISTA_COPIA / C.LAYOUT / "ai"
    pit = original.with_name("pit_lane.ai")
    pit_xz = A.ler(pit).pos[:, [0, 2]].astype(float) if pit.exists() else None
    trocas = R.ler(saida / "registro.csv")
    lista = R.blocos(trocas, datetime.fromisoformat(DESDE))
    if [bl.condicao for bl in lista] != ["C0", "L1", "C0", "L2", "C0"]:
        raise SystemExit(f"PARADO: os blocos do registro nao sao C0, L1, C0, L2, C0: {[bl.condicao for bl in lista]}")
    sessoes = E.sessoes_da_copia()
    inicios = {s.session_id: E._inicio(s) for s in sessoes}
    atrib = R.atribuir_aos_blocos({k: v for k, v in inicios.items() if v is not None}, lista, esperado)
    por_bloco = _voltas_dos_blocos(b, lista, atrib, sessoes, sectors, pit_xz)

    # E.1: a troca pegou em cada bloco?
    conferencia = {}
    for bl in lista:
        pts = [v["xz"] for v in por_bloco[bl.numero] if v["papel"] == "conta" and len(v["xz"])]
        p = np.vstack(pts) if pts else np.zeros((0, 2))
        d_linha = float(np.median(N._projetar_na_polilinha(p, linhas_xz[bl.condicao])[2])) if len(p) else None
        d_orig = float(np.median(N._projetar_na_polilinha(p, linhas_xz["C0"])[2])) if len(p) else None
        conferencia[bl.numero] = {"condicao": bl.condicao, "troca": bl.hora.isoformat(), "sha256": bl.sha256,
                                  "gravacoes": sorted({v["sessao"] for v in por_bloco[bl.numero]}),
                                  "mediana_ate_a_linha_do_bloco_m": d_linha, "mediana_ate_a_original_m": d_orig,
                                  "troca_pegou": bool(d_linha is not None and (bl.condicao == "C0" or d_linha < d_orig))}

    # E.2: as voltas validas e os tempos de cada bloco.
    resumo = {}
    for bl in lista:
        vs = por_bloco[bl.numero]
        validas = _contam_validas(vs)
        t = np.array([v["tempo_s"] for v in validas], float)
        resumo[bl.numero] = {"condicao": bl.condicao, "voltas": len(vs),
                             "papeis": {p: sum(v["papel"] == p for v in vs) for p in
                                        ("saida", "primeira lancada", "conta", "alem das que contam", "interrompida")},
                             "contam": sum(v["papel"] == "conta" for v in vs), "validas": int(t.size),
                             "motivos_das_invalidas": [{"sequencia": v["sequencia"], "motivos": v["motivos"]}
                                                       for v in vs if v["papel"] == "conta" and not v["valida"]],
                             "tempos_s": t.tolist(),
                             "melhor_s": float(t.min()) if t.size else None, "mediana_s": float(np.median(t)) if t.size else None,
                             "desvio_s": float(np.std(t, ddof=1)) if t.size > 1 else None,
                             "melhor": E.tempo_mmss(float(t.min())) if t.size else "-",
                             "mediana": E.tempo_mmss(float(np.median(t))) if t.size else "-"}

    # A.2: o veredito da meta, e os so relatados.
    vereditos = {}
    for bl in lista:
        if bl.condicao == "C0":
            continue
        antes, depois = R.vizinhos_de_c0(lista, bl.numero)
        tl = resumo[bl.numero]["tempos_s"]
        ta = resumo[antes.numero]["tempos_s"] if antes else []
        td = resumo[depois.numero]["tempos_s"] if depois else []
        v = LP.veredito_da_meta(tl, ta, td, troca_pegou=conferencia[bl.numero]["troca_pegou"])
        v["blocos"] = {"linha": bl.numero, "c0_antes": antes.numero if antes else None, "c0_depois": depois.numero if depois else None}
        v["contra_os_dois_c0_vizinhos"] = LP.diferenca_contra_os_vizinhos(tl, ta, td)
        v["contra_a_0013_s"] = (resumo[bl.numero]["melhor_s"] - VOLTA_0013_S) if resumo[bl.numero]["melhor_s"] else None
        vereditos[bl.condicao] = v

    # A deriva: o 2o e o 3o C0 contra o 1o.
    c0s = [bl.numero for bl in lista if bl.condicao == "C0"]
    deriva = {f"bloco {n} contra o bloco {c0s[0]}": E.bootstrap_diferenca(resumo[n]["tempos_s"], resumo[c0s[0]]["tempos_s"], semente=LP.SEMENTE)
              for n in c0s[1:] if resumo[n]["tempos_s"] and resumo[c0s[0]]["tempos_s"]}

    # E.3: por trecho, cada linha contra os dois C0 vizinhos, pela regra do ADR 0030.
    def matriz(numero, chave="trechos_s"):
        return np.array([v[chave] for v in _contam_validas(por_bloco[numero])], float)

    por_trecho = {}
    for bl in lista:
        if bl.condicao == "C0":
            continue
        antes, depois = R.vizinhos_de_c0(lista, bl.numero)
        x, ya, yd = matriz(bl.numero), matriz(antes.numero), matriz(depois.numero)
        ca = PT.comparar(x, ya, nomes)
        cd = PT.comparar(x, yd, nomes)
        cl = PT.classificar(ca, cd)
        por_trecho[bl.condicao] = [{"trecho": n, "mediana_s": float(np.median(x[:, j])),
                                    "c0_antes_mediana_s": float(np.median(ya[:, j])), "c0_depois_mediana_s": float(np.median(yd[:, j])),
                                    "contra_c0_antes": ca[j], "contra_c0_depois": cd[j], "regra": cl[j]}
                                   for j, n in enumerate(nomes)]

    # E.4: os medidores contra o jogo (a volta e por trecho), contra os dois C0 vizinhos juntos.
    medidores = Medidores(b)
    medicao = {}
    for bl in lista:
        if bl.condicao == "C0":
            continue
        antes, depois = R.vizinhos_de_c0(lista, bl.numero)
        lateral = np.load(raiz() / f"{bl.condicao.lower()}_lateral.npy")
        y = np.vstack([matriz(antes.numero), matriz(depois.numero)])
        x = matriz(bl.numero)
        jogo_trecho = np.median(x, axis=0) - np.median(y, axis=0)
        jogo_volta = float(np.median(x.sum(axis=1)) - np.median(y.sum(axis=1)))
        prev = medidores.prever(lateral)
        prev_trecho = medidores.prever_por_trecho(lateral)
        from scipy.stats import spearmanr
        medicao[bl.condicao] = {"jogo_volta_contra_c0_s": jogo_volta, "jogo_por_trecho_contra_c0_s": dict(zip(nomes, jogo_trecho.tolist())),
                                "medidores": {k: {"volta_contra_c0_s": prev[k]["contra_c0_s"],
                                                  "erro_s": prev[k]["contra_c0_s"] - jogo_volta,
                                                  "por_trecho_contra_c0_s": dict(zip(nomes, prev_trecho[k].tolist())),
                                                  "spearman_por_trecho": float(spearmanr(prev_trecho[k], jogo_trecho)[0])}
                                              for k in prev}}

    # A execucao da IA em cada linha (ADR 0030, item 5), para a referencia (item 11 do ADR 0031).
    execucao = {}
    for bl in lista:
        if bl.condicao == "C0":
            continue
        voltas = _contam_validas(por_bloco[bl.numero])
        execucao[bl.condicao] = {t.nome: PT.resumir_medidas([PT.medidas_da_execucao(v["canais"], track.s, track.length, t)
                                                             for v in voltas]) for t in b.trechos}

    payload = {**_cabecalho("E", "python -m ml.scripts.linha_do_projeto resultado", track),
               "conferencia_do_teste": {"desde": DESDE, "blocos": conferencia,
                                        "sha256_original_antes": m47["original"]["sha256"], "sha256_original_agora": sha_agora,
                                        "original_intacto": m47["original"]["sha256"] == sha_agora, "copia_ai_existe": copia_ai.exists(),
                                        "atribuicao": [{**a, "inicio": a["inicio"].isoformat()} for a in atrib if a["bloco"] is not None],
                                        "gravacoes_fora_dos_blocos": sum(1 for a in atrib if a["bloco"] is None)},
               "voltas": {n: [{k: v for k, v in item.items() if k not in ("xz", "canais", "microssetores_s")} for item in vs]
                          for n, vs in por_bloco.items()},
               "resumo": resumo, "vereditos": vereditos, "deriva": deriva, "por_trecho": por_trecho,
               "medidores_contra_o_jogo": medicao, "execucao": execucao,
               "a_0013": {"volta": C.VOLTA_IA, "tempo_s": VOLTA_0013_S, "tempo": E.tempo_mmss(VOLTA_0013_S)},
               "tempo_s": round(time.time() - t0, 1)}
    _json(raiz() / "resultado.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_resultado.json"), payload)
        figura_por_trecho(por_trecho, Path(str(args.handoff) + "_por_trecho.png"))
    for n, r in resumo.items():
        print(f"bloco {n} {r['condicao']}: validas {r['validas']}/{r['contam']}  melhor {r['melhor']}  mediana {r['mediana']}"
              f"  troca pegou {conferencia[n]['troca_pegou']}")
    for k, v in vereditos.items():
        print(k, v["veredito"], v.get("falta_s"), {kk: round(vv, 3) for kk, vv in (v["contra_os_dois_c0_vizinhos"] or {}).items()
                                                  if isinstance(vv, float)})
    print("deriva:", {k: round(v["diferenca_s"], 3) for k, v in deriva.items()})
    for k, rows in por_trecho.items():
        print(k, [f"{r['trecho']}:{r['regra']}" for r in rows if r["regra"] != "empate"])
    return 0


def figura_por_trecho(por_trecho: Dict[str, list], destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(len(por_trecho), 1, figsize=(12, 3.6 * len(por_trecho)), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (linha, rows) in zip(axes, por_trecho.items()):
        x = np.arange(len(rows))
        for desl, chave, cor, rotulo in ((-0.15, "contra_c0_antes", "#1f77b4", "contra o C0 antes"),
                                         (0.15, "contra_c0_depois", "#ff7f0e", "contra o C0 depois")):
            d = np.array([r[chave]["diferenca_s"] for r in rows])
            lo = np.array([r[chave]["ic95_inferior_s"] for r in rows])
            hi = np.array([r[chave]["ic95_superior_s"] for r in rows])
            sig = np.array([r[chave]["significativo_holm"] for r in rows])
            ax.errorbar(x + desl, d, yerr=[d - lo, hi - d], fmt="none", ecolor=cor, alpha=0.7)
            ax.scatter(x[sig] + desl, d[sig], color=cor, label=rotulo + " (cheio: Holm)", zorder=3)
            ax.scatter(x[~sig] + desl, d[~sig], facecolors="white", edgecolors=cor, zorder=3)
        for i, r in enumerate(rows):
            if r["regra"] != "empate":
                ax.annotate(r["regra"], (i, ax.get_ylim()[1]), ha="center", va="top", fontsize=8)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_ylabel(f"{linha} − C0 (s)\n(negativo = mais rápida)")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="lower left")
    axes[-1].set_xticks(np.arange(len(next(iter(por_trecho.values())))))
    axes[-1].set_xticklabels([r["trecho"] for r in next(iter(por_trecho.values()))], rotation=45)
    fig.suptitle("Pedido 50: cada linha do projeto contra os dois blocos de C0 vizinhos, por trecho (mediana e IC de 95%)")
    fig.tight_layout()
    fig.savefig(destino, dpi=110)
    plt.close(fig)


# ------------------------------------------------- parte E.5: a referencia ---

def referencia(args) -> int:
    """ADR 0031, item 11: a linha que atingiu a meta vira a referencia de todos os trechos (com a marca e a execucao)."""
    import shutil

    from ml.pista_teste import ai_spline as A
    from ml.pista_teste import por_trecho as PT

    b = Base()
    track = b.track
    res = _ler_json(raiz() / "resultado.json")
    atingiram = [k for k, v in res["vereditos"].items() if v["veredito"] == "meta atingida"]
    if not atingiram:
        print("nenhuma linha atingiu a meta: a referencia nao muda (ADR 0031, item 11).")
        return 0
    linha = min(atingiram, key=lambda k: res["vereditos"][k]["melhor_s"]["linha"])
    numero = res["vereditos"][linha]["blocos"]["linha"]
    data = res["conferencia_do_teste"]["blocos"][str(numero)]["troca"][:10]
    marca = PT.MARCA_DA_LINHA_DO_PROJETO + data
    pasta = _repo() / "data" / "modelo1_por_trecho"
    arquivo = pasta / "referencia_por_trecho.json"
    copia = pasta / "referencia_por_trecho_pedido49.json"
    if not copia.exists():
        shutil.copy2(arquivo, copia)
    anterior = _ler_json(copia)
    PT.conferir_formato_da_referencia(anterior)
    lateral = np.load(raiz() / f"{linha.lower()}_lateral.npy")
    voltas = [v for v in res["voltas"][str(numero)] if v["papel"] == "conta" and v["valida"]]
    tempos = np.array([v["trechos_s"] for v in voltas], float)
    trechos = []
    for j, t in enumerate(anterior["trechos"]):
        idx = np.rint(np.mod(np.asarray(t["linha_de_referencia"]["s"], float), track.length) / track.step).astype(int) % track.size
        pontos = {k: float(lateral[int(np.rint(np.mod(s, track.length) / track.step)) % track.size])
                  for k, s in t["pontos_de_linha_s"].items()}
        x = tempos[:, j]
        novo = dict(t)
        novo["linha_de_referencia"] = {
            "linha": linha, "marca": marca,
            "descricao": f"a {linha}, a linha do projeto do pedido 50 (ADR 0031), que atingiu a meta no teste no jogo",
            "lateral_nos_pontos_de_linha_m": pontos, "s": t["linha_de_referencia"]["s"], "lateral_m": lateral[idx].tolist()}
        novo["execucao_da_ia"] = {"linha": linha, "voltas": int(len(x)), "bloco": numero,
                                  "medidas": res["execucao"][linha][t["trecho"]],
                                  "tempo_do_trecho": {"mediana_s": float(np.median(x)), "desvio_s": float(np.std(x, ddof=1)),
                                                      "iqr_s": float(np.subtract(*np.percentile(x, [75, 25])))}}
        novo["referencia_anterior"] = {"linha": t["linha_de_referencia"]["linha"], "descricao": t["linha_de_referencia"]["descricao"],
                                       "lateral_nos_pontos_de_linha_m": t["linha_de_referencia"]["lateral_nos_pontos_de_linha_m"],
                                       "tempo_do_trecho": t["execucao_da_ia"]["tempo_do_trecho"], "pedido": 49}
        novo["provisorio"] = {**t["provisorio"], "nota_do_pedido_50": "calculado sobre a execucao da IA no C0 (pedido 49), nao refeito"}
        trechos.append(novo)
    manifesto = _ler_json(C.raiz_saida() / "linhas" / "linha_do_projeto.json")
    payload = {**anterior, "pedido": 50, "adr": "0030 e 0031", "commit": _cabecalho("", "", track)["commit"],
               "comando": "python -m ml.scripts.linha_do_projeto referencia",
               "aviso": ("Referencia por trecho do Modelo 1 (pedidos 49 e 50; ADR 0030 e 0031). O coach nao le este arquivo. "
                         f"A referencia de todo trecho e a {linha}, a linha do projeto que atingiu a meta do ADR 0031 em {data}; "
                         "a anterior (a linha da IA, C0) fica em 'referencia_anterior'. As candidatas do pedido 49 continuam "
                         "'a validar no jogo', e as propostas provisorias dependem da confirmacao do Eduardo."),
               "arquivos": {**anterior["arquivos"], "linha_do_projeto": {"linha": linha, "sha256_do_fast_lane": manifesto["condicoes"][linha]["sha256"],
                                                                         "resultado_do_pedido_50": str(raiz() / "resultado.json")}},
               "trechos": trechos}
    PT.conferir_formato_da_referencia(payload, linha=linha)
    _json(arquivo, payload)
    resumo = {**payload, "trechos": [{k: (v if k != "linha_de_referencia" else {kk: vv for kk, vv in v.items() if kk not in ("s", "lateral_m")})
                                      for k, v in t.items()} for t in trechos]}
    PT.conferir_formato_da_referencia(resumo, com_lateral=False, linha=linha)
    if args.handoff:
        _json(Path(str(args.handoff) + "_referencia.json"), resumo)
    print(f"a referencia de todos os trechos agora e a {linha} ({marca}); a do pedido 49 ficou em {copia.name}")
    return 0
