"""Gera a pista que acompanha o app do jogo (pedido 35, Parte E e o mapa aproximado).

Dois arquivos na pasta do app (`radio_engenheiro/`), instalados pelo `instalar.ps1`:

* **`pista.json`:** a pista do minimapa, para quando o backend estiver fora do ar (o
  minimapa baixa a mesma pista de `GET /api/radio/minimapa`): o contorno do asfalto
  tratado do cache, simplificado; a marca da linha do s = 0; o nome das 14 curvas; e
  onde fica a imagem da pista detalhada no mundo;
* **`pista_detalhada.png`:** a pista do mapa aproximado, desenhada uma vez com as camadas
  do cache que o mapa do app usa (`drawTrackSurface`, em
  `frontend/src/components/map/OverlayRenderer.tsx`): o asfalto, a pintura classificada
  (o limite em branco, os boxes em amarelo, as vias de servico em cinza) e as zebras (a
  base escura com as faixas brancas). As cores e as larguras sao as do app com o zoom de
  perto. O app do jogo gira e aproxima essa imagem em volta do carro, a cada quadro.

A imagem fica em `PX_POR_METRO` pixels por metro, desenhada com o dobro e reduzida (as
bordas ficam suaves). As camadas do cache estao nas coordenadas do mapa (x, -z) (a mesma
posicao do carro no jogo): coluna = (x - x0) * k e linha = (-z - y0) * k.

So le o repositorio. Uso (na pasta backend): python ../tools/csp_app/gerar_pista.py
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND))

from core.radio import minimapa  # noqa: E402
from core.radio.analise import Pista  # noqa: E402
from core.radio.janelas import CACHE_DA_PISTA, carregar_geometria  # noqa: E402

REPO = BACKEND.parent
PASTA_DO_APP = Path(__file__).resolve().parent / "radio_engenheiro"
PX_POR_METRO = 3            # o mapa aproximado abre com 120 m na janela de 360 px: 3 px/m
SUPERAMOSTRA = 2            # desenhada com o dobro e reduzida: as bordas ficam suaves
MARGEM_M = 120.0            # a vista em volta do carro nunca sai da imagem

# As do app (OverlayRenderer.tsx): ASPHALT_FILL, KERB_*, MARKING_STYLES.
ASFALTO = ((0x2C, 0x2C, 0x2C), 1.0)
ZEBRA_ESCURA = ((0x11, 0x11, 0x11), 1.0)
ZEBRA_CLARA = ((0xF4, 0xF4, 0xF5), 1.0)
ZEBRA_BORDA = ((228, 228, 231), 0.85)
FAIXA_DA_ZEBRA_M = 1.1
BORDA_DA_ZEBRA_M = 0.4      # 1,2 px na tela do app, com 3 px/m
# A pintura: a cor, a opacidade e a largura (o minimo em pixels do app, com 3 px/m), na ordem de desenho.
PINTURA = (
    ("servico", (148, 163, 184), 0.34, 0.30),
    ("boxes", (234, 179, 8), 0.62, 0.37),
    ("limite", (255, 255, 255), 1.0, 0.70),
)


def _angulo_dominante(pontos):
    """O mesmo `dominantAngle` do app: as direcoes dobradas em meio circulo."""
    sx = sy = 0.0
    for (x0, y0), (x1, y1) in zip(pontos[:-1], pontos[1:]):
        dx, dy = x1 - x0, y1 - y0
        if dx < 0:
            dx, dy = -dx, -dy
        sx += dx
        sy += dy
    return math.atan2(sy, sx)


def gerar_imagem(cache: dict):
    asfalto = [l["points"] for l in cache["asphaltSurface"]["loops"] if len(l.get("points") or []) >= 3]
    pinturas = [f for f in cache["markingGeometry"]["features"] if len(f.get("points") or []) >= 2]
    zebras = [p["points"] for p in cache["kerbGeometry"]["polygons"] if len(p.get("points") or []) >= 4]
    todos = np.array([q for grupo in (asfalto, [f["points"] for f in pinturas], zebras) for pts in grupo for q in pts])
    x0, y0 = float(todos[:, 0].min()) - MARGEM_M, float(todos[:, 1].min()) - MARGEM_M
    x1, y1 = float(todos[:, 0].max()) + MARGEM_M, float(todos[:, 1].max()) + MARGEM_M
    largura, altura = int(math.ceil((x1 - x0) * PX_POR_METRO)), int(math.ceil((y1 - y0) * PX_POR_METRO))
    k2 = PX_POR_METRO * SUPERAMOSTRA
    L2, A2 = largura * SUPERAMOSTRA, altura * SUPERAMOSTRA

    def px(pontos):
        return [((p[0] - x0) * k2, (p[1] - y0) * k2) for p in pontos]

    def poligono(mascara: np.ndarray, pontos, xor: bool = False) -> None:
        """Preenche o poligono na mascara (ou troca, para o par-impar do asfalto), so no retangulo dele."""
        p = px(pontos)
        c0 = max(0, int(min(q[0] for q in p)) - 1)
        l0 = max(0, int(min(q[1] for q in p)) - 1)
        c1 = min(L2, int(max(q[0] for q in p)) + 2)
        l1 = min(A2, int(max(q[1] for q in p)) + 2)
        recorte = Image.new("L", (c1 - c0, l1 - l0), 0)
        ImageDraw.Draw(recorte).polygon([(a - c0, b - l0) for a, b in p], fill=255)
        r = np.asarray(recorte)
        if xor:
            mascara[l0:l1, c0:c1] ^= r
        else:
            np.maximum(mascara[l0:l1, c0:c1], r, out=mascara[l0:l1, c0:c1])

    def reduzir(mascara: np.ndarray) -> np.ndarray:
        """Do dobro para o tamanho final: a cobertura de cada pixel, de 0 a 1."""
        return np.asarray(Image.fromarray(mascara).resize((largura, altura), Image.BOX), dtype=np.float32) / 255.0

    camadas = []   # (cobertura, cor, opacidade), na ordem do app: asfalto, pintura, zebras

    m = np.zeros((A2, L2), dtype=np.uint8)
    for loop in asfalto:
        poligono(m, loop, xor=True)       # par-impar, como o fill('evenodd') do app
    camadas.append((reduzir(m), *ASFALTO))

    for tipo, cor, opacidade, metros in PINTURA:
        img = Image.new("L", (L2, A2), 0)
        d = ImageDraw.Draw(img)
        for f in pinturas:
            if f.get("kind") != tipo:
                continue
            p = px(f["points"])
            if f.get("closed"):
                p = p + p[:1]
            d.line(p, fill=255, width=max(1, round(metros * k2)), joint="curve")
        camadas.append((reduzir(np.asarray(img).copy()), cor, opacidade))

    escura = np.zeros((A2, L2), dtype=np.uint8)
    clara = np.zeros((A2, L2), dtype=np.uint8)
    borda = Image.new("L", (L2, A2), 0)
    db = ImageDraw.Draw(borda)
    for pontos in zebras:
        p = px(pontos)
        c0 = max(0, int(min(q[0] for q in p)) - 1)
        l0 = max(0, int(min(q[1] for q in p)) - 1)
        c1 = min(L2, int(max(q[0] for q in p)) + 2)
        l1 = min(A2, int(max(q[1] for q in p)) + 2)
        recorte = Image.new("L", (c1 - c0, l1 - l0), 0)
        ImageDraw.Draw(recorte).polygon([(a - c0, b - l0) for a, b in p], fill=255)
        dentro = np.asarray(recorte) > 0
        # As faixas: como o app, giradas pelo angulo dominante, a partir de -span no centro do retangulo.
        xs = np.array([q[0] for q in pontos])
        ys = np.array([q[1] for q in pontos])
        cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
        span = math.hypot(xs.max() - xs.min(), ys.max() - ys.min())
        ang = _angulo_dominante(pontos)
        cols = (np.arange(c0, c1) + 0.5) / k2 + x0
        lins = (np.arange(l0, l1) + 0.5) / k2 + y0
        X, Y = np.meshgrid(cols, lins)
        ao_longo = (X - cx) * math.cos(ang) + (Y - cy) * math.sin(ang)
        faixa = np.mod(ao_longo + span, 2 * FAIXA_DA_ZEBRA_M) < FAIXA_DA_ZEBRA_M
        escura[l0:l1, c0:c1] |= (dentro & ~faixa).astype(np.uint8) * 255
        clara[l0:l1, c0:c1] |= (dentro & faixa).astype(np.uint8) * 255
        db.line(p + p[:1], fill=255, width=max(1, round(BORDA_DA_ZEBRA_M * k2)), joint="curve")
    camadas.append((reduzir(escura), *ZEBRA_ESCURA))
    camadas.append((reduzir(clara), *ZEBRA_CLARA))
    camadas.append((reduzir(np.asarray(borda).copy()), *ZEBRA_BORDA))

    # "Por cima", camada a camada, com a cor pre-multiplicada; o fundo e transparente.
    rgb = np.zeros((altura, largura, 3), dtype=np.float32)
    alfa = np.zeros((altura, largura), dtype=np.float32)
    for cobertura, cor, opacidade in camadas:
        a = cobertura * opacidade
        rgb *= (1.0 - a)[..., None]
        rgb += a[..., None] * (np.array(cor, dtype=np.float32) / 255.0)
        alfa = a + alfa * (1.0 - a)
    com_alfa = np.where(alfa > 1e-6, alfa, 1.0)
    saida = np.dstack([np.clip(rgb / com_alfa[..., None], 0, 1), alfa])
    imagem = Image.fromarray((saida * 255 + 0.5).astype(np.uint8))   # (altura, largura, 4): RGBA
    transformacao = {"arquivo": "pista_detalhada.png", "x0": round(x0, 3), "y0": round(y0, 3),
                     "pxPorMetro": PX_POR_METRO, "largura": largura, "altura": altura,
                     "eixos": "coluna = (x - x0) * pxPorMetro; linha = (-z - y0) * pxPorMetro"}
    return imagem, transformacao


def main() -> None:
    track = carregar_geometria(REPO)
    if track is None:
        raise SystemExit("sem a geometria oficial em data/cache/tracks")
    pista = Pista.da_geometria(track)
    dados = minimapa.montar(track, pista.segmentos, None, None, None, minimapa.linha_do_jogo_m(REPO),
                            minimapa.contorno_do_asfalto(REPO))
    cache = json.loads((REPO / "data" / "cache" / "tracks" / CACHE_DA_PISTA).read_text(encoding="utf-8"))
    imagem, transformacao = gerar_imagem(cache)
    PASTA_DO_APP.mkdir(exist_ok=True)
    arquivo_da_imagem = PASTA_DO_APP / transformacao["arquivo"]
    imagem.save(arquivo_da_imagem, optimize=True)
    saida = PASTA_DO_APP / "pista.json"
    saida.write_text(json.dumps({"comprimentoM": dados["comprimentoM"], "pista": dados["pista"],
                                 "linhaDoS0": dados["linhaDoS0"], "curvas": dados["curvas"], "imagem": transformacao,
                                 "geometryId": getattr(track, "geometry_id", None)},
                                separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    contornos = dados["pista"]["contornos"]
    print(f"{saida}: {saida.stat().st_size} bytes; pista: {dados['pista']['origem']}, {len(contornos)} contornos, "
          f"{sum(len(c) for c in contornos)} pontos; {len(dados['curvas'])} curvas")
    print(f"{arquivo_da_imagem}: {transformacao['largura']} x {transformacao['altura']} px, "
          f"{arquivo_da_imagem.stat().st_size} bytes")


if __name__ == "__main__":
    main()
