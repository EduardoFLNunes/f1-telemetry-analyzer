"""Ponte entre a identidade de volta do `ml` e a do replay.

Os dois lados cortam a mesma gravacao de jeitos diferentes:

* o `ml` corta pelo cronometro e numera pela ordem no arquivo:
  `"<sessao>#<ordem>"` (`recordings.iter_laps`);
* o replay (`core.recording.session_repository.lap_detail`, servido em
  `GET /api/laps/rec__<sessao>__<n>/replay`) entrega **todas** as amostras cujo
  contador do jogo vale `n`.

O contador do jogo nao e unico. Ele trava durante a parada de box: a sessao
`2026-08-16_03-30-14` tem quatro trechos gravados como volta 6, e o replay de
`rec__..__6` mostra os quatro emendados. E ele atrasa alguns quadros na linha
de chegada, entao o comeco de uma volta do `ml` ainda carrega o numero da
anterior.

Por isso a associacao nao e uma formula: ela e medida, contando quantas
amostras de cada volta do `ml` tem cada numero do jogo, e classificada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

# Fracao minima para considerar que um lado esta inteiro dentro do outro. Os
# quadros de atraso do contador sao ~3 de ~5000 por volta (0,06 %); 1 % deixa
# folga para eles sem aceitar um trecho de box (centenas a milhares de quadros).
CONTAINMENT_FRACTION = 0.99

# Classificacoes possiveis da associacao.
EXACT = "exact"                       # a volta do ml e o replay sao o mesmo trecho
REPLAY_HAS_MORE = "replay_has_more"   # o replay emenda esta volta com outros trechos
SPANS_COUNTERS = "spans_counters"     # a volta do ml atravessa mais de um numero do jogo
NO_COUNTER = "no_counter"             # nenhuma amostra com numero do jogo


@dataclass(frozen=True)
class LapIdentity:
    lap_id: str
    replay_lap_id: Optional[str]
    match: str
    game_lap_number: Optional[int]
    # Fracao das amostras desta volta que tem o numero do jogo escolhido.
    share_of_lap: float
    # Fracao das amostras do replay escolhido que pertencem a esta volta.
    share_of_replay: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "lap_id": self.lap_id,
            "replay_lap_id": self.replay_lap_id,
            "replay_match": self.match,
            "game_lap_number": self.game_lap_number,
            "replay_share_of_lap": self.share_of_lap,
            "replay_share_of_replay": self.share_of_replay,
        }


def replay_lap_id(session_id: str, game_lap_number: int) -> str:
    """O id que `routers.recording._parse_recording_lap_id` aceita."""
    return f"rec__{session_id}__{int(game_lap_number)}"


def classify(
    session_id: str,
    counts: Mapping[Tuple[str, int], Mapping[int, int]],
) -> Dict[str, LapIdentity]:
    """Associa cada volta do `ml` de uma sessao a um replay.

    `counts[(lap_id, sequence)]` e `{numero_do_jogo: amostras}` -- as voltas de
    **uma** sessao, todas elas, inclusive as que nao passam nos gates: um trecho
    de box rejeitado continua dentro do replay que o emenda.
    """
    replay_totals: Dict[int, int] = {}
    for per_lap in counts.values():
        for number, amount in per_lap.items():
            replay_totals[int(number)] = replay_totals.get(int(number), 0) + int(amount)

    out: Dict[str, LapIdentity] = {}
    for (lap_id, _sequence), per_lap in counts.items():
        total = sum(int(v) for v in per_lap.values())
        if total == 0:
            out[lap_id] = LapIdentity(lap_id, None, NO_COUNTER, None, 0.0, 0.0)
            continue
        number, amount = max(per_lap.items(), key=lambda item: (item[1], -item[0]))
        share_of_lap = amount / total
        share_of_replay = amount / replay_totals[int(number)]
        if share_of_lap < CONTAINMENT_FRACTION:
            match = SPANS_COUNTERS
        elif share_of_replay < CONTAINMENT_FRACTION:
            match = REPLAY_HAS_MORE
        else:
            match = EXACT
        out[lap_id] = LapIdentity(
            lap_id=lap_id,
            replay_lap_id=replay_lap_id(session_id, int(number)),
            match=match,
            game_lap_number=int(number),
            share_of_lap=float(share_of_lap),
            share_of_replay=float(share_of_replay),
        )
    return out


def counter_counts(frame) -> Dict[int, int]:
    """`{numero_do_jogo: amostras}` de uma volta crua (`RawLap.frame`)."""
    if frame is None or "lap_number" not in frame.columns:
        return {}
    values = frame["lap_number"].dropna().astype(int)
    return {int(k): int(v) for k, v in values.value_counts().items()}
