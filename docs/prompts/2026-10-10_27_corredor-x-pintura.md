# Pedido 27 — Conferir o corredor do modelo contra a faixa de limite pintada e contra o sinal de pneus fora do jogo

**De:** Eduardo. **Data:** 10/10/2026.
**Tipo:** medição e relatório. Nada muda: geometria, corredor, modelos, caches e coach ficam como estão. A decisão sobre o que fazer com o resultado é minha.

**Quando começar:** só depois do merge da branch `etapa/anotacao-sessoes-08-10-e-10-10` em `develop` (ADR 0008).

## Contexto

1. **O corredor do modelo** é a faixa lateral que uma trajetória pode ocupar em cada ponto da grade. Ele vem de `load_geometry` (`backend/ml/track/geometry.py`): linha central oficial ± `width_left`/`width_right`. As larguras são medidas contra `boundsLeft`/`boundsRight` do cache `data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json`. O corredor útil (`TrackGeometry.corridor`) é a largura menos `CAR_HALF_WIDTH_M` (1,0 m) mais `KERB_ALLOWANCE_M` (0,5 m), dos dois lados.
2. **Onde ele é usado, pelo que vi no código** (confira e complete a lista):
   - `clip_to_corridor` e `corridor_violation` (`backend/ml/track/trajectory.py`): algoritmo evolutivo e linha de referência da LSTM (`backend/ml/models/reference_line.py`);
   - `_outside_corridor_fraction` (`backend/ml/preprocessing/quality.py`): portão de qualidade das voltas;
   - `distance_to_left_edge`/`distance_to_right_edge` (`backend/ml/features/engineering.py` e `backend/ml/optimization/surrogate.py`): atributos de entrada;
   - `backend/ml/optimization/fitness.py`, `backend/ml/validation/search.py` e `backend/ml/scripts/alinhar_fastf1.py`.
3. **O mapa do app não desenha esse corredor.** Ele desenha só as camadas do jogo (`drawTrackSurface` em `frontend/src/components/map/OverlayRenderer.tsx`): `asphaltSurface.loops`, `markingGeometry.features` (classes `limite`, `boxes` e `servico`) e `kerbGeometry.polygons`. O comentário da função explica que o corredor "disagreed with the circuit" quando era desenhado.
4. **O que medi no Cowork em 10/10, para você conferir** (não são resultados definitivos):
   - **distância da borda do corredor até a faixa `limite` mais próxima,** sem as faixas transversais (item 5):
     - lado esquerdo: mediana de 0,10 m, mais de 1 m em 14,9% dos pontos;
     - lado direito: mediana de 0,19 m, mais de 1 m em 35,9% dos pontos, com máximo de 17,3 m entre 4006 e 4036 m;
   - **`boundsLeft`/`boundsRight` do cache têm o mesmo padrão** (15,3% e 34,7%). Então a diferença vem da reconstrução do cache, e não de `load_geometry`;
   - **trechos do lado direito com mais de 1 m:** 172–292, 408–804, 1180–1398 e 2904–3130 m, entre outros;
   - **degraus na largura de até 0,8 m** entre amostras vizinhas da grade (por exemplo, em 280, 370 e 3890 m);
   - **nas 29 voltas do protótipo** (31.436 pontos), 99,2% dos pontos caem sobre asfalto, zebra ou pintura. Os 0,8% restantes (237 pontos) ficam até 2,4 m fora; 141 deles estão entre 1400 e 1750 m.

   Um lado a mais de 1 m da pintura pode estar certo, onde aquele lado não tem faixa pintada e o limite é a borda do asfalto ou da zebra. Também pode ser o corredor deixando a trajetória sair da pista. É isso que este pedido precisa separar.
5. **Detalhes das camadas do cache que já conferi:**
   - as camadas estão em coordenadas de mapa (x, y), com **z = −y**. Com essa conversão, 100% da linha central oficial cai dentro do asfalto; com z = y, só 62%;
   - `boundsLeft`, `boundsRight` e `centerline` estão em (x, z) do mundo;
   - a superfície de asfalto vem sem as faixas de pintura e de zebra (`build_drawn_asphalt`). Então "sobre a pista" é a união de asfalto, zebra e pintura;
   - há **faixas transversais** da classe `limite`: retângulos fechados de 5 pontos que cruzam a linha central em cerca de 2, 384, 740, 946, 3396, 3882, 4172, 4270 e 4300 m (linha de largada e outras linhas pintadas). Elas precisam ficar fora da medição da borda.

## Parte A — Conferências antes de medir

Pare e registre no relatório se alguma destas não bater:

1. O `geometry_id` em uso é `0ed16f0dd2225990`, com 2167 pontos.
2. A conversão z = −y põe a linha central oficial dentro do asfalto em pelo menos 99% dos pontos.
3. A lista de usos do corredor do item 2 do contexto. Acrescente o que faltar e diga, para cada uso, se ele limita a trajetória (clip ou penalidade) ou só a descreve (atributo ou relatório).

## Parte B — Borda do corredor × pista desenhada

Para cada um dos 2167 pontos da grade, de cada lado, ao longo da normal da linha central oficial, meça:

1. **a borda do corredor** (`width_left`, `width_right`) e a borda do corredor útil;
2. **a distância até a faixa `limite`,** sem as transversais. Se não houver faixa a menos de 30 m, registre "sem faixa";
3. **a distância até a borda do asfalto** e se há zebra entre a faixa e a borda do asfalto.

Classifique cada ponto e cada lado em:

- **coincide:** o corredor fica a até 0,5 m da faixa;
- **mais largo, com pista:** o corredor passa da faixa, mas ainda sobre asfalto ou zebra;
- **mais largo, fora da pista:** o corredor passa da faixa e chega aonde não há asfalto nem zebra;
- **mais estreito:** o corredor fica antes da faixa;
- **sem faixa:** compare com a borda do asfalto e da zebra.

Relate a porcentagem da volta em cada classe, de cada lado, e a lista de trechos (início e fim em metros e o maior desvio). O lado vai por extenso, como manda o ADR 0003, por exemplo "1,2 m para a direita".

## Parte C — Conferência com o sinal do próprio jogo

O jogo diz quando o carro passa do limite: `tyres_out` (pneus fora) e, onde houver, `off_track`.

1. **Diga em quais gravações esses canais existem** (pasta, sessões e voltas). Se nenhuma tiver, registre e pule esta parte.
2. **Nas voltas que têm o canal** (`humano` e `ia`), cruze, ponto a ponto, a posição do centro do carro (`lateral`) com o corredor útil:
   - **dentro do corredor útil e com `tyres_out` ≥ 2:** o corredor está largo demais ali;
   - **fora do corredor útil e com `tyres_out` < 2:** o corredor está estreito demais ali.
3. **Relate por trecho,** junto com a classe da Parte B do mesmo trecho.

## Parte D — Efeito nas trajetórias que o sistema já produziu

Sem retreinar e sem rodar o otimizador de novo:

1. **Liste as trajetórias gravadas que achar e onde estão.** Por exemplo: a referência da LSTM, o melhor indivíduo do algoritmo evolutivo e as referências do coach (`volta_ia` e `minha_melhor`).
2. **Para cada uma, nos trechos das classes "mais largo, fora da pista" e "mais estreito":**
   - quantos pontos ficam encostados na borda do corredor útil, a até 0,1 m;
   - quantos passariam da faixa pintada mais a folga de zebra.

## Parte E — Figuras e resumo

1. **Uma figura com os trechos de maior desvio,** no máximo 8 quadros. Em cada quadro: asfalto, zebras, faixas, a borda do corredor e as voltas da IA e minhas. Grave em `docs/handoff/2026-10-10_27_corredor-x-pintura_figura.png`.
2. **Resumo em JSON** em `docs/handoff/2026-10-10_27_corredor-x-pintura_resumo.json`, com as classes por ponto e a lista de trechos.
3. **O script da medição fica versionado,** por exemplo `backend/ml/scripts/conferir_corredor.py`, para repetir depois.

## Parte F — Opções, sem implementar

Descreva, sem implementar, as opções para o corredor, com o que cada uma mudaria:

1. manter como está;
2. corredor a partir da faixa `limite`, mais a folga de zebra, e da borda do asfalto onde não houver faixa;
3. outra que os dados sugerirem.

Para cada uma, diga se ela muda o `geometry_id`, e então quais caches, modelos e referências precisariam ser refeitos, e se pede um ADR. Eu escolho.

## Testes

Os testes são sintéticos, com uma pista falsa pequena:

- a conversão das camadas (x, y) para o mundo (x, z = −y);
- a interseção da normal com a faixa, de cada lado, incluindo "sem faixa";
- a exclusão das faixas transversais;
- cada classe da Parte B.

A suíte `backend/tests` continua passando.

## Regras gerais

- **Nada muda além do script, dos testes e das saídas do relatório:** geometria, corredor, `config`, modelos, caches, coach e store ficam como estão. O `geometry_id` não muda.
- **O cache da pista e as gravações são só lidos.**
- **Não mexa no app instalado nem em arquivos do jogo.**
- **Não instale nem atualize pacotes.**
- **Não contorne nenhuma trava:** se algo parar, pare também e registre o motivo.
- **Não invente resultados:** onde não der para medir, diga que não deu.
- **Branch e commits:** branch `etapa/corredor-x-pintura`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-10_27_corredor-x-pintura_relatorio.md`, como manda o CLAUDE.md, com:
  - as conferências da Parte A e a lista completa de usos do corredor;
  - as tabelas das Partes B, C e D;
  - a figura e o resumo;
  - as opções da Parte F;
  - a saída da suíte de testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
