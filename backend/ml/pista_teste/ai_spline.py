"""Leitor e escritor do `fast_lane.ai` do Assetto Corsa, versao 7 (pedido 47, A.2).

O formato, conferido byte a byte no arquivo de `vhe_interlagos/gp/ai` e nas
duas fontes abertas (o `AcTools/AiFile` do Content Manager e o `import_ai.py`
do addon `io_import_accsv`):

* **cabecalho:** 4 inteiros de 32 bits: versao (7), numero de pontos, tempo de
  volta e numero de amostras (os dois ultimos valem 0 em Interlagos);
* **pontos:** por ponto, 3 floats de posicao (x, altura, z), a distancia
  acumulada e o indice (inteiro);
* **extras:** um inteiro com a contagem (igual ao numero de pontos) e 18 floats
  por ponto, nesta ordem: velocidade, acelerador, freio, `ObsoleteLatG`, raio,
  lateral esquerda, lateral direita, cambagem, direcao, normal (3), comprimento,
  vetor para a frente (3), marca e inclinacao (`Grade`);
* **grade:** um inteiro (`HasGrid`); se for 1, o maximo e o minimo (3 floats
  cada), o numero de vizinhos (inteiro), a densidade (float), o numero de
  colunas e, por coluna, o numero de celulas e, por celula, a contagem e os
  indices dos pontos mais proximos.

A grade e recalculavel: os extremos sao os dos pontos com 350 m de folga, as
colunas e as linhas sao o piso de (extensao / densidade), e cada celula guarda
os `k` pontos mais proximos do centro dela em X/Z, do mais perto ao mais longe.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

VERSAO = 7
CAMPOS_EXTRAS = (
    "velocidade", "acelerador", "freio", "obsolete_lat_g", "raio", "lateral_esquerda", "lateral_direita",
    "cambagem", "direcao", "normal_x", "normal_y", "normal_z", "comprimento", "frente_x", "frente_y", "frente_z",
    "marca", "inclinacao",
)
COL = {nome: i for i, nome in enumerate(CAMPOS_EXTRAS)}
FOLGA_DA_GRADE_M = 350.0

_PONTO = np.dtype([("pos", "<f4", (3,)), ("dist", "<f4"), ("idx", "<i4")])


@dataclass
class Grade:
    maximo: np.ndarray          # (3,) float32
    minimo: np.ndarray          # (3,) float32
    vizinhos: int
    densidade: float
    celulas: np.ndarray         # (colunas, linhas, vizinhos) int32

    @property
    def forma(self):
        return self.celulas.shape


@dataclass
class AiSpline:
    versao: int
    tempo_de_volta: int
    amostras: int
    pos: np.ndarray             # (n, 3) float32: x, altura, z
    dist: np.ndarray            # (n,) float32
    idx: np.ndarray             # (n,) int32
    extras: np.ndarray          # (n, 18) float32
    tem_grade: int = 1
    grade: Optional[Grade] = None
    cauda: bytes = field(default=b"", repr=False)   # bytes depois da grade (vazio em Interlagos)

    @property
    def n(self) -> int:
        return int(self.pos.shape[0])

    def campo(self, nome: str) -> np.ndarray:
        return self.extras[:, COL[nome]]

    def copia(self) -> "AiSpline":
        g = self.grade
        return replace(self, pos=self.pos.copy(), dist=self.dist.copy(), idx=self.idx.copy(), extras=self.extras.copy(),
                       grade=None if g is None else replace(g, maximo=g.maximo.copy(), minimo=g.minimo.copy(),
                                                            celulas=g.celulas.copy()))


class FormatoInvalido(ValueError):
    pass


def ler(fonte: Union[str, Path, bytes]) -> AiSpline:
    """Le um `fast_lane.ai` (caminho ou bytes). So le: nunca abre para escrita."""
    data = fonte if isinstance(fonte, (bytes, bytearray)) else Path(fonte).read_bytes()
    if len(data) < 16:
        raise FormatoInvalido("arquivo menor que o cabecalho")
    versao, n, tempo, amostras = struct.unpack_from("<4i", data, 0)
    if versao != VERSAO:
        raise FormatoInvalido(f"versao {versao}; so a 7 e conhecida")
    off = 16
    pontos = np.frombuffer(data, dtype=_PONTO, count=n, offset=off)
    off += n * _PONTO.itemsize
    (n_extras,) = struct.unpack_from("<i", data, off)
    off += 4
    if n_extras != n:
        raise FormatoInvalido(f"{n_extras} extras para {n} pontos")
    extras = np.frombuffer(data, dtype="<f4", count=n * 18, offset=off).reshape(n, 18)
    off += n * 72
    (tem_grade,) = struct.unpack_from("<i", data, off)
    off += 4
    grade = None
    if tem_grade:
        maximo = np.frombuffer(data, "<f4", 3, off).copy()
        minimo = np.frombuffer(data, "<f4", 3, off + 12).copy()
        vizinhos, densidade, colunas = struct.unpack_from("<ifi", data, off + 24)
        off += 36
        linhas_ref = None
        celulas: List[np.ndarray] = []
        for _ in range(colunas):
            (linhas,) = struct.unpack_from("<i", data, off)
            off += 4
            if linhas_ref is None:
                linhas_ref = linhas
            if linhas != linhas_ref:
                raise FormatoInvalido("colunas da grade com numeros de celulas diferentes")
            bloco = np.frombuffer(data, "<i4", linhas * (vizinhos + 1), off).reshape(linhas, vizinhos + 1)
            if not (bloco[:, 0] == vizinhos).all():
                raise FormatoInvalido("celula da grade com contagem diferente do numero de vizinhos")
            celulas.append(bloco[:, 1:].copy())
            off += bloco.nbytes
        grade = Grade(maximo, minimo, int(vizinhos), float(densidade),
                      np.stack(celulas) if celulas else np.zeros((0, 0, vizinhos), np.int32))
    return AiSpline(versao, tempo, amostras, pontos["pos"].copy(), pontos["dist"].copy(), pontos["idx"].copy(),
                    extras.copy(), int(tem_grade), grade, bytes(data[off:]))


def escrever(spline: AiSpline) -> bytes:
    """Os bytes do arquivo. Ler e escrever de novo da o mesmo arquivo, byte a byte."""
    n = spline.n
    partes = [struct.pack("<4i", spline.versao, n, spline.tempo_de_volta, spline.amostras)]
    pontos = np.zeros(n, dtype=_PONTO)
    pontos["pos"] = spline.pos
    pontos["dist"] = spline.dist
    pontos["idx"] = spline.idx
    partes += [pontos.tobytes(), struct.pack("<i", n), np.asarray(spline.extras, "<f4").reshape(n, 18).tobytes(),
               struct.pack("<i", spline.tem_grade)]
    if spline.tem_grade:
        g = spline.grade
        colunas, linhas, k = g.celulas.shape
        partes += [np.asarray(g.maximo, "<f4").tobytes(), np.asarray(g.minimo, "<f4").tobytes(),
                   struct.pack("<ifi", g.vizinhos, g.densidade, colunas)]
        for c in range(colunas):
            bloco = np.empty((linhas, k + 1), "<i4")
            bloco[:, 0] = k
            bloco[:, 1:] = g.celulas[c]
            partes += [struct.pack("<i", linhas), bloco.tobytes()]
    partes.append(spline.cauda)
    return b"".join(partes)


def construir_grade(pos: np.ndarray, vizinhos: int = 10, densidade: float = 10.0,
                    folga_m: float = FOLGA_DA_GRADE_M) -> Grade:
    """A grade de vizinhos de uma linha: os `vizinhos` pontos mais proximos do centro de cada celula, em X/Z."""
    from scipy.spatial import cKDTree

    pos32 = np.asarray(pos, np.float32)
    minimo = np.array([pos32[:, 0].min() - folga_m, 0.0, pos32[:, 2].min() - folga_m], np.float32)
    maximo = np.array([pos32[:, 0].max() + folga_m, 0.0, pos32[:, 2].max() + folga_m], np.float32)
    colunas = int(np.floor((float(maximo[0]) - float(minimo[0])) / densidade))
    linhas = int(np.floor((float(maximo[2]) - float(minimo[2])) / densidade))
    xz = pos32[:, [0, 2]].astype(np.float64)
    cx = float(minimo[0]) + (np.arange(colunas) + 0.5) * densidade
    cz = float(minimo[2]) + (np.arange(linhas) + 0.5) * densidade
    centros = np.stack(np.meshgrid(cx, cz, indexing="ij"), axis=-1).reshape(-1, 2)
    _, idx = cKDTree(xz).query(centros, k=vizinhos)
    idx = _desempatar(xz, centros, np.atleast_2d(idx))
    return Grade(maximo, minimo, int(vizinhos), float(densidade), idx.reshape(colunas, linhas, vizinhos).astype(np.int32))


def _desempatar(xz, centros, idx):
    """Ordena cada celula pela distancia e, no empate, pelo indice (a ordem estavel do arquivo)."""
    linhas = np.arange(idx.shape[0])[:, None]
    idx = np.sort(idx, axis=-1)
    d = np.sum((xz[idx] - centros[:, None, :]) ** 2, axis=-1)
    return idx[linhas, np.argsort(d, axis=-1, kind="stable")]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_arquivo(path: Union[str, Path]) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for bloco in iter(lambda: handle.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()
