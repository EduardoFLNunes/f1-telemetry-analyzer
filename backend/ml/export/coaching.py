"""O tracado otimizado, traduzido para o que o coach ao vivo sabe ler.

O subsistema de ML pensa em **metros**: a grade e uniforme em `s`, os
microsetores tem comprimento fixo, e tudo que ele produz esta indexado por
distancia percorrida. O coach pensa em **progresso**: recebe `p` de 0 a 1 do
runtime e corta a volta em sessenta fatias iguais nesse eixo.

Os dois eixos nao sao a mesma coisa, e a diferenca nao e desprezivel. O `p` do
runtime e o indice da amostra da centerline sobre o total de amostras -- e a
centerline nao e equidistante: os passos vao de 1,4 a 5,0 m. Medido no cache de
Interlagos, `p` por indice e `p` por distancia divergem em ate 0,0059, que sao
25 m de pista. Um microsetor tem 72 m. Converter por regra de tres colocaria o
alvo de cada fatia a um terco de microsetor do asfalto a que ele pertence.

Entao a conversao usa o proprio vetor `p` gravado no cache de geometria, que e
exatamente o que o runtime projeta. E o unico jeito de os dois lados falarem do
mesmo pedaco de pista.

O que sai daqui e JSON puro, de proposito: o backend empacotado le estes numeros
sem importar `ml`, sem PyTorch e sem SciPy. A rede e a busca ja rodaram, offline;
o que embarca e o resultado.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .. import config
from ..comparison.reference_frame import reference_lap_frame
from ..track.geometry import TrackGeometry

# O coach corta a volta em sessenta fatias. Nao e coincidencia com os
# microsetores do ML -- e o mesmo numero por acaso, em eixos diferentes -- entao
# o valor vem daqui e nao de `ml.config`.
COACH_MICROSECTORS = 60

FORMAT_VERSION = "optimal-line-1"


@dataclass
class OptimalLineTargets:
    """Tempo alvo por fatia de progresso, mais o que o coach usa para falar."""

    version: str
    track: str
    microsectors: int
    lap_seconds: float
    seconds: List[float] = field(default_factory=list)
    min_speed_kmh: List[Optional[float]] = field(default_factory=list)
    entry_speed_kmh: List[Optional[float]] = field(default_factory=list)
    exit_speed_kmh: List[Optional[float]] = field(default_factory=list)
    source: str = ""
    built_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8"
        )
        return path


def progress_to_distance(
    geometry_path: Optional[Path] = None, track_length: Optional[float] = None
) -> Any:
    """Devolve `s(p)`: dado o progresso do runtime, quantos metros de pista.

    Le o vetor `p` do cache -- o mesmo que o runtime projeta -- e a distancia
    acumulada ao longo da centerline. A distancia e reescalada para o
    `trackLength` declarado, porque a poligonal soma 4332,3 m contra 4334,1 m
    declarados: sem isso as duas pontas do mapeamento nao fechariam.
    """
    path = (
        Path(geometry_path)
        if geometry_path
        else config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    centre = np.array([[p["x"], p["z"]] for p in raw["centerline"]], dtype=float)
    stored = raw.get("p")

    steps = np.linalg.norm(np.diff(centre, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(steps)])
    total = float(cumulative[-1])
    if total <= 0.0:
        raise ValueError(f"centerline degenerada em {path}")

    length = float(track_length if track_length else raw["trackLength"])
    distance = cumulative / total * length

    if stored is not None and len(stored) == len(centre):
        progress = np.asarray(stored, dtype=float)
    else:
        # O cache antigo pode nao trazer `p`; o runtime o calcula assim.
        progress = np.arange(len(centre), dtype=float) / max(len(centre) - 1, 1)

    # `np.interp` exige o eixo de entrada crescente. `p` por indice ja e, mas
    # um cache remendado poderia nao ser, e um mapeamento fora de ordem erra em
    # silencio.
    order = np.argsort(progress)
    progress, distance = progress[order], distance[order]

    def s_of_p(values):
        return np.interp(np.asarray(values, dtype=float), progress, distance)

    return s_of_p


def beats_recorded_laps(
    track: TrackGeometry, lateral: np.ndarray, envelope: Any, store: Any
) -> Dict[str, Any]:
    """O tracado e mesmo mais rapido que as voltas do piloto?

    A pergunta parece obvia e nao e. O tempo do tracado sai do simulador
    quase-estatico; o tempo de uma volta gravada sai do cronometro do jogo. Os
    dois nao sao o mesmo relogio -- medido neste dataset, a razao entre eles
    varia de 0,981 a 1,009 conforme a volta. Comparar um com o outro diretamente
    responde qualquer coisa que se queira ouvir.

    A comparacao honesta passa as voltas reais pelo **mesmo** simulador e compara
    simulado contra simulado. E ai a resposta muda: 40 das 113 voltas gravadas
    simulam mais rapido que o tracado que a busca encontrou.

    Exportar um alvo que o piloto ja bate seria pior do que nao exportar nenhum:
    o coach diria a ele que esta atras de uma linha que ele supera em metade dos
    microsetores.
    """
    from ..optimization.lap_time_model import simulate

    line_seconds = float(simulate(track, np.asarray(lateral, dtype=float), envelope).lap_time_s)
    simulated = []
    for lap_id in store.laps["lap_id"]:
        shape = store.lap(lap_id)["lateral"].to_numpy(dtype=float)
        simulated.append(float(simulate(track, shape, envelope).lap_time_s))

    quickest = min(simulated) if simulated else float("inf")
    beaten_by = [value for value in simulated if value < line_seconds]
    return {
        "line_seconds": line_seconds,
        "quickest_recorded_seconds": quickest,
        "laps_compared": len(simulated),
        "laps_quicker_than_line": len(beaten_by),
        "margin_seconds": quickest - line_seconds,
        "is_an_improvement": bool(simulated) and line_seconds < quickest,
    }


def build_targets(
    track: TrackGeometry,
    lateral: np.ndarray,
    envelope: Any,
    track_name: str,
    microsectors: int = COACH_MICROSECTORS,
    geometry_path: Optional[Path] = None,
    source: str = "",
) -> OptimalLineTargets:
    """Simula o tracado otimizado e reparte o tempo pelas fatias do coach."""
    frame = reference_lap_frame(track, np.asarray(lateral, dtype=float), envelope)
    grid_s = frame["s"].to_numpy(dtype=float)
    elapsed = frame["elapsed_s"].to_numpy(dtype=float)
    speed = frame["speed_kmh"].to_numpy(dtype=float)
    lap_seconds = float(frame["lap_time_s"].iloc[0])

    s_of_p = progress_to_distance(geometry_path, track_length=track.length)
    edges_p = np.arange(microsectors + 1, dtype=float) / microsectors
    edges_s = s_of_p(edges_p)
    # As pontas sao ancoradas: `p=0` e a linha de chegada e `p=1` e a mesma
    # linha depois de uma volta. Deixar a interpolacao decidir isso faria a
    # ultima fatia perder alguns metros.
    edges_s[0], edges_s[-1] = 0.0, float(track.length)

    # A grade acaba um passo antes da linha de chegada -- o ultimo ponto esta em
    # `length - step`. Interpolar em `length` satura no valor dele, e a ultima
    # fatia sai curta pelo tempo desse passo (25 ms medidos em Interlagos). O
    # fecho do circuito precisa ser dito explicitamente.
    closed_s = np.append(grid_s, float(track.length))
    closed_elapsed = np.append(elapsed, lap_seconds)
    elapsed_at = np.interp(edges_s, closed_s, closed_elapsed)
    seconds = np.diff(elapsed_at)

    minima: List[Optional[float]] = []
    entries: List[Optional[float]] = []
    exits: List[Optional[float]] = []
    for index in range(microsectors):
        start, end = edges_s[index], edges_s[index + 1]
        inside = speed[(grid_s >= start) & (grid_s < end)]
        if inside.size:
            minima.append(round(float(inside.min()), 1))
            entries.append(round(float(inside[0]), 1))
            exits.append(round(float(inside[-1]), 1))
        else:
            minima.append(None)
            entries.append(None)
            exits.append(None)

    return OptimalLineTargets(
        version=FORMAT_VERSION,
        track=track_name,
        microsectors=microsectors,
        lap_seconds=round(lap_seconds, 3),
        seconds=[round(float(value), 4) for value in seconds],
        min_speed_kmh=minima,
        entry_speed_kmh=entries,
        exit_speed_kmh=exits,
        source=source,
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
