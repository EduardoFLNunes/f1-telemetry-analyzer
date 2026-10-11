# Relatório do pedido 27: corredor do modelo × faixa de limite pintada × sinal de pneus fora do jogo

- **Pedido:** `docs/prompts/2026-10-10_27_corredor-x-pintura.md`
- **Branch:** `etapa/corredor-x-pintura`, com merge em `develop`
- **Commits e merge:**
  - `d697042b` docs: pedido 27 (corredor do modelo x faixa pintada x pneus fora); conferencias da Parte A no relatorio.
    - O commit só tem o arquivo do pedido. Apesar da mensagem, as conferências da Parte A estão neste relatório.
  - `f2155279` ML: script que confere o corredor contra a faixa pintada, o sinal de pneus fora e as trajetorias (pedido 27, Partes B a E)
  - `cdd6864b` ML: perfil do sinal de pneus fora e as opcoes de corredor contra ele (pedido 27, Parte F, so medicao)
  - `6e5bb02f` ML: a conferencia lista as sessoes gravadas com tyresOut e offTrack, com a pasta e as voltas (pedido 27, Parte C.1)
  - `e52670fd` Merge etapa/corredor-x-pintura (pedido 27: corredor do modelo x faixa pintada x pneus fora)
  - o commit deste relatório, com as saídas e a suíte: "Relatório do pedido 27: corredor do modelo x faixa pintada x pneus fora"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-10_27_corredor-x-pintura_relatorio.md` (este)
  - `docs/handoff/2026-10-10_27_corredor-x-pintura_figura.png` (8 quadros; sha256 `8d612677…d83a63`)
  - `docs/handoff/2026-10-10_27_corredor-x-pintura_resumo.json` (gerado no commit `6e5bb02f`; sha256 `ba84d5a7…158940`)
  - `docs/handoff/2026-10-10_27_corredor-x-pintura.patch` (de `626c47c7` até o merge; sha256 `22eba1e2…243cc2`)
  - `docs/handoff/2026-10-10_27_corredor-x-pintura_testes.txt` (suíte `backend/tests`: 685 passando)

**Comando da medição** (de `backend/`, cerca de 2 min 20 s):

```bash
../.venv/Scripts/python.exe -m ml.scripts.conferir_corredor
```

As saídas originais ficam em `data/ml/corredor/` (`resumo.json`, `corredor_por_ponto.csv`, `corredor_x_pintura.png`), fora do git. A figura e o resumo foram copiados para `docs/handoff/`.

**O que não mudou:**
- Nada foi enviado ao remoto.
- Geometria, corredor, `config`, modelos, caches, coach e store ficaram como estavam, e o `geometry_id` continua `0ed16f0dd2225990`.
- O cache da pista e as gravações foram só lidos, inclusive os da pasta de gravações do app instalado. Lá ficam 4 das 7 sessões das voltas da Parte C. Para achar o canal, o script também leu o começo do fluxo de todas as 136 sessões. Nada foi gravado nessa pasta.
- Não instalei nem atualizei pacotes.

## Em resumo

1. **As conferências da Parte A bateram.**
   - A geometria é `0ed16f0dd2225990`, com 2167 pontos.
   - Com z = −y, 100% da linha central fica sobre o asfalto. Com z = y, só 10,75%.
   - Na lista de usos, uma correção: `_outside_corridor_fraction` não é um portão. É só uma métrica do relatório da volta, e nenhum critério de aceitação a usa.
2. **Parte B: onde o corredor diverge da pintura, ele é mais largo do que ela.**

   | lado | coincide | mais largo, com pista | mais largo, fora da pista | mais estreito | sem faixa |
   |---|---|---|---|---|---|
   | esquerda | 77,5% | 10,2% | 10,3% | 1,9% | 0% |
   | direita | 52,9% | 23,5% | 22,8% | 0% | 0,8% |

   - "Mais estreito" só aparece à esquerda, em dois trechos.
   - "Sem faixa" é um único trecho, de 4004 a 4040 m à direita. É o máximo de 17,3 m que o Cowork mediu.
   - A medida do Cowork se repete: medianas de 0,08 e 0,19 m, e mais de 1 m em 14,9% e 35,9% dos pontos.
3. **Parte C: o jogo é muito mais permissivo que o corredor e a pintura.**
   - O canal `tyresOut` existe em 26 das 136 sessões. Nas 58 voltas `humano` e `ia`, o sinal de pneus fora (`tyres_out` ≥ 2) aparece em só 0,4% das amostras.
   - **Corredor estreito demais:** 15.338 amostras, quase 30 vezes mais que as 548 de largo demais. É o carro fora do corredor útil sem que o jogo marque pneus fora. Em 85% a 94% dessas amostras, o trecho é da classe "coincide".
   - **Perfil do sinal:** com o centro do carro de 0 a 0,75 m além da faixa pintada, o jogo marca pneus fora em menos de 1% das amostras à esquerda e em até 8% à direita. Em nenhuma distância até 3 m além da faixa isso chega a 50%.
   - Conclusão: **o limite do jogo não é a faixa pintada.**
4. **Parte D: as trajetórias gravadas quase não usam o excesso.**
   - Nos 717 pontos "mais largo, fora da pista", ficam além da faixa mais a folga de zebra:
     - `volta_ia` do coach: 48;
     - `minha_melhor`: 24;
     - melhor indivíduo do algoritmo evolutivo: 52. Ele foi gravado antes da regravação do cache e não registra a geometria;
     - referência da F1: 8.
   - A referência da LSTM não está gravada em lugar nenhum.
5. **Parte F, medida contra o sinal do jogo:**
   - **corredor pela faixa (opção 2):** dobra o "estreito demais" (32.063 amostras) e zera quase todo o "largo demais" (9);
   - **corredor pela borda da superfície do cache, com asfalto, zebra e pintura (opção 3):** é a que mais se aproxima do jogo (6.764 e 411);
   - em qualquer das duas, mudar as bordas no cache muda o `geometry_id`.

   A decisão é sua.

## Parte A: conferências antes de medir

| conferência | o que achei | bate? |
|---|---|---|
| 1. `geometry_id` e pontos | `0ed16f0dd2225990`, 2167 pontos, passo de 2,0 m, volta de 4334,08 m. O script para se não for essa geometria. | sim |
| 2. z = −y põe a linha central dentro do asfalto em ≥ 99% | **100%** dos 2167 pontos com z = −y e 10,75% com z = y, com o asfalto lido como no cache: laços `external` e buracos `internal_hole`, por par-ímpar. Com asfalto, zebra e pintura juntos, também 100%. | sim |
| 3. lista de usos do corredor | completa abaixo, com uma correção: o portão de qualidade não usa o corredor | sim, com a correção |

Sobre o item 2: os 62% do Cowork com z = y vêm de ler os buracos como polígonos de fora. Do mesmo jeito, achei 61,8%. Com os buracos tratados como buracos, z = y dá 10,75%.

**Faixas transversais** da classe `limite`, que cruzam a linha central e ficam fora da medição:
- são 9 retângulos fechados de 5 pontos, em 3, 384, 740, 946, 3396, 3883, 4173, 4271 e 4301 m;
- os cruzamentos batem com os do Cowork;
- sobram 21 linhas `limite` laterais.

Uma faixa só conta se estiver até 1 m além da borda da superfície. Mais longe, ela é de outro trecho da pista. Nenhum ponto foi descartado por essa regra.

### Usos do corredor, conferidos no código

O corredor útil é `TrackGeometry.corridor()` (`backend/ml/track/geometry.py:129`): largura − (`CAR_HALF_WIDTH_M` − `KERB_ALLOWANCE_M`), ou seja, largura − 0,5 m.

| onde | o que faz | limita ou descreve |
|---|---|---|
| `ml/track/trajectory.py:100` `clip_to_corridor` | corta a lateral ao corredor útil | **limita** |
| `ml/optimization/representation.py:75`, `:79` e `:144` | algoritmo evolutivo: todo genoma decodificado passa pelo `clip_to_corridor`, e os limites de cada gene saem do corredor da vizinhança | **limita** |
| `ml/optimization/seed.py:89` | semente do evolutivo, cortada ao corredor | **limita** |
| `ml/models/reference_line.py:154` | linha de referência da LSTM, cortada ao corredor | **limita** |
| `ml/track/trajectory.py:88` `corridor_violation` → `ml/optimization/fitness.py:192` | penalidade `corridor` na aptidão do evolutivo | **limita** (penalidade) |
| `ml/validation/search.py` | busca de validação: usa o `FitnessEvaluator` e o `TrajectoryEncoding`, e herda o clip e a penalidade | **limita** (indireto) |
| `ml/external/f1_line.py:422` e `:427` (`excess_on_grid`, `excess_at_samples`) → `verdict` (`:465`), `ml/external/f1_band.py:99` (`lap_verdict`), `ml/scripts/alinhar_fastf1.py:213` | o excesso sobre o corredor é o critério que aceita ou não o alinhamento da F1 e cada volta da faixa. A linha não é cortada. | **limita** (critério de aceitação) |
| `ml/preprocessing/quality.py:63` `_outside_corridor_fraction` | vira a métrica `outside_corridor_fraction` (`:127`). O portão de fora de pista usa `off_track`, ou `tyres_out` ≥ 2 quando `off_track` falta (`:53` e `:164`). | **descreve** (o pedido o listava como portão) |
| `ml/features/engineering.py:134`, `ml/models/sequences.py:42`, `ml/optimization/surrogate.py:71` | `distance_to_left_edge` e `distance_to_right_edge` (largura ∓ lateral), atributos da LSTM e do substituto | **descreve** (atributo de entrada; muda o que o modelo prevê, mas não limita) |
| `ml/preprocessing/resampling.py:161` | copia `width_left` e `width_right` para a volta reamostrada | **descreve** |
| `ml/visualization/track_plots.py:25`, `telemetry_plots.py:74`, `comparison_plots.py:239` | desenham as bordas | **descreve** |
| `ml/scripts/alinhar_fastf1.py:111`, `:126` e `:236`; `referencia_f1.py:70`; `faixa_f1_secas.py:143` e `:184` | figuras e tabela por ponto da grade | **descreve** |
| `ml/scripts/conferir_corredor.py` (este pedido) | medição | **descreve** |

Fora do corredor do ML, mas da mesma fonte (`boundsLeft` e `boundsRight` do cache, sem passar por `load_geometry`):
- **no backend:** `routers/legacy.py:97`, `/api/data/track-limits`;
- **no front:** o `left_edge` e o `right_edge` só enquadram o mapa e a câmera (`TrackRenderer.tsx`, `CameraController.tsx`) e montam a fita de elevação (`TrackElevationRibbon.tsx`). Todos esses usos descrevem.
  - Em `OverlayRenderer.tsx`, `getTrackSurfaceCache` está definida e não é chamada.
  - O comentário de `drawTrackSurface` diz que o relevo (`buildReliefCache`) é ignorado.
  - O mapa não desenha o corredor, como o pedido dizia.

As bordas são construídas em `core/geometry/` (`limit_corridor.py`, `paint_edge_correction.py`, `width_continuity.py`). Esse é o lado que produz o corredor, não o que o usa.

**O coach não usa o corredor.** O export da geometria oficial (`ml/export/geometry.py`) não leva as larguras, e o coach só confere o `geometry_id`.

## Parte B: borda do corredor × pista desenhada

**Como medi.** Em cada um dos 2167 pontos, de cada lado, um raio sai da linha central oficial ao longo da normal, com passo de 0,05 m e até 30 m. Ele mede:
- a primeira faixa `limite` lateral, sem as transversais;
- a borda da superfície, que junta asfalto, zebra e pintura;
- a borda do asfalto, que junta asfalto e pintura, sem a zebra.

Cada borda é o primeiro trecho de ao menos 0,3 m fora da camada. Menos que isso é emenda entre polígonos.

O desvio é o corredor menos a faixa (+ = corredor mais largo). Sem faixa, é o corredor menos a borda da superfície.

### Porcentagem da volta em cada classe

| lado | coincide (até 0,5 m) | mais largo, com pista | mais largo, fora da pista | mais estreito | sem faixa |
|---|---|---|---|---|---|
| esquerda | 77,48% (1679 pontos) | 10,24% (222) | 10,34% (224) | 1,94% (42) | 0% |
| direita | 52,88% (1146) | 23,53% (510) | 22,75% (493) | 0% | 0,83% (18), todos "antes da borda" |

**Faixa, zebra e borda.** As medidas abaixo são lidas da tabela `por_ponto` do resumo.

| lado | pontos com faixa | zebra entre a faixa e a borda | borda da superfície além da faixa (mediana; p90) | borda do asfalto além da faixa (mediana) |
|---|---|---|---|---|
| esquerda | 2167 | 35,9% | 1,90 m; 5,58 m | 0,57 m |
| direita | 2149 | 27,8% | 0,61 m; 3,26 m | 0,48 m |

**O metadado do cache ajuda a explicar** (`metadata.builtFromLimits`):
- das 2680 amostras de borda de cada lado, vieram da pintura 1196 à esquerda e 887 à direita; da zebra, 1051 e 1011; e foram **estimadas** 433 (16%) e 782 (29%);
- a largura média passou de 12,39 m para 13,92 m na construção pelos limites;
- depois, `paintEdgeCorrection` corrigiu 39,6% das amostras e levou a média a 14,33 m.

O lado direito tem mais amostras estimadas e também mais pontos "mais largo". Essa relação é só no total: o cache não diz de onde veio cada amostra, então não dá para ligar ponto a ponto.

### Trechos de 10 m ou mais fora da classe "coincide"

A lista completa, com todos os 170 trechos e todos os comprimentos, está em `parte_b.trechos` do resumo.

**Lado esquerdo**

| classe | trecho (m) | comprimento (m) | maior desvio |
|---|---|---|---|
| mais largo, com pista | 338 a 354 | 16 | 2,52 m além da faixa, para a esquerda |
| mais largo, fora da pista | 354 a 382 | 28 | 4,30 m além da faixa, para a esquerda |
| mais largo, com pista | 404 a 422 | 18 | 0,81 m além da faixa, para a esquerda |
| mais largo, com pista | 448 a 474 | 26 | 1,15 m além da faixa, para a esquerda |
| mais estreito | 488 a 500 | 12 | 1,06 m antes da faixa, do lado esquerdo |
| mais largo, fora da pista | 744 a 770 | 26 | 2,60 m além da faixa, para a esquerda |
| mais largo, com pista | 770 a 782 | 12 | 2,25 m além da faixa, para a esquerda |
| mais estreito | 948 a 1.014 | 66 | 3,73 m antes da faixa, do lado esquerdo |
| mais largo, com pista | 1.320 a 1.330 | 10 | 0,59 m além da faixa, para a esquerda |
| mais largo, com pista | 1.390 a 1.408 | 18 | 0,68 m além da faixa, para a esquerda |
| mais largo, fora da pista | 1.786 a 1.828 | 42 | 2,93 m além da faixa, para a esquerda |
| mais largo, fora da pista | 1.842 a 1.876 | 34 | 3,28 m além da faixa, para a esquerda |
| mais largo, fora da pista | 1.878 a 1.992 | 114 | 5,30 m além da faixa, para a esquerda |
| mais largo, com pista | 1.992 a 2.002 | 10 | 2,35 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.092 a 2.110 | 18 | 3,49 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.112 a 2.140 | 28 | 4,51 m além da faixa, para a esquerda |
| mais largo, com pista | 2.140 a 2.150 | 10 | 2,76 m além da faixa, para a esquerda |
| mais largo, com pista | 2.252 a 2.274 | 22 | 0,78 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.698 a 2.712 | 14 | 1,91 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.716 a 2.768 | 52 | 4,68 m além da faixa, para a esquerda |
| mais largo, com pista | 2.768 a 2.788 | 20 | 2,57 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.788 a 2.798 | 10 | 2,35 m além da faixa, para a esquerda |
| mais largo, fora da pista | 2.812 a 2.848 | 36 | 3,95 m além da faixa, para a esquerda |
| mais largo, com pista | 3.018 a 3.080 | 62 | 2,19 m além da faixa, para a esquerda |
| mais largo, fora da pista | 3.080 a 3.092 | 12 | 2,13 m além da faixa, para a esquerda |
| mais largo, com pista | 3.190 a 3.208 | 18 | 0,74 m além da faixa, para a esquerda |
| mais largo, com pista | 3.308 a 3.354 | 46 | 1,88 m além da faixa, para a esquerda |
| mais largo, com pista | 3.470 a 3.482 | 12 | 1,23 m além da faixa, para a esquerda |
| mais largo, fora da pista | 3.490 a 3.500 | 10 | 1,35 m além da faixa, para a esquerda |
| mais largo, com pista | 3.506 a 3.538 | 32 | 2,83 m além da faixa, para a esquerda |
| mais largo, fora da pista | 3.538 a 3.548 | 10 | 2,06 m além da faixa, para a esquerda |
| mais largo, com pista | 3.884 a 3.936 | 52 | 6,43 m além da faixa, para a esquerda |

**Lado direito**

| classe | trecho (m) | comprimento (m) | maior desvio |
|---|---|---|---|
| mais largo, com pista | 166 a 288 | 122 | 5,49 m além da faixa, para a direita |
| mais largo, fora da pista | 288 a 298 | 10 | 3,31 m além da faixa, para a direita |
| mais largo, fora da pista | 310 a 320 | 10 | 2,48 m além da faixa, para a direita |
| mais largo, fora da pista | 334 a 344 | 10 | 2,12 m além da faixa, para a direita |
| mais largo, com pista | 344 a 356 | 12 | 1,90 m além da faixa, para a direita |
| mais largo, com pista | 362 a 372 | 10 | 0,60 m além da faixa, para a direita |
| mais largo, com pista | 404 a 422 | 18 | 3,20 m além da faixa, para a direita |
| mais largo, fora da pista | 422 a 476 | 54 | 4,18 m além da faixa, para a direita |
| mais largo, fora da pista | 478 a 582 | 104 | 4,73 m além da faixa, para a direita |
| mais largo, com pista | 582 a 596 | 14 | 2,71 m além da faixa, para a direita |
| mais largo, fora da pista | 596 a 732 | 136 | 4,51 m além da faixa, para a direita |
| mais largo, com pista | 732 a 810 | 78 | 3,33 m além da faixa, para a direita |
| mais largo, fora da pista | 830 a 842 | 12 | 2,01 m além da faixa, para a direita |
| mais largo, com pista | 842 a 852 | 10 | 2,58 m além da faixa, para a direita |
| mais largo, fora da pista | 852 a 862 | 10 | 1,82 m além da faixa, para a direita |
| mais largo, fora da pista | 878 a 896 | 18 | 1,44 m além da faixa, para a direita |
| mais largo, com pista | 896 a 906 | 10 | 2,25 m além da faixa, para a direita |
| mais largo, fora da pista | 906 a 932 | 26 | 2,45 m além da faixa, para a direita |
| mais largo, fora da pista | 934 a 978 | 44 | 3,47 m além da faixa, para a direita |
| mais largo, com pista | 978 a 1.020 | 42 | 0,92 m além da faixa, para a direita |
| mais largo, fora da pista | 1.020 a 1.044 | 24 | 1,62 m além da faixa, para a direita |
| mais largo, com pista | 1.062 a 1.074 | 12 | 1,02 m além da faixa, para a direita |
| mais largo, fora da pista | 1.074 a 1.096 | 22 | 1,59 m além da faixa, para a direita |
| mais largo, fora da pista | 1.132 a 1.156 | 24 | 1,62 m além da faixa, para a direita |
| mais largo, fora da pista | 1.178 a 1.382 | 204 | 5,09 m além da faixa, para a direita |
| mais largo, fora da pista | 1.390 a 1.416 | 26 | 2,69 m além da faixa, para a direita |
| mais largo, fora da pista | 1.628 a 1.708 | 80 | 0,79 m além da faixa, para a direita |
| mais largo, com pista | 2.254 a 2.276 | 22 | 0,67 m além da faixa, para a direita |
| mais largo, fora da pista | 2.494 a 2.528 | 34 | 2,97 m além da faixa, para a direita |
| mais largo, com pista | 2.528 a 2.538 | 10 | 2,29 m além da faixa, para a direita |
| mais largo, com pista | 2.596 a 2.622 | 26 | 1,91 m além da faixa, para a direita |
| mais largo, com pista | 2.678 a 2.706 | 28 | 0,70 m além da faixa, para a direita |
| mais largo, com pista | 2.748 a 2.762 | 14 | 0,66 m além da faixa, para a direita |
| mais largo, fora da pista | 2.770 a 2.786 | 16 | 1,77 m além da faixa, para a direita |
| mais largo, com pista | 2.786 a 2.802 | 16 | 2,85 m além da faixa, para a direita |
| mais largo, fora da pista | 2.802 a 2.814 | 12 | 2,32 m além da faixa, para a direita |
| mais largo, fora da pista | 2.898 a 2.912 | 14 | 2,11 m além da faixa, para a direita |
| mais largo, com pista | 2.912 a 3.062 | 150 | 4,17 m além da faixa, para a direita |
| mais largo, com pista | 3.072 a 3.084 | 12 | 3,14 m além da faixa, para a direita |
| mais largo, com pista | 3.086 a 3.136 | 50 | 4,76 m além da faixa, para a direita |
| mais largo, fora da pista | 3.188 a 3.208 | 20 | 0,69 m além da faixa, para a direita |
| mais largo, com pista | 3.276 a 3.290 | 14 | 2,17 m além da faixa, para a direita |
| mais largo, fora da pista | 3.290 a 3.348 | 58 | 3,46 m além da faixa, para a direita |
| mais largo, com pista | 3.878 a 3.912 | 34 | 3,22 m além da faixa, para a direita |
| sem faixa (antes da borda) | 4.004 a 4.040 | 36 | 2,37 m antes da borda, do lado direito |
| mais largo, com pista | 4.072 a 4.334 | 262 | 1,64 m além da faixa, para a direita |

### O que confere com o que o Cowork mediu

- **Distância da borda do corredor até a faixa mais próxima,** em qualquer direção, que é a medida do Cowork:
  - esquerda: mediana de 0,08 m, mais de 1 m em 14,86% dos pontos, máximo de 5,06 m em 1886 m;
  - direita: mediana de 0,19 m, mais de 1 m em 35,95%, máximo de **17,12 m em 4022 m**.

  Bate com o Cowork.
- **O máximo da direita é um vão na pintura.** De 4004 a 4040 m, nenhuma faixa `limite` cruza a normal até 30 m. A superfície vai até 12,15 m (em 4022 m), e o corredor fica em 9,86 m, 2,29 m antes da borda. A faixa mais próxima, a 17 m, está em outra direção.
- **Os trechos do Cowork com mais de 1 m à direita** são os mesmos que aparecem aqui como "mais largo":

  | Cowork | aqui |
  |---|---|
  | 172–292 | 166–288 |
  | 408–804 | 404–810, em sete trechos |
  | 1180–1398 | 1178–1382 e 1390–1416 |
  | 2904–3130 | 2912–3062, 3072–3084 e 3086–3136 |
- **Degraus na largura,** lidos de `por_ponto`:
  - o maior entre pontos vizinhos é de **0,81 m** à direita, em 290 m. À esquerda, é de 0,65 m em 382 m e de 0,57 m em 3894 m. Isso confere com os degraus do Cowork em 280, 370 e 3890 m;
  - **há um degrau de 1,64 m no fechamento do laço,** à direita, entre o último ponto (4332 m) e o primeiro (0 m). O Cowork não citou esse;
  - há 84 degraus acima de 0,3 m à esquerda e 107 à direita.
- **As 29 voltas do protótipo** (99,2% sobre a pista) não foram refeitas: eu não tenho esse conjunto. A Parte C mede a mesma ideia com o sinal do jogo.
- **O "mais estreito" de 948 a 1014 m à esquerda:**
  - o corredor tem de 2,64 a 4,40 m;
  - a faixa está a 5,0 a 6,4 m e o asfalto vai até 5,4 a 6,9 m, sem zebra entre eles;
  - nesse trecho, o corredor tira até 3,73 m de asfalto.

## Parte C: conferência com o sinal do próprio jogo

### Onde o canal existe

O gravador grava `carPhysics.environment.tyresOut` e `offTrack` a partir da sessão `2026-08-09_17-06-41`. São **26 das 136 sessões** de Interlagos, nas duas pastas, e todas têm os dois campos. O script procura as duas chaves no começo do fluxo de cada sessão, e a lista está em `parte_c.onde_o_canal_existe`:

| pasta | sessões com o canal |
|---|---|
| `data/recordings` (repositório) | 12: `2026-08-09_19-10-41`, `19-15-35`, `19-20-59`; `2026-08-16_03-30-14`, `03-58-36`; `2026-10-04_02-24-04`, `03-21-52`, `03-35-57`, `03-36-35`, `03-40-32`, `03-42-10`, `04-22-39` |
| `AppData\Roaming\Automobilista Telemetria\data\recordings` (app instalado, só lido) | 14: `2026-08-09_17-06-41`, `17-23-56`, `17-37-33`, `18-22-00`, `18-41-18`, `18-47-11`; `2026-08-19_20-57-37`, `20-58-36`, `21-45-59`, `22-23-14`; `2026-10-04_23-51-42`; `2026-10-05_20-33-47`; `2026-10-08_23-56-13`; `2026-10-10_09-57-09` |

**Voltas usadas:** todas as `humano` e `ia` do store v2, que são **58** (45 `humano` e 13 `ia`). Todas têm o canal, e nenhuma ficou de fora.
- Por sessão: `2026-10-04_02-24-04` tem 4 humano e 5 ia; `03-21-52`, 4 humano; `03-42-10`, 3 humano e 8 ia; `2026-10-04_23-51-42`, 7; `2026-10-05_20-33-47`, 11; `2026-10-08_23-56-13`, 4; e `2026-10-10_09-57-09`, 12.
- Nessas 26 sessões, o store v2 tem 189 voltas. Além das 58, há 129 `desconhecida`, todas das sessões de agosto, e 2 `misturada`, de 04/10. Elas também têm o canal, mas o pedido pede só `humano` e `ia`.
- Seis das sessões com o canal não têm volta no store v2: `2026-08-16_03-58-36`, `2026-08-19_20-57-37`, `2026-10-04_03-35-57`, `03-36-35`, `03-40-32` e `04-22-39`.

**Como cruzei:**
1. Cada volta passa pelo `clean_lap` e pelo `align_lap` na geometria oficial.
2. Cada amostra conta do lado em que o centro do carro está (`lateral` ≥ 0 é a esquerda) e é comparada com o corredor útil daquele ponto da grade.
3. "Pneus fora" é `tyres_out` ≥ 2, o mesmo critério de `quality.py`.

### Totais

| lado | amostras | pneus fora (≥ 2) | largo demais (dentro do útil, pneus fora) | estreito demais (fora do útil, sem pneus fora) |
|---|---|---|---|---|
| esquerda | 136.144 | 184 | 26 | 8.373 |
| direita | 167.489 | 1.092 | 522 | 6.965 |

**Quanto o carro passa ou fica dentro:**
- No "estreito demais", o centro do carro passa da borda útil por uma mediana de 0,46 m (esquerda) e 0,54 m (direita), com p90 de 1,50 e 2,87 m. Como a borda útil fica 0,5 m dentro do corredor, e o corredor coincide com a faixa na maior parte desses trechos, **o carro está com o centro sobre a faixa ou além dela, e o jogo não marca pneus fora**.
- No "largo demais" da direita, o carro está 2,79 m dentro da borda útil (mediana). É onde o corredor passa vários metros da faixa.

**Pela classe da Parte B** (somando as amostras dos trechos pela classe dominante de cada trecho):

| lado | situação | amostras | coincide | mais largo, com pista | mais largo, fora da pista |
|---|---|---|---|---|---|
| esquerda | estreito demais | 8.373 | 94% | 1% | 5% |
| direita | estreito demais | 6.965 | 85% | 4% | 11% |
| esquerda | largo demais | 26 | 54% | — | 46% |
| direita | largo demais | 522 | 12% | 65% | 23% |

### Perfil do sinal: onde o jogo passa a dizer "pneus fora"

As amostras estão agrupadas pela distância do centro do carro até cada referência, em faixas de 0,25 m (+ = além dela). As faixas são as do resumo, que vão de −1,5 a +3,0 m. Aqui aparecem as de −0,5 a +3,0 m.

| distância até a faixa pintada (m) | esquerda: amostras, % pneus fora | direita: amostras, % pneus fora |
|---|---|---|
| −0,50 a −0,25 | 4.113, 0,4% | 4.848, 2,6% |
| −0,25 a 0 | 3.783, 1,0% | 3.608, 5,4% |
| 0 a +0,25 | 2.614, 0,8% | 2.540, 4,7% |
| +0,25 a +0,50 | 2.300, 0,6% | 1.393, 7,8% |
| +0,50 a +0,75 | 1.678, 0,7% | 741, 7,3% |
| +0,75 a +1,00 | 697, 0% | 581, 10,0% |
| +1,00 a +1,25 | 411, 0% | 447, 7,2% |
| +1,25 a +1,50 | 224, 0% | 378, 8,7% |
| +1,50 a +1,75 | 121, 0% | 267, 15,4% |
| +1,75 a +2,00 | 105, 3,8% | 277, 11,2% |
| +2,00 a +2,25 | 88, 26,1% | 215, 3,7% |
| +2,25 a +2,50 | 65, 9,2% | 200, 6,5% |
| +2,50 a +2,75 | 82, 4,9% | 173, 4,6% |
| +2,75 a +3,00 | 31, 16,1% | 123, 6,5% |

**Contra a borda da superfície do cache:**
- **à direita,** o sinal fica entre 10% e 20% de −1,0 a +0,5 m e não passa de 13% além disso;
- **à esquerda,** até 1 m além da borda o sinal fica em até 8%, com 101 a 691 amostras por faixa. Ele passa de 50% de +1,0 a +1,75 m (64%, 63% e 56%), mas com só 11, 8 e 9 amostras.

Nenhuma das três referências tem uma faixa com ao menos 30 amostras em que a maioria já tem pneus fora (`limiar_50pct_m` vazio). As três são a faixa, a borda da superfície e a borda útil de hoje.

**O que isso diz:**
- **O limite do jogo não é a faixa pintada,** e na maior parte da volta também não é a borda da superfície desenhada no cache.
- Os poucos "largo demais" se concentram onde o corredor passa vários metros da faixa, por exemplo de 194 a 250 m à direita.
- Uma ressalva: o `lateral` vem do alinhamento, e um erro de alinhamento de alguns decímetros mexeria nas faixas de perto da borda. Não medi esse erro neste pedido.

### Trechos

Ao todo há 72 trechos:
- "estreito demais": 21 à esquerda e 26 à direita;
- "largo demais": 6 à esquerda e 19 à direita.

A tabela traz os de largo demais com ao menos 40 amostras e os de estreito demais com ao menos 200. A lista completa está em `parte_c.trechos`.

| lado | situação | trecho (m) | amostras | voltas | classe da Parte B |
|---|---|---|---|---|---|
| direita | largo demais | 194 a 250 | 249 | 4 | mais largo, com pista |
| direita | largo demais | 3.024 a 3.036 | 90 | 2 | mais largo, com pista |
| direita | largo demais | 2.494 a 2.520 | 61 | 4 | mais largo, fora da pista |
| direita | largo demais | 1.224 a 1.248 | 44 | 2 | mais largo, fora da pista |
| esquerda | estreito demais | 420 a 554 | 2.343 | 38 | coincide |
| direita | estreito demais | 0 a 166 | 1.599 | 28 | coincide |
| direita | estreito demais | 1.394 a 1.474 | 1.512 | 27 | coincide |
| esquerda | estreito demais | 2.858 a 2.994 | 1.235 | 27 | coincide |
| esquerda | estreito demais | 272 a 314 | 1.018 | 39 | coincide |
| esquerda | estreito demais | 2.320 a 2.412 | 814 | 12 | coincide |
| direita | estreito demais | 1.614 a 1.754 | 797 | 14 | mais largo, fora da pista |
| direita | estreito demais | 3.626 a 3.802 | 725 | 8 | coincide |
| esquerda | estreito demais | 776 a 948 | 598 | 7 | coincide |
| esquerda | estreito demais | 3.928 a 4.062 | 578 | 9 | coincide |
| esquerda | estreito demais | 1.816 a 1.856 | 443 | 28 | mais largo, fora da pista |
| direita | estreito demais | 370 a 402 | 438 | 21 | coincide |
| esquerda | estreito demais | 2.142 a 2.202 | 355 | 10 | coincide |
| direita | estreito demais | 2.262 a 2.328 | 325 | 11 | coincide |
| direita | estreito demais | 2.692 a 2.734 | 311 | 11 | coincide |
| direita | estreito demais | 2.028 a 2.126 | 278 | 8 | coincide |
| esquerda | estreito demais | 3.204 a 3.234 | 220 | 10 | coincide |
| direita | estreito demais | 3.134 a 3.174 | 220 | 18 | coincide |

O trecho de 1614 a 1754 m à direita (797 amostras) cai na região de 1400 a 1750 m. É onde o Cowork achou 141 dos 237 pontos fora da pista no protótipo.

## Parte D: efeito nas trajetórias já produzidas

Não retreinei nada nem rodei o otimizador.

**Trajetórias gravadas que achei:**

| trajetória | onde está | geometria |
|---|---|---|
| `volta_ia` do coach | `data/reference_models/vhe_interlagos.json` aponta `2026-10-04_03-42-10#0013`; a lateral vem do store v2 | `0ed16f0dd2225990` |
| `minha_melhor` do coach | `2026-10-04_02-24-04#0018`, do store v2 | `0ed16f0dd2225990` |
| melhor indivíduo do algoritmo evolutivo | `data/ml/optimization/optimised_lateral.npy`, de 24/08, com 2167 pontos | **não registrada.** Foi gravada antes da regravação do cache de 25/08, e o `result.json` não tem `geometry_id`. A comparação é aproximada. |
| referência da F1 2023-25 (ADR 0019) | `data/ml/externo/f1_referencia/referencia_2023_25.csv` | `0ed16f0dd2225990` |
| referência da LSTM | **não está gravada.** É calculada na hora por `reference_line.py`, a partir do modelo em `data/ml/models/reference/` (24/08, de antes da regravação do cache). Gerá-la seria rodar esse modelo numa geometria diferente da dele, e não rodei. | — |

**Contagens** nos pontos das classes pedidas, de cada lado:
- **encostados:** a até 0,1 m da borda do corredor útil;
- **além da faixa + folga:** o centro do carro além de faixa − 0,5 m, ou seja, a borda do carro mais de 0,5 m além da faixa.

| trajetória | classe | lado (pontos da classe) | encostados | além da faixa + folga |
|---|---|---|---|---|
| `volta_ia` | mais largo, fora da pista | esquerda (224) | 3 | 44 |
| | | direita (493) | 0 | 4 |
| | mais estreito | esquerda (42) | 0 | 6 |
| `minha_melhor` | mais largo, fora da pista | esquerda (224) | 0 | 0 |
| | | direita (493) | 11 | 24 |
| | mais estreito | esquerda (42) | 2 | 0 |
| evolutivo | mais largo, fora da pista | esquerda (224) | 0 | 39 |
| | | direita (493) | 0 | 13 |
| | mais estreito | esquerda (42) | 2 | 0 |
| F1 2023-25 | mais largo, fora da pista | esquerda (224) | 0 | 0 |
| | | direita (493) | 0 | 8 |
| | mais estreito | esquerda (42) | 0 | 0 |

À direita não há pontos "mais estreito".

**Leitura:**
- O excesso do corredor quase não aparece nas trajetórias gravadas.
- O evolutivo é limitado pelo corredor, mas não encosta na borda útil nos trechos "fora da pista". Mesmo assim, passa da faixa mais a folga em 39 pontos à esquerda e 13 à direita.
- A `volta_ia` passa da faixa mais a folga em 44 pontos à esquerda. É uma volta gravada no jogo, e a Parte C mostra que o jogo deixa passar da faixa. Não conferi o `tyres_out` dessa volta ponto a ponto.

## Parte E: figura e resumo

- **Figura:** `docs/handoff/2026-10-10_27_corredor-x-pintura_figura.png`.
  - São 8 quadros, os trechos de maior desvio sem repetir lugar, em 3854–3966, 136–318, 1848–2022, 1148–1412, 3056–3166, 448–612, 2686–2798 e 2082–2170 m.
  - Cada quadro mostra o asfalto (cinza), as zebras (vermelho), as faixas `limite` (preto), as bordas do corredor (laranja tracejado), as 13 voltas da IA (azul) e as suas voltas do equipamento atual (verde).
  - A pintura em área aparece só como contorno, porque o anel de limite fechado tem contorno de fora e de dentro e, preenchido, cobriria a pista.
- **Resumo:** `docs/handoff/2026-10-10_27_corredor-x-pintura_resumo.json`, com:
  - o commit (`cdd6864b`), a geometria e as regras;
  - as conferências;
  - `parte_b` (classes, os 170 trechos e o metadado do cache);
  - `parte_c` (voltas, totais, trechos e o perfil do sinal);
  - `parte_d`, `parte_f` e os quadros da figura;
  - `por_ponto`, com as classes e as medidas dos 2167 pontos dos dois lados.
- **Script:** `backend/ml/scripts/conferir_corredor.py`. A opção `--sem-voltas-cruas` pula a Parte C e roda em cerca de 16 s.

## Parte F: opções, sem implementar

As três opções usam a mesma regra de hoje para o corredor útil (largura − 0,5 m). Muda só a largura, e onde a referência da opção falta, fica a de hoje. Os números saem do `parte_f` do resumo.

| | 1. manter | 2. faixa `limite` (borda do asfalto onde não há faixa) | 3. borda da superfície do cache (asfalto, zebra e pintura) |
|---|---|---|---|
| borda útil × hoje, esquerda: mediana (p10; p90) | — | −0,32 m (−2,01; −0,02) | +1,49 m (−0,21; +4,55) |
| borda útil × hoje, direita | — | −0,42 m (−3,56; −0,25) | +0,24 m (−3,03; +2,54) |
| pontos mais de 0,5 m mais largos / mais estreitos (esq.; dir.) | — | 1,9% / 20,6%; 0,8% / 46,3% | 69,1% / 9,4%; 39,2% / 23,4% |
| pontos sem a referência da opção | — | 18 à direita usam a borda do asfalto (4004–4040 m); nenhum fica sem nada | 1 à esquerda |
| **contra o jogo:** largo demais (esq. + dir.) | 26 + 522 = **548** | 0 + 9 = **9** | 91 + 320 = **411** |
| **contra o jogo:** estreito demais (esq. + dir.) | 8.373 + 6.965 = **15.338** | 16.397 + 15.666 = **32.063** | 2.774 + 3.990 = **6.764** |

### 1. Manter como está

- **O que muda:** nada. O `geometry_id` fica, nada é refeito, e não precisa de ADR.
- **O que fica:**
  - o corredor passa da pintura em 20,6% da volta à esquerda e 46,3% à direita. Em 10,3% e 22,8%, ele chega aonde não há asfalto nem zebra;
  - o evolutivo e a linha da LSTM podem usar esses trechos, mas as trajetórias gravadas quase não usam (Parte D);
  - contra o jogo, o corredor é mais estreito que o limite real na maior parte das divergências.

### 2. Corredor pela faixa `limite`, mais a folga de zebra, e pela borda do asfalto onde não há faixa

- **O que muda:**
  - o corredor fica igual ao que a pintura declara;
  - fica mais estreito que hoje em quase metade da volta à direita;
  - acaba com o "largo demais" (de 548 para 9);
  - dobra o "estreito demais" (de 15.338 para 32.063). Ele proíbe o que o jogo deixa fazer, por exemplo o carro com o centro sobre a faixa e as rodas na zebra.
- **Serve se** a intenção for o limite do regulamento, o da linha branca, e não o do jogo. Para o coach e o evolutivo, isso tira traçado que as voltas reais usam.
- **`geometry_id`:** muda.
  - O caminho natural é reconstruir `boundsLeft` e `boundsRight` em `core/geometry/limit_corridor.py` e `paint_edge_correction.py`, e as bordas entram na impressão digital (`geometry_fingerprint`, `backend/ml/track/geometry.py:426`).
  - Se `load_geometry` passasse a ler as faixas sem mudar as bordas, a impressão digital teria de incluir a nova entrada. Sem isso, o id não diria que o corredor mudou, contra o ADR 0002.
- **O que precisaria ser refeito, se o id mudar:**
  - **inventário e tabelas de origem** (`data/ml/origem/`, com o cache de sessão) e **store v2** (`laps_grid_v2.parquet` e `cache_store_v2`). A chave global dos dois caches inclui o `geometry_id`, então é uma rodada completa do `atualizar_coach`, de cerca de 25 min. O store antigo (`laps_grid.parquet`) também, se ainda for usado;
  - **o export da geometria oficial e o modelo do coach** (`data/reference_models/vhe_interlagos.json`). O coach fica em silêncio se o id não bater (ADR 0013);
  - **a LSTM e o substituto** (`data/ml/models/`), porque os atributos `distance_to_*_edge` mudam, e **o evolutivo** (`data/ml/optimization/`), que hoje nem registra a geometria;
  - **as saídas da F1** (`data/ml/externo/f1_referencia/` e a faixa), porque o critério de aceitação usa o excesso sobre o corredor;
  - **os relatórios de evolução** (`data/ml/evolucao/`) e as validações (`data/ml/validation/`).
- **Uma observação que vale para as opções 2 e 3:**
  - o `s` e o `lateral` só dependem da linha central e das normais, e não das larguras. Store, coach e referência da F1 teriam os mesmos números, salvo as colunas que dependem do corredor;
  - é o id que força refazer tudo.
- **ADR:** sim.
  - A opção muda o que a largura da geometria oficial significa (ADR 0002).
  - Pelo ADR 0007, os resultados novos registram o id novo, e os artefatos substituídos são guardados antes.

### 3. Sugerida pelos dados: corredor pela borda da superfície do cache (asfalto, zebra e pintura)

- **O que muda:**
  - é a opção que mais se aproxima do sinal do jogo: o "estreito demais" cai de 15.338 para 6.764, e o "largo demais", de 548 para 411;
  - o corredor fica mais largo que hoje na maior parte da esquerda (mediana de +1,49 m) e mais estreito onde hoje ele passa da superfície. Esses são os trechos "mais largo, fora da pista": 9,4% da esquerda e 23,4% da direita ficam mais de 0,5 m mais estreitos.
- **O que não resolve:** mesmo com ela, o jogo deixa ir além da borda desenhada em muitos lugares (o perfil do sinal não passa de 50%). Uma variante seria tirar o corredor do próprio sinal, pelo envelope das posições com `tyres_out` < 2 nas voltas gravadas. Ela só cobre onde alguém passou, 26 sessões, e não medi.
- **`geometry_id`, o que refazer e ADR:** como na opção 2.

### Uma escolha que vale para as opções 2 e 3

Separar a identidade do corredor da identidade da projeção:
- o `geometry_id` continuaria cobrindo a linha central, as normais e a grade, de onde saem o `s` e o `lateral`;
- um `corridor_id` à parte cobriria as larguras.

Assim, só o que depende das larguras seria refeito: LSTM, substituto, evolutivo, critério da F1 e a métrica `outside_corridor_fraction`. Store, inventário e coach ficariam como estão. Isso emenda o ADR 0002, e precisa de um ADR.

**Um risco que existe hoje, em qualquer opção:**
- `CAR_HALF_WIDTH_M` e `KERB_ALLOWANCE_M` não entram na impressão digital. O corredor útil pode mudar sem o `geometry_id` mudar.
- O corredor útil também não tem um id próprio.

## Testes

`backend/tests/test_conferir_corredor.py`, com 15 testes sintéticos. A pista falsa é uma reta de 100 m, com asfalto, zebra, duas faixas laterais, uma faixa transversal e uma linha `boxes`. Os testes cobrem:
- a conversão das camadas (x, y) para o mundo (x, z = −y), e o asfalto que contém a linha central só com z = −y;
- a interseção da normal com a faixa de cada lado, as bordas da superfície e do asfalto, e a zebra entre elas;
- "sem faixa", inclusive a faixa de outro trecho além da superfície;
- a exclusão da faixa transversal, que não para o raio;
- cada classe da Parte B e os limites entre elas, e a emenda curta que não é borda;
- os trechos que fecham o laço e o lado por extenso;
- as bordas de cada opção da Parte F e o perfil do sinal;
- a procura das chaves `tyresOut` e `offTrack` no fluxo gravado.

**Suíte `backend/tests`:** 685 passando (670 de antes e 15 novos), em 9 min 32 s, com 18 avisos.
- 4 são os de antes (`ConvergenceWarning` do sklearn).
- 14 são de depreciação do pyparsing dentro do matplotlib, que o teste novo importa na coleta.

A saída está em `docs/handoff/2026-10-10_27_corredor-x-pintura_testes.txt`.

## Pontos para o Cowork e decisões do Eduardo

1. **A escolha do corredor** (Parte F): manter, faixa, borda da superfície ou a variante pelo sinal do jogo. Separar ou não o `corridor_id` do `geometry_id`.
2. **O portão de qualidade não usa o corredor** (Parte A). O contexto do pedido o listava como portão.
3. **Fora de pista nas sessões antigas.**
   - Nas sessões gravadas antes de `2026-08-09_17-06-41`, o leitor põe `off_track = False` quando o bloco `environment` existe e não tem o campo (`backend/ml/data/samples.py:163`).
   - Então `_off_track_fraction` usa esse `False` e dá 0. Nas sessões sem o canal que têm o bloco `environment`, o portão de fora de pista fica desligado, sem aviso. São até 110 sessões.
   - Achei isso de passagem e não mudei nada.
4. **O degrau de 1,64 m no fechamento do laço** (direita, de 4332 para 0 m) e os degraus de até 0,81 m vêm do cache e do reamostrador, e não deste pedido. Se a opção escolhida reconstruir as bordas, vale conferir isso junto.
5. **O erro do alinhamento perto da borda** não foi medido. Ele afeta a leitura fina do perfil do sinal da Parte C, mas não muda a ordem de grandeza.

## O que falta

Nada deste pedido. A decisão da Parte F é sua.

Arquivos que não são meus ficaram como estavam, sem commit:
- `docs/dashboard_inventario.md`, `docs/dashboard_visoes.md` e `docs/phase16_dashboard_3_visoes.md`;
- `docs/integracao_ml_e_empacotamento.md`;
- `docs/estudos/` e `docs/imagens/visoes/`;
- `frontend/mockups/prototipo_dashboard.html`.

`docs/handoff/2026-10-10_27_corredor-x-pintura_relatorio.md`
