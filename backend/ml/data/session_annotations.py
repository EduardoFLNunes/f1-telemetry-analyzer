"""Anotacoes do piloto para sessoes inteiras (05/10).

`docs/experimentos/anotacoes_de_sessao.csv` diz, para uma gravacao inteira,
quem pilotou e, quando a gravacao nao registrou, em que carro. Existe porque o
app instalado ainda grava sem o indicador de IA e sem o `carModel`: as voltas
da sessao de 04/10 23:51 ficavam `desconhecida` e fora do coach e da evolucao,
embora o Eduardo tenha pilotado todas.

As anotacoes sao a verdade de campo daquela gravacao, como as de 04/10 volta a
volta (`detector_ia.LAP_LABELS`). Uma gravacao anotada aqui nao pode estar
tambem no arquivo volta a volta, e o carro anotado nao pode contradizer o do
metadado: os dois casos param o comando.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from .. import config
from .origin import ORIGINS, SOURCE_SESSION_ANNOTATION

SESSION_ANNOTATIONS = config.repo_root() / "docs" / "experimentos" / "anotacoes_de_sessao.csv"


def session_annotations(path: Optional[Path] = None) -> pd.DataFrame:
    """As anotacoes por gravacao: sessao, origem, carModel, anotado_em, observacao."""
    source = Path(path) if path else SESSION_ANNOTATIONS
    if not source.exists():
        return pd.DataFrame(columns=["sessao", "origem", "carModel", "anotado_em", "observacao"])
    notes = pd.read_csv(source, dtype=str, keep_default_na=False)
    bad = sorted(set(notes["origem"]) - set(ORIGINS))
    if bad:
        raise SystemExit(f"PARADO: origem desconhecida nas anotacoes de sessao: {bad}")
    if notes["sessao"].duplicated().any():
        raise SystemExit("PARADO: uma gravacao aparece duas vezes nas anotacoes de sessao.")
    return notes


def check_session_annotations(inventory: pd.DataFrame, notes: pd.DataFrame, lap_labelled: set) -> List[str]:
    """O que impede de aplicar as anotacoes de sessao. Vazio quando batem."""
    problems = []
    sessions = set(inventory["session_id"])
    for sid in notes["sessao"]:
        if sid not in sessions:
            problems.append(f"{sid} nao esta no inventario")
        if sid in lap_labelled:
            problems.append(f"{sid} ja esta nos rotulos volta a volta de 04/10")
    return problems


def apply_session_annotations(inventory: pd.DataFrame, notes: pd.DataFrame) -> pd.DataFrame:
    """Todas as voltas de cada gravacao anotada recebem a origem anotada.

    A fonte e sempre `anotacao_sessao`, mesmo quando o indicador concorda: o
    rotulo vem da anotacao, e nunca do indicador nem do detector.
    """
    out = inventory.copy()
    for _, note in notes.iterrows():
        mask = out["session_id"] == note["sessao"]
        out.loc[mask, "origem"] = note["origem"]
        out.loc[mask, "origem_fonte"] = SOURCE_SESSION_ANNOTATION
    return out


def cars_with_annotations(cars: Dict[str, Optional[str]], notes: Optional[pd.DataFrame] = None) -> Dict[str, Optional[str]]:
    """O carro de cada gravacao: o do metadado, ou o anotado quando o metadado nao tem.

    Se os dois existem e discordam, o comando para.
    """
    notes = session_annotations() if notes is None else notes
    out = dict(cars)
    for _, note in notes.iterrows():
        car = (note.get("carModel") or "").strip()
        if not car:
            continue
        recorded = out.get(note["sessao"])
        if recorded and recorded != car:
            raise SystemExit(f"PARADO: o carro anotado para {note['sessao']} ({car}) nao e o do metadado ({recorded}).")
        out[note["sessao"]] = car
    return out


def car_for(session_id: str, recorded: Optional[str], notes: Optional[pd.DataFrame] = None) -> Optional[str]:
    """O carro de uma gravacao, com a anotacao quando o metadado nao tem."""
    return cars_with_annotations({session_id: recorded}, notes).get(session_id)
