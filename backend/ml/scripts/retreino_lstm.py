"""O retreino da LSTM geradora na regua do ADR 0026 (pedido 44, Partes D e E).

    python -m ml.scripts.retreino_lstm preparar
    python -m ml.scripts.retreino_lstm estimar [--paralelo K] [--threads T] [--epocas N]
    python -m ml.scripts.retreino_lstm todas [--paralelo K] [--threads T]
    python -m ml.scripts.retreino_lstm regua
    python -m ml.scripts.retreino_lstm final [--threads T]
    python -m ml.scripts.retreino_lstm linha

As saidas ficam em `data/ml/retreino_lstm/`; os modelos finais, em `data/ml/models/`.
As gravacoes e o store so sao lidos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml import config  # noqa: E402
from ml.data.lap_store import StoredLaps  # noqa: E402
from ml.data.origin import AI, HUMAN  # noqa: E402
from ml.data.recordings import list_all_sessions  # noqa: E402
from ml.data.store_v2 import git_commit  # noqa: E402
from ml.features.engineering import build_feature_frames  # noqa: E402
from ml.features.performance import build_reference  # noqa: E402
from ml.models import retreino as R  # noqa: E402
from ml.models.lstm import LSTMConfig  # noqa: E402
from ml.models.sequences import REFERENCE_TASK, SURROGATE_TASK, build_sequences, step_time  # noqa: E402
from ml.models.training import TrainConfig, save_model, train_model  # noqa: E402
from ml.track.corners import detect_corners  # noqa: E402
from ml.track.geometry import load_corridor_geometry  # noqa: E402
from ml.track.microsectors import build_microsectors  # noqa: E402

SEM_F1, COM_F1, SUBSTITUTA = "sem_f1", "com_f1", "substituta"
VERSIONS = (SEM_F1, COM_F1, SUBSTITUTA)
CHANNELS = ("lateral", "speed_kmh", "brake", "throttle")
HOURS_LIMIT = 6.0     # Parte D.5: acima disto, parar e propor


def root() -> Path:
    return config.artifacts_root() / "retreino_lstm"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def data_files() -> List[Path]:
    art = config.artifacts_root()
    return [art / "laps_grid_v2.parquet", art / "laps_grid_v2_meta.json",
            art.joinpath(*R.F1_REFERENCE_FILE),
            config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE]


def provenance(track) -> Dict[str, object]:
    """O que o ADR 0007 pede em toda saida, mais o `corridor_id` (ADR 0025)."""
    return {
        "commit": git_commit(),
        "geometry_id": track.geometry_id,
        "corridor_id": track.corridor_id,
        "ambiente": {"python": platform.python_version(), "plataforma": platform.platform()},
        "dados": [{"arquivo": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in data_files()],
    }


# --------------------------------------------------------------- preparar ---

def off_track_check(table: pd.DataFrame) -> List[Dict[str, object]]:
    """Parte D.3: quantas amostras tem o bloco `environment` sem o campo `offTrack`, por gravacao."""
    sessions = {s.session_id: s for s in list_all_sessions()}
    rows = []
    for gravacao in sorted(table["gravacao"].unique()):
        total = with_block = without_field = 0
        with Path(sessions[gravacao].player_stream).open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                total += 1
                if '"environment"' in line:
                    with_block += 1
                    if '"offTrack"' not in line:
                        without_field += 1
        rows.append({"gravacao": gravacao, "amostras": total, "com_o_bloco": with_block,
                     "bloco_sem_offTrack": without_field, "depende_do_false_do_leitor": bool(without_field > 0)})
    return rows


def prepare() -> Dict[str, object]:
    track = load_corridor_geometry()
    sources = R.load_sources(track)
    table = sources.table
    # `lap_features` le o tempo da volta na primeira linha da grade: confere se ele e o tempo da volta.
    first = sources.store.frame.groupby("lap_id")["lap_time_s"].first()
    drift = (first - table.set_index("lap_id")["lap_time_s"]).abs()

    out = root()
    out.mkdir(parents=True, exist_ok=True)
    sources.store.frame.to_parquet(out / "voltas.parquet")
    table.to_parquet(out / "voltas_tabela.parquet")
    summary = {
        "pedido": "docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md",
        "adr": "docs/decisoes/0026-retreino-da-lstm-geradora.md",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        **provenance(track),
        "store": {"grid_size": sources.store.grid_size, "track_length": sources.store.track_length,
                  "source_hash": sources.store.source_hash},
        "voltas": int(len(table)),
        "por_origem": {str(k): int(v) for k, v in table["origem"].value_counts().items()},
        "por_fonte_do_rotulo": {str(k): int(v) for k, v in table["origem_fonte"].value_counts().items()},
        "fora_do_store": int(table["fora_do_store"].sum()),
        "por_sessao": [
            {"sessao": str(s), "gravacoes": sorted(g["gravacao"].unique().tolist()),
             "humano": int((g["origem"] == HUMAN).sum()), "ia": int((g["origem"] == AI).sum()),
             "fora_do_store": int(g["fora_do_store"].sum()), "melhor_s": float(g["lap_time_s"].min()),
             "mediana_s": float(g["lap_time_s"].median())}
            for s, g in table.groupby("sessao")
        ],
        "tempo_da_primeira_linha_contra_o_da_volta_max_s": float(drift.max()),
        "fora_de_pista": off_track_check(table),
        "relatorio_de_fora_do_store": sources.outside_report,
    }
    (out / "fontes.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return summary


def load_prepared(track) -> R.Sources:
    meta = json.loads((root() / "fontes.json").read_text(encoding="utf-8"))
    if meta["corridor_id"] != track.corridor_id or meta["geometry_id"] != track.geometry_id:
        raise SystemExit(f"PARADO: as voltas foram preparadas com {meta['geometry_id']}/{meta['corridor_id']}.")
    frame = pd.read_parquet(root() / "voltas.parquet")
    table = pd.read_parquet(root() / "voltas_tabela.parquet")
    store = StoredLaps(frame=frame, laps=table, grid_size=int(meta["store"]["grid_size"]),
                       track_length=float(meta["store"]["track_length"]), geometry_id=track.geometry_id,
                       source_hash=meta["store"]["source_hash"])
    return R.Sources(store, table)


# ----------------------------------------------------------------- rodada ---

def lap_row(lap_id: str, table: pd.DataFrame) -> Dict[str, object]:
    row = table.set_index("lap_id").loc[lap_id]
    return {"lap_id": lap_id, "sessao": row["sessao"], "origem": row["origem"],
            "fora_do_store": bool(row["fora_do_store"]), "tempo_s": float(row["lap_time_s"])}


def architecture(task) -> LSTMConfig:
    return LSTMConfig(input_size=len(task.inputs), output_size=len(task.targets),
                      target_columns=tuple(task.targets), input_columns=tuple(task.inputs))


def round_frames(sources: R.Sources, track, sectors, corners, reference_laps):
    reference = build_reference(sources.store, track, sectors, list(reference_laps))
    return reference, build_feature_frames(sources.store, track, sectors, corners, reference)


def run_round(held_out: str, version: str, threads: int, epochs: Optional[int] = None) -> Dict[str, object]:
    import torch

    torch.set_num_threads(int(threads))
    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    sources = load_prepared(track)
    table = sources.table
    fold = R.build_fold(table, held_out)
    R.assert_no_leak(fold, table)
    if not fold.train or not fold.validation or not fold.test:
        raise SystemExit(f"PARADO: rodada {held_out} sem voltas numa das partes.")

    reference, frames = round_frames(sources, track, sectors, corners, fold.train)
    task = SURROGATE_TASK if version == SUBSTITUTA else REFERENCE_TASK
    train_set = build_sequences(frames, task, list(fold.train))
    validation_set = build_sequences(frames, task, list(fold.validation))
    extra, repeat = None, 0
    if version == COM_F1:
        repeat = R.f1_repeat(table, fold.train)
        extra = R.f1_sequences(track, corners, R.train_context(frames, fold.train), repeat, task=task)

    settings = TrainConfig() if epochs is None else TrainConfig(epochs=int(epochs), patience=int(epochs) + 1)
    trained = train_model(task, train_set, validation_set, model_config=architecture(task), config=settings,
                          verbose=False, extra_train=extra)

    rows = []
    if version == SUBSTITUTA:
        for lap_id in fold.test:
            frame = frames[lap_id].copy()
            frame["step_time_s"] = step_time(frame)
            predicted = R.predict_lap(trained, frame, task)[:, 0]
            actual = frame["step_time_s"].to_numpy(dtype=float)
            naive = np.nanmedian(np.vstack([step_time(frames[i]) for i in fold.train]), axis=0)
            rows.append({**lap_row(lap_id, table),
                         "erro_por_passo_s": R.channel_error(predicted, actual),
                         "erro_por_passo_ingenuo_s": R.channel_error(naive, actual),
                         "tempo_previsto_s": float(np.nansum(predicted)),
                         "tempo_real_s": float(np.nansum(actual)),
                         "tempo_ingenuo_s": float(np.nansum(naive))})
    else:
        naive = R.naive_reference(frames, fold.train, CHANNELS)
        for lap_id in fold.test:
            frame = frames[lap_id]
            predicted = R.predict_lap(trained, frame, task)
            row = lap_row(lap_id, table)
            for index, channel in enumerate(task.targets):
                actual = frame[channel].to_numpy(dtype=float)
                row[f"erro_{channel}"] = R.channel_error(predicted[:, index], actual)
                row[f"ingenuo_{channel}"] = R.channel_error(naive[channel], actual)
            row["lateral_completa"] = bool(np.isfinite(frame["lateral"].to_numpy(dtype=float)).all())
            row["erro_modelo_m"] = row["erro_lateral"]
            row["erro_ingenuo_m"] = row["ingenuo_lateral"]
            rows.append(row)

    return {
        "sessao_de_fora": held_out, "versao": version,
        "validacao": list(fold.validation_sessions),
        "voltas": {"treino": len(fold.train), "validacao": len(fold.validation), "teste": len(fold.test)},
        "janelas": {"treino": len(train_set), "validacao": len(validation_set), "f1": 0 if extra is None else len(extra)},
        "repeticoes_da_f1": repeat,
        "melhor_volta_do_treino_s": reference.best_lap_time,
        "melhor_epoca": trained.best_epoch, "epocas": len(trained.history),
        "segundos": trained.seconds, "threads": int(threads),
        "corridor_id": track.corridor_id, "geometry_id": track.geometry_id, "commit": git_commit(),
        "historico": trained.history,
        "erros": rows,
    }


def round_path(version: str, held_out: str) -> Path:
    return root() / "rodadas" / version / f"{held_out}.json"


def check_finished_rounds(track, versions=VERSIONS) -> None:
    """Uma rodada de outro corredor nao pode ser somada as novas (ADR 0025)."""
    for version in versions:
        for path in sorted((root() / "rodadas" / version).glob("*.json")):
            recorded = json.loads(path.read_text(encoding="utf-8"))["corridor_id"]
            if recorded != track.corridor_id:
                raise SystemExit(f"PARADO: {path} e do corredor {recorded}, e o de agora e {track.corridor_id}.")


def run_all(parallel: int, threads: int, versions=VERSIONS) -> None:
    """As rodadas que faltam, em `parallel` processos. O que ja terminou nao roda de novo."""
    check_finished_rounds(load_corridor_geometry(), versions)
    table = pd.read_parquet(root() / "voltas_tabela.parquet")
    pending = [(v, s) for v in versions for s in R.session_order(table) if not round_path(v, s).exists()]
    print(f"{len(pending)} rodadas", flush=True)
    running: List = []
    logs = root() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    started = time.time()
    backend = Path(__file__).resolve().parents[2]
    while pending or running:
        while pending and len(running) < parallel:
            version, session = pending.pop(0)
            handle = (logs / f"{version}_{session}.log").open("w", encoding="utf-8")
            process = subprocess.Popen(
                [sys.executable, "-m", "ml.scripts.retreino_lstm", "rodada", "--sessao", session,
                 "--versao", version, "--threads", str(threads)],
                cwd=str(backend), stdout=handle, stderr=subprocess.STDOUT,
            )
            running.append((process, version, session, handle))
        time.sleep(5)
        for item in list(running):
            process, version, session, handle = item
            code = process.poll()
            if code is None:
                continue
            handle.close()
            running.remove(item)
            print(f"[{(time.time() - started) / 60:6.1f} min] {version} {session}: saida {code}; "
                  f"faltam {len(pending)} + {len(running)}", flush=True)
            if code != 0:
                for other in running:
                    other[0].terminate()
                raise SystemExit(f"PARADO: a rodada {version} {session} falhou; veja {logs}.")


def estimate(parallel: int, threads: int, epochs: int) -> Dict[str, object]:
    """Parte D.5: mede a velocidade real rodando `parallel` treinos curtos juntos, com a F1."""
    table = pd.read_parquet(root() / "voltas_tabela.parquet")
    sessions = R.session_order(table)
    held = [sessions[(k * 3) % len(sessions)] for k in range(parallel)]
    backend = Path(__file__).resolve().parents[2]
    started = time.time()
    processes = [subprocess.Popen(
        [sys.executable, "-m", "ml.scripts.retreino_lstm", "rodada", "--sessao", s, "--versao", COM_F1,
         "--threads", str(threads), "--epocas", str(epochs), "--medir"],
        cwd=str(backend), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) for s in held]
    measured = []
    for process in processes:
        out, _ = process.communicate()
        if process.returncode != 0:
            raise SystemExit("PARADO: o treino de medida falhou.")
        measured.append(json.loads(out.strip().splitlines()[-1]))
    per_epoch = float(np.mean([m["segundos"] / m["epocas"] for m in measured]))
    return {"paralelo": parallel, "threads": threads, "epocas_de_medida": epochs,
            "segundos_por_epoca_em_cada_processo": per_epoch, "parede_s": time.time() - started,
            "janelas": measured[0]["janelas"]}


# ------------------------------------------------------------------ regua ---

def load_rounds(version: str, sessions: List[str]) -> List[Dict[str, object]]:
    return [json.loads(round_path(version, s).read_text(encoding="utf-8")) for s in sessions]


def channel_summary(errors: pd.DataFrame) -> Dict[str, object]:
    out = {}
    for channel in CHANNELS:
        out[channel] = {"erro_modelo": float(errors[f"erro_{channel}"].mean()),
                        "erro_ingenuo": float(errors[f"ingenuo_{channel}"].mean()),
                        "skill": R.skill(float(errors[f"erro_{channel}"].mean()), float(errors[f"ingenuo_{channel}"].mean()))}
    return out


def version_table(rounds: List[Dict[str, object]]) -> Dict[str, object]:
    errors = pd.DataFrame([row for r in rounds for row in r["erros"]])
    testable = errors[errors["lateral_completa"]]
    result = R.criteria(testable)
    result["voltas_sem_lateral_completa"] = int((~errors["lateral_completa"]).sum())
    result["canais"] = channel_summary(testable)
    result["por_ritmo"] = {
        "abaixo_de_88_s": R.group_skill(testable, testable["tempo_s"] < R.PACE_LIMIT_S),
        "de_88_s_em_diante": R.group_skill(testable, testable["tempo_s"] >= R.PACE_LIMIT_S),
    }
    result["por_fonte"] = {
        "voltas_do_eduardo": R.group_skill(testable, testable["origem"] == HUMAN),
        "voltas_da_ia": R.group_skill(testable, testable["origem"] == AI),
    }
    result["melhor_epoca_mediana"] = int(np.median([r["melhor_epoca"] for r in rounds]))
    result["melhor_epoca_por_rodada"] = {r["sessao_de_fora"]: r["melhor_epoca"] for r in rounds}
    result["segundos_de_treino"] = float(sum(r["segundos"] for r in rounds))
    result["por_sessao"] = [
        {"sessao": r["sessao_de_fora"], "voltas": r["voltas"]["teste"], "validacao": r["validacao"],
         "melhor_epoca": r["melhor_epoca"], "epocas": r["epocas"],
         "repeticoes_da_f1": r.get("repeticoes_da_f1", 0),
         "erro_modelo_m": float(pd.DataFrame(r["erros"])["erro_modelo_m"].mean()),
         "erro_ingenuo_m": float(pd.DataFrame(r["erros"])["erro_ingenuo_m"].mean())}
        for r in rounds
    ]
    return result


def surrogate_table(rounds: List[Dict[str, object]]) -> Dict[str, object]:
    errors = pd.DataFrame([row for r in rounds for row in r["erros"]])
    errors["erro_por_volta_s"] = (errors["tempo_previsto_s"] - errors["tempo_real_s"]).abs()
    errors["erro_por_volta_ingenuo_s"] = (errors["tempo_ingenuo_s"] - errors["tempo_real_s"]).abs()
    return {
        "voltas": int(len(errors)),
        "erro_por_passo_s": float(errors["erro_por_passo_s"].mean()),
        "erro_por_passo_ingenuo_s": float(errors["erro_por_passo_ingenuo_s"].mean()),
        "erro_por_volta_s": float(errors["erro_por_volta_s"].mean()),
        "erro_por_volta_ingenuo_s": float(errors["erro_por_volta_ingenuo_s"].mean()),
        "vies_por_volta_s": float((errors["tempo_previsto_s"] - errors["tempo_real_s"]).mean()),
        "melhor_epoca_mediana": int(np.median([r["melhor_epoca"] for r in rounds])),
        "segundos_de_treino": float(sum(r["segundos"] for r in rounds)),
        "por_sessao": [
            {"sessao": str(s), "voltas": int(len(g)),
             "erro_por_passo_s": float(g["erro_por_passo_s"].mean()),
             "erro_por_volta_s": float(g["erro_por_volta_s"].mean())}
            for s, g in errors.groupby("sessao")
        ],
    }


def f1_alignment_record(track) -> Dict[str, object]:
    from ml.external import f1_line

    base = config.artifacts_root() / "externo"
    summary = json.loads((base / "fastf1_alinhamento_resumo.json").read_text(encoding="utf-8"))
    reference = pd.read_csv(base / "f1_referencia" / "referencia_2023_25.csv")["lateral"].to_numpy(dtype=float)
    excess = f1_line.excess_summary(f1_line.excess_on_grid(track, reference))
    return {
        "icp_rms_ate_a_linha_central_m": summary["etapa2_alinhamento"]["icp"]["rms_ate_linha_central_m"],
        "escala_m_por_unidade": summary["etapa2_alinhamento"]["escala_m_por_unidade"],
        "diferenca_de_comprimento_pct": summary["etapa2_alinhamento"]["diferenca_pct"],
        "excesso_da_referencia_sobre_o_corredor_novo": {k: excess[k] for k in ("pontos_fora", "fracao_fora", "p95_m", "max_m")},
    }


def ruler() -> Dict[str, object]:
    track = load_corridor_geometry()
    table = pd.read_parquet(root() / "voltas_tabela.parquet")
    sessions = R.session_order(table)
    without_f1 = load_rounds(SEM_F1, sessions)
    with_f1 = load_rounds(COM_F1, sessions)
    surrogate = load_rounds(SUBSTITUTA, sessions)
    tables = {SEM_F1: version_table(without_f1), COM_F1: version_table(with_f1)}

    def sums(rounds):
        errors = pd.DataFrame([row for r in rounds for row in r["erros"]])
        return R.session_sums(errors[errors["lateral_completa"]])

    difference = R.paired_difference(sums(with_f1), sums(without_f1))
    keep = R.f1_stays(difference)
    chosen = COM_F1 if keep else SEM_F1
    result = {
        "pedido": "docs/prompts/2026-10-29_44_corredor-e-retreino-da-lstm.md",
        "adr": "docs/decisoes/0026-retreino-da-lstm-geradora.md",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        **provenance(track),
        "criterios_fixados": {"skill_minimo": R.MIN_SKILL, "ic95_inferior": "> 0",
                              "sessoes_com_skill_positivo": R.MIN_POSITIVE_SESSIONS, "sessoes_testaveis": R.MIN_TESTABLE_SESSIONS,
                              "bootstrap": {"reamostragens": R.BOOTSTRAP_DRAWS, "semente": R.BOOTSTRAP_SEED}},
        "versoes": tables,
        "f1": {"diferenca_de_skill_com_menos_sem": difference, "a_f1_fica": keep, "alinhamento": f1_alignment_record(track)},
        "modelo_final": {"versao": chosen, "aprovado_na_regua": tables[chosen]["aprovado"],
                         "epocas": tables[chosen]["melhor_epoca_mediana"]},
        "substituta": surrogate_table(surrogate),
    }
    (root() / "resultados.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return result


# ------------------------------------------------------------------ final ---

def final(threads: int) -> Dict[str, object]:
    import torch

    torch.set_num_threads(int(threads))
    results = json.loads((root() / "resultados.json").read_text(encoding="utf-8"))
    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    sources = load_prepared(track)
    table = sources.table
    laps = table["lap_id"].tolist()
    reference, frames = round_frames(sources, track, sectors, corners, laps)
    output = config.artifacts_root() / "models"
    backup = config.artifacts_root() / "_backup_pre_pedido44" / "models" / "reference" / "weights.pt"
    if not backup.exists():
        raise SystemExit("PARADO: os modelos de antes nao estao guardados (ADR 0007).")

    choice = results["modelo_final"]
    extra = None
    if choice["versao"] == COM_F1:
        extra = R.f1_sequences(track, corners, R.train_context(frames, laps), R.f1_repeat(table, laps))
    base = provenance(track)
    reports = {}
    for name, task, epochs, source_extra, tag in (
        ("reference", REFERENCE_TASK, int(choice["epocas"]), extra, choice["versao"]),
        ("surrogate", SURROGATE_TASK, int(results["substituta"]["melhor_epoca_mediana"]), None, SUBSTITUTA),
    ):
        # Rodado de novo, nao refaz o modelo que ja terminou com este corredor e estas rodadas.
        stage = root() / f"final_{name}.json"
        if stage.exists():
            saved = json.loads(stage.read_text(encoding="utf-8"))
            if saved["corridor_id"] == track.corridor_id and saved["versao"] == tag and saved["epocas"] == epochs:
                reports[name] = saved
                continue
        trained = train_model(task, build_sequences(frames, task, laps), None, model_config=architecture(task),
                              config=TrainConfig(epochs=max(epochs, 1), patience=max(epochs, 1) + 1),
                              verbose=False, extra_train=source_extra)
        trained.metadata = {
            **base, "pedido": 44, "adr": "0026", "versao": tag, "voltas": len(laps), "sessoes": int(table["sessao"].nunique()),
            "epocas_fixadas": epochs, "aprovado_na_regua": choice["aprovado_na_regua"] if name == "reference" else None,
        }
        directory = save_model(trained, output / name)
        reports[name] = {"pasta": str(directory), "epocas": epochs, "segundos": trained.seconds,
                         "sha256_pesos": sha256(directory / "weights.pt"), "perda_final": trained.history[-1]["train_loss"],
                         "corridor_id": track.corridor_id, "versao": tag}
        stage.write_text(json.dumps(reports[name], indent=1, ensure_ascii=False), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps({
        **base, "regua": "data/ml/retreino_lstm/resultados.json", "reference": reference.to_dict(),
        "voltas": laps, "modelos": reports,
    }, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return reports


# ------------------------------------------------------------------ linha ---

def distances_by_sector(sectors, lines: Dict[str, np.ndarray], base: str) -> List[Dict[str, object]]:
    rows = []
    for sector in range(sectors.count):
        mask = sectors.index == sector
        row: Dict[str, object] = {"microsetor": sectors.label(sector)}
        for name, values in lines.items():
            if name != base:
                row[name] = round(float(np.nanmedian(np.abs(lines[base][mask] - values[mask]))), 3)
        rows.append(row)
    return rows


def check_line() -> Dict[str, object]:
    from ml.data.store_v2 import load_store_v2
    from ml.models.reference_line import generate, neutral_context
    from ml.models.sequences import drop_warmup, with_warmup
    from ml.models.training import load_model
    from ml.models.reference_line import build_inputs
    from ml.optimization.representation import build_encoding

    track = load_corridor_geometry()
    sectors = build_microsectors(track)
    corners = detect_corners(track)
    trained = load_model(config.artifacts_root() / "models" / "reference")
    encoding = build_encoding(track)
    low, high = track.corridor()

    def outside(values):
        over = (values < low) | (values > high)
        excess = np.maximum(np.maximum(low - values, values - high), 0.0)
        return {"pontos_fora": int(over.sum()), "max_excesso_m": float(excess.max()),
                "s_dos_fora_m": [round(float(s), 1) for s in track.s[over]][:40]}

    pad = REFERENCE_TASK.window
    raw = drop_warmup(trained.predict(with_warmup(build_inputs(track, corners, trained=trained), pad)), pad)[0]
    raw_lateral = raw[:, 0]
    spline = encoding.basis @ encoding.encode(raw_lateral)

    lines = {loss: generate(trained, track, corners, sector_loss=loss, lap_loss=loss, encoding=encoding)
             for loss in (0.0, 0.5)}
    zero, half = lines[0.0], lines[0.5]
    shift = np.abs(half.lateral - zero.lateral)

    store = load_store_v2(track=track)
    coach = json.loads((config.repo_root() / "data" / "reference_models" / "vhe_interlagos.json").read_text(encoding="utf-8"))
    refs = coach.get("references", {})
    lateral_of = lambda lap_id: store.lap(lap_id)["lateral"].to_numpy(dtype=float)  # noqa: E731
    compare = {
        "linha_nova": zero.lateral,
        "ia_do_coach": lateral_of(refs["volta_ia"]["lap_id"]),
        "minha_melhor": lateral_of(refs["minha_melhor"]["lap_id"]),
        "f1": pd.read_csv(config.artifacts_root().joinpath(*R.F1_REFERENCE_FILE))["lateral"].to_numpy(dtype=float),
    }
    per_sector = distances_by_sector(sectors, compare, "linha_nova")
    frame = pd.DataFrame(per_sector)
    result = {
        **provenance(track),
        "modelo": trained.metadata,
        "contexto_neutro": neutral_context(trained),
        "corredor_util_antes_do_corte": {
            "saida_crua_da_rede": outside(raw_lateral),
            "depois_da_projecao_em_splines": outside(spline),
            "linha_final_com_o_corte": outside(zero.lateral),
        },
        "resposta_a_perda": {
            "velocidade_mediana_kmh": {"perda_0": float(np.median(zero.speed_kmh)), "perda_0_5": float(np.median(half.speed_kmh))},
            "deslocamento_da_linha_m": {"mediana": float(np.median(shift)), "p90": float(np.percentile(shift, 90)), "max": float(shift.max())},
        },
        "referencias": {"ia_do_coach": refs["volta_ia"]["lap_id"], "minha_melhor": refs["minha_melhor"]["lap_id"]},
        "distancia_por_microssetor": per_sector,
        "distancia_resumo_m": {c: {"mediana": float(frame[c].median()), "max": float(frame[c].max())}
                               for c in frame.columns if c != "microsetor"},
    }
    (root() / "linha_de_referencia.json").write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Retreino da LSTM geradora (pedido 44)")
    parser.add_argument("acao", choices=("preparar", "estimar", "rodada", "todas", "regua", "final", "linha"))
    parser.add_argument("--sessao")
    parser.add_argument("--versao", choices=VERSIONS, default=SEM_F1)
    parser.add_argument("--threads", type=int, default=max((os.cpu_count() or 2) // 2, 1))
    parser.add_argument("--paralelo", type=int, default=1)
    parser.add_argument("--epocas", type=int, default=None)
    parser.add_argument("--medir", action="store_true", help="so mede o tempo; nao grava a rodada")
    args = parser.parse_args(argv)

    if args.acao == "preparar":
        summary = prepare()
        print(json.dumps({k: summary[k] for k in ("voltas", "por_origem", "por_fonte_do_rotulo", "fora_do_store", "corridor_id")}, ensure_ascii=False))
    elif args.acao == "estimar":
        print(json.dumps(estimate(args.paralelo, args.threads, args.epocas or 3), ensure_ascii=False))
    elif args.acao == "rodada":
        result = run_round(args.sessao, args.versao, args.threads, args.epocas)
        if args.medir:
            print(json.dumps({k: result[k] for k in ("segundos", "epocas", "janelas")}))
        else:
            path = round_path(args.versao, args.sessao)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
            temporary.replace(path)
    elif args.acao == "todas":
        run_all(args.paralelo, args.threads)
    elif args.acao == "regua":
        result = ruler()
        print(json.dumps({"modelo_final": result["modelo_final"], "f1": result["f1"]["diferenca_de_skill_com_menos_sem"]}, ensure_ascii=False))
    elif args.acao == "final":
        print(json.dumps(final(args.threads), ensure_ascii=False))
    elif args.acao == "linha":
        result = check_line()
        print(json.dumps({k: result[k] for k in ("corredor_util_antes_do_corte", "resposta_a_perda", "distancia_resumo_m")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
