# Relatório do pedido 54: a trava do store v2 (parada antes da rodada, A.5)

- **Pedido:** `docs/prompts/2026-11-17_54_trava-do-store-v2.md`.
- **Situação:** **parado antes da rodada (A.5),** como o pedido manda.
  - A Parte 0 e as Partes A.1 a A.4 estão feitas.
  - A rodada (A.6), o antes e o depois (A.7), o merge (A.8) e a Parte B ficam para depois do seu sinal.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/trava-do-store-v2`, a partir de `develop` em `14fe1ca0`.
- **Commits** (na branch, nenhum merge):
  - `ba1c9bcb` Pedido 54: o texto do pedido (a trava do store v2: as sessoes aceitas com margem e a causa da linha do jogo);
  - `76f1c21e` Pedido 54, Parte A.1: a regra das sessoes aceitas com margem (2,0 ms, a mediana do efeito da sessao), registrada antes do codigo;
  - o commit do código, dos testes e deste relatório (o hash está no chat e na seção "O envio").
- **Arquivos de handoff:**
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_relatorio.md` (este);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_testes.txt` (a suíte do backend).

## Parte 0: a pasta e os dados

1. **A pasta:**
   - nenhuma outra sessão está ativa na pasta do 47: as sessões ligadas estão todas paradas, e a do pedido 50, a última que usou esta pasta, terminou;
   - a pasta principal (`etapa/engenheiro`, pedido 52) e a do 48 (`etapa/modelo2-rodada-2`, pedido 42) não foram tocadas. Nenhum comando mudou a branch ou a área de trabalho delas.
2. **A branch:** `etapa/trava-do-store-v2`, criada de `develop` (`14fe1ca0`, igual ao remoto) sem problema. O texto do pedido é o primeiro commit (`ba1c9bcb`).
3. **Os dados:**
   - **as três junções já existentes apontam para a pasta principal:**

     | na pasta do 47 | tipo | aponta para |
     |---|---|---|
     | `data\ml` | junção | `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\ml` |
     | `data\recordings` | junção | `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\recordings` |
     | `data\cache` | junção | `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\data\cache` |

   - **o que faltava:** o relatório de evolução lê o modelo do coach, a volta do modelo e a geometria oficial em `data\reference_models` da raiz do repositório. Essa pasta já existe na pasta do 47 (ela é versionada em parte), mas só tinha o `vhe_interlagos.optimal.json`;
   - **criei três vínculos reais** (a pasta já existe), como o pedido 42 fez. Todos são só lidos pela rodada:

     | arquivo em `data\reference_models` | SHA-256 (início), igual nas duas pastas |
     |---|---|
     | `vhe_interlagos.geometry.json` | `811DA4C989E6EFD4` |
     | `vhe_interlagos.json` (o modelo do coach) | `F8E61864BA2A38DF` |
     | `vhe_interlagos.volta_do_modelo.json` | `E8651D452F6BDA85` |

   - **onde a rodada escreve:** só em `data\ml` (por junção): o store, o meta, o relatório do construtor, o cache do passo 6 e `data\ml\evolucao`. Nada da pasta principal fora de `data\` muda. Os vínculos reais não são escritos;
   - os imports vêm da pasta do 47 (`ml.__file__` = `f1-telemetry-analyzer-47\backend\ml\__init__.py`), com o `.venv` da principal.
4. **O jogo:** o `acs.exe` estava fechado antes da suíte.

## Parte A: as sessões aceitas com margem

### A.1, a regra, registrada antes do código

- **Onde:** `docs/store_v2_e_evolucao.md`, seção 1.3, "Emenda de 17/11/2026 (pedido 54): as sessões aceitas com margem".
- **Quando:** no commit `76f1c21e`, antes de qualquer mudança no código e antes de qualquer conta nas voltas.
- **O número da sessão foi escolhido por você em 17/11, antes da conta,** entre a mediana e o p95. Pelas contas do contexto, a sessão de 01/11 fica no limite.
- **A regra:**
  - vale para uma sessão com pelo menos 3 voltas medidas, cuja mediana fica fora da tolerância de 0,10 m;
  - **a diferença da sessão** é a mediana da sessão menos 1,463 m (o mesmo número que a checagem já usa);
  - **o efeito, volta a volta:** `1000 × diferença / v`, em ms. `v` é a velocidade na passagem do começo da volta (`v_linha_inicio_kmh`), a mesma passagem em que a posição da linha é medida;
  - **o número da sessão é a mediana desses efeitos,** com o sinal;
  - **até 2,0 ms em módulo:** a sessão é aceita com margem, para cima ou para baixo;
  - **acima de 2,0 ms, ou sem velocidade:** a sessão reprova, como antes;
  - **a lista sai da medida, e não de uma lista no código.**
- **O que não muda:** os 1,463 m, a tolerância de 0,10 m, a mediana de todas as voltas (que continua conferida), a checagem do período e as outras checagens. Nenhuma volta sai do store, e nenhuma gravação muda.
- **O ADR:** nenhum ADR registra as checagens do store v2. Elas estão só em `docs/store_v2_e_evolucao.md` (seções 1.3 e 3), e por isso **a linha de atualização no ADR não foi escrita.** A regra está registrada nesse documento. **Isto fica para você decidir:** pôr a linha num ADR que já existe (o 0007, do versionamento de dados e do meta, é o mais perto) ou deixar como está.

### A.2, o meta do store: as chaves, para o pedido 42

O construtor (`ml/scripts/build_lap_store_v2.py`) grava no `laps_grid_v2_meta.json`, no nível de cima:

- `aprovado`: `true` quando cada sessão passa ou é aceita com margem e as outras checagens passam (como antes, pelas checagens);
- **`sessoes_aceitas_com_margem`**: a lista, com um item por sessão:
  - `sessao`: o `session_id`;
  - `mediana_m`: a mediana da linha do jogo na sessão;
  - `diferenca_m`: a mediana menos 1,463 m, com o sinal;
  - `efeito_ms`: o número da sessão, com o sinal;
  - `voltas`: as voltas com a velocidade usadas no efeito;
  - `decisao`: a data da decisão, `"2026-11-17"`;
- **`margem_linha_do_jogo_ms`**: `2.0`.

A mesma lista fica também na checagem, em `checagens.linha_do_jogo.aceitas_com_margem`, junto com `margem_ms`.

### A.3, o motivo na checagem

- **Cada sessão aceita com margem** vai para `checagens.linha_do_jogo.avisos_aceitas_com_margem`, com a mediana, a diferença e o efeito. Por exemplo: "…: a linha do jogo ficou a 1.580 m do s = 0, e a registrada e 1.463 m (tolerancia 0.10 m), diferenca de +0.117 m; efeito de +1.620 ms, ate 2.0 ms: aceita com margem (decisao de 2026-11-17, pedido 54)".
- **O construtor imprime esses avisos** abaixo da checagem.
- **Quando a sessão reprova,** o motivo também ganha a diferença e o efeito ("efeito de … ms, acima de 2.0 ms", ou "sem a velocidade na linha").
- **Na sessão, a entrada** ganha `diferenca_m`, `efeito_ms`, `voltas_com_velocidade` e `aceita_com_margem`.

### A.4, os testes

`backend/tests/test_trava_do_store_v2.py`, com 10 testes e dados sintéticos:
- **uma sessão dentro da tolerância:** passa, sem nenhuma aceita com margem;
- **fora da tolerância, com efeito de até 2,0 ms:**
  - com a linha depois de 1,463 m (+0,117 m a 260 km/h, +1,62 ms): aceita com margem e listada;
  - com a linha antes (−0,118 m, −1,63 ms): aceita com margem e listada;
- **o efeito é a mediana volta a volta,** com a velocidade de cada volta;
- **com efeito acima de 2,0 ms:** reprova, com o motivo:
  - pela velocidade: a mesma diferença a 150 km/h dá +2,81 ms;
  - pela diferença maior: +0,167 m a 260 km/h;
  - **sem a velocidade na linha,** também reprova;
- **a mediana de todas as voltas** continua sendo conferida;
- **o meta:** as duas chaves, a lista e os campos de cada item, e o construtor gravando as chaves.

Os testes da checagem que já existiam (`test_regua_do_periodo.py`, `test_store_v2_e_evolucao.py`) continuam passando: 45 no total com os novos.

**A suíte do backend:** 1053 testes passam, sem nenhuma falha (veja "Testes").

### A.5, a parada: o que está pronto e o que a rodada vai regravar

**Pronto:** a regra registrada, o código, os testes e os vínculos de dados.

**O estado de agora** (o meta construído em 15/11, no commit `a168e41f`):
- `aprovado: false`;
- a checagem da linha do jogo reprova com as 3 sessões;
- a mediana de todas as voltas é 1,4972 m, em 719 voltas medidas;
- as outras checagens passam;
- o relatório de evolução (`data\ml\evolucao`) é de 22/10, com 12 sessões, de 04/10 a 21/10.

**A rodada (A.6), depois do seu sinal, a partir de `f1-telemetry-analyzer-47\backend`:**

1. **Guardar a cópia de antes,** fora do git (ela ficou em `data\ml\_backup_antes_pedido54\`, veja A.6): o `laps_grid_v2.parquet` (398 MB), o `laps_grid_v2_meta.json`, o `store_v2_relatorio.json` e a pasta `evolucao`.
2. **Conferir** que o app instalado e o app do repositório estão fechados, que nenhuma sessão está sendo gravada e que o `acs.exe` está fechado.
3. **O passo 6, sozinho:** `python -m ml.scripts.build_lap_store_v2 --incremental`.
   - É o mesmo comando que o `atualizar_coach` roda no passo 6, com o inventário de `data\ml\origem` e o cache de `data\ml\cache_store_v2`.
   - **Ele regrava** `data\ml\laps_grid_v2.parquet`, `laps_grid_v2_meta.json` e `store_v2_relatorio.json`, e atualiza o cache do passo 6.
4. **O passo 7, sozinho:** `python tools/relatorio_evolucao.py`.
   - **Ele regrava** `data\ml\evolucao\` (os `sessao_*.json`, o `resumo.json` e o `painel.html`), contra a volta do modelo (ADR 0032).
5. **Os dois rodam sem o `atualizar_coach`:** os passos 1 a 5, o inventário e o modelo do coach não são tocados.
6. **Conferir pelo SHA-256** que os arquivos regravados na pasta principal são os novos.

**O que eu não sei antes de rodar:** se as 3 sessões entram. A regra decide pela medida. Se alguma ficar acima de 2,0 ms, o store continua com `aprovado: false`, o passo 7 não roda, e eu paro e aviso.

## A.6, a rodada (17/11, depois do seu sinal)

**O sinal:**
- você respondeu "Pode rodar" aqui;
- pela sessão que abriu esta, chegou a resposta com as suas palavras: "o teste do 52 no jogo não está acontecendo, e o app instalado e o do repositório estão fechados";
- a mesma resposta pediu a linha da decisão no ADR 0007. **Ela foi escrita no commit `ff0ce3ed`,** com uma linha no índice.

**Antes de rodar:**
- **A cópia de antes** ficou em `data\ml\_backup_antes_pedido54\`, fora do git, como os outros backups de `data\ml` (ADR 0007). Ela tem:
  - o `laps_grid_v2.parquet`, o `laps_grid_v2_meta.json` e o `store_v2_relatorio.json`;
  - a pasta `evolucao`, com 15 arquivos.

  O SHA-256 de cada cópia é igual ao original.
- **Os apps estavam fechados:** não havia processo do app instalado, do app do repositório, do backend nem do jogo. Também não havia gravação em andamento: a última pasta de gravação mudou em 16/11.

**O passo 6** (`python -m ml.scripts.build_lap_store_v2 --incremental`):
- **A primeira tentativa (20:34) foi interrompida às 20:47,** no meio da leitura das gravações, quando a sessão anterior terminou. O store e o meta não chegaram a ser escritos: os três arquivos continuaram os de 15/11. O cache do passo 6 ficou sem manifesto.
- **Por que ele lia tudo:** "a chave global mudou: codigo: …". O código desses arquivos é o mesmo do 15/11 (`git diff a168e41f` vazio). A chave mudou pelo fim de linha dos arquivos nesta pasta, como na memória do projeto sobre o cache do coach.
- **A segunda (21:16 a 21:31) terminou com código 0,** em 929 s, com a leitura completa ("o cache nao tem manifesto").
  - O `commit` no meta é `ff0ce3ed`, o HEAD na hora de gravar. O código da checagem é o do `b9cd4069`, porque o `ff0ce3ed` só mudou documentos.

**O passo 7** (`python tools/relatorio_evolucao.py`) terminou com código 0, às 21:32.

**O modelo do coach, o inventário e os passos 1 a 5 não rodaram.**

## A.7, o antes e o depois

**O meta:**

| | antes (15/11, `a168e41f`) | depois (17/11) |
|---|---|---|
| `aprovado` | `false` | **`true`** |
| a checagem da linha do jogo | reprovou com as 3 sessões | passou, com as 3 aceitas com margem |
| as outras checagens | passaram | passaram |
| a mediana de todas as voltas | 1,4972 m | 1,4972 m |
| o período contra o jogo | p99 de 3,72 ms (em módulo), mediana de 0,78 ms | o mesmo |

**As sessões aceitas com margem** (`sessoes_aceitas_com_margem`, com `margem_linha_do_jogo_ms` de 2,0):

| sessão | mediana | diferença | efeito (mediana das voltas) | voltas |
|---|---:|---:|---:|---:|
| `2026-11-01_19-47-03` | 1,606 m | +0,143 m | **+1,980 ms** | 6 |
| `2026-11-07_18-46-00` | 1,581 m | +0,118 m | +1,643 ms | 5 |
| `2026-11-12_22-57-03` | 1,573 m | +0,110 m | +1,590 ms | 4 |

**A de 01/11 entrou por 0,020 ms.** Com o p95, ela provavelmente teria ficado de fora.

**O store:**
- **o `laps_grid_v2.parquet` ficou byte a byte igual ao de antes** (SHA-256 `8FCADDF17783D50C…` nos dois). Nenhuma volta entrou, saiu ou mudou;
- são 721 voltas, iguais antes e depois:

  | por origem | | por pasta | | por equipamento | |
  |---|---:|---|---:|---|---:|
  | desconhecida | 552 | app instalado | 528 | anterior | 552 |
  | humano | 153 | repositório | 193 | atual | 169 |
  | IA | 13 | | | | |
  | misturada | 3 | | | | |

**O relatório de evolução:**

| | antes (22/10) | depois (17/11) |
|---|---|---|
| a referência | `volta_ia`, a `#0013` (1:24,829), sem rótulo | **`volta_do_modelo`, rótulo "Volta de referência"**: `2026-11-15_02-47-12_vhe_interlagos_teste_m1#0008`, 1:24,552 (ADR 0032) |
| as sessões | 12, de 04/10 a 21/10 | **16, de 04/10 a 12/11**: entraram 24/10, 01/11, 07/11 e 12/11 |
| o critério do ADR 0015 | "ainda variando" (amplitude de 2,23 s) | **"ainda variando"**: nas 3 últimas sessões, as medianas são 1:31,635, 1:30,364 e 1:30,207, uma amplitude de 1,428 s contra o limite de 0,5 s |
| a tendência da mediana | — | −0,179 s por sessão |
| as 3 curvas de maior perda | — | C04, C01 e C12 |

- **O que o terminal ainda mostra:** a saída impressa do relatório ainda escreve "mediana - IA" e "perda para a IA". São os nomes antigos das chaves, que o pedido 51 manteve (seção 1.4 do documento) e que agora medem contra a volta do modelo. **Nos JSONs, o rótulo é "Volta de referência".**
- **O caminho do modelo nos JSONs:** o `referencia.modelo` e o `referencia.arquivo` apontam para `f1-telemetry-analyzer-47\data\reference_models\…`, os vínculos reais da Parte 0. O conteúdo é o mesmo da pasta principal (o mesmo arquivo), mas o caminho escrito é o desta pasta.

**A conferência pelo SHA-256 na pasta principal** (`data\ml`, pela junção, os mesmos arquivos):

| arquivo | SHA-256 (início) | igual ao de antes? |
|---|---|---|
| `laps_grid_v2.parquet` | `8FCADDF17783D50C` | sim, byte a byte |
| `laps_grid_v2_meta.json` | `6E05753DE2FCDC00` | não (novo) |
| `store_v2_relatorio.json` | `2DCF28E9244AE982` | não (novo) |
| `evolucao\resumo.json` | `16F0C64F631C5EF4` | não (novo) |
| `evolucao\painel.html` | `4EA2A8B13ECFF02D` | não (novo) |
| `evolucao\sessao_*.json` | 16 arquivos, de 21:31:57 a 21:32:04 | 12 refeitos e 4 novos |

## Parte B: as hipóteses, registradas antes das contas (17/11, 21:20)

Escritas antes de qualquer conta da Parte B, enquanto o passo 6 da rodada rodava. Para cada uma, o que a confirmaria e o que a descartaria.

**Um discriminador que serve para todas:**
- se a linha se moveu no espaço (a geometria, o cache ou a pista), a diferença é **constante em metros**, qualquer que seja a velocidade na linha;
- se o que mudou foi o tempo (um atraso entre a posição e o cronômetro na amostra), a diferença **cresce com a velocidade**, e o que fica constante é o atraso em ms. A medida da linha é `s − v × cronômetro`, então um atraso Δt soma `v × Δt` à posição.

1. **O CSP 0.3.1 (chegou em 01/11).**
   - **Confirmaria:** a mudança começa na primeira sessão depois da instalação do CSP, em qualquer app (o instalado e o do repositório, de qualquer versão) e em qualquer pista (a original e a cópia). Ela aparece como um atraso constante em ms.
   - **Descartaria:** sessões depois da instalação do CSP que passam, ou uma mudança que começa antes dela.
2. **O gravador do app 0.5.0 em diante** (onde ele lê a troca de volta ou o instante da amostra).
   - **Confirmaria:**
     - a mudança acompanha a versão do app, e não a data;
     - sessões gravadas no mesmo período por um app 0.4.x passam;
     - o `git diff` do gravador entre o 0.4.x e o 0.5.0 mexe na leitura do cronômetro, da posição ou do instante da amostra.
   - **Descartaria:** sessões gravadas pelo 0.5.0 ou depois que passam, ou um gravador sem mudança nesses pontos.
3. **Uma atualização do jogo ou da pista.**
   - **Confirmaria:** os arquivos da pista ou do jogo mudaram perto de 01/11, com a data e o tamanho dos arquivos só lidos; e a diferença é constante em metros.
   - **Descartaria:** nenhum arquivo da pista ou do jogo mudou no período.
4. **A geometria oficial ou o cache da pista.**
   - **Confirmaria:** o `geometry_id` ou o arquivo da geometria mudou, ou o s = 0 se moveu; e a diferença é constante em metros.
   - **Descartaria:** todas as sessões, as que passam e as que reprovam, estão no mesmo `geometry_id` (`0ed16f0dd2225990`), e o arquivo não mudou.
5. **Outra que os dados mostrarem.** Por exemplo, o FPS ou a taxa de amostragem, o carro, ou a IA contra o piloto. O critério é o mesmo: a mudança tem de acompanhar a variável, e o discriminador diz se ela é de espaço ou de tempo.

## Testes

- **A suíte do backend:** `1053 passed, 37 warnings in 556.88s`, sem nenhuma falha. A saída inteira está em `_testes.txt`.
  - O `test_leitura.py::test_volta_da_conferencia_nos_arquivos_reais`, que falhava nesta pasta no pedido 47 por falta do `geometry.json`, agora passa com o vínculo real da Parte 0.
- **Os dados da pasta principal ficaram intactos:** a foto de `data\ml`, `data\cache`, `data\recordings` e `data\reference_models` (977 arquivos, com nome, tamanho e data) é a mesma antes e depois da suíte.
- **O jogo** estava fechado antes da suíte.

## O envio

- **Conferido antes do primeiro envio,** nos commits desde `develop`:
  - nenhum arquivo passa de 50 MB;
  - nenhuma gravação, nada de `data/ml`;
  - nenhum segredo.

  Os vínculos reais de `data\reference_models` são ignorados pelo git (`data/reference_models/*.json`).
- **Só a branch do pedido vai,** como branch nova e sem `--force`. `develop`, `main` e as tags não vão antes do merge.
- **O hash local e o remoto** estão no chat, conferidos com `git ls-remote origin`.

## O que falta (depois do seu sinal)

1. **A rodada (A.6),** como descrita em A.5.
2. **O antes e o depois (A.7).**
3. **O merge da Parte A em `develop` (A.8):**
   - trazer `develop` para a branch, com merge;
   - enviar;
   - voltar a pasta para a branch do pedido;
   - avisar que o pedido 42 pode retomar.
4. **A Parte B,** só análise.

**Precisa de você:**
- **o sinal para a rodada,** confirmando que o teste do pedido 52 no jogo não está acontecendo;
- **a linha de atualização no ADR:** onde pôr, já que nenhum ADR registra as checagens do store v2 (veja A.1).
