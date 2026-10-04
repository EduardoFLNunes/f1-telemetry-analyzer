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
  - **Onde procurar:** no trecho, do início do trecho ao ápice da curva.
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
