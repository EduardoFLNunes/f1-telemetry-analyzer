"""Normalizacao das variaveis, ajustada so no treino.

Ajustar a escala sobre o dataset inteiro vaza a distribuicao das voltas de teste
para dentro do treino. E um vazamento pequeno e real, e e gratuito de evitar:
media e desvio saem das voltas de treino e sao aplicados como estao nas demais.

Canais constantes (a temperatura de pista dentro de uma sessao, por exemplo)
ficam com desvio zero. Dividir por zero produz `inf`, entao o desvio vira 1 e o
canal passa a ser a diferenca para a media -- que e o comportamento certo: um
canal sem variacao nao carrega informacao para o modelo escalar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence

import numpy as np

MIN_STD = 1e-6


@dataclass
class StandardScaler:
    """Media e desvio por canal."""

    columns: Sequence[str]
    mean: np.ndarray
    std: np.ndarray

    def transform(self, matrix: np.ndarray) -> np.ndarray:
        # Preserva float32. Promover para float64 aqui dobrava a memoria de um
        # tensor de entrada de 56 MB, tres vezes (treino, validacao, teste).
        values = np.asarray(matrix)
        dtype = values.dtype if values.dtype == np.float32 else float
        return ((values - self.mean) / self.std).astype(dtype, copy=False)

    def inverse_transform(self, matrix: np.ndarray) -> np.ndarray:
        return np.asarray(matrix, dtype=float) * self.std + self.mean

    def to_dict(self) -> Dict[str, object]:
        return {
            "columns": list(self.columns),
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "StandardScaler":
        return cls(
            columns=list(payload["columns"]),
            mean=np.asarray(payload["mean"], dtype=float),
            std=np.asarray(payload["std"], dtype=float),
        )

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "StandardScaler":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class TargetTransform:
    """Como cada canal de saida e representado durante o treino.

    Tres modos, um por natureza de canal:

    * `unit` — ja vive em [0, 1] (`brake`, `throttle`). Nao se transforma: o
      modelo tem sigmoid nesse canal e a comparacao e direta.
    * `log` — estritamente positivo e com faixa larga (`step_time_s`, de 0,01 s
      numa reta a 0,1 s numa curva lenta). Em log, errar 10% custa o mesmo nos
      dois casos; em escala linear a perda so olharia as curvas lentas.
    * `standard` — o resto (`lateral` em metros, `speed_kmh` em km/h). Sem
      normalizar, uma perda quadratica soma metros com quilometros por hora e o
      canal de maior variancia decide o treino sozinho.
    """

    columns: Sequence[str]
    modes: Sequence[str]
    mean: np.ndarray
    std: np.ndarray

    UNIT = "unit"
    LOG = "log"
    STANDARD = "standard"

    def forward(self, values: np.ndarray) -> np.ndarray:
        out = np.asarray(values, dtype=float).copy()
        for index, mode in enumerate(self.modes):
            if mode == self.LOG:
                out[..., index] = np.log(np.maximum(out[..., index], 1e-6))
            if mode != self.UNIT:
                out[..., index] = (out[..., index] - self.mean[index]) / self.std[index]
        return out

    def inverse(self, values: np.ndarray) -> np.ndarray:
        out = np.asarray(values, dtype=float).copy()
        for index, mode in enumerate(self.modes):
            if mode != self.UNIT:
                out[..., index] = out[..., index] * self.std[index] + self.mean[index]
            if mode == self.LOG:
                out[..., index] = np.exp(out[..., index])
        return out

    def to_dict(self) -> Dict[str, object]:
        return {
            "columns": list(self.columns),
            "modes": list(self.modes),
            "mean": self.mean.tolist(),
            "std": self.std.tolist(),
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "TargetTransform":
        return cls(
            columns=list(payload["columns"]),
            modes=list(payload["modes"]),
            mean=np.asarray(payload["mean"], dtype=float),
            std=np.asarray(payload["std"], dtype=float),
        )


UNIT_CHANNELS = ("brake", "throttle", "clutch")
LOG_CHANNELS = ("step_time_s", "sector_time_s")


def fit_target_transform(values: np.ndarray, columns: Sequence[str]) -> TargetTransform:
    """Ajusta a transformacao de saida sobre os alvos de treino."""
    matrix = np.asarray(values, dtype=float)
    if matrix.ndim == 3:
        matrix = matrix.reshape(-1, matrix.shape[-1])

    modes = [
        TargetTransform.UNIT
        if name in UNIT_CHANNELS
        else TargetTransform.LOG
        if name in LOG_CHANNELS
        else TargetTransform.STANDARD
        for name in columns
    ]
    prepared = matrix.copy()
    for index, mode in enumerate(modes):
        if mode == TargetTransform.LOG:
            prepared[:, index] = np.log(np.maximum(prepared[:, index], 1e-6))

    mean = np.nanmean(prepared, axis=0)
    std = np.nanstd(prepared, axis=0)
    std = np.where(np.isfinite(std) & (std > MIN_STD), std, 1.0)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    for index, mode in enumerate(modes):
        if mode == TargetTransform.UNIT:
            mean[index], std[index] = 0.0, 1.0
    return TargetTransform(columns=list(columns), modes=modes, mean=mean, std=std)


def fit_scaler(matrix: np.ndarray, columns: Sequence[str]) -> StandardScaler:
    """Ajusta sobre uma matriz (amostras, canais)."""
    values = np.asarray(matrix, dtype=float)
    if values.ndim == 3:
        values = values.reshape(-1, values.shape[-1])
    mean = np.nanmean(values, axis=0)
    std = np.nanstd(values, axis=0)
    std = np.where(np.isfinite(std) & (std > MIN_STD), std, 1.0)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    return StandardScaler(columns=list(columns), mean=mean, std=std)
