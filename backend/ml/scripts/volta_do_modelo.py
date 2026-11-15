"""A volta do modelo como arquivo do app (pedido 51, Parte B; ADR 0032).

    python -m ml.scripts.volta_do_modelo --linhas <pasta>/data/pista_teste/linhas \
        --resultado docs/handoff/2026-11-12_50_linha-do-projeto_resultado.json [--handoff PREFIXO]

Le, sem copiar, a gravacao da melhor volta valida da linha que atingiu a meta
(a L2 do pedido 50) e grava so o que deriva dela em
`data/reference_models/<pista>.volta_do_modelo.json` (fora do git):

* a grade de 2 m da geometria oficial, pelo mesmo caminho do store v2 (limpeza,
  alinhamento e `resample_lap(..., line_clock=True)`): o tempo, a lateral, a
  posicao, a velocidade, a marcha e os pedais;
* os alvos por microssetor, pelo mesmo caminho das referencias do coach
  (`reference_from_laps` na geometria oficial exportada);
* a origem (a sessao, a sequencia, a volta do jogo e o sha256 dos arquivos da
  gravacao), a linha (o sha256 do `fast_lane.ai` dela), o `geometry_id`, o
  `corridor_id`, o carro, o preset e a marca do ADR 0031.

As conferencias (B.3 e B.5) vao para o `--handoff`, sem a grade:

* a pista da gravacao: a copia e a original com os mesmos arquivos de superficie
  (os da origem do cache da pista, fora a linha da IA) e as voltas medidas no
  mesmo `geometry_id`; senao, PARADO;
* o tempo refeito na grade contra o do `_resultado.json` do pedido 50 (ate 5 ms);
* os 15 trechos contra os do `_resultado.json`;
* a distancia da volta a linha da L2 e a da linha da IA (mediana e p95);
* os alvos por microssetor da volta do modelo e os da `#0013`, lado a lado.

A sessao da copia e pedida por `ml.pista_teste.etapas.sessoes_da_copia`, o unico
lugar que pede as sessoes da copia.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from core.assisted_analysis import volta_do_modelo as VM  # noqa: E402
from core.assisted_analysis.official_geometry import find_official_geometry  # noqa: E402
from core.assisted_analysis.reference_model import reference_from_laps  # noqa: E402
from ml import config  # noqa: E402
from ml.data.store_v2 import git_commit  # noqa: E402

PEDIDO = 51
PISTA = "vhe_interlagos"
LINHA = "L2"
SESSAO = "2026-11-15_02-47-12_vhe_interlagos_teste_m1"
SEQUENCIA = 8
TEMPO_DO_50_S = 84.55158121991376          # o `tempo_s` da volta no `_resultado.json` do pedido 50
SHA_L2 = "4e9f125094c08a9572c89f85da8d0ab8aa0a6d23b8f27430db13bd00a180fd1e"
SHA_C0 = "36b57fd8d259755d9b25ffdc1f61e328479045fc275e554b7b7e3de7eb3d8342"
PRESET = "pedido 47 [teste]"
META_ATINGIDA_EM = "2026-11-15"
TOLERANCIA_TEMPO_S = 0.005
ORIGEM_DO_CACHE = "vhe_interlagos_gp_kn5_surface_interval_geometry.origem.json"
COLUNAS = ("elapsed_s", "lateral", "x", "z", "speed_kmh", "gear", "throttle", "brake")
CASAS = {"elapsed_s": 6, "lateral": 4, "x": 3, "z": 3, "speed_kmh": 3, "gear": 0, "throttle": 4, "brake": 4}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


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


def _lista(valores, casas: int):
    out = []
    for v in np.asarray(valores, float):
        out.append(round(float(v), casas) if np.isfinite(v) else None)
    return out


def conferir_pista(copia: str, original: str) -> dict:
    """B.3: os arquivos que a geometria le (a origem do cache), na copia e na original, pelo sha256."""
    origem = json.loads((config.repo_root() / "data" / "cache" / "tracks" / ORIGEM_DO_CACHE).read_text(encoding="utf-8"))
    arquivos = []
    for item in origem["files"]:
        caminho_original = Path(item["file"])
        partes = [p.lower() for p in caminho_original.parts]
        i = partes.index(original.lower())
        relativo = Path(*caminho_original.parts[i + 1:])
        pasta_tracks = Path(*caminho_original.parts[:i])
        a, b = pasta_tracks / original / relativo, pasta_tracks / copia / relativo
        sha_a = _sha256(a) if a.exists() else None
        sha_b = _sha256(b) if b.exists() else None
        linha_da_ia = relativo.parts[:2] == ("gp", "ai") and relativo.name == "fast_lane.ai"
        arquivos.append({"arquivo": str(relativo).replace("\\", "/"), "sha256_original": sha_a, "sha256_copia": sha_b,
                         "igual": sha_a is not None and sha_a == sha_b,
                         "papel": "a linha da IA (troca de proposito no teste)" if linha_da_ia else "superficie e dados do layout"})
    superficie = [a for a in arquivos if not a["papel"].startswith("a linha")]
    kn5 = next(a for a in arquivos if a["arquivo"] == f"{original}.kn5")
    return {"arquivos": arquivos, "superficie_igual": all(a["igual"] for a in superficie),
            "kn5_da_pista": kn5, "sha256_da_origem_do_cache": origem.get("sha256")}


def _tool(nome: str):
    spec = importlib.util.spec_from_file_location(nome, config.repo_root() / "backend" / "tools" / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def main(argv=None) -> int:
    from ml.data.recordings import iter_laps
    from ml.data.store_v2 import game_lap_time
    from ml.pista_teste import ai_spline as A
    from ml.pista_teste import etapas as E
    from ml.pista_teste import linha_nova as N
    from ml.pista_teste import por_trecho as PT
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.preprocessing.resampling import lap_time_from_grid, resample_lap
    from ml.track.corners import detect_corners
    from ml.track.geometry import load_corridor_geometry

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--linhas", type=Path, required=True, help="data/pista_teste/linhas da pasta do pedido 50 (so lida)")
    parser.add_argument("--resultado", type=Path, required=True, help="o _resultado.json do pedido 50")
    parser.add_argument("--handoff", default=None, help="prefixo dos arquivos de conferencia em docs/handoff")
    parser.add_argument("--saida", type=Path, default=None, help="padrao: data/reference_models do repositorio")
    args = parser.parse_args(argv)
    repo = config.repo_root()

    # A linha e a linha da IA, conferidas pelo sha256 do pedido 50.
    l2_ai, c0_ai = args.linhas / LINHA / "fast_lane.ai", args.linhas / "C0" / "fast_lane.ai"
    if A.sha256_arquivo(l2_ai) != SHA_L2:
        raise SystemExit(f"PARADO: {l2_ai} nao tem o sha256 da L2 do pedido 50.")
    if A.sha256_arquivo(c0_ai) != SHA_C0:
        raise SystemExit(f"PARADO: {c0_ai} nao tem o sha256 da linha da IA original.")
    manifesto_50 = json.loads((args.linhas / "linha_do_projeto.json").read_text(encoding="utf-8"))
    resultado_50 = json.loads(args.resultado.read_text(encoding="utf-8"))
    veredito = (resultado_50.get("vereditos") or {}).get(LINHA) or {}

    # A volta no _resultado.json do pedido 50.
    voltas_do_bloco = [v for vs in resultado_50["voltas"].values() for v in vs
                       if v["sessao"] == SESSAO and v["sequencia"] == SEQUENCIA]
    if len(voltas_do_bloco) != 1 or not voltas_do_bloco[0]["valida"] or voltas_do_bloco[0]["condicao"] != LINHA:
        raise SystemExit(f"PARADO: a volta {SESSAO} #{SEQUENCIA} nao e uma volta valida da {LINHA} no _resultado.json.")
    volta_50 = voltas_do_bloco[0]
    melhor_da_l2 = min((v for vs in resultado_50["voltas"].values() for v in vs
                        if v["condicao"] == LINHA and v["valida"] and v.get("papel") == "conta"), key=lambda v: v["tempo_s"])
    if (melhor_da_l2["sessao"], melhor_da_l2["sequencia"]) != (SESSAO, SEQUENCIA):
        raise SystemExit("PARADO: a melhor volta valida da L2 no _resultado.json nao e a esperada.")

    # A geometria: a do projeto (com o corredor) e a oficial exportada, que o coach usa.
    track = load_corridor_geometry()
    oficial = find_official_geometry([repo], PISTA)
    if oficial is None or oficial.geometry_id != track.geometry_id:
        raise SystemExit("PARADO: a geometria oficial exportada nao e a do projeto.")
    corners = detect_corners(track)
    trechos = PT.trechos(corners, track.length)

    # A sessao da copia, so lida.
    sessoes = {s.session_id: s for s in E.sessoes_da_copia()}
    if SESSAO not in sessoes:
        raise SystemExit(f"PARADO: a gravacao {SESSAO} nao foi encontrada nas pastas de gravacoes.")
    sessao = sessoes[SESSAO]
    meta = sessao.metadata()
    pista_gravada = meta.get("track")
    laps = list(iter_laps(sessao))
    idx = next(i for i, lap in enumerate(laps) if lap.sequence == SEQUENCIA)
    lap = laps[idx]
    seguinte = laps[idx + 1] if idx + 1 < len(laps) else None

    # B.3: a pista da gravacao.
    pista = conferir_pista(pista_gravada, PISTA) if pista_gravada != PISTA else {"superficie_igual": True}
    pista["pista_da_gravacao"] = pista_gravada
    pista["cache_da_pista_na_gravacao"] = (meta.get("metadata") or {}).get("trackCache")
    pista["geometry_id_das_voltas"] = track.geometry_id
    pista["geometry_id_da_original"] = oficial.geometry_id
    pista["mesma_geometria"] = bool(pista["superficie_igual"] and track.geometry_id == oficial.geometry_id
                                    and pista["cache_da_pista_na_gravacao"] == "vhe_interlagos_gp_kn5_surface_interval_geometry")
    if not pista["mesma_geometria"]:
        print(json.dumps(pista, indent=1, ensure_ascii=False, default=_padrao))
        raise SystemExit("PARADO: a copia e a original nao tem a mesma geometria (B.3).")

    # A grade, pelo caminho do store v2.
    cleaned, _ = clean_lap(lap.frame)
    aligned, alignment = align_lap(cleaned, track)
    grid = resample_lap(aligned, track, line_clock=True)
    tempo = float(lap_time_from_grid(grid))
    tempo_jogo = game_lap_time(lap, seguinte, track)
    faltam = [c for c in COLUNAS if c not in grid.columns]
    if faltam:
        raise SystemExit(f"PARADO: a grade nao tem {faltam}.")
    trechos_s = PT.tempos_por_trecho(grid["elapsed_s"].to_numpy(float), track.s, tempo, trechos)

    # Os alvos por microssetor, pelo caminho das referencias do coach.
    treino = _tool("train_reference_model")
    quadro = treino.coach_frame(lap)
    ref, candidatos = reference_from_laps([(lap.lap_id, tempo, int(lap.sample_count), quadro)],
                                          geometry=oficial, kind=VM.KIND)
    if ref is None:
        raise SystemExit(f"PARADO: a volta nao passou nas regras da referencia do coach: {candidatos}")

    # A distancia a linha da L2 e a da IA.
    xz = aligned[["x", "z"]].to_numpy(float)
    xz = xz[np.isfinite(xz).all(axis=1)]
    d_l2 = N._projetar_na_polilinha(xz, A.ler(l2_ai).pos[:, [0, 2]].astype(float))[2]
    d_c0 = N._projetar_na_polilinha(xz, A.ler(c0_ai).pos[:, [0, 2]].astype(float))[2]
    distancia = {"pontos": int(len(xz)),
                 "ate_a_L2_m": {"mediana": float(np.median(d_l2)), "p95": float(np.percentile(d_l2, 95))},
                 "ate_a_linha_da_ia_m": {"mediana": float(np.median(d_c0)), "p95": float(np.percentile(d_c0, 95))}}
    distancia["e_a_L2"] = distancia["ate_a_L2_m"]["mediana"] < distancia["ate_a_linha_da_ia_m"]["mediana"]

    # O arquivo derivado.
    pasta = sessao.directory
    arquivos = [{"arquivo": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)}
                for p in sorted(pasta.iterdir()) if p.is_file()]
    agora = datetime.now().isoformat(timespec="seconds")
    ref["lap_seconds"] = round(float(sum(s["seconds"] for s in ref["sectors"])), 3)
    ref["candidates"] = []
    dados = {
        "formato": VM.FORMATO,
        "pedido": PEDIDO, "adr": "0032",
        "gerado_em": agora, "commit": git_commit(),
        "comando": "python -m ml.scripts.volta_do_modelo",
        "pista": PISTA,
        "rotulo": "Volta de referência",
        "lap_id": lap.lap_id,
        "tempo_s": round(tempo, 6),
        "tempo": E.tempo_mmss(tempo),
        "tempo_jogo_s": None if tempo_jogo is None else round(float(tempo_jogo), 6),
        "carro": (meta.get("metadata") or {}).get("carModel"),
        "preset": PRESET,
        "geometry_id": track.geometry_id,
        "corridor_id": track.corridor_id,
        "marca": f"linha do projeto, meta atingida em {META_ATINGIDA_EM}",
        "executada_por": "executada pela IA do jogo na linha do projeto",
        "pedais": "comando do controlador da IA: desenhados, nunca julgados (ADR 0032, item 5)",
        "linha": {"nome": LINHA, "adr": "0031", "pedido": 50, "fast_lane_sha256": SHA_L2,
                  "fast_lane_bytes": l2_ai.stat().st_size,
                  "codificacao": manifesto_50.get("codificacao"),
                  "veredito": veredito.get("veredito") or veredito.get("resultado"),
                  "melhor_s": volta_50["tempo_s"]},
        "origem": {"sessao": SESSAO, "sequencia": SEQUENCIA, "volta_do_jogo": lap.lap_number,
                   "pista_da_gravacao": pista_gravada, "app": (meta.get("metadata") or {}).get("appVersion"),
                   "pasta": "gravacoes do app instalado" if "Automobilista Telemetria" in str(pasta) else "gravacoes do repositorio",
                   "arquivos": arquivos,
                   "copiada": False},
        "pista_da_gravacao": {k: v for k, v in pista.items() if k != "arquivos"},
        "grade": {"pontos": int(track.size), "passo_m": float(track.step), "comprimento_m": float(track.length),
                  "cobertura": float(alignment.coverage),
                  **{c: _lista(grid[c].to_numpy(float), CASAS[c]) for c in COLUNAS}},
        "referencia": ref,
    }
    saida = args.saida or VM.caminho(repo, PISTA)
    guardada = None
    if saida.exists():
        anterior = json.loads(saida.read_text(encoding="utf-8"))
        if anterior.get("lap_id") != dados["lap_id"] or anterior.get("tempo_s") != dados["tempo_s"]:
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            guardada = saida.parent / "backup" / f"{saida.stem}.{stamp}.anterior.json"
            guardada.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saida, guardada)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":"), default=_padrao), encoding="utf-8")
    print(f"volta do modelo: {dados['lap_id']} {dados['tempo']} -> {saida}")

    # B.5: as conferencias.
    trechos_50 = list(volta_50["trechos_s"])
    dif_trechos = [float(a - b) for a, b in zip(trechos_s, trechos_50)]
    modelo_coach = json.loads((repo / "data" / "reference_models" / f"{PISTA}.json").read_text(encoding="utf-8"))
    ref_0013 = (modelo_coach.get("references") or {}).get("volta_ia") or {}
    por_ms = {int(s["index"]): s for s in ref_0013.get("sectors") or []}
    lado_a_lado = []
    for s in ref["sectors"]:
        o = por_ms.get(int(s["index"]), {})
        lado_a_lado.append({"microssetor": int(s["index"]),
                            "modelo_s": s["seconds"], "a_0013_s": o.get("seconds"),
                            "diferenca_s": None if o.get("seconds") is None else round(s["seconds"] - o["seconds"], 4),
                            "modelo_minima_kmh": s.get("min_speed_kmh"), "a_0013_minima_kmh": o.get("min_speed_kmh"),
                            "modelo_freada_m": s.get("brake_onset_m"), "a_0013_freada_m": o.get("brake_onset_m")})
    conferencia = {
        "pedido": PEDIDO, "adr": "0032", "parte": "B", "commit": git_commit(), "gerado_em": agora,
        "comando": "python -m ml.scripts.volta_do_modelo",
        "ambiente": {"python": platform.python_version(), "numpy": np.__version__},
        "arquivo": str(saida), "bytes": saida.stat().st_size, "sha256": _sha256(saida),
        "anterior_guardada": str(guardada) if guardada else None,
        "volta": {"lap_id": lap.lap_id, "sessao": SESSAO, "sequencia": SEQUENCIA, "volta_do_jogo": lap.lap_number,
                  "arquivos_da_gravacao": arquivos},
        "pista_da_gravacao": pista,
        "tempo": {"refeito_na_grade_s": tempo, "refeito": E.tempo_mmss(tempo), "do_resultado_50_s": TEMPO_DO_50_S,
                  "diferenca_ms": (tempo - TEMPO_DO_50_S) * 1000.0,
                  "contra_1_24_552_ms": (tempo - 84.552) * 1000.0,
                  "dentro_de_5_ms": abs(tempo - 84.552) <= TOLERANCIA_TEMPO_S,
                  "cronometro_do_jogo_s": tempo_jogo,
                  "soma_dos_60_microssetores_do_coach_s": ref["lap_seconds"]},
        "trechos": {"nomes": [t.nome for t in trechos], "refeitos_s": [float(x) for x in trechos_s],
                    "do_resultado_50_s": trechos_50, "diferenca_max_ms": max(abs(d) for d in dif_trechos) * 1000.0,
                    "batem": max(abs(d) for d in dif_trechos) <= 1e-6},
        "distancia": distancia,
        "microssetores_lado_a_lado": {"a_0013": ref_0013.get("lap_id"), "a_0013_s": ref_0013.get("lap_seconds"),
                                      "modelo": lap.lap_id, "modelo_s": ref["lap_seconds"], "linhas": lado_a_lado},
    }
    if args.handoff:
        destino = Path(f"{args.handoff}_conferencia.json")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(conferencia, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")
        print(f"-> {destino}")
    print(json.dumps({k: conferencia[k] for k in ("tempo", "distancia")}, indent=1, ensure_ascii=False, default=_padrao))
    print("trechos batem:", conferencia["trechos"]["batem"], "dif max ms", conferencia["trechos"]["diferenca_max_ms"])
    print("mesma geometria:", pista["mesma_geometria"], "superficie igual:", pista["superficie_igual"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
