# Relatório do pedido 28: reempacotamento do app instalado e aba "Coleta de dados" (parcial, parado na Parte F)

- **Pedido:** `docs/prompts/2026-10-11_28_reempacotamento-e-coleta.md`
- **Branch:** `etapa/reempacotamento-e-coleta`, com merge em `develop`. Nada foi enviado ao remoto.
- **Commits e merge:**
  - `1d15bce7` docs: pedido 28 (reempacotamento do app instalado e aba Coleta de dados)
  - `20f8e44c` docs: arquivos do Cowork do redesenho do dashboard (inventario, visoes, imagens e prototipo navegavel)
  - `d8205901` Coleta: registro do que os modelos precisam, com teste contra o store v2, a M1 e o gravador (pedido 28, Parte B)
  - `0fc4c71b` Empacotamento: backend em --onedir, versao 0.3.0-coleta-modelos, coach lendo o modelo do repositorio configurado e versao e commit do app no metadata.json (pedido 28, Parte C)
  - `8aae52da` Coleta: aba Coleta de dados, com o estado ao vivo de cada canal, a conferencia de cada volta pelos portoes do pipeline e a previa da M1 (pedido 28, Parte D)
  - `41744d16` Testes da coleta: configuracao, coach pelo repositorio, estado de cada canal, corte igual ao iter_laps, veredito da volta e da sessao, contagem oficial (pedido 28, Parte E.1)
  - `67b3563b` Coleta: script que roda a conferencia de fim de sessao numa gravacao ja feita e compara com o store v2 (pedido 28, Parte E.2)
  - `e6f4eb7f` docs: --onedir, caminho do modelo do coach e versao 0.3.0 nos READMEs; secao 8 do coach vira como gravar uma sessao de treino; como a contagem da M1 e conferida agora (pedido 28, Parte H)
  - `e0f64ece` Merge etapa/reempacotamento-e-coleta (pedido 28: reempacotamento do app instalado e aba Coleta de dados). **O instalador saiu deste commit.**
  - o commit deste relatório, com o handoff: "Relatório parcial do pedido 28: reempacotamento e aba Coleta de dados (parado na Parte F)"
- **Arquivos de handoff** (sha256, 12 primeiros dígitos):
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_relatorio.md` (este)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta.patch` (de `c521cf0d` até o merge, sem os arquivos do Cowork; `95b9e63e478e`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_testes.txt` (suítes em `develop`, `e0f64ece`; `c041201d8c68`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_conferencias.json` (E.2, saída de `tools/conferir_sessao.py`; `76e913ab6e93`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_pacote_rotas.json` (E.3: `/api/coleta/antes` e a conferência de 04/10 feitas pelo backend empacotado; `e900c6874eb9`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_pacote_logs.txt` (E.3: logs do Electron e do backend empacotado; `0c7214377a70`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_captura_1_antes.png` (`8f4144f2b309`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_captura_2_durante.png` (`c74a115e3502`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_captura_3_conferencia_10-10.png` (`0e3c796526b8`)
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_captura_4_conferencia_04-10.png` (`265cc8bcef75`)

**O que não mudou:**
- Nenhum modelo, critério, store ou regra do coach. No coach mudou só de onde ele lê o modelo e como a referência é escolhida.
- O `productName`, o `appId` e a pasta de dados (`%APPDATA%\Automobilista Telemetria`).
- As gravações das duas pastas foram só lidas. O app instalado e os arquivos do jogo não foram tocados (o backend lê os arquivos da pista do jogo para montar o cache, só lendo).
- Não instalei nem atualizei pacotes. O Electron 42.3.3 e as ferramentas do NSIS saíram do cache local.
- Uma exceção, relatada no achado 1: em 11/10, o backend de desenvolvimento que abri para ver a aba regravou `data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json`. O `geometry_id` continua `0ed16f0dd2225990`.

## Em resumo

1. **Parte A:** as quatro conferências foram feitas. Duas correções ao contexto, nenhuma trava:
   - o backend empacotado procura o modelo do coach na **pasta de dados** (`%APPDATA%`), não na de recursos. Lá está o modelo antigo de 24/08 e não há geometria; o resultado é o mesmo, o coach do app instalado fica calado;
   - a contagem oficial da M1 **não existia em código**: o "0 de 5" era conferido à mão. Ela foi escrita neste pedido (`core/coleta/oficial.py`), com a regra da seção 6.
2. **Parte B:** registro com 33 itens em 5 grupos (`backend/core/coleta/requisitos.py`). O teste passa uma amostra pelo caminho real do gravador até o arquivo e confere o registro contra o store v2 e a regra da M1.
3. **Parte C:** backend em **`--onedir`**, versão **`0.3.0-coleta-modelos`**. O coach lê o modelo e a geometria do repositório configurado; a referência (volta da IA, sua melhor ou desligado) virou configuração da aba. O `metadata.json` de cada sessão nova ganha a versão e o commit do app.
4. **Parte D:** aba "Coleta de dados" com antes, durante e depois, e rotas `/api/coleta/...`.
5. **Parte E:**
   - suítes: **735** testes do backend e **145** do front passando em `develop`, com 50 e 7 testes novos;
   - E.2: as duas sessões dão **"Não conta para a M1: faltam a guinada e as velocidades no referencial do carro"**. A de 10/10 diz também que o indicador de IA não foi gravado. As voltas que a conferência deixa entrar são **exatamente as do store v2** (12 e 4), com diferença de tempo 0,0 s;
   - E.3: o pacote abre isolado e a aba funciona, com o coach achando o modelo pelo repositório. Nenhuma extração em `%TEMP%`, e `%APPDATA%` ficou igual antes e depois.
6. **Instalador:** `desktop\dist\Automobilista-Telemetria-Setup-0.3.0-coleta-modelos.exe`, 228.873.657 bytes (218 MB), sha256 `7b27fe71ffe9be00da58180140e910a171a63b00d0e9f37f1b61de9e2775c0b6`.
7. **Achados fora do pedido:**
   - o cache da pista é refeito **a cada abertura** do backend (cerca de 36 s);
   - o backend `--onefile` antigo deixou **2,8 GB** de pastas `_MEI*` no `%TEMP%`;
   - houve sessões novas gravadas no app antigo em 11/10 e 13/10.
8. **Parado na Parte F.** Os passos de instalação estão no fim. As Partes G e o item do backlog esperam o seu aviso.

## Parte A: conferências antes do código

| conferência | o que achei | bate? |
|---|---|---|
| 1. O gravador grava os campos do pedido 18, o indicador de IA e o `carModel` | Sim. Em `carPhysics`: `tyres.tyreTempInner/Middle/Outer`, `brakes.brakeTemp[4]` e `brakeBias`, `motion.localVelocity` e `localAngularVelocity`, e a embreagem certa (`core/car_physics.py`, `build_player_car_physics`). O indicador vai em `carPhysics.controls.isAIControlled`. O `carModel` vai no `metadata.json`, em `metadata.carModel` (`main.recording_metadata`). | sim |
| 2. Como o backend empacotado acha o modelo e a geometria do coach | Ver abaixo. O modelo é procurado na pasta de dados, não na de recursos. | **com correção** |
| 3. Onde o Electron e o backend gravam empacotados | Ver abaixo. | sim |
| 4. O build-info marca a árvore suja com arquivo não rastreado? | Sim: o `stamp-build-info.js` usa `git status --porcelain`, que lista os não rastreados. No build, eram 4 (ver Parte C). O build não depende deles. | sim |

**Onde cada item 1 está coberto em teste:**
- `backend/tests/test_canais_fisicos.py`: `RecordedChannelsTest` (adaptador → bloco gravado) e `ReaderTest` (adaptador → leitor → amostra → bloco).
- `backend/tests/test_lap_origin.py`, `RecorderTests`: o indicador do adaptador até a amostra. O `carModel` é conferido só pelo texto do `main.py` (`'"carModel": source_manager.current_car_model()'`).
- **Novo:** `backend/tests/test_coleta_requisitos.py` passa uma amostra pelo caminho real (adaptador → `TelemetrySample` → `RuntimeState.update_car` → `SessionRecorder`) até o `player.jsonl` e o `metadata.json`, e confere que todo item do registro, inclusive o `carModel`, lê um valor do que foi escrito.

**Item 2, como era antes deste pedido no app instalado:**
- **Raiz de recursos:** `AT_BACKEND_RESOURCE_ROOT` = `process.resourcesPath` (`<instalação>\resources`).
- **Raiz de dados:** `AT_BACKEND_RUNTIME_ROOT` = `app.getPath('userData')` = `%APPDATA%\Automobilista Telemetria`.
- **Modelo:** `model_path(runtime_root, pista)`, só na raiz de dados: `%APPDATA%\Automobilista Telemetria\data\reference_models\vhe_interlagos.json`. Esse arquivo existe e é o modelo antigo (24/08, sha256 `9d08d705…`).
- **Geometria:** `find_official_geometry([runtime_root, resource_root])`, nesta ordem. Não existe em nenhuma das duas, porque o `extraResources` só leva `*.optimal.json`. Com o modelo tendo `geometry_id`, o coach ficava calado.
- **Linha ótima:** `[runtime_root, resource_root]`; a enviada no pacote é achada nos recursos.
- **Referência:** `AT_COACH_REFERENCE`, `volta_ia` por padrão.
- **A correção ao contexto:** o pedido diz que o backend procura os modelos "na pasta de recursos do Electron". A geometria e a linha ótima, sim; o modelo, não, é na pasta de dados. A conclusão é a mesma: o coach empacotado não acharia o modelo novo.

**Item 3, onde o app empacotado grava:**
- **Pasta de usuário do Electron:** `%APPDATA%\Automobilista Telemetria`, que sai do `productName`. Ela guarda:
  - o perfil do Chromium: `Cache`, `Code Cache`, `GPUCache`, `Local Storage`, `Network`, `Session Storage`, `Local State`, `DIPS` e outros;
  - `assetto-corsa-setup.json`.
- **Logs:** `%APPDATA%\Automobilista Telemetria\logs\desktop.log` e `backend.log` (`AT_DESKTOP_LOG_DIR` muda).
- **Backend:** tudo sob a raiz de dados, a mesma pasta: `data\recordings`, `data\cache\tracks`, `data\assisted_analysis`, `data\external_references` e `data\fastf1_cache`. Neste pedido entram também `data\configuracao` e `data\verificacoes`.
- **`%TEMP%\_MEI*`:** a extração do `--onefile` antigo, cerca de 0,4 GB por abertura.
- **Base do teste E.3:** a variável nova `AT_DESKTOP_USER_DATA_DIR` chama `app.setPath('userData')` antes de qualquer caminho ser pedido. Os logs e a raiz de dados do backend derivam dela.

**Outras diferenças entre o contexto e o repositório, nenhuma bloqueante:**
- **A contagem oficial "no `atualizar_coach`":** não havia código que contasse as sessões da M1; o "0 de 5" era conferido à mão nos relatórios. Escrevi `core/coleta/oficial.py` com a regra da seção 6, explicitada na Parte D.
- **O instalador mais recente:** é mesmo o `0.1.7-phase-16` (25/08), mas `desktop/dist` tem também um `0.2.0-assetto-udp` (14/06), de versão maior. A versão nova, `0.3.0`, é maior que as duas.
- **O `.spec`:** é ignorado pelo git (`*.spec`) e refeito a cada build pelo `build_backend.ps1`. A mudança para `--onedir` está no script; o `.spec` saiu com ela.

## Parte B: registro do que os modelos precisam

**Onde:** `backend/core/coleta/requisitos.py`, 33 itens. A tabela abaixo foi gerada pelo próprio módulo (`python -m core.coleta.requisitos`).

**Regras das faixas:**
- **onde o inventário do pedido 18 mediu o campo:** `[p1 − m, p99 + m]`, com a margem `m = 0,5 × (p99 − p1)`, cortada nos limites físicos do item (pedal entre 0 e 1, temperatura e carga não negativas). O p1 e o p99 ficam copiados no módulo, porque o backend empacotado não lê `docs/`, e um teste confere a cópia contra o JSON;
- **onde não mediu:** um limite físico com folga, e a fonte da faixa diz isso. É o caso dos canais que só passaram a ser gravados no pedido 18 (guinada, velocidades locais, freios, temperaturas de superfície) e dos de base que o inventário não listou;
- **o desgaste do pneu** é a exceção: o inventário só viu pneus novos (p1 99,94), e a faixa medida não serviria. Ficou 0 a 100.

**Preenchimento mínimo:** 90% nos cinco canais do portão de qualidade (o limiar do próprio portão) e 95% nos outros (o das checagens do pedido 18 e da M1).

**Grupo a mais:** "Contexto do store v2" (combustível, desgaste, índice de aderência), porque o teste exige que toda coluna do store esteja no registro.

| grupo | item | campo gravado | coluna do store v2 | quem usa | unidade | faixa | preench. mín. | M1 |
|---|---|---|---|---|---|---|---:|---|
| Base | Cronômetro do jogo | `lap_time` | `lap_time_s`, `elapsed_s` | coach, store v2 e LSTM | s | 0 a 600 | 95% |  |
| Base | Número da volta | `lap_number` | — | coach, store v2 e LSTM, origem da volta | volta do jogo | 0 a 1.000 | 95% |  |
| Base | Distância na volta | `distanceAlongTrack` | — | store v2 e LSTM | m | 0 a 4.400 | 95% |  |
| Base | Posição x e z | `world_x, world_z` | `x`, `z`, `lateral` | coach, store v2 e LSTM | m (mundo do jogo) | −2.000 a 2.000 | 95% |  |
| Base | Velocidade | `speedKmh` | `speed_kmh` | coach, store v2 e LSTM | km/h | 0 a 360 | 95% |  |
| Base | Acelerador | `carPhysics.controls.throttle` | `throttle` | coach, store v2 e LSTM | 0 a 1 | 0 a 1 | 90% |  |
| Base | Freio | `carPhysics.controls.brake` | `brake` | coach, store v2 e LSTM, bloco técnica do relatório de evolução | 0 a 1 | 0 a 1 | 90% |  |
| Base | Volante | `carPhysics.controls.steerAngle` | `steering`, `steer_angle` | store v2 e LSTM, bloco técnica do relatório de evolução, modelo do carro (M1) | sem unidade documentada | −0,9713 a 0,9981 | 90% |  |
| Base | Marcha | `carPhysics.controls.gear` | `gear` | store v2 e LSTM | marcha do jogo (0 = ré, 1 = neutro) | 0 a 9 | 95% |  |
| Base | Rotação | `carPhysics.controls.rpm` | `rpm` | store v2 e LSTM | rpm | 0 a 15.000 | 95% |  |
| Origem da volta | Indicador de IA | `carPhysics.controls.isAIControlled` | — | origem da volta, coach, store v2 e LSTM | ligado ou desligado | — | 95% |  |
| Origem da volta | Modelo do carro | `metadata.carModel` | — | origem da volta, store v2 e LSTM | nome do jogo | — | 95% |  |
| Origem da volta | Pista | `track` | — | origem da volta, store v2 e LSTM | nome do jogo | — | 95% |  |
| Limites de pista | Pneus fora | `carPhysics.environment.tyresOut` | — | limites de pista, store v2 e LSTM | rodas fora (0 a 4) | 0 a 4 | 95% |  |
| Limites de pista | Fora da pista | `carPhysics.environment.offTrack` | `off_track` | limites de pista, store v2 e LSTM | sim ou não | — | 95% |  |
| Modelo do carro (M1) | Guinada | `carPhysics.motion.localAngularVelocity.y` | `yaw_rate` | modelo do carro (M1), store v2 e LSTM | rad/s | −5 a 5 | 95% | obrigatório |
| Modelo do carro (M1) | Velocidade longitudinal (referencial do carro) | `carPhysics.motion.localVelocity.z` | `velocity_long` | modelo do carro (M1), store v2 e LSTM | m/s | −20 a 100 | 95% | obrigatório |
| Modelo do carro (M1) | Velocidade lateral (referencial do carro) | `carPhysics.motion.localVelocity.x` | `velocity_lat` | modelo do carro (M1), store v2 e LSTM | m/s | −30 a 30 | 95% | obrigatório |
| Modelo do carro (M1) | Temperatura dos freios | `carPhysics.brakes.brakeTemp[0..3]` | `brake_temp_fl`, `brake_temp_fr`, `brake_temp_rl`, `brake_temp_rr` | modelo do carro (M1), store v2 e LSTM, bloco técnica do relatório de evolução | °C | 0 a 1.200 | 95% |  |
| Modelo do carro (M1) | Distribuição dos freios | `carPhysics.brakes.brakeBias` | — | modelo do carro (M1) | fração na dianteira | 0 a 1 | 95% |  |
| Modelo do carro (M1) | Temperatura do núcleo do pneu | `carPhysics.tyres.tyreCoreTemperature[0..3]` | `tyre_core_temp_fl`, `tyre_core_temp_fr`, `tyre_core_temp_rl`, `tyre_core_temp_rr` | modelo do carro (M1), store v2 e LSTM, bloco técnica do relatório de evolução | °C | 0 a 130,2 | 95% |  |
| Modelo do carro (M1) | Temperatura da superfície do pneu, interna | `carPhysics.tyres.tyreTempInner[0..3]` | — | modelo do carro (M1) | °C | 0 a 200 | 95% |  |
| Modelo do carro (M1) | Temperatura da superfície do pneu, central | `carPhysics.tyres.tyreTempMiddle[0..3]` | — | modelo do carro (M1) | °C | 0 a 200 | 95% |  |
| Modelo do carro (M1) | Temperatura da superfície do pneu, externa | `carPhysics.tyres.tyreTempOuter[0..3]` | — | modelo do carro (M1) | °C | 0 a 200 | 95% |  |
| Modelo do carro (M1) | Carga na roda | `carPhysics.tyres.wheelLoad[0..3]` | `wheel_load_fl`, `wheel_load_fr`, `wheel_load_rl`, `wheel_load_rr` | modelo do carro (M1), store v2 e LSTM | N | 0 a 8.400 | 95% |  |
| Modelo do carro (M1) | Escorregamento | `carPhysics.tyres.wheelSlip[0..3]` | `wheel_slip_fl`, `wheel_slip_fr`, `wheel_slip_rl`, `wheel_slip_rr`, `wheel_slip` | modelo do carro (M1), store v2 e LSTM | adimensional (medida do jogo) | 0 a 3,06 | 95% |  |
| Modelo do carro (M1) | Pressão do pneu | `carPhysics.tyres.tyrePressure[0..3]` | `tyre_pressure_fl`, `tyre_pressure_fr`, `tyre_pressure_rl`, `tyre_pressure_rr` | modelo do carro (M1), store v2 e LSTM | psi | 8,48 a 26,58 | 95% |  |
| Modelo do carro (M1) | Curso da suspensão | `carPhysics.suspension.suspensionTravel[0..3]` | — | modelo do carro (M1) | m | 0,019 a 0,0826 | 95% |  |
| Modelo do carro (M1) | Aceleração (accG) | `carPhysics.motion.accG.{lateral, longitudinal, vertical}` | `lateral_g`, `longitudinal_g` | modelo do carro (M1), store v2 e LSTM, bloco técnica do relatório de evolução | g | −4,132 a 4,141 | 90% |  |
| Modelo do carro (M1) | Embreagem | `carPhysics.controls.clutch` | — | modelo do carro (M1) | 0 a 1 | 0 a 1 | 95% |  |
| Contexto do store v2 | Combustível | `carPhysics.carState.fuel` | `fuel` | store v2 e LSTM | L | 0 a 150 | 95% |  |
| Contexto do store v2 | Desgaste do pneu | `carPhysics.tyres.tyreWear[0..3]` | `tyre_wear` | store v2 e LSTM | % (100 = novo) | 0 a 100 | 95% |  |
| Contexto do store v2 | Índice de aderência estimado | `carPhysics.tyres.estimatedGripIndex[0..3]` | `grip_index` | store v2 e LSTM | adimensional (calculado pelo app) | 0 a 1,2 | 95% |  |

**O teste** (`backend/tests/test_coleta_requisitos.py`, 12 casos) quebra se um dos lados sair do lugar:
- toda coluna da grade do store v2 (`STORE_COLUMNS` + `PHYSICAL_COLUMNS`) tem item no registro, e todo item aponta para coluna que existe;
- os obrigatórios da M1 são `yaw_rate`, `velocity_long` e `velocity_lat`, com 95%;
- todo item lê um valor do que o gravador escreveu, pelo caminho do gravador atual, e o achatamento do ML (`flatten`) lê o mesmo valor na coluna que o item declara;
- as faixas medidas seguem a regra da margem, e o p1 e o p99 copiados são os do JSON do inventário.

## Parte C: reempacotamento

| mudança | onde |
|---|---|
| Versão `0.3.0-coleta-modelos`; rótulo da janela "Coleta de dados" (era "Phase 16") | `desktop/package.json`, `desktop/main.js` |
| Versão do serviço `coleta-modelos` (era `phase-16-consolidation`). O app novo não usa um backend antigo que esteja na porta 8000: ele aparece como conflito de porta. | `backend/main.py`, `desktop/main.js` |
| **`--onedir`:** `backend/dist/automobilista-backend/` (executável e `_internal/`, 423 MB) | `backend/packaging/build_backend.ps1` (o `.spec` sai dele) |
| `extraResources` leva a pasta para `resources/backend/automobilista-backend/` | `desktop/package.json` |
| Busca do executável na mesma ordem, com o caminho novo: `AT_BACKEND_EXE_PATH`, recursos, `desktop/resources`, `backend/dist/...` e `dist/...` do repositório | `desktop/main.js` |
| **Coach:** lê `data/reference_models/vhe_interlagos.json` e `.geometry.json` do repositório configurado, só lendo; sem os arquivos ou com outro `geometry_id`, fica calado e a aba diz por quê | `core/assisted_analysis/service.py`, `core/coleta/configuracao.py`, `core/coleta/estado.py` |
| **Repositório padrão:** `AT_REPO_PATH`; rodando do código-fonte, o próprio repositório; no app instalado, o `repoPath` carimbado no `build-info.json` (`C:\Users\Dokas\Desktop\f1-telemetry-analyzer`), se ainda tiver `.git`. Editável na aba. | `desktop/main.js`, `desktop/scripts/stamp-build-info.js` |
| **Referência:** volta da IA, sua melhor ou desligado, na aba, em `data/configuracao/app.json`. Vale na hora: o serviço e o coach ao vivo esquecem o modelo carregado (`reload_coach`, `reset_model`). `AT_COACH_REFERENCE`, quando definida, vale mais e trava a escolha da aba. | `core/coleta/configuracao.py`, `core/live/driving_coach.py`, `backend/main.py` |
| **Origem do dado:** o `metadata.json` de cada sessão nova ganha `appVersion`, `appCommit`, `appCommitDirty` e `appPackaged`, sem mudar os campos que já existiam. O Electron empacotado passa o carimbo do build; rodando do código-fonte, o backend pergunta ao git. | `core/coleta/origem_app.py`, `backend/main.py` |
| Teste do pacote sem tocar na pasta real: `AT_DESKTOP_USER_DATA_DIR` | `desktop/main.js` |

**Por que o `--onedir` entrou sem problema:** nada quebrou. O backend empacotado subiu, leu o modelo, rodou o pipeline do ML na conferência e fechou com o app (E.3).

**O inventário e o store v2 continuam lendo** uma sessão com os campos novos no `metadata.json`. O teste `NewMetadataFieldsTest` passa uma sessão sintética por `ml.data.inventory.read_session` e `store_v2.materialize_session`: as voltas válidas, o `carModel` e os canais saem como antes.

**O pacote leva o `ml` da conferência sem o torch:**
- **entraram,** pelo grafo do PyInstaller: `ml.data.recordings`, `ml.preprocessing.quality`, `ml.track.geometry`, `ml.data.origin`, `core.coleta.conferencia` e `routers.coleta`;
- **ficaram de fora:** `torch`, `ml.validation` e `ml.data.ai_detector`;
- **o portão do box:** foi copiado para `core/coleta/conferencia.py`, porque o detector importa `ml.validation`, que puxa o torch. Um teste confere que a cópia e o original dão o mesmo resultado.

**Build** (de `develop`, `e0f64ece`, em 14/10):
- o `build-info.json` saiu com `dirty: true`, por 4 arquivos não rastreados que o build não usa:
  - `docs/estudos/`;
  - `docs/handoff/2026-10-11_28_reempacotamento-e-coleta_conferencias.json` (este handoff, ainda sem commit);
  - `docs/integracao_ml_e_empacotamento.md`;
  - `docs/phase16_dashboard_3_visoes.md`.
- o PyInstaller avisou sobre os `pandas.tests` excluídos e o `numba` ausente, como nos builds anteriores.

## Parte D: aba "Coleta de dados"

**Rotas** (`backend/routers/coleta.py`). Só leem. A única escrita é a configuração e a conferência de cada sessão.

| rota | o quê |
|---|---|
| `GET /api/coleta/requisitos` | o registro da Parte B |
| `GET /api/coleta/antes` | versão e commit do app, pasta e espaço livre, carro e pista detectados com aviso, estado do coach, configuração, geometria da conferência |
| `GET /api/coleta/ao-vivo` | janela de 5 s do que está sendo gravado: estado, taxa e último valor de cada item, indicador de IA |
| `GET`/`PUT /api/coleta/configuracao` | repositório e referência do coach |
| `GET /api/coleta/sessao-atual` | a conferência da sessão em gravação, volta a volta |
| `GET /api/coleta/verificacoes`, `GET`/`POST /api/coleta/verificacoes/{sessao}` | conferências gravadas, e conferir uma sessão sob pedido |
| `GET /api/coleta/m1/oficial` | a contagem oficial, lida do store v2 do repositório |

O estado do backend e do jogo continua vindo de `/api/runtime/status` e `/api/recording/status`, como no cartão "Estado da coleta" da página inicial. A `LiveSessionStrip` foi reaproveitada na aba e mostra agora a taxa real no lugar do "60 HZ" fixo.

**1. Antes de pilotar:**
- a versão e o commit do app;
- a pasta e o espaço livre, em amarelo abaixo de 5 GB e em vermelho abaixo de 2 GB;
- o backend, o Assetto Corsa, o carro e a pista, com aviso se não forem os esperados;
- o coach: a referência, se o modelo foi achado, se o `geometry_id` bate, a data e as voltas suas;
- a escolha da referência e do repositório;
- a contagem oficial ("n de 5").

**2. Durante:**
- **uma tabela por grupo,** com estado, Hz e último valor. Os estados:
  - **ausente:** nenhum quadro com valor;
  - **taxa baixa:** abaixo de 40 Hz, o piso das voltas que ensinam o coach;
  - **parado:** valor constante com o carro acima de 30 km/h; na embreagem, só o 0 constante, o defeito antigo;
  - **fora da faixa:** mais de 5% dos valores.
- **o indicador de IA em destaque:** "Você no volante", "IA no volante" ou "Indicador de IA ausente".
- **o monitor só olha o que o gravador está gravando,** e só faz conta quando a aba pergunta.

**3. Depois:**
- **cada volta** passa pelas mesmas funções do store v2: o corte de `iter_laps`, `clean_lap`, `align_lap`, `evaluate_lap`, `resample_lap(line_clock=True)` e o portão do box. A aba mostra o tempo em M:SS,mmm, se passa e o motivo, e o preenchimento de cada grupo;
- **a prévia da sessão**, pela regra registrada na seção 6 de `docs/modelo_fisico_m0.md`:
  - humana é a sessão com `lap_origin` igual a `humano` em todas as voltas;
  - os três canais precisam estar em pelo menos 95% dos pontos da grade das voltas válidas, fora do box;
- **a conferência é incremental durante a gravação:** a cada 5 s, o backend lê o que o arquivo cresceu e confere a volta que fechou. Em 04/10 isso custou 0,14 s por volta;
- **onde fica:** `<pasta de dados>\data\verificacoes\<sessao>.json`. Se o app fechar no meio da sessão, a conferência é concluída na próxima abertura.

**Nenhum leitor do ML confunde `data/verificacoes` com uma sessão:**
- o ML lista só subpastas de `data/recordings` com `player.jsonl` (`ml.data.recordings.list_sessions`);
- o gravador e o repositório de sessões usam `data/recordings`;
- a análise assistida lê `data/recordings` das duas raízes;
- o teste `test_ml_readers_do_not_see_the_checks_as_sessions` confere isso;
- `data/verificacoes/` e `data/configuracao/` entraram no `.gitignore` (no app de desenvolvimento, a pasta de dados é o repositório).

**Contagem oficial** (`core/coleta/oficial.py`): conta a sessão em que **todas** as voltas do store têm `origem` igual a `humano` e os três canais estão em pelo menos 95% dos pontos da grade dessas voltas. Lê só as quatro colunas necessárias do `laps_grid_v2.parquet` e o meta. Hoje dá **0 de 5**: 7 sessões têm voltas suas, e nenhuma tem os canais.

## Parte E: testes e conferência sem o jogo

### E.1 Testes sintéticos

`backend/tests/test_coleta.py` (38 casos) e `test_coleta_requisitos.py` (12), mais `frontend/src/utils/coleta.test.ts` (7):

- **o registro** contra o store v2 e a regra da M1 (Parte B);
- **o estado de cada canal:**
  - ok;
  - ausente;
  - parado: a guinada constante e a embreagem em 0 com o carro andando; a distribuição dos freios constante não conta, e o carro parado também não;
  - fora da faixa: uma roda;
  - taxa baixa: 20 Hz;
  - só o que é gravado entra, e a janela esquece o que é velho;
- **o veredito da volta é o dos portões:** fora de pista e volta curta;
- **o corte em voltas é o de `iter_laps`:** com o arquivo lido inteiro, em blocos de 40 KB e com o arquivo crescendo;
- **o veredito da sessão:**
  - humana e com os canais: "Conta para a M1.";
  - com uma volta da IA: não conta, "há volta com a IA no volante (#0001)";
  - sem a guinada: "Não conta para a M1: falta a guinada.";
  - sem a guinada, sem as velocidades e sem o indicador, como as gravações antigas: as duas faltas;
- **a configuração:** padrão, gravação, validação e a precedência de `AT_COACH_REFERENCE`;
- **o coach lendo do repositório,** sem copiar nada e sem mudar o repositório; calado com o coach desligado ou sem repositório, e com o motivo;
- **a identidade do app** no `metadata.json`, empacotado e do código-fonte;
- **o inventário e o store v2** com o `metadata.json` novo;
- **a cópia do portão do box** contra o detector, em 40 grades aleatórias;
- **a contagem oficial** num store sintético;
- **a formatação** M:SS,mmm e com vírgula, no front.

### E.2 Conferência nas gravações reais (só leitura)

Comando, de `backend/` (35,6 s e 12,1 s):

```bash
../.venv/Scripts/python.exe tools/conferir_sessao.py --sessao "%APPDATA%\Automobilista Telemetria\data\recordings\2026-10-10_09-57-09_vhe_interlagos" --sessao ../data/recordings/2026-10-04_03-21-52_vhe_interlagos --saida ../docs/handoff/2026-10-11_28_reempacotamento-e-coleta_conferencias.json
```

- **Leitura só:** o script para se a pasta da sessão mudar durante a conferência, e nenhuma mudou. Geometria `0ed16f0dd2225990`.
- **O resultado bate com o store v2:** nas duas sessões, as voltas que a conferência deixa entrar são exatamente as que o store v2 tem daquela sessão (12 e 4), e o tempo de cada uma é o mesmo (maior diferença: 0,0 s).

**`2026-10-10_09-57-09` (app instalado, 534 MB, 142.067 linhas):**

> **Não conta para a M1: faltam a guinada e as velocidades no referencial do carro; o indicador de IA não foi gravado.**

O esperado era "faltam a guinada e as velocidades". A segunda falta também é verdade: o app antigo não grava o indicador, e por isso o store rotula essa sessão por anotação (`origem_fonte` = `anotacao_sessao`). O `carModel` também não foi gravado.

| volta | jogo | amostras | quem | tempo | portões | base | origem | limites | M1 | contexto |
|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| #0000 | 1 | 7.118 | sem indicador | (2:02,079) | não passa: faltam 225,4 m de pista; carro parado em 17,7% | 100% | 0% | 100% | 0% | 100% |
| #0001 | 1 | 7.952 | sem indicador | (2:21,702) | não passa: carro parado em 6,5% | 100% | 0% | 100% | 0% | 100% |
| #0002 | 3 | 5.422 | sem indicador | 1:34,411 | passa | 100% | 0% | 100% | 0% | 100% |
| #0003 | 4 | 6.848 | sem indicador | 1:57,378 | passa | 100% | 0% | 100% | 0% | 100% |
| #0004 | 5 | 5.404 | sem indicador | 1:32,580 | passa | 100% | 0% | 100% | 0% | 100% |
| #0005 | 6 | 5.277 | sem indicador | 1:30,709 | passa | 100% | 0% | 100% | 0% | 100% |
| #0006 | 7 | 6.492 | sem indicador | (1:50,721) | não passa: carro parado em 6,0%; fora de pista em 10,8% | 100% | 0% | 100% | 0% | 100% |
| #0007 | 8 | 5.278 | sem indicador | 1:30,804 | passa | 100% | 0% | 100% | 0% | 100% |
| #0008 | 9 | 6.422 | sem indicador | (1:50,331) | não passa: carro parado em 14,6%; fora de pista em 20,5% | 100% | 0% | 100% | 0% | 100% |
| #0009 | 10 | 5.392 | sem indicador | 1:32,271 | passa | 100% | 0% | 100% | 0% | 100% |
| #0010 | 11 | 7.801 | sem indicador | (2:14,082) | não passa: carro parado em 20,5% | 100% | 0% | 100% | 0% | 100% |
| #0011 | 12 | 23.618 | sem indicador | (6:45,342) | não passa: volta longa demais (405,3 s); carro parado em 45,1%; fora de pista em 25,7% | 100% | 0% | 100% | 0% | 100% |
| #0012 | 13 | 5.335 | sem indicador | 1:32,651 | passa | 100% | 0% | 100% | 0% | 100% |
| #0013 | 14 | 5.337 | sem indicador | 1:31,540 | passa | 100% | 0% | 100% | 0% | 100% |
| #0014 | 14 | 5.585 | sem indicador | 1:36,231 | passa | 100% | 0% | 100% | 0% | 100% |
| #0015 | 16 | 5.365 | sem indicador | 1:32,206 | passa | 100% | 0% | 100% | 0% | 100% |
| #0016 | 16 | 7.644 | sem indicador | (2:11,586) | não passa: carro parado em 15,2%; fora de pista em 6,3% | 100% | 0% | 100% | 0% | 100% |
| #0017 | 18 | 5.271 | sem indicador | 1:30,313 | passa | 100% | 0% | 100% | 0% | 100% |
| #0018 | 19 | 5.265 | sem indicador | 1:30,508 | passa | 100% | 0% | 100% | 0% | 100% |
| #0019 | 19 | 7.686 | sem indicador | (2:11,742) | não passa: carro parado em 11,9%; fora de pista em 9,0% | 100% | 0% | 100% | 0% | 100% |
| #0020 | 21 | 1.555 | sem indicador | (0:26,544) | não passa: volta curta demais (26,5 s); faltam 4105,9 m de pista; carro parado em 21,1% | 100% | 0% | 100% | 0% | 100% |

**`2026-10-04_03-21-52` (repositório, 183 MB, 48.896 linhas):**

> **Não conta para a M1: faltam a guinada e as velocidades no referencial do carro.**

É o esperado. As voltas são suas pelo indicador (`origem_fonte` = `indicador` no store), e o `carModel` foi gravado.

| volta | jogo | amostras | quem | tempo | portões | base | origem | limites | M1 | contexto |
|---|---:|---:|---|---|---|---:|---:|---:|---:|---:|
| #0000 | 6 | 6.099 | você | (1:44,697) | não passa: faltam 224,6 m de pista; carro parado em 3,8% | 100% | 100% | 100% | 0% | 100% |
| #0001 | 7 | 5.563 | você | 1:35,239 | passa | 100% | 100% | 100% | 0% | 100% |
| #0002 | 8 | 5.315 | você | 1:31,742 | passa | 100% | 100% | 100% | 0% | 100% |
| #0003 | 8 | 6.246 | você | (1:47,157) | não passa: carro parado em 4,5% | 100% | 100% | 100% | 0% | 100% |
| #0004 | 10 | 5.411 | você | 1:32,675 | passa | 100% | 100% | 100% | 0% | 100% |
| #0005 | 10 | 5.432 | você | 1:33,458 | passa | 100% | 100% | 100% | 0% | 100% |
| #0006 | 12 | 5.423 | você | (1:33,000) | não passa: faltam 6,1 m de pista (limite 6 m) | 100% | 100% | 100% | 0% | 100% |
| #0007 | 12 | 9.407 | você | (2:41,667) | não passa: faltam 4107,7 m de pista; carro parado em 63,6% | 100% | 100% | 100% | 0% | 100% |

**Como ler as tabelas:**
- **tempo:** o relógio da grade, igual ao `lap_time_s` do store v2. Entre parênteses, a duração das voltas que não passam;
- **grupos:** o preenchimento é o do pior item do grupo nas amostras da volta. No M1, o pior é a guinada, com 0%;
- **preenchimento na grade das voltas válidas,** nas duas sessões: `yaw_rate`, `velocity_long`, `velocity_lat` e `brake_temp_*` com 0%.

### E.3 Teste do pacote sem instalar

**Como foi isolado:**
- o app foi aberto de `desktop\dist\win-unpacked\Automobilista Telemetria.exe`, com o app instalado fechado e a porta 8000 livre;
- `AT_DESKTOP_USER_DATA_DIR` apontou a pasta de usuário do Electron para `tmp\teste-pacote-28\userData`, no repositório. Os logs, o perfil do Chromium, a configuração e a raiz de dados do backend foram para lá;
- a janela foi conduzida pela porta de depuração do Chromium (`--remote-debugging-port=9229`): abrir a aba, escolher a conferência, tirar as capturas e fechar pela própria janela.

**Conferido antes e depois:**

| o quê | resultado |
|---|---|
| `%APPDATA%\Automobilista Telemetria` | **igual:** 610 entradas, nenhuma nova, sumida ou mudada (tamanho e data de cada arquivo) |
| `%TEMP%\_MEI*` | **nenhuma pasta nova** (as 12 que existiam continuaram 12) |
| processos do backend | **um só** (o `--onefile` criava dois), executado de `resources\backend\automobilista-backend\` e encerrado junto com o app |
| arquivos do repositório | só lidos: o modelo, a geometria, o cache da pista, o store v2 e a gravação de 04/10, com as mesmas datas de antes |

**`/api/health`:** `{"service": "automobilista-telemetria-backend", "version": "coleta-modelos"}`.

**`/api/coleta/antes`** (completo em `_pacote_rotas.json`):
- **app:** `0.3.0-coleta-modelos`, commit `e0f64ec`, empacotado, fonte `build-info`;
- **coach:** **ligado**, `volta_ia`, repositório `C:\Users\Dokas\Desktop\f1-telemetry-analyzer` com fonte `AT_REPO_PATH` (o repositório carimbado no build);
  - modelo achado: `data\reference_models\vhe_interlagos.json`, de 10/10, com 43 voltas suas;
  - geometria achada, com o `geometry_id` `0ed16f0dd2225990` batendo com o do modelo;
- **conferência:** geometria do repositório, a mesma `0ed16f0dd2225990`.

**A conferência rodando dentro do pacote:**
- o `POST /api/coleta/verificacoes/2026-10-04_03-21-52_vhe_interlagos` levou 14 s;
- o resultado é **igual ao do script da E.2** em todas as voltas (identidade, amostras, origem, portões, tempo, duração, motivos e preenchimento) e no veredito;
- isso mostra o pipeline do ML funcionando no backend congelado.

**Contagem oficial pelo pacote:** "0 de 5", lida do store v2 de 10/10.

**Referência e repositório pela aba, no pacote:**
- `minha_melhor`: ligado;
- `desligado`: calado, "o coach está desligado na configuração";
- `volta_ia`: ligado;
- repositório errado: calado, "o modelo não foi encontrado em …\tmp\data\reference_models\vhe_interlagos.json";
- vazio: volta ao padrão e o coach liga de novo.

**Tempo de abertura**, do clique até o `/api/health` responder:

| abertura | tempo | onde foi o tempo |
|---|---|---|
| 1ª, pasta de dados vazia | 46,6 s | o executável subiu o Python em 1,3 s; a montagem do cache da pista a partir dos arquivos do jogo levou 37 s |
| 2ª | 38,9 s | o mesmo cache foi montado de novo: 35,5 s (achado 1) |

Sem o achado 1, o backend estaria pronto em cerca de 4 s: 2,7 s até a montagem do cache começar e 1,3 s depois dela. O `--onefile` antigo somava a extração de cerca de 0,4 GB em `%TEMP%` a cada abertura.

**Capturas da janela real do app** (não há modo de reprodução de uma gravação real; o modo "replay" do backend é o CSV de exemplo):
- `_captura_1_antes.png`: Antes de pilotar;
- `_captura_2_durante.png`: Durante, sem gravação em andamento;
- `_captura_3_conferencia_10-10.png`: o resultado da E.2 para 10/10. A conferência da sessão de 10/10, que está na pasta real do app instalado, foi copiada para a pasta isolada;
- `_captura_4_conferencia_04-10.png`: a conferência de 04/10 feita pelo próprio pacote.

### E.4 Suítes

| suíte | resultado |
|---|---|
| `backend/tests` (em `develop`, `e0f64ece`) | **735 passaram**, 18 avisos, 7 min 52 s. Antes eram 685; os 50 novos são da coleta. |
| front: `vitest run` | **145 passaram** (8 arquivos; 7 novos) |
| front: `tsc --noEmit` | sem erros |

A saída completa está em `_testes.txt`.

## Achados fora do pedido

1. **O cache da pista é refeito a cada abertura do backend** (cerca de 36 s):
   - **o que acontece:** `core/geometry/track_geometry_provider.py` considera o cache "anterior ao mapa desenhado" quando `boundsLeft[0].elevation` é vazio (`_cache_predates_marking_classification`). O cache recém-gravado sai com esse campo vazio, então a reconstrução nunca para;
   - **é anterior a este pedido.** Vale para o app instalado, para o de desenvolvimento e para o pacote novo;
   - **o efeito em 11/10:** o backend de desenvolvimento que abri para ver a aba (`launch.json`, configuração "backend") **regravou `data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_geometry.json` do repositório** às 13:11:50. Parei o backend e conferi o `geometry_id`: continua `0ed16f0dd2225990`. A chave do cache incremental do `atualizar_coach` usa o `geometry_id`, então nada será relido por isso. Não tenho a cópia anterior do arquivo para comparar byte a byte, e o `conferir_corredor` do pedido 27 lê a pintura desse arquivo. Depois disso, rodei os testes de desenvolvimento com a pasta de dados isolada;
   - **a proposta, decisão sua:** um pedido próprio para corrigir a checagem ou gravar a elevação. Mexe no arquivo de que o ML tira a geometria, então não fiz aqui.
2. **2,8 GB de pastas `_MEI*` no `%TEMP%`,** de 08/10 a 13/10:
   - **de onde vêm:** são extrações do backend `--onefile` antigo que não foram apagadas, porque o Electron encerra o backend com `taskkill /F`;
   - **o tamanho:** sete delas têm cerca de 0,4 GB cada;
   - **o efeito:** isso explica parte da falta de espaço de 08/10;
   - **o que fazer:** com o `--onedir`, isso para de acontecer. As pastas podem ser apagadas com o app antigo fechado. Não apaguei: a decisão é sua.
3. **Sessões novas no app antigo:**
   - `2026-10-11_14-16-34` e `2026-10-11_14-19-52`, de 11/10;
   - `2026-10-13_19-24-10`, de 13/10;
   - `2026-10-11_13-56-20`, de 11/10, com 1 amostra.

   Foram gravadas pelo `0.1.7`: sem o indicador de IA, sem o `carModel`, sem os canais do pedido 18 e sem `endedAt`. Não contam para a M1, e o store só as rotula por anotação. Depois de instalar, a aba confere essas sessões pelo botão "Conferir".
4. **O `metadata.json` não ganha `endedAt`** quando o app fecha: o backend é encerrado à força e o gravador não finaliza. É anterior a este pedido. Por isso, a conferência de uma sessão interrompida é concluída na próxima abertura.

## Parte F: instalação e sessão de teste (com você)

**Parei aqui.** O instalador:

- **caminho:** `C:\Users\Dokas\Desktop\f1-telemetry-analyzer\desktop\dist\Automobilista-Telemetria-Setup-0.3.0-coleta-modelos.exe`
- **versão:** `0.3.0-coleta-modelos`, de `develop` `e0f64ec`
- **tamanho:** 228.873.657 bytes (218 MB)
- **sha256:** `7b27fe71ffe9be00da58180140e910a171a63b00d0e9f37f1b61de9e2775c0b6`

**Passos para você:**

1. Feche o jogo e o app instalado, inclusive na bandeja do Windows.
2. **Recomendado:** copie `%APPDATA%\Automobilista Telemetria\data\recordings` para outro disco antes de instalar.
3. Rode o instalador novo por cima do atual, na mesma pasta. A fase 12.6 mostrou que a instalação preserva `%APPDATA%`.
4. Abra o app e vá à aba **"Coleta de dados"** (no menu, entre "Pista" e "Análise"):
   - **a primeira abertura** pode levar uns 40 s, por causa do achado 1;
   - **o repositório do modelo** deve aparecer como `C:\Users\Dokas\Desktop\f1-telemetry-analyzer`, com origem "repositório em que o app foi construído", e o coach como **ligado**;
   - **escolha a referência:** volta da IA, sua melhor volta ou coach desligado.
5. Abra o Assetto Corsa em Interlagos com o `rss_formula_rss_3_v6_2026` e faça de 3 a 5 voltas sem a IA, olhando a aba antes e depois:
   - **durante,** o destaque deve dizer **"Você no volante"**, e o grupo "Modelo do carro (M1)" deve ficar **ok**;
   - **depois de cada volta,** a volta aparece em "Depois de cada volta e no fim da sessão".
6. Feche o app e me avise: **"instalei e gravei a sessão de teste"**.

**Opcional:** com o app antigo fechado, você pode apagar as pastas `C:\Users\Dokas\AppData\Local\Temp\_MEI*` (achado 2).

## O que falta e o que precisa de decisão

**Falta, depois do seu aviso (Parte G):**
1. Rodar o `atualizar_coach` incremental com o app fechado.
2. Conferir no store v2 a sessão nova:
   - `yaw_rate`, `velocity_long`, `velocity_lat` e a temperatura dos freios em pelo menos 95% dos pontos das voltas válidas;
   - o `carModel`, o indicador de IA, a versão e o commit no `metadata.json`;
   - `origem_fonte` igual a `indicador`.
3. Conferir a contagem oficial, que deve ir a 1 de 5.
4. Comparar o veredito da aba com o do store.
5. Tirar do `docs/backlog.md` a linha do app instalado, se a Parte G passar.
6. Completar este relatório.

**Decisões suas:**
- **A regra da contagem oficial que escrevi:** todas as voltas da sessão no store como suas, e os três canais em pelo menos 95% da grade dessas voltas. A seção 6 não dizia como tratar uma sessão com voltas suas e da IA; aqui, ela não conta. Confirme ou ajuste.
- **O achado 1:** o cache da pista é refeito a cada abertura. Proponho um pedido próprio.
- **O achado 2:** as pastas `_MEI*` do `%TEMP%`.

`docs/handoff/2026-10-11_28_reempacotamento-e-coleta_relatorio.md`

## Pergunta no chat (14/10): as sessões que gravei contaram para o treinamento?

Conferido em 14/10, só lendo (`tools/conferir_sessao.py` nas três sessões novas; store v2 e modelo do coach do repositório).

**Modelo do coach e store v2 (relatório de evolução):**
- **Até 10/10, sim.** O store v2 (refeito em 10/10 17:42) e o modelo do coach (treinado em 10/10 17:38, 43 voltas suas) têm as sessões de 04/10 (app de desenvolvimento), 04/10 23:51, 05/10, 08/10 e 10/10. As do app instalado entraram pela anotação em `docs/experimentos/anotacoes_de_sessao.csv`.
- **11/10 e 13/10, ainda não.** O `atualizar_coach` não rodou depois de 10/10. E, gravadas pelo app antigo, essas sessões não têm o indicador de IA: sem uma linha de anotação confirmando que todas as voltas foram suas, as voltas saem `desconhecida` e não entram no modelo do coach.

| sessão | linhas | voltas válidas pelos portões | melhor volta |
|---|---:|---:|---|
| `2026-10-11_14-16-34` | 1.134 | 0 | — |
| `2026-10-11_14-19-52` | 130.442 | 16 | 1:27,594 |
| `2026-10-13_19-24-10` | 95.087 | 9 | 1:29,768 |

A volta de 1:27,594 é mais rápida que a referência `minha_melhor` atual (1:29,389).

**Modelo do carro (M1):** nenhuma sessão gravada até agora conta (0 de 5). Todas foram gravadas sem a guinada e as velocidades no referencial do carro. Só as sessões do app novo (0.3.0) vão ter esses canais.

**Anotação feita em 14/10, a seu pedido no chat** ("sim, todas as voltas foram minhas, pode anotar"):
- **O que entrou:** três linhas em `docs/experimentos/anotacoes_de_sessao.csv`, todas como `humano`, `rss_formula_rss_3_v6_2026`:
  - `2026-10-11_14-16-34`;
  - `2026-10-11_14-19-52`;
  - `2026-10-13_19-24-10`.
- **O carro foi anotado pelo padrão das anotações anteriores e pelos tempos de volta.** Você confirmou o piloto; confirme também o carro.
- **`2026-10-11_13-56-20` ficou de fora:** tem uma amostra só e não entra no inventário. Anotada, ela faria o `atualizar_coach` parar.
- **Nada rodou ainda:** as voltas entram no coach e no store v2 no `atualizar_coach` da Parte G. A volta de 1:27,594 deve virar a referência `minha_melhor`.

## Pasta de versões e menu Iniciar (pedido no chat de 14/10)

Você disse que o app não aparecia no menu Iniciar e pediu um lugar com todas as versões.

**O que existe hoje no Windows:**
- A instalação é a `0.1.7-phase-16`, registrada para todos os usuários (registro `HKLM`), na pasta `C:\Users\Dokas\AppData\Local\Programs\Automobilista Telemetria`.
- Há dois atalhos "Automobilista Telemetria", de 02/09, apontando para ela:
  - no menu Iniciar de todos os usuários: `C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Automobilista Telemetria.lnk`;
  - na área de trabalho pública: `C:\Users\Public\Desktop\Automobilista Telemetria.lnk`.
- A `0.3.0` ainda não foi instalada. O instalador dela recria os atalhos.

**A pasta nova:** `versoes\`, na raiz do repositório:
- **uma subpasta por versão,** com o instalador, o `build-info.json` e o `sha256.txt`;
- **os instaladores antigos** foram movidos de `desktop\dist\`: 10 instaladores de 9 versões. As versões anteriores à `0.1.7` não têm carimbo de build; a data delas é a do arquivo;
- **a `0.3.0`** foi copiada para `versoes\0.3.0-coleta-modelos\`. Ela continua também em `desktop\dist\`, a saída do build;
- **`versoes\LEIA-ME.md`,** gerado pelo script e versionado, diz:
  - qual é a mais atual, a de build mais recente (a `0.2.0-assetto-udp` é de 14/06, anterior à `0.1.7`);
  - qual está instalada, pelo registro do Windows;
  - como instalar a mais atual: por cima da atual, escolhendo "todos os usuários" e mantendo a pasta, como na instalação de hoje;
  - como abrir o app e conferir a versão.
- **o build guarda o instalador novo sozinho:** `desktop/scripts/publish-version.js` roda no fim do `npm run dist:win` (`npm run publicar`). `npm run versoes` só refaz o LEIA-ME.

**Na Parte F, use o instalador** `versoes\0.3.0-coleta-modelos\Automobilista-Telemetria-Setup-0.3.0-coleta-modelos.exe`. É o mesmo arquivo de `desktop\dist\`, sha256 `7b27fe71…`.

## Parte G: conferência da sessão de teste (16/10, junto com o pedido 32)

O relatório completo está em `docs/handoff/2026-10-15_32_sessoes-11-e-13-10-e-botao-do-coach_relatorio.md`, na seção "Parte G do pedido 28".

- **A sessão:** `2026-10-15_23-24-50_vhe_interlagos`, com 20 voltas, todas `humano` pelo indicador. Ela saiu do **app do repositório** (`appPackaged: false`), e não do pacote instalado: foi gravada pela janela de validação do pedido 30. Por isso entrou por uma cópia em `data/recordings`.
- **No store v2:** guinada, velocidades locais e os quatro freios em 100% dos pontos das 11 voltas. O metadado tem `carModel`, indicador, versão e commit, e a origem é o `indicador`, sem anotação.
- **O veredito da aba e o do store batem,** e a contagem oficial da M1 foi para **1 de 5**.
- **Falta:** uma sessão curta gravada pelo pacote instalado, para confirmar o mesmo por ele.
