"""O Modelo 1 por trecho (pedido 49; ADR 0030): a conta por trecho (Parte B).

    python -m ml.scripts.modelo1_por_trecho [--handoff PREFIXO]

Le, sem escrever nada fora de `data/modelo1_por_trecho/`:
* as voltas que contam e sao validas no `_resultado.json` do pedido 47, refeitas
  das gravacoes da copia da pista (na pasta do app instalado);
* as 136 voltas `humano` do pedido 44 (`data/ml/retreino_lstm/`);
* as linhas do 47 em `data/pista_teste/linhas/` (conferidas pelo sha256).

Sai `data/modelo1_por_trecho/conta.json` (tudo, incluindo o que a Parte C usa) e
`tabelas.md`; com `--handoff`, tambem `<PREFIXO>_conta.json` (sem as laterais
ponto a ponto) e `<PREFIXO>_por_trecho.png`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml import config  # noqa: E402
from ml.pista_teste import ai_spline as A  # noqa: E402
from ml.pista_teste import condicoes as C  # noqa: E402
from ml.pista_teste import por_trecho as PT  # noqa: E402
from ml.pista_teste import registro as R  # noqa: E402

RESULTADO_47 = Path("docs") / "handoff" / "2026-11-07_47_linha-gerada-no-jogo_resultado.json"
CONDICOES_DO_TESTE = ("C0", "C1", "C2", "C3", "C4", R.C0_FINAL)
LINHAS = ("C0", "C1", "C2", "C3", "C4")
SESSAO_2410 = "2026-10-24"


def raiz_saida() -> Path:
    return config.repo_root() / "data" / "modelo1_por_trecho"


def _padrao(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def indice(track, s: float) -> int:
    """O ponto da grade mais perto de `s` (os limites das curvas sao pontos da grade)."""
    return int(np.rint(np.mod(float(s), track.length) / track.step)) % track.size


# ----------------------------------------------------------------- leitura ---

def carregar_linhas(track) -> Dict[str, dict]:
    pasta = C.raiz_saida() / "linhas"
    manifesto = json.loads((pasta / "linhas.json").read_text(encoding="utf-8"))
    out = {}
    for nome in LINHAS:
        arquivo = pasta / nome / "fast_lane.ai"
        sha = A.sha256_arquivo(arquivo)
        if sha != manifesto["condicoes"][nome]["sha256"]:
            raise SystemExit(f"PARADO: o arquivo da {nome} nao bate com o linhas.json do pedido 47.")
        sp = A.ler(arquivo)
        xz = sp.pos[:, [0, 2]].astype(float)
        out[nome] = {"arquivo": arquivo, "sha256": sha, "spline": sp, "xz": xz,
                     "lateral": C.lateral_da_linha(track, xz)}
    if out["C0"]["sha256"] != manifesto["original"]["sha256"]:
        raise SystemExit("PARADO: o arquivo C0 nao e a copia do original.")
    return out


def carregar_voltas_do_teste(track, resultado: dict) -> Dict[str, object]:
    from ml.data.recordings import iter_laps, list_all_sessions
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.preprocessing.resampling import lap_time_from_grid, resample_lap

    queridas = {(v["sessao"], int(v["sequencia"])): v for v in resultado["voltas"]
                if v.get("papel") == "conta" and v.get("valida")}
    sessoes = list_all_sessions(track_prefixes=(C.PISTA_COPIA,), incluir_pistas_de_teste=True)
    por_condicao: Dict[str, List[dict]] = {c: [] for c in CONDICOES_DO_TESTE}
    arquivos = []
    achadas = set()
    for sessao in sessoes:
        if not any(k[0] == sessao.session_id for k in queridas):
            continue
        for f in sorted(p for p in sessao.directory.iterdir() if p.is_file()):
            arquivos.append({"sessao": sessao.session_id, "arquivo": f.name, "bytes": f.stat().st_size, "sha256": _sha256(f)})
        for lap in iter_laps(sessao):
            chave = (sessao.session_id, int(lap.sequence))
            if chave not in queridas:
                continue
            v = queridas[chave]
            cleaned, _ = clean_lap(lap.frame)
            aligned, _ = align_lap(cleaned, track)
            grid = resample_lap(aligned, track, line_clock=True)
            tempo = float(lap_time_from_grid(grid))
            if not abs(tempo - float(v["tempo_s"])) <= PT.TEMPO_REFEITO_TOLERANCIA_S:
                raise SystemExit(f"PARADO: a volta {chave} refeita da {tempo:.4f} s e o 47 tinha {v['tempo_s']:.4f} s.")
            por_condicao[v["condicao"]].append({
                "id": f"{sessao.session_id}#{int(lap.sequence):04d}", "sessao": sessao.session_id,
                "sequencia": int(lap.sequence), "tempo_s": tempo, "tempo_47_s": float(v["tempo_s"]),
                "tempo_jogo_s": v.get("tempo_jogo_s"), "inicio_s": float(v["inicio_s"]),
                "canais": {k: (grid[k].to_numpy(float) if k in grid else None)
                           for k in ("brake", "throttle", "gear", "speed_kmh", "lateral")},
                "elapsed": grid["elapsed_s"].to_numpy(float), "grid": grid})
            achadas.add(chave)
    faltam = sorted(set(queridas) - achadas)
    if faltam:
        raise SystemExit(f"PARADO: voltas do 47 nao achadas nas gravacoes: {faltam}")
    for lista in por_condicao.values():
        lista.sort(key=lambda v: v["inicio_s"])
    return {"voltas": por_condicao, "arquivos": arquivos}


def carregar_voltas_humanas(track) -> Dict[str, object]:
    from ml.scripts import retreino_lstm as RL

    src = RL.load_prepared(track)
    tabela = src.table
    humanas = tabela[tabela["origem"] == "humano"].sort_values("lap_id")
    frame = src.store.frame
    frame = frame[frame["lap_id"].isin(set(humanas["lap_id"]))].sort_values(["lap_id", "grid_index"])
    voltas = []
    sessao = dict(zip(humanas["lap_id"], humanas["sessao"]))
    for lap_id, g in frame.groupby("lap_id", sort=True):
        if len(g) != track.size or not (g["grid_index"].to_numpy() == np.arange(track.size)).all():
            raise SystemExit(f"PARADO: a volta {lap_id} nao esta na grade inteira.")
        voltas.append({"id": lap_id, "sessao": sessao[lap_id], "tempo_s": float(g["lap_time_s"].iloc[0]),
                       "elapsed": g["elapsed_s"].to_numpy(float),
                       "canais": {k: (g[k].to_numpy(float) if k in g else None)
                                  for k in ("brake", "throttle", "gear", "speed_kmh", "lateral")}})
    raiz = RL.root()
    arquivos = [{"arquivo": str(raiz / n), "sha256": _sha256(raiz / n)} for n in ("voltas.parquet", "voltas_tabela.parquet", "fontes.json")]
    return {"voltas": voltas, "arquivos": arquivos}


# ------------------------------------------------------------------- contas ---

def tempos_das_voltas(voltas: List[dict], track, trechos, referencia: str) -> np.ndarray:
    linhas = []
    for v in voltas:
        t = PT.tempos_por_trecho(v["elapsed"], track.s, v["tempo_s"], trechos)
        try:
            v["soma_menos_tempo_s"] = PT.conferir_soma(t, v[referencia])
        except ValueError as exc:
            raise SystemExit(f"PARADO: a volta {v['id']}: {exc}")
        v["tempos_por_trecho_s"] = t
        linhas.append(t)
    return np.array(linhas, float)


def resumo_de_tempos(m: np.ndarray, nomes) -> List[dict]:
    out = []
    for j, nome in enumerate(nomes):
        x = m[:, j]
        out.append({"trecho": nome, "voltas": int(len(x)), "mediana_s": float(np.median(x)), "melhor_s": float(x.min()),
                    "desvio_s": float(np.std(x, ddof=1)) if len(x) > 1 else None,
                    "iqr_s": float(np.subtract(*np.percentile(x, [75, 25]))) if len(x) > 1 else None})
    return out


def medidas_por_condicao(voltas: List[dict], track, trechos) -> Dict[str, object]:
    por_trecho = []
    for t in trechos:
        lista = [PT.medidas_da_execucao(v["canais"], track.s, track.length, t) for v in voltas]
        por_trecho.append({"trecho": t.nome, "resumo": PT.resumir_medidas(lista), "por_volta": lista})
    return por_trecho


def dicas_do_arquivo(linha: dict, estacao: np.ndarray, track, trechos) -> List[dict]:
    """ADR 0030, item 6: o que os campos `freio` e `velocidade` do arquivo dizem em cada trecho."""
    sp = linha["spline"]
    freio = sp.campo("freio").astype(float)
    vel = sp.campo("velocidade").astype(float) * 3.6
    s = np.mod(estacao, track.length)
    ordem = np.argsort(s, kind="stable")
    s_o, f_o, v_o = s[ordem], freio[ordem], vel[ordem]
    out = []
    for t in trechos:
        sel = np.flatnonzero((s_o >= t.inicio_s - 1e-6) & (s_o < t.fim_s - 1e-6))
        if not sel.size:
            out.append({"trecho": t.nome, "freio_inicio_s": "sem dados", "velocidade_minima_kmh": "sem dados"})
            continue
        ate = int(np.searchsorted(s_o[sel], float(t.apice_s) + 1e-6)) - 1 if t.tem_curva else len(sel) - 1
        ate = int(np.clip(ate, 0, len(sel) - 1))
        i0 = PT.inicio_da_frenagem(f_o, sel, ate)
        k = int(np.argmin(v_o[sel]))
        out.append({"trecho": t.nome, "freio_inicio_s": float(s_o[i0]) if i0 is not None else None,
                    "velocidade_minima_kmh": float(v_o[sel][k]), "velocidade_minima_s": float(s_o[sel][k])})
    return out


def _mediana(resumo: dict, nome: str):
    m = resumo[nome]["mediana"]
    return m if isinstance(m, (int, float)) else None


def comparacao_completa(m: Dict[str, np.ndarray], nomes) -> Dict[str, object]:
    comp = {}
    for x in ("C1", "C2", "C3", "C4"):
        comp[f"{x} contra C0"] = PT.comparar(m[x], m["C0"], nomes)
        comp[f"{x} contra C0 final"] = PT.comparar(m[x], m[R.C0_FINAL], nomes)
    comp["C0 final contra C0"] = PT.comparar(m[R.C0_FINAL], m["C0"], nomes)
    comp["C2 contra C3"] = PT.comparar(m["C2"], m["C3"], nomes)
    comp["C2 contra C4"] = PT.comparar(m["C2"], m["C4"], nomes)
    return comp


def hipoteses(teste, linhas, track, trechos, sectors, medidas, estacao) -> Dict[str, object]:
    from scipy.stats import spearmanr
    from ml.pista_teste.etapas import tempos_por_microssetor

    micro = {}
    for c in LINHAS:
        micro[c] = np.array([tempos_por_microssetor(v["grid"], track, sectors, v["tempo_s"]) for v in teste[c]], float)
    perda = {c: np.median(micro[c], axis=0) - np.median(micro["C0"], axis=0) for c in LINHAS if c != "C0"}
    rug_pontos, rug_micro = {}, {}
    for c in LINHAS:
        sp = linhas[c]["spline"]
        kappa = PT.curvatura_do_arquivo(sp.campo("raio"), sp.campo("direcao"))
        rug_pontos[c] = PT.rugosidade(kappa, estacao, track.length)
        rug_micro[c] = PT.media_por_microssetor(rug_pontos[c], estacao, sectors.edges_s, track.length)
    afast = {c: PT.media_por_microssetor(np.abs(linhas[c]["lateral"] - linhas["C0"]["lateral"]), track.s,
                                         sectors.edges_s, track.length) for c in LINHAS}
    corr = {}
    for c in ("C1", "C2", "C3", "C4"):
        r1 = spearmanr(perda[c], rug_micro[c] - rug_micro["C0"])
        r2 = spearmanr(perda[c], afast[c])
        corr[c] = {"perda_total_microssetores_s": float(perda[c].sum()),
                   "rho_com_a_diferenca_de_rugosidade": float(r1.correlation), "p_rugosidade": float(r1.pvalue),
                   "rho_com_o_afastamento_lateral": float(r2.correlation), "p_afastamento": float(r2.pvalue),
                   "rugosidade_media_1_m": float(np.mean(rug_pontos[c])),
                   "afastamento_lateral_medio_m": float(np.mean(np.abs(linhas[c]["lateral"] - linhas["C0"]["lateral"])))}
    corr["C0"] = {"rugosidade_media_1_m": float(np.mean(rug_pontos["C0"]))}

    # Leitura acrescentada depois de ver os dados (so relatada, fora do ADR 0030): o menor `raio` do arquivo em
    # cada trecho, porque a IA freia na C1 e na C2 no trecho C14->linha, onde as dicas do arquivo nao tem freio.
    raio_minimo = []
    for t in trechos:
        sel = (estacao >= t.inicio_s - 1e-6) & (estacao < t.fim_s - 1e-6)
        item = {"trecho": t.nome}
        for c in LINHAS:
            r = linhas[c]["spline"].campo("raio").astype(float)[sel]
            k = int(np.argmin(r))
            item[c] = {"raio_minimo_m": float(r[k]), "s": float(estacao[sel][k])}
        raio_minimo.append(item)

    dicas_c0 = dicas_do_arquivo(linhas["C0"], estacao, track, trechos)
    dicas_c1 = dicas_do_arquivo(linhas["C1"], estacao, track, trechos)
    tabela = []
    for j, t in enumerate(trechos):
        r0, r1 = medidas["C0"][j]["resumo"], medidas["C1"][j]["resumo"]
        f0, f1 = _mediana(r0, "frenagem_inicio_s"), _mediana(r1, "frenagem_inicio_s")
        v0, v1 = _mediana(r0, "velocidade_minima_kmh"), _mediana(r1, "velocidade_minima_kmh")
        tabela.append({
            "trecho": t.nome,
            "ia_c0_frenagem_inicio_s": f0, "ia_c1_frenagem_inicio_s": f1,
            "frenagem_c1_menos_c0_m": (f1 - f0) if (f0 is not None and f1 is not None) else None,
            "frenagem_no_mesmo_lugar": (abs(f1 - f0) < PT.MESMO_LUGAR_M) if (f0 is not None and f1 is not None) else None,
            "ia_c0_minima_kmh": v0, "ia_c1_minima_kmh": v1,
            "minima_c1_menos_c0_kmh": (v1 - v0) if (v0 is not None and v1 is not None) else None,
            "dica_c0": dicas_c0[j], "dica_c1": dicas_c1[j],
            "dicas_iguais_nas_duas": dicas_c0[j] == dicas_c1[j]})
    return {"dicas": tabela, "curvatura": corr, "raio_minimo_por_trecho_depois_de_ver_os_dados": raio_minimo,
            "por_microssetor": {"perda_s": {c: perda[c] for c in perda}, "rugosidade_1_m": rug_micro,
                                "afastamento_lateral_m": afast}}


def minhas_contas(humanas: List[dict], m_c0: np.ndarray, med_c0, linhas, track, trechos) -> Dict[str, object]:
    nomes = [t.nome for t in trechos]
    tempos = tempos_das_voltas(humanas, track, trechos, "tempo_s")
    mediana_c0 = np.median(m_c0, axis=0)
    out = {"voltas": len(humanas), "voltas_2410": int(sum(v["sessao"] == SESSAO_2410 for v in humanas))}
    for rotulo, sel in (("todas", np.ones(len(humanas), bool)),
                        ("24/10", np.array([v["sessao"] == SESSAO_2410 for v in humanas]))):
        sub = tempos[sel]
        out[f"tempos_{rotulo}"] = [{"trecho": n, "voltas": int(sel.sum()), "mediana_s": float(np.median(sub[:, j])),
                                     "melhor_s": float(sub[:, j].min()),
                                     "mediana_menos_c0_s": float(np.median(sub[:, j]) - mediana_c0[j]),
                                     "melhor_menos_c0_s": float(sub[:, j].min() - mediana_c0[j])}
                                    for j, n in enumerate(nomes)]
        out[f"volta_{rotulo}"] = {"mediana_s": float(np.median(sub.sum(axis=1))), "melhor_s": float(sub.sum(axis=1).min())}
    medidas = medidas_por_condicao(humanas, track, trechos)
    laterais = np.array([v["canais"]["lateral"] for v in humanas], float)
    lat_ia = linhas["C0"]["lateral"]
    linha = []
    for j, t in enumerate(trechos):
        rampas = [PT.rampa_do_freio(v["canais"]["brake"], track.s, track.length, t) for v in humanas]
        rampas = [r for r in rampas if r is not None]
        rampa = float(np.median(rampas)) if len(rampas) >= PT.RAMPA_MINIMO_DE_VOLTAS else "sem dados"
        pontos = {k: indice(track, s) for k, s in t.pontos_de_linha().items()}
        lim = PT.limite_de_linha(laterais, list(pontos.values()))
        acima = PT.acima_do_limite(lim["mediana"], lim["limite"], lat_ia[list(pontos.values())])
        idx = t.indices(track.s, track.length)
        lim_t = PT.limite_de_linha(laterais, idx)
        acima_t = PT.acima_do_limite(lim_t["mediana"], lim_t["limite"], lat_ia[idx])
        ia_inicio = _mediana(med_c0[j]["resumo"], "frenagem_inicio_s")
        linha.append({
            "trecho": t.nome,
            "rampa_do_freio_m": rampa, "voltas_com_frenagem": len(rampas),
            "frenagem_traduzida_s": (ia_inicio - rampa) if (ia_inicio is not None and isinstance(rampa, float)) else "sem dados",
            "ia_frenagem_inicio_s": ia_inicio,
            "pontos": {k: {"s": float(track.s[i]), "minha_mediana_m": float(lim["mediana"][n]), "limite_m": float(lim["limite"][n]),
                           "linha_da_ia_m": float(lat_ia[i]), "distancia_m": float(abs(lim["mediana"][n] - lat_ia[i])),
                           "acima_do_limite": bool(acima[n])}
                       for n, (k, i) in enumerate(pontos.items())},
            "fracao_do_trecho_acima_do_limite": float(np.mean(acima_t)),
            "metros_acima_do_limite": float(np.sum(acima_t) * track.step)})
    return {"tempos": out, "medidas": medidas, "linha": linha, "matriz_tempos": tempos}


def teto(m: Dict[str, np.ndarray], nomes) -> Dict[str, object]:
    meds = {c: np.median(m[c], axis=0) for c in LINHAS}
    escolha, soma = [], 0.0
    for j, n in enumerate(nomes):
        c = min(LINHAS, key=lambda c: meds[c][j])
        escolha.append({"trecho": n, "linha": c, "mediana_s": float(meds[c][j]), "ganho_contra_c0_s": float(meds[c][j] - meds["C0"][j])})
        soma += meds[c][j]
    return {"aviso": "teto, nao previsao: o ganho de um trecho muda a entrada do seguinte, e escolher depois de ver favorece o acaso",
            "por_trecho": escolha, "soma_s": float(soma), "soma_das_medianas_do_c0_s": float(meds["C0"].sum()),
            "teto_menos_c0_s": float(soma - meds["C0"].sum())}


# ------------------------------------------------------------------ figura ---

def figura(comp: Dict[str, list], nomes, destino: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = [("C1 contra C0", "#1f77b4"), ("C2 contra C0", "#2ca02c"), ("C3 contra C0", "#d62728"),
              ("C4 contra C0", "#ff7f0e"), ("C0 final contra C0", "#7f7f7f")]
    x = np.arange(len(nomes))
    fig, ax = plt.subplots(figsize=(15, 6.5))
    for k, (chave, cor) in enumerate(series):
        dx = (k - 2) * 0.15
        for j, d in enumerate(comp[chave]):
            y, lo, hi = d["diferenca_s"], d["ic95_inferior_s"], d["ic95_superior_s"]
            cheio = d["sentido"] != "nenhum"
            ax.errorbar(x[j] + dx, y, yerr=[[y - lo], [hi - y]], fmt="o", color=cor, ms=6 if cheio else 5,
                        mfc=cor if cheio else "white", capsize=2, lw=1.1,
                        label=chave.replace(" contra C0", "") if j == 0 else None)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(nomes)
    ax.set_ylabel("diferença das medianas contra o C0 (s)")
    ax.set_title("Pedido 49 (ADR 0030): cada trecho contra o C0, com o IC de 95% (bootstrap, semente 49).\n"
                 "Marcador cheio: significativo no Holm contra o C0 (permutação exata da diferença das médias).", fontsize=10)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=5, loc="upper left")
    fig.tight_layout()
    fig.savefig(destino, dpi=120)
    plt.close(fig)


# ----------------------------------------------------------------- tabelas ---

def _n(v, casas=3, sinal=False):
    if v is None:
        return "-"
    if isinstance(v, str):
        return v
    txt = f"{v:+.{casas}f}" if sinal else f"{v:.{casas}f}"
    return txt.replace(".", ",")


def _trocas(r: dict, chave: str = "trocas_sem_neutro") -> str:
    tr = r[chave]
    seq = tr.get("sequencia_mais_comum")
    if not isinstance(seq, list):
        return str(seq)
    if not seq:
        return f"nenhuma ({tr['voltas_com_ela']}/{r['voltas']})"
    return ", ".join(f"{a}: {_n(s, 0)}" for a, s in zip(seq, tr["s_mediano"])) + f" ({tr['voltas_com_ela']}/{r['voltas']})"


def tabelas(payload: dict) -> str:
    nomes = payload["nomes_dos_trechos"]
    linhas = []
    linhas.append("## B.1 O tempo por trecho (mediana, desvio) e a diferença contra o C0\n")
    cab = "| trecho | " + " | ".join(f"{c} mediana (desvio)" for c in CONDICOES_DO_TESTE) + " |"
    linhas += [cab, "|" + "---|" * (len(CONDICOES_DO_TESTE) + 1)]
    for j, n in enumerate(nomes):
        cel = [f"{_n(payload['tempos'][c][j]['mediana_s'])} ({_n(payload['tempos'][c][j]['desvio_s'])})" for c in CONDICOES_DO_TESTE]
        linhas.append(f"| {n} | " + " | ".join(cel) + " |")
    for x in ("C1", "C2", "C3", "C4"):
        linhas.append(f"\n### {x}\n")
        linhas.append("| trecho | contra C0 (IC 95%) | p | Holm | contra C0 final (IC 95%) | p | Holm | regra |")
        linhas.append("|---|---|---|---|---|---|---|---|")
        a, b = payload["comparacoes"][f"{x} contra C0"], payload["comparacoes"][f"{x} contra C0 final"]
        for j, n in enumerate(nomes):
            linhas.append(f"| {n} | {_n(a[j]['diferenca_s'], sinal=True)} ({_n(a[j]['ic95_inferior_s'], sinal=True)} a {_n(a[j]['ic95_superior_s'], sinal=True)}) "
                          f"| {_n(a[j]['p_permutacao'], 4)} | {a[j]['sentido']} "
                          f"| {_n(b[j]['diferenca_s'], sinal=True)} ({_n(b[j]['ic95_inferior_s'], sinal=True)} a {_n(b[j]['ic95_superior_s'], sinal=True)}) "
                          f"| {_n(b[j]['p_permutacao'], 4)} | {b[j]['sentido']} | **{payload['classificacao'][x][j]}** |")
    for chave in ("C0 final contra C0", "C2 contra C3", "C2 contra C4"):
        linhas.append(f"\n### {chave} (só relatado)\n")
        linhas.append("| trecho | diferença (IC 95%) | p | Holm |")
        linhas.append("|---|---|---|---|")
        for d in payload["comparacoes"][chave]:
            linhas.append(f"| {d['trecho']} | {_n(d['diferenca_s'], sinal=True)} ({_n(d['ic95_inferior_s'], sinal=True)} a "
                          f"{_n(d['ic95_superior_s'], sinal=True)}) | {_n(d['p_permutacao'], 4)} | {d['sentido']} |")
    linhas.append("\n## B.4 A execução da IA por trecho (medianas)\n")
    linhas.append("A marcha e as trocas estão sem o neutro da troca (leitura acrescentada depois de ver os dados; a marcha mínima "
                  "registrada, com o neutro, sai 0 sempre que há troca e fica no `_conta.json`).\n")
    linhas.append("| trecho | condição | início da frenagem (m; voltas) | freio máx. | até o ápice (m) | mínima (km/h) | onde (m) | marcha mín. | trocas (mais comum: s mediano; voltas) | retomada (m; voltas) |")
    linhas.append("|---|---|---|---|---|---|---|---|---|---|")
    for j, n in enumerate(nomes):
        for c in CONDICOES_DO_TESTE:
            r = payload["execucao"][c][j]["resumo"]
            linhas.append(f"| {n} | {c} | {_n(r['frenagem_inicio_s']['mediana'], 1)} ({r['frenagem_inicio_s']['voltas_com_a_medida']}) "
                          f"| {_n(r['freio_maximo']['mediana'], 2)} | {_n(r['frenagem_ate_o_apice_m']['mediana'], 1)} "
                          f"| {_n(r['velocidade_minima_kmh']['mediana'], 1)} | {_n(r['velocidade_minima_s']['mediana'], 1)} "
                          f"| {_n(r['marcha_minima_sem_neutro']['mediana'], 0)} | {_trocas(r)} | {_n(r['retomada_s']['mediana'], 1)} ({r['retomada_s']['voltas_com_a_medida']}) |")
    linhas.append("\n## B.3 As minhas voltas por trecho\n")
    for rot in ("todas", "24/10"):
        linhas.append(f"\n### {rot}\n")
        linhas.append("| trecho | voltas | mediana | melhor | mediana − C0 | melhor − C0 |")
        linhas.append("|---|---|---|---|---|---|")
        for r in payload["eduardo"]["tempos"][f"tempos_{rot}"]:
            linhas.append(f"| {r['trecho']} | {r['voltas']} | {_n(r['mediana_s'])} | {_n(r['melhor_s'])} | {_n(r['mediana_menos_c0_s'], sinal=True)} | {_n(r['melhor_menos_c0_s'], sinal=True)} |")
    linhas.append("\n### Linha (distância à linha da IA e o limite, m) e as propostas provisórias\n")
    linhas.append("| trecho | entrada: dist. / limite | ápice: dist. / limite | saída: dist. / limite | fração acima | rampa (m; voltas) | frenagem IA (m) | traduzida (m) |")
    linhas.append("|---|---|---|---|---|---|---|---|")
    for r in payload["eduardo"]["linha"]:
        p = r["pontos"]
        cel = [f"{_n(p[k]['distancia_m'], 2)} / {_n(p[k]['limite_m'], 2)}{' **acima**' if p[k]['acima_do_limite'] else ''}" for k in ("entrada", "apice", "saida")]
        linhas.append(f"| {r['trecho']} | " + " | ".join(cel) + f" | {_n(r['fracao_do_trecho_acima_do_limite'], 2)} | {_n(r['rampa_do_freio_m'], 1)} ({r['voltas_com_frenagem']}) "
                      f"| {_n(r['ia_frenagem_inicio_s'], 1)} | {_n(r['frenagem_traduzida_s'], 1)} |")
    linhas.append("\n### Execução: as minhas medianas contra as da IA no C0\n")
    linhas.append("| trecho | frenagem eu / IA (m) | freio máx. eu / IA | mínima eu / IA (km/h) | onde eu / IA (m) | marcha mín. sem neutro eu / IA | retomada eu / IA (m) |")
    linhas.append("|---|---|---|---|---|---|---|")
    for j, n in enumerate(nomes):
        e, i = payload["eduardo"]["execucao"][j]["resumo"], payload["execucao"]["C0"][j]["resumo"]
        def par(k, casas):
            return f"{_n(e[k]['mediana'], casas)} / {_n(i[k]['mediana'], casas)}"
        linhas.append(f"| {n} | {par('frenagem_inicio_s', 1)} | {par('freio_maximo', 2)} | {par('velocidade_minima_kmh', 1)} | {par('velocidade_minima_s', 1)} "
                      f"| {par('marcha_minima_sem_neutro', 0)} | {par('retomada_s', 1)} |")
    linhas.append("\n## B.5 As hipóteses dos 2,1 s\n")
    linhas.append("| trecho | frenagem IA C0 / C1 (m) | C1 − C0 (m) | no mesmo lugar | dica do arquivo: freio em (m) | mínima IA C0 / C1 (km/h) | dica: mínima (km/h) em (m) |")
    linhas.append("|---|---|---|---|---|---|---|")
    for d in payload["hipoteses"]["dicas"]:
        dc = d["dica_c0"]
        linhas.append(f"| {d['trecho']} | {_n(d['ia_c0_frenagem_inicio_s'], 1)} / {_n(d['ia_c1_frenagem_inicio_s'], 1)} | {_n(d['frenagem_c1_menos_c0_m'], 1, True)} "
                      f"| {d['frenagem_no_mesmo_lugar']} | {_n(dc.get('freio_inicio_s'), 1)} | {_n(d['ia_c0_minima_kmh'], 1)} / {_n(d['ia_c1_minima_kmh'], 1)} "
                      f"| {_n(dc.get('velocidade_minima_kmh'), 1)} em {_n(dc.get('velocidade_minima_s'), 1)} |")
    linhas.append("\n| linha | perda nos microssetores (s) | ρ com a rugosidade (p) | ρ com o afastamento (p) | rugosidade média (1/m) | afastamento médio (m) |")
    linhas.append("|---|---|---|---|---|---|")
    for c in ("C1", "C2", "C3", "C4"):
        h = payload["hipoteses"]["curvatura"][c]
        linhas.append(f"| {c} | {_n(h['perda_total_microssetores_s'], 3, True)} | {_n(h['rho_com_a_diferenca_de_rugosidade'], 2, True)} ({_n(h['p_rugosidade'], 4)}) "
                      f"| {_n(h['rho_com_o_afastamento_lateral'], 2, True)} ({_n(h['p_afastamento'], 4)}) | {h['rugosidade_media_1_m']:.2e} | {_n(h['afastamento_lateral_medio_m'], 2)} |")
    linhas.append(f"| C0 | - | - | - | {payload['hipoteses']['curvatura']['C0']['rugosidade_media_1_m']:.2e} | - |")
    linhas.append("\n### O menor raio do arquivo por trecho (m, e onde; leitura acrescentada depois de ver os dados)\n")
    linhas.append("| trecho | " + " | ".join(LINHAS) + " |")
    linhas.append("|" + "---|" * (len(LINHAS) + 1))
    for r in payload["hipoteses"]["raio_minimo_por_trecho_depois_de_ver_os_dados"]:
        linhas.append(f"| {r['trecho']} | " + " | ".join(f"{_n(r[c]['raio_minimo_m'], 0)} em {_n(r[c]['s'], 0)}" for c in LINHAS) + " |")
    t = payload["teto"]
    linhas.append("\n## B.6 O teto da referência por trecho (só relatado)\n")
    linhas.append("| trecho | linha mais rápida | mediana | contra o C0 |")
    linhas.append("|---|---|---|---|")
    for r in t["por_trecho"]:
        linhas.append(f"| {r['trecho']} | {r['linha']} | {_n(r['mediana_s'])} | {_n(r['ganho_contra_c0_s'], 3, True)} |")
    linhas.append(f"\nSoma: {_n(t['soma_s'])} s contra {_n(t['soma_das_medianas_do_c0_s'])} s das medianas do C0 ({_n(t['teto_menos_c0_s'], 3, True)} s).")
    return "\n".join(linhas) + "\n"


# -------------------------------------------------------------------- main ---

def main(argv=None) -> int:
    from ml.data.store_v2 import git_commit
    from ml.pista_teste import linha_nova as N
    from ml.track.corners import detect_corners
    from ml.track.geometry import load_corridor_geometry
    from ml.track.microsectors import build_microsectors

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--handoff", help="prefixo dos arquivos de handoff")
    args = parser.parse_args(argv)
    t0 = time.time()
    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    trechos = PT.trechos(detect_corners(track), track.length)
    nomes = [t.nome for t in trechos]
    caminho_resultado = config.repo_root() / RESULTADO_47
    resultado = json.loads(caminho_resultado.read_text(encoding="utf-8"))
    linhas = carregar_linhas(track)
    estacao = np.mod(N.estacoes(linhas["C0"]["spline"], track), track.length)
    teste = carregar_voltas_do_teste(track, resultado)
    voltas = teste["voltas"]
    m = {c: tempos_das_voltas(voltas[c], track, trechos, "tempo_47_s") for c in CONDICOES_DO_TESTE}
    comp = comparacao_completa(m, nomes)
    classe = {x: PT.classificar(comp[f"{x} contra C0"], comp[f"{x} contra C0 final"]) for x in ("C1", "C2", "C3", "C4")}
    candidatas = [{"trecho": nomes[j], "linha": x, "ganho_contra_c0_s": comp[f"{x} contra C0"][j]["diferenca_s"],
                   "ganho_contra_c0_final_s": comp[f"{x} contra C0 final"][j]["diferenca_s"]}
                  for x in ("C3", "C4") for j in range(len(nomes)) if classe[x][j] == "ganho"]
    medidas = {c: medidas_por_condicao(voltas[c], track, trechos) for c in CONDICOES_DO_TESTE}
    hip = hipoteses(voltas, linhas, track, trechos, sectors, medidas, estacao)
    humanas = carregar_voltas_humanas(track)
    eu = minhas_contas(humanas["voltas"], m["C0"], medidas["C0"], linhas, track, trechos)
    eu_medidas = eu.pop("medidas")
    eu_matriz = eu.pop("matriz_tempos")
    freio_max_humano = float(np.nanmax([np.nanmax(v["canais"]["brake"]) for v in humanas["voltas"]]))
    freio_max_ia = float(np.nanmax([np.nanmax(v["canais"]["brake"]) for c in CONDICOES_DO_TESTE for v in voltas[c]]))

    payload = {
        "pedido": 49, "adr": "docs/decisoes/0030-modelo1-por-trecho.md", "parte": "B", "commit": git_commit(),
        "comando": "python -m ml.scripts.modelo1_por_trecho", "ambiente": {"python": platform.python_version()},
        "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, "grade_m": float(track.step),
        "comprimento_m": float(track.length),
        "trechos": [{"trecho": t.nome, "inicio_s": t.inicio_s, "fim_s": t.fim_s, "pontos_de_linha_s": t.pontos_de_linha()} for t in trechos],
        "nomes_dos_trechos": nomes,
        "entradas": {"resultado_47": {"arquivo": caminho_resultado, "sha256": _sha256(caminho_resultado)},
                     "gravacoes_da_copia": teste["arquivos"], "voltas_humano": humanas["arquivos"],
                     "linhas": {c: {"arquivo": linhas[c]["arquivo"], "sha256": linhas[c]["sha256"]} for c in LINHAS}},
        "canais": {"freio_maximo_nas_voltas_da_ia": freio_max_ia, "freio_maximo_nas_voltas_do_eduardo": freio_max_humano},
        "voltas": {c: [{"id": v["id"], "tempo_s": v["tempo_s"], "tempo_47_s": v["tempo_47_s"], "tempo_jogo_s": v["tempo_jogo_s"],
                        "soma_menos_tempo_s": v["soma_menos_tempo_s"], "tempos_por_trecho_s": v["tempos_por_trecho_s"]}
                       for v in voltas[c]] for c in CONDICOES_DO_TESTE},
        "soma_dos_trechos": {
            "maior_diferenca_teste_s": float(max(abs(v["soma_menos_tempo_s"]) for c in CONDICOES_DO_TESTE for v in voltas[c])),
            "maior_diferenca_eduardo_s": float(max(abs(v["soma_menos_tempo_s"]) for v in humanas["voltas"])),
            "maior_diferenca_do_tempo_refeito_s": float(max(abs(v["tempo_s"] - v["tempo_47_s"]) for c in CONDICOES_DO_TESTE for v in voltas[c]))},
        "tempos": {c: resumo_de_tempos(m[c], nomes) for c in CONDICOES_DO_TESTE},
        "volta_pela_soma_das_medianas_s": {c: float(np.median(m[c], axis=0).sum()) for c in CONDICOES_DO_TESTE},
        "comparacoes": comp, "classificacao": classe, "candidatas": candidatas,
        "execucao": medidas, "hipoteses": hip,
        "eduardo": {**eu, "execucao": eu_medidas,
                    "voltas": [{"id": v["id"], "sessao": v["sessao"], "tempo_s": v["tempo_s"],
                                "tempos_por_trecho_s": v["tempos_por_trecho_s"]} for v in humanas["voltas"]]},
        "teto": teto(m, nomes),
        "lateral_da_linha": {c: linhas[c]["lateral"] for c in LINHAS},
        "tempo_s": None,
    }
    payload["tempo_s"] = round(time.time() - t0, 1)
    saida = raiz_saida()
    _json(saida / "conta.json", payload)
    texto = tabelas(payload)
    (saida / "tabelas.md").write_text(texto, encoding="utf-8")
    if args.handoff:
        leve = {k: v for k, v in payload.items() if k != "lateral_da_linha"}
        leve["execucao"] = {c: [{"trecho": t["trecho"], "resumo": t["resumo"]} for t in medidas[c]] for c in medidas}
        leve["eduardo"] = {k: v for k, v in payload["eduardo"].items() if k != "voltas"}
        leve["eduardo"]["execucao"] = [{"trecho": t["trecho"], "resumo": t["resumo"]} for t in eu_medidas]
        _json(Path(str(args.handoff) + "_conta.json"), leve)
        figura(comp, nomes, Path(str(args.handoff) + "_por_trecho.png"))
    print(f"candidatas: {candidatas}")
    for x, cl in classe.items():
        print(x, dict(zip(nomes, cl)))
    print(f"tempo: {payload['tempo_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
