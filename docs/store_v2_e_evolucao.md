# Store v2 e relatório de evolução (pedido 16)

Branch: `etapa/store-v2`, a partir de `develop` (`40937092`).

## 1. Registrado antes de construir e de rodar

Esta seção foi commitada antes de o store v2 ser construído e antes de o relatório de evolução rodar pela primeira vez. Nada nela muda depois de olhar os resultados.

### 1.1 O que entra no store v2

- **De onde vêm as voltas:** do inventário rotulado (`data/ml/origem/lap_inventory.parquet`, o do `atualizar_coach`), com as duas pastas de gravações.
- **Quais entram:**
  - só voltas válidas pelos portões de qualidade (`valid`);
  - sem as marcadas com `duplicada_de`;
  - sem passagem pelo box (portão novo, detalhado a seguir).
- **Todas as origens entram.** O store guarda as colunas `origem`, `origem_fonte`, `equipamento`, `relogio_verificado`, `relogio_suspeito`, `pasta` e `carModel` (da gravação, quando houver), e quem lê filtra.
- **Portão do box:** é a detecção do pedido 12 (`ai_detector.pit_lap`). A volta passa pelo box quando, nos microsetores perto da linha (0 a 3 e 57 a 59), fica a mais de 10 m da linha central e abaixo de 90 km/h. Ela é medida na grade da própria volta.
- **Correção do período:** o relógio da grade passa a ser zerado na linha (s = 0) com o período verdadeiro da volta.
  - **Antes:** o período era o `span` dos tempos na grade, um passo mais curto que a volta.
  - **O período verdadeiro** é o tempo entre duas passagens por s = 0, no cronômetro do jogo. Em cada ponta, o tempo da passagem é a mediana, entre as amostras a até 15 m da linha, de `t + (s_linha − s)/v`, com a velocidade gravada. Uma amostra com o cronômetro repetido não desloca a passagem.
  - O tempo de volta do store v2 (`lap_time_s`) é esse período.
- **Onde fica:** `data/ml/laps_grid_v2.parquet` e `data/ml/laps_grid_v2_meta.json`. O store antigo (`laps_grid.parquet`) e os scripts das Fases 1, 2 e 2b não mudam.
- **Meta (ADR 0007):**
  - `geometry_id` e `source_hash` da geometria;
  - o commit;
  - o sha256 e o tamanho de cada entrada lida: o inventário, os rótulos de 04/10 e cada `player.jsonl` que deu volta ao store.

### 1.2 Efeitos esperados

Nas voltas que estão nos dois stores:

- **Toda volta e o microsetor 0 sobem cerca de 26 ms:** a mediana da diferença v2 − antigo fica entre +20 e +35 ms, e é o tempo de um passo da grade na reta.
- **Os outros 59 microsetores quase não mudam:** p99 de \|diferença\| abaixo de 5 ms.

E no store:

- **As voltas com box saem.** O relatório conta quantas o portão tirou.
- **As duplicatas saem.** O relatório conta quantas.

### 1.3 Checagens

| | checagem | passa quando |
|---|---|---|
| **principal** | O período de s = 0 a s = 0 bate com o cronômetro do jogo | em toda volta do store v2 com o fechamento medido, p99 de \|período − tempo do jogo\| ≤ 5 ms |
| 2 | Nenhuma volta passa pelo box | `pit_lap` falso em todas as voltas do store v2 |
| 3 | Nenhuma volta aparece duas vezes | `lap_id` único, nenhuma volta com `duplicada_de`, e nenhum par de voltas de pastas diferentes com mais de 50% do intervalo de relógio de parede em comum |
| 4 | Uma geometria só | todas as voltas com o mesmo `geometry_id`, igual ao da geometria carregada |

**O tempo do jogo,** para a checagem principal:

- **Como é medido:** o gravador só tem o cronômetro da volta corrente (`lap_time`), que zera na linha. Por isso o tempo de volta do jogo é o cronômetro no instante em que zera, costurado pela distância e pela velocidade entre as últimas amostras da volta e as primeiras da seguinte.
  - Para cada par (uma das 5 últimas amostras da volta e uma das 5 primeiras da seguinte), vale `t_antes + distância/velocidade média − t_depois`.
  - O tempo do jogo é a mediana dos pares.
- **Quando é medido:** só quando a volta seguinte começa na mesma gravação, a até 50 m e 0,5 s da última amostra.
- **Voltas sem fechamento medido** (a última de uma gravação, por exemplo) ficam fora da checagem e são contadas no relatório.
- **Controle:** a mesma conta, feita no store antigo, deve dar cerca de −26 ms. Isso mostra que a checagem enxerga o erro que veio corrigir.

**Se a checagem principal falhar, o trabalho para aqui** e o relatório vai para o Eduardo, sem merge.

### 1.4 Regras do relatório de evolução

- **Voltas:**
  - do store v2;
  - `humano`, equipamento `atual`;
  - válidas (todas as do store v2 são), relógio conferido e sem `relogio_suspeito`.
- **Sessão:** as gravações do mesmo dia, pela data no nome da gravação. A sessão de 04/10 junta as 7 gravações daquele dia.
- **Referência:** a volta da IA do coach (`volta_ia`) do modelo do repositório (`data/reference_models/vhe_interlagos.json`), lida do store v2 pelo `lap_id`. Se ela não estiver no store v2, o relatório para.
- **Unidades:** as 14 curvas de `detect_corners`. Os microsetores ficam como detalhe.
  - **Trecho de cada curva:** vai do meio da reta anterior ao meio da reta seguinte. A fronteira é o ponto médio entre o fim de uma curva e o início da próxima.
  - Os 14 trechos cobrem a volta inteira, então a soma das perdas por curva é a diferença de tempo de volta.
- **Perda para a IA, por curva e volta:** o tempo do trecho na volta menos o tempo do trecho na volta da IA, com o relógio do store v2.
  - Por sessão: a mediana e o intervalo interquartil (p25 a p75).
- **Diferença consistente:** o intervalo de 90% da perda mediana não inclui zero.
  - O intervalo é por bootstrap: 2000 reamostragens das voltas da sessão, com reposição e semente fixa, pelos percentis 5 e 95.
  - O relatório diz o lado: perde ou ganha para a IA.
- **Poucos dados:** com menos de 5 voltas na sessão, a curva fica "poucos dados", sem intervalo.
- **Ponto de frenagem em relação à IA:**
  - **Onde procurar:** no trecho, do início do trecho ao ápice da curva. Esta regra foi trocada pela emenda da seção 1.5.
  - **O ponto de frenagem:** o primeiro ponto em que o freio passa de abaixo de 0,15 para 0,15 ou mais. É o limiar da Fase 2b.
  - **A diferença:** em metros de pista, volta menos IA; positivo é frear depois da IA.
  - **Casos sem número:**
    - curva em que a IA não freia: fica sem número;
    - volta sem frenagem no trecho: fica fora da mediana daquela curva.
  - **Por sessão:** a mediana e o intervalo interquartil.
- **Posição lateral no ápice em relação à linha da IA:** a lateral da volta menos a da IA, no ápice da curva. Positivo é mais à esquerda (ADR 0003). Por sessão: a mediana e o intervalo interquartil.
- **Velocidade mínima em relação à IA:** a mínima dentro da curva (do início ao fim dela), volta menos IA. Por sessão: a mediana.
- **Por sessão:**
  - o número de voltas;
  - a melhor volta, a mediana e o desvio-padrão;
  - a diferença para a volta da IA: a mediana menos a IA, e a melhor menos a IA.
- **Entre sessões:**
  - a série das medianas de volta, com a tendência: a inclinação da reta de mínimos quadrados, em segundos por sessão, a partir de 2 sessões;
  - as 3 curvas de maior perda mediana na sessão mais recente, com a série delas.
- **Critério do ADR 0015:** com 3 sessões ou mais, a diferença entre a maior e a menor mediana de volta das últimas 3 sessões é menor que 0,5 s. Com menos de 3 sessões, ainda não dá para avaliar.

### 1.5 Emenda de 04/10/2026 (pedido 17): janela de frenagem

Registrada antes de rodar de novo, depois de ver a falha na C10 na primeira rodada (seção 4).

- **Onde procurar o início da frenagem de uma curva:** passa a ir do ápice da curva anterior até o ápice da curva. Para a C01, a anterior é a C14, e a janela cruza a linha de chegada.
- **O que não muda:**
  - o trecho usado para o tempo de cada curva;
  - o ponto de frenagem, que continua sendo o primeiro em que o freio passa de abaixo de 0,15 para 0,15 ou mais;
  - os casos sem número;
  - os critérios de "diferença consistente" e de "poucos dados".
- **Natureza da mudança:** é uma definição de medida, e não um limite de decisão. Nenhum critério foi mexido.

## 2. O que mudou no store (Parte B)

O store v2 é um arquivo novo: `data/ml/laps_grid_v2.parquet`, com o meta em `laps_grid_v2_meta.json`. Ele é construído por `python -m ml.scripts.build_lap_store_v2`, e o `atualizar_coach` também o refaz.

O store antigo (`laps_grid.parquet`, 122 voltas) continua intacto, e os scripts das Fases 1, 2 e 2b continuam lendo ele.

| | store antigo | store v2 |
|---|---|---|
| relógio da grade | zerado em s = 0 com o `span` da grade, um passo mais curto que a volta | zerado em s = 0 com o período verdadeiro (`resample_lap(..., line_clock=True)`) |
| voltas com box | entravam | saem (`pit_lap`, a detecção do pedido 12) |
| pastas | só a do repositório | as duas, sem as cópias `duplicada_de` |
| origens | só `humano` (na prática, o rótulo antigo) | todas, com `origem`, `origem_fonte`, `equipamento`, `relogio_*`, `pasta` e `carModel` em cada volta |
| tempo do jogo | não tinha | `tempo_jogo_s`, o cronômetro do jogo costurado na troca de volta |
| meta | geometria | geometria, commit, sha256 e tamanho do inventário, dos rótulos de 04/10 e de cada gravação usada (ADR 0007), e o resultado das checagens (`aprovado`) |

### Contagem

- **Entrada:** 1.952 voltas no inventário, 720 válidas.
- **Saídas:**
  - 4 duplicatas;
  - 138 voltas com passagem pelo box.
- **Resultado:** 578 voltas no store v2.

| origem | equipamento | pasta | voltas |
|---|---|---|---:|
| desconhecida | anterior | app_instalado | 451 |
| desconhecida | anterior | repositorio | 101 |
| humano | atual | repositorio | 11 |
| ia | atual | repositorio | 13 |
| misturada | atual | repositorio | 2 |

As 101 voltas antigas do repositório são exatamente as 122 do store antigo menos as 21 com box que o pedido 12 tinha apontado.

## 3. As checagens

Todas passaram. O meta saiu com `aprovado: true`.

| checagem | resultado |
|---|---|
| **principal:** período contra o cronômetro do jogo, p99 de \|diferença\| ≤ 5 ms | **passou.** As 578 voltas têm o fechamento medido. A diferença tem mediana de +0,7 ms e vai de −3,1 a +3,3 ms entre o p1 e o p99; o p99 de \|diferença\| é 3,9 ms. |
| nenhuma volta passa pelo box | passou: 0 voltas com `pit_lap` |
| nenhuma volta duas vezes | passou: `lap_id` únicos, nenhuma `duplicada_de` e nenhum par sobreposto entre as pastas |
| uma geometria só | passou: `0ed16f0dd2225990` |

**As 4 voltas acima de 5 ms:**

- uma volta de 125,1 s com parada no meio, já marcada com `relogio_suspeito` (`2026-08-19_20-58-36#0011`, −20,1 ms);
- três gravações de 14/06 a 31 Hz, com metade da amostragem: −8,2, −5,5 e +7,4 ms.

**Efeitos esperados,** nas 101 voltas que estão nos dois stores:

- **a volta sobe** 27,8 ms (mediana);
- **o microsetor 0 sobe** 27,2 ms (mediana);
- **os outros microsetores** mudam no máximo 0,6 ms (p99).

Tudo isso dentro do registrado.

**Controle:** o store antigo, contra o mesmo cronômetro do jogo, fica 27,3 ms curto (mediana) e não passaria na checagem principal. A checagem enxerga o erro que veio corrigir.

O relatório completo fica em `data/ml/store_v2_relatorio.json`.

## 4. Relatório de evolução (Parte C)

```
..\.venv\Scripts\python.exe tools\relatorio_evolucao.py
```

O comando roda na pasta `backend`, em cerca de 5 segundos. Ele lê o store v2 e para se o meta não estiver `aprovado`. Também para se a volta da IA do coach não estiver no store v2.

O `atualizar_coach.py` agora faz, no fim, dois passos novos:

- o passo 6 refaz o store v2 com as checagens;
- o passo 7 chama este relatório.

O store v2 entra no comando para as sessões novas chegarem ao relatório.

**Conferido de ponta a ponta:** `atualizar_coach.py --sem-varrer` rodou os 7 passos em `develop`, depois do merge. Levou 667 s e saiu com código 0; com a varredura, o comando completo leva cerca de 26 minutos.

- O store v2 e o relatório saíram iguais aos da primeira rodada.
- O modelo do app instalado (`9d08d705…`) e o store antigo (`laps_grid.parquet`, `a9798c3a…`) não mudaram.

### Como ler

- **Sessão:** as gravações do mesmo dia.
- **Perda para a IA por curva:** quanto tempo você gasta a mais que a volta da IA do coach no trecho da curva, do meio da reta anterior ao meio da seguinte. Positivo é mais lento que a IA.
- **Situação de cada curva:**
  - `diferenca_consistente`: o intervalo de 90% da perda mediana não inclui zero. O campo `lado` diz se você perde ou ganha.
  - `sem_diferenca_consistente`: o intervalo inclui zero.
  - `poucos_dados`: menos de 5 voltas na sessão.
- **Frenagem:** em metros, positivo é frear depois da IA. Desde o pedido 17, o início é procurado do ápice da curva anterior ao ápice da curva (seção 1.5). Fica vazia quando a IA não freia nessa janela (`ia_freia: false`) ou quando nenhuma volta sua começa a frear dentro dela.
- **Lateral no ápice:** positivo é mais à esquerda que a IA. A interface deve dizer o lado em palavras (ADR 0003).

### Primeira rodada: a linha de base, sessão de 04/10

- **Voltas:** 11.
- **Tempos:** melhor de 89,39 s, mediana de 93,46 s e desvio de 2,40 s.
- **Diferença para a volta da IA (84,83 s):** a mediana fica 8,63 s acima, e a melhor, 4,56 s acima.

A coluna de frenagem desta tabela é da regra original. A versão com a janela emendada está na seção 6.

| curva | perda mediana (s) | intervalo de 90% (s) | situação | frenagem vs IA (m) | lateral no ápice (m) | mínima vs IA (km/h) |
|---|---:|---|---|---:|---:|---:|
| C01-esq | +1,27 | 1,03 a 1,59 | perde | −66 (11 voltas) | −0,85 | −4,1 |
| C02-dir | +0,06 | −0,04 a 0,07 | sem diferença consistente | — | −0,11 | −1,5 |
| C03-esq | +0,51 | 0,36 a 0,59 | perde | IA não freia | −0,78 | −0,6 |
| C04-esq | +0,73 | 0,56 a 0,79 | perde | −48 (11) | −0,47 | −11,4 |
| C05-esq | +0,32 | 0,19 a 0,51 | perde | IA não freia | −2,21 | −11,9 |
| C06-dir | +0,56 | 0,30 a 0,71 | perde | −72 (9) | −3,85 | −3,5 |
| C07-dir | +0,51 | 0,40 a 0,73 | perde | +40 (5) | +1,06 | −6,7 |
| C08-esq | +0,28 | 0,23 a 0,55 | perde | +32 (1) | −0,04 | +3,6 |
| C09-dir | +0,35 | 0,18 a 0,35 | perde | IA não freia | −1,69 | −20,3 |
| C10-dir | +0,79 | 0,63 a 0,89 | perde | — | +1,21 | −7,3 |
| C11-esq | +0,79 | 0,62 a 1,42 | perde | IA não freia | −0,57 | −20,4 |
| C12-esq | +0,64 | 0,50 a 1,07 | perde | −2 (3) | −0,89 | +0,4 |
| C13-esq | +0,17 | 0,16 a 0,23 | perde | IA não freia | −2,23 | −5,6 |
| C14-esq | +0,35 | 0,24 a 0,73 | perde | IA não freia | −2,49 | −6,6 |

- **Diferença consistente:** 13 das 14 curvas. A exceção é a C02.
- **As 3 de maior perda:** C01, o S do Senna (1,27 s); C11 (0,79 s); e C10 (0,79 s).
- **Tendência e critério do ADR 0015:** ainda não dá para calcular, com uma sessão só (1 de 3).
- **A soma das perdas medianas por curva** é 7,33 s. Ela não precisa bater com a mediana da volta menos a IA (8,63 s), porque a soma de medianas não é a mediana das somas. Volta a volta, a soma das 14 perdas é exatamente a diferença para a IA.

### Limitação encontrada na primeira rodada

**A janela de frenagem perde frenagens que começam no trecho anterior.** A regra registrada procura o início da frenagem do começo do trecho até o ápice da curva. Com duas curvas próximas, a frenagem da segunda pode começar ainda no trecho da primeira, depois do ápice dela.

- **Na C10,** a IA começa a frear em 2.622 m, depois do ápice da C09 (2.610 m) e antes do trecho da C10 (2.649 m). Dentro do trecho, o pedal da IA pulsa em torno de 0,15, e nenhuma volta sua tem um início de frenagem ali.
- **Na C02,** você vem freando da C01.
- **Na C07, C08 e C12,** só algumas voltas têm ponto de frenagem.

A regra não foi mudada depois de ver o resultado. Uma opção para a próxima versão é começar a janela de frenagem no ápice da curva anterior, e ela fica para decisão sua.

O Eduardo decidiu adotar essa opção no pedido 17 (seções 1.5 e 6).

## 5. Formato dos JSONs

Os arquivos ficam em `data/ml/evolucao/`, fora do git:

- `sessao_<AAAA-MM-DD>.json`, um por sessão;
- `resumo.json`.

Todos os tempos estão em segundos, as distâncias em metros e as velocidades em km/h. Valor `null` quer dizer que não deu para medir.

### `sessao_<AAAA-MM-DD>.json` (`formato: "evolucao-sessao/1"`)

| campo | o que é |
|---|---|
| `sessao` | o dia (`2026-10-04`) |
| `gravacoes` | as gravações do dia que deram voltas |
| `resumo` | `voltas`, `melhor_s`, `mediana_s`, `desvio_s` (desvio-padrão amostral), `volta_da_ia_s`, `mediana_menos_ia_s`, `melhor_menos_ia_s` e `poucos_dados` (menos de 5 voltas) |
| `voltas[]` | `volta` (o `lap_id`), `gravacao` e `tempo_s` (o período do store v2), na ordem em que foram feitas |
| `curvas[]` | uma por curva, na ordem da pista (a tabela abaixo) |
| `microsetores[]` | `microsetor` (0 a 59), `perda_mediana_s`, `p25_s` e `p75_s` contra a volta da IA |
| `referencia` | `tipo` (`volta_ia`), `volta`, `tempo_s` e `modelo`, o arquivo do coach de onde veio |
| `store` | `arquivo`, `sha256`, `commit_do_store` e `geometry_id` do store v2 lido |
| `regras` | onde estão as regras (este documento, seção 1.4) |

Campos de cada item de `curvas[]`:

| campo | o que é |
|---|---|
| `curva`, `indice` | o rótulo (`C01-esq`) e a posição (1 a 14) |
| `trecho_m` | `[início, fim]` do trecho; o da C01 cruza a linha (`[4112.1, 346.0]`) |
| `curva_m`, `apice_m` | início e fim da curva, e o ápice, pela curvatura da linha central |
| `perda_para_ia_s` | `mediana`, `p25`, `p75`, `iqr` e `voltas` |
| `situacao`, `lado`, `intervalo_90_s` | `diferenca_consistente`, `sem_diferenca_consistente` ou `poucos_dados`. `lado` é `perde`, `ganha` ou `null`. `intervalo_90_s` é `[baixo, alto]` ou `null` com poucos dados |
| `ia_freia` | se a volta da IA tem início de frenagem na janela de busca (do ápice da curva anterior ao ápice da curva) |
| `frenagem_vs_ia_m` | `mediana`, `p25`, `p75`, `iqr` e `voltas`, só das voltas com início de frenagem na janela; `null` quando a IA não freia ou nenhuma volta freia nela |
| `lateral_apice_vs_ia_m` | `mediana`, `p25`, `p75`, `iqr` e `voltas` |
| `velocidade_minima_vs_ia_kmh` | `mediana` |
| `por_volta[]` | `volta`, `perda_s`, `frenagem_vs_ia_m`, `lateral_apice_vs_ia_m` e `velocidade_minima_vs_ia_kmh` de cada volta |

### `resumo.json` (`formato: "evolucao-resumo/1"`)

| campo | o que é |
|---|---|
| `sessoes[]` | por sessão, em ordem de data: `sessao`, `voltas`, `melhor_s`, `mediana_s`, `desvio_s`, `mediana_menos_ia_s`, `melhor_menos_ia_s`, `poucos_dados` e `curvas_com_diferenca_consistente` |
| `tendencia_mediana_s_por_sessao` | inclinação da reta da mediana de volta, em s por sessão; `null` com menos de 2 sessões. Negativo é melhorar |
| `curvas_de_maior_perda[]` | as 3 de maior perda mediana na sessão mais recente, cada uma com `serie[]` (`sessao`, `perda_mediana_s`, `situacao`) e `tendencia_s_por_sessao` |
| `criterio_adr_0015` | `limite_s` (0,5), `sessoes_necessarias` (3), `sessoes_disponiveis`, `amplitude_s` (maior menos menor mediana das últimas 3), `estabilizou` (`true`, `false` ou `null`) e `situacao` em texto |
| `referencia`, `store`, `regras` | como no JSON da sessão |
| `arquivos_de_sessao` | os caminhos dos JSONs de sessão |

## 6. Pedido 17: janela de frenagem e painel

### Janela de frenagem: antes e depois, sessão de 04/10

- **Antes:** a regra do pedido 16, do início do trecho ao ápice.
- **Depois:** a emenda da seção 1.5, do ápice da curva anterior ao ápice.
- **O que ficou igual:** o tempo dos trechos. As perdas, os intervalos de 90% e a situação das 14 curvas não mudaram.

| curva | antes: mediana (voltas com ponto) | depois: mediana (voltas com ponto) | depois: p25 a p75 |
|---|---|---|---|
| C01-esq | −66 m (11 de 11) | −66 m (11 de 11) | −95 a −58 m |
| C02-dir | sem ponto (0) | sem ponto (0) | — |
| C07-dir | +40 m (5) | −28 m (10) | −38 a −14,5 m |
| C08-esq | +32 m (1) | −17 m (2) | −41,5 a +7,5 m |
| C10-dir | sem ponto (0) | −11 m (4) | −12 a −9,5 m |
| C12-esq | −2 m (3) | −34 m (10) | −42 a −30 m |

- **C07 e C12:** antes, só entravam as voltas em que você freava já dentro do trecho, que são as mais tardias. Por isso a mediana saía perto de zero ou positiva. Com a janela nova, quase todas as voltas entram, e você freia antes da IA: 28 m na C07 e 34 m na C12.
- **C02:** você não freia entre o ápice da C01 e o da C02 em nenhuma volta, e a IA só dá um toque em 360 m.
- **C10 (Bico de Pato):**
  - A IA começa a frear em 2.622 m, logo depois do ápice da C09 (2.610 m).
  - Em 7 das 11 voltas, você começa antes desse ápice, entre 2.588 e 2.608 m. Essas voltas continuam sem ponto pela regra, e por isso só 4 entram.
  - **Diagnóstico, fora da regra:** procurando desde o ápice da C08, você começa a frear de 2.588 a 2.614 m, uma mediana de 14 m antes da IA.
- **C08:** só 2 voltas têm ponto.

**Correção de implementação feita junto:**

- **A falha:** a busca não via uma freada que começa exatamente no primeiro ponto da janela, porque não olhava o ponto anterior. A definição inclui o ápice da curva anterior, então era um erro do código, não da regra.
- **Onde aparecia:** em 2 voltas da C10, a freada começa exatamente em 2.610 m.
- **A correção:** o ponto anterior entra só para ver a subida do pedal. Com ela, a C10 passou de 2 para 4 voltas com ponto.

O arquivo com as 14 curvas e o diagnóstico é `docs/handoff/2026-10-04_painel-evolucao_frenagem_antes_depois.json`.

### Painel local

- **O modelo:** o Claude (Cowork) desenhou o painel, e ele fica em `backend/tools/painel_evolucao.html`, ao lado do `relatorio_evolucao.py`. A pasta de anexos do pedido foi apagada.
- **Como é gerado:** o `relatorio_evolucao.py` grava `data/ml/evolucao/painel.html` trocando o marcador `/*DADOS*/` por um JSON com:
  - `resumo`: o `resumo.json`;
  - `sessoes`: cada sessão pela data;
  - `pista`: `x` e `z` da linha central da geometria oficial exportada (`data/reference_models/vhe_interlagos.geometry.json`, 2.167 pontos), `ds` (2,00004 m) e `L` (4.334,08 m);
  - `carro`: o `carModel` das sessões;
  - `pista_nome`: "Interlagos".
- **Proteção do JSON:** o `<` dos dados é escrito como `\u003c`, para nenhum texto fechar o `<script>`.
- **Travas:** o relatório para se a geometria exportada faltar ou não for a do store v2.
- **Para abrir:** abra o `painel.html` no navegador. Ele não precisa de servidor; as fontes vêm do Google Fonts quando há internet.
- **No `atualizar_coach.py`:** ele imprime no fim o caminho do painel.

**O que mudou no modelo:** só uma frase. Quando não há ponto de frenagem, ela dizia "A busca começa no trecho da curva, e a freada desta curva começa antes dele (correção em andamento)", o que deixou de ser verdade. Agora diz "Sem ponto de frenagem medido aqui: em nenhuma volta você começa a frear entre o ápice da curva anterior e o ápice desta." O desenho não mudou.

**Conferido no navegador do app,** com os dados de 04/10:

- o painel desenha os números, o mapa de Interlagos com as curvas coloridas, as listas e o detalhe, sem erro no console;
- depois da correção de implementação, a C10 mostra "Você freia 11 m antes da IA; metade das voltas entre 9 e 12 m antes. Medido em 4 de 11 voltas."
