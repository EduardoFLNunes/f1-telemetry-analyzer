# Relatório do pedido 40: limpeza, defeitos do backlog e o app do jogo 0.4.1

- **Pedido:** `docs/prompts/2026-10-28_40_limpeza-e-app-do-jogo.md`
- **Branch:** `etapa/limpeza-e-app-do-jogo`, criada de `develop` (`4782aefb`).
- **Commits:**
  - `30f9fd86` docs: pedido 40
  - `869dae13` Parte B: o app do jogo 0.4.1 em `develop` (merge de `etapa/radio-unidades-e-replay`, só o `0092ed38`)
  - `01d99c95` Parte B: a versão 0.4.1 em `realidade_aumentada.md`
  - `1a30023a` relatório parcial (a sessão parou no limite de uso e foi retomada)
  - `862d135a` Parte C: o código sem uso sai
  - `ec65dcf7` Parte D.1: o gravador abre uma sessão nova quando o contador de voltas volta. Por engano, este commit levou também a renomeação `backend/test_ws_client.py` → `tools/ws_client.py`, só o nome
  - `013f5e07` Parte D.2: a rota das frases do coach acha a gravação na pasta configurada e na do app instalado
  - `51e27380` Parte D.3: o cache da pista só é refeito quando os arquivos do jogo mudam
  - `cc662ef0` Parte D.4: `tools/ws_client.py`, com o cabeçalho, fora da coleta do pytest
  - `f006a508` Parte D.7: a rota da linha de corrida calcula fora do laço do servidor
  - `5edc45fb` Parte E: o que o pedido 40 entregou, no inventário da dashboard
  - mais o commit deste relatório
- **Merge em `develop`:** feito no fim, sem push (o hash está na Parte F).
- **Handoff:**
  - este relatório;
  - `docs/handoff/2026-10-28_40_limpeza-e-app-do-jogo_remocoes.csv`.
- **A pasta:** voltou para `etapa/m1-modelo-do-carro`.

## Resumo

1. **Parte B:** o app do jogo 0.4.1 está em `develop`. O `conferir_lua.py` passa.
2. **Parte C:**
   - **saíram:** `Dashboard.tsx`, `AnalysisPage.tsx`, 17 componentes, 3 utilitários, as funções mortas do mapa, 24 métodos do `client.ts` e 35 das 94 rotas;
   - **ficaram:** o que um teste, um script ou o app do jogo usa, e os quatro globais em `window`.
3. **Parte D:**
   - **corrigidos com teste:** os defeitos 1, 2, 3, 4 e 7c;
   - **conferidos e relatados, sem mudança:** o 5 e o 6;
   - **já não acontecem:** o 7a e o 7b.
4. **A abertura do backend:**
   - **antes:** o cache da pista era remontado a cada abertura, 42,4 s nesta máquina;
   - **depois:** 2,8 s quando o cache já existe.
5. **Testes:**

   | Suíte | Antes | Depois |
   |---|---|---|
   | Backend | 794 | **811**, rodada da pasta `backend` sem argumentos (8 min 54 s) |
   | `vitest run` | 189 | 164 (saíram 25 testes de código morto) |
   | `tsc --noEmit` | sem erros | sem erros |
   | `npm test` (desktop) | 4 | 4 |

## Parte A: preparar

- **As sessões:** antes de trocar de branch, as sessões dos pedidos 38 e 39 estavam paradas (`ListAgents`), e não havia trava do git.
- **A árvore:** só o pedido e uma pasta `recordings/` na raiz.
  - A pasta não é rastreada nem ignorada: a linha do `.gitignore` começa com uma tabulação.
  - Não mexi nela; ela acompanha as trocas de branch.
- **A medição do antes, em `develop`:**

| Suíte | Antes |
|---|---|
| Backend (`pytest tests`, na pasta `backend`) | 794 passando, 9 min 8 s |
| `vitest run` | 189 testes em 17 arquivos, todos passando |
| `tsc --noEmit` | sem erros |
| `npm test` (desktop) | 4 testes, todos passando |
| `conferir_lua.py` (0.4.0) | 0 erros de léxico, blocos ok, 45 chamadas da API e 11 métodos, todos no SDK do CSP |

## Parte B: o app do jogo 0.4.1

- **O que a branch trazia:** `git log develop..etapa/radio-unidades-e-replay` mostrou só o `0092ed38`. O merge (`869dae13`) trouxe:
  - o `manifest.ini`, com `VERSION = 0.4.1`;
  - 37 linhas no `radio_engenheiro.lua`: a cada 2 s, uma janela ligada com menos de 40 px dentro da tela volta para dentro.
- **O `conferir_lua.py` depois do merge:** 0 erros de léxico, blocos ok, 45 chamadas da API e 12 métodos (entrou o `move`), todos no `lib.lua` do SDK do CSP instalado.
- **A documentação:** `docs/realidade_aumentada.md`, seção 5, tem a versão e a correção.
- **O que não fiz:** não rodei o `instalar.ps1` e não escrevi na pasta do jogo.

## Parte C: o código sem uso

A lista completa, com quem usa cada item e a decisão, está no CSV (118 linhas, 92 itens removidos).

**Como procurei os usos:**
- **o front:** o grafo de imports a partir de `main.tsx`. Para cada método do `client.ts`, procurei quem o chama no código que continua;
- **as rotas:**
  - o caminho literal no front, no `desktop`, no app do jogo, no backend inteiro (com `ml`), em `scripts` e `tools`, e nos testes;
  - o nome da função da rota, porque vários testes chamam as funções direto (`backend_main.<nome>`), sem HTTP;
- **os documentos:** registrei também onde cada rota é citada.

**O que saiu:**
- **Front:**
  - `Dashboard.tsx` e `AnalysisPage.tsx`;
  - os componentes `AIDebriefPanel`, `AIEngineerPanel`, `AssistedAnalysisPanel`, `AssistedLapTraces`, `CoachingFeed`, `CognitiveDashboard`, `ElevationProfile`, `GGDiagram`, `Header`, `LiveComparisonPanel`, `LiveTelemetryPanels` (com o `StabilityPanel`), `RacingLineAnalysisPanel`, `ReplayControls`, `SectorComparison`, `SessionLapsPanel`, `SessionTimeline` e `TelemetryTraces`;
  - `types/racingLine.ts`, `utils/comparisonAnalysis.ts` e `utils/sectorTimes.ts`;
  - dois testes que só cobriam esse código: `CoachingFeed.test.ts` e `sectorTimes.test.ts`. São os 25 testes a menos no `vitest`.
- **As funções mortas do mapa:**
  - `OverlayRenderer.tsx`: o bloco do relevo, o cache de superfície, os traços por trecho e o desenho do box (cerca de 320 linhas);
  - `CarRenderer.tsx`: o `drawTrajectory`.
- **`client.ts`:** 24 métodos e 3 tipos que só eles usavam.
- **35 rotas:**
  - as 8 de `/api/debug/*`;
  - `/api/telemetry/live`, `/api/upload/telemetry`, `/api/upload/track`, `/api/data/track`, `/api/data/telemetry`, `/api/data/ai-raceline` e `/api/data/track-limits`;
  - `/api/validation/laps`, `/udp` e `/track`;
  - `/api/analysis/comparison`, `/api/analysis/racing-line`, `GET /api/live/source` e `POST /api/live/telemetry`;
  - `/api/track/current`, `/api/track/cache` (GET e POST), `/api/track/reconstruct` e `/api/car/state`;
  - `/api/recording/start` e `/stop`, `/api/sessions/{id}`, `/api/sessions/{id}/laps/{n}` e `/api/laps/{id}`;
  - as duplicatas da análise assistida: `/api/assisted-analysis/laps`, mais `/api/assisted-analysis/laps/{id}/analysis` em GET e em POST.
  - Também tirei os imports que sobraram e atualizei a lista de rotas do `README.md`.

**O que ficou, e por quê:**
- **Rotas com teste:**
  - `/api/analysis/assisted/lap/{id}` (GET, POST e `/telemetry`) e `/api/laps/{id}/summary` e `/samples`: `test_assisted_analysis_validation_flow`;
  - `GET /api/live/telemetry`: `test_udp_integration_contract`;
  - `POST /api/live/source/{s}`: `test_assetto_shared_memory_gate`;
  - `/api/references/external/fastf1/import`: `test_external_references`.
- **Rotas que um script usa:**
  - `/api/data/comparison`: `backend/test_api_comparison.py`;
  - `/api/test/simulate`: `backend/stress_test.py`.
- **A ferramenta de teste:** `/api/teste/*`, a do pedido 35, usada no teste de ponta a ponta.
- **Na dúvida:**
  - `GET /api/live/comparison`: citada no checklist manual `docs/phase12_distribution_checklist.md`;
  - `GET /api/references/external` e `/{id}`: fazem par com a rota de importar, que tem teste.
- **Os globais em `window`:** `__latestFrame`, `__latestOpponents`, `__telemetryPerf` e `__replayMapDiagnostics` têm leitores (`TrackRenderer`, `DesktopRuntimePanel`).
- **Na dúvida, fora do front:**
  - as funções de `main.py` e os módulos de `core` (kn5, debug, upload) que só as rotas removidas chamavam;
  - não conferi função a função, e alguns têm testes próprios.
- **Na dúvida, no front:** as métricas `dashboardRps`, `tracesRps`, `ggDiagramRps`, `linePanelRps` e `comparisonRps` do painel de desempenho do `TrackRenderer`. Agora dão sempre 0; tirá-las mexe na tela de depuração.

**Os testes da Parte C:**
- `tsc` sem erros;
- `vitest` 164;
- backend 794 (`pytest tests`, 9 min 31 s);
- desktop 4.

**O teste de ponta a ponta:**
- **Como:**
  - o backend do repositório na porta 8011, com a raiz de dados isolada no rascunho;
  - o front de desenvolvimento apontado para ele, numa aba "[teste]" do navegador do app.
  - Para subir o backend isolado pelo painel, pus uma configuração temporária no `.claude/launch.json` e a desfiz no fim (o arquivo é rastreado).
- **As telas abertas:** Sessões, Ao vivo, Volta, Evolução, Coleta de dados e Sistema (Diagnóstico, Depuração e Guia visual).
- **O console:**
  - um erro só: um 404 em `/api/sessions/2026-10-21_20-30-54_vhe_interlagos/laps`, do hero;
  - a rota existe (a resposta é "Recorded session not found");
  - o 404 vem de a pasta de gravações do backend de teste estar isolada e vazia, e não da remoção.
- **O log do backend:** nenhum erro.
- **No fim:** a aba fechada, os dois servidores parados e nenhum `electron.exe` aberto.

**O build do front:** `frontend/dist` foi refeito (`vite build`), porque o app aberto pelo repositório o carrega. A pasta é ignorada pelo git.

## Parte D: os defeitos do backlog

### D.1 O gravador junta duas passagens numa volta: corrigido (`ec65dcf7`)

- **A causa:**
  - o `RecordingRuntime._should_rotate` já abria uma sessão nova quando a sessão do jogo recomeçava, mas pedia, no mesmo quadro, o contador de voltas caindo 2 ou mais e o relógio da volta caindo mais de 5 s;
  - na gravação `2026-10-04_02-24-04` (linha 125.041 do `player.jsonl`), o contador cai de 14 para 1 com o relógio ainda em 264,717 s. O relógio só zera no quadro seguinte (0,468 s);
  - as duas condições nunca apareceram juntas, e a segunda passagem continuou no mesmo arquivo. A "volta 5" ficou com 85,107 s e, 46 min depois, 89,388 s (1:25,107 e 1:29,388).
- **A correção:** o contador que diminui basta para abrir a sessão nova (uma pasta nova, pelo caminho que já existia).
  - O formato do arquivo não muda.
  - Vale só para as gravações novas; nenhuma gravação foi regravada.
  - O app instalado (0.5.0) só recebe a correção no próximo instalador.
- **O teste:** `backend/tests/test_gravador_corta_reinicio.py`, com 5 testes.
  - Os dados simulados cobrem: o contador antes do relógio; os dois juntos; o contador caindo uma volta só; e as voltas normais, que ficam numa sessão.
  - O teste com a gravação real lê as 80 linhas em volta do reinício da gravação de 04/10. Ele é pulado se o arquivo não existir.
  - **Antes:** 3 falhas (o contador antes do relógio, o que cai uma volta e a gravação de 04/10). **Depois:** os 5 passam.
- **O que fica de fora:** um reinício durante a volta 1 não muda o contador. Ele não é detectado sem olhar os quadros seguintes.
- **O efeito:** uma sessão do jogo reiniciada vira duas pastas de gravação, e cada uma entra no coach, no store v2 e no relatório como uma sessão. A regra de nenhum deles muda; muda o que o gravador entrega.

### D.2 A rota das frases do coach só procurava em `data/recordings`: corrigido (`013f5e07`)

- **Antes:** o `LapDataLoader` procurava só em `data/recordings` do repositório e da raiz do backend.
- **Agora:** procura também na pasta configurada (`TELEMETRY_RECORDING_DIR`) e na do app instalado (`ml.config.installed_app_recordings_root()`, a mesma que o `list_all_sessions` lê).
- **A regra do nome repetido:** é a mesma do `list_all_sessions`. A sessão em duas pastas é um erro ("compare as duas antes de seguir"), e a rota responde 404 com essa mensagem.
- **Uma diferença do `list_all_sessions`:** a regra vale para a sessão pedida, conferida pelo caminho direto em cada pasta, sem varrer todas as sessões.
  - O motivo: o `list_all_sessions` leva 1,6 s nas 159 sessões desta máquina.
  - Hoje não há nenhuma sessão repetida entre as duas pastas.
- **A lista de voltas da análise assistida não muda:** as pastas novas servem só para achar uma volta pelo id.
- **O teste:** `backend/tests/test_rota_do_coach_acha_a_gravacao.py`, com 5 testes: a pasta configurada, a do app instalado, o repositório, o nome repetido e a volta que não existe.
  - **Antes:** 3 falhas (`FileNotFoundError`). **Depois:** os 5 passam.

### D.3 O cache da pista refeito a cada abertura: corrigido (`51e27380`)

- **A causa:**
  - `_cache_predates_marking_classification` exige `boundsLeft[0].elevation`;
  - a pista montada pelos limites pintados (`construct_track_from_limits`) sai sem esse campo;
  - todo cache recém-gravado parecia antigo, e o backend remontava a pista a cada abertura.
- **A correção:** uma chave da origem num arquivo ao lado do cache (`<cache>.origem.json`):
  - **o que entra:** a versão da chave, os arquivos do jogo que o manifesto aponta (nome, tamanho, data e o sha256 do conteúdo; são 19 arquivos em Interlagos) e nunca o `data.acd`;
  - **a decisão:** a mesma lista com os mesmos tamanhos e datas usa o cache. Uma data mudada com o mesmo tamanho cai no sha256 do conteúdo. Um conteúdo mudado remonta;
  - **o JSON do cache não ganha campo:** é de lá que o ML tira a geometria, e o `geometry_id` não muda.
  - Sem o arquivo da chave, vale a checagem antiga. Por isso, a primeira abertura depois desta correção ainda remonta o cache uma vez e grava a chave.
- **O teste:** `backend/tests/test_cache_da_pista.py`, com 5 testes. A montagem é trocada por uma falsa que conta as chamadas; o cache, o serializador e as checagens são os reais.
  - **Antes:** 4 falhas; só passava o do `data.acd` nunca lido. **Depois:** os 5 passam.
- **O tempo de abertura do backend:** o backend do repositório na porta 8011, com a raiz de dados isolada no rascunho, medido até o `/api/health` responder.

| Abertura | Antes | Depois |
|---|---|---|
| 1ª (sem cache) | 65,1 s* | 42,4 s (monta o cache e grava a chave) |
| 2ª | 64,1 s* (remontou: "Rebuilding track cache written before the drawn map had its own geometry") | **2,8 s** (usou o cache) |
| 3ª | — | **2,8 s** |

\* Medido com a suíte do backend rodando ao lado. A 1ª abertura do "depois" mostra o custo da montagem sem carga: 42,4 s. Antes da correção, toda abertura pagava esse custo.

- **Atenção:** a primeira vez que o backend de desenvolvimento abrir com a raiz no repositório, ele ainda remonta o `data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json` do repositório uma vez (sem o arquivo da chave, vale a checagem antiga). Ele já remontava a cada abertura (a última vez foi em 24/10, às 13:42). Depois disso, para.

### D.4 `backend/test_ws_client.py` falhava na coleta: corrigido (`ec65dcf7` e `cc662ef0`)

- **A mudança:** o script virou `tools/ws_client.py`, com um cabeçalho de uso, sem instalar nada.
- **Antes:** rodado na pasta `backend`, o pytest colhia `test_ws_client.py::test_ws` e falhava ("async def functions are not natively supported").
- **Depois:** a suíte rodada de `backend`, sem argumentos, passa (811).
- **O que continua sendo colhido:** `backend/test_api_comparison.py::test_comparison`, que passa sem o backend no ar, porque trata o erro. Não mexi.

### D.5 `/api/sessions` e a conferência contam as voltas de jeitos diferentes: relatado, sem mudança

- **Quem usa `/api/sessions`, depois da Parte C:**
  - **o hero de Sessões:** a última sessão, depois lida na conferência;
  - **a tela Sessões:** `voltasGravadas` = o número de voltas do gravador;
  - **a Coleta de dados:** "N voltas" na lista de gravações;
  - **o teste `test_assisted_analysis_validation_flow`:** `list_recorded_sessions`;
  - **o hero:** ainda usa `/api/sessions/{id}/laps` e `/api/laps/{id}/replay` para o trecho da volta de referência.
- **Quem usa a conferência:** o hero, a tela Sessões (as válidas e a melhor) e a Coleta.
- **A decisão:** não são só as telas novas que usam `/api/sessions`: um teste do backend também a chama. Pela regra do pedido, não mudei.
- **O que muda com o D.1:** as sessões novas do gravador passam a ser cortadas no reinício, o que tira uma das causas da diferença (as passagens juntas sob o mesmo número).

### D.6 O `timestamp` do gravador engasga: conferido e relatado, sem mudança

**Quem ainda usa o `timestamp` no lugar do cronômetro do jogo:**
- **Os portões de qualidade do ML** (`ml/preprocessing/cleaning.py` e `quality.py`):
  - **a frequência** (`sample_rate_hz`): o número de amostras pela diferença entre o primeiro e o último `timestamp`. Um engasgo de +357 ms numa volta de cerca de 90 s muda a frequência em cerca de 0,4%, longe do portão de 20 Hz (40 Hz na referência);
  - **os buracos** (`sample_gaps`): o maior intervalo entre `timestamp`s e quantos passam de 0,5 s. O engasgo medido (0,357 s) fica abaixo do limite;
  - **a limpeza:** ordena as amostras pelo `timestamp` e tira as repetidas.
- **O resto:**
  - **o store v2** (`store_v2.py`): o intervalo entre o fim de uma volta e o começo da seguinte, para costurar o tempo na virada;
  - **o alinhamento** (`alignment.py`): só usa o `timestamp` quando o cronômetro da volta não cresce;
  - **a análise assistida** (`assisted_analysis/utils.py`): o tempo decorrido, também como reserva;
  - **o inventário** (`inventory.py`): o início e o fim da volta em hora de parede;
  - **a Coleta ao vivo** (`coleta/ao_vivo.py`): o instante do quadro;
  - **a comparação ao vivo** (`comparison_analysis.py`);
  - **o gravador:** o limite de amostragem.

**A decisão:** nenhum uso se mostrou errado para o engasgo medido, e mudar os portões ou a limpeza mudaria uma regra do store v2. Não mudei.

### D.7 A conferir, do inventário da dashboard

- **a. O canto inferior direito do mapa lê `latestFrame` no replay:** não acontece mais.
  - O `MapReadout` só aparece no mapa do `TrackRenderer`, que hoje só existe em Sistema › Depuração.
  - O replay do store (`startOfflineReplay`) só era aberto pela Pista (`Dashboard`) e pela Análise (`SessionLapsPanel`), que saíram. Hoje só um teste do store o chama.
  - A tela Volta e a Ao vivo têm replays próprios, fora do store.
- **b. `addFrame` mexe no store no replay:** não acontece mais, pelo mesmo motivo: o replay do store nunca fica ativo no app.
- **c. A rota da linha de corrida travava o servidor:** ainda acontecia (o mapa da depuração a pede a cada 6 s), e foi corrigida (`f006a508`).
  - **A correção:** o cálculo roda com `asyncio.to_thread`, fora do laço do servidor.
  - **O teste:** `backend/tests/test_rota_linha_de_corrida_nao_trava.py`. O cálculo é trocado por um que dorme 0,4 s, e um relógio no mesmo laço mede o maior intervalo entre os seus tiques.
  - **Antes:** o laço ficou parado 0,41 s. **Depois:** passa, com o limite de 0,2 s.
  - No ponta a ponta, a rota respondeu 200 com a depuração aberta.

### Os itens do backlog

O `docs/backlog.md` não foi editado (o Cowork o mantém). Os itens resolvidos:

| Item do backlog | Situação | Commit |
|---|---|---|
| O gravador junta duas passagens numa volta (pedido 29, achado 1) | resolvido | `ec65dcf7` |
| A rota das frases do coach só procura em `data/recordings` (pedido 30, achado 2) | resolvido | `013f5e07` |
| O cache da pista refeito a cada abertura (pedido 28, achado 1) | resolvido | `51e27380` |
| `backend/test_ws_client.py` falha na suíte rodada de `backend` (pedido 30) | resolvido | `ec65dcf7` e `cc662ef0` |
| `/api/sessions` e a conferência contam diferente (pedido 29, achado 2) | relatado, sem mudança (D.5) | — |
| O `timestamp` do gravador engasga (pedido 14) | conferido e relatado, sem mudança (D.6) | — |
| O canto do mapa e o `addFrame` no replay (inventário) | já não acontecem (D.7a e b) | `862d135a` (a Parte C tirou quem abria o replay) |
| A rota da linha de corrida trava o servidor (inventário, 2.G) | resolvido | `f006a508` |
| A limpeza (inventário, seção 7, item 6) | feito | `862d135a` |
| O app do jogo 0.4.1 fora de `develop` | resolvido | `869dae13` |

## Parte E: documentação

- `docs/dashboard_inventario.md`: "O que o pedido 40 entregou", no fim da seção 7 (`5edc45fb`).
- `docs/realidade_aumentada.md`: a versão 0.4.1 do app do jogo (`01d99c95`).
- `README.md`: a lista de rotas, sem as que saíram (`862d135a`).

## Testes: o antes e o depois

| Suíte | Antes (`develop`) | Depois da Parte C | No fim |
|---|---|---|---|
| Backend | 794 (`pytest tests`) | 794 | **811** (pytest rodado da pasta `backend` sem argumentos, 8 min 54 s: os 794, mais os 16 novos da Parte D e o `test_api_comparison.py` da raiz) |
| `vitest run` | 189 em 17 arquivos | 164 em 15 | 164 em 15 |
| `tsc --noEmit` | sem erros | sem erros | sem erros |
| `npm test` (desktop) | 4 | 4 | 4 |
| `conferir_lua.py` | 0.4.0: ok | 0.4.1: ok | 0.4.1: ok |

Os 16 testes novos da Parte D (5 + 5 + 5 + 1) passam, e falhavam antes da correção (a saída de cada um está nas seções do D.1, D.2, D.3 e D.7). No D.3, o teste do `data.acd` já passava antes.

## Parte F: merge e a pasta

- **O merge:** `etapa/limpeza-e-app-do-jogo` em `develop`, sem push (o hash está na resposta do chat).
- **A pasta:** antes de trocar de branch, conferi que as outras sessões estavam paradas e que a árvore estava limpa. Ela voltou para `etapa/m1-modelo-do-carro`.

## O que não foi feito

- **O que o pedido deixou de fora:**
  - o horário 3 h adiantado do gravador;
  - a geometria única (ADR 0002);
  - o `stash@{0}`;
  - qualquer regra do coach, do store v2 ou do relatório de evolução.
- **O que as regras do pedido proíbem:**
  - não instalei nem atualizei pacotes;
  - não gerei instalador;
  - não mexi no app instalado nem na pasta do jogo;
  - as gravações só foram lidas.
- **O remoto:** nada foi enviado.
- **O backlog:** não editei o `docs/backlog.md`.
