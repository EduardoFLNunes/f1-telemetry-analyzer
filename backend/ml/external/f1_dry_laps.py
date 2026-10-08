"""Voltas secas de classificacao da F1 em Interlagos (pedido 23; ADR 0018).

Coleta pelo FastF1 (3.4.0, fixado em `backend/requirements.txt`) as voltas
que entram na faixa de linhas reais: classificacao (`Qualifying`) de cada ano
e a classificatoria da sprint (Sprint Shootout em 2023, Sprint Qualifying
de 2024 em diante). A corrida sprint nunca entra.

**So a posicao entra.** De cada volta escolhida sai so `X` e `Y` dos dados de
posicao (`Lap.get_pos_data()`), sem interpolar nos instantes dos dados do
carro (`get_telemetry()` nao e usado). Velocidade, pedais, marcha, rotacao,
DRS e distancia nao sao lidos nem salvos. O tempo da volta so escolhe e
identifica a volta; nunca vira dado.

O funil, nesta ordem (a volta fica na primeira etapa em que falha):

1. `composto`: pneu fora de SOFT, MEDIUM e HARD;
2. `imprecisa`: `IsAccurate` falso;
3. `apagada`: `Deleted` verdadeiro. A sessao sem essa informacao (coluna
   ausente ou nao booleana, o que acontece sem as mensagens da direcao de
   prova) fica inteira de fora;
4. `bandeira`: `TrackStatus` diferente de `'1'` (verde a volta toda);
5. `box`: entrada ou saida de box;
6. `chuva`: algum registro de `Rainfall` verdadeiro em `weather_data` entre o
   inicio e o fim da volta. Sem o intervalo da volta, nao ha como conferir, e
   ela cai aqui.

Depois do funil: de cada piloto, a volta mais rapida que sobrou; de cada
sessao, os 10 pilotos mais rapidos.

A classificacao de 2024 e carregada pelo caminho em que foi publicada
(`use_published_path`, pedido 24; ADR 0019): o FastF1 3.4.0 monta outro.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

YEARS = (2018, 2019, 2021, 2022, 2023, 2024, 2025)
EVENT = "Sao Paulo"
QUALIFYING = "Qualifying"
SPRINT_QUALIFYING_NAMES = ("Sprint Shootout", "Sprint Qualifying")
SPRINT_RACE = "Sprint"
LOAD_KWARGS = {"laps": True, "telemetry": True, "weather": True, "messages": True}

DRY_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
GREEN = "1"
TOP_DRIVERS = 10
POSITION_COLUMNS = ("X", "Y")

# Etapas do funil, na ordem em que sao aplicadas.
STAGES = ("composto", "imprecisa", "apagada", "bandeira", "box", "chuva")
STAGE_TEXT = {
    "composto": "pneu fora de SOFT, MEDIUM e HARD",
    "imprecisa": "IsAccurate falso",
    "apagada": "volta apagada (Deleted)",
    "bandeira": "TrackStatus diferente de '1'",
    "box": "entrada ou saida de box",
    "chuva": "Rainfall verdadeiro durante a volta, ou volta sem intervalo",
    "nao_e_a_melhor_do_piloto": "passou nos filtros, mas o piloto tem volta mais rapida",
    "fora_dos_10": "melhor volta do piloto, fora dos 10 pilotos mais rapidos da sessao",
    "escolhida": "melhor volta do piloto, entre os 10 mais rapidos",
}
PASSED = "passou"

# Sessoes publicadas num caminho diferente do que o FastF1 3.4.0 monta (pedido 24;
# ADR 0019, item 5). O FastF1 guarda o caminho em `Session.api_path`, montado em
# `fastf1/core.py` (linha 1180) com a data local da sessao no calendario atual. A
# classificacao de 2024 em Interlagos foi adiada de sabado, 02/11, para domingo,
# 03/11, e o calendario traz a data nova; a sessao, porem, foi publicada no caminho
# da data original. O cache usa o mesmo caminho (`fastf1/req.py`, linha 470).
PUBLISHED_PATHS = {
    (2024, "São Paulo Grand Prix", QUALIFYING):
        "/static/2024/2024-11-03_São_Paulo_Grand_Prix/2024-11-02_Qualifying/",
}


# --------------------------------------------------------------- sessoes ---

def event_sessions(event) -> List[Tuple[str, pd.Timestamp]]:
    """(nome, data) das sessoes do fim de semana, na ordem do calendario."""
    out = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        if isinstance(name, str) and name:
            out.append((name, pd.Timestamp(event.get(f"Session{i}Date"))))
    return out


def choose_sessions(event) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    """Sessoes que entram e sessoes ligadas a sprint que nao entram, com o motivo.

    A classificatoria da sprint e conferida pelo nome e pela data: ela so entra
    se vier antes de uma sessao chamada `Sprint` (a corrida). Em 2021 e 2022 a
    "Sprint Qualifying" era a propria corrida sprint; nessas datas nao existe
    corrida depois dela, e a sessao fica de fora.
    """
    sessions = event_sessions(event)
    sprint_dates = [date for name, date in sessions if name == SPRINT_RACE]
    chosen, skipped = [], []
    for name, date in sessions:
        row = {"nome": name, "data": date.isoformat()}
        if name == QUALIFYING:
            chosen.append({**row, "tipo": "Q"})
        elif name in SPRINT_QUALIFYING_NAMES:
            if sprint_dates and all(date < race for race in sprint_dates):
                chosen.append({**row, "tipo": "SQ"})
            else:
                skipped.append({**row, "motivo": "nao ha corrida sprint depois dela: e a propria corrida sprint"})
        elif name == SPRINT_RACE:
            skipped.append({**row, "motivo": "corrida sprint nao entra"})
    return chosen, skipped


def published_api_path(year: int, event_name: str, session_name: str) -> Optional[str]:
    """O caminho publicado da sessao, so quando ano, evento e sessao sao exatamente os de `PUBLISHED_PATHS`."""
    return PUBLISHED_PATHS.get((int(year), str(event_name), str(session_name)))


def use_published_path(session, year: int, event_name: str, session_name: str) -> Optional[str]:
    """Troca `session.api_path` pelo caminho publicado, antes do `load`, so na sessao listada.

    Devolve o caminho que o FastF1 tinha montado, se trocou; `None` se a sessao
    nao e a listada, e entao nada muda. Nao toca em nenhum arquivo do FastF1.
    """
    path = published_api_path(year, event_name, session_name)
    if path is None:
        return None
    previous = str(session.api_path)
    session.api_path = path
    return previous


# ---------------------------------------------------------------- funil ---

def has_deleted_info(laps: pd.DataFrame) -> bool:
    """A sessao sabe quais voltas foram apagadas: coluna `Deleted` booleana, sem vazios."""
    if "Deleted" not in laps.columns:
        return False
    column = laps["Deleted"]
    return column.dtype == bool and not column.isna().any()


def weather_records(laps: pd.DataFrame, weather: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Para cada volta: quantos registros de tempo caem nela e se algum tem chuva.

    Volta sem inicio ou fim conhecido devolve -1 registros e conta como chuva:
    nao ha como conferir.
    """
    times = pd.to_timedelta(weather["Time"]).to_numpy()
    rain = weather["Rainfall"].fillna(False).astype(bool).to_numpy()
    counts = np.full(len(laps), -1, dtype=int)
    wet = np.ones(len(laps), dtype=bool)
    starts = pd.to_timedelta(laps["LapStartTime"]).to_numpy()
    ends = pd.to_timedelta(laps["Time"]).to_numpy()
    for i, (start, end) in enumerate(zip(starts, ends)):
        if pd.isna(start) or pd.isna(end):
            continue
        inside = (times >= start) & (times <= end)
        counts[i] = int(inside.sum())
        wet[i] = bool(rain[inside].any())
    return counts, wet


def funnel(laps: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Etapa em que cada volta caiu (`passou` se passou nas seis), na ordem do pedido 23.

    Devolve um DataFrame com o mesmo indice de `laps`: `etapa` e
    `registros_de_tempo` (quantos registros de `weather_data` caem na volta).
    """
    compound_ok = laps["Compound"].isin(DRY_COMPOUNDS).to_numpy()
    accurate_ok = laps["IsAccurate"].fillna(False).astype(bool).to_numpy()
    deleted_ok = ~laps["Deleted"].fillna(True).astype(bool).to_numpy()
    green_ok = (laps["TrackStatus"].astype(object) == GREEN).to_numpy()
    box_ok = (laps["PitInTime"].isna() & laps["PitOutTime"].isna()).to_numpy()
    counts, wet = weather_records(laps, weather)
    checks = (compound_ok, accurate_ok, deleted_ok, green_ok, box_ok, ~wet)
    stage = np.full(len(laps), PASSED, dtype=object)
    for name, ok in zip(reversed(STAGES), reversed(checks)):
        stage = np.where(ok, stage, name)
    return pd.DataFrame({"etapa": stage, "registros_de_tempo": counts}, index=laps.index)


def funnel_counts(stages: Sequence[str], total: int) -> Dict[str, int]:
    """Quantas voltas restam depois de cada etapa (e quantas cairam nela)."""
    stages = list(stages)
    remaining = int(total)
    out: Dict[str, int] = {"voltas": remaining}
    for name in STAGES:
        fell = stages.count(name)
        remaining -= fell
        out[f"caem_{name}"] = fell
        out[f"restam_depois_{name}"] = remaining
    return out


def pick_laps(passed: pd.DataFrame, top: int = TOP_DRIVERS) -> Tuple[pd.Index, pd.Index, pd.Index]:
    """(escolhidas, nao_e_a_melhor_do_piloto, fora_dos_10), como indices de `passed`.

    De cada piloto fica a volta mais rapida; dos pilotos, os `top` mais
    rapidos. O tempo so escolhe: nao sai daqui como dado.
    """
    timed = passed[passed["LapTime"].notna()]
    if timed.empty:
        return pd.Index([]), passed.index, pd.Index([])
    best = timed.loc[timed.groupby("Driver")["LapTime"].idxmin()].sort_values("LapTime", kind="stable")
    chosen = best.index[: int(top)]
    beyond = best.index[int(top):]
    not_best = passed.index.difference(best.index)
    return chosen, not_best, beyond


# --------------------------------------------------------------- leitura ---

def read_xy(lap) -> Tuple[np.ndarray, int]:
    """(N, 2) com `X` e `Y` dos dados de posicao da volta, e quantas linhas nao finitas sairam.

    So `get_pos_data()` e so as duas colunas: nada de velocidade, pedais,
    marcha, rotacao, DRS ou distancia (ADR 0018), e nada de `get_telemetry()`,
    que interpola a posicao nos instantes dos dados do carro.
    """
    position = lap.get_pos_data()
    xy = np.asarray(position[list(POSITION_COLUMNS)], dtype=float)
    finite = np.isfinite(xy).all(axis=1)
    return xy[finite], int((~finite).sum())


def seconds(value) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return float(pd.Timedelta(value).total_seconds())


# --------------------------------------------------------------- coleta ---

class _Collector(logging.Handler):
    """Guarda os avisos do FastF1 durante o `load`: eles dizem o que falhou."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages: List[str] = []

    def emit(self, record):
        message = record.getMessage()
        if message not in self.messages:
            self.messages.append(message)


@dataclass
class SessionData:
    """O que sai de uma sessao: o registro para o manifesto e o X/Y das voltas escolhidas."""

    info: Dict[str, Any]
    laps: List[Dict[str, Any]] = field(default_factory=list)
    xy: Dict[str, np.ndarray] = field(default_factory=dict)


def lap_key(year: int, kind: str, driver: str, lap_number: int) -> str:
    return f"{int(year)}_{kind}_{driver}_{int(lap_number)}"


def deletion_messages(session) -> Dict[str, int]:
    """Mensagens da direcao de prova que falam de tempo apagado, para conferir o `Deleted`."""
    try:
        messages = session.race_control_messages["Message"].astype(str)
    except Exception:
        return {"mensagens": 0, "com_deleted": 0, "com_reinstated": 0, "com_track_limits": 0}
    return {
        "mensagens": int(len(messages)),
        "com_deleted": int(messages.str.contains("DELETED").sum()),
        "com_reinstated": int(messages.str.contains("REINSTATED").sum()),
        "com_track_limits": int(messages.str.contains("TRACK LIMITS").sum()),
    }


def collect_session(fastf1, year: int, name: str, kind: str, event: str = EVENT,
                    extra_laps: Sequence[Tuple[str, int]] = ()) -> SessionData:
    """Carrega uma sessao, passa o funil, escolhe as voltas e le o X/Y delas.

    `extra_laps` sao voltas (piloto, numero) lidas a parte, fora do funil (a
    volta de chuva de 2024). Se a sessao nao carregar, `info["erro"]` diz por
    que, e nada mais e lido.
    """
    info: Dict[str, Any] = {"ano": int(year), "sessao": name, "tipo": kind, "carregou": False}
    collector = _Collector()
    logger = logging.getLogger("fastf1")
    logger.addHandler(collector)
    started = time.perf_counter()
    try:
        weekend = fastf1.get_event(int(year), event)
        info["evento"] = str(weekend.get("EventName", ""))
        session = weekend.get_session(name)
        info["data"] = str(getattr(session, "date", ""))
        previous = use_published_path(session, int(year), info["evento"], name)
        if previous is not None:
            info["caminho_corrigido"] = {"montado_pelo_fastf1": previous, "publicado": str(session.api_path)}
        info["api_path"] = str(getattr(session, "api_path", ""))
        session.load(**LOAD_KWARGS)
        laps = session.laps
        if laps is None or len(laps) == 0:
            raise RuntimeError("a sessao carregou sem nenhuma volta")
        session.pos_data  # noqa: B018 -- so confere que a posicao carregou
        weather = session.weather_data
    except Exception as exc:
        info["erro"] = f"{type(exc).__name__}: {exc}"
    finally:
        logger.removeHandler(collector)
        info["tempo_de_carga_s"] = time.perf_counter() - started
        info["avisos_do_fastf1"] = collector.messages[:12]
    if "erro" in info:
        return SessionData(info)
    info["carregou"] = True
    info["voltas"] = int(len(laps))
    info["compostos"] = {str(k): int(v) for k, v in laps["Compound"].value_counts(dropna=False).items()}
    info["apagadas"] = deletion_messages(session)

    data = SessionData(info)
    if not has_deleted_info(laps):
        info["fora"] = "sem a informacao de volta apagada (coluna Deleted ausente ou incompleta)"
        return data
    if weather is None or len(weather) == 0 or "Rainfall" not in weather.columns:
        info["fora"] = "sem dados de tempo (Rainfall) para conferir chuva"
        return data
    info["voltas_marcadas_apagadas"] = int(laps["Deleted"].sum())
    info["registros_de_tempo"] = int(len(weather))
    info["registros_com_chuva"] = int(weather["Rainfall"].fillna(False).astype(bool).sum())

    stages = funnel(laps, weather)
    passed = laps[stages["etapa"] == PASSED]
    chosen, not_best, beyond = pick_laps(passed)
    final = stages["etapa"].copy()
    final[not_best] = "nao_e_a_melhor_do_piloto"
    final[beyond] = "fora_dos_10"
    final[chosen] = "escolhida"
    info["funil"] = funnel_counts(stages["etapa"].tolist(), len(laps))
    info["funil"]["melhores_por_piloto"] = int(len(chosen) + len(beyond))
    info["funil"]["escolhidas"] = int(len(chosen))

    extras = {(str(driver), int(number)) for driver, number in extra_laps}
    for index in laps.index:
        lap = laps.loc[index]
        record = {
            "chave": lap_key(year, kind, str(lap["Driver"]), int(lap["LapNumber"])),
            "ano": int(year),
            "sessao": name,
            "piloto": str(lap["Driver"]),
            "volta": int(lap["LapNumber"]),
            "tempo_s": seconds(lap["LapTime"]),
            "pneu": None if pd.isna(lap["Compound"]) else str(lap["Compound"]),
            "etapa": str(final[index]),
            "registros_de_tempo": int(stages.at[index, "registros_de_tempo"]),
        }
        wanted = record["etapa"] == "escolhida"
        extra = (record["piloto"], record["volta"]) in extras
        if wanted or extra:
            xy, dropped = read_xy(lap)
            record["amostras_xy"] = int(len(xy))
            record["linhas_nao_finitas"] = dropped
            data.xy[record["chave"]] = xy
            if extra:
                record["a_parte"] = "volta de chuva, fora da faixa seca"
        data.laps.append(record)
    return data
