import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
W = Path(sys.argv[1]); saida = Path(sys.argv[2])
itens = [("c12_v2_antes.png", "C12, volta 2 de 21/10 (frase do coach): antes"),
         ("c12_v2_depois_420x480.png", "C12, volta 2: depois (numeros da voz, trecho da fala, visuais)"),
         ("c01_v17_420x480.png", "C01, volta 17 (2a analise de 21/10)"),
         ("c10_v16_420x480.png", "C10, volta 16 (2a analise de 21/10)"),
         ("c12_v2_300x300.png", "janela 300 x 300: a velocidade sai"),
         ("c12_v2_420x300.png", "janela 420 x 300 (a de abertura)"),
         ("c01_v17_boxes_672x480.png", "boxes: 672 x 480 (1,6 x 420 x 300), com a grade"),
         ("c01_v17_boxes_480x480.png", "boxes: 480 x 480 (1,6 x 300 x 300), com a grade")]
fonte = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
imgs = [(Image.open(W / n), t) for n, t in itens]
col = 2; larg = max(i.width for i, _ in imgs) + 20
linhas = [imgs[k:k + col] for k in range(0, len(imgs), col)]
alturas = [max(i.height for i, _ in l) + 34 for l in linhas]
folha = Image.new("RGB", (larg * col + 10, sum(alturas) + 10), (40, 43, 47))
d = ImageDraw.Draw(folha); y = 10
for l, h in zip(linhas, alturas):
    for k, (i, t) in enumerate(l):
        x = 10 + k * larg
        d.text((x, y), t, fill=(235, 238, 242), font=fonte)
        folha.paste(i, (x, y + 24))
    y += h
folha.save(saida)
print(saida, folha.size)
