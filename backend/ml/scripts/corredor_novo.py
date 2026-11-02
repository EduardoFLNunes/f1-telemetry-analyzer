"""Confere o corredor novo e refaz o que depende dele (pedido 44, Partes B e C).

    python -m ml.scripts.corredor_novo [--saida data/ml/corredor/novo]

So le. O store, o inventario, o coach e as gravacoes ficam como estao, e a
referencia da F1 nao e regravada: o criterio dela e recalculado aqui, com as
laterais ja gravadas pelo pedido 23.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.scripts import conferir_corredor as cc  # noqa: E402

OFFICIAL_GEOMETRY_ID = "0ed16f0dd2225990"
SESSION_TO_COMPARE = "2026-10-10_09-57-09_vhe_interlagos"
OPTION_3 = cc.OPTION_SURFACE
PEDIDO_27 = {"estreito_demais": 6764, "largo_demais": 411}


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def steps_table(track, widths: np.ndarray, raw_layers, sign: float, top: int = 10) -> Dict[str, object]:
    """Os degraus entre pontos vizinhos, o do fechamento do laco e o que ha em cada ponta dos maiores."""
    closed = np.concatenate([widths, widths[:1]])
    jump = np.abs(np.diff(closed))
    rows = []
    for i in np.argsort(-jump)[:top]:
        j = (i + 1) % track.size
        wide = int(i) if widths[i] > widths[j] else int(j)
        # O que existe logo antes da borda do lado mais largo: e essa camada que abriu o degrau.
        probe = track.points[wide] + sign * track.normal[wide] * max(widths[wide] - 0.5, 0.0)
        layers = [layer.name for layer in raw_layers if bool(layer.inside(probe[None, :])[0])]
        rows.append({"s_m": round(float(track.s[i]), 1), "de_m": round(float(widths[i]), 2),
                     "para_m": round(float(widths[j]), 2), "degrau_m": round(float(jump[i]), 2),
                     "camada_junto_da_borda": layers})
    return {"acima_de_0_3m": int((jump > 0.3).sum()), "acima_de_1m": int((jump > 1.0).sum()),
            "acima_de_3m": int((jump > 3.0).sum()), "maior_m": round(float(jump.max()), 3),
            "fechamento_do_laco_m": round(float(abs(widths[-1] - widths[0])), 3), "maiores": rows}


def compare_session(old, new, store) -> Dict[str, object]:
    """O `s` e o `lateral` de uma sessao nas duas geometrias, e contra o store."""
    from ml.data.recordings import iter_laps, list_all_sessions
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.preprocessing.resampling import resample_lap

    session = {s.session_id: s for s in list_all_sessions()}[SESSION_TO_COMPARE]
    stored = set(store.laps["lap_id"])
    laps = samples = 0
    equal = True
    worst_store = 0.0
    for lap in iter_laps(session):
        cleaned, _ = clean_lap(lap.frame)
        a, _ = align_lap(cleaned, old)
        b, _ = align_lap(cleaned, new)
        equal &= np.array_equal(a["s"].to_numpy(), b["s"].to_numpy(), equal_nan=True)
        equal &= np.array_equal(a["lateral"].to_numpy(), b["lateral"].to_numpy(), equal_nan=True)
        laps += 1
        samples += len(a)
        if lap.lap_id in stored:
            grid = resample_lap(b, new, line_clock=True).reset_index(drop=True)
            kept = store.lap(lap.lap_id)["lateral"].to_numpy(dtype=float)
            worst_store = max(worst_store, float(np.nanmax(np.abs(grid["lateral"].to_numpy(dtype=float) - kept))))
    return {"sessao": SESSION_TO_COMPARE, "voltas": laps, "amostras": samples, "ponto_a_ponto_igual": bool(equal),
            "maior_diferenca_para_o_store_m": worst_store}


def coach_check(track) -> Dict[str, object]:
    """O coach so confere o `geometry_id` (ADR 0013): o da geometria exportada e o do modelo."""
    from core.assisted_analysis.official_geometry import geometry_path
    from core.assisted_analysis.reference_model import model_path

    out: Dict[str, object] = {"geometry_id_carregado": track.geometry_id}
    root = config.repo_root()
    for name, path in (("geometria_oficial", geometry_path(root, "vhe_interlagos")), ("modelo_do_coach", model_path(root, "vhe_interlagos"))):
        path = Path(path)
        out[name] = {"arquivo": str(path), "geometry_id": json.loads(path.read_text(encoding="utf-8")).get("geometry_id"),
                     "sha256": sha256(path)}
    out["coach_fala"] = all(out[k]["geometry_id"] == track.geometry_id for k in ("geometria_oficial", "modelo_do_coach"))
    return out


def game_signal(new, old_measures, new_measures, store, lap_ids, sessions, label: str) -> Dict[str, object]:
    edges = cc.option_edges(old_measures)
    check = cc.tyres_out_check(new, new_measures, store, lap_ids, sessions, edges)
    totals = check["totais"]
    options = check["opcoes_da_parte_f"]
    today = cc.OPTION_KEEP
    return {
        "voltas": label, "voltas_usadas": len(check["voltas_usadas"]), "voltas_sem_canal": check["voltas_sem_canal"],
        "corredor_novo": {
            "estreito_demais": int(sum(totals[s]["estreito_demais"] for s in cc.SIDES)),
            "largo_demais": int(sum(totals[s]["largo_demais"] for s in cc.SIDES)),
            "por_lado": {s: {k: totals[s][k] for k in ("amostras", "pneus_fora", "largo_demais", "estreito_demais")} for s in cc.SIDES},
        },
        "pela_conta_da_opcao_3_do_pedido_27": {
            "estreito_demais": int(sum(options[OPTION_3][s]["estreito_demais"] for s in cc.SIDES)),
            "largo_demais": int(sum(options[OPTION_3][s]["largo_demais"] for s in cc.SIDES)),
        },
        "corredor_de_antes": {
            "estreito_demais": int(sum(options[today][s]["estreito_demais"] for s in cc.SIDES)),
            "largo_demais": int(sum(options[today][s]["largo_demais"] for s in cc.SIDES)),
        },
    }


def f1_criterion(old, new) -> Dict[str, object]:
    """Parte C.1: o criterio da F1 com o corredor novo, no alinhamento e em cada volta da faixa."""
    from ml.external import f1_band, f1_line
    from ml.external.f1_reference import era_laps

    root = config.artifacts_root() / "externo"
    grid = pd.read_csv(root / "fastf1_linha_na_grade.csv")["lateral_f1"].to_numpy(dtype=float)
    alignment = {}
    for name, track in (("corredor_de_antes", old), ("corredor_novo", new)):
        summary = f1_line.excess_summary(f1_line.excess_on_grid(track, grid))
        verdict = f1_line.verdict(summary)
        alignment[name] = {k: summary[k] for k in ("pontos_fora", "fracao_fora", "p95_m", "max_m")}
        alignment[name]["aceito"] = verdict["aceito"]

    manifest = json.loads((root / "f1_faixa" / "manifesto.json").read_text(encoding="utf-8"))
    chosen = [r for r in manifest["voltas"] if r.get("etapa") == "escolhida"]
    rows, flips, to_refused, to_accepted = [], [], 0, 0
    era = {r["chave"] for r in era_laps(manifest["voltas"])}
    for record in chosen:
        before = record["criterio"]
        path = root / "f1_faixa" / "voltas" / f"{record['chave']}.csv"
        if not path.exists():
            # Recusada por cobertura ou buraco, que nao dependem do corredor: nao ha como virar aceita.
            if before["cobertura_ok"] and before["buraco_ok"]:
                raise SystemExit(f"PARADO: {record['chave']} sem a lateral gravada e nao recusada por cobertura ou buraco.")
            rows.append({"chave": record["chave"], "ano": record["ano"], "antes": before["veredito"],
                         "depois": before["veredito"], "motivo": "cobertura ou buraco, que nao dependem do corredor"})
            continue
        lateral = pd.read_csv(path)["lateral"].to_numpy(dtype=float)
        summary = f1_line.excess_summary(f1_line.excess_on_grid(new, lateral))
        after = f1_band.lap_verdict(before["cobertura"], before["maior_buraco_m"], summary)
        row = {"chave": record["chave"], "ano": record["ano"], "na_epoca_2023_25": record["chave"] in era,
               "antes": before["veredito"], "depois": after["veredito"],
               "fracao_fora_antes": before["fracao_fora"], "fracao_fora_depois": round(summary["fracao_fora"], 4),
               "p95_antes_m": before["p95_excesso_m"], "p95_depois_m": round(summary["p95_m"], 4)}
        rows.append(row)
        if before["aceita"] != after["aceita"]:
            flips.append(record["chave"])
            to_refused += int(before["aceita"] and not after["aceita"])
            to_accepted += int(after["aceita"] and not before["aceita"])
    reference = pd.read_csv(root / "f1_referencia" / "referencia_2023_25.csv")["lateral"].to_numpy(dtype=float)
    return {
        "alinhamento": alignment,
        "voltas_escolhidas": len(chosen),
        "de_aceita_para_recusada": to_refused,
        "de_recusada_para_aceita": to_accepted,
        "voltas_que_mudam": flips,
        "voltas_da_epoca_que_mudam": [k for k in flips if k in era],
        "referencia_2023_25": {
            name: {k: f1_line.excess_summary(f1_line.excess_on_grid(t, reference))[k] for k in ("pontos_fora", "fracao_fora", "p95_m", "max_m")}
            for name, t in (("corredor_de_antes", old), ("corredor_novo", new))
        },
        "por_volta": rows,
    }


def outside_fraction(old, new, table: pd.DataFrame) -> Dict[str, object]:
    """Parte C.2: `outside_corridor_fraction` nas voltas do treino, nos dois corredores."""
    from ml.data.recordings import iter_laps, list_all_sessions
    from ml.preprocessing.alignment import align_lap
    from ml.preprocessing.cleaning import clean_lap
    from ml.preprocessing.quality import _outside_corridor_fraction

    sessions = {s.session_id: s for s in list_all_sessions()}
    wanted = table.set_index("lap_id")
    rows: List[Dict[str, object]] = []
    for gravacao, group in table.groupby("gravacao"):
        ids = set(group["lap_id"])
        for lap in iter_laps(sessions[gravacao]):
            if lap.lap_id not in ids:
                continue
            cleaned, _ = clean_lap(lap.frame)
            aligned, _ = align_lap(cleaned, new)
            rows.append({"lap_id": lap.lap_id, "origem": wanted.loc[lap.lap_id, "origem"],
                         "sessao": wanted.loc[lap.lap_id, "sessao"],
                         "antes": _outside_corridor_fraction(aligned, old),
                         "depois": _outside_corridor_fraction(aligned, new)})
    frame = pd.DataFrame(rows)
    return {
        "voltas": int(len(frame)),
        "mediana_antes": float(frame["antes"].median()), "mediana_depois": float(frame["depois"].median()),
        "media_antes": float(frame["antes"].mean()), "media_depois": float(frame["depois"].mean()),
        "por_origem": {str(k): {"voltas": int(len(g)), "mediana_antes": float(g["antes"].median()),
                                "mediana_depois": float(g["depois"].median())} for k, g in frame.groupby("origem")},
        "nota": "calculada aqui; a coluna do inventario segue com o corredor de antes, porque o inventario nao muda",
        "por_volta": frame.round(5).to_dict("records"),
    }


def mark_optimised(new) -> Path:
    """O evolutivo de 24/08 fica como esta, marcado como de outra geometria."""
    optimised = config.artifacts_root() / "optimization"
    path = optimised / "PROVENIENCIA_pedido44.json"
    path.write_text(json.dumps({
        "aviso": "optimised_lateral.npy e optimised_speed_mps.npy sao de outra geometria: gravados em 24/08, antes da "
                 "regravacao do cache de 25/08, e com o corredor de antes do ADR 0025. Nao foram refeitos no pedido 44.",
        "geometria": "nao registrada", "corredor": "nao registrado",
        "geometry_id_atual": new.geometry_id, "corridor_id_atual": new.corridor_id,
        "sha256_optimised_lateral": sha256(optimised / "optimised_lateral.npy"),
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def run(out_dir: Path) -> Dict[str, object]:
    from ml.comparison import evolution as ev
    from ml.data.recordings import list_all_sessions
    from ml.data.store_v2 import git_commit, load_store_v2
    from ml.models.retreino import load_sources
    from ml.scripts.alinhar_fastf1 import labelled_ai_laps
    from ml.track.geometry import load_corridor_geometry, load_geometry

    old = load_geometry()
    new = load_corridor_geometry()
    if old.geometry_id != OFFICIAL_GEOMETRY_ID or new.geometry_id != OFFICIAL_GEOMETRY_ID:
        raise SystemExit(f"PARADO: a geometria e {old.geometry_id} / {new.geometry_id}.")
    raw = json.loads((config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE).read_text(encoding="utf-8"))
    centre_closed = np.vstack([old.points, old.points[:1]])
    layers = cc.load_layers(raw, centre_closed, old.s, old.step)
    surface = (layers.asphalt, layers.kerb, layers.paint)

    store = load_store_v2(track=new)
    sessions = list_all_sessions()
    old_measures = cc.measure_track(old, layers)
    new_measures = cc.measure_track(new, layers)

    previous = json.loads((config.artifacts_root() / "corredor" / "resumo.json").read_text(encoding="utf-8"))
    laps_27 = previous["parte_c"]["voltas_usadas"]
    signal_27 = game_signal(new, old_measures, new_measures, store, laps_27, sessions, "as 58 do pedido 27")

    sources = load_sources(new)
    signal_all = game_signal(new, old_measures, new_measures, store, sources.table["lap_id"].tolist(), sessions,
                             "as voltas do treino")

    same_frame = {k: bool(np.array_equal(getattr(old, k), getattr(new, k)))
                  for k in ("s", "x", "z", "elevation", "tangent", "normal", "curvature")}

    # O degrau do fechamento do laco: as larguras cruas do cache nas pontas, antes do reamostrador.
    centre = np.array([[p["x"], p["z"]] for p in raw["centerline"]], dtype=float)
    normal = np.array([[n["x"], n["z"]] for n in raw["normals"]], dtype=float)
    right = np.array([[p["x"], p["z"]] for p in raw["boundsRight"]], dtype=float)
    raw_right = np.abs(np.sum((right - centre) * normal, axis=1))

    out_dir.mkdir(parents=True, exist_ok=True)
    ai = np.vstack([store.lap(i)["lateral"].to_numpy(dtype=float) for i in labelled_ai_laps(store.laps)["lap_id"]])
    mine = np.vstack([store.lap(i)["lateral"].to_numpy(dtype=float) for i in ev.driver_laps(store.laps)["lap_id"]])
    windows = [{**w, "maior_desvio_texto": f"mesmo quadro do pedido 27 (lá: {w['classe']})"} for w in previous["figura"]["quadros"]]
    figure = cc.draw_figure(out_dir / "corredor_novo_x_pintura.png", new, layers, raw, windows, ai, mine,
                            previous=old, title="Corredor novo (laranja) x de antes (pontilhado), nos 8 trechos do pedido 27")

    per_point = pd.DataFrame({"i": np.arange(new.size), "s": np.round(new.s, 1),
                              "largura_esq_antes": np.round(old.width_left, 3), "largura_dir_antes": np.round(old.width_right, 3),
                              "largura_esq_nova": np.round(new.width_left, 3), "largura_dir_nova": np.round(new.width_right, 3)})
    per_point.to_csv(out_dir / "larguras.csv", index=False)

    def widths(values):
        return {"mediana_m": float(np.median(values)), "p10_m": float(np.percentile(values, 10)),
                "p90_m": float(np.percentile(values, 90)), "min_m": float(values.min()), "max_m": float(values.max())}

    marked = mark_optimised(new)
    result = {
        "pedido": "docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md",
        "adr": "docs/decisoes/0025-corredor-pela-borda-da-superficie.md",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "commit": git_commit(),
        "parte_b": {
            "identidade": {"geometry_id_antes": old.geometry_id, "geometry_id_novo": new.geometry_id,
                           "corridor_id_antes": old.corridor_id, "corridor_id_novo": new.corridor_id,
                           "meia_bitola_m": config.CAR_HALF_WIDTH_M, "folga_de_zebra_m": config.KERB_ALLOWANCE_M},
            "grade_igual": same_frame,
            "pontos_que_ficaram_com_a_borda_de_antes": {
                "esquerda": int(np.sum(new.width_left == old.width_left)),
                "direita": int(np.sum(new.width_right == old.width_right))},
            "larguras": {"esquerda_antes": widths(old.width_left), "esquerda_nova": widths(new.width_left),
                         "direita_antes": widths(old.width_right), "direita_nova": widths(new.width_right)},
            "s_e_lateral": compare_session(old, new, store),
            "coach": coach_check(new),
            "sinal_do_jogo": {"referencia_do_pedido_27": PEDIDO_27, "as_58_do_pedido_27": signal_27, "todas_as_do_treino": signal_all},
            "degraus": {
                "esquerda_antes": steps_table(old, old.width_left, surface, 1.0),
                "esquerda_nova": steps_table(new, new.width_left, surface, 1.0),
                "direita_antes": steps_table(old, old.width_right, surface, -1.0),
                "direita_nova": steps_table(new, new.width_right, surface, -1.0),
                "fechamento_cru_do_cache": {
                    "largura_direita_primeiro_vertice_m": float(raw_right[0]),
                    "largura_direita_ultimo_vertice_m": float(raw_right[-1]),
                    "degrau_no_cache_m": float(abs(raw_right[-1] - raw_right[0])),
                },
            },
            "figura": str(figure),
        },
        "parte_c": {
            "criterio_da_f1": f1_criterion(old, new),
            "outside_corridor_fraction": outside_fraction(old, new, sources.table),
            "evolutivo": {"arquivo": str(config.artifacts_root() / "optimization" / "optimised_lateral.npy"),
                          "marcado_em": str(marked)},
        },
    }
    (out_dir / "resumo.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Confere o corredor novo (pedido 44, Partes B e C)")
    parser.add_argument("--saida", type=Path, default=config.artifacts_root() / "corredor" / "novo")
    args = parser.parse_args(argv)
    result = run(args.saida)
    print(json.dumps({k: v for k, v in result["parte_b"].items() if k != "degraus"}, indent=1, ensure_ascii=False, default=str)[:5000])
    print(f"-> {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
