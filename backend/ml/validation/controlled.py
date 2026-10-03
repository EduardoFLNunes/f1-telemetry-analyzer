"""Sessao controlada (Fase 2c, ADR 0011): plano sorteado e analise do 2 x 2.

A Fase 2b mostrou que as voltas do dia a dia nao identificam o efeito de mudar
o ponto de frenagem ou a linha: o piloto quase nunca muda essas coisas. Aqui as
mudancas sao feitas de proposito, numa curva, em blocos de quatro voltas com as
quatro condicoes em ordem sorteada (`docs/experimentos/protocolo_sessao_controlada.md`).

Tudo que depende so de numeros fica neste modulo, sem gravacao nem cache de
geometria, para poder ser testado com dados sinteticos. Os scripts
`plan_controlled_session` e `analyze_controlled_session` ligam isto ao pipeline
existente (leitor, store, janelas da Fase 2b).

Convencoes
----------
* Ponto de frenagem: diferenca em metros, positiva = freou depois. "10 m mais
  cedo" e -10 m.
* Linha: medida no `lateral` do `ml` (positivo a esquerda, ADR 0003) e relatada
  como deslocamento **para dentro da curva**: `lateral * direcao`, com a direcao
  da curva +1 a esquerda e -1 a direita.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

# ----------------------------------------------------------- condicoes ---

@dataclass(frozen=True)
class Condition:
    code: str
    braking_m: float          # pedido, em relacao a A (negativo = mais cedo)
    inward_m: float           # pedido, para dentro da curva
    braking_text: str
    line_text: str


CONDITIONS: Dict[str, Condition] = {
    "A": Condition("A", 0.0, 0.0, "habitual", "habitual"),
    "B": Condition("B", -10.0, 0.0, "10 m mais cedo", "habitual"),
    "C": Condition("C", 0.0, 2.0, "habitual", "2 m para dentro"),
    "D": Condition("D", -10.0, 2.0, "10 m mais cedo", "2 m para dentro"),
}
WARMUP = "AQ"

# Nomes das curvas -> rotulo de `ml.track.corners.detect_corners` na geometria
# `0ed16f0dd2225990`. Sao as curvas que abrem as janelas da Fase 2b.
CORNER_NAMES = {
    "S do Senna": "C01-esq",
    "Descida do Lago": "C04-esq",
    "Ferradura": "C06-dir",
    "Laranjinha": "C07-dir",
    "Pinheirinho": "C08-esq",
    "Bico de Pato": "C10-dir",
    "Juncao": "C12-esq",
}

# "Longe do pedido": a execucao media errou o alvo por mais da metade dele.
BRAKING_TOLERANCE_M = 5.0
INWARD_TOLERANCE_M = 1.0

PLAN_COLUMNS = ("ordem", "bloco", "condicao", "freada", "linha", "curva", "semente")


# --------------------------------------------------------------- plano ---

def make_plan(
    curve: str = "Bico de Pato",
    conditions: Sequence[str] = ("A", "B", "C", "D"),
    laps_per_condition: int = 8,
    warmup: int = 5,
    seed: int = 2026,
) -> pd.DataFrame:
    """Aquecimento, depois blocos com todas as condicoes em ordem sorteada."""
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise ValueError(f"condicoes desconhecidas: {unknown}; validas: {sorted(CONDITIONS)}")
    if len(set(conditions)) != len(conditions):
        raise ValueError("condicao repetida na lista")
    if curve not in CORNER_NAMES:
        raise ValueError(f"curva desconhecida: {curve}; validas: {sorted(CORNER_NAMES)}")

    rng = np.random.default_rng(seed)
    rows: List[Dict[str, object]] = []
    for _ in range(int(warmup)):
        rows.append({"bloco": 0, "condicao": WARMUP, "freada": "livre", "linha": "livre"})
    for block in range(1, int(laps_per_condition) + 1):
        for code in rng.permutation(list(conditions)):
            condition = CONDITIONS[str(code)]
            rows.append(
                {
                    "bloco": block,
                    "condicao": condition.code,
                    "freada": condition.braking_text,
                    "linha": condition.line_text,
                }
            )
    plan = pd.DataFrame(rows)
    plan.insert(0, "ordem", np.arange(1, len(plan) + 1))
    plan["curva"] = curve
    plan["semente"] = int(seed)
    return plan[list(PLAN_COLUMNS)]


def plan_text(plan: pd.DataFrame) -> str:
    """O plano para imprimir ou deixar na tela durante a sessao."""
    curve = str(plan["curva"].iloc[0])
    seed = int(plan["semente"].iloc[0])
    measured = plan[plan["condicao"] != WARMUP]
    lines = [
        f"PLANO DA SESSAO CONTROLADA - {curve}",
        f"semente {seed} | {len(plan) - len(measured)} voltas de aquecimento | "
        f"{len(measured)} voltas medidas em {measured['bloco'].nunique()} blocos",
        "",
        "Volta errada (passou reto, rodou, freou fora do ponto): anote o numero da",
        "volta no jogo como invalida e REPITA A MESMA CONDICAO na volta seguinte.",
        "",
        "Condicoes:",
    ]
    for code in sorted(measured["condicao"].unique()):
        c = CONDITIONS[code]
        lines.append(f"  {code}: freada {c.braking_text}; linha {c.line_text}")
    lines.append("")
    current = None
    for _, row in plan.iterrows():
        if row["bloco"] != current:
            current = row["bloco"]
            if current == 0:
                lines.append("AQUECIMENTO (alem da volta de saida dos boxes; o numero exato nao importa)")
            else:
                lines.append(f"BLOCO {current}")
                if current == 1:
                    lines.append("  ANOTE o numero no jogo desta volta (primeira do bloco 1): ____")
        if row["condicao"] == WARMUP:
            lines.append(f"  volta {row['ordem']:>2}  livre")
        else:
            lines.append(
                f"  volta {row['ordem']:>2}  [{row['condicao']}]  freada {row['freada']:<15} linha {row['linha']}"
            )
    return "\n".join(lines) + "\n"


# ------------------------------------------------------- casar voltas ---

def lap_label(row) -> str:
    """O que o piloto viu na tela: numero da volta no jogo, tempo e hora.

    `lap_time_s` (cronometro do jogo no fim da volta) e `clock` (hora do relogio
    no inicio dela) sao opcionais; o script de analise os preenche a partir da
    gravacao.
    """
    parts = [f"volta {int(row['lap_number'])} no jogo"]
    lap_time = row.get("lap_time_s")
    if lap_time is not None and np.isfinite(lap_time):
        minutes, seconds = divmod(float(lap_time), 60.0)
        parts.append(f"tempo {int(minutes)}:{seconds:06.3f}")
    clock = row.get("clock")
    if isinstance(clock, str) and clock:
        parts.append(f"as {clock}")
    return "(" + ", ".join(parts) + ")"


class PlanMismatchError(ValueError):
    """As voltas da gravacao nao casam com o plano. Nunca se adivinha."""


def match_laps(
    laps: pd.DataFrame, plan: pd.DataFrame, invalid: Sequence[int] = (), start: Optional[int] = None
) -> pd.DataFrame:
    """Casa, em ordem, as voltas aproveitaveis da gravacao com as linhas do plano.

    `laps`: uma linha por volta gravada, com `lap_id`, `sequence`, `lap_number`
    (numero do jogo), `valid` (gates de qualidade) e `reasons`. Aproveitavel e a
    volta que passou nos gates e nao foi anotada como invalida pelo piloto.

    Com `start` (o numero no jogo da primeira volta do bloco 1, anotado pelo
    piloto), tudo antes dessa volta e ignorado -- quantas voltas de aquecimento
    houver -- e so as voltas medidas do plano sao casadas, a partir dela. Contar
    o aquecimento de cabeca e facil de errar, e um erro de uma volta
    desalinharia o plano inteiro. Sem `start`, vale a contagem pelo plano.

    Se a contagem nao bater, levanta `PlanMismatchError` com a lista de voltas e
    o motivo de cada exclusao -- quem resolve e o piloto, nao o script.
    """
    invalid = [int(v) for v in invalid]
    ordered = laps.sort_values("sequence").reset_index(drop=True)

    if start is not None:
        start = int(start)
        present = ordered["lap_number"].astype(int)
        hits = ordered.index[present == start]
        if len(hits) == 0:
            raise PlanMismatchError(
                f"a volta {start} informada em --inicio nao existe na gravacao. "
                f"Numeros de volta no jogo presentes: {sorted(set(present.tolist()))}."
            )
        if len(hits) > 1:
            raise PlanMismatchError(
                f"a volta {start} informada em --inicio aparece {len(hits)} vezes na gravacao com o mesmo "
                "numero do jogo (o contador trava no box). Nada foi casado: diga qual delas, pelo lap_id."
            )
        first = int(hits[0])
        before = ordered.iloc[:first]
        ordered = ordered.iloc[first:].reset_index(drop=True)
        plan = plan[plan["condicao"] != WARMUP].reset_index(drop=True)
        # Uma volta anotada como invalida antes do inicio nao muda nada; so as
        # de depois contam.
        invalid = [n for n in invalid if n not in set(before["lap_number"].astype(int)) or n in set(ordered["lap_number"].astype(int))]

    repeated = ordered["lap_number"].value_counts()
    ambiguous = sorted(int(n) for n in invalid if repeated.get(n, 0) > 1)
    if ambiguous:
        raise PlanMismatchError(
            f"as voltas anotadas como invalidas {ambiguous} aparecem mais de uma vez com o "
            "mesmo numero do jogo (o contador trava no box); diga qual delas, pelo lap_id."
        )
    missing = sorted(set(invalid) - set(int(n) for n in ordered["lap_number"]))
    if missing:
        raise PlanMismatchError(f"voltas anotadas como invalidas que nao existem na gravacao: {missing}")

    status = []
    for _, row in ordered.iterrows():
        if int(row["lap_number"]) in invalid:
            status.append("invalida (anotada pelo piloto)")
        elif not bool(row["valid"]):
            status.append(f"excluida pelos gates: {row.get('reasons', '')}")
        else:
            status.append("aproveitavel")
    ordered["status"] = status
    usable = ordered[ordered["status"] == "aproveitavel"].reset_index(drop=True)

    if len(usable) != len(plan):
        listing = "\n".join(
            f"  gravada n. {i + 1:>2}  {lap_label(r)}  {r['lap_id']}: {r['status']}"
            for i, (_, r) in enumerate(ordered.iterrows())
        )
        if start is not None:
            raise PlanMismatchError(
                f"a partir da volta {start} (--inicio), o plano tem {len(plan)} voltas medidas, mas a "
                f"gravacao tem {len(usable)} voltas aproveitaveis de {len(ordered)} gravadas dali em diante. "
                "Nada foi casado.\n"
                "Confira se alguma volta errada nao foi anotada como invalida, se alguma volta do plano "
                "caiu nos gates de qualidade, ou se houve volta extra depois do bloco final.\n"
                f"Voltas gravadas a partir da volta {start}:\n{listing}"
            )
        raise PlanMismatchError(
            f"o plano tem {len(plan)} voltas ({int((plan['condicao'] == WARMUP).sum())} de aquecimento + "
            f"{int((plan['condicao'] != WARMUP).sum())} medidas), mas a gravacao tem {len(usable)} voltas "
            f"aproveitaveis de {len(ordered)} gravadas. Nada foi casado.\n"
            "Confira se alguma volta errada nao foi anotada como invalida, se alguma volta do plano "
            "caiu nos gates de qualidade, ou se o aquecimento teve mais ou menos voltas que o plano. "
            "Para nao depender da contagem do aquecimento, use --inicio com o numero no jogo da "
            "primeira volta do bloco 1.\n"
            f"Voltas gravadas:\n{listing}"
        )
    matched = pd.concat(
        [usable.reset_index(drop=True), plan.reset_index(drop=True)[["ordem", "bloco", "condicao"]]],
        axis=1,
    )
    return matched


# ------------------------------------------------- conferencia da execucao ---

MEASURES = ("braking_point_s", "lateral_entry_m", "lateral_apex_m", "lateral_exit_m", "throttle_point_s")


def execution_check(matched: pd.DataFrame, direction: int) -> Dict[str, object]:
    """Por condicao, quanto o piloto de fato mudou em relacao a A.

    `matched` precisa das colunas de `MEASURES` (em metros) e `condicao`.
    """
    measured = matched[matched["condicao"] != WARMUP]
    if "A" not in set(measured["condicao"]):
        raise PlanMismatchError("a analise compara tudo com a condicao A, e nao ha voltas A")
    base = measured[measured["condicao"] == "A"][list(MEASURES)].mean()
    out: Dict[str, object] = {}
    for code, group in measured.groupby("condicao"):
        means = group[list(MEASURES)].mean()
        spread = group[list(MEASURES)].std(ddof=1)
        braking = float(means["braking_point_s"] - base["braking_point_s"])
        inward = {
            where: float((means[f"lateral_{where}_m"] - base[f"lateral_{where}_m"]) * direction)
            for where in ("entry", "apex", "exit")
        }
        requested = CONDITIONS[code]
        notes = []
        if abs(braking - requested.braking_m) > BRAKING_TOLERANCE_M:
            notes.append(
                f"frenagem: pedido {requested.braking_m:+.0f} m, executado {braking:+.1f} m em media"
            )
        if abs(inward["entry"] - requested.inward_m) > INWARD_TOLERANCE_M:
            notes.append(
                f"linha na entrada: pedido {requested.inward_m:+.1f} m para dentro, executado {inward['entry']:+.2f} m"
            )
        out[code] = {
            "voltas": int(len(group)),
            "frenagem_vs_A_m": braking,
            "frenagem_dp_m": float(spread["braking_point_s"]) if len(group) > 1 else float("nan"),
            "para_dentro_vs_A_m": inward,
            "lateral_entrada_dp_m": float(spread["lateral_entry_m"]) if len(group) > 1 else float("nan"),
            "retomada_vs_A_m": float(means["throttle_point_s"] - base["throttle_point_s"]),
            "pedido": {"frenagem_m": requested.braking_m, "para_dentro_m": requested.inward_m},
            "longe_do_pedido": bool(notes),
            "observacoes": notes,
        }
    return out


# ------------------------------------------------------------ efeitos ---

CONTRASTS: Dict[str, Dict[str, float]] = {
    # media de B e D menos media de A e C
    "frenagem": {"A": -0.5, "B": 0.5, "C": -0.5, "D": 0.5},
    # media de C e D menos media de A e B
    "linha": {"A": -0.5, "B": -0.5, "C": 0.5, "D": 0.5},
    # (D - C) - (B - A)
    "interacao": {"A": 1.0, "B": -1.0, "C": -1.0, "D": 1.0},
    "B_menos_A": {"A": -1.0, "B": 1.0},
    "C_menos_A": {"A": -1.0, "C": 1.0},
    "D_menos_A": {"A": -1.0, "D": 1.0},
}


def estimate_effects(times: np.ndarray, conditions: Sequence[str], blocks: Sequence[int]) -> Dict[str, Dict[str, float]]:
    """Efeitos com IC 95 % por modelo linear com efeito de bloco.

    `tempo = media da condicao + efeito do bloco + erro`. E o modelo do
    delineamento em blocos casualizados: o bloco absorve o que muda ao longo da
    sessao (pneu, combustivel, cansaco), e os contrastes entre condicoes saem
    livres dele porque toda condicao aparece em todo bloco. Funciona tambem com
    um bloco incompleto (volta perdida e nao repetida), o que o bootstrap dentro
    dos blocos nao faz. O IC usa a distribuicao t com os graus de liberdade do
    residuo.
    """
    from scipy import stats

    y = np.asarray(times, dtype=float)
    conditions = np.asarray(conditions)
    blocks = np.asarray(blocks)
    codes = [c for c in ("A", "B", "C", "D") if c in set(conditions)]
    if set(codes) != {"A", "B", "C", "D"}:
        raise PlanMismatchError(f"o 2 x 2 precisa das quatro condicoes; ha so {codes}")
    levels = sorted(set(blocks.tolist()))
    columns = [(conditions == c).astype(float) for c in codes]
    columns += [(blocks == b).astype(float) for b in levels[1:]]
    x = np.column_stack(columns)
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    dof = len(y) - rank
    if dof <= 0:
        raise PlanMismatchError("voltas insuficientes para estimar o erro (graus de liberdade <= 0)")
    residual = y - x @ beta
    sigma2 = float(residual @ residual) / dof
    covariance = sigma2 * np.linalg.pinv(x.T @ x)
    t = float(stats.t.ppf(0.975, dof))

    out: Dict[str, Dict[str, float]] = {}
    for name, weights in CONTRASTS.items():
        c = np.zeros(x.shape[1])
        for code, weight in weights.items():
            c[codes.index(code)] = weight
        estimate = float(c @ beta)
        se = float(np.sqrt(c @ covariance @ c))
        out[name] = {"estimativa_s": estimate, "ep_s": se, "ic95_s": [estimate - t * se, estimate + t * se]}
    out["_modelo"] = {
        "voltas": int(len(y)),
        "blocos": int(len(levels)),
        "graus_de_liberdade": int(dof),
        "dp_residuo_s": float(np.sqrt(sigma2)),
    }
    return out


# ------------------------------------------------ comparacao com estimadores ---

def condition_differences(matched: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Diferencas medias X - A nas cinco entradas acionaveis da Fase 2b."""
    measured = matched[matched["condicao"] != WARMUP]
    base = measured[measured["condicao"] == "A"][list(MEASURES)].mean()
    out = {}
    for code in ("B", "C", "D"):
        group = measured[measured["condicao"] == code][list(MEASURES)].mean()
        diff = group - base
        # Ordem de `empirical.ACTIONABLE`.
        out[code] = np.array(
            [
                diff["braking_point_s"],
                diff["lateral_entry_m"],
                diff["lateral_apex_m"],
                diff["lateral_exit_m"],
                diff["throttle_point_s"],
            ],
            dtype=float,
        )
    return out


def compare_with_estimators(
    effects: Dict[str, Dict[str, float]],
    predictions: Dict[str, Dict[str, Tuple[float, float, float]]],
    out_of_distribution: Dict[str, bool],
) -> Dict[str, object]:
    """Efeito medido contra o previsto, condicao a condicao e nos contrastes.

    `predictions[estimador][codigo] = (centro, baixo, alto)` para X - A; baixo e
    alto sao NaN quando o estimador nao tem faixa. Os efeitos principais e a
    interacao previstos saem das mesmas combinacoes lineares das previsoes; para
    eles so o erro e relatado, porque a faixa de uma soma de faixas nao e a soma
    delas.
    """
    out: Dict[str, object] = {}
    for estimator, by_code in predictions.items():
        rows = {}
        for code in ("B", "C", "D"):
            centre, low, high = by_code[code]
            measured = effects[f"{code}_menos_A"]["estimativa_s"]
            rows[f"{code}_menos_A"] = {
                "medido_s": measured,
                "previsto_s": centre,
                "faixa95_s": [low, high],
                "erro_s": centre - measured,
                "medido_dentro_da_faixa": (bool(low <= measured <= high) if np.isfinite(low) else None),
                "fora_da_distribuicao": bool(out_of_distribution.get(code, False)),
            }
        p = {code: by_code[code][0] for code in ("B", "C", "D")}
        derived = {
            "frenagem": (p["B"] + p["D"] - p["C"]) / 2.0,
            "linha": (p["C"] + p["D"] - p["B"]) / 2.0,
            "interacao": p["D"] - p["C"] - p["B"],
        }
        for name, value in derived.items():
            rows[name] = {
                "medido_s": effects[name]["estimativa_s"],
                "previsto_s": value,
                "erro_s": value - effects[name]["estimativa_s"],
                "previsto_dentro_do_ic_medido": bool(
                    effects[name]["ic95_s"][0] <= value <= effects[name]["ic95_s"][1]
                ),
            }
        out[estimator] = rows
    return out
