"""A galeria da rodada 4 (pedido 42, Parte E.2.5; secao 7.5, item 5).

Para cada uma das 5 perguntas do kit, 3 passagens "aplica" e 3 "nao aplica" da
rodada 4, minhas e da IA, ao lado do desenho da literatura e com as referencias
como no kit 2. Pode ser gerada agora, porque nenhum humano vai rotular depois de
ve-la (atualizacao de 20/11). Sorteio com a semente 42.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import rotulagem as K
from .dados import carregar, raiz, volta_do_modelo, voltas_da_rodada1
from .detectores import APLICA, NAO_APLICA, Lap, measure_passage
from .fases import CornerPhases
from ..track.geometry import load_geometry

SEED = 42
POR_ESTADO = 3


def _fases(path: Path):
    out = []
    for d in json.loads(path.read_text(encoding="utf-8"))["curvas"]:
        d = dict(d)
        d["trecho"] = tuple(d["trecho"])
        out.append(CornerPhases(**d))
    return out


def escolher(estados: pd.DataFrame, det: str, rng: np.random.Generator) -> pd.DataFrame:
    d = estados[estados["detector"] == det]
    picked = []
    for state in (APLICA, NAO_APLICA):
        pool = d[d["estado"] == state]
        ai, mine = pool[pool["origem"] == "ia"], pool[pool["origem"] != "ia"]
        n_ai = min(len(ai), 1)
        part = [ai.sample(n=n_ai, random_state=int(rng.integers(1 << 30)))] if n_ai else []
        n_me = min(len(mine), POR_ESTADO - n_ai)
        if n_me:
            part.append(mine.sample(n=n_me, random_state=int(rng.integers(1 << 30))))
        if part:
            picked.append(pd.concat(part))
    return pd.concat(picked) if picked else d.iloc[:0]


def gerar_galeria(out_html: Path, pasta_rodada: str = "rodada4") -> Path:
    root = raiz() / pasta_rodada
    track = load_geometry()
    phases = _fases(root / "fases.json")
    data = carregar(track, so_ids=voltas_da_rodada1(), progress=lambda *_: None)
    laps = {k: Lap.build(v) for k, v in data.voltas.items()}
    humans = sorted((l for l in laps.values() if l.volta.origem != "ia"), key=lambda l: l.total)
    ordered_best = [l.volta.lap_id for l in humans]
    model = Lap.build(volta_do_modelo(track))
    flat = lambda v: np.full_like(np.asarray(v, dtype=float), np.nan)
    rows = [measure_passage(model, track, cp, phases[cp.k - 1], flat, rodada=4) for cp in phases]
    model_points = pd.DataFrame([{k: v for k, v in r.items() if k != "_ausente"} for r in rows]).set_index("curva")
    estados = pd.DataFrame(json.loads((root / "tecnicas.json").read_text(encoding="utf-8"))["estados"])
    estados = estados[estados["curva"] != "volta"]
    cp_by = {cp.curva: cp for cp in phases}
    rng = np.random.default_rng(SEED)
    body, resumo = [], {}
    for det in K.DETECTORS:
        body.append(K.literature_page(det))
        chosen = escolher(estados, det, rng)
        resumo[det] = chosen.groupby(["estado", "origem"]).size().to_dict()
        for n, (_, r) in enumerate(chosen.iterrows(), start=1):
            cp = cp_by[r["curva"]]
            best_id = ordered_best[0] if r["lap_id"] != ordered_best[0] else ordered_best[1]
            mp = model_points.loc[cp.curva].to_dict() if cp.curva in model_points.index else {}
            svg = K.trace_svg2(laps[r["lap_id"]], model, laps[best_id], track, cp, phases[cp.k - 1], mp)
            quem = "IA" if r["origem"] == "ia" else "piloto"
            estado = "aplica" if r["estado"] == APLICA else "não aplica"
            body.append(f'<p class="q"><b>{det}-G{n:02d}</b> · a rodada 4 diz <b>{estado}</b> · {quem} · '
                        f'{html.escape(r["lap_id"])}</p>' + K._card(f"{det}-G{n:02d}", cp, track, svg))
    intro = ('<p>A galeria da rodada 4: para cada pergunta, 3 passagens que o detector chama de "aplica" e 3 de "não aplica", '
             'minhas e da IA (semente 42), ao lado do desenho da literatura. Aqui o estado do detector e a origem aparecem, porque '
             'a galeria não é para rotular: ela mostra se o "aplica" do detector se parece com o que a literatura descreve.</p>')
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(K._page("Galeria da rodada 4", intro, "".join(body)), encoding="utf-8")
    (out_html.with_suffix(".json")).write_text(json.dumps({str(k): {str(kk): int(vv) for kk, vv in v.items()}
                                                           for k, v in resumo.items()}, indent=1), encoding="utf-8")
    return out_html
