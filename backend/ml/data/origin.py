"""Quem pilotou cada volta, e se o relogio dela e plausivel (ADR 0014).

Muitas sessoes foram gravadas com a IA do Assetto Corsa no volante, as vezes
alternando com o piloto dentro da mesma sessao. Uma volta da IA lida como volta
do piloto contamina tudo o que fala dele: a variacao entre voltas, o melhor
trecho, a referencia do coach. Por isso cada volta carrega:

* `origem`: `humano` ou `ia` quando o gravador registrou quem pilotava e o
  valor nao mudou na volta; `misturada` quando mudou; `desconhecida` quando o
  campo nao existe -- todas as gravacoes anteriores a 2026-10-03;
* `pasta`: de que pasta de gravacoes a volta veio (`repositorio` ou
  `app_instalado`);
* `relogio_suspeito`: algum microsetor em que o tempo do relogio gravado e o
  tempo que a velocidade explica discordam alem do limite;
* `duplicada_de`: a mesma volta gravada duas vezes, por dois backends abertos
  ao mesmo tempo.

Para tudo o que fala do piloto, o padrao e `humano`, com relogio conferido e
sem relogio suspeito (`select_laps`). Na duvida, a volta fica de fora.

Desde o ADR 0015 cada volta diz tambem com que `equipamento` foi feita: o
volante RS50 com pedais de celula de carga a partir de 2026-10-01 (`atual`),
o controle de antes (`anterior`). Uma volta `humano` so fala do piloto de hoje
com o equipamento `atual`. E `origem_fonte` diz de onde veio o rotulo: o
indicador do jogo, as anotacoes do piloto numa sessao rotulada ou o detector.

Desde o pedido 15, as sessoes novas sem anotacao seguem `unannotated_origin`:
o indicador ate a IA ligar pela primeira vez, a volta em que ela liga como
`misturada`, e o detector depois disso.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

import numpy as np
import pandas as pd

from .. import config
from ..track.geometry import TrackGeometry
from ..track.microsectors import Microsectors, split_times
from ..track.trajectory import step_lengths

HUMAN = "humano"
AI = "ia"
MIXED = "misturada"
UNKNOWN = "desconhecida"
ORIGINS = (HUMAN, AI, MIXED, UNKNOWN)

# O que conta como volta do piloto, para tudo o que fala dele.
DRIVER_ORIGINS = (HUMAN,)

# Equipamento (ADR 0015).
CURRENT_EQUIPMENT = "atual"
PREVIOUS_EQUIPMENT = "anterior"
EQUIPMENT_SINCE = "2026-10-01"
DRIVER_EQUIPMENT = (CURRENT_EQUIPMENT,)

# De onde veio o rotulo de origem.
SOURCE_INDICATOR = "indicador"
SOURCE_ANNOTATION = "anotacao"
SOURCE_DETECTOR = "detector"
# 05/10: uma gravacao inteira anotada pelo piloto (anotacoes_de_sessao.csv).
SOURCE_SESSION_ANNOTATION = "anotacao_sessao"

# Diferenca maxima, em segundos, entre o tempo do relogio e o tempo explicado
# pela velocidade, em qualquer microsetor. Proposta a partir da distribuicao
# medida nas duas pastas (688 voltas validas e unicas) e registrada em
# docs/origem_das_voltas.md antes de ser aplicada: fora dos microsetores do box
# o p99,9 da diferenca e 0,068 s, o microsetor 0 tem vies fixo de -0,034 s, e
# de 0,10 a 0,20 s o numero de voltas marcadas quase nao muda (144 -> 141).
CLOCK_LIMIT_S: Optional[float] = 0.10

# Abaixo disto a velocidade nao explica tempo nenhum (carro quase parado).
MIN_SPEED_MS = 1.0


# ------------------------------------------------------------- origem ---

def _known(value) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number != 0.0


def lap_origin(flags: Iterable) -> str:
    """Origem de uma volta a partir do indicador de IA de cada amostra.

    Constante em todas as amostras -> `humano` ou `ia`. Muda dentro da volta ->
    `misturada`. Nenhuma amostra com o campo -> `desconhecida`. Campo ausente
    em parte da volta e o resto constante -> `desconhecida`: nao da para dizer
    quem pilotou o trecho sem registro.
    """
    values = [_known(v) for v in flags]
    known = [v for v in values if v is not None]
    if not known:
        return UNKNOWN
    if any(known) and not all(known):
        return MIXED
    if len(known) < len(values):
        return UNKNOWN
    return AI if known[0] else HUMAN


def unannotated_origin(indicator: str, detector: Optional[str]) -> tuple:
    """Origem de uma volta de sessao nova sem anotacao, e de onde veio (pedido 15).

    O indicador do jogo liga com o Ctrl+C e fica travado ate a sessao do jogo
    reiniciar. Antes de ligar, a volta e `humano` pelo indicador; a volta em que
    liga e `misturada`; depois, o indicador diz `ia` mesmo com o piloto de volta
    ao volante, e quem decide e o detector pela linha da IA. O que o detector
    nao resolve, ou uma volta sem o campo, fica `desconhecida`.
    """
    if indicator in (HUMAN, MIXED):
        return indicator, SOURCE_INDICATOR
    if indicator == AI and detector in (HUMAN, AI, MIXED):
        return detector, SOURCE_DETECTOR
    return UNKNOWN, None


def label_unannotated(inventory: pd.DataFrame, annotated: Set[str], classify) -> pd.DataFrame:
    """Aplica `unannotated_origin` as voltas do equipamento `atual` fora de `annotated`.

    `classify(lap_id, row)` devolve o veredito do detector (`classify_lap`) ou
    `None` sem a grade; so e chamado nas voltas que o indicador da como `ia`.
    As voltas do equipamento `anterior` e as anotadas nao mudam.
    """
    out = inventory.copy()
    for column in ("origem_detector", "motivo_detector", "linha_detector"):
        if column not in out.columns:
            out[column] = None
    target = (out["equipamento"] == CURRENT_EQUIPMENT) & ~out["lap_id"].isin(annotated)
    for index in out.index[target]:
        row = out.loc[index]
        verdict = classify(row["lap_id"], row) if row["origem_indicador"] == AI else None
        if verdict is not None:
            out.at[index, "origem_detector"] = verdict["origem_detector"]
            out.at[index, "motivo_detector"] = verdict["motivo"]
            out.at[index, "linha_detector"] = verdict["linha"]
        label, source = unannotated_origin(row["origem_indicador"], verdict["origem_detector"] if verdict else None)
        out.at[index, "origem"] = label
        out.at[index, "origem_fonte"] = source
    return out


def ai_share(flags: Iterable) -> float:
    """Fracao das amostras com o campo que indicam IA. NaN sem o campo."""
    known = [v for v in (_known(f) for f in flags) if v is not None]
    return float(sum(known)) / len(known) if known else float("nan")


def equipment_for(session_id: str) -> str:
    """`atual` para sessoes de 2026-10-01 em diante, `anterior` antes (ADR 0015).

    A data e a do nome da sessao, que o gravador escreve com a hora local do
    inicio da gravacao. Sem data no nome, `anterior`: na duvida, a volta nao
    fala do piloto de hoje.
    """
    prefix = str(session_id or "")[:10]
    if len(prefix) == 10 and prefix[4] == "-" and prefix[7] == "-" and prefix.replace("-", "").isdigit():
        return CURRENT_EQUIPMENT if prefix >= EQUIPMENT_SINCE else PREVIOUS_EQUIPMENT
    return PREVIOUS_EQUIPMENT


# ------------------------------------------------------------- pastas ---

def recording_folder(directory: Path) -> str:
    """Rotulo da pasta de gravacoes de uma sessao (`repositorio`, `app_instalado`)."""
    parent = Path(directory).resolve().parent
    for label, root in config.recordings_roots().items():
        try:
            if parent == Path(root).resolve():
                return label
        except OSError:
            continue
    return str(parent)


# ------------------------------------------------------------- relogio ---

def speed_time_on_grid(grid: pd.DataFrame, track: TrackGeometry) -> tuple:
    """Tempo acumulado que a velocidade explica, ponto a ponto na grade.

    Cada passo da grade custa o comprimento percorrido pela trajetoria do carro
    (`step_lengths`, que segue a linha e nao a centerline) dividido pela
    velocidade media nas duas pontas. Devolve (acumulado na grade, total com o
    passo que fecha a volta), na mesma forma que `elapsed_s` e `lap_time_s`.
    """
    speed = grid["speed_kmh"].to_numpy(dtype=float) / 3.6
    lateral = grid["lateral"].to_numpy(dtype=float) if "lateral" in grid.columns else np.zeros(track.size)
    steps = step_lengths(track, np.nan_to_num(lateral))
    ahead = np.roll(speed, -1)
    mean = np.maximum(0.5 * (speed + ahead), MIN_SPEED_MS)
    dt = steps / mean                    # passo i: do ponto i ao i+1 (o ultimo fecha a volta)
    cumulative = np.concatenate([[0.0], np.cumsum(dt[:-1])])
    return cumulative, float(np.sum(dt))


def clock_check(
    grid: pd.DataFrame, track: TrackGeometry, sectors: Microsectors
) -> pd.DataFrame:
    """Por microsetor: tempo pelo relogio gravado, tempo pela velocidade, diferenca.

    O relogio e o `elapsed_s` da grade (cronometro do jogo). As duas medidas
    usam as mesmas fronteiras (`split_times`). Uma diferenca grande quer dizer
    que o relogio e a distancia percorrida nao contam a mesma historia: relogio
    que pula, posicao que salta, projecao que escorrega.
    """
    from ..preprocessing.resampling import lap_time_from_grid

    clock = split_times(grid["elapsed_s"].to_numpy(dtype=float), sectors, track, total=lap_time_from_grid(grid))
    cumulative, total = speed_time_on_grid(grid, track)
    by_speed = split_times(cumulative, sectors, track, total=total)
    return pd.DataFrame(
        {
            "microsetor": np.arange(sectors.count),
            "t_relogio_s": clock,
            "t_velocidade_s": by_speed,
            "diferenca_s": clock - by_speed,
        }
    )


def clock_summary(check: pd.DataFrame) -> dict:
    """O pior microsetor de uma volta, para o inventario."""
    difference = check["diferenca_s"].to_numpy(dtype=float)
    finite = np.isfinite(difference)
    if not finite.all():
        return {"relogio_verificado": False, "relogio_pior_s": float("nan"), "relogio_pior_microsetor": -1}
    worst = int(np.argmax(np.abs(difference)))
    return {
        "relogio_verificado": True,
        "relogio_pior_s": float(difference[worst]),
        "relogio_pior_microsetor": worst,
    }


def mark_clock(inventory: pd.DataFrame, limit: Optional[float] = None) -> pd.DataFrame:
    """Marca `relogio_suspeito` nas voltas com algum microsetor alem do limite."""
    limit = CLOCK_LIMIT_S if limit is None else limit
    out = inventory.copy()
    if limit is None or "relogio_pior_s" not in out.columns:
        return out
    verified = out.get("relogio_verificado", pd.Series(False, index=out.index)).fillna(False).astype(bool)
    worst = out["relogio_pior_s"].abs()
    out["relogio_suspeito"] = verified & (worst > float(limit))
    out["relogio_limite_s"] = float(limit)
    return out


# ----------------------------------------------------------- duplicatas ---

# Fracao minima de sobreposicao no relogio de parede (da volta mais curta)
# para duas voltas de sessoes diferentes serem a mesma volta gravada duas vezes.
DUPLICATE_OVERLAP = 0.5


def mark_duplicates(inventory: pd.DataFrame) -> pd.DataFrame:
    """Marca `duplicada_de` nas voltas gravadas duas vezes ao mesmo tempo.

    Medido em 2026-10-03: dois backends abertos gravaram os mesmos instantes em
    sessoes de ids diferentes, uma em cada pasta (3 casos) ou na mesma pasta
    (2026-06-01). Mesmo instante, mesmas posicoes: e a mesma volta. Fica a
    copia com mais amostras; empate, a de sessao de nome menor.
    """
    out = inventory.copy()
    out["duplicada_de"] = None
    needed = {"inicio_epoch_s", "fim_epoch_s", "session_id", "raw_samples", "lap_number"}
    if out.empty or not needed.issubset(out.columns):
        return out
    rows = out.dropna(subset=["inicio_epoch_s", "fim_epoch_s"]).sort_values("inicio_epoch_s")
    start = rows["inicio_epoch_s"].to_numpy(dtype=float)
    end = rows["fim_epoch_s"].to_numpy(dtype=float)
    session = rows["session_id"].to_numpy()
    samples = rows["raw_samples"].to_numpy(dtype=float)
    number = rows["lap_number"].to_numpy(dtype=float)
    lap_ids = rows["lap_id"].to_numpy()
    index = rows.index.to_numpy()

    parent = {i: i for i in range(len(rows))}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(rows)):
        j = i + 1
        while j < len(rows) and start[j] < end[i]:
            if session[i] != session[j] and abs(number[i] - number[j]) <= 1:
                overlap = min(end[i], end[j]) - max(start[i], start[j])
                shorter = min(end[i] - start[i], end[j] - start[j])
                if shorter > 0 and overlap / shorter > DUPLICATE_OVERLAP:
                    parent[find(j)] = find(i)
            j += 1

    groups = {}
    for i in range(len(rows)):
        groups.setdefault(find(i), []).append(i)
    for members in groups.values():
        if len(members) < 2:
            continue
        kept = sorted(members, key=lambda k: (-samples[k], str(session[k])))[0]
        for k in members:
            if k != kept:
                out.at[index[k], "duplicada_de"] = lap_ids[kept]
    return out


# ------------------------------------------------------------- selecao ---

def driver_mask(
    laps: pd.DataFrame,
    origins: Optional[Sequence[str]] = DRIVER_ORIGINS,
    include_clock_suspect: bool = False,
    equipment: Optional[Sequence[str]] = DRIVER_EQUIPMENT,
) -> pd.Series:
    """Quais linhas passam no filtro de origem, equipamento, relogio e duplicata.

    `origins=None` aceita qualquer origem. Sem as colunas do ADR 0014 (um
    inventario antigo), a origem e `desconhecida` e o relogio nao foi
    conferido: com o filtro padrao, nada passa. O equipamento so filtra voltas
    `humano` (ADR 0015): a volta da IA e a mesma com qualquer controle na mao
    do piloto. `equipment=None` aceita qualquer um.
    """
    mask = pd.Series(True, index=laps.index)
    origin = laps["origem"] if "origem" in laps.columns else pd.Series(UNKNOWN, index=laps.index)
    origin = origin.fillna(UNKNOWN)
    if origins is not None:
        mask &= origin.isin(list(origins))
    if equipment is not None:
        kit = laps["equipamento"] if "equipamento" in laps.columns else pd.Series(PREVIOUS_EQUIPMENT, index=laps.index)
        mask &= ~((origin == HUMAN) & ~kit.fillna(PREVIOUS_EQUIPMENT).isin(list(equipment)))
    if not include_clock_suspect:
        verified = laps["relogio_verificado"] if "relogio_verificado" in laps.columns else pd.Series(False, index=laps.index)
        suspect = laps["relogio_suspeito"] if "relogio_suspeito" in laps.columns else pd.Series(True, index=laps.index)
        mask &= verified.fillna(False).astype(bool) & ~suspect.fillna(True).astype(bool)
    if "duplicada_de" in laps.columns:
        mask &= laps["duplicada_de"].isna()
    return mask


def select_laps(
    laps: pd.DataFrame,
    origins: Optional[Sequence[str]] = DRIVER_ORIGINS,
    include_clock_suspect: bool = False,
    equipment: Optional[Sequence[str]] = DRIVER_EQUIPMENT,
) -> pd.DataFrame:
    return laps[driver_mask(laps, origins, include_clock_suspect, equipment)]


def replay_selection(
    inventory: pd.DataFrame,
    origins: Optional[Sequence[str]] = DRIVER_ORIGINS,
    include_clock_suspect: bool = False,
    equipment: Optional[Sequence[str]] = DRIVER_EQUIPMENT,
) -> Set[str]:
    """Voltas do replay (`rec__<sessao>__<n>`, a identidade do coach) que passam.

    Uma volta do replay pode conter mais de uma volta do `ml` (o contador do
    jogo trava no box). Ela so passa se todas as voltas do `ml` dentro dela
    passarem: um trecho sem conferencia contamina a volta inteira.
    """
    if "replay_lap_id" not in inventory.columns:
        return set()
    mask = driver_mask(inventory, origins, include_clock_suspect, equipment)
    ok: dict = {}
    for replay, passed in zip(inventory["replay_lap_id"], mask):
        if not isinstance(replay, str) or not replay:
            continue
        ok[replay] = ok.get(replay, True) and bool(passed)
    return {replay for replay, passed in ok.items() if passed}


def parse_equipment(values: Optional[List[str]]) -> Optional[List[str]]:
    """Argumento de linha de comando -> equipamentos (`todos` = sem filtro)."""
    if not values:
        return list(DRIVER_EQUIPMENT)
    if any(v == "todos" for v in values):
        return None
    unknown = [v for v in values if v not in (CURRENT_EQUIPMENT, PREVIOUS_EQUIPMENT)]
    if unknown:
        raise ValueError(f"equipamento desconhecido: {unknown}; use atual, anterior ou 'todos'")
    return list(values)


def parse_origins(values: Optional[List[str]]) -> Optional[List[str]]:
    """Argumento de linha de comando -> lista de origens (`todas` = sem filtro)."""
    if not values:
        return list(DRIVER_ORIGINS)
    if any(v == "todas" for v in values):
        return None
    unknown = [v for v in values if v not in ORIGINS]
    if unknown:
        raise ValueError(f"origem desconhecida: {unknown}; use {ORIGINS} ou 'todas'")
    return list(values)
