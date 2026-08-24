"""A fronteira entre o subsistema e um aplicativo que queira usa-lo.

Hoje nada chama isto: o `ml/` roda por linha de comando e o backend nao o
importa. Esta classe existe para que a integracao deixe de ser hipotese e passe
a ser uma chamada de funcao -- e para que o teste ponta a ponta exercite o mesmo
caminho que um endpoint exercitaria.

O que ela recebe e exatamente o que o runtime ja grava: a lista de amostras no
formato do `player.jsonl`. O que ela devolve e o que um painel precisaria para
falar com o piloto: onde ele perdeu tempo, por que, e qual seria a linha.

Os artefatos pesados -- geometria, modelos, tracado otimizado -- sao carregados
uma vez e reaproveitados. Carregar por chamada custaria segundos e nao faz
sentido num servico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from . import config
from .comparison.lap_vs_reference import LapComparison, compare_lap
from .comparison.reference_frame import reference_lap_frame, rescale_to_measured
from .data.samples import flatten
from .preprocessing.alignment import align_lap
from .preprocessing.cleaning import clean_lap
from .preprocessing.quality import evaluate_lap
from .preprocessing.resampling import lap_time_from_grid, resample_lap
from .track.corners import detect_corners
from .track.geometry import load_geometry
from .track.microsectors import build_microsectors


@dataclass
class LapAnalysis:
    """O resultado de analisar uma volta contra o tracado de referencia."""

    accepted: bool
    reasons: List[str] = field(default_factory=list)
    lap_time_s: Optional[float] = None
    reference_time_s: Optional[float] = None
    delta_s: Optional[float] = None
    sectors: List[Dict[str, Any]] = field(default_factory=list)
    corners: List[Dict[str, Any]] = field(default_factory=list)
    quality: Dict[str, float] = field(default_factory=dict)

    def to_api(self) -> Dict[str, Any]:
        """A forma que um endpoint devolveria."""
        return {
            "accepted": self.accepted,
            "reasons": self.reasons,
            "lapTimeSeconds": self.lap_time_s,
            "referenceTimeSeconds": self.reference_time_s,
            "deltaSeconds": self.delta_s,
            "sectors": self.sectors,
            "corners": self.corners,
            "quality": self.quality,
        }

    def worst_sectors(self, count: int = 5) -> List[Dict[str, Any]]:
        return sorted(self.sectors, key=lambda item: -item["deltaSeconds"])[:count]


class RacingLineService:
    """Carrega os artefatos uma vez e analisa voltas contra a referencia."""

    def __init__(
        self,
        root: Optional[Path] = None,
        reference_lateral: Optional[np.ndarray] = None,
        target_time_s: Optional[float] = None,
    ):
        self.root = Path(root) if root else config.artifacts_root()
        self.track = load_geometry()
        self.sectors = build_microsectors(self.track)
        self.corners = detect_corners(self.track)
        self._reference_lateral = reference_lateral
        self._target_time = target_time_s
        self._reference_frame: Optional[pd.DataFrame] = None
        self._envelope = None

    # ------------------------------------------------------- prontidao ------

    def missing(self) -> List[str]:
        """Artefatos ausentes. Vazio quer dizer pronto para atender."""
        absent: List[str] = []
        if self._reference_lateral is None:
            if not (self.root / "optimization" / "optimised_lateral.npy").exists():
                absent.append("optimization/optimised_lateral.npy")
            if not (self.root / "vehicle_envelope.json").exists():
                absent.append("vehicle_envelope.json")
        return absent

    @property
    def ready(self) -> bool:
        return not self.missing()

    # ------------------------------------------------------- referencia -----

    def reference(self) -> pd.DataFrame:
        """A volta de referencia na grade, carregada sob demanda."""
        if self._reference_frame is not None:
            return self._reference_frame

        from .optimization.vehicle_model import load_envelope

        if self._envelope is None:
            self._envelope = load_envelope(self.root)
        lateral = self._reference_lateral
        if lateral is None:
            lateral = np.load(self.root / "optimization" / "optimised_lateral.npy")

        frame = reference_lap_frame(self.track, np.asarray(lateral, dtype=float), self._envelope)
        if self._target_time:
            frame = rescale_to_measured(frame, float(self._target_time))
        self._reference_frame = frame
        return frame

    # ---------------------------------------------------------- analise -----

    def prepare(self, samples: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        """Amostras cruas -> volta na grade, com o veredito de qualidade.

        Mesmo caminho do pipeline offline, e de proposito: uma volta analisada
        ao vivo tem de passar pelos mesmos filtros que uma volta de treino,
        senao o sistema compara contra uma referencia construida sob regras que
        a volta do jogador nao respeita.
        """
        rows = [flatten(sample) for sample in samples]
        if not rows:
            return {"accepted": False, "reasons": ["nenhuma amostra recebida"]}

        cleaned, cleaning = clean_lap(pd.DataFrame(rows))
        if len(cleaned) < 4:
            return {"accepted": False, "reasons": ["amostras insuficientes apos limpeza"]}

        aligned, alignment = align_lap(cleaned, self.track)
        quality = evaluate_lap(aligned, self.track, alignment)
        grid = resample_lap(aligned, self.track)
        return {
            "accepted": quality.valid,
            "reasons": quality.reasons,
            "grid": grid,
            "quality": quality.metrics,
            "cleaning": cleaning.to_dict(),
            "lap_time_s": lap_time_from_grid(grid),
        }

    def analyse(self, samples: Iterable[Dict[str, Any]]) -> LapAnalysis:
        """O caminho completo: telemetria crua -> comparacao com a referencia."""
        prepared = self.prepare(samples)
        if not prepared.get("accepted"):
            return LapAnalysis(accepted=False, reasons=list(prepared.get("reasons", [])))

        grid = prepared["grid"]
        reference = self.reference()
        lap_time = float(prepared["lap_time_s"])
        reference_time = float(reference["lap_time_s"].iloc[0])

        comparison = compare_lap(
            "volta_recebida",
            grid,
            reference,
            self.track,
            self.sectors,
            self.corners,
            lap_time,
            reference_time,
        )
        return LapAnalysis(
            accepted=True,
            reasons=[],
            lap_time_s=lap_time,
            reference_time_s=reference_time,
            delta_s=comparison.delta_s,
            sectors=[
                {
                    "label": sector.label,
                    "startMeters": sector.start_s,
                    "endMeters": sector.end_s,
                    "deltaSeconds": sector.delta_s,
                    "lateralDeviationMeters": sector.lateral_deviation_mean_m,
                    "speedDeltaKmh": sector.speed_delta_mean_kmh,
                }
                for sector in comparison.sectors
            ],
            corners=[
                {
                    "label": corner.label,
                    "apexMeters": corner.apex_s,
                    "brakingDeltaMeters": corner.braking_delta_m,
                    "throttleDeltaMeters": corner.throttle_delta_m,
                    "minSpeedDeltaKmh": corner.min_speed_delta_kmh,
                    "exitSpeedDeltaKmh": corner.exit_speed_delta_kmh,
                    "apexOffsetMeters": corner.apex_lateral_delta_m,
                    "notes": corner.notes(),
                }
                for corner in comparison.corners
            ],
            quality={k: float(v) for k, v in prepared["quality"].items()},
        )
