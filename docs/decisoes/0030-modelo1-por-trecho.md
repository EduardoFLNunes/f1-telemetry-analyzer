# 0030 — O Modelo 1 por trecho

- **Status:** aceita (pedido 49). Registrada antes de qualquer conta nas gravações; o resultado entra no fim, sem mudar o registro
- **Data:** 2026-11-12
- **Decisor:** Eduardo
- **Refina:** 0029 (o teste no jogo como medidor da linha). **Mantém:** 0009 (a linha gerada não vai para o coach), o corredor do 0025 e a geometria do 0002

## Contexto

1. **O pedido 47** (ADR 0029) pôs a IA do jogo para dirigir cinco linhas na cópia da pista, com 7 voltas que contam por condição (4 no C0 final). As medianas foram:
   - C0 1:25,438;
   - C4 1:25,920;
   - C3 1:26,015;
   - C2 1:27,014;
   - C1 1:27,517;
   - C0 final 1:25,667.

   O veredito de C3 e C4 foi "não conclusivo (deriva)".
2. **A volta inteira esconde onde a linha ganha e onde perde.** Somando os microssetores do `_resultado.json` do 47 em trechos aproximados pela curvatura, o Cowork achou ganho das linhas geradas na saída da C06 e na C08, e perda no S do Senna, na C03, na C07 e na C10.
3. **As decisões do Eduardo de 11/11** (desenho "Modelo 1 no aprendizado do piloto", decisões 1 e 2):
   - **o Modelo 1 entrega ao coach uma referência por trecho:** em cada trecho, a linha que ganhou no jogo com o mesmo piloto;
   - uma linha gerada só vira referência num trecho depois de vencer num teste novo no jogo. Até lá, ela é "candidata";
   - esta rodada é só a conta por trecho, com os dados do 47.
4. **O Modelo 1 decide só a linha.** No teste do 47, o ponto de frenagem, a marcha e os pedais foram da IA. Nas linhas novas, a velocidade, o acelerador e o freio gravados no arquivo foram copiados da linha original na mesma estação (ADR 0029, item 1).
5. **A codificação custou 2,1 s** (C1 contra C0). Há duas hipóteses: as dicas da linha (a velocidade e os pedais copiados não acompanham a linha nova) e a curvatura (o raio recalculado de uma linha codificada fica serrilhado).
6. **Duas propostas do desenho, ainda não confirmadas pelo Eduardo,** entram como provisórias: a tradução do ponto de frenagem da IA pela rampa do freio do Eduardo, e o limite "de linha" pela repetibilidade dele.

## Decisão

### 1. Os trechos

**Um trecho por curva oficial, mais o trecho da chegada: 15 ao todo.**
- **A geometria** é a do corredor (`ml.track.geometry.load_corridor_geometry`: `geometry_id 0ed16f0dd2225990`, `corridor_id 707d07029036abd6`, 2.167 pontos de 2,000 m, 4.334,080 m).
- **As curvas** são as 14 de `ml.track.corners.detect_corners`, as mesmas do coach, do rádio (`core/radio/janelas.py`) e da evolução.
- **Cada trecho vai do fim da curva anterior ao fim da curva.** O da C01 começa na linha (s = 0), e o último vai do fim da C14 até a linha.

| trecho | curva (início / ápice / fim, m) | limites do trecho (m) |
|---|---|---|
| C01 | 224,0 / 298,0 / 334,0 | 0,0 → 334,0 |
| C02 | 358,0 / 390,0 / 422,0 | 334,0 → 422,0 |
| C03 | 434,0 / 490,0 / 692,0 | 422,0 → 692,0 |
| C04 | 1.312,0 / 1.372,0 / 1.402,0 | 692,0 → 1.402,0 |
| C05 | 1.480,0 / 1.520,0 / 1.606,0 | 1.402,0 → 1.606,0 |
| C06 | 1.938,0 / 2.102,0 / 2.140,0 | 1.606,0 → 2.140,0 |
| C07 | 2.246,0 / 2.282,0 / 2.334,0 | 2.140,0 → 2.334,0 |
| C08 | 2.350,0 / 2.394,0 / 2.498,0 | 2.334,0 → 2.498,0 |
| C09 | 2.566,0 / 2.610,0 / 2.626,0 | 2.498,0 → 2.626,0 |
| C10 | 2.672,0 / 2.728,1 / 2.758,1 | 2.626,0 → 2.758,1 |
| C11 | 2.850,1 / 2.884,1 / 3.024,1 | 2.758,1 → 3.024,1 |
| C12 | 3.188,1 / 3.222,1 / 3.262,1 | 3.024,1 → 3.262,1 |
| C13 | 3.334,1 / 3.356,1 / 3.380,1 | 3.262,1 → 3.380,1 |
| C14 | 3.578,1 / 3.640,1 / 3.666,1 | 3.380,1 → 3.666,1 |
| C14→linha | sem curva | 3.666,1 → 4.334,1 |

- **Os trechos cobrem a volta inteira, sem buraco e sem sobreposição:** o fim de um é o começo do seguinte.
- **O tempo de cada trecho** sai do cronômetro de cada volta na grade (`resample_lap(..., line_clock=True)`, o mesmo relógio do store v2 e do resultado do 47). O tempo na fronteira `s` é o `elapsed_s` interpolado em `s`. O fim do último trecho é o tempo da volta.
- **Em cada volta, a soma dos 15 trechos tem de bater com o tempo da volta (`tempo_s` do 47) em até 5 ms.** Se uma volta não bater, a conta para e o motivo é registrado.
- **Os pontos de cada trecho** para as medidas de linha: a **entrada** é o início da curva, o **ápice** é o ápice dela e a **saída** é o fim dela. No trecho C14→linha, que não tem curva, são o início, o meio e o fim do trecho.

### 2. As voltas

- **As do teste no jogo:** as que contam e são válidas no `_resultado.json` do pedido 47 (`docs/handoff/2026-11-07_47_linha-gerada-no-jogo_resultado.json`, `papel == "conta"` e `valida`). São 7 por condição e 4 no C0 final, identificadas por `sessao` e `sequencia`, sem mudar a atribuição nem a validade.
  - Cada uma é refeita a partir da gravação com o caminho do 47 (`clean_lap`, `align_lap`, `resample_lap` com `line_clock`). **O tempo refeito tem de ser igual ao `tempo_s` do 47 em até 1 ms;** se não for, a conta para.
  - As gravações da cópia ficam na pasta do app instalado e só são lidas.
- **As voltas do Eduardo:** as 136 de origem `humano` do pedido 44 (`data/ml/retreino_lstm/voltas.parquet` e `voltas_tabela.parquet`, já na mesma grade e com a mesma `geometry_id`). As 9 de 24/10 (`sessao == "2026-10-24"`) são um subconjunto delas e saem também à parte. As voltas do Eduardo são da pista original, e as da IA são da cópia, com a mesma geometria.
- **As linhas** são lidas dos arquivos do 47 em `data/pista_teste/linhas/C0` a `C4` (`fast_lane.ai`), conferidos pelo sha256 do `linhas.json`. A linha da IA (C0) é o arquivo C0, que é a cópia byte a byte do original. **A lateral de cada linha na grade** é a projeção dos pontos do arquivo (`ml.pista_teste.condicoes.lateral_da_linha`). Nenhum arquivo da pasta do jogo é aberto.

### 3. A regra do ganho por trecho

Para cada comparação de uma condição X contra uma base Y, em cada trecho:

- **o efeito:** a diferença das medianas dos tempos do trecho, `mediana(X) − mediana(Y)`;
- **o IC de 95%:** bootstrap com 10.000 reamostragens. Cada grupo é reamostrado com reposição, com um gerador novo de semente 49 por comparação e por trecho (`numpy.random.default_rng(49)`), e o IC vai dos percentis 2,5 aos 97,5 da diferença das medianas;
- **o p-valor:** permutação exata, com todas as divisões das voltas entre os dois grupos (3.432 com 7 e 7; 330 com 7 e 4). **A estatística é a diferença das médias** (decisão do Eduardo, 12/11, antes de qualquer conta). O p-valor é bilateral: a fração das divisões com |diferença das médias| ≥ a observada;
- **a correção de Holm a 5%** entre os 15 trechos de cada comparação;
- **ganho:** a diferença das medianas é negativa, a diferença das médias também é negativa, e o p-valor passa no Holm. Isso vale **contra o C0 e contra o C0 final, nas duas comparações;**
- **perda:** o mesmo, com as duas diferenças positivas, contra o C0 e contra o C0 final;
- **empate:** todo o resto.

**Por que a estatística da permutação é a média:**
- com a diferença das medianas, o menor p-valor possível, mesmo com separação completa, é 0,0117 com 7 e 7 voltas, e 0,0121 com 7 e 4. O primeiro limite do Holm com 15 trechos é 0,05 / 15 = 0,0033, então nenhum trecho poderia passar;
- com a diferença das médias, o piso é 0,0006 (7 e 7) e 0,0030 (7 e 4);
- a conta, com dados sintéticos, está no relatório do pedido 49.

**O que isso implica contra o C0 final (4 voltas):** o piso de 0,0030 fica logo abaixo do primeiro limite do Holm. Só passa um trecho em que as 4 voltas do C0 final ficam todas de um lado das 7 da condição, e mesmo assim só se nenhuma outra divisão chegar à mesma diferença.

**As comparações:**
- C1, C2, C3 e C4 contra o C0 e contra o C0 final (B.1);
- o C0 final contra o C0, só relatado (B.2, a deriva);
- a C2 contra a C3 e contra a C4, só relatado (B.3). Nas comparações só relatadas, "significativo" quer dizer passar no Holm da própria comparação.

### 4. A candidata

**Uma linha é candidata num trecho quando a C3 ou a C4 tem ganho pela regra do item 3.** Nenhuma vira referência neste pedido: a referência de todos os trechos é a linha da IA (C0), e a candidata leva a marca "a validar no jogo".

### 5. As medidas da execução

Por trecho e por volta, na grade de 2 m. Os canais são `brake` e `throttle` (de 0 a 1), `gear` (como gravado) e `speed_kmh`. Um canal que falta sai como "não gravado", e uma medida sem dados como "sem dados".

- **O início da frenagem:** o primeiro ponto da grade, do início do trecho até o ápice, em que o freio fica ≥ 0,10 e o ponto anterior está abaixo de 0,10. O ponto anterior ao trecho entra só para ver a subida no primeiro ponto. No trecho C14→linha, a busca vai do início ao fim do trecho. Sem subida, a medida é "sem frenagem no trecho".
- **O freio máximo:** o maior freio da frenagem, do início dela até o freio voltar abaixo de 0,10 (ou o fim do trecho).
- **A distância até o ápice:** o ápice menos o início da frenagem, em metros. No trecho C14→linha, "sem curva".
- **A velocidade mínima e onde ela acontece:** o menor `speed_kmh` do trecho e o `s` dele.
- **A marcha mínima** do trecho e **cada troca de marcha:** o `s` do primeiro ponto com a marcha nova e a troca ("de → para"). Uma troca entre o último ponto do trecho anterior e o primeiro deste conta neste.
- **A retomada:** o primeiro ponto do trecho a partir do qual o acelerador fica ≥ 0,90 até o fim do trecho. Se o último ponto ficar abaixo de 0,90, "sem retomada no trecho".
- **O resumo por condição:** a mediana e o desvio padrão (amostral) de cada medida entre as voltas, e quantas voltas têm a medida. Para as trocas de marcha, a sequência de trocas mais comum entre as voltas, a mediana do `s` de cada troca nela e quantas voltas têm essa sequência.

### 6. As hipóteses dos 2,1 s (só relatadas)

**As dicas da linha:**
- por trecho: o início da frenagem e a velocidade mínima da IA na C1 e no C0 (as medianas e a diferença);
- ao lado, o que os campos dos arquivos dizem: o primeiro ponto do trecho em que o `freio` do arquivo fica ≥ 0,10 e o anterior não, e a menor `velocidade` do arquivo (em km/h) com o `s` dela;
- o `s` de cada ponto do arquivo é a estação dele na geometria (`ml.pista_teste.linha_nova.estacoes`, sobre o arquivo C0). Na C1, cada ponto fica na mesma estação do ponto original, então as dicas ficam no mesmo `s` nas duas;
- **o que se espera, se as dicas mandarem:** nos trechos com frenagem, o início da frenagem da IA fica no mesmo lugar na C1 e no C0 (a menos de 4 m, dois pontos da grade), preso ao lugar da dica, e a perda da C1 aparece depois, na mínima ou na retomada. Se a IA frear em outro lugar na C1, as dicas não prendem a frenagem.

**A curvatura:**
- **a curvatura de cada ponto de um arquivo** é `κ = direcao / raio`, com os dois campos do próprio arquivo, que são o que a IA lê. Um raio não finito ou ≤ 0 dá `κ = 0`;
- **a segunda diferença:** `Δ²κ_i = κ_{i+1} − 2κ_i + κ_{i−1}`, com a linha fechada;
- **a rugosidade de um ponto:** a raiz da média de `(Δ²κ)²` nos pontos a até 10 m de estação dele (uma janela de 20 m), em 1/m;
- **a rugosidade de um microssetor:** a média da rugosidade dos pontos do arquivo cuja estação cai nele;
- **o afastamento lateral de um microssetor:** a média de |lateral da linha − lateral do C0| nos pontos da grade dele;
- **a perda de uma linha num microssetor:** a mediana dos tempos dela menos a do C0, com as voltas do item 2 e os 60 microssetores de `build_microsectors` (como na E.5 do 47);
- **o teste:** a correlação de Spearman (`scipy.stats.spearmanr`, com o ρ e o p-valor), entre os 60 microssetores, da perda da C1 com:
  - a diferença de rugosidade (C1 − C0);
  - o afastamento lateral.

  A C2, a C3 e a C4 saem na mesma tabela, para comparar;
- **o que se espera, se a curvatura mandar:** ρ com a diferença de rugosidade positivo e maior que o ρ com o afastamento lateral.

### 7. As regras provisórias (sem confirmação do Eduardo; o coach não as usa)

**As voltas do Eduardo** são as 136 `humano` do item 2.

- **A rampa do freio, por trecho:**
  - em cada volta com frenagem no trecho (item 5), a distância entre o freio passar de 0,10 e chegar a 90% do freio máximo daquela frenagem;
  - os dois pontos são interpolados linearmente entre os pontos da grade;
  - a rampa do trecho é a mediana entre as voltas. Com menos de 5 voltas com frenagem, é "sem dados".
- **O ponto de frenagem traduzido:** o início da frenagem da IA no C0 (a mediana das 7 voltas) menos a rampa do trecho. Assim, o freio do Eduardo chega a 90% onde a IA começa a frear.
- **O limite "de linha":** na entrada, no ápice e na saída de cada trecho:
  - a mediana da lateral das voltas do Eduardo naquele ponto;
  - a distância de cada volta a essa mediana;
  - o limite é o percentil 90 dessas distâncias (a repetibilidade dele).
- **A distância "de linha" do Eduardo,** nos mesmos pontos, é |mediana da lateral dele − lateral da linha da IA (C0)|. **Ela fica acima do limite** quando passa do percentil 90 do mesmo ponto.
- **"Quanto do trecho fica acima do limite":**
  - a mesma conta em cada ponto da grade do trecho (a mediana, o percentil 90 e a distância à linha da IA);
  - a fração do comprimento do trecho em que a distância passa do limite.

### 8. As outras contas da Parte B (só relatadas)

- **O tempo por trecho de cada condição:** a mediana, o desvio padrão e o intervalo interquartil, mais a regra do item 3. Uma figura mostra cada trecho contra o C0, com o IC, na ordem da pista.
- **As voltas do Eduardo por trecho:** a mediana, a melhor e a diferença de cada uma para a mediana do C0. É feita para as 136 e para as 9 de 24/10.
- **A diferença do Eduardo em linha e execução:** a distância "de linha" do item 7 e as medidas do item 5 dele (as medianas) contra as da IA no C0.
- **O teto da referência por trecho:** em cada trecho, a menor mediana entre C0, C1, C2, C3 e C4, somadas. **É um teto, não uma previsão:**
  - o ganho de um trecho muda a entrada do seguinte;
  - escolher a melhor depois de ver os dados favorece o acaso;
  - o C0 final fica fora, porque é a mesma linha do C0.

### 9. A referência por trecho (Parte C)

`ml/scripts/referencia_por_trecho.py` gera `data/modelo1_por_trecho/referencia_por_trecho.json`, fora do git, porque deriva do arquivo da pista. Por trecho, ele traz:
- os limites (o `s` na geometria do item 1);
- a linha de referência: a linha da IA (C0) em todos os trechos, como a lateral nos pontos da grade do trecho;
- a execução da IA nessa linha: as medidas do item 5, com a mediana e o desvio das 7 voltas do C0;
- a candidata, quando houver: a linha, a lateral, o ganho medido e a marca "a validar no jogo";
- as propostas provisórias do item 7, com a marca "provisório, sem confirmação".

O arquivo também traz o `geometry_id`, o `corridor_id`, o commit e o sha256 das gravações e dos arquivos usados. Um resumo, sem a lateral ponto a ponto, vai para `docs/handoff/2026-11-11_49_modelo1-por-trecho_referencia.json`. **O coach não lê esse arquivo.**

### 10. O que se espera (escrito antes das contas)

1. **A soma por trecho repete o que o Cowork achou:** as linhas geradas ganham no trecho C06 e talvez no C08, e perdem no C01 e no C02 (o S do Senna), no C03, no C07 e no C10.
   - **Por quê:** os trechos oficiais juntam os mesmos microssetores que o Cowork somou, com limites um pouco diferentes.
2. **Contra o C0, com 7 e 7 voltas, diferenças de 0,1 s ou mais passam no Holm.**
   - **Por quê:** o desvio da volta inteira é de cerca de 0,1 s, e o de um trecho deve ficar entre 0,01 e 0,05 s.
3. **Contra o C0 final, quase nada passa no Holm.**
   - **Por quê:** com 4 voltas, o p-valor só chega ao limite com separação completa.
   - **O mais provável é nenhuma candidata,** ou só a C3 ou a C4 no trecho C06.
4. **A deriva (C0 final contra C0) se espalha pela volta,** sem nenhum trecho que passe no Holm.
   - **Por quê:** 0,23 s em 15 trechos é cerca de 0,015 s por trecho.
5. **A C1 perde em quase todos os trechos,** mais nos trechos longos e rápidos (C03, C06, C11 e C14→linha).
6. **As hipóteses dos 2,1 s: a curvatura explica mais que as dicas.**
   - **Por quê:** a linha C1 fica a 0,32 m da linha da IA (mediana; 1,37 m no máximo), com cada ponto no mesmo `s`. As dicas ficam praticamente no lugar certo, e mesmo assim a C1 perde 2,1 s.
   - **O que se espera:** o início da frenagem da IA igual na C1 e no C0 (a menos de 4 m), e ρ com a rugosidade positivo e maior que ρ com o afastamento.
7. **O Eduardo perde para a IA em quase todos os trechos.** A maior parte vem da execução: freia antes, a mínima fica mais baixa e a retomada vem depois. A distância "de linha" passa do limite em poucos pontos, mais no ápice das curvas lentas (C01, C10 e C12).
8. **O teto da referência por trecho** fica entre 0,2 e 0,5 s abaixo da mediana do C0. Ele não é uma previsão.

### 11. Nenhuma regra muda depois de ver os números

Este registro é commitado antes de qualquer conta nas gravações. O resultado entra numa seção no fim, sem mudar nada acima dela.

## Consequências

- **O coach continua igual:** ele não lê a referência por trecho, e o ADR 0009 não muda.
- **Uma candidata não é uma referência.** Ela precisa de um teste novo no jogo, num pedido próprio, com a mesma IA e o C0 intercalado para separar a deriva.
- **As propostas do item 7 são provisórias.** Elas só entram no coach depois que o Eduardo confirmar as decisões 3 e 5 do desenho.

## Resultado

Escrito depois das contas, em 12/11, sem mudar nada acima. As contas são do commit `686003de` (`python -m ml.scripts.modelo1_por_trecho` e `python -m ml.scripts.referencia_por_trecho`; as mesmas de `2457540b`, refeitas depois de o script passar a ler as sessões da cópia pelo `etapas.py`). As saídas estão em `docs/handoff/2026-11-11_49_modelo1-por-trecho_conta.json`, `_referencia.json` e `_por_trecho.png`, e o relatório tem as tabelas inteiras.

### A conferência

- **As 39 voltas que contam no 47** foram refeitas das gravações. O tempo refeito é igual ao do 47 (diferença máxima de 0,0 ms).
- **A soma dos 15 trechos bate com o tempo da volta:**
  - nas voltas da IA, em até 0,33 ms;
  - nas 136 voltas do Eduardo, em até 1,85 ms.
- **Os canais:** o freio vai de 0 a 0,99 nas voltas da IA e de 0 a 1 nas do Eduardo. Nenhum canal faltou.

### As candidatas (itens 3 e 4)

| trecho | linha | contra o C0 (IC 95%) | contra o C0 final (IC 95%) |
|---|---|---|---|
| C06 | C3 | −0,234 s (−0,246 a −0,208) | −0,264 s (−0,276 a −0,243) |
| C06 | C4 | −0,223 s (−0,236 a −0,196) | −0,253 s (−0,265 a −0,232) |
| C09 | C3 | −0,105 s (−0,112 a −0,059) | −0,075 s (−0,089 a −0,064) |
| C09 | C4 | −0,140 s (−0,165 a −0,097) | −0,111 s (−0,138 a −0,093) |
| C13 | C4 | −0,013 s (−0,019 a −0,008) | −0,016 s (−0,021 a −0,011) |

- **Os p-valores** ficam no piso: 0,0006 contra o C0 e 0,0030 contra o C0 final, ou seja, separação completa. Todos passam no Holm.
- **Na referência (item 9),** cada trecho com candidata leva a de maior ganho contra o C0: C3 na C06, C4 na C09 e C4 na C13. A outra fica como "outras candidatas".
- **Nenhuma vira referência:** todas levam a marca "a validar no jogo".
- **As perdas pela regra:**
  - C3: C02, C03, C07 e C10;
  - C4: C01, C02, C03, C10 e C12.

  Os outros trechos ficam em empate.

### A deriva (C0 final contra C0, só relatado)

- **A deriva ficou no fim da volta.** Três trechos passam no Holm: C03 (+0,014 s), C14 (+0,038 s) e C14→linha (+0,079 s). Juntos, eles somam 0,131 s dos 0,248 s da soma das medianas.
- Nos outros trechos, a diferença fica entre −0,030 e +0,056 s, sem significância.

### As linhas codificadas (C1 e C2)

- **A C1 perde em 9 trechos e ganha em 1 (C09, −0,057 s).** O trecho C14→linha sozinho custa +0,836 s, 41% da soma (+2,045 s pela soma das medianas).
- **A C2 ganha na C04 (−0,187 s) e na C06 (−0,176 s)** e perde em 7 trechos. O trecho C14→linha custa +0,856 s.
- **No trecho C14→linha, a IA freia na C1 e na C2,** a partir de 3.860 m e 3.866 m, e cai para 204 e 208 km/h. No C0, na C3 e na C4, ela não freia ali e passa a 218 a 220 km/h.

### As hipóteses dos 2,1 s (item 6, só relatadas)

- **As dicas da linha: o esperado não se confirmou.**
  - Nos 8 trechos em que a IA freia no C0 e na C1, o início da frenagem fica a menos de 4 m em só 2 (C02 e C12).
  - Nos outros, a frenagem da C1 vem de −4 a +32 m do C0 (+32 m na C10).
  - **A IA também não freia no lugar da dica no C0:** em 6 dos 7 trechos com dica de freio, ela começa a frear de 12 a 46 m depois do ponto do arquivo.
  - Na C14→linha, o arquivo não tem freio, e mesmo assim a IA freia na C1.
- **A curvatura, como registrada: o esperado também não se confirmou.**
  - O ρ da perda da C1 com a diferença de rugosidade é de +0,03 (p = 0,81).
  - O ρ com o afastamento lateral é de +0,36 (p = 0,004).
  - Na C3 e na C4, os dois ρ ficam entre −0,04 e +0,18, sem significância.
- **O que a conta mostra (leitura depois de ver os dados, só relatada):**
  - **as quatro linhas codificadas têm a curvatura de 4 a 5 vezes mais rugosa que a do C0** (de 1,32 a 1,46 × 10⁻³ contra 0,31 × 10⁻³ 1/m, média dos pontos). A rugosidade é comum às quatro e não separa a C1 da C3;
  - **o menor raio do arquivo no trecho C14→linha é de 85 m na C1 e de 90 m na C2,** em 3.898 m, justo onde a IA freia. Na C3 e na C4, ele é de 134 e 136 m, e no C0, de 226 m. Nas três, a IA não freia;
  - **a perda grande da codificação parece vir de um raio fechado num ponto só,** e não de uma rugosidade espalhada. A medida registrada (a média numa janela de 20 m por microssetor) não pega isso.

### A linha do Eduardo (item 7 e item 8, só relatados)

- **As 136 voltas:** a mediana fica atrás do C0 em 14 dos 15 trechos. A exceção é a C06 (−0,023 s). A melhor volta de cada trecho fica à frente do C0 em 12 deles.
- **As 9 de 24/10:** a mediana fica atrás em 14 trechos e à frente na C06 (−0,385 s).
- **A linha:** a distância da mediana dele à linha da IA fica dentro do limite (o percentil 90 da repetibilidade dele) em 43 dos 45 pontos. Ela passa do limite na saída da C08 (6,31 m contra 3,71 m) e na saída da C13 (4,96 m contra 3,58 m).
  - O limite vai de 1,44 a 6,11 m, porque as 136 voltas juntam semanas diferentes.
  - A fração do trecho acima do limite chega a 0,45 na C14 e é zero em 8 trechos.
- **A execução:**
  - ele começa a frear antes da IA na C01 (52 m), na C04 (32 m), na C06 (58 m), na C07 (25 m), na C10 (10 m) e na C12 (45 m);
  - o freio máximo dele (mediana de 0,15 a 0,75) fica abaixo do da IA (0,80 a 0,99);
  - a mínima dele é mais baixa em 11 trechos;
  - ele usa uma marcha acima da IA em 8 trechos (contando sem o neutro da troca).
- **As propostas provisórias:**
  - **a rampa do freio** vai de 7,5 m (C10) a 35,7 m (C01) nos 7 trechos com pelo menos 5 voltas com frenagem;
  - **o ponto de frenagem traduzido** sai nos 6 trechos em que a IA também freia: C01 100,3 m, C04 1.174,7 m, C06 1.877,2 m, C07 2.183,3 m, C10 2.644,6 m e C12 3.100,5 m;
  - nos outros 9 trechos, ele fica "sem dados".

### O teto (só relatado)

**A linha mais rápida de cada trecho, somada, dá 84,712 s contra 85,438 s do C0 (−0,726 s).** É um teto, e não uma previsão. Ele junta a C2 na C04, a C3 na C06, na C11 e na C12, a C4 na C07, na C08, na C09 e na C13, e a C1 na C14.

### O que se esperava (item 10) e o que veio

| item | esperado | resultado |
|---|---|---|
| 1 | ganho na C06 e talvez na C08; perda no C01/C02, C03, C07 e C10 | **em parte:** ganho na C06 e na C09 (não na C08); perda no C02, C03 e C10 nas duas, no C01 só na C4, no C07 só na C3 |
| 2 | 0,1 s ou mais passa no Holm contra o C0 | **sim** |
| 3 | quase nada passa contra o C0 final; no máximo a C06 | **não:** o desvio por trecho vai de 0,002 a 0,12 s, quase sempre abaixo de 0,03 s, e a separação completa é comum; 5 candidatas |
| 4 | a deriva se espalha, sem trecho no Holm | **não:** 3 trechos passam, no fim da volta |
| 5 | a C1 perde em quase todos, mais nos longos e rápidos | **em parte:** 9 perdas; a maior é a C14→linha (+0,836 s), mas a C11 empata e a C12 perde +0,366 s |
| 6 | a curvatura explica mais que as dicas | **nenhuma das duas, como registradas;** um raio fechado num ponto explica a maior perda (leitura depois de ver os dados) |
| 7 | o Eduardo perde em quase todos, mais pela execução; a linha passa do limite no ápice das curvas lentas | **em parte:** perde em 14 de 15 e freia antes; a linha passa do limite só em 2 saídas (C08 e C13) |
| 8 | teto de −0,2 a −0,5 s | **não:** −0,726 s |

### Duas leituras acrescentadas depois de ver os dados (só relatadas, fora das regras)

1. **A marcha sem o neutro da troca.** O gravador guarda a marcha como `gear − 1` do jogo (−1 é a ré, 0 o neutro e 1 a primeira). O carro passa pelo neutro em cada troca, de 2 a 6 m na grade (16 m no máximo, nas voltas do pedido 44). Por isso, a marcha mínima do item 5 sai 0 em todo trecho com troca. A leitura sem o neutro ignora o 0 e junta `5 → 0 → 4` em `5 → 4`. A medida registrada continua no JSON.
2. **O menor raio do arquivo em cada trecho,** para a frenagem da IA no trecho C14→linha.

### O que isto quer dizer

- **Há onde a linha gerada ganha no jogo,** com a mesma IA: na C06 (−0,22 a −0,23 s, com cerca de 20 km/h a mais de mínima) e na C09 (−0,10 a −0,14 s). São candidatas para um teste novo no jogo, e não referências.
- **A referência de todos os trechos continua sendo a linha da IA (C0).**
- **O custo da codificação parece vir de pontos com o raio fechado** (85 m num trecho de 226 m), mais do que de uma rugosidade espalhada. Isso é uma pista para a codificação de um próximo pedido, e não uma conclusão.
- **O coach não muda,** e o ADR 0009 continua como está.
