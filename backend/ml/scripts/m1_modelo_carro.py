"""M1, o modelo do carro para a frente (pedido 37; ADR 0017 e ADR 0022).

    python -m ml.scripts.m1_modelo_carro dados        # Parte B: le as 5 sessoes e reamostra
    python -m ml.scripts.m1_modelo_carro convencoes   # Parte B: confere os sinais
    python -m ml.scripts.m1_modelo_carro validar      # Partes C a E: as 5 rodadas e o veredito

Tudo o que sai fica em `data/ml/modelo_carro/`, fora do git, com o hash e o
tamanho de cada arquivo lido e escrito (ADR 0007). As gravacoes so sao lidas.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data.store_v2 import file_entry, git_commit, store_v2_meta  # noqa: E402
from ml.modelo_carro import convencoes as C  # noqa: E402
from ml.modelo_carro import dados as D  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_geometry  # noqa: E402


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=float), encoding="utf-8")


def _ambiente() -> dict:
    import scipy
    import sklearn
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "scipy": scipy.__version__, "scikit-learn": sklearn.__version__, "plataforma": platform.platform()}


def grade_path(session_id: str) -> Path:
    return D.raiz_dados() / f"grade_{session_id}.parquet"


def carregar_grades() -> pd.DataFrame:
    return pd.concat([pd.read_parquet(grade_path(s)) for s in D.SESSOES_M1], ignore_index=True)


def cmd_dados(args) -> int:
    started = time.time()
    root = D.raiz_dados()
    root.mkdir(parents=True, exist_ok=True)
    meta = store_v2_meta()
    geometry = load_geometry()
    if meta.get("geometry_id") != geometry.geometry_id:
        raise SystemExit(f"geometria do store ({meta.get('geometry_id')}) != carregada ({geometry.geometry_id})")
    store_path = config.artifacts_root() / "laps_grid_v2.parquet"
    meta_path = config.artifacts_root() / "laps_grid_v2_meta.json"
    recorded = (meta.get("entradas") or {}).get("gravacoes") or {}
    report = {"pedido": 37, "parte": "B", "commit": git_commit(), "geometry_id": geometry.geometry_id,
              "dt_s": D.DT, "buraco_s": D.GAP_S, "ambiente": _ambiente(),
              "comando": "python -m ml.scripts.m1_modelo_carro dados",
              "lidos": {"store_v2": file_entry(store_path), "store_v2_meta": file_entry(meta_path)},
              "gravacoes": {}, "escritos": {}, "sessoes": {}}
    for session_id in D.SESSOES_M1:
        t0 = time.time()
        session = D.sessao_por_id(session_id)
        entry = file_entry(session.player_stream)
        expected = (recorded.get(session_id) or {}).get("sha256")
        entry["igual_ao_do_store"] = bool(expected == entry["sha256"])
        report["gravacoes"][session_id] = entry
        if not entry["igual_ao_do_store"]:
            raise SystemExit(f"{session_id}: a gravacao mudou desde o store ({expected} != {entry['sha256']})")
        frame, laps = D.ler_sessao(session, meta, geometry)
        out = grade_path(session_id)
        frame.to_parquet(out, index=False)
        report["escritos"][out.name] = file_entry(out)
        laps_d = [asdict(r) for r in laps]
        report["sessoes"][session_id] = {
            "voltas": len(laps),
            "amostras_cruas": int(sum(r.amostras_cruas for r in laps)),
            "tiradas_na_limpeza": int(sum(r.tiradas_na_limpeza for r in laps)),
            "repetidas": int(sum(r.repetidas for r in laps)),
            "buracos": int(sum(r.buracos for r in laps)),
            "trechos": int(sum(r.trechos for r in laps)),
            "trechos_curtos_tirados": int(sum(r.trechos_curtos for r in laps)),
            "passos": int(len(frame)),
            "segundos": float(sum(r.segundos for r in laps)),
            "faixas": D.faixas(frame, [c for c in D.COLUNAS if c not in ("x", "z", "heading", "s")]),
            "por_volta": laps_d,
            "tempo_s": round(time.time() - t0, 1),
        }
        print(f"{session_id}: {len(laps)} voltas, {len(frame)} passos, {time.time() - t0:.0f} s", flush=True)
    report["tempo_s"] = round(time.time() - started, 1)
    _json(root / "dados_relatorio.json", report)
    return 0


def cmd_convencoes(args) -> int:
    geometry = load_geometry()
    corners = detect_corners(geometry)
    frame = carregar_grades()
    result, conv = C.conferir(frame, corners, geometry.length)
    by_session = {}
    for session_id, part in frame.groupby("session_id", sort=False):
        res, cv = C.conferir(part.reset_index(drop=True), corners, geometry.length)
        by_session[session_id] = {"todas_batem": res["todas_batem"], "convencoes": cv.to_dict(),
                                  "guinada": res["guinada"]["todas"], "heading": res["heading"]["todas"],
                                  "velocidade_lateral": res["velocidade_lateral"]["todas"],
                                  "velocidade_longitudinal": res["velocidade_longitudinal"]["todas"],
                                  "volante": res["volante"]["todas"]}
    consistent = len({json.dumps(v["convencoes"], sort_keys=True) for v in by_session.values()}) == 1
    payload = {"pedido": 37, "parte": "B.3", "commit": git_commit(), "geometry_id": geometry.geometry_id,
               "comando": "python -m ml.scripts.m1_modelo_carro convencoes",
               "lidos": {grade_path(s).name: file_entry(grade_path(s)) for s in D.SESSOES_M1},
               "convencoes": conv.to_dict(), "conferencias": result,
               "por_sessao": by_session, "mesma_convencao_nas_5_sessoes": consistent,
               "sinais_por_curva": C.sinais_por_curva(frame, conv, corners, geometry.length),
               "todas_batem": bool(result["todas_batem"] and consistent
                                   and all(v["todas_batem"] for v in by_session.values()))}
    _json(D.raiz_dados() / "convencoes.json", payload)
    print(json.dumps({k: payload[k] for k in ("convencoes", "todas_batem", "mesma_convencao_nas_5_sessoes")}, indent=1))
    return 0 if payload["todas_batem"] else 2


def cmd_retrato(args) -> int:
    """Pedido 39, Parte B: a primeira olhada no retrato da memoria (so uma olhada; nada entra na M1)."""
    import ast
    from ml.modelo_carro import geometria_medida as GM
    path = config.repo_root() / "data" / "debug" / "ac_shared_memory_full_inventory.csv"
    table = pd.read_csv(path)

    def value(structure, name):
        row = table[(table["structure"] == structure) & (table["field_name"] == name)].iloc[0]
        text = str(row["current_value"])
        return ast.literal_eval(text) if text.startswith("[") else (float(text) if text.replace(".", "", 1).lstrip("-").isdigit() else text)

    contact = GM.achatar_4x3(value("Physics", "tyreContactPoint"))
    dirs = GM.achatar_4x3(value("Physics", "tyreContactHeading"))
    heading = float(value("Physics", "heading"))
    car = np.asarray(value("Graphics", "carCoordinates"), dtype=float)
    steer = float(value("Physics", "steerAngle"))
    inst = GM.instantaneas(contact[None], dirs[None], np.array([heading]), car[None])
    sentido = float(inst["sentido"][0])
    ang = GM.angulos_das_rodas(dirs[None], np.array([heading]), sentido)
    # A velocidade no referencial do carro estava no antigo `brakeTemp` (pedido 18): [brakeBias, x, y, z].
    old = value("Physics", "brakeTemp")
    yaw = value("Physics", "localAngularVel")[1]
    L = float(inst["L"][0])
    payload = {
        "pedido": 39, "parte": "B", "arquivo": file_entry(path),
        "carModel": value("Static", "carModel"), "track": value("Static", "track"),
        "acVersion": value("Static", "acVersion"),
        "contatos_4x3": contact.tolist(), "direcoes_4x3": dirs.tolist(),
        "entre_eixos_m": L, "bitola_dianteira_m": float(inst["bitola_dianteira"][0]),
        "bitola_traseira_m": float(inst["bitola_traseira"][0]),
        "carCoordinates_a_partir_do_eixo_traseiro_m": float(inst["x_carro"][0]),
        "carCoordinates_fracao_do_entre_eixos": float(inst["x_carro"][0] / L),
        "carCoordinates_desvio_lateral_m": float(inst["y_carro"][0]),
        "carCoordinates_altura_sobre_os_contatos_m": float(inst["altura_carro"][0]),
        "cgHeight_m": float(value("Physics", "cgHeight")),
        "direcoes_apontam_para_tras": bool(sentido < 0),
        "angulo_rodas_rad": {k: float(v[0]) for k, v in ang.items()},
        "steerAngle": steer,
        "k_delta_rad_por_unidade": {k: float(-v[0] / steer) for k, v in ang.items()},
        "localVelocity_x_y_z": old[1:4], "guinada_rad_s": yaw,
        "speedKmh": float(value("Physics", "speedKmh")),
    }
    k = payload["k_delta_rad_por_unidade"]["media"]
    payload["k_delta_graus"] = float(np.degrees(k))
    payload["L_sobre_k_delta"] = float(L / k)
    payload["reportagem"] = {"entre_eixos_m": 2.943, "bitola_dianteira_m": 1.552, "bitola_traseira_m": 1.502}
    payload["m0_razao_volante_curvatura"] = 10.6
    out = Path(args.saida) if args.saida else D.raiz_dados() / "retrato_geometria.json"
    _json(out, payload)
    print(json.dumps({k: v for k, v in payload.items() if k not in ("contatos_4x3", "direcoes_4x3", "arquivo")}, indent=1, ensure_ascii=False))
    return 0


GEOMETRIA_MEDIDA = "geometria_medida.json"
IMPACTO_G = 5.0


def cmd_geometria(args) -> int:
    """Pedido 39, Parte D: a geometria medida pela regra da secao 1.9, com os portoes do ADR 0024."""
    from ml.modelo_carro import geometria_medida as GM
    path = Path(args.sessao)
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    if meta.get("carModel") != GM.CARRO or meta.get("track") != GM.PISTA:
        raise SystemExit(f"a sessao e de {meta.get('carModel')} em {meta.get('track')}; a 1.9 so aceita {GM.CARRO} em {GM.PISTA}")
    raw = pd.read_parquet(path)
    K = GM.medir_k_delta(raw)
    L = GM.medir_relogio(raw)
    gates = GM.portoes(L, K)

    # So para informacao (nao decide nada): o maior impacto da sessao e as contas antes dele.
    g = np.hypot(raw["acc_x"].to_numpy(dtype=float), raw["acc_z"].to_numpy(dtype=float))
    hit = np.flatnonzero(g >= IMPACTO_G)
    info = {"impacto_g_max": float(g.max()), "impacto_t_wall_s": float(raw["t_wall"].iloc[hit[0]]) if hit.size else None}
    if hit.size:
        pre = raw.iloc[:hit[0]].reset_index(drop=True)
        Kp, Lp = GM.medir_k_delta(pre), GM.medir_relogio(pre)
        info["antes_do_impacto"] = {
            "k_delta": {s: {k: Kp[s][k] for k in ("k_delta", "r2", "convergencia_rad")} for s in ("media", "esquerda", "direita")},
            "linearidade": Kp["linearidade"], "L": Lp["L"], "x_v": Lp["x_v"],
            "reserva_k_delta": Lp["reserva_k_delta"]["k_delta"]}
    clean = lambda d: {k: v for k, v in d.items() if not str(k).startswith("_")}
    payload = {
        "pedido": 39, "parte": "D", "commit": git_commit(), "comando": "python -m ml.scripts.m1_modelo_carro geometria --sessao " + path.name,
        "sessao": {**file_entry(path), "meta": meta},
        "k_delta": clean(K), "relogio": L, "portoes": gates, "informativo": info,
        "usados": {"L": gates["L"]["usado"], "k_delta": gates["k_delta"]["usado"], "x_v": gates["x_v"]["usado"],
                   "cg_height": L["cg_height"], "h_L": gates["h_L"]["valor"]},
    }
    out = D.raiz_dados() / GEOMETRIA_MEDIDA
    _json(out, payload)
    if args.saida:
        _json(Path(args.saida), payload)
    print(json.dumps({"portoes": gates, "usados": payload["usados"], "informativo": {k: v for k, v in info.items() if k != "antes_do_impacto"}},
                     indent=1, ensure_ascii=False, default=float))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dados")
    sub.add_parser("convencoes")
    retrato = sub.add_parser("retrato")
    retrato.add_argument("--saida")
    geometria = sub.add_parser("geometria")
    geometria.add_argument("--sessao", required=True)
    geometria.add_argument("--saida")
    args = parser.parse_args(argv)
    return {"dados": cmd_dados, "convencoes": cmd_convencoes, "retrato": cmd_retrato,
            "geometria": cmd_geometria}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
