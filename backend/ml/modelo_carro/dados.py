"""Os dados da M1: as voltas validas, no cronometro do jogo, em trechos de 50 ms (pedido 37, Parte B).

O que foi registrado antes de construir (`docs/modelo_fisico_m1.md`, 1.1 e 1.2):

* **so as 5 sessoes da contagem oficial,** e nelas so as voltas que estao no
  store v2, cortadas pelas mesmas funcoes do store (`iter_laps`, `clean_lap` e
  `align_lap`). O numero de amostras cruas de cada volta tem de bater com o
  `raw_samples` do meta do store;
* **o relogio e o cronometro do jogo** (`lap_time_s`). O horario do gravador
  nao entra em conta nenhuma;
* **amostra repetida** e a que tem o cronometro igual ou menor que o da ultima
  mantida: a pagina de fisica mudou, o tempo nao andou;
* **um trecho** termina num intervalo de 50 ms ou mais e no fim da volta;
* **a reamostragem** e linear, em `t0 + k*DT` dentro de cada trecho, com o
  `heading` desdobrado antes.

As gravacoes so sao lidas. O que sai fica em `data/ml/modelo_carro/`, fora do
git, com o hash e o tamanho de cada arquivo lido e escrito (ADR 0007).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .. import config
from ..data.recordings import RawLap, Session, _is_new_lap, list_all_sessions
from ..data.samples import flatten, number
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap

# As 5 sessoes da contagem oficial (pedido 36, Parte A; ADR 0022, item 3).
SESSOES_M1 = (
    "2026-10-15_23-24-50_vhe_interlagos",
    "2026-10-17_01-02-22_vhe_interlagos",
    "2026-10-17_16-17-08_vhe_interlagos",
    "2026-10-18_12-38-44_vhe_interlagos",
    "2026-10-21_20-30-54_vhe_interlagos",
)

DT = 0.05            # passo do modelo, s
GAP_S = 0.05         # intervalo que encerra um trecho, s
G = 9.80665

WHEELS = ("fl", "fr", "rl", "rr")

# As colunas que a reamostragem carrega, todas interpoladas linearmente.
COLUNAS = (
    "x", "z", "heading", "speed_kmh",
    "vel_wx", "vel_wy", "vel_wz",
    "velocity_long", "velocity_lat", "yaw_rate",
    "steer_angle", "throttle", "brake",
    "lateral_g", "longitudinal_g",
    "wheel_load_fl", "wheel_load_fr", "wheel_load_rl", "wheel_load_rr",
    "brake_bias", "tyre_core_temp", "s",
)


def raiz_dados() -> Path:
    return config.artifacts_root() / "modelo_carro"


# ------------------------------------------------------------- leitura ---

def linha_m1(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """`flatten` mais o que a M1 precisa e o store nao guarda: a velocidade no mundo e o `brakeBias`."""
    row = flatten(envelope)
    sample = envelope.get("sample") if isinstance(envelope.get("sample"), Mapping) else envelope
    physics = sample.get("carPhysics") if isinstance(sample.get("carPhysics"), Mapping) else {}
    motion = physics.get("motion") if isinstance(physics.get("motion"), Mapping) else {}
    brakes = physics.get("brakes") if isinstance(physics.get("brakes"), Mapping) else {}
    velocity = motion.get("velocity") if isinstance(motion.get("velocity"), Mapping) else {}
    row["vel_wx"] = number(velocity.get("x"))
    row["vel_wy"] = number(velocity.get("y"))
    row["vel_wz"] = number(velocity.get("z"))
    row["brake_bias"] = number(brakes.get("brakeBias"))
    return row


def iter_voltas_m1(session: Session, min_samples: int = 2) -> Iterator[RawLap]:
    """O `iter_laps` do store, com as colunas de `linha_m1`.

    O corte e o mesmo -- a mesma regra de volta nova (`_is_new_lap`) e a mesma
    contagem de ordem --, entao o `lap_id` daqui e o do store. Quem confere e
    `ler_sessao`, contra o `raw_samples` do meta.
    """
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
            row = linha_m1(envelope)
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


# ------------------------------------------- relogio, trechos, grade ---

def descartar_repetidas(frame: pd.DataFrame, clock: str = "lap_time_s") -> Tuple[pd.DataFrame, int]:
    """Tira as amostras cujo cronometro nao andou: igual ou menor que o da ultima mantida.

    Como os tempos mantidos sao crescentes, "a ultima mantida" e o maximo de
    todas as anteriores, mantidas ou nao.
    """
    t = pd.to_numeric(frame[clock], errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(t)
    before = np.concatenate([[-np.inf], np.fmax.accumulate(np.where(finite, t, -np.inf))[:-1]])
    keep = finite & (t > before)
    return frame.loc[keep].reset_index(drop=True), int((~keep).sum())


def cortar_trechos(t: np.ndarray, gap_s: float = GAP_S) -> List[Tuple[int, int]]:
    """Os trechos contiguos, como (inicio, fim exclusivo), cortando em intervalos >= `gap_s`."""
    t = np.asarray(t, dtype=float)
    if t.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(t) >= gap_s - 1e-9) + 1
    edges = np.concatenate([[0], cuts, [t.size]])
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:])]


def reamostrar(frame: pd.DataFrame, columns: Sequence[str] = COLUNAS, dt: float = DT,
               clock: str = "lap_time_s") -> pd.DataFrame:
    """Um trecho reamostrado em `t0 + k*dt`, de `t0` ate a ultima amostra.

    Interpolacao linear; o `heading` e desdobrado antes. Coluna ausente fica NaN.
    """
    t = frame[clock].to_numpy(dtype=float)
    if t.size < 2:
        return pd.DataFrame(columns=["k", "t", *columns])
    steps = int(np.floor((t[-1] - t[0]) / dt + 1e-9))
    grid = t[0] + dt * np.arange(steps + 1)
    out = {"k": np.arange(steps + 1), "t": grid}
    for column in columns:
        if column not in frame.columns:
            out[column] = np.full(grid.size, np.nan)
            continue
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if column == "heading":
            good = np.isfinite(values)
            unwrapped = np.full(values.size, np.nan)
            unwrapped[good] = np.unwrap(values[good])
            values = unwrapped
        good = np.isfinite(values)
        out[column] = np.interp(grid, t[good], values[good]) if good.sum() >= 2 else np.full(grid.size, np.nan)
    return pd.DataFrame(out)


@dataclass
class RelatorioVolta:
    lap_id: str
    amostras_cruas: int
    raw_samples_store: Optional[int]
    tiradas_na_limpeza: int
    repetidas: int
    buracos: int
    trechos: int
    trechos_curtos: int
    passos: int
    segundos: float


def processar_volta(lap: RawLap, geometry, raw_samples_store: Optional[int] = None,
                    dt: float = DT, gap_s: float = GAP_S) -> Tuple[pd.DataFrame, RelatorioVolta]:
    """Uma volta crua -> os trechos reamostrados, com a identidade de cada passo."""
    cleaned, cleaning = clean_lap(lap.frame)
    aligned, _ = align_lap(cleaned, geometry)
    kept, repeated = descartar_repetidas(aligned)
    t = kept["lap_time_s"].to_numpy(dtype=float)
    pieces = cortar_trechos(t, gap_s)
    blocks, short = [], 0
    for number_, (a, b) in enumerate(pieces):
        block = reamostrar(kept.iloc[a:b], dt=dt)
        if len(block) < 2:
            short += 1
            continue
        block.insert(0, "trecho", f"{lap.lap_id}/{number_:03d}")
        block.insert(0, "lap_id", lap.lap_id)
        block.insert(0, "session_id", lap.session_id)
        blocks.append(block)
    frame = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame()
    report = RelatorioVolta(
        lap_id=lap.lap_id, amostras_cruas=int(lap.sample_count), raw_samples_store=raw_samples_store,
        tiradas_na_limpeza=int(cleaning.input_rows - cleaning.output_rows), repetidas=repeated,
        buracos=max(len(pieces) - 1, 0), trechos=len(pieces) - short, trechos_curtos=short,
        passos=int(len(frame)), segundos=float(sum((len(g) - 1) * dt for _, g in frame.groupby("trecho"))) if len(frame) else 0.0,
    )
    return frame, report


# --------------------------------------------------------- sessao toda ---

def voltas_validas(store_meta: Mapping[str, Any], session_id: str) -> Dict[int, Dict[str, Any]]:
    """As voltas da sessao no store v2, pela ordem no arquivo, com o registro do meta."""
    return {int(lap["sequence"]): lap for lap in store_meta["laps"] if lap["session_id"] == session_id}


def sessao_por_id(session_id: str) -> Session:
    for session in list_all_sessions():
        if session.session_id == session_id:
            return session
    raise FileNotFoundError(f"sessao {session_id} nao encontrada nas pastas de gravacoes")


def ler_sessao(session: Session, store_meta: Mapping[str, Any], geometry) -> Tuple[pd.DataFrame, List[RelatorioVolta]]:
    """As voltas validas de uma sessao, reamostradas. Para se o corte nao bater com o do store."""
    wanted = voltas_validas(store_meta, session.session_id)
    blocks, reports = [], []
    for lap in iter_voltas_m1(session):
        record = wanted.get(lap.sequence)
        if record is None:
            continue
        if record["lap_id"] != lap.lap_id or int(record["raw_samples"]) != lap.sample_count:
            raise ValueError(
                f"{lap.lap_id}: o corte nao bate com o do store "
                f"({lap.sample_count} amostras, o store tem {record['raw_samples']} em {record['lap_id']})"
            )
        frame, report = processar_volta(lap, geometry, int(record["raw_samples"]))
        blocks.append(frame)
        reports.append(report)
    missing = sorted(set(wanted) - {int(r.lap_id.split("#")[1]) for r in reports})
    if missing:
        raise ValueError(f"{session.session_id}: voltas do store nao encontradas na gravacao: {missing}")
    return pd.concat(blocks, ignore_index=True), reports


def faixas(frame: pd.DataFrame, columns: Sequence[str]) -> Dict[str, Dict[str, float]]:
    out = {}
    for column in columns:
        values = frame[column].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            out[column] = {"n": 0}
            continue
        p1, p50, p99 = np.percentile(values, [1, 50, 99])
        out[column] = {"n": int(values.size), "min": float(values.min()), "p1": float(p1), "p50": float(p50),
                       "p99": float(p99), "max": float(values.max()), "preenchido": float(values.size / len(frame))}
    return out
