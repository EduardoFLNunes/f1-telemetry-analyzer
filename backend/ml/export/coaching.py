"""O tracado otimizado, traduzido para o que o coach ao vivo sabe ler.

O subsistema de ML pensa em **metros**: a grade e uniforme em `s`, os
microsetores tem comprimento fixo, e tudo que ele produz esta indexado por
distancia percorrida. O coach pensa em **progresso**: recebe `p` de 0 a 1 do
runtime e corta a volta em sessenta fatias iguais nesse eixo.

Os dois eixos nao sao a mesma coisa, e a diferenca nao e desprezivel. Ha duas
reguas no caminho, e as duas ja enganaram este modulo:

* **o `p` do runtime e distancia, nao indice.** `ProjectionEngine.project_car`
  devolve `p = distanceAlongTrack / total`, com `distanceAlongTrack` medido no
  campo `distance` dos vertices do cache e `total` incluindo o segmento que
  fecha o laco. O vetor `p` gravado no cache e outra coisa -- indice do vertice
  sobre o total -- e diverge do `p` do runtime em ate 0,0058, 25 m de pista.
* **os metros do runtime nao sao os metros do ML.** O runtime mede a poligonal
  crua do cache; `load_geometry` conserta degraus, aplica um passa baixo de 60
  m e reparametriza por comprimento de arco. Os dois `s` coincidem na linha e
  se afastam em ate ~30 m no meio da volta.

Um microsetor do coach tem 72 m. Somados, os dois erros punham o alvo de uma
fatia a ate dois tercos de microsetor do asfalto a que ele pertence. A conversao
entao passa pelo mundo: `p` -> distancia na poligonal do runtime -> ponto
world X/Z -> projecao na grade do ML. E o unico caminho em que os dois lados
falam do mesmo pedaco de pista.

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


def _runtime_polygon(raw: Dict[str, Any]) -> Any:
    """Vertices da centerline e o `p` que o runtime da a cada um.

    Reproduz `ProjectionEngine`: a distancia vem do campo `distance` do vertice
    e o total, num laco fechado, soma o segmento do ultimo vertice de volta ao
    primeiro. O vertice 0 e repetido no fim com `p = 1`, porque o runtime
    tambem percorre esse segmento e um `p` de 0,9997 tem de cair nele.
    """
    centre = np.array([[p["x"], p["z"]] for p in raw["centerline"]], dtype=float)
    steps = np.linalg.norm(np.diff(centre, axis=0), axis=1)
    cumulative = np.concatenate([[0.0], np.cumsum(steps)])
    stored = [p.get("distance") for p in raw["centerline"]]
    if all(value is not None for value in stored):
        distance = np.asarray(stored, dtype=float)
    else:
        # Cache sem `distance`: o runtime le 0 e quebra; o melhor que da para
        # fazer aqui e a propria poligonal.
        distance = cumulative

    if bool(raw.get("closedLoop", True)):
        total = float(distance[-1] + np.linalg.norm(centre[-1] - centre[0]))
        centre = np.vstack([centre, centre[:1]])
        distance = np.append(distance, total)
    else:
        total = float(distance[-1])
    if total <= 0.0:
        raise ValueError("centerline degenerada")
    return centre, distance / total


def _projected_distance(track: TrackGeometry, points: np.ndarray) -> np.ndarray:
    """`s` do ML de cada vertice cru, desenrolado numa volta so e monotono.

    A projecao devolve `s` em [0, length): o vertice 0 pode cair alguns
    centimetros antes da linha (s ~ length) e o vertice de fecho logo depois
    dela (s ~ 0). Desenrolar pelos passos entre vertices consecutivos poe a
    volta inteira numa regua continua ancorada no vertice 0.

    O maximo acumulado e para os trechos que `load_geometry` conserta: ali o
    vertice cru salta metros de lado e a projecao pode recuar alguns
    centimetros. Um `s(p)` que anda para tras daria fatia de tempo negativo.
    """
    projected, _ = track.project_sequence(points)
    length = float(track.length)
    steps = np.mod(np.diff(projected) + length / 2.0, length) - length / 2.0
    first = projected[0] if projected[0] < length / 2.0 else projected[0] - length
    distance = first + np.concatenate([[0.0], np.cumsum(steps)])
    return np.maximum.accumulate(distance)


def progress_to_distance(
    geometry_path: Optional[Path] = None,
    track_length: Optional[float] = None,
    track: Optional[TrackGeometry] = None,
) -> Any:
    """Devolve `s(p)`: dado o progresso do runtime, quantos metros de pista.

    Com `track`, os metros sao o `s` da grade do ML: cada vertice da poligonal
    do runtime e projetado na centerline de `track`, e `s(p)` interpola entre
    eles. E o modo que `build_targets` usa, e o unico que serve para cortar
    algo indexado pela grade de `load_geometry`.

    Sem `track`, os metros sao os do proprio runtime -- `p` vezes o comprimento
    da poligonal fechada -- reescalados para `track_length` (ou o `trackLength`
    declarado) para as pontas fecharem.
    """
    path = (
        Path(geometry_path)
        if geometry_path
        else config.track_cache_root() / config.INTERLAGOS_GEOMETRY_FILE
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    points, progress = _runtime_polygon(raw)

    if track is not None:
        distance = _projected_distance(track, points)
    else:
        length = float(track_length if track_length else raw["trackLength"])
        distance = progress * length

    # `np.interp` exige o eixo de entrada crescente. A distancia do cache ja e,
    # mas um cache remendado poderia nao ser, e um mapeamento fora de ordem erra
    # em silencio.
    order = np.argsort(progress, kind="stable")
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

    s_of_p = progress_to_distance(geometry_path, track_length=track.length, track=track)
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
