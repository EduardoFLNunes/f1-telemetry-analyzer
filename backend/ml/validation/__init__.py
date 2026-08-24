"""Verificacao do que o subsistema afirma fazer.

Separado de `tests/` de proposito. Os testes provam que o codigo se comporta
como escrito, com dados sinteticos e em segundos. Isto aqui mede se os modelos
**treinados** e a busca **executada** produzem alguma coisa util sobre os dados
reais -- o que leva minutos, depende de artefatos em `data/ml/` e nao pode
rodar numa suite.

Nada aqui assume que algo funciona por existir codigo.
"""

from .generalization import HoldoutReport, channel_errors, holdout, per_lap_error, unknown_lap
from .learning import LearningEvidence, gather, responds_to_input, untrained_twin
from .search import SearchComparison, compare, random_search

__all__ = [
    "LearningEvidence",
    "gather",
    "responds_to_input",
    "untrained_twin",
    "HoldoutReport",
    "channel_errors",
    "holdout",
    "per_lap_error",
    "unknown_lap",
    "SearchComparison",
    "compare",
    "random_search",
]
