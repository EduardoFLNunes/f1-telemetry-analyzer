# Relatório do pedido 25: modo incremental do `atualizar_coach`

- **Pedido:** `docs/prompts/2026-10-08_25_atualizar-coach-incremental.md`
- **Branch:** `etapa/atualizar-coach-incremental`, com merge em `develop`
- **Commits e merge:**
  - `e2f845c7` docs: pedido 25 (modo incremental do atualizar_coach); medicao da Parte A no relatorio (Parte A)
  - `f6c99069` ML: inventario incremental, com a leitura de uma sessao separada e cache por gravacao (pedido 25, Parte B)
  - `bf69d8ac` ML: store v2 incremental com cache por gravacao, --incremental opcional no atualizar_coach e tempos por passo (pedido 25, Parte C)
  - `412de8b0` ML: script de comparacao das saidas do atualizar_coach com a referencia completa (pedido 25, Parte D)
  - `511588ed` ML: o incremental vira o padrao do atualizar_coach depois das tres rodadas; --completo le tudo e refaz os caches (pedido 25, Parte D)
  - `59cfaf1e` docs: modo incremental do atualizar_coach, cache do store v2, backlog e errata do relatorio 23 (pedido 25, Parte E)
  - `480847e9` Merge etapa/atualizar-coach-incremental (pedido 25: modo incremental do atualizar_coach)
  - o commit deste relatório, com o patch, a saída da suíte e o JSON das comparações: "Relatório do pedido 25: modo incremental do atualizar_coach"
- **Arquivos de handoff:**
  - `docs/handoff/2026-10-08_25_atualizar-coach-incremental_relatorio.md` (este)
  - `docs/handoff/2026-10-08_25_atualizar-coach-incremental.patch` (de `481191ef` até o merge `480847e9`; sha256 `8771479b…e5a49a08`)
  - `docs/handoff/2026-10-08_25_atualizar-coach-incremental_testes.txt` (suíte `backend/tests`: 670 passando)
  - `docs/handoff/2026-10-08_25_atualizar-coach-incremental_comparacoes.json`: os tempos da Parte A e, de cada rodada, os tempos por passo, as leituras e o resultado de cada arquivo comparado

Nada foi enviado ao remoto. O app instalado e os arquivos do jogo não foram tocados: o app estava fechado nas medições, e nenhum processo dele rodava. As gravações foram só lidas, nas duas pastas. Nenhum pacote foi instalado nem atualizado.

Nenhum resultado mudou: rótulos, detector, treino do coach, checagens do store v2, relatório de evolução e store antigo (`laps_grid.parquet`). O esquema do store v2 continua 2.1.

## Em resumo

1. **O incremental dá o mesmo resultado do comando completo.** Foram quatro rodadas contra a referência completa, mais a de conferência do padrão: todas deram "tudo igual" nos 14 arquivos. O inventário, as três tabelas de `data/ml/origem/` e o store v2 saíram **idênticos byte a byte** em todas.
2. **O tempo depois de uma sessão caiu de 24,6 min para 3,3 a 3,9 min.**

   | | comando completo (Parte A) | incremental, nada novo | incremental, uma sessão nova |
   |---|---|---|---|
   | passo 1 | 735 s | 1,0 a 1,3 s | 5,7 a 17,0 s |
   | passo 6 | 571 s | 28 a 30 s | 29 a 43 s |
   | total | 1.478 s | 200,5 s | 205 a 233 s |

   Agora o que mais pesa é o treino do passo 4 (cerca de 167 s), que este pedido não mexeu.
3. **O incremental virou o padrão** depois de as três rodadas passarem. `--completo` lê tudo e refaz os dois caches, e `--sem-varrer` continua como antes. No fim, o comando imprime o tempo de cada passo e quantas sessões foram lidas e quantas saíram do cache.
4. **Duas divergências do contexto,** nenhuma bloqueante (ver a conferência):
   - o `carModel` do store v2 vem também do `metadata.json` da sessão;
   - a sessão indicada para a rodada 3 não tem nenhuma volta no store v2. Fiz a rodada 3 como pedida e uma rodada 3b com uma sessão que tem voltas no store.

## Conferência do contexto

| fato do pedido | onde está | bate? |
|---|---|---|
| Backlog: "atualizar_coach leva ~16 min; criar um modo incremental", e o comando completo ~26 min (~13 min no passo 1, ~10 min no passo 6) | `docs/backlog.md`, linha 25 | sim. Medi 24,6 min: 12,3 min no passo 1 e 9,5 min no passo 6 |
| Com `--sem-varrer`, o pedido 16 mediu 667 s | `docs/handoff/2026-10-04_store-v2_atualizar_coach.txt`, linha 139 | sim |
| O comando é `tools/atualizar_coach.py` | `backend/tools/atualizar_coach.py` | sim, com o caminho relativo a `backend/` |
| `scan_sessions` lê cada sessão de forma independente; só `mark_duplicates` e `mark_clock` cruzam sessões, sobre a tabela pronta | `backend/ml/data/inventory.py` | sim |
| O gancho de `report_lap_origin.scan` monta, volta a volta, as tabelas de relógio, sinais e grade | `backend/ml/scripts/report_lap_origin.py` | sim |
| `build_store_v2` lê cada sessão de forma independente | `backend/ml/data/store_v2.py` | sim |
| Os rótulos (`CARRIED_COLUMNS`) e o `carModel` vêm do inventário e das anotações, sem abrir gravação | `store_v2.build_store_v2` | **em parte.** Os rótulos, sim. O `carModel` sai de `car_for(session_id, carModel do metadata.json, anotações)`: abre o `metadata.json` da pasta da sessão, mas não o `player.jsonl`. Por isso o cache do passo 6 guarda o `carModel` gravado, o `car_for` é recalculado a cada rodada com as anotações atuais, e o `metadata.json` entra no manifesto da sessão |
| Os passos 2 a 5 e 7 leem as tabelas e só as voltas escolhidas | `atualizar_coach` | sim. O treino (passo 4) lê da gravação só as voltas escolhidas, e leva cerca de 167 s |
| 656 testes hoje | suíte do pedido 24 | sim |
| Merge `5e1bd317` em `develop` | `git log` | sim; a Parte A rodou em `develop` no `481191ef` (o relatório do pedido 24, depois do merge), sem nenhuma mudança de código |

**Rodada 3.** O pedido manda tirar do cache "a sessão mais recente da pasta do repositório com equipamento `atual`" e espera que só ela seja lida nos passos 1 e 6. Essa sessão é a `2026-10-04_04-22-39_vhe_interlagos`, com uma volta só, inválida. Ela não tem volta no store v2, então nunca esteve no cache do passo 6 e não há o que reler ali. Não parei, porque o comportamento é o certo e a conferência continua valendo:

- fiz a rodada 3 como pedida: o passo 1 leu só ela, e o passo 6 não leu nada;
- acrescentei a **rodada 3b** com `2026-10-04_03-42-10_vhe_interlagos`, a mais recente da mesma pasta e do mesmo equipamento com voltas no store: os passos 1 e 6 leram só ela.

As duas deram tudo igual.

## Parte A: medição do comando atual

Rodei em `develop`, no `481191ef`, com o app fechado. Medi com um script fora do repositório que envolve as funções de cada passo com marcações de tempo (`time.perf_counter`) e chama o `atualizar_coach` com os argumentos padrão, sem mudar nenhum código. Saída: código 0.

| passo | tempo | detalhe |
|---|---|---|
| 1, inventário | **735,2 s** | leitura das sessões (`scan_sessions`, com o gancho das três tabelas): 734,5 s; gravação do inventário e do resumo: 0,12 s; gravação das três tabelas: 0,6 s |
| 2 e 3, anotações e sessões novas | 2,3 s | uma chamada só (`detector_ia.apply`), por isso medidos juntos |
| 4, backup e treino | 167,9 s | quase tudo no treino; o backup leva menos de 0,01 s |
| 5, resumo | < 0,1 s | |
| 6, store v2 | **571,0 s** | materialização das voltas (`build_store_v2`): 528,1 s; checagens (`run_checks`): 25,6 s; sha256 das 52 gravações do meta (`file_entry`): 15,2 s; gravação do store e do meta: 1,5 s; sha256 do store: 0,24 s; leitura do store antigo para as checagens: 0,06 s; lista das sessões: 0,09 s |
| 7, relatório de evolução | 1,5 s | |
| **total** | **1.478,0 s (24,6 min)** | |

**Contexto dos números:**

- **sessões:** 134 de Interlagos (61 na pasta do repositório e 73 na do app instalado);
- **gravações:** 22,51 GB de `player.jsonl`;
- **inventário:** 1.993 voltas, das quais 740 válidas;
- **store v2:** 596 voltas, de 52 sessões com voltas selecionadas. Saíram 4 duplicadas e 140 com box.

Nessa rodada entrou a sessão `2026-10-05_20-33-47_vhe_interlagos`, da pasta do app instalado, gravada depois do último `atualizar_coach`: 25 voltas, todas `desconhecida`.

**A referência completa** fica em `data/ml/_p25_referencia_completa/`, fora do git, com **351,1 MB** (351.117.738 bytes). Ela tem 14 arquivos, copiados por `comparar_saidas_coach --guardar`:

- `origem/`: `lap_inventory.parquet`, `relogio_microsetores.parquet`, `sinais_voltas.parquet`, `grade_voltas.parquet`, `lap_inventory_summary.json`, `detector_aplicar.json` e `atualizar_coach.json`;
- `laps_grid_v2.parquet`, `laps_grid_v2_meta.json` e `store_v2_relatorio.json`;
- `reference_models/vhe_interlagos.json`;
- `evolucao/resumo.json`, `sessao_2026-10-04.json` e `sessao_2026-10-05.json`.

Ela fica; você decide depois se apaga.

## Parte B: inventário incremental (passo 1)

### Um caminho só

- `inventory.read_session(session, geometry, sectors, gates, lap_hook)` é a leitura inteira de uma sessão: limpeza, alinhamento, portões, relógio e identidade (`classify`). Ela devolve as linhas antes de `mark_duplicates` e `mark_clock`.
- `inventory.assemble_inventory(rows)` faz o que cruza sessões: a ordenação por `session_id` e `sequence`, `mark_duplicates` e `mark_clock`.
- `scan_sessions` passou a ser só o laço sobre `read_session` mais o `assemble_inventory`.
- `report_lap_origin.read_session_tables` chama `read_session` com o gancho e devolve, por sessão, as linhas e os blocos das três tabelas.
- `report_lap_origin.scan(out_dir, track, mode=…)` usa a mesma função nos três modos: `None` (sem cache, como antes), `completo` e `incremental`. Nada da lógica de leitura foi duplicado.

### O cache

**Pasta:** `data/ml/origem/cache/`, fora do git (`data/ml/` está no `.gitignore`). São **50,4 MB** para as 134 sessões.

**Um arquivo por sessão,** `<session_id>.pkl`. Ele guarda, por `pickle`, a lista de dicionários do inventário e dos sinais e os blocos de DataFrame do relógio e da grade, exatamente como o caminho completo os monta. Assim os tipos das colunas saem iguais, e as tabelas saíram idênticas byte a byte.

**O `manifesto.json` tem:**

- `chave`:
  - o formato do cache (`CACHE_FORMAT = 1`);
  - o `geometry_id` (`0ed16f0dd2225990`);
  - os portões (`config.DEFAULT_GATES`, campo a campo);
  - o sha256 de cada arquivo de código da lista abaixo;
- por sessão:
  - a pasta (`…/data/recordings` ou a do app instalado);
  - os arquivos que a leitura abre, com o tamanho e a data de modificação em nanossegundos: `player.jsonl` e `session-index.json`. Um arquivo que não existe fica `null`, e a mudança de presença também conta;
  - o nome do arquivo do cache;
- `ultima_rodada`: o modo, o motivo, as sessões lidas, quantas saíram do cache e as que sumiram. É esse o "resumo" do passo 1. Não pus esses dados no `atualizar_coach.json`, porque ele é um dos arquivos comparados, e um campo novo nele quebraria o critério de "mesmas chaves".

**O código na chave do passo 1** (`session_cache.INVENTORY_CODE`, 22 arquivos, relativos a `backend/`):

- `ml/__init__.py` e `ml/config.py`;
- `ml/preprocessing/`: `__init__`, `alignment`, `cleaning`, `quality`, `resampling` e `splits`;
- `ml/track/`: `__init__`, `corners`, `geometry`, `microsectors` e `trajectory`;
- `ml/data/`: `__init__`, `inventory`, `lap_identity`, `origin`, `origin_signals`, `recordings`, `samples` e `session_cache`;
- `ml/scripts/report_lap_origin.py`.

Um teste confere que todo módulo `ml` que a leitura importa está na lista, e que todo `.py` de `ml/preprocessing` e `ml/track` entra.

### A cada rodada

1. As sessões são listadas como antes (`list_all_sessions`).
2. A sessão com os mesmos arquivos (tamanho e data) sai do cache. A sessão nova ou mudada é lida e atualiza o cache. A sessão que sumiu do disco sai do inventário e do cache, e aparece em `sumiram`.
3. Sobre a tabela inteira, nas sessões na mesma ordem, rodam a ordenação, `mark_duplicates` e `mark_clock`. Depois a gravação do inventário e das três tabelas, nos mesmos arquivos e no mesmo formato.

**O cache inteiro é refeito,** com o motivo impresso e gravado em `ultima_rodada`, quando:

- a chave global mudou ("a chave global mudou: …", dizendo o quê);
- o cache não abre (manifesto ilegível, `pickle` que não abre ou que não bate com o manifesto);
- o comando rodou com `--completo`.

O cache é apagado antes de ler tudo, então nunca há mistura de cache velho com cache novo.

A gravação é segura: cada sessão vai para um temporário e é renomeada, e o manifesto é gravado por último. Um `pickle` que não bate com o manifesto é tratado como cache que não abre.

### O risco da ordenação (item B.6)

Não pode haver duas linhas com o mesmo `session_id` e `sequence`:

- `list_all_sessions` para com erro se o mesmo `session_id` existe nas duas pastas ("compare as duas antes de seguir"), e há um teste disso desde o ADR 0014;
- dentro de uma sessão, `iter_laps` dá um `sequence` diferente a cada volta.

Mesmo assim, a ordenação por duas colunas do pandas é estável, e o incremental monta as linhas na mesma ordem do completo: sessões por id e voltas pela ordem no arquivo. Um empate sairia igual nos dois modos.

## Parte C: store v2 incremental (passo 6)

### Um caminho só

- `store_v2.materialize_session(session, sequences, geometry, sectors)` é a única parte que abre a gravação. Para cada volta pedida, ela guarda a identidade, a marca de box e, fora do box, o bloco na grade com os canais físicos, os canais com algum ponto, os campos medidos e o tempo do jogo. Guarda também o `carModel` gravado e as voltas pedidas.
- `store_v2.selection_plan` faz a seleção (`select_v2`) e os rótulos (`CARRIED_COLUMNS`).
- `store_v2.assemble_store_v2` monta o store, os detalhes e o `carModel` (`car_for` com as anotações atuais), na mesma ordem de sempre.
- `build_store_v2(…, materials=None)` lê tudo como antes. Com `materials`, usa as sessões já materializadas e lê só as que faltam.

### O cache

**Pasta:** `data/ml/cache_store_v2/`, fora do git. São **445,4 MB** para as 52 sessões com voltas selecionadas.

- **um arquivo por sessão:** o `SessionMaterial` inteiro, em `pickle`;
- **o manifesto, por sessão:**
  - os arquivos (`player.jsonl` e `metadata.json`, com tamanho e data em ns);
  - `sequencias_pedidas`;
  - `sha256_player`: o sha256 do `player.jsonl`, para o `entradas.gravacoes` do meta. Calculado uma vez e reaproveitado enquanto os arquivos não mudam.

**A chave** é a do passo 1 mais o código da materialização (`session_cache.STORE_CODE`, 26 arquivos): os 22 do passo 1 mais `ml/data/ai_detector.py` (`pit_lap`), `ml/data/lap_store.py` (`STORE_COLUMNS`), `ml/data/store_v2.py` e `ml/scripts/build_lap_store_v2.py`.

Ficaram fora de propósito a seleção, os rótulos e as anotações (`session_annotations.py`), que são recalculados a cada rodada. Também ficou fora o `ml/validation/`: o `ai_detector` o importa, mas o `pit_lap` só usa numpy e os microssetores. Assim, uma mudança no código do retreino não força reler as gravações.

**Uma sessão é relida quando:**

- os arquivos dela mudaram;
- uma volta selecionada não está entre as `sequencias_pedidas`;
- a chave global mudou (aí o cache inteiro é refeito).

Na releitura, as voltas pedidas antes continuam pedidas, porque materializar uma volta a mais não muda nenhuma outra (o tempo do jogo depende só da volta crua seguinte). Assim a sessão não fica indo e voltando.

**O meta e o relatório** seguem no mesmo formato e no esquema 2.1. O meta ganhou só o campo `construcao`, com:

- `modo`;
- `motivo`;
- `cache_vazio_no_inicio`;
- `sessoes_com_voltas_selecionadas`;
- `sessoes_lidas`;
- `sessoes_do_cache`;
- `sumiram`.

Na última rodada ele ficou assim: `{"modo": "incremental", "motivo": null, "cache_vazio_no_inicio": false, "sessoes_com_voltas_selecionadas": 52, "sessoes_lidas": [], "sessoes_do_cache": 52, "sumiram": []}`.

**Modos do `build_lap_store_v2`:**

- sem flag, lê tudo sem cache, como antes;
- `--incremental` usa o cache;
- `--completo` lê tudo e refaz o cache.

O `atualizar_coach` sempre passa uma das duas flags.

## Parte D: conferência com os dados reais

### O script

**`backend/ml/scripts/comparar_saidas_coach.py`**, versionado para conferências futuras:

- `--guardar PASTA` copia as 14 saídas;
- `--referencia PASTA [--json ARQUIVO]` compara e sai com 1 se algo difere.

**Tabelas:**

1. primeiro o sha256 do arquivo (bytes iguais encerram);
2. depois o esquema arrow, ou seja, as colunas, a ordem e os tipos, e o número de linhas;
3. depois coluna a coluna: mesmo tipo no pandas e valores idênticos, com NaN igual a NaN e o tipo de cada valor conferido nas colunas de objeto;
4. por fim, os metadados pandas do esquema.

A leitura é coluna a coluna, para o store (315 MB) não precisar caber duas vezes na memória.

**JSONs:** mesmas chaves e mesmos valores, recursivamente, fora dos campos excluídos.

### Campos excluídos

Fixados antes da rodada 1. Levantei-os varrendo os JSONs da referência atrás de datas, durações, commits e caminhos:

| arquivo | campo excluído | o que é |
|---|---|---|
| `laps_grid_v2_meta.json` | `construido_em` | data e hora da construção |
| `laps_grid_v2_meta.json` | `commit` | commit |
| `laps_grid_v2_meta.json` | `construcao` | o campo novo (Parte C) |
| `store_v2_relatorio.json` | `segundos` | duração |
| `store_v2_relatorio.json` | `meta.commit` | commit |
| `origem/atualizar_coach.json` | `backup` | caminho do backup |
| `reference_models/vhe_interlagos.json` | `built_at` | data e hora do treino |
| `evolucao/resumo.json`, `sessao_2026-10-04.json` e `sessao_2026-10-05.json` | `store.commit_do_store` | commit do store lido |

Ficam na comparação as datas e durações que saem das gravações, como `periodos_das_gravacoes.*.inicio` e `duracao_s` no meta. `detector_aplicar.json` e `lap_inventory_summary.json` não têm nenhum campo excluído.

### As rodadas

| rodada | o que | passo 1 | passo 6 | total | comparação |
|---|---|---|---|---|---|
| 1 | `--incremental` com os dois caches vazios | 134 lidas, 704,1 s | 52 lidas, 587,4 s | 1.461,4 s | **tudo igual** |
| 2 | `--incremental` de novo, nada novo | 0 lidas (134 do cache), 1,3 s | 0 lidas (52 do cache), 29,9 s | 200,5 s | **tudo igual** |
| 3 | `2026-10-04_04-22-39` tirada dos caches (estava só no do passo 1) | 1 lida, 5,7 s | 0 lidas, 28,6 s | 205,3 s | **tudo igual** |
| 3b | `2026-10-04_03-42-10` tirada dos dois caches | 1 lida, 17,0 s | 1 lida (14 voltas), 42,9 s | 233,4 s | **tudo igual** |
| padrão | sem flags, depois da troca do padrão (`511588ed`) | 0 lidas, 1,0 s | 0 lidas, 27,7 s | 200,5 s | **tudo igual** |

Os passos 2 e 3 levaram de 2,1 a 2,3 s em todas; o passo 4, de 165,5 a 169,8 s; o 7, de 1,4 a 1,9 s.

**Resultado por arquivo, igual nas cinco rodadas:**

| arquivo | resultado | campos excluídos |
|---|---|---|
| `origem/lap_inventory.parquet` | igual, bytes iguais | — |
| `origem/relogio_microsetores.parquet` | igual, bytes iguais | — |
| `origem/sinais_voltas.parquet` | igual, bytes iguais | — |
| `origem/grade_voltas.parquet` | igual, bytes iguais | — |
| `origem/lap_inventory_summary.json` | igual | — |
| `origem/detector_aplicar.json` | igual | — |
| `origem/atualizar_coach.json` | igual | `backup` |
| `laps_grid_v2.parquet` | igual, bytes iguais | — |
| `laps_grid_v2_meta.json` | igual | `construido_em`, `commit`, `construcao` |
| `store_v2_relatorio.json` | igual | `segundos`, `meta.commit` |
| `reference_models/vhe_interlagos.json` | igual | `built_at` |
| `evolucao/resumo.json` | igual | `store.commit_do_store` |
| `evolucao/sessao_2026-10-04.json` | igual | `store.commit_do_store` |
| `evolucao/sessao_2026-10-05.json` | igual | `store.commit_do_store` |

**Ordem do que foi feito:**

1. Commitei o incremental como opção (`--incremental`), com o padrão ainda lendo tudo sem cache.
2. Rodei as rodadas 1, 2, 3 e 3b.
3. Só depois da última comparação, troquei o padrão (`511588ed`): sem flag é incremental, `--completo` lê tudo e refaz os dois caches, e `--sem-varrer` continua pulando o passo 1.
4. Para tirar sessões do cache nas rodadas 3 e 3b, usei `session_cache.forget_session`, que apaga só o arquivo do cache e a linha do manifesto, nunca a gravação.

**Tamanhos:**

| | bytes |
|---|---|
| cache do passo 1 (`data/ml/origem/cache/`) | 50.401.218 (50,4 MB) |
| cache do store v2 (`data/ml/cache_store_v2/`) | 445.447.673 (445,4 MB) |
| referência completa (`data/ml/_p25_referencia_completa/`) | 351.117.738 (351,1 MB) |

**Fim do comando.** Ele imprime o tempo de cada passo e, nos passos 1 e 6, quantas sessões foram lidas e quantas saíram do cache, com o motivo se a leitura foi completa. Os mesmos números ficam em `data/ml/origem/atualizar_coach_tempos.json`, um arquivo novo que não entra na comparação. A última linha continua sendo o caminho do painel, como o teste do pedido 17 exige.

## Parte E: documentação e pendências do pedido 24

1. **`docs/coach_aprendizado.md`, seção 10:**
   - os passos 1 e 6 da lista foram atualizados;
   - a subseção nova "Modo incremental (pedido 25)" explica como funciona, o que é reaproveitado, quando tudo é lido de novo, o `--completo` e onde ficam os caches, com a tabela de tempos antes e depois.
2. **`docs/store_v2_e_evolucao.md`:** a seção nova "7. Cache do store v2 e o campo `construcao` do meta".
3. **`docs/backlog.md`:**
   - saiu a linha "atualizar_coach leva ~16 min; criar um modo incremental";
   - saiu a linha "Dados externos no treino do Modelo 1";
   - na linha do retreino, o Impacto ganhou no fim "Decidir como tratar os 10 microssetores pouco confiáveis da referência da F1 (ADR 0019, item 7)";
   - entrou a linha do "LAP DELETED", com o texto do pedido.
4. **Errata no relatório 23:** o parágrafo do pedido entrou logo depois do cabeçalho, antes de "Nada foi enviado ao remoto". O resto do texto não mudou (2 linhas acrescentadas no diff).

## Testes

**Novos, 14, em `backend/tests/test_atualizar_coach_incremental.py`.** São sintéticos: três gravações falsas pequenas numa pista circular, em pastas temporárias. As leituras são contadas embrulhando `read_session_tables` e `materialize_session`.

- **mesmos tamanhos e datas:** nenhuma sessão é lida, e as tabelas saem iguais;
- **mudanças na sessão:**
  - data de modificação mudada: a sessão é lida de novo;
  - tamanho mudado: idem;
  - sessão apagada: sai do inventário e do manifesto, e o resultado é igual ao completo;
- **chave global mudada:** geometria, portões, código (com um sha256 trocado) e formato. Cada um faz ler tudo, com o motivo certo;
- **cache que não abre** (um `pickle` estragado): lê tudo, com o motivo, e o resultado é igual;
- **`--completo`:** lê tudo, e a rodada seguinte não lê nada;
- **duplicatas:** uma cópia de uma sessão do cache entra como sessão nova. Ela é a única lida, as duplicatas saem marcadas e o resultado é igual ao completo;
- **store v2:**
  - um rótulo mudado no inventário chega ao store sem nenhuma leitura;
  - uma volta selecionada fora do cache faz a sessão ser relida;
  - o sha256 sai do cache quando os arquivos não mudaram;
- **ponta a ponta:** as três rodadas da Parte D (cache vazio, nada novo e uma sessão tirada dos dois caches) dão o mesmo inventário, as mesmas tabelas e o mesmo store do caminho completo;
- **pasta do app instalado:**
  - o cache recusa ser criado nela;
  - o comando para com `--saida` dentro dela, antes de varrer;
  - os caches padrão ficam no repositório;
- **lista de código:** os arquivos existem e cobrem o que a leitura importa (por um subprocesso).

**Alterado:** `tests/test_atualizar_coach.py`.

- O `scan` falso aceita `mode`.
- O teste da ordem dos passos confere que o padrão é `incremental` nos passos 1 e 6.

**Suíte `backend/tests`:** 670 passando, 4 avisos, em 7 min 11 s. Eram 656 no pedido 24; os 14 novos somam 670. Rodei só `tests/`, como nos relatórios anteriores.

## Escolhas minhas

1. **`--incremental` provisório.** Para respeitar o item D.4, o incremental entrou primeiro como opção e só virou o padrão num commit à parte, depois das rodadas. No fim, a flag saiu: o padrão é incremental, e `--completo` força a leitura.
2. **Os scripts avulsos não mudaram o comportamento padrão.** `report_lap_origin` (o `main`) e `build_lap_store_v2` sem flag continuam lendo tudo sem cache. Só o `atualizar_coach` usa os caches.
3. **O cache do store guarda só as sessões com voltas selecionadas.** Uma sessão sem volta no store não é materializada, e é por isso que a rodada 3 não leu nada no passo 6.
4. **Os tempos saem antes da linha do painel,** para o painel continuar sendo a última linha (teste do pedido 17).
5. **Trava nova:** o `atualizar_coach` também para se `--saida` estiver na pasta do app instalado, e o cache se recusa a ser criado nela.
6. **Os backups do modelo.** Cada rodada do comando faz, como sempre, o backup do modelo em `data/reference_models/backup/`. As seis rodadas de hoje (a Parte A, a 1, a 2, a 3, a 3b e a do padrão) criaram seis backups de cerca de 59 KB, de `vhe_interlagos.2026-10-08_10-09-11…` a `…_11-06-39…`. O modelo treinado saiu igual em todas, fora o `built_at`.

## Pontos para o Cowork e decisões do Eduardo

1. **A pasta `_p25_referencia_completa` (351,1 MB) ficou,** como o pedido manda. Você decide se apaga.
2. **O treino do passo 4 virou o passo mais lento** (cerca de 167 s de um total de 200 s). Ele lê da gravação as voltas escolhidas a cada rodada. Um cache para ele seria outro pedido.
3. **Cuidado ao mudar o código.** Uma mudança em qualquer arquivo da lista do passo 1 (por exemplo `ml/config.py` ou `ml/track/`) faz a próxima rodada ler tudo de novo (cerca de 12 min no passo 1 e 10 no passo 6), com o motivo impresso. Isso é o esperado. Já uma mudança só em `ml/models`, `ml/validation` ou nas anotações não refaz nenhum cache.

## O que falta

Nada deste pedido.

`docs/handoff/2026-10-08_25_atualizar-coach-incremental_relatorio.md`
