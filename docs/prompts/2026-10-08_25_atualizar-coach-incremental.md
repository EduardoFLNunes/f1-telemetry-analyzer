# Pedido 25 — Modo incremental do `atualizar_coach`: ler só as gravações novas, com o mesmo resultado do comando completo

**De:** Eduardo (o plano é meu). **Data:** 08/10/2026.
**Tipo:** engenharia (desempenho) e documentação. Nenhum resultado muda: rótulos, detector, treino do coach, checagens do store v2 e relatório de evolução continuam iguais.

## Contexto

1. **O backlog registra:** "atualizar_coach leva ~16 min; criar um modo incremental". Com o store v2 e o relatório de evolução (pedido 16), o comando completo passou a levar cerca de 26 min:
   - a varredura do inventário (passo 1), cerca de 13 min;
   - o store v2 (passo 6), cerca de 10 min;
   - com `--sem-varrer`, o pedido 16 mediu 667 s.

   Os dois passos releem todas as gravações das duas pastas a cada sessão nova.
2. **Por que agora:** vou gravar as 5 sessões com o app aberto a partir do repositório, que são a condição da M1 (ADR 0017). Depois de cada uma, rodo o `atualizar_coach`.
3. **O que pode ser reaproveitado, pelo código atual:**
   - **Passo 1:** `scan_sessions` (`backend/ml/data/inventory.py`) lê cada sessão de forma independente. Isso inclui limpeza, alinhamento, portões, conferência do relógio e identidade (`classify`). O gancho de `report_lap_origin.scan` monta, volta a volta, as tabelas de relógio, sinais e grade. Só duas operações cruzam sessões, e as duas trabalham sobre a tabela pronta, sem abrir gravação: `mark_duplicates` e `mark_clock`.
   - **Passo 6:** `build_store_v2` (`backend/ml/data/store_v2.py`) lê cada sessão de forma independente para materializar as voltas na grade, o tempo do jogo e a marca de box. Já os rótulos de cada volta (`CARRIED_COLUMNS`) e o `carModel` vêm do inventário e das anotações, sem abrir gravação.
   - **Passos 2 a 5 e 7:** leem as tabelas e só as voltas escolhidas. Não mudam.
4. **Pendências pequenas do pedido 24** entram na Parte E.

## Princípio, fixado antes do código

**O modo incremental tem de dar exatamente o mesmo resultado que o comando completo.** O critério de comparação é este:

- **tabelas** (inventário, as três tabelas de `data/ml/origem/` e o store v2): mesmas colunas, mesmos tipos, mesma ordem de linhas e valores idênticos (NaN igual a NaN);
- **JSONs:** mesmas chaves e mesmos valores. Ficam fora da comparação só os campos de data e hora, de duração, de commit e de caminho de backup, mais o campo novo `construcao` do meta (Parte C). Liste no relatório cada campo excluído e onde ele aparece.

Se alguma comparação falhar, o incremental **não vira o padrão**. Pare, registre a diferença (arquivo, coluna, quantas linhas e um exemplo) e deixe a decisão para mim. Nada é ajustado depois de ver o resultado.

## Parte A — Medição do comando atual (antes do código)

1. **Em `develop`, depois do merge `5e1bd317`, com o app fechado,** rode o `tools/atualizar_coach.py` completo e meça:
   - o tempo de cada um dos 7 passos;
   - no passo 1, o tempo de leitura das sessões e o de gravação das tabelas;
   - no passo 6, o tempo da materialização das voltas, do sha256 das gravações (`file_entry`, para o meta), das checagens e da gravação.

   Pode medir com `cProfile` ou com marcações de tempo. Uma impressão permanente do tempo de cada passo no fim do comando é bem-vinda.
2. **Guarde as saídas dessa rodada como "referência completa"** em `data/ml/_p25_referencia_completa/`, fora do git:
   - o inventário e as três tabelas de `data/ml/origem/`;
   - `detector_aplicar.json` e `atualizar_coach.json`;
   - o store v2, o meta e `store_v2_relatorio.json`;
   - o modelo do coach (`data/reference_models/vhe_interlagos.json`);
   - os JSONs de `data/ml/evolucao/`.
3. **Para dar o contexto, relate também:** o número de sessões e de voltas e o tamanho total das gravações lidas.

## Parte B — Inventário incremental (passo 1)

1. **Cache por gravação** em `data/ml/origem/cache/`, fora do git. Para cada sessão, ele guarda:
   - as linhas do inventário **antes** de `mark_duplicates` e `mark_clock`, já com a identidade de `classify`;
   - as linhas das três tabelas: relógio, sinais e grade.

   Guarde as linhas no mesmo formato em que o caminho completo as monta (a lista de dicionários do inventário e dos sinais, os blocos do relógio e da grade). Assim, os tipos das colunas saem iguais quando a tabela é montada.
2. **Manifesto** (`manifesto.json`) com:
   - **por sessão:** o `session_id`, a pasta (`repositorio` ou `app_instalado`), os arquivos que a leitura abre e o tamanho e a data de modificação de cada um;
   - **chave global:** `geometry_id`, os portões (`config.DEFAULT_GATES`), a versão do formato do cache e o sha256 dos arquivos de código que mudam a leitura. A lista desses arquivos fica explícita no código e no relatório. Na dúvida, entra: `ml/preprocessing/`, `ml/track/`, `ml/config.py` e os módulos de `ml/data/` e `ml/scripts/` que a varredura usa.
3. **A cada rodada:**
   - liste as sessões como hoje (`list_all_sessions`);
   - sessão com os mesmos tamanhos e datas sai do cache; sessão nova ou mudada é lida e atualiza o cache; sessão que sumiu do disco sai do inventário e do cache e aparece listada no resumo;
   - depois, sobre a tabela inteira, faça as etapas que cruzam sessões exatamente como hoje: ordenação por `session_id` e `sequence`, `mark_duplicates`, `mark_clock`, e a gravação do inventário e das três tabelas, nos mesmos arquivos e no mesmo formato.
4. **Um caminho só:** separe de `scan_sessions` uma função que lê uma sessão. Os dois modos, completo e incremental, chamam essa mesma função. Nada da lógica de leitura fica duplicado.
5. **Quando o cache inteiro é refeito:**
   - a chave global mudou (geometria, portões, código ou formato);
   - o cache não abre.

   Nos dois casos, o comando faz a varredura completa, imprime o motivo e o grava no resumo. Nunca há mistura de cache velho com cache novo.
6. **Confira um risco da ordenação:** pode haver duas linhas com o mesmo `session_id` e `sequence`, por exemplo a mesma sessão nas duas pastas? Se puder, a ordem entre elas precisa sair igual nos dois modos.

## Parte C — Store v2 incremental (passo 6)

1. **Cache por gravação** em `data/ml/cache_store_v2/`, fora do git. Para cada sessão, ele guarda:
   - os blocos materializados de cada volta (a grade com os canais físicos);
   - os campos medidos: `lap_time_s`, `tempo_jogo_s`, `sample_hz`, `raw_samples`, `coverage` e as velocidades;
   - a marca de box e os canais de cada volta (`channels_by_lap`);
   - o sha256 do `player_stream`, para o `entradas.gravacoes` do meta.
2. **Recalculado sempre, a partir do inventário e das anotações atuais:**
   - a seleção (`select_v2`);
   - os rótulos (`CARRIED_COLUMNS`);
   - o `carModel` (`car_for`, com as anotações);
   - `recording_periods`;
   - as checagens (`store_checks.run_checks`);
   - o meta.

   Assim, um rótulo que o detector ou uma anotação mudou chega ao store v2 sem reler a gravação.
3. **Uma sessão é relida quando:**
   - os arquivos dela mudaram;
   - uma volta selecionada dela não está no cache;
   - a chave global mudou. Aqui a chave é a da Parte B mais o código do store v2: `store_v2.py`, `ai_detector.py` (`pit_lap`), a reamostragem e o que mais a materialização usar.
4. **O store v2, o meta e o relatório continuam no mesmo formato e no esquema 2.1.** O meta ganha só o campo `construcao`, com:
   - o modo (`incremental` ou `completo`);
   - as sessões lidas;
   - quantas saíram do cache;
   - o motivo, se foi completo.

## Parte D — Conferência com os dados reais

Compare cada rodada com a referência completa da Parte A, pelo critério do princípio. Use um script de comparação versionado, que fica para conferências futuras, por exemplo `backend/ml/scripts/comparar_saidas_coach.py`.

1. **Rodada 1, cache vazio:** o incremental sem cache equivale ao completo. Compare.
2. **Rodada 2, nada novo:** rode de novo. O esperado é que nenhuma sessão seja lida. Compare e meça.
3. **Rodada 3, sessão nova simulada:** tire **só do cache** (nunca das gravações) a sessão mais recente da pasta do repositório com equipamento `atual`, e rode de novo. O esperado é que só ela seja lida, no passo 1 e no passo 6. Compare e meça.
4. **Só depois das três rodadas passarem,** o incremental vira o padrão do comando:
   - `--completo` força a leitura de tudo e refaz os dois caches;
   - `--sem-varrer` continua como hoje.
5. **No fim do comando,** imprima o tempo de cada passo e quantas sessões foram lidas e quantas saíram do cache.
6. **A pasta `_p25_referencia_completa` fica,** e o tamanho dela vai para o relatório. Eu decido depois se apago.

## Parte E — Documentação e pendências do pedido 24

1. **`docs/coach_aprendizado.md`, seção 10:**
   - como funciona o modo incremental;
   - o que é reaproveitado;
   - quando tudo é lido de novo;
   - o `--completo`;
   - onde ficam os caches;
   - os tempos medidos, antes e depois.
2. **`docs/store_v2_e_evolucao.md`:** uma seção curta sobre o cache do store v2 e o campo `construcao` do meta.
3. **`docs/backlog.md`:**
   - **tire a linha** "atualizar_coach leva ~16 min; criar um modo incremental" (concluída);
   - **tire a linha** "Dados externos no treino do Modelo 1". Ela ficou concluída com os pedidos 22 a 24, e a entrada no treino já está na linha do retreino (ADR 0019);
   - **na linha "Retreinar a LSTM geradora com as três fontes",** no Impacto, acrescente ao fim: "Decidir como tratar os 10 microssetores pouco confiáveis da referência da F1 (ADR 0019, item 7)";
   - **acrescente a linha:**

     | Item | Origem | Impacto | Quando |
     |---|---|---|---|
     | O FastF1 3.4.0 não reconhece "LAP DELETED" sem tempo de volta: uma volta apagada assim passaria pelo filtro 3 | Pedido 24 (08/10) | Nenhum nas sessões usadas hoje: as contagens de 2023–25 batiam no pedido 23, e em 2024 todas as voltas caem pelo pneu | Conferir se entrar sessão nova da F1 |

4. **Errata no relatório 23** (`docs/handoff/2026-10-05_23_voltas-secas-f1_relatorio.md`). Logo depois do cabeçalho, acrescente o parágrafo abaixo, sem mudar o resto do texto:

   > **Errata (08/10, pedido 24):** onde este relatório diz que a pasta da classificação de 2024 no cache foi baixada em junho "com o mesmo FastF1 3.4.0" ou "com a mesma versão", a afirmação está errada. Os arquivos de junho não passaram na checagem de versão do cache do FastF1 3.4.0 e foram sobrescritos no pedido 24. Ver `docs/handoff/2026-10-08_24_f1-referencia-2023-25_relatorio.md`.

## Testes

Os testes são sintéticos, com gravações falsas pequenas e sem as gravações reais:

- **mesmos tamanhos e datas:** a sessão não é lida (conte as leituras);
- **tamanho ou data mudou:** a sessão é lida de novo; **sessão sumiu:** ela sai do inventário;
- **chave global mudou** (geometria, portões, código ou formato): leitura completa, com o motivo;
- **duplicatas entre uma sessão do cache e uma nova:** marcadas igual ao modo completo;
- **store v2:**
  - um rótulo mudado no inventário chega ao store sem reler a gravação;
  - uma volta selecionada fora do cache faz a sessão ser relida;
- **ponta a ponta, com 3 sessões falsas:** o incremental dá o mesmo que o completo nas três situações da Parte D;
- **pasta do app instalado:** os caches nunca são gravados nela.

A suíte `backend/tests` continua passando: são 656 testes hoje, mais os novos.

## Regras gerais

- **Nenhum resultado muda:**
  - rótulos, detector, treino do coach, checagens do store v2, relatório de evolução e store antigo (`laps_grid.parquet`) ficam como estão;
  - o esquema do store v2 continua 2.1.
- **Todas as travas do comando continuam:**
  - rótulos de 04/10 que não batem;
  - microssetores e zonas do detector que não batem;
  - nenhuma volta limpa para treinar;
  - checagem do store v2 que falha;
  - `--modelo` dentro da pasta do app instalado.
- **As gravações são só lidas,** nas duas pastas. Nenhuma é movida, renomeada ou apagada.
- **Não mexa no app instalado nem em arquivos do jogo.** Nenhum cache fica na pasta do app instalado.
- **Não instale nem atualize pacotes.**
- **Branch e commits:** branch `etapa/atualizar-coach-incremental`, commits por parte, merge em `develop`. Sem push.
- **Uma sessão de implementação por vez** (ADR 0008).
- **Relatório** em `docs/handoff/2026-10-08_25_atualizar-coach-incremental_relatorio.md`, como manda o CLAUDE.md, com:
  - os tempos da Parte A, por passo e com o detalhamento dos passos 1 e 6;
  - o desenho dos caches: as chaves, os arquivos e a lista do código que entra na chave;
  - a tabela de comparação das três rodadas (arquivo, resultado e campos excluídos);
  - os tempos das três rodadas;
  - o tamanho dos dois caches e da referência completa;
  - a saída da suíte de testes e os commits.
- Se algo do contexto não bater com o repositório, pare e registre no relatório.
