"""Diagnostico da M1 v2: onde ela erra e por que (pedido 48; secao 7.5 da M1). So analise.

    python -m ml.scripts.m1_diagnostico dados        # B: os canais extras das gravacoes (so leitura)
    python -m ml.scripts.m1_diagnostico reproduzir   # B: a fase de teste do 46, a conferencia e os casos
    python -m ml.scripts.m1_diagnostico analisar     # C: as analises, o JSON e as figuras

Nenhum modelo novo e ajustado. Os Processos Gaussianos do pedido 46 nao foram
salvos; eles sao reajustados pela propria `experimento_v2.fase_teste`, sem
mudanca (mesmo codigo, mesma amostra, semente 46). Tudo o que sai fica em
`data/diagnostico_m1/` (fora do git), e as gravacoes, `data/ml` e `data/cache`
so sao lidos. Os arquivos da M1 v2 (sufixo `_v2`) nao sao reescritos.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data.recordings import RawLap, _is_new_lap  # noqa: E402
from ml.data.samples import number  # noqa: E402
from ml.data.store_v2 import file_entry, git_commit, store_v2_meta  # noqa: E402
from ml.modelo_carro import dados as D  # noqa: E402
from ml.preprocessing.alignment import align_lap  # noqa: E402
from ml.preprocessing.cleaning import clean_lap  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402

PEDIDO = 48
SESSOES_DEPOIS = ("2026-10-24_13-26-12_vhe_interlagos", "2026-10-24_13-43-32_vhe_interlagos",
                  "2026-11-01_19-47-03_vhe_interlagos")
SESSAO_0111 = "2026-11-01_19-47-03_vhe_interlagos"
# Contexto, item 4: as voltas de 01/11 com as saidas de traseira, pelo tempo no session-index.
VOLTAS_EPISODIOS = {3: 285.743, 4: 224.219, 10: 145.948, 11: 159.678}

EXTRAS = ("ride_height_f", "ride_height_r",
          "slip_fl", "slip_fr", "slip_rl", "slip_rr",
          "susp_fl", "susp_fr", "susp_rl", "susp_rr",
          "drs", "fuel", "air_temp", "road_temp", "ia")
# As colunas guardadas das amostras cruas (para o atraso, C.3, e os episodios, C.8).
CRUAS = ("lap_time_s", "x", "z", "heading", "s", "velocity_long", "velocity_lat", "yaw_rate", "steer_angle",
         "throttle", "brake", "lateral_g", "longitudinal_g", "speed_kmh", *EXTRAS)


def raiz() -> Path:
    return config.repo_root() / "data" / "diagnostico_m1"


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=_padrao), encoding="utf-8")


def _padrao(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return str(v)


def jogo_aberto() -> bool:
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq acs.exe"], capture_output=True, text=True).stdout
    return "acs.exe" in out.lower()


def conferir_jogo() -> None:
    if jogo_aberto():
        raise SystemExit("o acs.exe esta aberto: o Eduardo pode estar no jogo. Espere e rode de novo.")


# ------------------------------------------------------------ leitura ---

def _lista(values, i):
    try:
        return number(values[i])
    except (TypeError, IndexError, KeyError):
        return None


def linha_diag(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """A linha da M1 (`linha_m1`, sem mudanca) mais os canais extras do diagnostico."""
    row = D.linha_m1(envelope)
    sample = envelope.get("sample") if isinstance(envelope.get("sample"), Mapping) else envelope
    physics = sample.get("carPhysics") if isinstance(sample.get("carPhysics"), Mapping) else {}
    tyres = physics.get("tyres") if isinstance(physics.get("tyres"), Mapping) else {}
    susp = physics.get("suspension") if isinstance(physics.get("suspension"), Mapping) else {}
    state = physics.get("carState") if isinstance(physics.get("carState"), Mapping) else {}
    env = physics.get("environment") if isinstance(physics.get("environment"), Mapping) else {}
    controls = physics.get("controls") if isinstance(physics.get("controls"), Mapping) else {}
    ride = susp.get("rideHeight")
    row["ride_height_f"], row["ride_height_r"] = _lista(ride, 0), _lista(ride, 1)
    for i, w in enumerate(D.WHEELS):
        row[f"slip_{w}"] = _lista(tyres.get("wheelSlip"), i)
        row[f"susp_{w}"] = _lista(susp.get("suspensionTravel"), i)
    drs = state.get("drs")
    row["drs"] = None if drs is None else float(bool(drs))
    row["fuel"] = number(state.get("fuel"))
    row["air_temp"] = number(env.get("airTemp"))
    row["road_temp"] = number(env.get("roadTemp"))
    ia = controls.get("isAIControlled")
    row["ia"] = None if ia is None else float(bool(ia))
    return row


def iter_voltas_diag(session, min_samples: int = 2) -> Iterator[RawLap]:
    """O `iter_voltas_m1` do pedido 46, linha a linha igual, com `linha_diag` no lugar de `linha_m1`."""
    rows: List[Dict[str, Any]] = []
    corrupt = 0
    lap_number: Optional[int] = None
    sequence = 0
    previous: Dict[str, Any] = {}

    def build(number_value, collected, bad, order):
        if number_value is None or len(collected) < min_samples:
            return None
        return RawLap(session_id=session.session_id, lap_number=int(number_value), track=session.track,
                      frame=pd.DataFrame(collected), sequence=order, corrupt_lines=bad)

    with session.player_stream.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1
                continue
            row = linha_diag(envelope)
            if row.get("lap_number") is None:
                corrupt += 1
                continue
            if previous and _is_new_lap(row, previous):
                lap = build(lap_number, rows, corrupt, sequence)
                if lap is not None:
                    yield lap
                sequence += 1
                rows, corrupt = [], 0
                lap_number = int(row["lap_number"])
            elif lap_number is None:
                lap_number = int(row["lap_number"])
            rows.append(row)
            previous = row
    lap = build(lap_number, rows, corrupt, sequence)
    if lap is not None:
        yield lap


def processar_volta_diag(lap: RawLap, geometry):
    """O `processar_volta` do 46, com as colunas extras na grade, e as amostras cruas mantidas."""
    cleaned, _ = clean_lap(lap.frame)
    aligned, _ = align_lap(cleaned, geometry)
    kept, _ = D.descartar_repetidas(aligned)
    t = kept["lap_time_s"].to_numpy(dtype=float)
    pieces = D.cortar_trechos(t, D.GAP_S)
    blocks = []
    for number_, (a, b) in enumerate(pieces):
        block = D.reamostrar(kept.iloc[a:b], columns=(*D.COLUNAS, *EXTRAS), dt=D.DT)
        if len(block) < 2:
            continue
        block.insert(0, "trecho", f"{lap.lap_id}/{number_:03d}")
        block.insert(0, "lap_id", lap.lap_id)
        block.insert(0, "session_id", lap.session_id)
        blocks.append(block)
    frame = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame()
    raw = kept[[c for c in CRUAS if c in kept.columns]].copy()
    raw.insert(0, "lap_id", lap.lap_id)
    return frame, raw


def cmd_dados(args) -> int:
    """Os canais extras na mesma grade das grades do 46 (conferida coluna a coluna) e as amostras cruas."""
    conferir_jogo()
    started = time.time()
    out_dir = raiz()
    out_dir.mkdir(parents=True, exist_ok=True)
    geometry = load_geometry()
    meta = store_v2_meta()
    table = pd.read_parquet(config.artifacts_root() / "retreino_lstm" / "voltas_tabela.parquet")
    report = {"pedido": PEDIDO, "parte": "B, os canais extras", "commit": git_commit(),
              "geometry_id": geometry.geometry_id, "sessoes": {}}
    sessoes = list(D.SESSOES_M1) + list(SESSOES_DEPOIS)
    for session_id in sessoes:
        t0 = time.time()
        session = D.sessao_por_id(session_id)
        if session_id in D.SESSOES_M1:
            wanted = {lap["lap_id"]: int(lap["raw_samples"]) for lap in meta["laps"] if lap["session_id"] == session_id}
            ref = pd.read_parquet(D.raiz_dados() / f"grade_{session_id}.parquet")
        else:
            wanted = {k: None for k in table.loc[table["gravacao"] == session_id, "lap_id"]}
            ref = pd.read_parquet(D.raiz_dados() / f"grade_depois_{session_id}.parquet")
        grids, raws, episodios = [], [], {}
        for lap in iter_voltas_diag(session):
            keep = lap.lap_id in wanted
            # As voltas dos episodios sao achadas pelo tempo (o `lap_number` das amostras pode
            # estar atrasado em relacao ao `session-index.json`).
            tempo = float(pd.to_numeric(lap.frame["lap_time_s"], errors="coerce").max())
            ep_n = [n for n, alvo in VOLTAS_EPISODIOS.items() if abs(tempo - alvo) < 0.002] \
                if session_id == SESSAO_0111 else []
            ep = bool(ep_n)
            if not (keep or ep):
                continue
            if keep and wanted[lap.lap_id] is not None and wanted[lap.lap_id] != lap.sample_count:
                raise SystemExit(f"{lap.lap_id}: o corte nao bate com o store ({lap.sample_count} != {wanted[lap.lap_id]})")
            frame, raw = processar_volta_diag(lap, geometry)
            if keep:
                grids.append(frame)
                raws.append(raw)
            if ep:
                n = ep_n[0]
                raw_ep = raw.copy()
                raw_ep.insert(1, "volta_session_index", n)
                episodios[n] = {"lap_id": lap.lap_id, "lap_number_das_amostras": lap.lap_number, "tempo_s": tempo,
                                "amostras": lap.sample_count, "valida_no_store": keep, "_raw": raw_ep, "_grade": frame}
        grid = pd.concat(grids, ignore_index=True)
        # A conferencia: a mesma grade do 46, chave a chave e coluna a coluna.
        same_keys = (len(grid) == len(ref) and np.array_equal(grid["trecho"].to_numpy(), ref["trecho"].to_numpy())
                     and np.array_equal(grid["k"].to_numpy(), ref["k"].to_numpy()))
        diffs = {}
        if same_keys:
            for c in D.COLUNAS:
                a, b = grid[c].to_numpy(dtype=float), ref[c].to_numpy(dtype=float)
                both = np.isfinite(a) & np.isfinite(b)
                diffs[c] = {"max_abs": float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0,
                            "nan_iguais": bool(np.array_equal(np.isfinite(a), np.isfinite(b)))}
        ok = same_keys and all(d["max_abs"] <= 1e-9 and d["nan_iguais"] for d in diffs.values())
        if not ok:
            _json(out_dir / "dados_relatorio.json", {**report, "parado": session_id, "diferencas": diffs,
                                                     "mesmas_chaves": same_keys})
            raise SystemExit(f"{session_id}: a grade refeita nao bate com a do pedido 46")
        cols = ["session_id", "lap_id", "trecho", "k", *EXTRAS]
        grid[cols].to_parquet(out_dir / f"extra_{session_id}.parquet", index=False)
        pd.concat(raws, ignore_index=True).to_parquet(out_dir / f"cru_{session_id}.parquet", index=False)
        entry = {"voltas": len(grids), "passos": len(grid), "igual_a_grade_do_46": ok,
                 "preenchido": {c: float(np.mean(np.isfinite(grid[c].to_numpy(dtype=float)))) for c in EXTRAS},
                 "lidos": file_entry(session.player_stream), "tempo_s": round(time.time() - t0, 1)}
        if session_id == SESSAO_0111:
            entry["episodios"] = {}
            for n, ep in sorted(episodios.items()):
                ep["_raw"].to_parquet(out_dir / f"episodio_volta{n}_cru.parquet", index=False)
                ep["_grade"].to_parquet(out_dir / f"episodio_volta{n}_grade.parquet", index=False)
                entry["episodios"][str(n)] = {k: v for k, v in ep.items() if not k.startswith("_")}
            faltam = sorted(set(VOLTAS_EPISODIOS) - set(episodios))
            if faltam:
                raise SystemExit(f"voltas de 01/11 nao achadas pelo tempo: {faltam}")
        report["sessoes"][session_id] = entry
        print(session_id, entry["voltas"], "voltas", entry["passos"], "passos", entry["tempo_s"], "s", flush=True)
    report["tempo_s"] = round(time.time() - started, 1)
    _json(out_dir / "dados_relatorio.json", report)
    return 0


# --------------------------------------------------------- reproducao ---

HORIZONTES_DIAG = (1, 2, 5, 10, 20)
TOLERANCIA = 0.002


def _derivada_volante(frame: pd.DataFrame) -> np.ndarray:
    from ml.modelo_carro import convencoes as C
    return C.derivada(frame, "steer")


def _tercis(rate: np.ndarray) -> List[float]:
    a = np.abs(rate[np.isfinite(rate)])
    return [float(v) for v in np.percentile(a, [100.0 / 3.0, 200.0 / 3.0])]


def _curvas():
    from ml.track.corners import detect_corners
    geometry = load_geometry()
    return detect_corners(geometry), geometry.length


def curva_e_fase(s: np.ndarray, corners, length: float):
    """O rotulo da curva (C01 a C14) e a fase (entrada ate o apice, saida depois) de cada ponto."""
    s = np.asarray(s, dtype=float)
    curva = np.full(s.shape, "fora", dtype=object)
    fase = np.full(s.shape, "fora", dtype=object)
    for c in corners:
        span = np.mod(c.end_s - c.start_s, length)
        pos = np.mod(s - c.start_s, length)
        inside = pos <= span
        curva[inside] = c.label[:3]
        apex = np.mod(c.apex_s - c.start_s, length)
        fase[inside & (pos <= apex)] = "entrada"
        fase[inside & (pos > apex)] = "saida"
    return curva, fase


def um_passo_de_todos(frame: pd.DataFrame, p, corr):
    """A previsao de um passo da fisica v2 e da M1 v2 a partir de cada passo gravado (NaN no fim do trecho)."""
    from ml.modelo_carro import fisica_v2 as F2
    from ml.modelo_carro import validacao as V
    S = frame[list(V.ESTADO)].to_numpy(dtype=float)
    U = frame[list(V.ENTRADA)].to_numpy(dtype=float)
    tr = frame["trecho"].to_numpy()
    nxt = np.zeros(len(frame), dtype=bool)
    nxt[:-1] = tr[:-1] == tr[1:]
    Ustep = np.full_like(U, np.nan)
    Ustep[:-1] = 0.5 * (U[:-1] + U[1:])
    ok = nxt & np.isfinite(S).all(1) & np.isfinite(Ustep).all(1)
    ok[:-1] &= np.isfinite(S[1:]).all(1)
    r1 = np.full_like(S, np.nan)
    m1 = np.full_like(S, np.nan)
    phys = F2.passo(S[ok], Ustep[ok], p)
    mean, _, _ = corr.prever(S[ok], Ustep[ok], com_desvio=False)
    r1[ok] = phys
    m1[ok] = phys + mean
    S1 = np.full_like(S, np.nan)
    S1[:-1] = S[1:]
    S1[~ok] = np.nan
    return {"ok": ok, "S1": S1, "R1": r1, "M1": m1, "Ustep": Ustep}


def detalhar(test: str, modelos, extra: pd.DataFrame, conv, corners, length: float, ref_casos: Dict[str, np.ndarray]):
    """Os casos da rodada, com o caminho inteiro e o que o diagnostico precisa no inicio de cada um."""
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro import fisica as F
    from ml.modelo_carro import fisica_v2 as F2
    from ml.modelo_carro import validacao as V
    p, _, corr, sigma, frame, train = modelos
    frame = frame.reset_index(drop=True)
    if not (np.array_equal(frame["trecho"].to_numpy(), extra["trecho"].to_numpy())
            and np.array_equal(frame["k"].to_numpy(), extra["k"].to_numpy())):
        raise SystemExit(f"{test}: os canais extras nao estao na mesma grade")
    for c in EXTRAS:
        frame[c] = extra[c].to_numpy()
    frame["taxa_volante"] = _derivada_volante(frame)
    one = um_passo_de_todos(frame, p, corr)

    cs = V.casos(frame, conv)
    m1 = F2.malha_aberta(cs.S0, cs.U, p, corr)
    r1 = F2.malha_aberta(cs.S0, cs.U, p)
    r0 = F.persistencia(cs.S0, V.H_MAX)
    conferencia = {name: float(np.max(np.abs((pred[:, 10] - cs.S[:, 10]) - ref_casos[f"err_{name}_10"])))
                   for name, pred in (("M1", m1), ("R1", r1), ("R0", r0))}

    row = {(t, int(k)): i for i, (t, k) in enumerate(zip(frame["trecho"].to_numpy(), frame["k"].to_numpy()))}
    i0 = np.array([row[(t, int(k))] for t, k in zip(cs.trecho, cs.k0)])
    path = i0[:, None] + np.arange(V.H_MAX + 1)[None, :]
    if not (np.array_equal(frame["trecho"].to_numpy()[path[:, -1]], cs.trecho)
            and np.array_equal(frame["k"].to_numpy()[path[:, -1]], cs.k0 + V.H_MAX)):
        raise SystemExit(f"{test}: o caminho dos casos nao e contiguo na grade")
    inc = {name: DG.soma_de_incrementos(cs.S, one[name][path[:, :-1]]) for name in ("M1", "R1")}

    f = frame.iloc[i0].reset_index(drop=True)
    alpha = DG.deriva_rodas(f["vx"], f["vy"], f["r"], f["steer"], p.a, p.b, p.t_f, p.t_r, p.k_delta)
    load_true = f[[f"wheel_load_{w}" for w in D.WHEELS]].to_numpy(dtype=float)
    load_pred = F2.cargas(f["vx"].to_numpy(float), f["a_x"].to_numpy(float), f["a_y"].to_numpy(float), p) * p.m
    curva, fase = curva_e_fase(f["s"].to_numpy(float), corners, length)
    out = {"rodada": np.full(len(cs), test, dtype=object), "sessao": cs.session, "volta": cs.lap,
           "trecho": cs.trecho, "k0": cs.k0, "t0": f["t"].to_numpy(float), "s0": cs.s0, "curva": curva, "fase": fase,
           "regime": cs.regime, "faixa": V.faixa_de_velocidade(cs.vx_kmh),
           "vx": cs.S0[:, 0], "vy": cs.S0[:, 1], "r": cs.S0[:, 2],
           "steer": f["steer"].to_numpy(float), "T": f["T"].to_numpy(float), "B": f["B"].to_numpy(float),
           "a_x": f["a_x"].to_numpy(float), "a_y": f["a_y"].to_numpy(float), "taxa_volante": f["taxa_volante"].to_numpy(float),
           "indice": ref_casos["indice"], "nao_conclusivo": ref_casos["nao_conclusivo"]}
    for w, wheel in enumerate(D.WHEELS):
        out[f"deriva_{wheel}"] = alpha[:, w]
        out[f"carga_{wheel}"] = load_true[:, w]
        out[f"carga_prevista_{wheel}"] = load_pred[:, w]
    for c in EXTRAS:
        out[c] = f[c].to_numpy(float)
    preds = {"M1": m1, "R1": r1, "R0": r0, "M1inc": inc["M1"], "R1inc": inc["R1"]}
    for name, pred in preds.items():
        for h in HORIZONTES_DIAG:
            e = (pred[:, h] - cs.S[:, h]) / sigma
            for q, g in enumerate(V.ESTADO):
                out[f"e_{name}_{h}_{g}"] = e[:, q]
    # Os passos da sessao de teste, para a carga (C.5) e a memoria (C.7).
    passos = frame[["session_id", "lap_id", "trecho", "k", "t", "s", "vx", "vy", "r", "steer", "T", "B", "a_x", "a_y",
                    "taxa_volante", *[f"wheel_load_{w}" for w in D.WHEELS], *EXTRAS]].copy()
    from ml.modelo_carro.correcao import regimes
    passos["regime"] = regimes(frame["B"].to_numpy(float), frame["a_y"].to_numpy(float), frame["T"].to_numpy(float),
                               frame["a_x"].to_numpy(float))
    pc, pf = curva_e_fase(frame["s"].to_numpy(float), corners, length)
    passos["curva"], passos["fase"] = pc, pf
    lp = F2.cargas(frame["vx"].to_numpy(float), frame["a_x"].to_numpy(float), frame["a_y"].to_numpy(float), p) * p.m
    for w, wheel in enumerate(D.WHEELS):
        passos[f"carga_prevista_{wheel}"] = lp[:, w]
    alpha_all = DG.deriva_rodas(frame["vx"], frame["vy"], frame["r"], frame["steer"], p.a, p.b, p.t_f, p.t_r, p.k_delta)
    for w, wheel in enumerate(D.WHEELS):
        passos[f"deriva_{wheel}"] = alpha_all[:, w]
    for q, g in enumerate(V.ESTADO):
        passos[f"res_M1_{g}"] = (one["S1"][:, q] - one["M1"][:, q]) / sigma[q]
        passos[f"res_R1_{g}"] = (one["S1"][:, q] - one["R1"][:, q]) / sigma[q]
    passos["rodada"] = test
    tercis = _tercis(_derivada_volante(train))
    return out, passos, conferencia, tercis


def _comparar(a, b, path="") -> List[tuple]:
    """Todos os numeros de `a` contra os de `b`, com o caminho de cada um."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            if k in b:
                out += _comparar(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out += _comparar(x, y, f"{path}[{i}]")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if np.isfinite(a) and np.isfinite(b):
            out.append((path, float(a), float(b), abs(float(a) - float(b))))
    return out


def cmd_reproduzir(args) -> int:
    """A fase de teste do pedido 46, pela propria funcao dele, a conferencia com a secao 7.3 e os casos."""
    conferir_jogo()
    from ml.modelo_carro import experimento as X
    from ml.modelo_carro import experimento_v2 as X2
    from ml.modelo_carro import validacao as V
    from ml.scripts import m1_modelo_carro as M
    started = time.time()
    out_dir = raiz()
    geo, conv, v1 = M._geo_v2(), M._convencoes(), M._v1_por_sessao()
    grades = {s: pd.read_parquet(M.grade_path(s)) for s in D.SESSOES_M1}
    treino_path = D.raiz_dados() / "rodadas_treino_v2.json"
    treino = json.loads(treino_path.read_text(encoding="utf-8"))
    ref_json_path = D.raiz_dados() / "validacao_v2.json"
    ref = json.loads(ref_json_path.read_text(encoding="utf-8"))
    ref_cases_path = D.raiz_dados() / "validacao_casos_v2.parquet"
    ref_cases = pd.read_parquet(ref_cases_path)
    v1_cases = pd.read_parquet(D.raiz_dados() / "validacao_casos.parquet")
    corners, length = _curvas()
    partes, infos, casos, passos, conf, tercis = [], [], [], [], {}, {}
    offset = 0
    for rodada in treino["rodadas"]:
        if jogo_aberto():
            raise SystemExit("o acs.exe abriu no meio da reproducao; parado para o Eduardo jogar")
        test = rodada["sessao_de_teste"]
        print(f"rodada sem {test}", flush=True)
        t0 = time.time()
        out = X2.fase_teste(rodada, grades, conv, geo, v1[test])
        partes.append(out["casos"])
        infos.append(out["info"])
        p, p1, corr, sigma, frame, train = out["_modelos"]
        with open(out_dir / f"modelos_{test}.pkl", "wb") as handle:
            pickle.dump({"sessao_de_teste": test, "p": p, "p1": p1, "corr": corr, "sigma": sigma,
                         "corte": out["info"]["corte"], "sessoes_de_treino": rodada["sessoes_de_treino"]}, handle)
        extra = pd.read_parquet(out_dir / f"extra_{test}.parquet")
        det, pas, c, terc = detalhar(test, out["_modelos"], extra, conv, corners, length, out["casos"])
        n = len(det["volta"])
        rc = ref_cases.iloc[offset:offset + n]
        c["sq_contra_o_46"] = {m: float(np.max(np.abs(rc[f"sq_{m}_10"].to_numpy(float) - out["casos"][f"sq_{m}_10"])))
                               for m in ("M1", "R1", "R0", "R1v1")}
        offset += n
        conf[test], tercis[test] = c, terc
        casos.append(pd.DataFrame(det))
        passos.append(pas)
        print(f"  {n} casos em {time.time() - t0:.0f} s; conferencia {c}", flush=True)
    cases = X.juntar(partes)
    same = (len(v1_cases) == len(cases["volta"])
            and np.array_equal(v1_cases["volta"].to_numpy().astype(str), cases["volta"].astype(str)))
    v1c = v1_cases if same else None
    nc = cases["nao_conclusivo"]
    novo = {"veredito": X.veredito(cases), "horizontes": X.resumo_horizontes(cases),
            "horizontes_so_conclusivos": X.resumo_horizontes(cases, ~nc),
            "por_sessao": X2.lado_a_lado(cases, v1c, "sessao"), "por_regime": X2.lado_a_lado(cases, v1c, "regime"),
            "por_faixa": X2.lado_a_lado(cases, v1c, "faixa"), "nao_conclusivo": X2.nao_conclusivo(cases),
            "lado_a_lado": {hn: X2.lado_a_lado(cases, v1c, None, hh) for hn, hh in V.HORIZONTES.items()}}
    diffs = _comparar(novo, {k: ref[k] for k in novo})
    maior = max(diffs, key=lambda d: d[3]) if diffs else ("", 0, 0, 0.0)
    resumo = {"numeros_comparados": len(diffs), "maior_diferenca": {"onde": maior[0], "46": maior[2], "48": maior[1],
                                                                   "diferenca": maior[3]},
              "acima_da_tolerancia": [{"onde": d[0], "46": d[2], "48": d[1], "diferenca": d[3]}
                                      for d in diffs if d[3] > TOLERANCIA],
              "criterio_1": novo["veredito"]["criterios"][0]["valor"], "criterio_2": novo["veredito"]["criterios"][1]["valor"]}
    payload = {"pedido": PEDIDO, "parte": "B, a reproducao", "commit": git_commit(),
               "comando": "python -m ml.scripts.m1_diagnostico reproduzir",
               "lidos": {"rodadas_treino_v2.json": file_entry(treino_path), "validacao_v2.json": file_entry(ref_json_path),
                         "validacao_casos_v2.parquet": file_entry(ref_cases_path)},
               "rodadas": infos, "conferencia_por_rodada": conf, "tercis_taxa_volante": tercis,
               "conferencia": resumo, "tempo_s": round(time.time() - started, 1)}
    _json(out_dir / "reproducao.json", payload)
    if resumo["acima_da_tolerancia"]:
        print("PARADO: diferenca acima de 0,002", json.dumps(resumo["maior_diferenca"]))
        return 2
    pd.concat(casos, ignore_index=True).to_parquet(out_dir / "casos.parquet", index=False)
    pd.concat(passos, ignore_index=True).to_parquet(out_dir / "passos.parquet", index=False)
    print("reproducao conferida:", resumo["numeros_comparados"], "numeros; maior diferenca", maior[3])
    return 0


# ------------------------------------------------------------ analises ---

G = D.G
RODADA_INFO = "2026-10-21_20-30-54_vhe_interlagos"   # a rodada da C.4 do 46 (treinada de 15/10 a 18/10)
ESTADO = ("vx", "vy", "r")


def _modelos(test: str) -> dict:
    with open(raiz() / f"modelos_{test}.pkl", "rb") as handle:
        return pickle.load(handle)


def _sq(frame: pd.DataFrame, name: str, h: int) -> np.ndarray:
    return sum(frame[f"e_{name}_{h}_{g}"].to_numpy(float) ** 2 for g in ESTADO)


def _grupo_tabela(cases: pd.DataFrame, mask: np.ndarray, grupos: np.ndarray, ordem=None) -> List[dict]:
    """Por grupo: casos, skill da M1 v2 contra R0 em 0,5 s, a parte no erro do conjunto e o skill da fisica v2."""
    from ml.modelo_carro import diagnostico as DG
    sq_m, sq_r, sq_f = cases["sq_M1_10"].to_numpy(), cases["sq_R0_10"].to_numpy(), cases["sq_R1_10"].to_numpy()
    total = sq_m[mask].sum()
    names = ordem if ordem is not None else sorted(set(np.asarray(grupos)[mask].tolist()))
    rows = []
    for g in names:
        m = mask & (np.asarray(grupos) == g)
        if not m.any():
            rows.append({"grupo": g, "casos": 0})
            continue
        rows.append({"grupo": g, "casos": int(m.sum()), "skill_M1_v2_contra_R0": DG.skill(sq_m, sq_r, m),
                     "skill_fisica_v2_contra_R0": DG.skill(sq_f, sq_r, m),
                     "parte_no_erro_pct": float(100.0 * sq_m[m].sum() / total),
                     "erro_M1_v2": DG.erro(sq_m, m), "erro_R0": DG.erro(sq_r, m)})
    return rows


def carregar_casos() -> pd.DataFrame:
    cases = pd.read_parquet(raiz() / "casos.parquet")
    for name in ("M1", "R1", "R0", "M1inc", "R1inc"):
        for h in HORIZONTES_DIAG:
            cases[f"sq_{name}_{h}"] = _sq(cases, name, h)
    alpha_f = 0.5 * (cases["deriva_fl"] + cases["deriva_fr"])
    alpha_r = 0.5 * (cases["deriva_rl"] + cases["deriva_rr"])
    cases["deriva_dianteira_graus"] = np.degrees(np.abs(alpha_f))
    cases["deriva_traseira_graus"] = np.degrees(np.abs(alpha_r))
    return cases


def c1_acaso(cases: pd.DataFrame) -> dict:
    from ml.modelo_carro import diagnostico as DG
    sq_m, sq_r, lap = cases["sq_M1_10"].to_numpy(), cases["sq_R0_10"].to_numpy(), cases["volta"].to_numpy()

    def ic(mask):
        out = DG.bootstrap_por_volta(sq_m[mask], sq_r[mask], lap[mask], n=10000, seed=48)
        out["0,50_dentro"] = bool(out["p2_5"] <= 0.5 <= out["p97_5"])
        return out

    allm = np.ones(len(cases), dtype=bool)
    return {"geral": ic(allm), "curvas": ic(cases["regime"].to_numpy() == "curva"),
            "por_sessao": {s: ic(cases["sessao"].to_numpy() == s) for s in D.SESSOES_M1},
            "nota": "nao muda o veredito: o criterio e o valor pontual (ADR 0022)"}


def c2_onde(cases: pd.DataFrame, tercis: Dict[str, List[float]]) -> dict:
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro import validacao as V
    regime = cases["regime"].to_numpy()
    steer_b = DG.faixa(np.abs(cases["steer"].to_numpy()), DG.FAIXAS_STEER)
    ay_b = DG.faixa(np.abs(cases["a_y"].to_numpy()) / G, DG.FAIXAS_AY_G)
    df_b = DG.faixa(cases["deriva_dianteira_graus"].to_numpy(), DG.FAIXAS_DERIVA)
    dr_b = DG.faixa(cases["deriva_traseira_graus"].to_numpy(), DG.FAIXAS_DERIVA)
    rate = np.abs(cases["taxa_volante"].to_numpy())
    terc = np.full(len(cases), "", dtype=object)
    for test, (t1, t2) in tercis.items():
        m = cases["rodada"].to_numpy() == test
        terc[m & (rate < t1)] = "tercil de baixo"
        terc[m & (rate >= t1) & (rate < t2)] = "tercil do meio"
        terc[m & (rate >= t2)] = "tercil de cima"
    out = {"tercis_da_taxa_do_volante_rad_s": tercis}
    vel = [n for *_, n in V.FAIXAS_KMH]
    for reg in ("curva", "freio e volante juntos"):
        m = regime == reg
        sq_m = cases["sq_M1_10"].to_numpy()
        part = {}
        for g in ESTADO:
            e_m = cases[f"e_M1_10_{g}"].to_numpy()[m]
            e_r = cases[f"e_R0_10_{g}"].to_numpy()[m]
            part[g] = {"parte_no_erro_pct": float(100.0 * np.sum(e_m ** 2) / sq_m[m].sum()),
                       "skill": float(1.0 - np.sqrt(np.mean(e_m ** 2)) / np.sqrt(np.mean(e_r ** 2)))}
        out[reg] = {
            "casos": int(m.sum()), "skill": DG.skill(sq_m, cases["sq_R0_10"].to_numpy(), m),
            "por_steer": _grupo_tabela(cases, m, steer_b, [n for *_, n in DG.FAIXAS_STEER]),
            "por_velocidade": _grupo_tabela(cases, m, cases["faixa"].to_numpy(), vel),
            "por_a_y": _grupo_tabela(cases, m, ay_b, [n for *_, n in DG.FAIXAS_AY_G]),
            "por_deriva_dianteira": _grupo_tabela(cases, m, df_b, [n for *_, n in DG.FAIXAS_DERIVA]),
            "por_deriva_traseira": _grupo_tabela(cases, m, dr_b, [n for *_, n in DG.FAIXAS_DERIVA]),
            "por_taxa_do_volante": _grupo_tabela(cases, m, terc, ["tercil de baixo", "tercil do meio", "tercil de cima"]),
            "por_curva": _grupo_tabela(cases, m, cases["curva"].to_numpy(),
                                       [f"C{i:02d}" for i in range(1, 15)] + ["fora"]),
            "por_fase": _grupo_tabela(cases, m, cases["fase"].to_numpy(), ["entrada", "saida", "fora"]),
            "por_grandeza": part,
            "mapa_steer_velocidade": {sb: {vb: _grupo_tabela(cases, m & (steer_b == sb), cases["faixa"].to_numpy(), [vb])[0]
                                           for vb in vel} for *_, sb in DG.FAIXAS_STEER},
        }
        # A parte no mapa e a da celula no erro de todas as curvas.
        for sb, row in out[reg]["mapa_steer_velocidade"].items():
            for vb, cell in row.items():
                if cell.get("casos"):
                    sel = m & (steer_b == sb) & (cases["faixa"].to_numpy() == vb)
                    cell["parte_no_erro_pct"] = float(100.0 * sq_m[sel].sum() / sq_m[m].sum())
    curva = regime == "curva"
    out["skill_que_as_curvas_precisariam"] = DG.skill_necessario(cases["sq_M1_10"].to_numpy(), cases["sq_R0_10"].to_numpy(), curva)
    out["_bandas"] = {"steer": steer_b, "deriva_dianteira": df_b, "deriva_traseira": dr_b}
    return out


def decidir_h1(c2: dict) -> dict:
    out = {}
    for eixo in ("dianteira", "traseira"):
        rows = {r["grupo"]: r for r in c2["curva"][f"por_deriva_{eixo}"]}
        low = rows["abaixo de 3°"]
        high = [rows[k] for k in ("6° a 8°", "8° a 10°", "acima de 10°") if rows[k].get("casos")]
        n_high = sum(r["casos"] for r in high)
        out[eixo] = {"casos_abaixo_de_3": low.get("casos", 0), "casos_acima_de_6": n_high,
                     "skill_abaixo_de_3": low.get("skill_M1_v2_contra_R0"),
                     "parte_acima_de_6_pct": float(sum(r["parte_no_erro_pct"] for r in high))}
    return out


def _skill_grupo(sq_m, sq_r, mask):
    from ml.modelo_carro import diagnostico as DG
    return DG.skill(sq_m, sq_r, mask) if mask.sum() else float("nan")


def h1_regra(cases: pd.DataFrame, c2: dict) -> dict:
    sq_m, sq_r = cases["sq_M1_10"].to_numpy(), cases["sq_R0_10"].to_numpy()
    curva = cases["regime"].to_numpy() == "curva"
    res = {}
    for eixo, col in (("dianteira", "deriva_dianteira_graus"), ("traseira", "deriva_traseira_graus")):
        a = cases[col].to_numpy()
        lo, hi = curva & (a < 3.0), curva & (a >= 6.0)
        s_lo, s_hi = _skill_grupo(sq_m, sq_r, lo), _skill_grupo(sq_m, sq_r, hi)
        parte = float(100.0 * sq_m[hi].sum() / sq_m[curva].sum())
        res[eixo] = {"casos_abaixo_de_3": int(lo.sum()), "casos_acima_de_6": int(hi.sum()), "skill_abaixo_de_3": s_lo,
                     "skill_acima_de_6": s_hi, "diferenca": s_lo - s_hi, "parte_acima_de_6_pct": parte,
                     "decide": bool(hi.sum() >= 100 and lo.sum() >= 100)}
    dec = [r for r in res.values() if r["decide"]]
    if not dec:
        label = "inconclusiva"
    elif any(r["diferenca"] >= 0.15 and r["parte_acima_de_6_pct"] >= 15.0 for r in dec):
        label = "apoiada"
    elif len(dec) == 2 and all(r["diferenca"] < 0.05 for r in res.values()):
        label = "nao apoiada"
    else:
        label = "inconclusiva"
    return {"eixos": res, "rotulo": label}


def _cru_modelo(raw: pd.DataFrame, conv, b: float, x_v: float) -> pd.DataFrame:
    out = pd.DataFrame({"lap_id": raw["lap_id"].to_numpy(), "t": raw["lap_time_s"].to_numpy(float)})
    r = conv.s_r * raw["yaw_rate"].to_numpy(float)
    out["vx"] = raw["velocity_long"].to_numpy(float)
    out["vy"] = conv.s_vy * raw["velocity_lat"].to_numpy(float) + (b - x_v) * r
    out["r"] = r
    out["steer"] = raw["steer_angle"].to_numpy(float)
    out["T"] = raw["throttle"].to_numpy(float)
    out["B"] = raw["brake"].to_numpy(float)
    out["s"] = raw["s"].to_numpy(float)
    for c in ("slip_fl", "slip_fr", "slip_rl", "slip_rr"):
        out[c] = raw[c].to_numpy(float) if c in raw else np.nan
    return out


ANTES, DEPOIS, PASSO_FINO = 100, 240, 0.005
LAGS = np.arange(-20, 81)          # -0,1 a +0,4 s, em 5 ms
JANELA = (-50, 150)                # -0,25 a +0,75 s
N_GRADE = (ANTES + DEPOIS) // 10   # 34 passos de 50 ms


def _taxa(x: np.ndarray) -> np.ndarray:
    return np.gradient(x, PASSO_FINO)


def c3_atraso(conv, geo, max_gap: float = 0.02) -> dict:
    """O atraso do volante para a guinada, nas entradas de curva das 5 sessoes.

    `max_gap` = 0,02 s e a regra do pedido; 0,0499 s (os trechos da secao 1.2) so informa.
    """
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro import fisica_v2 as F2
    from ml.modelo_carro import validacao as V
    series = ("gravado_5ms", "gravado_grade", "fisica_v2", "m1_v2")
    entries = []          # (sessao, volta, vx_kmh, {serie: (cxy, cxx, cyy)})
    cobertura = {}
    for test in D.SESSOES_M1:
        mod = _modelos(test)
        p, corr = mod["p"], mod["corr"]
        raw = pd.read_parquet(raiz() / f"cru_{test}.parquet")
        cru = _cru_modelo(raw, conv, p.b, geo["x_v"])
        S0, U, fine_r, fine_rate, meta = [], [], [], [], []
        gaps, longest = [], []
        for lap_id, lap in cru.groupby("lap_id", sort=False):
            t = lap["t"].to_numpy()
            gaps.append(np.diff(t))
            segs = DG.segmentos(t, max_gap)
            longest.append(max((t[b - 1] - t[a] for a, b in segs), default=0.0))
            for a, b in segs:
                if t[b - 1] - t[a] < (ANTES + DEPOIS) * PASSO_FINO + 0.1:
                    continue
                grid, cols = DG.reamostrar_fino(t[a:b], {c: lap[c].to_numpy()[a:b] for c in ("vx", "vy", "r", "steer", "T", "B")})
                for i in DG.entradas_de_curva(np.abs(cols["steer"]), antes=ANTES, depois=DEPOIS):
                    gi = i - ANTES + 10 * np.arange(N_GRADE + 1)
                    S0.append([cols["vx"][gi[0]], cols["vy"][gi[0]], cols["r"][gi[0]]])
                    u = np.column_stack([cols["steer"][gi], cols["T"][gi], cols["B"][gi]])
                    U.append(0.5 * (u[:-1] + u[1:]))
                    seg = slice(i - ANTES, i + DEPOIS + 1)
                    fine_r.append({"r": cols["r"][seg], "r_grade": cols["r"][gi]})
                    fine_rate.append(_taxa(-cols["steer"][seg]))   # a roda vira -k_delta*steer: o sinal da guinada
                    meta.append((test, lap_id, float(cols["vx"][i] * 3.6)))
        g = np.concatenate(gaps)
        cobertura[test] = {"intervalos_acima_de_20ms": float(np.mean(g > 0.02)), "intervalo_p50_ms": float(1000 * np.median(g)),
                           "intervalo_p95_ms": float(1000 * np.percentile(g, 95)), "trecho_mais_longo_s": float(max(longest)),
                           "entradas": len(S0)}
        if not S0:
            continue
        S0, U = np.asarray(S0), np.asarray(U)
        r1 = F2.malha_aberta(S0, U, p)[:, :, 2]
        m1 = F2.malha_aberta(S0, U, p, corr)[:, :, 2]
        fine_t = np.arange(ANTES + DEPOIS + 1)
        grid_t = 10 * np.arange(N_GRADE + 1)
        for e in range(len(S0)):
            ys = {"gravado_5ms": fine_r[e]["r"],
                  "gravado_grade": np.interp(fine_t, grid_t, fine_r[e]["r_grade"]),
                  "fisica_v2": np.interp(fine_t, grid_t, r1[e]),
                  "m1_v2": np.interp(fine_t, grid_t, m1[e])}
            x = fine_rate[e]
            win = slice(ANTES + JANELA[0], ANTES + JANELA[1])
            sums = {k: DG.correlacao_cruzada(x, _taxa(y), LAGS, win) for k, y in ys.items()}
            entries.append((*meta[e], sums))
        print(f"  C.3 {test[:19]}: {len(S0)} entradas", flush=True)
    lags_s = LAGS * PASSO_FINO
    from ml.modelo_carro.validacao import FAIXAS_KMH
    out = {"intervalo_maximo_s": max_gap, "entradas": len(entries), "cobertura_das_amostras_cruas": cobertura, "faixas": {}}
    rng_seed = 48
    for low, high, name in FAIXAS_KMH:
        sel = [e for e in entries if low <= e[2] < high]
        row = {"entradas": len(sel), "vx_media_m_s": float(np.mean([e[2] for e in sel]) / 3.6) if sel else float("nan")}
        if len(sel) < 3:
            out["faixas"][name] = row
            continue
        laps = sorted({e[1] for e in sel})
        lap_index = {l: i for i, l in enumerate(laps)}
        per_lap = {s: (np.zeros((len(laps), LAGS.size)), np.zeros(len(laps)), np.zeros((len(laps), LAGS.size))) for s in series}
        for e in sel:
            li = lap_index[e[1]]
            for s in series:
                cxy, cxx, cyy = e[3][s]
                per_lap[s][0][li] += cxy
                per_lap[s][1][li] += cxx
                per_lap[s][2][li] += cyy
        for s in series:
            lag, rho = DG.atraso_somado(*per_lap[s], lags_s)
            row[f"atraso_{s}_ms"] = 1000.0 * lag
            row[f"correlacao_pico_{s}"] = float(np.max(rho))
            row[f"_rho_{s}"] = rho
        rng = np.random.default_rng(rng_seed)
        draws = rng.integers(0, len(laps), size=(2000, len(laps)))
        extra = np.empty(2000)
        for d in range(2000):
            w = np.bincount(draws[d], minlength=len(laps)).astype(float)
            vals = {}
            for s in ("gravado_grade", "fisica_v2"):
                cxy, cxx, cyy = per_lap[s]
                rho = (w @ cxy) / np.sqrt((w @ cxx) * (w @ cyy))
                vals[s] = DG.pico_parabola(rho, float(lags_s[1] - lags_s[0]), float(lags_s[0]))
            extra[d] = vals["gravado_grade"] - vals["fisica_v2"]
        row["atraso_a_mais_ms"] = row["atraso_gravado_grade_ms"] - row["atraso_fisica_v2_ms"]
        row["atraso_a_mais_ic95_ms"] = [float(1000 * np.percentile(extra, 2.5)), float(1000 * np.percentile(extra, 97.5))]
        row["efeito_da_grade_no_gravado_ms"] = row["atraso_gravado_grade_ms"] - row["atraso_gravado_5ms_ms"]
        row["produto_atraso_a_mais_vezes_v_m"] = row["atraso_a_mais_ms"] / 1000.0 * row["vx_media_m_s"]
        row["voltas"] = len(laps)
        row["decide"] = len(sel) >= 20
        out["faixas"][name] = row
    dec = {k: v for k, v in out["faixas"].items() if v.get("decide")}
    acima = [k for k, v in dec.items() if v["atraso_a_mais_ic95_ms"][0] > 10.0]
    prods = [dec[k]["produto_atraso_a_mais_vezes_v_m"] for k in acima]
    med = float(np.median(prods)) if prods else float("nan")
    consistente = bool(prods) and all(abs(pv - med) <= 0.35 * abs(med) for pv in prods)
    if not entries:
        label = "sem dados"
    elif len(acima) >= 3 and consistente:
        label = "apoiada"
    elif dec and len(dec) == 4 and all(v["atraso_a_mais_ms"] < 10.0 for v in dec.values()):
        label = "nao apoiada"
    elif dec and all(v["atraso_a_mais_ms"] < 10.0 for v in dec.values()):
        label = "nao apoiada"
    else:
        label = "inconclusiva"
    out["regra_h2"] = {"faixas_que_decidem": list(dec), "faixas_com_ic_acima_de_10ms": acima,
                       "mediana_do_produto_m": med, "produtos_a_35pct": consistente, "rotulo": label}
    return out


def _passos_cinco(conv, geo, p) -> pd.DataFrame:
    """Todos os passos das 5 sessoes, na convencao do modelo, com `vy` no centro de massa da rodada `p`."""
    from ml.modelo_carro import convencoes as C
    from ml.modelo_carro.experimento import levar_ao_centro
    from ml.scripts import m1_modelo_carro as M
    frames = []
    for s in D.SESSOES_M1:
        f = C.no_modelo(pd.read_parquet(M.grade_path(s)), conv)
        f = levar_ao_centro(f, p.b, geo["x_v"])
        extra = pd.read_parquet(raiz() / f"extra_{s}.parquet")
        for c in EXTRAS:
            f[c] = extra[c].to_numpy()
        frames.append(f)
    out = pd.concat(frames, ignore_index=True)
    out["taxa_volante"] = C.derivada(out, "steer")
    out["dr_dt"] = C.derivada(out, "r")
    return out


def c4_direcao(cinco: pd.DataFrame, cases: pd.DataFrame, geo, sigmas: Dict[str, np.ndarray]) -> dict:
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro.validacao import FAIXAS_KMH
    rate = np.abs(cinco["taxa_volante"].to_numpy())
    t1 = float(np.nanpercentile(rate, 100.0 / 3.0))
    vx = cinco["vx"].to_numpy()
    sel = (np.abs(cinco["dr_dt"].to_numpy()) < 0.1) & (rate < t1) & (vx >= 10.0)
    sel &= np.isfinite(cinco[["r", "steer", "a_y"]].to_numpy()).all(1)
    L = geo["L"]
    y = L * cinco["r"].to_numpy() / np.maximum(vx, 1e-6)
    steer = cinco["steer"].to_numpy()
    bands = DG.faixa(np.abs(steer), DG.FAIXAS_STEER)
    ay = cinco["a_y"].to_numpy()

    def reg(mask):
        r = DG.ganho_direcao(y[mask], -steer[mask], -ay[mask], bands[mask], min_amostras=200)
        hi = DG.media_pesada(r["k_ef"], r["amostras"], ("0,4 a 0,6", "acima de 0,6"))
        lo = DG.media_pesada(r["k_ef"], r["amostras"], ("0 a 0,1", "0,1 a 0,2"))
        r["ganho_acima_de_0_4"], r["ganho_abaixo_de_0_2"] = hi, lo
        r["diferenca_relativa"] = float((hi - lo) / lo) if np.isfinite(hi) and np.isfinite(lo) and lo else float("nan")
        r["k_ef_sobre_k_delta"] = {k: v / geo["k_delta"] for k, v in r["k_ef"].items()}
        r["amostras_por_faixa_de_steer_todas"] = {n: int(((bands == n) & mask).sum()) for *_, n in DG.FAIXAS_STEER}
        return r

    kmh = vx * 3.6
    out = {"k_delta": geo["k_delta"], "L": L, "tercil_de_baixo_da_taxa_rad_s": t1, "amostras": int(sel.sum()),
           "todas_as_velocidades": reg(sel),
           "por_velocidade": {n: reg(sel & (kmh >= lo) & (kmh < hi)) for lo, hi, n in FAIXAS_KMH
                              if (sel & (kmh >= lo) & (kmh < hi)).sum() >= 200}}
    # O erro de r em 0,5 s, por faixa de |steer|, nas curvas (rad/s).
    err_r = np.empty(len(cases))
    for test, sig in sigmas.items():
        m = cases["rodada"].to_numpy() == test
        err_r[m] = np.abs(cases.loc[m, "e_M1_10_r"].to_numpy() * sig[2])
    curva = cases["regime"].to_numpy() == "curva"
    cb = DG.faixa(np.abs(cases["steer"].to_numpy()), DG.FAIXAS_STEER)
    med_all = float(np.median(err_r[curva]))
    out["erro_r_0_5s_curvas"] = {"mediana_todas_rad_s": med_all,
                                 "por_steer": {n: {"casos": int((curva & (cb == n)).sum()),
                                                   "mediana_rad_s": float(np.median(err_r[curva & (cb == n)])) if (curva & (cb == n)).any() else None,
                                                   "rmse_rad_s": float(np.sqrt(np.mean(err_r[curva & (cb == n)] ** 2))) if (curva & (cb == n)).any() else None}
                                               for *_, n in DG.FAIXAS_STEER}}
    hi_mask = curva & (np.abs(cases["steer"].to_numpy()) >= 0.4)
    med_hi = float(np.median(err_r[hi_mask])) if hi_mask.any() else float("nan")
    out["erro_r_0_5s_curvas"]["mediana_steer_acima_de_0_4_rad_s"] = med_hi
    out["erro_r_0_5s_curvas"]["razao"] = med_hi / med_all
    d = out["todas_as_velocidades"]["diferenca_relativa"]
    razao = med_hi / med_all
    if np.isfinite(d) and abs(d) >= 0.15 and razao >= 1.5:
        label = "apoiada"
    elif np.isfinite(d) and abs(d) < 0.05:
        label = "nao apoiada"
    elif not np.isfinite(d):
        label = "inconclusiva"
    else:
        label = "inconclusiva"
    out["regra_h3"] = {"diferenca_relativa_do_ganho": d, "razao_do_erro_de_r": razao, "rotulo": label}
    return out


def _r2(X: np.ndarray, y: np.ndarray) -> float:
    A = np.column_stack([np.ones(len(y)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y - A @ coef
    return float(1.0 - np.sum(res ** 2) / np.sum((y - y.mean()) ** 2))


def c5_carga(passos: pd.DataFrame, cases: pd.DataFrame, depois: Dict[str, pd.DataFrame], cinco_raw: Dict[str, pd.DataFrame]) -> dict:
    from ml.modelo_carro import diagnostico as DG
    out = {}
    vx2 = passos["vx"].to_numpy() ** 2
    rf, rr = passos["ride_height_f"].to_numpy(), passos["ride_height_r"].to_numpy()
    X = np.column_stack([rf, rr, vx2, vx2 * rf, vx2 * rr])
    susp = passos[[f"susp_{w}" for w in D.WHEELS]].to_numpy()
    for eixo, (a, b) in (("dianteiro", ("fl", "fr")), ("traseiro", ("rl", "rr"))):
        res = (passos[f"carga_prevista_{a}"] + passos[f"carga_prevista_{b}"]
               - passos[f"wheel_load_{a}"] - passos[f"wheel_load_{b}"]).to_numpy()
        ok = np.isfinite(res) & np.isfinite(X).all(1)
        ok2 = ok & np.isfinite(susp).all(1)
        out[eixo] = {"passos": int(ok.sum()), "residuo_medio_N": float(np.mean(res[ok])),
                     "residuo_rmse_N": float(np.sqrt(np.mean(res[ok] ** 2))),
                     "r2_altura_e_velocidade": _r2(X[ok], res[ok]),
                     "r2_com_suspensionTravel": _r2(np.column_stack([X[ok2], susp[ok2]]), res[ok2]),
                     "r2_so_velocidade": _r2(vx2[ok][:, None], res[ok])}
    drs = passos["drs"].to_numpy()
    out["drs"] = {"gravado": bool(np.isfinite(drs).any()), "fracao_dos_passos_com_drs": float(np.nanmean(drs > 0.5))}
    # A massa pela soma das cargas, por sessao.
    massa = {}
    frames = {**cinco_raw, **depois}
    for s, f in frames.items():
        loads = f[[f"wheel_load_{w}" for w in D.WHEELS]].to_numpy(float).sum(1)
        ax, ay = f["longitudinal_g"].to_numpy(float), f["lateral_g"].to_numpy(float)
        vx = f["velocity_long"].to_numpy(float)
        sel = (vx < 15) & (np.abs(ax) < 0.1) & (np.abs(ay) < 0.1) & np.isfinite(loads)
        fuel = f["fuel"].to_numpy(float)
        massa[s] = {"amostras": int(sel.sum()), "massa_kg_mediana": float(np.median(loads[sel]) / G) if sel.any() else None,
                    "massa_kg_media": float(np.mean(loads[sel]) / G) if sel.any() else None,
                    "combustivel_l": {"media": float(np.nanmean(fuel)), "min": float(np.nanmin(fuel)), "max": float(np.nanmax(fuel))}
                    if np.isfinite(fuel).any() else "nao gravado"}
    out["massa_por_sessao"] = massa
    out["massa_referencias"] = {"regressoes_da_v1_kg": [578, 653], "f3_real_kg": 673, "faixa_da_secao_1_4_kg": [700, 900]}
    # O skill por quartil do erro de carga no inicio do caso.
    true = cases[[f"carga_{w}" for w in D.WHEELS]].to_numpy()
    pred = cases[[f"carga_prevista_{w}" for w in D.WHEELS]].to_numpy()
    err = np.abs(pred - true).sum(1) / true.sum(1)
    q = np.nanpercentile(err, [25, 50, 75])
    quart = np.digitize(err, q)
    sq_m, sq_r = cases["sq_M1_10"].to_numpy(), cases["sq_R0_10"].to_numpy()
    curva = cases["regime"].to_numpy() == "curva"
    out["quartis_do_erro_de_carga"] = {"limites": [float(v) for v in q],
                                       "skill": [DG.skill(sq_m, sq_r, quart == i) for i in range(4)],
                                       "skill_nas_curvas": [DG.skill(sq_m, sq_r, (quart == i) & curva) for i in range(4)],
                                       "casos": [int((quart == i).sum()) for i in range(4)]}
    r2s = [out[e]["r2_altura_e_velocidade"] for e in ("dianteiro", "traseiro")]
    diff = out["quartis_do_erro_de_carga"]["skill"][0] - out["quartis_do_erro_de_carga"]["skill"][3]
    if all(v >= 0.30 for v in r2s) and diff >= 0.10:
        label = "apoiada"
    elif all(v < 0.10 for v in r2s) and abs(diff) < 0.05:
        label = "nao apoiada"
    else:
        label = "inconclusiva"
    out["regra_h4"] = {"r2": r2s, "diferenca_de_skill_q1_menos_q4": diff, "rotulo": label}
    return out


def _cobertura(af: np.ndarray, ar: np.ndarray) -> dict:
    out = {}
    for name, a in (("dianteira", af), ("traseira", ar)):
        a = a[np.isfinite(a)]
        out[name] = {f"acima_de_{lim}": float(np.mean(a > lim)) for lim in (6, 8, 10)}
        out[name]["p99_graus"] = float(np.percentile(a, 99))
        out[name]["passos"] = int(a.size)
    return out


def c6_pneu(cinco: pd.DataFrame, cases: pd.DataFrame, depois_frames: Dict[str, pd.DataFrame], p) -> dict:
    from ml.modelo_carro import diagnostico as DG

    def eixos(f):
        al = DG.deriva_rodas(f["vx"], f["vy"], f["r"], f["steer"], p.a, p.b, p.t_f, p.t_r, p.k_delta)
        af, ar = DG.deriva_eixos(al)
        return np.degrees(np.abs(af)), np.degrees(np.abs(ar)), al

    af, ar, al = eixos(cinco)
    out = {"treino": _cobertura(af, ar),
           "teste": _cobertura(cases["deriva_dianteira_graus"].to_numpy(), cases["deriva_traseira_graus"].to_numpy())}
    for nome, ids in (("24/10", SESSOES_DEPOIS[:2]), ("01/11", SESSOES_DEPOIS[2:])):
        f = pd.concat([depois_frames[s] for s in ids], ignore_index=True)
        a1, a2, _ = eixos(f)
        out[nome] = _cobertura(a1, a2)
    # O wheelSlip contra a deriva estimada e contra a forca lateral por carga.
    slip = cinco[[f"slip_{w}" for w in D.WHEELS]].to_numpy(float)
    loads = cinco[[f"wheel_load_{w}" for w in D.WHEELS]].to_numpy(float)
    mu = p.m * np.abs(cinco["a_y"].to_numpy()) / loads.sum(1)
    sel = (cinco["vx"].to_numpy() >= 10) & (cinco["B"].to_numpy() < 0.1) & np.isfinite(slip).all(1) & np.isfinite(mu)
    from scipy.stats import spearmanr
    rel = {}
    for name, cols, ang in (("dianteira", [0, 1], np.degrees(np.abs(0.5 * (al[:, 0] + al[:, 1])))),
                            ("traseira", [2, 3], np.degrees(np.abs(0.5 * (al[:, 2] + al[:, 3]))))):
        s = slip[:, cols].mean(1)
        qs = np.nanpercentile(s[sel], np.arange(0, 101, 10))
        bins = []
        for i in range(10):
            m = sel & (s >= qs[i]) & (s <= qs[i + 1])
            bins.append({"slip_de": float(qs[i]), "slip_ate": float(qs[i + 1]), "passos": int(m.sum()),
                         "deriva_mediana_graus": float(np.median(ang[m])), "forca_por_carga_mediana": float(np.median(mu[m])),
                         "forca_por_carga_p90": float(np.percentile(mu[m], 90))})
        meds = [b["forca_por_carga_mediana"] for b in bins]
        imax = int(np.argmax(meds))
        rel[name] = {"spearman_slip_deriva": float(spearmanr(s[sel], ang[sel])[0]),
                     "spearman_slip_forca_por_carga": float(spearmanr(s[sel], mu[sel])[0]),
                     "decis": bins, "decil_do_maximo_da_forca": imax,
                     "forca_para_de_crescer": bool(imax < 9 and max(meds[imax + 1:]) <= meds[imax] * 1.02),
                     "slip_no_maximo": [bins[imax]["slip_de"], bins[imax]["slip_ate"]]}
    out["wheelSlip"] = rel
    out["wheelSlip_faixa"] = {"p1": float(np.nanpercentile(slip, 1)), "p50": float(np.nanpercentile(slip, 50)),
                              "p99": float(np.nanpercentile(slip, 99))}
    out["_fig"] = {"af": af, "ar": ar, "slip_f": slip[:, :2].mean(1), "slip_r": slip[:, 2:].mean(1),
                   "ang_f": np.degrees(np.abs(0.5 * (al[:, 0] + al[:, 1]))), "ang_r": np.degrees(np.abs(0.5 * (al[:, 2] + al[:, 3]))),
                   "mu": mu, "sel": sel}
    return out


def c7_acumulo(cases: pd.DataFrame, passos: pd.DataFrame) -> dict:
    from ml.modelo_carro import diagnostico as DG
    regime = cases["regime"].to_numpy()
    regs = ["curva", "freio e volante juntos", "freada", "tracao", "reta"]
    out = {"razao_de_acumulo": {}, "skill_por_horizonte": {}}
    for reg in ["todos"] + regs:
        m = np.ones(len(cases), bool) if reg == "todos" else regime == reg
        out["razao_de_acumulo"][reg] = {
            "M1_v2": DG.razao_acumulo(cases["sq_M1_10"].to_numpy(), cases["sq_M1inc_10"].to_numpy(), m),
            "fisica_v2": DG.razao_acumulo(cases["sq_R1_10"].to_numpy(), cases["sq_R1inc_10"].to_numpy(), m),
            "erro_malha_aberta_M1_v2": DG.erro(cases["sq_M1_10"].to_numpy(), m),
            "erro_incrementos_M1_v2": DG.erro(cases["sq_M1inc_10"].to_numpy(), m),
            "por_horizonte_M1_v2": {str(h): DG.razao_acumulo(cases[f"sq_M1_{h}"].to_numpy(), cases[f"sq_M1inc_{h}"].to_numpy(), m)
                                    for h in HORIZONTES_DIAG}}
        out["skill_por_horizonte"][reg] = {str(h): {"M1_v2": DG.skill(cases[f"sq_M1_{h}"].to_numpy(), cases[f"sq_R0_{h}"].to_numpy(), m),
                                                    "fisica_v2": DG.skill(cases[f"sq_R1_{h}"].to_numpy(), cases[f"sq_R0_{h}"].to_numpy(), m),
                                                    "M1_v2_incrementos": DG.skill(cases[f"sq_M1inc_{h}"].to_numpy(), cases[f"sq_R0_{h}"].to_numpy(), m)}
                                           for h in HORIZONTES_DIAG}
    # A memoria: a autocorrelacao do residuo de um passo, por rodada (a grade de cada sessao), juntada.
    ac = {"curva": {}, "reta": {}}
    for reg in ac:
        for g in ESTADO:
            num = {}
            for j in range(1, 11):
                xs, ys = [], []
                for _, f in passos.groupby("rodada", sort=False):
                    a, b = DG.pares(len(f), f["trecho"].to_numpy(), f["k"].to_numpy(), j)
                    res = f[f"res_M1_{g}"].to_numpy()
                    ok = (f["regime"].to_numpy() == reg)
                    sel = ok[a] & ok[b] & np.isfinite(res[a]) & np.isfinite(res[b])
                    xs.append(res[a[sel]])
                    ys.append(res[b[sel]])
                xs, ys = np.concatenate(xs), np.concatenate(ys)
                num[str(j)] = float(np.corrcoef(xs, ys)[0, 1])
            ac[reg][g] = num
    out["autocorrelacao_residuo_um_passo_M1_v2"] = ac
    # A correlacao parcial com a taxa do volante de 0,1 a 0,3 s antes, nas curvas.
    parc = {}
    pieces = {g: ([], [], []) for g in ESTADO}
    for _, f in passos.groupby("rodada", sort=False):
        n = len(f)
        tr, k = f["trecho"].to_numpy(), f["k"].to_numpy()
        rate = f["taxa_volante"].to_numpy()
        hist = np.full(n, np.nan)
        acc = np.zeros(n)
        cnt = np.zeros(n)
        for j in range(2, 7):
            a, b = DG.pares(n, tr, k, j)        # b = k, a = k - j
            acc[b] += np.where(np.isfinite(rate[a]), rate[a], 0.0)
            cnt[b] += np.isfinite(rate[a])
        full = cnt == 5
        hist[full] = acc[full] / 5.0
        a1, b1 = DG.pares(n, tr, k, 1)
        U = f[["steer", "T", "B"]].to_numpy(float)
        Ustep = np.full_like(U, np.nan)
        Ustep[a1] = 0.5 * (U[a1] + U[b1])
        Z = np.column_stack([f[["vx", "vy", "r"]].to_numpy(float), Ustep])
        curva = f["regime"].to_numpy() == "curva"
        for g in ESTADO:
            pieces[g][0].append(f[f"res_M1_{g}"].to_numpy()[curva])
            pieces[g][1].append(hist[curva])
            pieces[g][2].append(Z[curva])
    for g in ESTADO:
        y, x, Z = (np.concatenate(v) for v in pieces[g])
        good = np.isfinite(y) & np.isfinite(x)
        parc[g] = {"parcial": DG.correlacao_parcial(y, x, Z), "simples": float(np.corrcoef(y[good], x[good])[0, 1]),
                   "passos": int((good & np.isfinite(Z).all(1)).sum())}
    out["correlacao_com_a_taxa_do_volante_antes"] = parc
    razao = out["razao_de_acumulo"]["curva"]["M1_v2"]
    out["regra_h5"] = {"razao_nas_curvas": razao,
                       "rotulo": "apoiada" if razao >= 1.3 else ("nao apoiada" if razao <= 1.1 else "inconclusiva")}
    lag1 = [ac["curva"]["vy"]["1"], ac["curva"]["r"]["1"]]
    out["regra_h6"] = {"atraso_1_vy_r_curvas": lag1, "atraso_1_vy_r_reta": [ac["reta"]["vy"]["1"], ac["reta"]["r"]["1"]],
                       "rotulo": "apoiada" if max(lag1) >= 0.5 else ("nao apoiada" if max(lag1) <= 0.2 else "inconclusiva")}
    return out


def _depois_frames(conv, geo, p) -> Dict[str, pd.DataFrame]:
    from ml.modelo_carro import convencoes as C
    from ml.modelo_carro.experimento import levar_ao_centro
    out = {}
    for s in SESSOES_DEPOIS:
        raw = pd.read_parquet(D.raiz_dados() / f"grade_depois_{s}.parquet")
        f = levar_ao_centro(C.no_modelo(raw, conv), p.b, geo["x_v"])
        extra = pd.read_parquet(raiz() / f"extra_{s}.parquet")
        if not np.array_equal(extra["trecho"].to_numpy(), f["trecho"].to_numpy()):
            raise SystemExit(f"{s}: os canais extras nao estao na grade do 46")
        for c in EXTRAS:
            f[c] = extra[c].to_numpy()
        out[s] = f
    return out


def _vizinhanca(mod, conv, geo, grades):
    from ml.modelo_carro import correcao_v2 as K2
    from ml.modelo_carro import validacao as V
    from ml.modelo_carro.experimento import levar_ao_centro, no_modelo
    train = levar_ao_centro(no_modelo(grades, mod["sessoes_de_treino"], conv), mod["p"].b, geo["x_v"])
    P = V.passos(train)
    return K2.Vizinhanca(np.column_stack([P.S0, P.U]), P.lap)


def c8_0111(conv, geo, grades, depois_frames: Dict[str, pd.DataFrame]) -> dict:
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro import fisica as F
    from ml.modelo_carro import fisica_v2 as F2
    from ml.modelo_carro import validacao as V
    mod = _modelos(RODADA_INFO)
    p, corr, sigma, cut = mod["p"], mod["corr"], mod["sigma"], mod["corte"]
    viz = _vizinhanca(mod, conv, geo, grades)
    corners, length = _curvas()
    out = {"modelos": "os da rodada sem 2026-10-21_20-30-54 (treinados nas 4 sessoes de 15/10 a 18/10)", "sessoes": {}}
    pool = {}
    for s, f in depois_frames.items():
        cs = V.casos(f, conv)
        m1 = F2.malha_aberta(cs.S0, cs.U, p, corr)
        r1 = F2.malha_aberta(cs.S0, cs.U, p)
        r0 = F.persistencia(cs.S0, V.H_MAX)
        sq = {n: V.erro_quadrado(x, cs.S, sigma, 10) for n, x in (("M1", m1), ("R1", r1), ("R0", r0))}
        idx = viz.indice(np.column_stack([cs.S0, cs.U[:, 0]]))
        row ={(t, int(k)): i for i, (t, k) in enumerate(zip(f["trecho"].to_numpy(), f["k"].to_numpy()))}
        i0 = np.array([row[(t, int(k))] for t, k in zip(cs.trecho, cs.k0)])
        al = DG.deriva_rodas(cs.S0[:, 0], cs.S0[:, 1], cs.S0[:, 2], f["steer"].to_numpy()[i0], p.a, p.b, p.t_f, p.t_r, p.k_delta)
        af, ar = DG.deriva_eixos(al)
        af, ar = np.degrees(np.abs(af)), np.degrees(np.abs(ar))
        pool[s] = {"sq": sq, "af": af, "ar": ar, "regime": cs.regime}
        tyre = f["tyre_core_temp"].to_numpy(float)
        out["sessoes"][s] = {"voltas": int(f["lap_id"].nunique()), "casos": len(cs),
                             "skill_M1_v2_contra_R0": DG.skill(sq["M1"], sq["R0"]),
                             "skill_fisica_v2_contra_R0": DG.skill(sq["R1"], sq["R0"]),
                             "nao_conclusivo": float(np.mean(idx > cut)),
                             "temperatura_media_dos_pneus_c": float(np.nanmean(tyre)),
                             "ar_c": float(np.nanmean(f["air_temp"])), "pista_c": float(np.nanmean(f["road_temp"])),
                             "por_deriva_maior_eixo": {}}
        big = np.maximum(af, ar)
        for *_, name in DG.FAIXAS_DERIVA:
            b = DG.faixa(big, DG.FAIXAS_DERIVA) == name
            out["sessoes"][s]["por_deriva_maior_eixo"][name] = {"casos": int(b.sum()),
                                                                "skill": DG.skill(sq["M1"], sq["R0"], b) if b.any() else None}
    # A versao do CSP e do app de cada sessao.
    for s in SESSOES_DEPOIS:
        meta = json.loads((D.sessao_por_id(s).directory / "metadata.json").read_text(encoding="utf-8"))
        out["sessoes"][s]["versao_do_csp"] = "0.3.1 (informacao do Eduardo; nao gravada)" if s == SESSAO_0111 else "nao registrada"
        out["sessoes"][s]["appVersion"] = (meta.get("metadata") or {}).get("appVersion")

    def juntar(ids, mask_fn):
        sq_m = np.concatenate([pool[s]["sq"]["M1"][mask_fn(pool[s])] for s in ids])
        sq_r = np.concatenate([pool[s]["sq"]["R0"][mask_fn(pool[s])] for s in ids])
        return DG.skill(sq_m, sq_r) if sq_m.size else float("nan"), int(sq_m.size)

    low = lambda d: (d["af"] < 3.0) & (d["ar"] < 3.0)
    s24, n24 = juntar(SESSOES_DEPOIS[:2], low)
    s01, n01 = juntar(SESSOES_DEPOIS[2:], low)
    a24, _ = juntar(SESSOES_DEPOIS[:2], lambda d: np.ones(d["af"].size, bool))
    a01, _ = juntar(SESSOES_DEPOIS[2:], lambda d: np.ones(d["af"].size, bool))
    diff = s24 - s01
    if n24 < 100 or n01 < 100:
        la = lb = "inconclusiva"
    elif diff <= 0.10:
        la, lb = "apoiada", "nao apoiada"
    elif diff > 0.20:
        la, lb = "nao apoiada", "apoiada"
    else:
        la = lb = "inconclusiva"
    out["regra_h7"] = {"skill_24_10_deriva_abaixo_de_3": s24, "casos_24_10": n24, "skill_01_11_deriva_abaixo_de_3": s01,
                       "casos_01_11": n01, "diferenca": diff, "skill_24_10_todos": a24, "skill_01_11_todos": a01,
                       "rotulo_h7a": la, "rotulo_h7b": lb}
    out["episodios"] = c8_episodios(conv, geo, p, corr, sigma, viz, cut, corners, length)
    return out


EPISODIOS = ((3, "C05"), (3, "C06"), (3, "C13"), (4, "C01"), (4, "C06"), (10, "C05"), (11, "C01"))


def c8_episodios(conv, geo, p, corr, sigma, viz, cut, corners, length) -> List[dict]:
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro import fisica as F
    from ml.modelo_carro import fisica_v2 as F2
    by = {c.label[:3]: c for c in corners}
    out = []
    for volta, label in EPISODIOS:
        raw = pd.read_parquet(raiz() / f"episodio_volta{volta}_cru.parquet")
        cru = _cru_modelo(raw, conv, p.b, geo["x_v"])
        c = by[label]
        i = DG.indice_do_pico(cru["s"].to_numpy(), cru["vx"].to_numpy(), cru["vy"].to_numpy(), c.start_s, c.end_s, length)
        t = cru["t"].to_numpy()
        tp = float(t[i])
        al = DG.deriva_rodas(cru["vx"].to_numpy()[[i]], cru["vy"].to_numpy()[[i]], cru["r"].to_numpy()[[i]],
                             cru["steer"].to_numpy()[[i]], p.a, p.b, p.t_f, p.t_r, p.k_delta)[0]
        ep = {"volta": volta, "curva": label, "lap_id": raw["lap_id"].iloc[0], "t_pico_s": tp, "s_pico_m": float(cru["s"].iloc[i]),
              "vx_pico_kmh": float(cru["vx"].iloc[i] * 3.6),
              "beta_pico_graus": float(np.degrees(np.arctan2(cru["vy"].iloc[i], cru["vx"].iloc[i]))),
              "deriva_pico_graus": {w: float(np.degrees(v)) for w, v in zip(D.WHEELS, al)},
              "wheelSlip_pico": {w: float(cru[f"slip_{w}"].iloc[i]) for w in D.WHEELS}, "casos": {}}
        for antes in (1.0, 0.5, 0.25):
            n = int(round(antes / D.DT))
            grid = tp - D.DT * np.arange(n, -1, -1)
            win = (t >= grid[0] - 0.05) & (t <= tp)
            gaps = np.diff(t[win])
            cols = {k: np.interp(grid, t, cru[k].to_numpy()) for k in ("vx", "vy", "r", "steer", "T", "B")}
            S = np.column_stack([cols["vx"], cols["vy"], cols["r"]])
            u = np.column_stack([cols["steer"], cols["T"], cols["B"]])
            U = 0.5 * (u[:-1] + u[1:])[None]
            S0 = S[:1]
            m1 = F2.malha_aberta(S0, U, p, corr)[0]
            r1 = F2.malha_aberta(S0, U, p)[0]
            r0 = F.persistencia(S0, n)[0]
            idx = float(viz.indice(np.column_stack([S0, U[:, 0]]))[0])
            dv = {"gravado": float(S[-1, 1] - S[0, 1]), "M1_v2": float(m1[-1, 1] - S[0, 1]), "fisica_v2": float(r1[-1, 1] - S[0, 1])}
            acomp = {k: bool(np.sign(dv[k]) == np.sign(dv["gravado"]) and abs(dv[k]) >= 0.5 * abs(dv["gravado"]))
                     for k in ("M1_v2", "fisica_v2")}
            ep["casos"][f"{antes:g} s"] = {
                "maior_intervalo_cru_s": float(gaps.max()) if gaps.size else None,
                "t_s": (grid - tp).tolist(), "vy_gravado": S[:, 1].tolist(), "r_gravado": S[:, 2].tolist(),
                "vy_M1_v2": m1[:, 1].tolist(), "r_M1_v2": m1[:, 2].tolist(), "vy_fisica_v2": r1[:, 1].tolist(),
                "r_fisica_v2": r1[:, 2].tolist(), "vy_R0": r0[:, 1].tolist(), "r_R0": r0[:, 2].tolist(),
                "variacao_de_vy_ate_o_pico": dv, "acompanha": acomp, "indice": idx, "nao_conclusivo": bool(idx > cut)}
        out.append(ep)
    return out


def c9_jogo() -> dict:
    """O que o retrato da memoria compartilhada do repositorio tem sobre o pneu (so leitura)."""
    path = Path(r"C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\debug\ac_shared_memory_full_inventory.json")
    inv = json.loads(path.read_text(encoding="utf-8"))
    fields = inv.get("fields") or []
    keys = ("slip", "angle", "force", "load", "fy", "fx", "contact", "camber", "suspension", "ride", "drs")
    hits = []
    for f in fields:
        name = str(f.get("field_name") or f.get("name") or "")
        if any(k in name.lower() for k in keys):
            hits.append({k: f.get(k) for k in ("structure", "field_name", "type", "current_value", "category") if k in f})
    return {"arquivo": file_entry(path), "campos_do_pneu": hits, "chaves": list(inv.keys())}


def cmd_analisar(args) -> int:
    conferir_jogo()
    from ml.scripts import m1_modelo_carro as M
    started = time.time()
    rep = json.loads((raiz() / "reproducao.json").read_text(encoding="utf-8"))
    cases = carregar_casos()
    passos = pd.read_parquet(raiz() / "passos.parquet")
    geo, conv = M._geo_v2(), M._convencoes()
    grades = {s: pd.read_parquet(M.grade_path(s)) for s in D.SESSOES_M1}
    sigmas = {s: np.asarray(_modelos(s)["sigma"]) for s in D.SESSOES_M1}
    p_info = _modelos(RODADA_INFO)["p"]
    so = set(args.so.split(",")) if args.so else None
    res = {}

    def quer(n):
        return so is None or n in so

    if quer("c1"):
        res["C1"] = c1_acaso(cases); print("C.1 feito", flush=True)
    c2 = c2_onde(cases, rep["tercis_taxa_volante"])
    res["C2"] = {k: v for k, v in c2.items() if not k.startswith("_")}
    res["H1"] = h1_regra(cases, c2)
    print("C.2 feito", flush=True)
    cinco = _passos_cinco(conv, geo, p_info)
    if quer("c3"):
        res["C3"] = c3_atraso(conv, geo, 0.02)
        res["C3_informativo_trechos_de_50ms"] = c3_atraso(conv, geo, 0.0499)
        res["C3_informativo_trechos_de_50ms"]["nota"] = ("so informa, nao decide: os trechos da secao 1.2 (intervalos menores que 50 ms) "
                                                          "no lugar dos de ate 20 ms do pedido, que nao tem nenhuma entrada")
        print("C.3 feito", flush=True)
    if quer("c4"):
        res["C4"] = c4_direcao(cinco, cases, geo, sigmas); print("C.4 feito", flush=True)
    depois = _depois_frames(conv, geo, p_info)
    if quer("c5"):
        cinco_raw = {s: pd.read_parquet(M.grade_path(s)).assign(fuel=pd.read_parquet(raiz() / f"extra_{s}.parquet")["fuel"].to_numpy())
                     for s in D.SESSOES_M1}
        dep_raw = {s: pd.read_parquet(D.raiz_dados() / f"grade_depois_{s}.parquet").assign(
            fuel=pd.read_parquet(raiz() / f"extra_{s}.parquet")["fuel"].to_numpy()) for s in SESSOES_DEPOIS}
        res["C5"] = c5_carga(passos, cases, dep_raw, cinco_raw); print("C.5 feito", flush=True)
    if quer("c6"):
        c6 = c6_pneu(cinco, cases, depois, p_info)
        res["C6"] = {k: v for k, v in c6.items() if not k.startswith("_")}
        print("C.6 feito", flush=True)
    if quer("c7"):
        res["C7"] = c7_acumulo(cases, passos); print("C.7 feito", flush=True)
    if quer("c8"):
        res["C8"] = c8_0111(conv, geo, grades, depois); print("C.8 feito", flush=True)
    if quer("c9"):
        res["C9"] = c9_jogo()
    payload = {"pedido": PEDIDO, "parte": "C, as analises", "commit": git_commit(),
               "comando": "python -m ml.scripts.m1_diagnostico analisar", "reproducao": rep["conferencia"],
               **{k: _limpar(v) for k, v in res.items()}, "tempo_s": round(time.time() - started, 1)}
    nome = "analises.json" if so is None else f"analises_{'_'.join(sorted(so))}.json"
    _json(raiz() / nome, payload)
    if so is None and args.handoff:
        _json(Path(args.handoff + ".json"), payload)
        figuras(cases, c2, res, c6, Path(args.handoff))
    print("pronto em", round(time.time() - started), "s")
    return 0


def _limpar(v):
    if isinstance(v, dict):
        return {k: _limpar(x) for k, x in v.items() if not str(k).startswith("_")}
    if isinstance(v, list):
        return [_limpar(x) for x in v]
    return v


# ------------------------------------------------------------- figuras ---

def figuras(cases, c2, res, c6, prefix: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ml.modelo_carro import diagnostico as DG
    from ml.modelo_carro.validacao import FAIXAS_KMH

    # 1. A parte do erro das curvas por |steer| e velocidade.
    mapa = res["C2"]["curva"]["mapa_steer_velocidade"]
    sb = [n for *_, n in DG.FAIXAS_STEER]
    vb = [n for *_, n in FAIXAS_KMH]
    grid = np.array([[mapa[s][v].get("parte_no_erro_pct", 0.0) for v in vb] for s in sb])
    sk = np.array([[mapa[s][v].get("skill_M1_v2_contra_R0", np.nan) if mapa[s][v].get("casos", 0) >= 100 else np.nan
                    for v in vb] for s in sb])
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(grid, cmap="Blues", aspect="auto")
    for i in range(len(sb)):
        for j in range(len(vb)):
            n = mapa[sb[i]][vb[j]].get("casos", 0)
            txt = f"{grid[i, j]:.1f}%\n" + (f"skill {sk[i, j]:.2f}" if np.isfinite(sk[i, j]) else "") + f"\n{n} casos"
            ax.text(j, i, txt, ha="center", va="center", fontsize=8, color="white" if grid[i, j] > grid.max() * 0.6 else "black")
    ax.set_xticks(range(len(vb)), vb, fontsize=8)
    ax.set_yticks(range(len(sb)), [f"|steer| {s}" for s in sb], fontsize=8)
    ax.set_title("Parte do erro das curvas (M1 v2, 0,5 s) por |steer| e velocidade")
    fig.colorbar(im, label="% do erro quadrático das curvas")
    fig.tight_layout()
    fig.savefig(str(prefix) + "_mapa_do_erro.png", dpi=130)
    plt.close(fig)

    # 2. A distribuicao da deriva estimada.
    f = c6["_fig"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, key, name in ((axes[0], "af", "dianteira"), (axes[1], "ar", "traseira")):
        a = f[key][np.isfinite(f[key])]
        ax.hist(np.clip(a, 0, 15), bins=np.arange(0, 15.25, 0.25), color="#4a78b5")
        ax.set_yscale("log")
        ax.axvline(6, color="k", ls="--", lw=1)
        ax.axvline(12, color="#c0392b", ls="-", lw=1.5)
        ax.text(6.2, ax.get_ylim()[1] * 0.3, "6°", fontsize=9)
        ax.text(12.2, ax.get_ylim()[1] * 0.3, "α_pico = 12°", fontsize=9, color="#c0392b")
        ax.set_xlabel(f"|deriva| do eixo {name} (°)")
        ax.set_title(f"eixo {name}: {100 * np.mean(a > 6):.2f}% acima de 6°")
    axes[0].set_ylabel("passos (5 sessões, escala log)")
    fig.suptitle("Deriva estimada (ADR 0028, item 3) nas 5 sessões")
    fig.tight_layout()
    fig.savefig(str(prefix) + "_deriva.png", dpi=130)
    plt.close(fig)

    # 3. O atraso por velocidade.
    if "C3" in res:
        fonte = res["C3"] if res["C3"]["entradas"] else res["C3_informativo_trechos_de_50ms"]
        nota = "" if res["C3"]["entradas"] else " (informativo: trechos da seção 1.2, a regra de 20 ms não tem dados)"
        fx = fonte["faixas"]
        names = [n for n in vb if fx.get(n, {}).get("entradas", 0) >= 3]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
        xs = np.arange(len(names))
        for k, (s, lab) in enumerate((("gravado_5ms", "gravado (5 ms)"), ("gravado_grade", "gravado (grade de 50 ms)"),
                                      ("fisica_v2", "física v2"), ("m1_v2", "M1 v2"))):
            ax1.bar(xs + (k - 1.5) * 0.2, [fx[n][f"atraso_{s}_ms"] for n in names], 0.2, label=lab)
        ax1.set_xticks(xs, [f"{n}\n({fx[n]['entradas']} entradas)" for n in names], fontsize=8)
        ax1.set_ylabel("atraso no pico da correlação (ms)")
        ax1.legend(fontsize=8)
        ax1.set_title("Atraso do volante para a guinada" + nota, fontsize=9)
        extra = [fx[n]["atraso_a_mais_ms"] for n in names]
        lo = [fx[n]["atraso_a_mais_ms"] - fx[n]["atraso_a_mais_ic95_ms"][0] for n in names]
        hi = [fx[n]["atraso_a_mais_ic95_ms"][1] - fx[n]["atraso_a_mais_ms"] for n in names]
        ax2.errorbar(xs, extra, yerr=[lo, hi], fmt="o", color="#c0392b", capsize=4, label="atraso a mais (IC 95%)")
        ax2.axhline(10, color="k", ls="--", lw=1)
        ax2.axhline(0, color="gray", lw=0.8)
        ax2.set_xticks(xs, names, fontsize=8)
        ax2.set_ylabel("gravado − física v2 (ms)")
        ax2b = ax2.twinx()
        ax2b.plot(xs, [fx[n]["produto_atraso_a_mais_vezes_v_m"] for n in names], "s--", color="#2c7a3f", label="× velocidade (m)")
        ax2b.set_ylabel("atraso a mais × velocidade (m)")
        ax2.legend(loc="upper left", fontsize=8)
        ax2b.legend(loc="upper right", fontsize=8)
        ax2.set_title("O atraso a mais e o produto pela velocidade")
        fig.tight_layout()
        fig.savefig(str(prefix) + "_atraso.png", dpi=130)
        plt.close(fig)

    # 4. O wheelSlip contra a deriva e contra a forca lateral por carga.
    sel = f["sel"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    for ax, y, lab in ((axes[0], "ang", "|deriva| estimada do eixo (°)"), (axes[1], "mu", "força lateral por carga (m·|a_y| / Σ cargas)")):
        for key, color, name in (("slip_f", "#4a78b5", "dianteira"), ("slip_r", "#c0392b", "traseira")):
            yy = f[y + key[-2:]] if y == "ang" else f["mu"]
            ax.scatter(f[key][sel][::7], yy[sel][::7], s=1, alpha=0.15, color=color, label=name)
            dec = res["C6"]["wheelSlip"]["dianteira" if key == "slip_f" else "traseira"]["decis"]
            mids = [0.5 * (d["slip_de"] + d["slip_ate"]) for d in dec]
            val = [d["deriva_mediana_graus"] if y == "ang" else d["forca_por_carga_mediana"] for d in dec]
            ax.plot(mids, val, "o-", color=color, lw=2)
        ax.set_xlabel("wheelSlip gravado (média do eixo)")
        ax.set_ylabel(lab)
        ax.legend(markerscale=10, fontsize=8)
    fig.suptitle("wheelSlip gravado (vx ≥ 10 m/s, sem freio; linhas: medianas por decil)")
    fig.tight_layout()
    fig.savefig(str(prefix) + "_wheelslip.png", dpi=130)
    plt.close(fig)

    # 5. Os 7 episodios de 01/11.
    if "C8" in res:
        eps = res["C8"]["episodios"]
        fig, axes = plt.subplots(2, len(eps), figsize=(3.0 * len(eps), 6), sharex=True)
        for j, ep in enumerate(eps):
            cs = ep["casos"]
            for row, (q, unit) in enumerate((("vy", "m/s"), ("r", "rad/s"))):
                ax = axes[row, j]
                ax.plot(cs["1 s"]["t_s"], cs["1 s"][f"{q}_gravado"], "k-", lw=2, label="gravado")
                for key, ls in (("1 s", ":"), ("0.5 s", "-"), ("0.25 s", "--")):
                    c = cs[key]
                    ax.plot(c["t_s"], c[f"{q}_M1_v2"], ls, color="#c0392b", label=f"M1 v2 ({key})")
                    ax.plot(c["t_s"], c[f"{q}_fisica_v2"], ls, color="#4a78b5", lw=1, label=f"física v2 ({key})")
                ax.axvline(0, color="gray", lw=0.8)
                if row == 0:
                    ok = "acompanha" if cs["0.5 s"]["acompanha"]["M1_v2"] else "não acompanha"
                    ax.set_title(f"volta {ep['volta']}, {ep['curva']}\n{ep['vx_pico_kmh']:.0f} km/h, β {ep['beta_pico_graus']:.1f}°\n{ok}",
                                 fontsize=8)
                if j == 0:
                    ax.set_ylabel(f"{q} ({unit})")
                if row == 1:
                    ax.set_xlabel("t − pico (s)")
        axes[0, 0].legend(fontsize=6)
        fig.suptitle("01/11: os 7 episódios de saída de traseira (rodada sem 21/10)")
        fig.tight_layout()
        fig.savefig(str(prefix) + "_episodios.png", dpi=110)
        plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dados")
    sub.add_parser("reproduzir")
    an = sub.add_parser("analisar")
    an.add_argument("--handoff", help="prefixo dos arquivos de handoff (docs/handoff/<pedido>)")
    an.add_argument("--so", help="so estas analises, separadas por virgula (c1,c3,...), para conferir")
    args = parser.parse_args(argv)
    return {"dados": cmd_dados, "reproduzir": cmd_reproduzir, "analisar": cmd_analisar}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
