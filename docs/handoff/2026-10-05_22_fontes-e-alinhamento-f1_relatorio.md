# Relatório do pedido 22: ajustes do ADR 0018 e alinhamento da volta da F1 à pista oficial

- **Pedido:** `docs/prompts/2026-10-05_22_fontes-e-alinhamento-f1.md`
- **Branch:** `etapa/fastf1-alinhamento`, com merge em `develop`
- **Commits e merge:**
  - `9494212c` docs: pecas A a E nos dois modelos, esclarecimento do ADR 0018, backlog e pedido 22 (Parte A)
  - `4d104365` ML: alinhamento da linha da F1 (FastF1) a geometria oficial e erro de alinhamento (pedido 22) (Parte B)
  - `698b9534` Merge etapa/fastf1-alinhamento (pedido 22: ADR 0018 esclarecido e linha da F1 alinhada)
  - o commit deste relatório, com o patch, a saída da suíte, o resumo JSON e a figura: "Relatório do pedido 22: ADR 0018 esclarecido e linha da F1 alinhada"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_relatorio.md` (este)
  - `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1.patch` (de `37ca9d09` até o merge `698b9534`; sha256 `b2afe552…27bef385`)
  - `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_testes.txt` (suíte `backend/tests`: 624 passando)
  - `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_resumo.json` (cópia de `data/ml/externo/fastf1_alinhamento_resumo.json`)
  - `docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_figura.png` (cópia de `data/ml/externo/fastf1_alinhamento.png`)

Nada foi enviado ao remoto. O app instalado e os arquivos do jogo não foram tocados. Nenhum modelo foi treinado, e coach, store e critérios não mudaram.

**Veredito do critério: aceito.** Fora do corredor ficaram 2,03% dos pontos da grade, contra o limite de 10%. O p95 do excesso é 0 m, contra o limite de 1 m.

## Conferência do contexto

Tudo bate com o repositório, e não precisei parar. Duas linhas corrigem o que eu mesmo escrevi no relatório do pedido 21.

| fato do pedido | onde está | bate? |
|---|---|---|
| Peças A a E definidas na Parte 2, seção 1, de `docs/correcao_trajetoria_auditoria.md` | linhas 314 a 411: o diagrama com os subgrafos A a E e um parágrafo para cada peça | sim. **Correção do relatório 21:** eu disse que as peças C e E não tinham definição no repositório. Estava errado, porque as duas estão nessa seção |
| O detector rotulou 75 voltas antigas (35 `ia`, 8 `humano`, 32 `misturada`) e nada foi promovido | `docs/detector_ia.md`, linhas 158 e 160 | sim. **Correção do relatório 21:** lá saiu "75 como `ia`" |
| Volta FastF1 com 633 amostras, `x` e `y`, marcada `UNCALIBRATED` | `data/external_references/fastf1__2024__Brazil__Q__NOR__32__093bbee0.json` (sha256 `dbf1ddea…98ad2c`) | sim |
| Geometria oficial `0ed16f0dd2225990`, 4.334 m, grade de 2.167 pontos | `load_geometry()` e `laps_grid_v2_meta.json` | sim: 4.334,08 m, passo de 2,000 m, store v2 aprovado e na mesma geometria |
| 13 voltas `ia` rotuladas de 04/10 | store v2 | sim: 5 de `2026-10-04_02-24-04` e 8 de `2026-10-04_03-42-10`, todas pelo indicador do jogo, com o relógio conferido |
| Voltas `humano` com equipamento `atual` | store v2, mesmo filtro do relatório de evolução (`evolution.driver_laps`) | 18 voltas (o pedido não dava o número) |
| Situação das peças | ver a Parte A, item 3 | sim, cada uma com a fonte |

## Parte A: documentação

Commit `9494212c` na branch, junto com o arquivo do pedido.

### 1. `docs/backlog.md`

- **Saiu** a linha antiga da peça A: "Peça A: retreinar LSTMs, envelope e traçado com voltas rotuladas e criar a faixa de incerteza σ(s). Peça B, parte estatística…".
- **Ficou** uma linha só, no lugar da linha nova do ADR 0018:

| Item | Origem | Impacto | Quando |
|---|---|---|---|
| **Retreinar a LSTM geradora com as três fontes** (voltas `humano` com equipamento `atual`, voltas `ia` rotuladas e forma da linha da F1), testada na régua do ADR 0006 | Fase 1; revisão da arquitetura (03/10). ADR 0018; pedido 21 (05/10). As duas linhas foram juntadas no pedido 22 | As LSTMs aprenderam sobretudo voltas da IA: hoje a rede erra 0,528 m de lateral abaixo de 88 s e 2,898 m acima, onde está o piloto. Da linha antiga da peça A seguem junto o envelope, o traçado e a faixa de incerteza σ(s). A peça B estatística (desvios contra a referência, sem prometer segundos) já existe como relatório de evolução (pedidos 16 e 17) | Depois das 5 sessões de treino e do alinhamento da F1 (pedido 22, Parte B) |

O texto do item e do "Quando" é o do pedido. No "Quando", troquei "Parte B deste pedido" por "pedido 22, Parte B", porque no backlog "deste pedido" fica sem referência. O "Impacto" é meu: juntei os dois e mantive o que a linha antiga dizia do envelope, do traçado, de σ(s) e da peça B, para não sumir.

- **Linha nova**, pedida no item 2:

| Item | Origem | Impacto | Quando |
|---|---|---|---|
| **Voltas antigas no treino do Modelo 1, num teste à parte:** treinar com e sem elas e comparar na régua do ADR 0006 | ADR 0018, esclarecimento de 05/10; pedido 22 | As voltas antigas ficam fora do treino do Modelo 1. Isso vale para as de origem `desconhecida`, inclusive as 75 que o detector rotulou sem promover (35 `ia`, 8 `humano` e 32 `misturada`). As 552 voltas antigas sem box passam, na mediana, a 0,031 m da linha da IA de hoje | Depois do retreino da LSTM com as três fontes |

O "Quando" desta linha é meu: o teste compara com e sem as voltas antigas, então precisa do retreino com as três fontes como base. Vale o Cowork revisar.

### 2. `docs/decisoes/0018-dois-modelos-e-fontes-de-treino.md`

Seção nova no fim do arquivo:

```markdown
## Esclarecimento (05/10, pedido 22)

- **"Voltas `ia` rotuladas" (item 3 da decisão) são só as de sessões com rótulo pelo indicador do jogo ou por anotação** (ADR 0014): `origem_fonte` igual a `indicador`, `anotacao` ou `anotacao_sessao`, nunca `detector`.
- **As voltas antigas ficam fora do treino do Modelo 1.** Isso vale para as de origem `desconhecida`, inclusive as que o detector marcou sem promover: 75 voltas, sendo 35 `ia`, 8 `humano` e 32 `misturada` (`docs/detector_ia.md`).
- **Elas podem entrar depois num teste à parte**, treinando com e sem elas e comparando na régua do ADR 0006. O teste está no backlog.
```

Os valores de `origem_fonte` são os de `backend/ml/data/origin.py` (`SOURCE_INDICATOR`, `SOURCE_ANNOTATION`, `SOURCE_SESSION_ANNOTATION` e `SOURCE_DETECTOR`).

### 3. `docs/arquitetura_ml.md`

Seção nova no fim, "As peças A a E e os dois modelos". Ela tem um parágrafo com os links para a seção 1 da Parte 2 de `correcao_trajetoria_auditoria.md` e para o ADR 0018, e esta tabela:

| peça | modelo | situação |
|---|---|---|
| A — previsão de trajetória (LSTM geradora) | Modelo 1 | existe |
| busca evolutiva | Modelo 1 | existe |
| juiz do tempo | Modelo 1 | em construção: o juiz novo, o modelo do carro do ADR 0017, com a etapa M0 feita |
| B — erro do piloto | Modelo 2 | em uso: versão 1, o relatório de evolução (pedidos 16 e 17) |
| C — autocorreção | Modelo 2 | planejado |
| D — tempo contrafactual | Modelo 2 | não passou (`fase1_validacao_contrafactual.md`, seção 6; ADR 0011) |
| E — avaliação | avalia os dois | em uso: a régua do ADR 0006 |

Embaixo da tabela, uma frase registra que o juiz é compartilhado: hoje é o simulador quase-estacionário, e a peça D refeita sobre o modelo do carro é a M4 do ADR 0017.

As fontes de cada situação são estas:

- **"não passou" da D:** os estimadores reprovados na Fase 1 (quatro, seção 6) e na 2b (quatro, ADR 0011);
- **"em uso" da B versão 1:** o ADR 0017, M0;
- **"em uso" da E:** a régua do ADR 0006, que é a avaliação da seção 7 da Parte 2.

## Parte B: alinhar a volta da F1 à geometria oficial e medir o erro

### O que foi feito

| arquivo | o que é |
|---|---|
| `backend/ml/external/f1_line.py` (novo) | leitura só de `x`/`y`, unidade, Procrustes (Umeyama) com escala única e espelho opcional, ICP contra a linha central, projeção na grade, excesso sobre o corredor, critério e comparação por microsetor |
| `backend/ml/scripts/alinhar_fastf1.py` (novo) | roda as etapas 1 a 6 e grava em `data/ml/externo/` (fora do git: `data/ml/` está no `.gitignore`) |
| `backend/tests/test_fastf1_alinhamento.py` (novo, 12 testes) | recuperação de uma transformação conhecida (três casos), sinal do lateral (três casos), unidade, excesso, critério, leitura só da posição e sinal da comparação |

Comando: `python -m ml.scripts.alinhar_fastf1`, a partir de `backend/`. Leva cerca de 11 s.

**Só a posição da F1 entra.** `load_xy` lê só `x` e `y`. Velocidade, pedais, marcha, rotação, tempo e a `distanceM`, que o FastF1 integra da velocidade, não são lidos (ADR 0018). O JSON registra isso em `entrada.campos_lidos`.

**O método, em uma frase por etapa:**

1. A unidade sai do perímetro da volta comparado com os 4.334 m.
2. **Busca inicial:** as duas linhas são reamostradas em 500 pontos pela fração do comprimento, e o Procrustes testa todos os deslocamentos cíclicos, com e sem espelho. **ICP:** cada amostra é casada com o pé da perpendicular na linha central (`project_sequence`), e a semelhança é reajustada até nenhuma amostra andar mais de 1 µm. Cada amostra pesa pelo comprimento de linha que representa. Nada deforma a linha.
3. `project_sequence` dá `s` e lateral de cada amostra. Entre as amostras, a interpolação é linear em `s`, fechando o laço, como faz o `resample_lap`.
4. O excesso é o `corridor_violation` de `ml.track`: meia-largura medida, mais 0,5 m de zebra, menos 1,0 m de meia-bitola. Vale 0 dentro.

### Etapa 1: unidades e amostragem

| medida | valor |
|---|---|
| perímetro da volta (polígono fechado das 633 amostras) | 42.319,8 unidades |
| unidades por metro da pista oficial | 9,764 |
| **unidade** | **decímetro (0,1 m)**, a candidata mais perto entre m, dm, cm e pé; é a unidade que o FastF1 documenta |
| perímetro em metros | 4.232,0 m, contra 4.334,08 m |
| espaçamento entre amostras | **mediana 5,45 m, p95 16,46 m**, máximo 57,3 m |

### Etapa 2: alinhamento rígido com escala única

| medida | valor |
|---|---|
| **escala ajustada** | **0,09981 m por unidade**, 0,9981 do decímetro nominal |
| **comprimento da linha alinhada** (polígono das amostras × escala) | **4.224,0 m, contra 4.334,08 m (−2,54%)** |
| **rotação** | **0,55°** |
| **espelhamento** | **sim**: `y → −y` no sistema do FastF1, antes da rotação |
| translação | (−60,5; −365,4) m |
| busca inicial | RMS de 7,80 m com espelho, contra 293,0 m sem. O espelho não é ambíguo |
| ICP | 43 iterações, convergiu |
| distância RMS até a linha central | 3,28 m (não é erro: é o quanto uma linha de corrida se afasta do centro da pista) |

**Os −2,54% são, na maior parte, a linha de corrida cortando as curvas.** Medidas do mesmo jeito na grade (`path_length`), as linhas ficam assim:

| linha | comprimento |
|---|---|
| F1 | 4.257,2 m |
| mediana das voltas `ia` | 4.252,0 m |
| mediana das voltas `humano` | 4.273,3 m |
| linha central | 4.334,08 m |

A linha da F1 tem praticamente o comprimento da linha da IA (+5,2 m, +0,12%). O restante da diferença do polígono vem das cordas entre amostras distantes.

### Etapa 3: projeção na grade

| medida | valor |
|---|---|
| pontos da grade | 2.167, os mesmos do store v2 (geometria `0ed16f0dd2225990`) |
| cobertura entre a primeira e a última amostra | 0,9997 da volta |
| passos para trás em `s` | 0 |
| espaçamento entre amostras ao longo de `s` | mediana 5,70 m, p95 16,55 m, máximo 57,6 m |
| lateral da F1 na grade | de −7,55 m a +9,03 m; média −0,20 m |

A linha na grade está em `data/ml/externo/fastf1_linha_na_grade.csv`, com `s`, lateral, os dois limites do corredor, o excesso e as linhas medianas da IA e do piloto.

### Etapa 4: erro de alinhamento (excesso sobre o corredor)

| | na grade (2.167 pontos, vale para o critério) | nas amostras (633, complementar) |
|---|---|---|
| pontos fora do corredor | **44 (2,03%)** | 20 (3,16%) |
| mediana do excesso | **0 m** | 0 m |
| p95 do excesso | **0 m** | 0 m |
| máximo do excesso | **2,26 m** | 2,29 m |
| mediana só dos pontos fora | 0,56 m | 0,49 m |

**Microsetores com maior excesso.** Só 3 dos 60 microsetores têm algum excesso, e os outros 57 têm zero. O 4º e o 5º do JSON (MS01 e MS02) aparecem só porque empatam em zero.

| microsetor | curva | excesso máximo | excesso médio | pontos fora | lado |
|---|---|---|---|---|---|
| MS45 (3.178 a 3.251 m) | Junção (C12, à esquerda) | 2,26 m | 0,82 m | 56% | esquerda, por dentro da curva |
| MS38 (2.673 a 2.745 m) | Bico de Pato (C10, à direita) | 0,62 m | 0,17 m | 36% | direita, por dentro da curva |
| MS19 (1.300 a 1.372 m) | Descida do Lago (C04, à esquerda) | 0,43 m | 0,09 m | 31% | esquerda, por dentro da curva |

Todo o excesso fica no lado de dentro de três curvas, perto do ápice. Há três hipóteses, que não foram medidas:

- o carro da F1 passa mais por cima da zebra do que os 0,5 m que o corredor permite;
- a borda medida do jogo difere da pista real nesses pontos;
- é alinhamento residual.

Os dados não separam as três.

### Veredito do critério

| condição (fixada antes de rodar, na grade) | medido | passa? |
|---|---|---|
| fração de pontos fora do corredor ≤ 10% | 2,03% | sim |
| p95 do excesso ≤ 1 m | 0 m | sim |

**Aceito para uso futuro.** Nada foi ajustado depois de ver o resultado (ver "Escolhas minhas e o que mudou entre as rodadas").

### Etapa 5: comparação descritiva, só para leitura

Diferença = lateral da F1 − lateral mediano das voltas, por ponto da grade. Depois tirei a mediana em cada microsetor. Positivo quer dizer que a F1 passa mais à esquerda. Nada disso muda coach, store ou critério.

- **IA:** as 13 voltas `ia` rotuladas de 04/10 (lista em `etapa5_comparacao.voltas_ia` no JSON).
- **Piloto:** as 18 voltas `humano` com equipamento `atual` (lista em `etapa5_comparacao.voltas_humano`).

| | mediana de \|Δ\| por microsetor | p90 | máximo |
|---|---|---|---|
| F1 − mediana da IA | 1,81 m | 3,33 m | 5,02 m (MS48, 3.395 a 3.467 m) |
| F1 − mediana do piloto | 1,44 m | 3,04 m | 3,80 m (MS35, 2.456 a 2.528 m) |

Lateral médio na volta: F1 −0,20 m, mediana da IA +0,38 m, mediana do piloto −0,81 m.

Tabela completa, em metros:

| microsetor | s (m) | F1 − IA | F1 − piloto |
|---|---|---|---|
| MS01 | 0 a 72 | +1,48 | +1,20 |
| MS02 | 72 a 144 | +1,78 | +1,61 |
| MS03 | 144 a 217 | +2,89 | +2,34 |
| MS04 | 217 a 289 | +2,32 | +2,22 |
| MS05 | 289 a 361 | −2,96 | −1,87 |
| MS06 | 361 a 433 | −0,43 | −0,52 |
| MS07 | 433 a 506 | −1,98 | −0,69 |
| MS08 | 506 a 578 | −2,18 | −0,40 |
| MS09 | 578 a 650 | −2,93 | −0,97 |
| MS10 | 650 a 722 | −3,33 | −2,35 |
| MS11 | 722 a 795 | +0,11 | −0,61 |
| MS12 | 795 a 867 | −0,72 | −0,04 |
| MS13 | 867 a 939 | +0,09 | +0,69 |
| MS14 | 939 a 1.011 | +1,04 | +0,61 |
| MS15 | 1.011 a 1.084 | +1,70 | +0,59 |
| MS16 | 1.084 a 1.156 | +2,24 | +1,06 |
| MS17 | 1.156 a 1.228 | +2,27 | +2,00 |
| MS18 | 1.228 a 1.300 | +1,71 | +2,07 |
| MS19 | 1.300 a 1.372 | +1,88 | +2,65 |
| MS20 | 1.372 a 1.445 | −0,18 | +1,94 |
| MS21 | 1.445 a 1.517 | +0,36 | +1,31 |
| MS22 | 1.517 a 1.589 | −2,22 | +0,89 |
| MS23 | 1.589 a 1.661 | −2,31 | +1,01 |
| MS24 | 1.661 a 1.734 | +1,14 | +1,28 |
| MS25 | 1.734 a 1.806 | −3,08 | −2,02 |
| MS26 | 1.806 a 1.878 | −4,20 | −2,97 |
| MS27 | 1.878 a 1.950 | −1,73 | −0,73 |
| MS28 | 1.950 a 2.023 | +1,87 | +2,44 |
| MS29 | 2.023 a 2.095 | −0,64 | +3,49 |
| MS30 | 2.095 a 2.167 | −0,18 | +0,68 |
| MS31 | 2.167 a 2.239 | −0,72 | −0,69 |
| MS32 | 2.239 a 2.312 | −1,30 | −1,77 |
| MS33 | 2.312 a 2.384 | −0,01 | −3,15 |
| MS34 | 2.384 a 2.456 | −3,39 | −1,69 |
| MS35 | 2.456 a 2.528 | −2,00 | +3,80 |
| MS36 | 2.528 a 2.600 | −2,28 | −0,63 |
| MS37 | 2.600 a 2.673 | −4,53 | −0,67 |
| MS38 | 2.673 a 2.745 | −2,15 | −2,27 |
| MS39 | 2.745 a 2.817 | −0,54 | −1,06 |
| MS40 | 2.817 a 2.889 | −2,98 | −2,40 |
| MS41 | 2.889 a 2.962 | −2,01 | −1,18 |
| MS42 | 2.962 a 3.034 | +1,23 | +0,19 |
| MS43 | 3.034 a 3.106 | +1,88 | +1,56 |
| MS44 | 3.106 a 3.178 | +3,91 | +2,80 |
| MS45 | 3.178 a 3.251 | +2,44 | +3,46 |
| MS46 | 3.251 a 3.323 | +1,96 | +2,56 |
| MS47 | 3.323 a 3.395 | −1,85 | +0,26 |
| MS48 | 3.395 a 3.467 | −5,02 | +1,09 |
| MS49 | 3.467 a 3.539 | −4,28 | −0,03 |
| MS50 | 3.539 a 3.612 | −1,84 | +0,15 |
| MS51 | 3.612 a 3.684 | −0,04 | +2,30 |
| MS52 | 3.684 a 3.756 | −1,52 | +1,65 |
| MS53 | 3.756 a 3.828 | −0,04 | −0,18 |
| MS54 | 3.828 a 3.901 | −0,28 | +1,12 |
| MS55 | 3.901 a 3.973 | −0,67 | +3,17 |
| MS56 | 3.973 a 4.045 | −0,82 | +2,93 |
| MS57 | 4.045 a 4.117 | −1,75 | +3,03 |
| MS58 | 4.117 a 4.190 | −1,31 | +3,43 |
| MS59 | 4.190 a 4.262 | +0,36 | +1,94 |
| MS60 | 4.262 a 4.334 | +1,28 | +1,33 |

### Etapa 6: figura

`docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_figura.png` é a cópia de `data/ml/externo/fastf1_alinhamento.png`. Ela mostra:

- a pista oficial: o asfalto entre as bordas medidas, o corredor tracejado e a linha central pontilhada;
- a linha da F1 alinhada, em laranja;
- a mediana das 13 voltas `ia`, em azul;
- zoom no S do Senna (s = 184 a 462 m, da C01 à C02) e no Bico de Pato (s = 2.632 a 2.798 m, a C10). Os zooms também mostram as amostras do FastF1.

O plano é o X/Z do jogo.

### Limitação do método

**Contra a linha central, um deslocamento lateral uniforme se confunde com a escala.** O ICP minimiza o lateral ao quadrado. Por isso, parte de qualquer tendência da linha a ficar de um lado é absorvida pela escala e pela translação, e a linha sai mais perto do centro do que de fato está. Vi isso nos testes sintéticos, antes de rodar a volta real:

- uma linha toda 3 m à esquerda saiu a −0,4 m;
- uma onda de ±3 m saiu com viés de cerca de 0,6 m. Por isso, o teste de sinal confere o lado, com 1 m de tolerância no valor.

Na volta real, isso quer dizer duas coisas:

- **A posição da linha da F1 pode ter um viés de alguns decímetros que o excesso não mede.** A média de −0,20 m é, em parte, produto do ajuste.
- **A escala de 0,9981 sozinha não diz se a pista do jogo tem outro tamanho que a real.** Nela se misturam essa absorção, o ruído das posições do FastF1 e uma eventual diferença de tamanho.

O pedido fixou o ajuste contra a linha central, e foi o que usei. Ajustar contra o corredor ou contra a linha da IA tornaria a medida de erro circular.

### Escolhas minhas e o que mudou entre as rodadas

Escolhas que o pedido deixava em aberto, todas fixadas no código antes de rodar a volta real:

1. **Peso de cada amostra no ajuste:** metade dos dois segmentos vizinhos. As amostras do FastF1 são uniformes no tempo, e por isso mais densas nas curvas lentas. Com o peso, cada metro de pista pesa o mesmo, como na grade.
2. **O critério é medido na grade** (2.167 pontos), que é o que vai ser usado depois. As amostras entram como complemento e também passariam: 3,16% fora e p95 de 0 m.
3. **Ordem dos microsetores:** pelo excesso máximo, com desempate pelo excesso médio.
4. **Salto máximo da projeção em sequência:** 150 m, em vez dos 60 m do gravador. A F1 tem buracos de até 57 m entre amostras, e 150 m ainda separa os trechos que correm lado a lado.

Durante o desenvolvimento, só com dados sintéticos, dois testes falharam e foram refeitos. O método não mudou.

- A tolerância da translação passou a ser medida no centróide da linha. O vetor de translação é a imagem da origem do FastF1, a cerca de 5 km da pista, e ali 0,02° de rotação já viram 1,6 m.
- O teste de sinal com espelho passou a usar uma linha que alterna os lados (é a limitação acima).

Depois da primeira rodada na volta real, mudei só a apresentação:

- **figura:** as molduras dos zooms eram brancas e não apareciam, e um título se sobrepunha a um eixo;
- **JSON:** três campos descritivos novos (comprimentos na grade, lado do maior excesso e número de microsetores com excesso).

Rodei de novo e comparei. Todos os números da primeira rodada ficaram idênticos (só mudaram `gerado_em` e os campos novos), e a grade em CSV ficou igual byte a byte.

O campo `commit` do JSON é `9494212c`, porque rodei antes de commitar a Parte B. O código que gerou o JSON é o do commit `4d104365`, sem nenhuma diferença.

### Testes

- **Os 12 testes novos passam.**
- **Suíte `backend/tests`:** 624 passando. Antes eram 612, e agora são 624 com os 12 novos.
- **Nota:** a primeira tentativa rodou o `pytest` na pasta `backend/` inteira e pegou `test_ws_client.py`, um script da raiz que precisa do servidor no ar. Parei essa rodada e repeti só em `tests/`, como nos relatórios anteriores.

## Pontos para o Cowork e decisões do Eduardo

Nada disto bloqueou o pedido.

1. **A linha do backlog "Dados externos no treino do Modelo 1"** continua com "Quando: A definir". Este pedido fez o alinhamento e a medida de erro, mas não a entrada no treino. Não mexi na linha porque o pedido não pedia. Vale o Cowork atualizá-la.
2. **O excesso de até 2,26 m na Junção.** Se a linha da F1 entrar no retreino como está, 44 pontos ficam fora do corredor que o resto do pipeline usa (`clip_to_corridor`). Clipar, aceitar ou marcar esses pontos é decisão do pedido do retreino.
3. **O viés da limitação acima não aparece no erro medido.** Se ele importar para o uso no treino, medi-lo pede outra referência independente da linha central. Não fiz nada disso: fica registrado.
4. **É uma volta só** (Norris, classificação de 2024, volta 32). A forma de uma volta inclui as escolhas daquela volta.

## O que falta

Nada deste pedido. O retreino com as três fontes e o teste das voltas antigas estão no backlog e esperam pedido próprio.

`docs/handoff/2026-10-05_22_fontes-e-alinhamento-f1_relatorio.md`
