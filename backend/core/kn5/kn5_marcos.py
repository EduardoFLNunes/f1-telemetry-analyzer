"""Os marcos da pista lidos dos kn5 (pedido 52, Parte B; ADR 0033, item 3). So leitura.

Le um kn5 inteiro (o formato do Assetto Corsa, versao 5) e guarda, de cada malha estatica, o
material, a textura difusa do material, os vertices (a posicao, a normal e o UV, ja no mundo) e os
triangulos. Nada e escrito: o arquivo e aberto so para leitura e nenhum dado dele vai para fora,
alem dos marcos derivados (`marcos_da_pista`).

O formato (o mesmo que `kn5_reader` le, com os campos que ele pula):

* o cabecalho: `sc6969`, a versao, as texturas (o tipo, o nome e os bytes);
* os materiais: o nome, o shader, 6 bytes, as variaveis (o nome e 40 bytes) e as texturas
  (o slot, 4 bytes e o nome da textura);
* os nos: o tipo, o nome, o numero de filhos e um byte; o no de transformacao (tipo 1) traz a
  matriz 4 x 4 (linhas, com a translacao na ultima linha); a malha estatica (tipo 2) traz 3 bytes,
  os vertices (44 bytes: a posicao, a normal, o UV e a tangente), os indices (16 bits) e 33 bytes
  (o material, a camada, os LODs, a esfera e um byte).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

MAGIC = b"sc6969"


class Kn5Erro(RuntimeError):
    pass


@dataclass
class Malha:
    nome: str
    caminho: str
    material: str
    textura: Optional[str]          # a textura difusa (txDiffuse) do material
    posicoes: np.ndarray            # (n, 3), no mundo
    normais: np.ndarray             # (n, 3), no mundo
    uv: np.ndarray                  # (n, 2)
    triangulos: np.ndarray          # (m, 3)


@dataclass
class Kn5:
    arquivo: Path
    versao: int
    texturas: Dict[str, bytes] = field(default_factory=dict)
    malhas: List[Malha] = field(default_factory=list)


class _Leitor:
    def __init__(self, dados: bytes):
        self.d = dados
        self.p = 0

    def ler(self, n: int) -> bytes:
        if self.p + n > len(self.d):
            raise Kn5Erro(f"fim do arquivo em {self.p} (faltam {n} bytes)")
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def u8(self) -> int:
        return self.ler(1)[0]

    def u32(self) -> int:
        return struct.unpack_from("<I", self.ler(4))[0]

    def texto(self) -> str:
        n = self.u32()
        return self.ler(n).decode("utf-8", errors="replace")


def ler_kn5(arquivo: Path, texturas_guardadas: Sequence[str] = ()) -> Kn5:
    """Le o kn5 inteiro (so leitura). `texturas_guardadas`: os nomes das texturas cujos bytes ficam na memoria."""
    arquivo = Path(arquivo)
    with arquivo.open("rb") as f:
        dados = f.read()
    r = _Leitor(dados)
    if r.ler(6) != MAGIC:
        raise Kn5Erro("nao e um kn5")
    versao = r.u32()
    if versao > 5:
        r.u32()
    kn5 = Kn5(arquivo=arquivo, versao=versao)
    guardar = {t.upper() for t in texturas_guardadas}
    for _ in range(r.u32()):
        r.u32()
        nome = r.texto()
        n = r.u32()
        b = r.ler(n)
        if nome.upper() in guardar:
            kn5.texturas[nome] = b
    materiais: List[Tuple[str, Optional[str]]] = []
    for _ in range(r.u32()):
        nome = r.texto()
        r.texto()                  # o shader
        r.ler(6)
        for _ in range(r.u32()):
            r.texto()
            r.ler(40)
        difusa = None
        for _ in range(r.u32()):
            slot = r.texto()
            r.ler(4)
            tex = r.texto()
            if slot == "txDiffuse":
                difusa = tex
        materiais.append((nome, difusa))

    def no(pai: np.ndarray, caminho_pai: str) -> None:
        tipo = r.u32()
        nome = r.texto()
        caminho = f"{caminho_pai}/{nome}" if caminho_pai else nome
        filhos = r.u32()
        r.u8()
        if tipo == 1:
            m = np.array(struct.unpack_from("<16f", r.ler(64)), dtype=float).reshape(4, 4)
            mundo = m @ pai
            for _ in range(filhos):
                no(mundo, caminho)
            return
        if tipo == 2:
            r.ler(3)
            nv = r.u32()
            bruto = np.frombuffer(r.ler(nv * 44), dtype="<f4").reshape(nv, 11).astype(float)
            ni = r.u32()
            idx = np.frombuffer(r.ler(ni * 2), dtype="<u2").astype(np.int64)
            mat = struct.unpack_from("<I", r.ler(33))[0]
            pos = np.c_[bruto[:, 0:3], np.ones(nv)] @ pai
            nor = bruto[:, 3:6] @ pai[:3, :3]
            nome_mat, difusa = materiais[mat] if 0 <= mat < len(materiais) else (f"#{mat}", None)
            kn5.malhas.append(Malha(nome=nome, caminho=caminho, material=nome_mat, textura=difusa,
                                    posicoes=pos[:, :3], normais=nor, uv=bruto[:, 6:8],
                                    triangulos=idx[: (ni // 3) * 3].reshape(-1, 3)))
            for _ in range(filhos):
                no(pai, caminho)
            return
        raise Kn5Erro(f"no do tipo {tipo} nao suportado ({caminho})")

    no(np.eye(4), "")
    if r.p != len(dados):
        raise Kn5Erro(f"sobraram {len(dados) - r.p} bytes depois dos nos")
    return kn5


# ── as pecas ligadas de uma malha ────────────────────────────────────────

def pecas_ligadas(malha: Malha, solda_m: float = 0.01) -> List[np.ndarray]:
    """Os triangulos da malha separados em pecas ligadas (vertices na mesma posicao, a menos de `solda_m`,
    contam como o mesmo: as placas de uma malha por material repetem os vertices em cada face)."""
    chave = np.round(malha.posicoes / solda_m).astype(np.int64)
    _, unico = np.unique(chave, axis=0, return_inverse=True)
    unico = unico.reshape(-1)
    pai = list(range(int(unico.max()) + 1 if unico.size else 0))

    def raiz(a: int) -> int:
        while pai[a] != a:
            pai[a] = pai[pai[a]]
            a = pai[a]
        return a

    for t in malha.triangulos:
        a, b, c = (raiz(int(unico[k])) for k in t)
        pai[b] = a
        pai[raiz(c)] = a
    grupos: Dict[int, List[int]] = {}
    for k, t in enumerate(malha.triangulos):
        grupos.setdefault(raiz(int(unico[t[0]])), []).append(k)
    return [np.array(v, dtype=np.int64) for v in grupos.values()]
