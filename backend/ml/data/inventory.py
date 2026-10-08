"""Inventario de voltas: o que existe no disco e o que serve.

Varre `data/recordings/` uma vez, limpa, alinha e julga cada volta, e escreve
uma tabela onde cada linha e uma volta com seu veredito e os numeros que o
produziram. A varredura completa leva alguns minutos sobre 11 GB, entao o
resultado e persistido -- todo o resto do pipeline le a tabela, nao os JSONL.

A tabela e a analise exploratoria. Ela responde, sem abrir um unico arquivo de
novo: quantas voltas utilizaveis existem, de quantas sessoes, com que
frequencia de amostragem, e quanto tempo separa a melhor da mediana.

Desde o ADR 0014 cada volta diz tambem quem pilotou (`origem`), de que pasta
veio (`pasta`), se o relogio dela bate com a velocidade (`relogio_*`) e se e
a copia de uma volta gravada duas vezes (`duplicada_de`). Ver `origin`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .. import config
from ..preprocessing.alignment import align_lap
from ..preprocessing.cleaning import clean_lap
from ..preprocessing.quality import evaluate_lap
from ..preprocessing.resampling import resample_lap
from ..track.geometry import TrackGeometry, load_geometry
from ..track.microsectors import build_microsectors
from .lap_identity import classify, counter_counts
from .origin import (
    SOURCE_INDICATOR,
    UNKNOWN,
    ai_share,
    equipment_for,
    clock_check,
    clock_summary,
    lap_origin,
    mark_clock,
    mark_duplicates,
    recording_folder,
)
from .recordings import RawLap, Session, iter_laps, list_sessions

# Chamado para cada volta valida com (volta crua, volta alinhada, grade,
# conferencia do relogio por microsetor, linha do inventario).
LapHook = Callable[[RawLap, pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any]], None]

INVENTORY_FILENAME = "lap_inventory.parquet"
INVENTORY_SUMMARY = "lap_inventory_summary.json"


def _record(lap: RawLap, quality, cleaning, alignment) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "lap_id": lap.lap_id,
        "session_id": lap.session_id,
        "sequence": lap.sequence,
        "lap_number": lap.lap_number,
        "driver_id": lap.driver_id,
        "track": lap.track,
        "raw_samples": lap.sample_count,
        "corrupt_lines": lap.corrupt_lines,
        "valid": bool(quality.valid),
        "reasons": "; ".join(quality.reasons),
        "cleaned_samples": cleaning.output_rows,
        "dropped_missing": cleaning.dropped_missing,
        "dropped_duplicate_time": cleaning.dropped_duplicate_time,
    }
    row.update({key: float(value) for key, value in quality.metrics.items()})
    return row


def _provenance(lap: RawLap, folder: str) -> Dict[str, Any]:
    """Quem pilotou, de que pasta veio e quando foi gravada (ADR 0014)."""
    flags = lap.frame["ai_controlled"] if "ai_controlled" in lap.frame.columns else [None] * lap.sample_count
    stamps = (
        pd.to_numeric(lap.frame["timestamp_s"], errors="coerce")
        if "timestamp_s" in lap.frame.columns
        else pd.Series(dtype=float)
    )
    indicated = lap_origin(flags)
    return {
        "origem": indicated,
        # O indicador sozinho, guardado mesmo quando outra fonte da o rotulo.
        "origem_indicador": indicated,
        "origem_fonte": SOURCE_INDICATOR if indicated != UNKNOWN else None,
        "equipamento": equipment_for(lap.session_id),
        "ia_fracao": ai_share(flags),
        "ia_amostras_com_campo": int(sum(1 for f in flags if f is not None and f == f)),
        "pasta": folder,
        "inicio_epoch_s": float(stamps.min()) if stamps.notna().any() else float("nan"),
        "fim_epoch_s": float(stamps.max()) if stamps.notna().any() else float("nan"),
        "relogio_verificado": False,
    }


def read_session(
    session: Session,
    geometry: TrackGeometry,
    sectors,
    gates: config.LapQualityGates = config.DEFAULT_GATES,
    lap_hook: Optional[LapHook] = None,
) -> List[Dict[str, Any]]:
    """Le uma sessao: uma linha por volta, ja com a identidade de `classify`.

    E a leitura inteira de uma sessao, a unica que abre a gravacao: limpeza,
    alinhamento, portoes, conferencia do relogio e identidade. As linhas saem
    antes de `mark_duplicates` e `mark_clock`, que cruzam sessoes e trabalham
    sobre a tabela pronta (`assemble_inventory`). O modo completo e o
    incremental do `atualizar_coach` (pedido 25) chamam esta mesma funcao.
    """
    rows: List[Dict[str, Any]] = []
    counters: Dict[tuple, Dict[int, int]] = {}
    folder = recording_folder(session.directory)
    # `min_samples=1`: um trecho de uma amostra so nao vira linha do
    # inventario, mas a amostra dele esta dentro de algum replay e precisa
    # entrar na contagem que associa as duas identidades.
    for lap in iter_laps(session, min_samples=1):
        counters[(lap.lap_id, lap.sequence)] = counter_counts(lap.frame)
        if lap.sample_count < 2:
            continue
        cleaned, cleaning = clean_lap(lap.frame)
        if cleaned.empty or len(cleaned) < 4:
            rows.append(
                {
                    "lap_id": lap.lap_id,
                    "session_id": lap.session_id,
                    "sequence": lap.sequence,
                    "lap_number": lap.lap_number,
                    "driver_id": lap.driver_id,
                    "track": lap.track,
                    "raw_samples": lap.sample_count,
                    "corrupt_lines": lap.corrupt_lines,
                    "valid": False,
                    "reasons": "amostras insuficientes apos limpeza",
                    "cleaned_samples": int(len(cleaned)),
                    "geometry_id": geometry.geometry_id,
                    **_provenance(lap, folder),
                }
            )
            continue
        aligned, alignment = align_lap(cleaned, geometry)
        quality = evaluate_lap(aligned, geometry, alignment, gates)
        row = _record(lap, quality, cleaning, alignment)
        row["geometry_id"] = geometry.geometry_id
        row.update(_provenance(lap, folder))
        if quality.valid:
            # O relogio so e conferido onde a volta inteira esta na grade.
            grid = resample_lap(aligned, geometry)
            check = clock_check(grid, geometry, sectors)
            row.update(clock_summary(check))
            if lap_hook is not None:
                lap_hook(lap, aligned, grid, check, row)
        rows.append(row)
    identities = classify(session.session_id, counters)
    for row in rows:
        identity = identities.get(row["lap_id"])
        if identity is not None:
            row.update({k: v for k, v in identity.to_dict().items() if k != "lap_id"})
    return rows


def assemble_inventory(rows: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    """A tabela a partir das linhas de todas as sessoes, com as etapas que cruzam sessoes.

    A ordenacao por duas colunas e estavel: linhas empatadas ficam na ordem
    em que chegaram, que e a ordem das sessoes e das voltas.
    """
    frame = pd.DataFrame(list(rows))
    if not frame.empty:
        frame = frame.sort_values(["session_id", "sequence"]).reset_index(drop=True)
        frame = mark_clock(mark_duplicates(frame))
    return frame


def scan_sessions(
    sessions: Optional[Sequence[Session]] = None,
    track: Optional[TrackGeometry] = None,
    gates: config.LapQualityGates = config.DEFAULT_GATES,
    progress: Optional[Callable[[str], None]] = None,
    lap_hook: Optional[LapHook] = None,
) -> pd.DataFrame:
    """Percorre as sessoes e devolve uma linha por volta."""
    geometry = track or load_geometry()
    available = list(sessions) if sessions is not None else list_sessions()
    sectors = build_microsectors(geometry)

    rows: List[Dict[str, Any]] = []
    for position, session in enumerate(available, start=1):
        session_rows = read_session(session, geometry, sectors, gates, lap_hook)
        rows.extend(session_rows)
        if progress:
            progress(f"[{position}/{len(available)}] {session.session_id}: {len(session_rows)} voltas")
    return assemble_inventory(rows)


def summarise(inventory: pd.DataFrame) -> Dict[str, Any]:
    """Resumo legivel do inventario -- a analise exploratoria em numeros.

    O `duration_s` do inventario vai do primeiro ao ultimo ponto gravado da
    volta e nao e o tempo de volta: fica de 13 a 43 ms curto, sem os trechos
    ate a linha. Ate o pedido 20 o resumo o publicava com o nome `lap_time_s`,
    e dali ele foi parar como tempo de volta em documentos (pedido 19). O tempo
    de volta oficial e o `lap_time_s` do store v2.
    """
    if inventory.empty:
        return {"laps": 0}

    valid = inventory[inventory["valid"]]
    summary: Dict[str, Any] = {
        "laps_total": int(len(inventory)),
        "laps_valid": int(len(valid)),
        "sessions_total": int(inventory["session_id"].nunique()),
        "sessions_with_valid_laps": int(valid["session_id"].nunique()) if len(valid) else 0,
        "drivers": sorted(inventory["driver_id"].dropna().unique().tolist()),
    }

    rejected = inventory[~inventory["valid"]]
    causes: Dict[str, int] = {}
    for text in rejected["reasons"].fillna(""):
        for reason in (part.strip() for part in str(text).split(";") if part.strip()):
            # Agrupa pelo motivo, sem os numeros que variam de volta para volta.
            key = reason.split("(")[0].strip()
            causes[key] = causes.get(key, 0) + 1
    summary["rejection_causes"] = dict(sorted(causes.items(), key=lambda kv: -kv[1]))

    # ADR 0014: quem pilotou, de onde veio, relogio e duplicatas.
    for column, label in (("origem", "laps_by_origin"), ("pasta", "laps_by_folder")):
        if column in inventory.columns:
            summary[label] = inventory[column].fillna("?").value_counts().to_dict()
    if "duplicada_de" in inventory.columns:
        summary["laps_duplicated"] = int(inventory["duplicada_de"].notna().sum())
    if "relogio_suspeito" in inventory.columns:
        summary["valid_laps_clock_suspect"] = int(valid["relogio_suspeito"].fillna(False).astype(bool).sum())
        summary["clock_limit_s"] = float(inventory["relogio_limite_s"].iloc[0])

    if len(valid):
        for column, label in (
            ("duration_s", "duration_s"),
            ("sample_hz", "sample_hz"),
            ("speed_mean_kmh", "speed_mean_kmh"),
            ("coverage", "coverage"),
        ):
            if column not in valid.columns:
                continue
            values = valid[column].dropna().to_numpy(dtype=float)
            if values.size == 0:
                continue
            summary[label] = {
                "min": float(values.min()),
                "p10": float(np.percentile(values, 10)),
                "median": float(np.median(values)),
                "p90": float(np.percentile(values, 90)),
                "max": float(values.max()),
            }
        shortest = valid.loc[valid["duration_s"].idxmin()]
        summary["shortest_duration_lap"] = {
            "lap_id": str(shortest["lap_id"]),
            "duration_s": float(shortest["duration_s"]),
            "sample_hz": float(shortest["sample_hz"]),
        }
        summary["valid_laps_per_session"] = (
            valid.groupby("session_id").size().sort_values(ascending=False).to_dict()
        )
    return summary


def inventory_path(root: Optional[Path] = None) -> Path:
    return (Path(root) if root else config.artifacts_root()) / INVENTORY_FILENAME


def save_inventory(inventory: pd.DataFrame, root: Optional[Path] = None) -> Path:
    path = inventory_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_parquet(path, index=False)
    summary_path = path.parent / INVENTORY_SUMMARY
    summary_path.write_text(
        json.dumps(summarise(inventory), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return path


def load_inventory(root: Optional[Path] = None) -> pd.DataFrame:
    path = inventory_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"inventario nao encontrado em {path}. Rode `python -m ml.scripts.build_inventory`."
        )
    return pd.read_parquet(path)
