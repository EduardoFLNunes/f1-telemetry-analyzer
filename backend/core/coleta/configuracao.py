"""A configuracao do app que a aba "Coleta de dados" edita (pedido 28, Parte C.3).

Dois valores:

* **repositorio**: a pasta do repositorio. O coach le dela, so lendo,
  `data/reference_models/<pista>.json` (o modelo) e `<pista>.geometry.json` (a
  geometria oficial). O modelo nao e copiado para o pacote nem para a pasta de
  dados, porque muda a cada `atualizar_coach`. A contagem oficial da M1 tambem
  le o store v2 de la (`data/ml/`).
* **referenciaCoach**: `volta_ia`, `minha_melhor` ou `desligado`. Substitui a
  variavel `AT_COACH_REFERENCE` e o "renomeie o arquivo para treinar sem o coach".

O arquivo fica em `<pasta de dados>/data/configuracao/app.json`, fora da pasta
de gravacoes. Nenhum leitor do ML olha para ele.

Quem vale, quando ha mais de uma fonte:

* referencia: `AT_COACH_REFERENCE`, se estiver definida (o app de
  desenvolvimento continua obedecendo a ela), depois a configuracao, depois
  `volta_ia`;
* repositorio: a configuracao, depois `AT_REPO_PATH` (o Electron passa o
  repositorio em que o app foi construido, quando ele ainda existe), depois a
  raiz do codigo, quando o backend roda do codigo-fonte.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..assisted_analysis.reference_model import DEFAULT_REFERENCE, REFERENCE_KINDS, REFERENCE_LABELS

COACH_OFF = "desligado"
REFERENCE_CHOICES = tuple(REFERENCE_KINDS) + (COACH_OFF,)
CHOICE_LABELS = {**REFERENCE_LABELS, COACH_OFF: "coach desligado"}
CONFIG_RELATIVE = Path("data") / "configuracao" / "app.json"


class ConfigError(ValueError):
    """Valor invalido para a configuracao; a mensagem vai para a aba."""


class AppConfig:
    def __init__(self, runtime_root: Path, default_repository: Optional[Path] = None,
                 default_source: str = "AT_REPO_PATH"):
        self.path = Path(runtime_root) / CONFIG_RELATIVE
        self.default_repository = Path(default_repository) if default_repository else None
        self.default_source = default_source
        self._lock = threading.Lock()
        self._cache: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------ arquivo ---

    def read(self) -> Dict[str, Any]:
        with self._lock:
            if self._cache is None:
                try:
                    self._cache = json.loads(self.path.read_text(encoding="utf-8"))
                    if not isinstance(self._cache, dict):
                        self._cache = {}
                except (OSError, json.JSONDecodeError):
                    self._cache = {}
            return dict(self._cache)

    def save(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """Grava as mudancas validas. Valor vazio volta ao padrao."""
        current = self.read()
        if "repositorio" in changes:
            value = changes.get("repositorio")
            if value in (None, ""):
                current.pop("repositorio", None)
            else:
                folder = Path(str(value)).expanduser()
                if not folder.is_dir():
                    raise ConfigError(f"A pasta {folder} não existe.")
                current["repositorio"] = str(folder.resolve())
        if "referenciaCoach" in changes:
            value = changes.get("referenciaCoach")
            if value in (None, ""):
                current.pop("referenciaCoach", None)
            elif value not in REFERENCE_CHOICES:
                raise ConfigError(f"Referência desconhecida: {value}. Use {', '.join(REFERENCE_CHOICES)}.")
            else:
                current["referenciaCoach"] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        with self._lock:
            self._cache = dict(current)
        return current

    # ------------------------------------------------------------ valores ---

    def repository(self) -> Tuple[Optional[Path], Optional[str]]:
        """(pasta do repositorio, de onde ela veio)."""
        saved = self.read().get("repositorio")
        if saved:
            return Path(saved), "configuracao"
        if self.default_repository is not None:
            return self.default_repository, self.default_source
        return None, None

    def reference(self) -> Tuple[str, str]:
        """(escolha, de onde ela veio). A escolha e uma de `REFERENCE_CHOICES`."""
        env = (os.environ.get("AT_COACH_REFERENCE") or "").strip().lower()
        if env:
            # Como antes do pedido 28: valor desconhecido vira a referencia padrao.
            return (env if env in REFERENCE_CHOICES else DEFAULT_REFERENCE), "AT_COACH_REFERENCE"
        saved = self.read().get("referenciaCoach")
        if saved in REFERENCE_CHOICES:
            return saved, "configuracao"
        return DEFAULT_REFERENCE, "padrao"

    # -------------------------------------------- o que o coach pergunta ---

    def coach_root(self) -> Optional[Path]:
        """A raiz de onde o coach le `data/reference_models/`, ou None."""
        folder, _ = self.repository()
        return folder

    def coach_reference(self) -> Optional[str]:
        """A referencia do coach, ou None com o coach desligado."""
        choice, _ = self.reference()
        return None if choice == COACH_OFF else choice

    def to_api(self) -> Dict[str, Any]:
        folder, folder_source = self.repository()
        choice, choice_source = self.reference()
        return {
            "arquivo": str(self.path),
            "repositorio": str(folder) if folder else None,
            "repositorioFonte": folder_source,
            "repositorioPadrao": str(self.default_repository) if self.default_repository else None,
            "repositorioExiste": bool(folder and folder.is_dir()),
            "referenciaCoach": choice,
            "referenciaCoachRotulo": CHOICE_LABELS.get(choice, choice),
            "referenciaCoachFonte": choice_source,
            "referenciaTravadaPelaVariavel": choice_source == "AT_COACH_REFERENCE",
            "opcoesReferencia": [{"id": c, "rotulo": CHOICE_LABELS[c]} for c in REFERENCE_CHOICES],
        }
