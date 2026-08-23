"""Leitura das sessoes gravadas em `data/recordings/`.

Cada sessao e um diretorio com `player.jsonl` (uma amostra por linha),
opcionalmente `metadata.json` e `session-index.json`. Os arquivos vao a 950 MB,
entao tudo aqui e streaming: nenhuma funcao carrega uma sessao inteira na
memoria, so uma volta de cada vez.

Onde a volta comeca
-------------------
Nao no contador de voltas. O Assetto Corsa incrementa o contador alguns quadros
*depois* de o cronometro da volta zerar, e o repositorio de sessoes do projeto
resolve isso jogando esses quadros fora
(`core.recording.session_repository.is_assetto_lap_counter_lag_frame`). Jogar
fora custa os primeiros metros de cada volta -- justamente a saida da ultima
curva, que e o que decide o tempo da reta principal.

Aqui a volta e cortada pelo **cronometro**: uma queda de mais de 10 s no
`lap_time` e uma linha de chegada cruzada, com ou sem o contador ter acompanhado.
Os quadros atrasados vao para a volta nova, que e onde eles aconteceram.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

import pandas as pd

from .. import config
from .samples import flatten, number

PLAYER_STREAM = "player.jsonl"
SESSION_INDEX = "session-index.json"
SESSION_METADATA = "metadata.json"

# Queda no cronometro que conta como linha de chegada cruzada.
LAP_RESET_DROP_S = 10.0


@dataclass(frozen=True)
class Session:
    """Uma sessao gravada em disco."""

    session_id: str
    directory: Path
    track: Optional[str] = None

    @property
    def player_stream(self) -> Path:
        return self.directory / PLAYER_STREAM

    @property
    def index_path(self) -> Path:
        return self.directory / SESSION_INDEX

    def metadata(self) -> Dict[str, Any]:
        path = self.directory / SESSION_METADATA
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}


@dataclass
class RawLap:
    """Uma volta como foi gravada, ainda sem limpeza nem reamostragem."""

    session_id: str
    lap_number: int
    track: Optional[str]
    frame: pd.DataFrame
    # Ordem da volta dentro do arquivo. E ela, e nao `lap_number`, que
    # identifica a volta: o contador do jogo trava durante a parada de box, e a
    # sessao `2026-08-16_03-30-14` tem quatro trechos distintos gravados como
    # volta 6 -- tres deles o carro parado no box. Chaveado pelo contador, o
    # store guardava os quatro sob o mesmo nome e uma parada de box entrava no
    # dataset como se fosse uma volta valida.
    sequence: int = 0
    driver_id: str = "player_1"
    # Quantas linhas do arquivo nao puderam ser lidas dentro desta volta.
    corrupt_lines: int = 0

    @property
    def lap_id(self) -> str:
        return f"{self.session_id}#{self.sequence:04d}"

    @property
    def sample_count(self) -> int:
        return int(len(self.frame))

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de console
        return f"<RawLap {self.lap_id} n={self.sample_count}>"


def list_sessions(
    root: Optional[Path] = None, track_prefixes: Sequence[str] = config.INTERLAGOS_TRACK_PREFIXES
) -> List[Session]:
    """Sessoes gravadas disponiveis, filtradas por pista.

    O filtro e pelo nome da pista dentro dos dados, e nao pelo nome do
    diretorio: ha sessoes cujo diretorio traz o sufixo de um experimento de
    geometria (`..._InterlagosPitAccessAsphaltMergeFix`) e que continuam sendo
    Interlagos.
    """
    base = Path(root) if root else config.recordings_root()
    if not base.exists():
        raise FileNotFoundError(f"diretorio de gravacoes nao encontrado: {base}")

    sessions: List[Session] = []
    for directory in sorted(base.iterdir()):
        stream = directory / PLAYER_STREAM
        if not directory.is_dir() or not stream.exists() or stream.stat().st_size == 0:
            continue
        track = _session_track(directory, stream)
        if track_prefixes and not any(str(track or "").startswith(p) for p in track_prefixes):
            continue
        sessions.append(Session(session_id=directory.name, directory=directory, track=track))
    return sessions


def _session_track(directory: Path, stream: Path) -> Optional[str]:
    index_path = directory / SESSION_INDEX
    if index_path.exists():
        try:
            track = json.loads(index_path.read_text(encoding="utf-8")).get("track")
            if track:
                return str(track)
        except (json.JSONDecodeError, OSError):
            pass
    try:
        with stream.open("r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline()
        envelope = json.loads(first)
        track = envelope.get("track") or (envelope.get("sample") or {}).get("track")
        return str(track) if track else None
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def _is_new_lap(row: Dict[str, Any], previous: Dict[str, Any]) -> bool:
    """A amostra abre uma volta nova?"""
    lap_now, lap_before = row.get("lap_number"), previous.get("lap_number")
    time_now, time_before = row.get("lap_time_s"), previous.get("lap_time_s")

    if time_now is not None and time_before is not None:
        if time_before - time_now > LAP_RESET_DROP_S:
            return True
        # O cronometro ja zerou e segue crescendo; o contador so agora alcancou.
        # Isso nao e volta nova, e a mesma volta que ja tinha comecado.
        if lap_now != lap_before and time_now > time_before:
            return False
    return lap_now != lap_before


def iter_laps(
    session: Session, min_samples: int = 2
) -> Iterator[RawLap]:
    """Percorre `player.jsonl` uma vez e entrega volta a volta."""
    rows: List[Dict[str, Any]] = []
    corrupt = 0
    lap_number: Optional[int] = None
    sequence = 0
    previous: Dict[str, Any] = {}

    def build(number_value: Optional[int], collected: List[Dict[str, Any]], bad: int, order: int):
        if number_value is None or len(collected) < min_samples:
            return None
        return RawLap(
            session_id=session.session_id,
            lap_number=int(number_value),
            track=session.track,
            frame=pd.DataFrame(collected),
            sequence=order,
            corrupt_lines=bad,
        )

    with session.player_stream.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                envelope = json.loads(line)
            except json.JSONDecodeError:
                corrupt += 1
                continue
            row = flatten(envelope)
            if row.get("lap_number") is None:
                corrupt += 1
                continue

            if previous and _is_new_lap(row, previous):
                lap = build(lap_number, rows, corrupt, sequence)
                if lap is not None:
                    yield lap
                # A ordem avanca a cada corte, tenha a volta sido entregue ou
                # nao: um trecho curto demais para virar volta ainda ocupa um
                # lugar na sessao, e reusar o numero embaralharia a identidade.
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


def lap_offsets(session: Session) -> Dict[int, Dict[str, Any]]:
    """Offsets de byte por volta, quando a sessao tem indice.

    O gravador ja escreve onde cada volta comeca e termina no arquivo. Onde esse
    indice existe da para ler uma volta sem varrer os 950 MB; onde nao existe,
    so resta `iter_laps`.
    """
    if not session.index_path.exists():
        return {}
    try:
        index = json.loads(session.index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    laps = index.get("laps")
    if not isinstance(laps, dict):
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    for key, value in laps.items():
        if not isinstance(value, dict):
            continue
        start, end = value.get("start_offset"), value.get("end_offset")
        if start is None or end is None or end <= start:
            continue
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def read_lap(session: Session, sequence: int) -> RawLap:
    """Le a volta de ordem `sequence` dentro da sessao.

    Varre o arquivo, porque so a varredura conhece a ordem. Para acesso rapido
    por numero de volta do jogo existe `read_lap_by_number`, com a ressalva que
    o numero nao e unico.
    """
    for lap in iter_laps(session):
        if lap.sequence == int(sequence):
            return lap
    raise KeyError(f"volta de ordem {sequence} nao encontrada em {session.session_id}")


def read_lap_by_number(session: Session, lap_number: int) -> RawLap:
    """Le uma volta pelo numero do jogo, usando os offsets do gravador.

    Rapido -- nao varre o arquivo -- mas o numero do jogo se repete dentro da
    sessao quando o contador trava no box, e neste caso volta o trecho que o
    gravador indexou, que pode nao ser o que se queria. Para identidade
    confiavel use `read_lap`.
    """
    offsets = lap_offsets(session).get(int(lap_number))
    if offsets is None:
        for lap in iter_laps(session):
            if lap.lap_number == int(lap_number):
                return lap
        raise KeyError(f"volta {lap_number} nao encontrada em {session.session_id}")

    with session.player_stream.open("rb") as handle:
        handle.seek(int(offsets["start_offset"]))
        block = handle.read(int(offsets["end_offset"]) - int(offsets["start_offset"]))

    rows: List[Dict[str, Any]] = []
    corrupt = 0
    for line in block.decode("utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            corrupt += 1
            continue
        row = flatten(envelope)
        if number(row.get("lap_number")) is None:
            corrupt += 1
            continue
        rows.append(row)

    if not rows:
        raise KeyError(f"volta {lap_number} vazia em {session.session_id}")
    return RawLap(
        session_id=session.session_id,
        lap_number=int(lap_number),
        track=session.track,
        frame=pd.DataFrame(rows),
        corrupt_lines=corrupt,
    )
