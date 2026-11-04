"""O retreino da LSTM geradora com as tres fontes, na regua do ADR 0026.

Aqui ficam as pecas que precisam de teste: quais voltas entram, como cada rodada
divide as sessoes, como a linha da F1 entra no treino e como os numeros da regua
saem. O laco de treino e o de `training`, e a orquestracao fica em
`ml.scripts.retreino_lstm`.

As gravacoes e o store so sao lidos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from .. import config
from ..comparison.evolution import group_sessions
from ..data.lap_store import STORE_COLUMNS, StoredLaps
from ..data.origin import AI, HUMAN
from ..data.recordings import list_all_sessions
from ..data.store_v2 import load_store_v2, store_v2_meta
from ..features.engineering import track_features
from ..modelo2.dados import read_outside, recording_period, store_selection
from ..track.geometry import TrackGeometry
from .sequences import (
    CONTEXT_FEATURES,
    REFERENCE_TASK,
    SequenceSet,
    TaskSpec,
    _circular_windows,
    drop_warmup,
    full_lap_sequence,
    with_warmup,
)

# Gravacoes a partir daqui sao posteriores ao store v2 (construido em 22/10, 00:34 local).
OUTSIDE_SINCE = "2026-10-22"
# So rotulos pelo indicador do jogo ou por anotacao, nunca pelo detector (ADR 0018).
LABELLED_SOURCES = ("indicador", "anotacao", "anotacao_sessao")

MIN_VALIDATION_FRACTION = 0.15     # ADR 0026: a validacao de parada soma ao menos isto das voltas de treino
PACE_LIMIT_S = 88.0                # o corte da auditoria (docs/auditoria_ml.md, secao 3)
BOOTSTRAP_DRAWS = 10_000
BOOTSTRAP_SEED = 44

# Os criterios do ADR 0026, fixados antes de rodar.
MIN_SKILL = 0.20
MIN_POSITIVE_SESSIONS = 0.70
MIN_TESTABLE_SESSIONS = 5

F1_REFERENCE_FILE = ("externo", "f1_referencia", "referencia_2023_25.csv")
# So a posicao da F1 entra (ADRs 0018 e 0019): e tudo que se le do arquivo.
F1_READ_COLUMNS = ("lateral", "pouco_confiavel")
F1_TARGET = "lateral"


@dataclass
class Sources:
    """As voltas do treino: o store combinado e de onde cada uma veio."""

    store: StoredLaps
    table: pd.DataFrame        # lap_id, gravacao, sessao, origem, origem_fonte, fora_do_store, lap_time_s
    outside_report: Dict[str, List[Dict[str, object]]] = field(default_factory=dict)


def select_store_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """As voltas do store que entram: `humano` atual e `ia` rotuladas, nunca pelo detector nem `desconhecida`."""
    selected = store_selection(laps)
    return selected[selected["origem"].isin((HUMAN, AI)) & selected["origem_fonte"].isin(LABELLED_SOURCES)]


def load_sources(track: TrackGeometry, progress=print) -> Sources:
    """Le as voltas das fontes reais. As de fora do store sao lidas sem gravar nele."""
    meta = store_v2_meta()
    if not meta or not meta.get("aprovado"):
        raise SystemExit("PARADO: store v2 ausente ou nao aprovado.")
    store = load_store_v2(track=track)
    selected = select_store_laps(store.laps)

    available = {s.session_id: s for s in list_all_sessions()}
    stored = set(store.laps["session_id"])
    outside_ids = sorted(sid for sid in available if sid[:10] >= OUTSIDE_SINCE and sid not in stored)
    outside, report = [], {}
    for sid in outside_ids:
        progress(f"  fora do store: {sid}")
        laps, entries, _ = read_outside(available[sid], track)
        outside.extend(laps)
        report[sid] = entries

    columns = ["lap_id", "grid_index", *[c for c in STORE_COLUMNS if c in store.frame.columns]]
    frames = [store.frame.loc[store.frame["lap_id"].isin(selected["lap_id"]), columns]]
    rows = [
        {
            "lap_id": row["lap_id"], "gravacao": row["session_id"], "session_id": row["session_id"],
            "origem": row["origem"], "origem_fonte": row["origem_fonte"], "fora_do_store": False,
            "lap_time_s": float(row["lap_time_s"]),
        }
        for _, row in selected.iterrows()
    ]
    for volta in outside:
        grid = volta.grid.reset_index(drop=True).copy()
        grid["lap_id"] = volta.lap_id
        grid["grid_index"] = np.arange(len(grid))
        frames.append(grid.reindex(columns=columns))
        rows.append({
            "lap_id": volta.lap_id, "gravacao": volta.gravacao, "session_id": volta.gravacao,
            "origem": volta.origem, "origem_fonte": "indicador", "fora_do_store": True,
            "lap_time_s": float(volta.tempo_s),
        })

    table = pd.DataFrame(rows)
    periods = dict(meta.get("periodos_das_gravacoes") or {})
    for gravacao in table["gravacao"].unique():
        periods.setdefault(gravacao, recording_period(gravacao, pd.DataFrame()))
    sessions = group_sessions({g: periods[g] for g in table["gravacao"].unique()})
    table["sessao"] = table["gravacao"].map(sessions)
    table = table.sort_values(["sessao", "lap_id"]).reset_index(drop=True)

    frame = pd.concat(frames, ignore_index=True).sort_values(["lap_id", "grid_index"]).reset_index(drop=True)
    combined = StoredLaps(
        frame=frame, laps=table, grid_size=store.grid_size, track_length=store.track_length,
        geometry_id=store.geometry_id, source_hash=store.source_hash, selection=store.selection,
    )
    return Sources(combined, table, report)


# ------------------------------------------------------------ as rodadas ---

@dataclass(frozen=True)
class Fold:
    """Uma rodada: a sessao de fora e as voltas de cada parte."""

    held_out: str
    validation_sessions: Tuple[str, ...]
    test: Tuple[str, ...]
    validation: Tuple[str, ...]
    train: Tuple[str, ...]


def session_order(table: pd.DataFrame) -> List[str]:
    return sorted(table["sessao"].unique())


def build_fold(table: pd.DataFrame, held_out: str,
               min_fraction: float = MIN_VALIDATION_FRACTION) -> Fold:
    """Divide as voltas da rodada pela regra do ADR 0026."""
    order = session_order(table)
    if held_out not in order:
        raise KeyError(f"sessao {held_out} nao existe")
    with_ai = set(table.loc[table["origem"] == AI, "sessao"])
    remaining = table[table["sessao"] != held_out]
    needed = min_fraction * len(remaining)

    start = order.index(held_out)
    chosen: List[str] = []
    count = 0
    for step in range(1, len(order)):
        candidate = order[(start + step) % len(order)]
        if candidate in with_ai:
            continue
        chosen.append(candidate)
        count += int((table["sessao"] == candidate).sum())
        if count >= needed:
            break
    in_validation = remaining["sessao"].isin(chosen)
    return Fold(
        held_out=held_out,
        validation_sessions=tuple(chosen),
        test=tuple(table.loc[table["sessao"] == held_out, "lap_id"]),
        validation=tuple(remaining.loc[in_validation, "lap_id"]),
        train=tuple(remaining.loc[~in_validation, "lap_id"]),
    )


def assert_no_leak(fold: Fold, table: pd.DataFrame) -> None:
    """Nenhuma volta aparece em duas partes, e nenhuma sessao fica dos dois lados."""
    parts = [set(fold.test), set(fold.validation), set(fold.train)]
    if parts[0] & parts[1] or parts[0] & parts[2] or parts[1] & parts[2]:
        raise ValueError("uma volta em duas partes da rodada")
    sessions = table.set_index("lap_id")["sessao"]
    groups: List[Set[str]] = [set(sessions.loc[list(part)]) for part in parts]
    if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
        raise ValueError("uma sessao em duas partes da rodada")


# ---------------------------------------------------------- a linha da F1 ---

def read_f1_line(path: Optional[Path] = None) -> pd.DataFrame:
    """Le so a posicao da F1 e a marca de faixa pouco confiavel. A lateral fica NaN nos pontos marcados."""
    source = Path(path) if path else config.artifacts_root().joinpath(*F1_REFERENCE_FILE)
    frame = pd.read_csv(source, usecols=list(F1_READ_COLUMNS))
    unreliable = frame["pouco_confiavel"].astype(str).str.lower().isin(("true", "1"))
    return pd.DataFrame({"lateral": frame["lateral"].where(~unreliable).to_numpy(dtype=float),
                         "pouco_confiavel": unreliable.to_numpy()})


def f1_inputs(track: TrackGeometry, corners, context: Dict[str, float],
              task: TaskSpec = REFERENCE_TASK) -> np.ndarray:
    """(grade, n_in): a pista, perda 0 e o contexto medio do treino da rodada."""
    frame = track_features(track, corners).copy()
    frame["sector_loss_s"] = 0.0
    frame["lap_loss_s"] = 0.0
    for name in CONTEXT_FEATURES:
        frame[name] = float(context[name])
    missing = [c for c in task.inputs if c not in frame.columns]
    if missing:
        raise KeyError(f"faltam atributos para a linha da F1: {missing}")
    return np.nan_to_num(frame.reindex(columns=list(task.inputs)).to_numpy(dtype=np.float32), nan=0.0)


def f1_sequences(track: TrackGeometry, corners, context: Dict[str, float], repeat: int,
                 line: Optional[pd.DataFrame] = None, task: TaskSpec = REFERENCE_TASK) -> SequenceSet:
    """As janelas da F1: so a lateral como alvo, repetidas `repeat` vezes (ADR 0026).

    Velocidade, freio e acelerador ficam NaN, e a perda ignora alvos ausentes.
    """
    line = read_f1_line() if line is None else line
    lateral = line["lateral"].to_numpy(dtype=float)
    if lateral.size != track.size:
        raise ValueError(f"a linha da F1 tem {lateral.size} pontos, e a grade, {track.size}")
    if F1_TARGET not in task.targets:
        raise ValueError(f"a tarefa {task.name} nao tem a lateral como alvo")

    target = np.full((track.size, len(task.targets)), np.nan, dtype=np.float32)
    target[:, list(task.targets).index(F1_TARGET)] = lateral
    source = f1_inputs(track, corners, context, task)

    index = _circular_windows(track.size, task.window, task.stride)
    usable = np.isfinite(target[index]).any(axis=(1, 2))
    index = index[usable]
    copies = max(int(repeat), 1)
    return SequenceSet(
        inputs=np.repeat(source[index], copies, axis=0),
        targets=np.repeat(target[index], copies, axis=0),
        lap_ids=np.full(int(index.shape[0]) * copies, "f1_referencia_2023_25", dtype=object),
        start_index=np.repeat(index[:, 0], copies, axis=0),
        input_columns=task.inputs,
        target_columns=task.targets,
    )


def train_context(frames: Dict[str, pd.DataFrame], lap_ids: Sequence[str]) -> Dict[str, float]:
    """A media de combustivel, desgaste e aderencia nas voltas de treino da rodada."""
    return {
        name: float(np.nanmean(np.concatenate(
            [frames[lap][name].to_numpy(dtype=float) for lap in lap_ids]
        )))
        for name in CONTEXT_FEATURES
    }


def f1_repeat(table: pd.DataFrame, lap_ids: Sequence[str]) -> int:
    """A mediana de voltas por sessao de treino, arredondada: o peso de uma sessao tipica."""
    counts = table[table["lap_id"].isin(lap_ids)].groupby("sessao").size()
    return max(int(round(float(counts.median()))), 1)


# ------------------------------------------------------------- as medidas ---

def predict_lap(trained, frame: pd.DataFrame, task: TaskSpec, pad: Optional[int] = None) -> np.ndarray:
    """A volta inteira, com o aquecimento de `generate`, na saida crua da rede: (grade, n_out)."""
    warmup = task.window if pad is None else int(pad)
    inputs = full_lap_sequence(frame, task)
    return drop_warmup(trained.predict(with_warmup(inputs, warmup)), warmup)[0]


def channel_error(predicted: np.ndarray, actual: np.ndarray) -> float:
    """Media de |previsto - real| nos pontos em que o real existe."""
    values = np.abs(np.asarray(predicted, dtype=float) - np.asarray(actual, dtype=float))
    return float(np.nanmean(values))


def naive_reference(frames: Dict[str, pd.DataFrame], lap_ids: Sequence[str],
                    columns: Sequence[str]) -> Dict[str, np.ndarray]:
    """A mediana das voltas de treino, ponto a ponto. Nunca inclui a F1."""
    return {
        column: np.nanmedian(
            np.vstack([frames[lap][column].to_numpy(dtype=float) for lap in lap_ids]), axis=0
        )
        for column in columns
    }


def skill(model_error: float, reference_error: float) -> float:
    return float(1.0 - model_error / reference_error) if reference_error > 0 else float("nan")


def session_sums(errors: pd.DataFrame, model: str = "erro_modelo_m", reference: str = "erro_ingenuo_m",
                 session: str = "sessao") -> pd.DataFrame:
    """Soma dos erros por sessao, na ordem das sessoes. E o que o bootstrap reamostra."""
    return errors.groupby(session, sort=True).agg(modelo=(model, "sum"), ingenuo=(reference, "sum"),
                                                  voltas=(model, "size"))


def bootstrap_draws(sessions: int, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> np.ndarray:
    """(draws, sessoes): quantas vezes cada sessao cai em cada reamostragem."""
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, sessions, size=(draws, sessions))
    weights = np.zeros((draws, sessions), dtype=np.int32)
    rows = np.repeat(np.arange(draws), sessions)
    np.add.at(weights, (rows, picks.ravel()), 1)
    return weights


def skill_interval(sums: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> Dict[str, float]:
    """O IC 95% do skill agregado, reamostrando sessoes com reposicao."""
    weights = bootstrap_draws(len(sums), draws, seed)
    model = weights @ sums["modelo"].to_numpy(dtype=float)
    reference = weights @ sums["ingenuo"].to_numpy(dtype=float)
    values = 1.0 - model / reference
    return {"ic95_inf": float(np.percentile(values, 2.5)), "ic95_sup": float(np.percentile(values, 97.5))}


def paired_difference(with_f1: pd.DataFrame, without_f1: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS,
                      seed: int = BOOTSTRAP_SEED) -> Dict[str, float]:
    """Skill com a F1 menos skill sem ela: as mesmas sessoes sorteadas nas duas versoes."""
    if list(with_f1.index) != list(without_f1.index):
        raise ValueError("as duas versoes precisam ter as mesmas sessoes")
    weights = bootstrap_draws(len(with_f1), draws, seed)

    def values(sums: pd.DataFrame) -> np.ndarray:
        return 1.0 - (weights @ sums["modelo"].to_numpy(dtype=float)) / (weights @ sums["ingenuo"].to_numpy(dtype=float))

    difference = values(with_f1) - values(without_f1)
    point = (skill(float(with_f1["modelo"].sum()), float(with_f1["ingenuo"].sum()))
             - skill(float(without_f1["modelo"].sum()), float(without_f1["ingenuo"].sum())))
    return {"diferenca": float(point), "ic95_inf": float(np.percentile(difference, 2.5)),
            "ic95_sup": float(np.percentile(difference, 97.5))}


def criteria(errors: pd.DataFrame) -> Dict[str, object]:
    """A tabela do ADR 0026 para uma versao, a partir do erro de cada volta de teste."""
    sums = session_sums(errors)
    total = skill(float(errors["erro_modelo_m"].mean()), float(errors["erro_ingenuo_m"].mean()))
    interval = skill_interval(sums)
    per_session = 1.0 - sums["modelo"] / sums["ingenuo"]
    positive = float((per_session > 0).mean())
    checks = {
        "skill_minimo": bool(total >= MIN_SKILL),
        "ic95_inferior_positivo": bool(interval["ic95_inf"] > 0),
        "sessoes_com_skill_positivo": bool(positive >= MIN_POSITIVE_SESSIONS),
        "sessoes_testaveis": bool(len(sums) >= MIN_TESTABLE_SESSIONS),
    }
    return {
        "erro_modelo_m": float(errors["erro_modelo_m"].mean()),
        "erro_ingenuo_m": float(errors["erro_ingenuo_m"].mean()),
        "skill": total,
        **interval,
        "skill_medio_por_sessao": float(per_session.mean()),
        "fracao_de_sessoes_com_skill_positivo": positive,
        "sessoes_testaveis": int(len(sums)),
        "voltas": int(len(errors)),
        "skill_por_sessao": {str(k): float(v) for k, v in per_session.items()},
        "criterios": checks,
        "aprovado": bool(all(checks.values())),
    }


def f1_stays(difference: Dict[str, float]) -> bool:
    """A F1 fica so se a diferenca for positiva e o limite inferior do IC ficar acima de 0."""
    return bool(difference["diferenca"] > 0 and difference["ic95_inf"] > 0)


def group_skill(errors: pd.DataFrame, mask: pd.Series) -> Dict[str, object]:
    part = errors[mask]
    if part.empty:
        return {"voltas": 0}
    return {"voltas": int(len(part)), "sessoes": int(part["sessao"].nunique()),
            "erro_modelo_m": float(part["erro_modelo_m"].mean()),
            "erro_ingenuo_m": float(part["erro_ingenuo_m"].mean()),
            "skill": skill(float(part["erro_modelo_m"].mean()), float(part["erro_ingenuo_m"].mean()))}
