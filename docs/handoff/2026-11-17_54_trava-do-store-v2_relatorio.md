# Relatório do pedido 54: a trava do store v2 (parada antes da rodada, A.5)

- **Pedido:** `docs/prompts/2026-11-17_54_trava-do-store-v2.md`.
- **Situação:** **a Parte A está feita e em `develop`** (o merge é o `64fe180a`).
  - A rodada aprovou o store, com as 3 sessões aceitas com margem: +1,980, +1,643 e +1,590 ms.
  - O relatório de evolução foi refeito contra a volta do modelo.
  - O pedido 42 pode retomar.
  - **A Parte B está feita.** A causa provável é o CSP 0.3.1, instalado em 31/10 às 19:52: a linha do jogo andou +0,11 m em todas as sessões depois dele.
    - Não está confirmada, porque a versão do app mudou no mesmo dia.
    - A confirmação e a correção são decisão sua (B.4).
  - A parada antes da rodada (A.5) está registrada abaixo, como foi escrita.
- **Pasta:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer-47`.
- **Branch:** `etapa/trava-do-store-v2`, a partir de `develop` em `14fe1ca0`.
- **Commits** (na branch, nenhum merge):
  - `ba1c9bcb` Pedido 54: o texto do pedido (a trava do store v2: as sessoes aceitas com margem e a causa da linha do jogo);
  - `76f1c21e` Pedido 54, Parte A.1: a regra das sessoes aceitas com margem (2,0 ms, a mediana do efeito da sessao), registrada antes do codigo;
  - o commit do código, dos testes e deste relatório (o hash está no chat e na seção "O envio").
- **Arquivos de handoff:**
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_relatorio.md` (este);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_testes.txt` (a suíte do backend);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_parteb_sessoes.csv` (B.1, uma linha por sessão);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_parteb_voltas.csv` (B.1, uma linha por volta);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_parteb_amostras.txt` (B.3, as amostras na passagem pela linha);
  - `docs/handoff/2026-11-17_54_trava-do-store-v2_scripts/` (os três scripts da Parte B, só leitura).

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

## A.8, o merge da Parte A em `develop` (18/11)

- **Antes:**
  - `develop` não tinha andado: estava em `14fe1ca0` no local e no remoto, o mesmo ponto de partida da branch. Não houve o que trazer, nem conflito;
  - nenhuma pasta estava com `develop` aberta: a principal está em `etapa/engenheiro`, e a do 48 em `etapa/modelo2-rodada-2`;
  - nenhuma trava do git.
- **O merge:** `64fe180a` Merge do pedido 54, Parte A: as sessoes aceitas com margem na checagem da linha do jogo (ate 2,0 ms; ADR 0007) e o store v2 reaprovado. É um `--no-ff`, sem conflito.
- **Este registro** foi commitado em `develop`. Depois, a branch do pedido avançou até ele, e **a pasta do 47 voltou para `etapa/trava-do-store-v2`.** `develop` fica livre para a pasta principal fazer o merge do 52.
- **O pedido 42 pode retomar.**
  - O store v2 está com `aprovado: true`.
  - As chaves que ele lê no meta são `sessoes_aceitas_com_margem` e `margem_linha_do_jogo_ms` (veja A.2).

| envio | ref | hash local | hash no remoto (`git ls-remote origin`) | confere |
|---|---|---|---|---|
| a parada da A.5 | `etapa/trava-do-store-v2` (nova) | `b9cd4069d91b70b87633c03bc4405dc5eed8896a` | `b9cd4069d91b70b87633c03bc4405dc5eed8896a` | sim |
| A.6 e A.7 | `etapa/trava-do-store-v2` | `d8e07ff036a8b7b42e79cc6f4b326e512d228e68` | `d8e07ff036a8b7b42e79cc6f4b326e512d228e68` | sim |
| o merge | `develop` | `64fe180af3a27aa7fd301fd8086b42803b85914f` | `64fe180af3a27aa7fd301fd8086b42803b85914f` | sim |
| o registro do merge da Parte A | `develop` e a branch | `46acad97b1de2c98014a81510ff4733a0fce1ddc` | `46acad97b1de2c98014a81510ff4733a0fce1ddc` | sim |
| a Parte B | `etapa/trava-do-store-v2` | `f293932613352a99de099b82a79dcd8eacd9ae3d` | `f293932613352a99de099b82a79dcd8eacd9ae3d` | sim |
| o merge da Parte B (`a21065a0`, `--no-ff`, sem conflito; só documentos) | `develop` | `a21065a017a031e85ec1a7aa0d63f193080857cc` | `a21065a017a031e85ec1a7aa0d63f193080857cc` | sim |

O último commit (este registro, `Relatorio do pedido 54: o merge da Parte B conferido`) foi feito em `develop`. A branch avançou até ele por avanço simples, e a pasta do 47 voltou para `etapa/trava-do-store-v2`. O hash dele está no chat.

- Todos foram avanços simples, sem `--force`.
- `main` e as tags não foram.
- **Conferido antes do envio de `develop`:** as 9 mudanças desde `14fe1ca0` não têm nada acima de 50 MB, nenhuma gravação, nada de `data/ml` e nenhum segredo.

**A Parte B vem a seguir, nesta branch.** As hipóteses estão registradas logo abaixo, antes das contas.

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

## Parte B: a medida, as evidências e a conclusão (18/11)

**Como foi medida:**
- é a mesma medida do store (`game_line_position` e `line_speeds`, na volta limpa e alinhada à geometria `0ed16f0dd2225990`), feita nas primeiras 240 amostras de cada volta crua, o que cobre a passagem do começo;
- foram **todas as 171 sessões de Interlagos** das duas pastas, de 01/06 a 16/11, a cópia da pista incluída. Isso deu 1.221 voltas com a linha medida;
- as gravações só foram lidas;
- com o `acs.exe` fechado.

**Os arquivos:**
- `_parteb_voltas.csv`: uma linha por volta;
- `_parteb_sessoes.csv`: uma linha por sessão;
- `_parteb_amostras.txt`;
- `_scripts\`: os três scripts.

**Esta medida não é a do store.** Ela inclui as voltas que o store não usa (inválidas e com box), e por isso as medianas diferem um pouco das do store. Na sessão de 01/11, por exemplo, ela dá 1,590 m em 13 voltas, contra 1,606 m em 6 no store.

### B.1, a tabela por sessão (as sessões depois de 15/10 com pelo menos 3 voltas medidas; a tabela inteira está no CSV)

| sessão | pasta | pista | app | empacotado | voltas (IA) | mediana | desvio | v na linha | atraso equivalente |
|---|---|---|---|---|---|---:|---:|---:|---:|
| `2026-10-15_23-24-50` | repositório | original | 0.3.0 | não | 19 (0) | 1,448 m | 0,054 | 263 km/h | −0,20 ms |
| `2026-10-17_01-02-22` | repositório | original | 0.3.0 | não | 18 (0) | 1,462 m | 0,077 | 264 km/h | −0,01 ms |
| `2026-10-17_16-17-08` | instalado | original | 0.4.0 | sim | 21 (0) | 1,460 m | 0,057 | 257 km/h | −0,05 ms |
| `2026-10-18_12-38-44` | repositório | original | 0.4.0 | não | 15 (0) | 1,490 m | 0,060 | 255 km/h | 0,38 ms |
| `2026-10-21_20-30-54` | repositório | original | 0.4.0 | não | 19 (0) | 1,494 m | 0,054 | 265 km/h | 0,41 ms |
| `2026-10-24_13-26-12` | repositório | original | 0.4.0 | não | 5 (0) | 1,450 m | 0,054 | 260 km/h | −0,18 ms |
| **`2026-10-24_13-43-32`** (a última que passa) | repositório | original | 0.4.0 | não | 11 (0) | 1,499 m | 0,060 | 262 km/h | 0,50 ms |
| *31/10, 19:52: o CSP 0.3.1 instalado* | | | | | | | | | |
| **`2026-11-01_19-47-03`** (a primeira que reprova) | repositório | original | 0.5.0 | não | 13 (0) | 1,590 m | 0,048 | 257 km/h | 1,76 ms |
| `2026-11-07_18-46-00` | repositório | original | 0.7.0 | não | 8 (0) | 1,614 m | 0,070 | 259 km/h | 2,10 ms |
| `2026-11-07_19-52-33` | instalado | original | 0.7.0 | sim | 3 (0) | 1,627 m | 0,003 | 260 km/h | 2,27 ms |
| `2026-11-09_08-59-24` | instalado | cópia | 0.7.0 | sim | 9 (9) | 1,600 m | 0,014 | 268 km/h | 1,84 ms |
| `2026-11-09_09-15-20` | instalado | cópia | 0.7.0 | sim | 11 (11) | 1,618 m | 0,016 | 250 km/h | 2,22 ms |
| `2026-11-09_10-00-41` | instalado | cópia | 0.7.0 | sim | 11 (11) | 1,601 m | 0,015 | 267 km/h | 1,86 ms |
| `2026-11-09_11-19-46` | instalado | cópia | 0.7.0 | sim | 11 (11) | 1,587 m | 0,020 | 249 km/h | 1,79 ms |
| `2026-11-09_14-32-22` | instalado | cópia | 0.7.0 | sim | 3 (3) | 1,624 m | 0,041 | 265 km/h | 2,18 ms |
| `2026-11-09_14-37-38` | instalado | cópia | 0.7.0 | sim | 10 (10) | 1,601 m | 0,040 | 266 km/h | 1,88 ms |
| `2026-11-09_15-01-32` | instalado | cópia | 0.7.0 | sim | 10 (10) | 1,593 m | 0,029 | 267 km/h | 1,75 ms |
| `2026-11-12_22-57-03` | repositório | original | 0.7.0 | não | 8 (0) | 1,594 m | 0,024 | 261 km/h | 1,81 ms |
| `2026-11-14_19-01-15` | instalado | cópia | 0.7.0 | sim | 8 (8) | 1,603 m | 0,022 | 273 km/h | 1,84 ms |
| `2026-11-14_22-52-59` | instalado | cópia | 0.7.0 | sim | 9 (9) | 1,605 m | 0,022 | 272 km/h | 1,89 ms |
| `2026-11-15_02-29-50` | instalado | cópia | 0.7.0 | sim | 9 (9) | 1,574 m | 0,020 | 273 km/h | 1,46 ms |
| `2026-11-15_02-47-12` | instalado | cópia | 0.7.0 | sim | 9 (9) | 1,594 m | 0,023 | 273 km/h | 1,72 ms |
| `2026-11-15_03-01-09` | instalado | cópia | 0.7.0 | sim | 9 (9) | 1,625 m | 0,026 | 273 km/h | 2,13 ms |

- **Notas da tabela:**
  - o "atraso equivalente" é a mediana, volta a volta, de (linha − 1,463 m) / v;
  - "voltas (IA)" conta as voltas com `isAIControlled` em todas as amostras da cabeça da volta;
  - as gravações de junho a setembro não guardam a versão do app (é o campo vazio no CSV);
  - **a versão do CSP e a do jogo não estão em nenhuma gravação.**
- **Por grupo:**

  | grupo | voltas | sessões | mediana | desvio |
  |---|---:|---:|---:|---:|
  | antes do CSP 0.3.1, tudo | 1.080 | 75 | 1,494 m | — |
  | antes, as voltas da IA | 22 | — | 1,488 m | 0,069 |
  | depois, o piloto, na pista original | 32 | — | 1,600 m | 0,050 |
  | depois, a IA, na cópia | 109 | — | 1,601 m | 0,026 |
  | depois, o app instalado (empacotado) | 112 | 13 | 1,605 m | — |
  | depois, o app do repositório | 29 | 3 | 1,594 m | — |
  | depois, o app 0.5.0 | 13 | 1 | 1,590 m | — |
  | depois, o app 0.7.0 | 128 | 15 | 1,601 m | — |

  **O deslocamento é de +0,108 m** (1,494 → 1,601 m), cerca de 1,46 ms a 265 km/h.
- **A sessão `2026-11-07_19-52-33`** (2 voltas no store) mede 1,627 m em 3 voltas na cabeça crua. Ela não aparece entre as reprovadas porque, no store, tem menos de 3 voltas medidas, e a checagem não dá veredito com menos de 3.
- **Antes do CSP, uma sessão já saiu da tolerância na cabeça crua:** `2026-08-08_16-52-13`, com 1,575 m em 4 voltas. É o ruído de uma sessão curta. Ela não reprovou o store.

### B.3, as evidências

1. **A data exata:**
   - a última sessão que passa é a `2026-10-24_13-43-32`, de 24/10;
   - o CSP 0.3.1, build 4302, foi instalado em 31/10 às 19:52. As datas vêm do `extension\installed.log` e do `dwrite.dll`, só lidos;
   - a primeira sessão que reprova é a `2026-11-01_19-47-03`. **É a primeira sessão gravada depois da instalação.**
   - **Depois dela, todas as 16 sessões ficam fora da tolerância, e nenhuma antes de 31/10 tem esse deslocamento em grupo.**
2. **As amostras em volta da passagem** (`_parteb_amostras.txt`; 24/10 contra 12/11):
   - nas duas sessões, o cronômetro zera na mesma amostra em que o carro passa a linha. O contador de voltas às vezes troca uma amostra depois do cronômetro, e isso acontece nas duas;
   - a cadência das amostras é a mesma (cerca de 15,6 ms, com buracos de cerca de 31 ms);
   - a de 12/11 tem uma amostra repetida (o mesmo cronômetro e a mesma posição), mas a de 24/10 também tem buracos;
   - **a diferença está só no valor:** na primeira amostra depois do zero, `s − v × cronômetro` dá 1,36 e 1,43 m em 24/10, e 1,55 e 1,59 m em 12/11. O gravador e o corte em voltas se comportam igual.
3. **O código do gravador entre o 0.4.0 e o 0.5.0** (`git diff 3b192d61 b85638dd`):
   - o `recording_runtime.py` só mudou a detecção do reinício da sessão (quando abrir um arquivo novo). A leitura do cronômetro, da posição e do instante da amostra não mudou;
   - o `track_geometry_provider.py` ganhou uma chave de origem para refazer o cache da pista do app. Mas a medida do ML não usa esse cache: ela alinha a posição no mundo à geometria do ML (`0ed16f0dd2225990`), a mesma em todas as sessões.
4. **As sessões da cópia** (a IA, 109 voltas depois do CSP):
   - mostram o mesmo deslocamento que as suas na pista original (1,601 contra 1,600 m), com metade do desvio;
   - **não é o piloto nem a pista:** a cópia tem os mesmos arquivos da original, com só a linha da IA trocada.
5. **O app instalado contra o do repositório:**
   - depois do CSP, os dois deslocam igual (1,605 e 1,594 m);
   - antes, também eram iguais (1,497 e 1,487 m).
6. **A pista e o jogo:**
   - os arquivos da pista (fora do `data.acd`, que não foi aberto) são de maio;
   - o `acs.exe` é de maio de 2025;
   - nada mudou perto de 01/11.
7. **O discriminador (espaço ou tempo): não conclusivo.**
   - Quase todas as passagens ficam entre 250 e 275 km/h. Nessa faixa, um atraso constante de 1,5 ms dá 0,104 m a 250 km/h e 0,115 m a 275 km/h, uma diferença de 0,011 m, abaixo do ruído (desvio de 0,02 a 0,07 m por sessão).
   - Por faixa de velocidade, o deslocamento é de +0,086 m (230 a 250 km/h), +0,132 m (250 a 265 km/h) e +0,105 m (acima de 265 km/h). As faixas lentas têm poucas voltas.

### B.2, as hipóteses contra as evidências

| hipótese | resultado | por quê |
|---|---|---|
| 1. o CSP 0.3.1 | **a causa provável** | a mudança começa na primeira sessão depois da instalação e vale para tudo: os dois apps, as duas pastas, as duas pistas, o piloto e a IA |
| 2. o gravador do app 0.5.0 em diante | **improvável, não descartada** | o código que lê o cronômetro e a posição não mudou entre o 0.4.0 e o 0.5.0. Mas **o 0.5.0 é de 01/11 às 17:47, depois da instalação do CSP:** nenhuma sessão foi gravada com app novo e CSP velho, nem com app velho e CSP novo. Os dados não separam os dois |
| 3. uma atualização do jogo ou da pista | **descartada** | nenhum arquivo da pista ou do jogo mudou desde maio |
| 4. a geometria oficial ou o cache da pista | **descartada** | uma geometria só (`0ed16f0dd2225990`) em todas as sessões, e a medida não usa o cache da pista do app |
| 5. outra | nenhuma achada | a IA contra o piloto e o app instalado contra o do repositório não mudam o deslocamento |

### B.4, a conclusão

- **A causa provável é o CSP 0.3.1.** Ele mudou o ponto em que o cronômetro do jogo zera, em cerca de +0,11 m (cerca de 1,5 ms à velocidade da reta), a partir de 31/10.
- **Não está confirmada:** a versão do app mudou no mesmo dia, e os dados não separam as duas. O código do gravador aponta para o CSP.
- **Para confirmar** (decisão sua), basta uma das duas:
  - **uma sessão curta com o app atual e o CSP de antes** (ou desligado), de 5 voltas. Se a linha voltar para cerca de 1,49 m, é o CSP;
  - **uma sessão curta com o app 0.4.0 e o CSP 0.3.1.** Se a linha ficar em cerca de 1,60 m, é o CSP.

**As correções possíveis (a decisão é sua; nada mudou além da Parte A):**

1. **Manter a margem de 2,0 ms.**
   - Não custa nada agora.
   - **O risco:** o deslocamento vale cerca de 1,5 a 2,3 ms por sessão, e o efeito cresce quando a passagem é mais lenta. Na cópia, as sessões a 250 km/h dão 2,2 ms (`2026-11-09_09-15-20`), e a `2026-11-15_03-01-09` dá 2,13 ms a 273 km/h.
   - **Uma sessão sua nova, com a mesma diferença e uma passagem um pouco mais lenta, passa de 2,0 ms e reprova o store de novo.** A de 01/11 já ficou a 0,020 ms do limite.
2. **Uma nova medida dos 1,463 m, por regime.**
   - Seria registrar a linha depois do CSP 0.3.1 (cerca de 1,60 m, das 141 voltas de 01/11 a 16/11) como um segundo valor, a partir de 31/10, com a mesma tolerância de 0,10 m.
   - **É a correção mais fiel se o CSP for confirmado:** a linha do jogo mudou de lugar, e a checagem continua conferindo que ela fica onde foi medida.
   - A checagem do período já usa a linha medida nas próprias voltas, e por isso não muda.
3. **Uma correção no gravador:** **não proposta.** Nada indica que o gravador esteja errado. Ele grava o que o jogo publica.

**O que eu recomendaria:** confirmar com uma das duas sessões curtas e, se for o CSP, a opção 2.

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

## O que falta

Escrito na parada da A.5. As duas decisões de então já foram tomadas: o sinal para a rodada e a linha no ADR 0007. A rodada, o merge e a Parte B estão feitos (veja acima).

**O pedido está concluído.** As decisões que ficam com você, todas da Parte B (B.4):
- confirmar a causa com uma sessão curta: o app atual com o CSP de antes, ou o app 0.4.0 com o CSP 0.3.1;
- escolher a correção: manter a margem de 2,0 ms, ou registrar uma nova medida da linha a partir de 31/10.

**O risco de manter só a margem:** uma sessão nova com passagem mais lenta pela linha pode passar de 2,0 ms e reprovar o store de novo.

**O backup** `data\ml\_backup_antes_pedido54\` (cerca de 400 MB) fica até você decidir apagar.
