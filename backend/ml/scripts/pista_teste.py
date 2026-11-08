"""A linha gerada dirigida pela IA do jogo (pedido 47; ADR 0029).

    python -m ml.scripts.pista_teste parte-a  [--handoff PREFIXO]
    python -m ml.scripts.pista_teste medidor  [--handoff PREFIXO]
    python -m ml.scripts.pista_teste linhas   [--handoff PREFIXO]
    python -m ml.scripts.pista_teste conferencia [--rotulo sessao1] [--handoff PREFIXO]
    python -m ml.scripts.pista_teste resultado [--handoff PREFIXO]

* `parte-a`: so leitura e contas. A pasta da pista (nomes e tamanhos), o
  formato do `fast_lane.ai` (com a ida e volta), o referencial contra a volta da
  IA `#0013`, os campos e as regras, a linha nova em 3D e os caches do CSP;
* `medidor`: o tempo de cada condicao no medidor do pedido 46 (B.8), antes do
  jogo;
* `linhas`: os `fast_lane.ai` de C1 a C4 em `data/pista_teste/linhas/` (fora do
  git), com o sha256, e a figura;
* `conferencia`: so a conferencia da troca (E.1), entre as sessoes no jogo,
  sem calcular nem mostrar nenhum tempo (pedido do Eduardo de 08/11);
* `resultado`: depois do teste no jogo (Parte E).

Nada aqui escreve na pasta do jogo: quem copia e troca a linha sao os scripts
de `tools/pista_teste/`, que o Eduardo roda.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from ml import config  # noqa: E402
from ml.data.store_v2 import git_commit  # noqa: E402
from ml.pista_teste import ai_spline as A  # noqa: E402
from ml.pista_teste import condicoes as C  # noqa: E402
from ml.pista_teste import linha_nova as N  # noqa: E402
from ml.track.geometry import load_corridor_geometry  # noqa: E402

FONTES = {
    "actools": "https://github.com/gro-ove/actools/tree/master/AcTools/AiFile (AiSpline.cs, AiPointExtra.cs, AiSplineGrid.cs)",
    "addon": "https://github.com/leBluem/io_import_accsv (import_ai.py)",
    "addon_overwrite": "https://www.modland.net/assetto-corsa-mods/other/blender-addon-importexport-aicsvini-files.html",
}


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")


def _padrao(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(type(o))


def _stats(x) -> dict:
    x = np.asarray(x, float)
    return {"min": float(x.min()), "p50": float(np.median(x)), "max": float(x.max()), "unicos": int(len(np.unique(x)))}


def _dist_a_polilinha(q: np.ndarray, poli: np.ndarray) -> np.ndarray:
    _, _, d = N._projetar_na_polilinha(np.asarray(q, float), np.asarray(poli, float))
    return d


# ------------------------------------------------------------------ parte A ---

def pasta_da_pista() -> dict:
    jogo = C.pasta_do_jogo()
    pista = jogo / "content" / "tracks" / C.PISTA_ORIGINAL
    arquivos, total = 0, 0
    for raiz, _, nomes in os.walk(pista):
        for nome in nomes:
            arquivos += 1
            total += (Path(raiz) / nome).stat().st_size
    layouts = sorted(p.name for p in pista.iterdir() if p.is_dir() and (p / "ai").is_dir())
    ai = {lay: {f.name: f.stat().st_size for f in sorted((pista / lay / "ai").iterdir())} for lay in layouts}
    hints = {lay: (pista / lay / "data" / "ai_hints.ini").exists() for lay in layouts}
    copia = jogo / "content" / "tracks" / C.PISTA_COPIA
    livre = {d: shutil.disk_usage(d).free for d in {str(jogo.anchor), "C:\\"}}
    return {"jogo": jogo, "pista": pista, "layouts": layouts, "arquivos_ai": ai, "ai_hints_ini": hints,
            "arquivos": arquivos, "bytes": total, "espaco_livre_bytes": livre,
            "copia": {"nome": C.PISTA_COPIA, "existe": copia.exists(), "nome_no_jogo": C.NOME_NO_JOGO},
            "sha256": {lay: {f: A.sha256_arquivo(pista / lay / "ai" / f) for f in ai[lay]} for lay in layouts}}


def formato(spline: A.AiSpline, raw: bytes) -> dict:
    escrito = A.escrever(spline)
    g = A.construir_grade(spline.pos, spline.grade.vizinhos, spline.grade.densidade)
    iguais = (g.celulas == spline.grade.celulas).all(axis=-1)
    mesmo_conjunto = int(sum(set(g.celulas[i, j]) == set(spline.grade.celulas[i, j]) for i, j in np.argwhere(~iguais)))
    return {
        "cabecalho": {"versao": spline.versao, "pontos": spline.n, "tempo_de_volta": spline.tempo_de_volta,
                      "amostras": spline.amostras},
        "bytes": len(raw), "indices_em_ordem": bool((spline.idx == np.arange(spline.n)).all()),
        "extras": {nome: _stats(spline.campo(nome)) for nome in A.CAMPOS_EXTRAS},
        "grade": {"tem_grade": spline.tem_grade, "maximo": spline.grade.maximo, "minimo": spline.grade.minimo,
                  "vizinhos": spline.grade.vizinhos, "densidade_m": spline.grade.densidade,
                  "colunas_linhas": list(spline.grade.forma[:2]),
                  "folga_m": float(spline.pos[:, 0].min() - spline.grade.minimo[0]),
                  "recalculada": {"celulas": int(iguais.size), "iguais_na_ordem": int(iguais.sum()),
                                  "diferentes_com_o_mesmo_conjunto": mesmo_conjunto,
                                  "extremos_iguais": bool((g.minimo == spline.grade.minimo).all()
                                                          and (g.maximo == spline.grade.maximo).all())}},
        "bytes_depois_da_grade": len(spline.cauda),
        "ida_e_volta_byte_a_byte": escrito == raw,
        "fontes": FONTES,
    }


def referencial(track, spline: A.AiSpline) -> dict:
    from ml.scripts import retreino_lstm as RL

    src = RL.load_prepared(track)
    f = src.store.frame
    lap = f[f["lap_id"] == C.VOLTA_IA].sort_values("grid_index")
    gravada = lap[["x", "z"]].to_numpy(float)
    linha = spline.pos[:, [0, 2]].astype(float)
    d = _dist_a_polilinha(linha, gravada)
    d2 = _dist_a_polilinha(gravada, linha)
    espelhada = _dist_a_polilinha(linha, gravada * [1, -1])
    return {"volta": C.VOLTA_IA, "pontos_gravados": len(gravada),
            "fast_lane_ate_a_volta_m": {"mediana": float(np.median(d)), "p95": float(np.percentile(d, 95)), "max": float(d.max())},
            "volta_ate_o_fast_lane_m": {"mediana": float(np.median(d2)), "p95": float(np.percentile(d2, 95))},
            "com_z_invertido_mediana_m": float(np.median(espelhada)),
            "mesmo_referencial": bool(np.median(d) <= 2.0)}


def campos(track, spline: A.AiSpline) -> dict:
    from scipy.spatial import cKDTree

    esq, dir_ = N.bordas(spline)
    cl = track.points + track.normal * track.width_left[:, None]
    cr = track.points - track.normal * track.width_right[:, None]
    dl = cKDTree(cl).query(esq)[0]
    dr = cKDTree(cr).query(dir_)[0]
    idx = cKDTree(track.points).query(spline.pos[:, [0, 2]].astype(float))[1]
    largura = spline.campo("lateral_esquerda") + spline.campo("lateral_direita") - track.width()[idx]
    seg = np.r_[np.diff(spline.dist.astype(float)), spline.campo("comprimento")[0]]
    tempo_pela_velocidade = float(np.sum(seg / spline.campo("velocidade")))
    v2r = spline.campo("velocidade").astype(float) ** 2 / spline.campo("raio").astype(float)
    return {
        "regras_conferidas_no_original": N.conferir_formulas(spline),
        "bordas_contra_o_corredor_do_pedido_44_m": {
            "esquerda": {"mediana": float(np.median(dl)), "p95": float(np.percentile(dl, 95))},
            "direita": {"mediana": float(np.median(dr)), "p95": float(np.percentile(dr, 95))},
            "largura_da_ia_menos_a_do_corredor": {"mediana": float(np.median(largura)), "p5": float(np.percentile(largura, 5)),
                                                  "p95": float(np.percentile(largura, 95))}},
        "velocidade": {"tempo_da_volta_pela_velocidade_gravada_s": tempo_pela_velocidade,
                       "volta_da_ia_no_cronometro_s": 84.829163,
                       "aceleracao_lateral_v2_sobre_r_m_s2": {"p50": float(np.median(v2r)), "p95": float(np.percentile(v2r, 95)),
                                                              "max": float(v2r.max())}},
        "pedais": {"pontos_com_acelerador_abaixo_de_1": int((spline.campo("acelerador") < 1).sum()),
                   "pontos_com_freio": int((spline.campo("freio") > 0).sum())},
        "ultimo_ponto": {"comprimento": float(spline.campo("comprimento")[-1]), "direcao": float(spline.campo("direcao")[-1])},
    }


def linha_nova_3d(track, spline: A.AiSpline, laterais: dict) -> dict:
    out = {}
    original = spline.campo("comprimento")
    for nome in ("C1", "C2", "C3", "C4"):
        bruto_esq, bruto_dir = _laterais_sem_piso(spline, track, laterais[nome])
        ln = N.montar(spline, track, laterais[nome])
        sp = ln.spline
        seg = sp.campo("comprimento")
        un = np.unwrap(ln.estacao_s, period=track.length)
        out[nome] = {
            "pontos": sp.n, "mesmo_numero_do_original": sp.n == spline.n,
            "espacamento_m": {"min": float(seg.min()), "p50": float(np.median(seg)), "max": float(seg.max())},
            "fechamento_m": float(seg[0]), "comprimento_total_m": float(sp.dist[-1] + seg[0]),
            "sentido_igual": bool((np.diff(un) > 0).all()),
            "ponto_0_estacao_s": float(np.mod(ln.estacao_s[0], track.length)),
            "deslocamento_do_original_m": {"mediana": float(np.median(ln.deslocamento_m)), "max": float(ln.deslocamento_m.max())},
            "altura_m": {"min": float(sp.pos[:, 1].min()), "max": float(sp.pos[:, 1].max())},
            "laterais_negativas_antes_do_piso": {"esquerda": int((bruto_esq < 0).sum()), "direita": int((bruto_dir < 0).sum()),
                                                 "maior_movimento_da_borda_m": float(max(0.0, -bruto_esq.min(), -bruto_dir.min()))},
        }
    out["original"] = {"espacamento_m": {"min": float(original.min()), "p50": float(np.median(original)),
                                         "max_sem_o_ultimo": float(original[:-1].max())},
                       "comprimento_total_m": float(spline.dist[-1] + original[0])}
    return out


def _laterais_sem_piso(spline, track, lateral):
    s = N.estacoes(spline, track)
    lat = np.interp(np.mod(s, track.length), np.r_[track.s, track.length], np.r_[lateral, lateral[0]])
    xz = track.to_world(s, lat)
    pos = np.column_stack([xz[:, 0], np.zeros(len(xz)), xz[:, 1]])
    esq = N.esquerda_xz(N.geometria(pos)["frente"])
    be, bd = N.bordas(spline)
    return N._distancia_ate_a_borda(xz, esq, be), N._distancia_ate_a_borda(xz, -esq, bd)


def caches_do_csp() -> dict:
    cache = C.pasta_do_jogo() / "cache"
    out = {}
    for pasta in ("ai_grids", "ai_payloads", "ai_alt_lanes", "tracks_data", "csp_configs"):
        p = cache / pasta
        if p.is_dir():
            out[pasta] = sorted(f"{f.name} ({f.stat().st_size} bytes)" for f in p.iterdir()
                                if f.name.startswith(C.PISTA_ORIGINAL))
    return out


def parte_a(args) -> int:
    t0 = time.time()
    caminho = C.fast_lane_original()
    raw = caminho.read_bytes()
    spline = A.ler(raw)
    track = load_corridor_geometry()
    laterais = C.linhas(track, spline.pos[:, [0, 2]].astype(float))
    payload = {
        "pedido": 47, "parte": "A", "commit": git_commit(), "comando": "python -m ml.scripts.pista_teste parte-a",
        "ambiente": {"python": platform.python_version(), "plataforma": platform.platform()},
        "arquivo": {"caminho": caminho, "sha256": A.sha256_bytes(raw)},
        "geometry_id": track.geometry_id, "corridor_id": track.corridor_id,
        "pasta": pasta_da_pista(), "formato": formato(spline, raw), "referencial": referencial(track, spline),
        "campos": campos(track, spline), "linha_nova": linha_nova_3d(track, spline, laterais),
        "caches_do_csp": caches_do_csp(), "tempo_s": None,
    }
    payload["tempo_s"] = round(time.time() - t0, 1)
    _json(C.raiz_saida() / "parte_a.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_parte_a.json"), payload)
    print(json.dumps({k: payload[k] for k in ("arquivo", "referencial")}, indent=1, default=_padrao))
    print("ida e volta:", payload["formato"]["ida_e_volta_byte_a_byte"], "| grade:", payload["formato"]["grade"]["recalculada"])
    return 0


# ------------------------------------------------------------- medidor B.8 ---

def medidor(args) -> int:
    from ml.optimization.lap_time_model import simulate
    from ml.optimization.vehicle_model import envelope_path, load_envelope
    from ml.scripts.modelo1_final import tempos_por_microssetor
    from ml.track.microsectors import build_microsectors

    spline = A.ler(C.fast_lane_original())
    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    laterais = C.linhas(track, spline.pos[:, [0, 2]].astype(float))
    env = load_envelope()
    sims = {k: simulate(track, v, env) for k, v in laterais.items()}
    base = tempos_por_microssetor(sims["C0"], sectors)
    tabela = {}
    for k, s in sims.items():
        sec = tempos_por_microssetor(s, sectors) - base
        tabela[k] = {"descricao": C.DESCRICAO[k], "tempo_s": float(s.lap_time_s), "contra_c0_s": float(s.lap_time_s - sims["C0"].lap_time_s),
                     "por_microssetor_contra_c0_s": sec.tolist(),
                     "microssetores_36_0_1_contra_c0_s": {str(i): float(sec[i]) for i in (36, 0, 1)}}
    ordem = sorted(tabela, key=lambda k: tabela[k]["tempo_s"])
    payload = {"pedido": 47, "parte": "B.8", "commit": git_commit(), "comando": "python -m ml.scripts.pista_teste medidor",
               "medidor": "simulador quase-estacionario, envelope das voltas reais (o do pedido 46)",
               "envelope": {"arquivo": envelope_path(), "sha256": A.sha256_arquivo(envelope_path())},
               "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, "tempos": tabela, "ordem_do_medidor": ordem,
               "linhas_sha256": {k: A.sha256_bytes(np.ascontiguousarray(v, dtype="<f8").tobytes()) for k, v in laterais.items()}}
    _json(C.raiz_saida() / "medidor.json", payload)
    if args.handoff:
        _json(Path(str(args.handoff) + "_medidor.json"), payload)
    for k in ordem:
        print(f"{k}  {tabela[k]['tempo_s']:8.3f} s  ({tabela[k]['contra_c0_s']:+.3f} s contra C0)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("comando", choices=("parte-a", "medidor", "linhas", "conferencia", "resultado"))
    parser.add_argument("--handoff", help="prefixo dos arquivos de handoff")
    parser.add_argument("--rotulo", default="sessao1", help="conferencia: o nome do arquivo de saida")
    args = parser.parse_args(argv)
    if args.comando == "parte-a":
        return parte_a(args)
    if args.comando == "medidor":
        return medidor(args)
    from ml.pista_teste import etapas
    acoes = {"linhas": etapas.linhas, "conferencia": etapas.conferencia, "resultado": etapas.resultado}
    return acoes[args.comando](args)


if __name__ == "__main__":
    raise SystemExit(main())
