"""O resultado final do Modelo 1 (pedido 46, Parte D; ADR 0028, item 10).

    python -m ml.scripts.modelo1_final [--handoff docs/handoff/<pedido>] [--medidor auto|real|m1v2]

* **o medidor:** o simulador quase-estacionario. Com a M1 v2 aprovada
  (`validacao_v2.json`), o envelope sai da M1 v2; senao, o envelope das voltas
  reais (`data/ml/vehicle_envelope.json`), como esta;
* **a comparacao,** no mesmo medidor: a volta da IA `2026-10-04_03-42-10#0013`,
  a melhor volta do Eduardo `2026-10-24_13-43-32#0003` e as duas linhas geradas;
* **a busca:** o algoritmo genetico registrado (100 individuos, ate 250
  geracoes ou estagnacao), com o corredor do pedido 44, sementes das 150 voltas
  rotuladas (`humano` e `ia`) e a semente aleatoria 46, sem e com a LSTM
  geradora como semente. A aptidao e so a fisica do medidor.

A linha gerada nao vai para o coach (ADR 0009): ela e salva em
`data/ml/modelo1_final/`, com o `geometry_id`, o `corridor_id`, o medidor e o
commit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data.store_v2 import git_commit  # noqa: E402
from ml.features.performance import build_reference  # noqa: E402
from ml.optimization.evolution import EvolutionConfig, evolve  # noqa: E402
from ml.optimization.fitness import FitnessEvaluator, FitnessWeights, fit_shape_reference, shape_metrics  # noqa: E402
from ml.optimization.lap_time_model import simulate  # noqa: E402
from ml.optimization.representation import DEFAULT_CONTROL_SPACING_M, build_encoding  # noqa: E402
from ml.optimization.seed import build_population, composite_best_segments, lateral_by_lap  # noqa: E402
from ml.optimization.vehicle_model import envelope_path, load_envelope  # noqa: E402
from ml.scripts import retreino_lstm as RL  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_corridor_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402
from ml.track.trajectory import corridor_violation  # noqa: E402

VOLTA_IA = "2026-10-04_03-42-10_vhe_interlagos#0013"
VOLTA_EDUARDO = "2026-10-24_13-43-32_vhe_interlagos#0003"
SEMENTE = 46
POPULACAO = 100
GERACOES = 250
LIMITE_H = 6.0


class TempoEsgotado(RuntimeError):
    pass


def raiz() -> Path:
    return config.artifacts_root() / "modelo1_final"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def _arquivo(path: Path) -> dict:
    return {"arquivo": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def medidor(escolha: str):
    """(envelope, descricao). `auto` le o veredito da M1 v2."""
    from ml.modelo_carro import dados as D
    validacao = D.raiz_dados() / "validacao_v2.json"
    aprovada = None
    if validacao.exists():
        aprovada = bool(json.loads(validacao.read_text(encoding="utf-8"))["veredito"]["aprovada"])
    if escolha == "auto":
        if aprovada is None:
            raise SystemExit("PARADO: sem validacao_v2.json, o medidor nao pode ser escolhido pela regra do ADR 0028.")
        escolha = "m1v2" if aprovada else "real"
    real = load_envelope()
    if escolha == "real":
        return real, {"medidor": "simulador quase-estacionario, envelope das voltas reais",
                      "envelope": _arquivo(envelope_path()), "m1_v2_aprovada": aprovada}
    from ml.modelo_carro import fisica_v2 as F2
    treino_path = D.raiz_dados() / "rodadas_treino_v2.json"
    rodadas = json.loads(treino_path.read_text(encoding="utf-8"))["rodadas"]
    p = parametros_medianos(rodadas, real)
    env = F2.envelope(p, real.speed_mps, real.top_speed_mps, real.samples, source_laps=real.source_laps)
    return env, {"medidor": "simulador quase-estacionario, envelope da M1 v2 (mediana das 5 rodadas)",
                 "envelope_das_voltas_reais": _arquivo(envelope_path()), "rodadas_treino_v2": _arquivo(treino_path),
                 "envelope": env.to_dict(), "m1_v2_aprovada": aprovada}


def parametros_medianos(rodadas, real):
    """ADR 0028, item 10 (emenda de 07/11): a mediana de cada parametro nas 5 rodadas; A_env do envelope real."""
    from ml.modelo_carro import fisica_v2 as F2
    first = dict(rodadas[0]["params"])
    values = {}
    for key, value in first.items():
        if key in ("a", "env_speed", "env_traction") or not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        values[key] = float(np.median([r["params"][key] for r in rodadas]))
    values.update(env_speed=np.asarray(real.speed_mps, dtype=float), env_traction=np.asarray(real.traction, dtype=float),
                  pneu=first.get("pneu", "v2"))
    return F2.ParametrosV2(**values)


def tempos_por_microssetor(result, sectors) -> np.ndarray:
    return np.bincount(sectors.index, weights=result.step_time_s, minlength=sectors.count)


def forma(track, lateral, shape) -> dict:
    m = shape_metrics(track, lateral[None, :])
    violation = float(np.mean(corridor_violation(track, lateral)))
    return {"serpenteio": float(m["weaving"][0]), "limite_serpenteio": shape.weaving,
            "variacao_de_curvatura": float(m["curvature_jerk"][0]), "limite_variacao": shape.curvature_jerk,
            "fora_do_corredor_m": violation,
            "dentro": bool(violation == 0.0 and m["weaving"][0] <= shape.weaving
                           and m["curvature_jerk"][0] <= shape.curvature_jerk)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--medidor", choices=("auto", "real", "m1v2"), default="auto")
    parser.add_argument("--handoff", help="prefixo dos arquivos de handoff")
    parser.add_argument("--geracoes", type=int, default=GERACOES)
    args = parser.parse_args(argv)
    started = time.time()

    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    envelope, med = medidor(args.medidor)
    src = RL.load_prepared(track)
    table = src.table[src.table["origem"].isin(["humano", "ia"])].sort_values("lap_time_s")
    laterals_all = lateral_by_lap(src.store, table["lap_id"].tolist())
    finite = {k: v for k, v in laterals_all.items() if np.isfinite(v).all()}
    excluded = sorted(set(table["lap_id"]) - set(finite))
    ordered = [k for k in table["lap_id"] if k in finite]
    laterals = {k: finite[k] for k in ordered}
    for lap in (VOLTA_IA, VOLTA_EDUARDO):
        if lap not in laterals:
            raise SystemExit(f"PARADO: a volta {lap} nao esta entre as voltas rotuladas com a lateral completa.")
    times = table.set_index("lap_id")["lap_time_s"]
    shape = fit_shape_reference(track, np.vstack(list(laterals.values())))
    reference = build_reference(src.store, track, sectors, ordered)
    composite = composite_best_segments(track, sectors, laterals, reference.best_lap_per_sector)
    encoding = build_encoding(track, spacing_m=DEFAULT_CONTROL_SPACING_M)
    weights = FitnessWeights(surrogate_weight=0.0)
    evaluator_args = (track, encoding, envelope, shape, weights, None, None)

    # A LSTM geradora (so a semente; a rede substituta nao entra).
    from ml.models.reference_line import generate
    from ml.models.training import load_model
    lstm_root = config.artifacts_root() / "models" / "reference"
    lstm_line = generate(load_model(lstm_root), track, corners).lateral
    lstm_files = [_arquivo(lstm_root / name) for name in ("model.json", "weights.pt")]

    # O medidor: a mesma linha duas vezes da o mesmo tempo.
    ia_sim = simulate(track, laterals[VOLTA_IA], envelope)
    again = simulate(track, laterals[VOLTA_IA], envelope)
    repetivel = bool(ia_sim.lap_time_s == again.lap_time_s)

    versions = {}
    for name, extra in (("sem_lstm", [composite]), ("com_lstm", [composite, lstm_line])):
        print(f"\nbusca {name}", flush=True)
        population = build_population(encoding, size=POPULACAO, laterals=laterals, extra=extra, seed=SEMENTE)
        evaluator = FitnessEvaluator(*evaluator_args)
        t0 = time.time()

        def progress(text, t0=t0):
            print(text, flush=True)
            if time.time() - started > LIMITE_H * 3600:
                raise TempoEsgotado(f"passou de {LIMITE_H} h")

        result = evolve(evaluator, encoding, population,
                        EvolutionConfig(generations=args.geracoes, population_size=POPULACAO, seed=SEMENTE),
                        progress=progress)
        sim = simulate(track, result.best_lateral, envelope)
        hist = result.history
        first_below_ia = next((h["generation"] for h in hist if h.get("best_cost", np.inf) <= ia_sim.lap_time_s), None)
        versions[name] = {"result": result, "sim": sim, "tempo_s": round(time.time() - t0, 1),
                          "primeira_geracao_abaixo_da_ia": first_below_ia}
        np.save(raiz_mk() / f"linha_{name}.npy", result.best_lateral)

    lines = {
        "volta da IA": laterals[VOLTA_IA],
        "volta da IA, codificada": encoding.decode(encoding.encode(laterals[VOLTA_IA])),
        "melhor volta do Eduardo": laterals[VOLTA_EDUARDO],
        "melhor volta do Eduardo, codificada": encoding.decode(encoding.encode(laterals[VOLTA_EDUARDO])),
        "composicao dos melhores trechos": composite,
        "linha da LSTM geradora": lstm_line,
        "linha gerada sem a LSTM": versions["sem_lstm"]["result"].best_lateral,
        "linha gerada com a LSTM": versions["com_lstm"]["result"].best_lateral,
    }
    sims = {k: simulate(track, v, envelope) for k, v in lines.items()}
    ia_sectors = tempos_por_microssetor(sims["volta da IA"], sectors)
    table_out = {}
    for k, s in sims.items():
        sec = tempos_por_microssetor(s, sectors)
        table_out[k] = {"tempo_s": s.lap_time_s, "diferenca_para_a_ia_s": s.lap_time_s - sims["volta da IA"].lap_time_s,
                        "percurso_m": s.path_length_m, "forma": forma(track, lines[k], shape),
                        "por_microssetor_contra_a_ia_s": (sec - ia_sectors).tolist()}
    for lap, label in ((VOLTA_IA, "volta da IA"), (VOLTA_EDUARDO, "melhor volta do Eduardo")):
        table_out[label]["cronometro_s"] = float(times[lap])
    criterio = {}
    for name in ("sem_lstm", "com_lstm"):
        label = "linha gerada sem a LSTM" if name == "sem_lstm" else "linha gerada com a LSTM"
        row = table_out[label]
        criterio[name] = {"tempo_s": row["tempo_s"], "ia_s": table_out["volta da IA"]["tempo_s"],
                          "mais_rapida_ou_igual_a_ia": row["tempo_s"] <= table_out["volta da IA"]["tempo_s"],
                          "forma_e_corredor": row["forma"]["dentro"]}
        criterio[name]["aprovada"] = bool(criterio[name]["mais_rapida_ou_igual_a_ia"] and criterio[name]["forma_e_corredor"])
    a, b = lines["linha gerada sem a LSTM"], lines["linha gerada com a LSTM"]
    payload = {
        "pedido": 46, "parte": "D", "commit": git_commit(), "comando": "python -m ml.scripts.modelo1_final",
        "ambiente": {"python": platform.python_version(), "plataforma": platform.platform()},
        "geometry_id": track.geometry_id, "corridor_id": track.corridor_id, **med,
        "medidor_repetivel": repetivel, "erro_conhecido_do_medidor_s": 1.36,
        "voltas": {"rotuladas": int(len(table)), "com_lateral_completa": len(ordered), "sem_lateral_completa": excluded,
                   "humano": int((table["origem"] == "humano").sum()), "ia": int((table["origem"] == "ia").sum())},
        "forma_limites": shape.to_dict(), "lstm": lstm_files,
        "busca": {name: {"geracoes": v["result"].generations_run, "parada": v["result"].stopped_by,
                         "avaliacoes": v["result"].evaluations, "custo_inicial": v["result"].initial_cost,
                         "custo_final": v["result"].best_cost, "tempo_s": v["tempo_s"],
                         "primeira_geracao_abaixo_da_ia": v["primeira_geracao_abaixo_da_ia"],
                         "historia": v["result"].history} for name, v in versions.items()},
        "config": {**EvolutionConfig(generations=args.geracoes, population_size=POPULACAO, seed=SEMENTE).to_dict(),
                   "populacao_inicial_semente": SEMENTE, "espacamento_m": DEFAULT_CONTROL_SPACING_M,
                   "aptidao": weights.to_dict()},
        "tempos": table_out, "criterio": criterio,
        "distancia_entre_as_linhas_m": {"media": float(np.mean(np.abs(a - b))), "max": float(np.max(np.abs(a - b))),
                                        "rms": float(np.sqrt(np.mean((a - b) ** 2)))},
        "tempo_total_s": round(time.time() - started, 1),
        "aviso": "A linha gerada nao vai para o coach (ADR 0009). Tempo simulado, nao tempo de pista.",
    }
    (raiz_mk() / "resultado.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    if args.handoff:
        slim = {**payload, "busca": {k: {kk: vv for kk, vv in v.items() if kk != "historia"} for k, v in payload["busca"].items()}}
        Path(str(args.handoff) + "_modelo1.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False, default=float),
                                                             encoding="utf-8")
        figuras(track, sims, lines, sectors, Path(str(args.handoff)), versions)
    for k, v in table_out.items():
        print(f"{k:40s} {v['tempo_s']:8.3f} s  ({v['diferenca_para_a_ia_s']:+.3f} s)  forma ok: {v['forma']['dentro']}")
    print(json.dumps(criterio, indent=1, default=float))
    return 0


def raiz_mk() -> Path:
    out = raiz()
    out.mkdir(parents=True, exist_ok=True)
    return out


def figuras(track, sims, lines, sectors, prefix: Path, versions) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from ml.visualization.track_plots import plot_trajectories

    keys = ["volta da IA", "melhor volta do Eduardo", "linha gerada sem a LSTM", "linha gerada com a LSTM"]
    plot_trajectories(track, [(f"{k} ({sims[k].lap_time_s:.3f} s sim.)", track.s, lines[k]) for k in keys],
                      Path(str(prefix) + "_linhas.png"), title="Interlagos: as linhas no medidor (pedido 46)")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    base = np.cumsum(sims["volta da IA"].step_time_s)
    for k in keys[1:]:
        ax.plot(track.s, np.cumsum(sims[k].step_time_s) - base, label=f"{k} ({sims[k].lap_time_s - sims['volta da IA'].lap_time_s:+.3f} s)")
    ax.axhline(0, color="black", lw=0.8)
    for e in sectors.edges_s[1:-1]:
        ax.axvline(e, color="#eeeeee", lw=0.5, zorder=0)
    ax.set_xlabel("distância na pista (m)")
    ax.set_ylabel("diferença acumulada contra a IA (s)\n(positivo = mais lento)")
    ax.set_title("Diferença de tempo acumulada contra a volta da IA, no medidor")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(Path(str(prefix) + "_diferenca_acumulada.png"), dpi=120)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    for name, v in versions.items():
        hist = v["result"].history
        ax.plot([h["generation"] for h in hist], [h["best_cost"] for h in hist], label=name.replace("_", " "))
    ax.axhline(sims["volta da IA"].lap_time_s, color="black", ls=":", label="volta da IA no medidor")
    ax.set_xlabel("geração")
    ax.set_ylabel("melhor custo (s)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(Path(str(prefix) + "_evolucao.png"), dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    raise SystemExit(main())
