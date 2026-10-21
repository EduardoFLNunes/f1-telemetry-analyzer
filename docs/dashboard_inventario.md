# Inventário da dashboard e base do redesenho

- **Data:** 08/10/2026. **Autor:** Claude (Cowork), a pedido do Eduardo.
- **Fonte:** leitura do código em `develop` (`frontend/src`, `desktop/`, `backend/routers`, `backend/core/live/driving_coach.py`, `backend/core/assisted_analysis/service.py`, `backend/tools/painel_evolucao.html`). O app não foi executado. As linhas citadas são da leitura de 08/10 e podem mudar.
- **Para que serve:** registrar o que existe hoje, o que contradiz as decisões do projeto e o destino de cada parte no redesenho. Os pedidos de implementação partem daqui.

## 1. O que existe hoje

### 1.1 Páginas

O app tem 4 páginas, sem roteador (`App.tsx:20,46-49`). Ao recarregar, ele volta sempre para Início.

| Página (menu) | O que mostra |
|---|---|
| **Início** | estado da coleta (4 passos), sessões gravadas e atalhos (`HomePage.tsx`) |
| **Pista** | cabeçalho; faixa da sessão ao vivo; 3 colunas (`Dashboard.tsx:89-167`): <br>• à esquerda: comparação por setor, "Lap Timing" e "Vehicle State"; <br>• no centro: mapa e "LAP COMPARISON"; <br>• à direita: abas "Compare", "Linha", "Engineer" e "Debrief", mais "AI Coaching"; <br>• embaixo: barra de replay |
| **Análise** | abas "Voltas", "Analise assistida", "Tracados" e "Elevacao" (`AnalysisPage.tsx:10-15`) |
| **Sistema** | runtime, Assetto, versão, qualidade dos dados e física do carro (`DiagnosticsPage.tsx`) |

**Fora do app:** o painel de evolução (`data/ml/evolucao/painel.html`) é um HTML estático, gerado pelo `atualizar_coach` e aberto no navegador.

**Electron:** uma janela de 1280×820, sem modo de sobreposição (`desktop/main.js:900-936`).

### 1.2 Como os dados chegam

- **WebSocket `/ws`:** telemetria a 30 Hz, física a 2 Hz, oponentes a 10 Hz e eventos (`core/websocket_server.py:194-262`). O cliente só aproveita `coaching_event`, as métricas e a fala do engenheiro. Os outros eventos são descartados (`useTelemetryWS.ts:169-176`).
- **HTTP:** cerca de 20 rotas são usadas pelo front, de mais de 50 que o backend expõe. As principais:
  - `/api/track/geometry`;
  - `/api/live/racing-line`;
  - `/api/sessions` e `/api/sessions/{id}/laps`;
  - `/api/laps/{id}/replay`;
  - `/api/analysis/assisted/lap/{id}`;
  - `/api/analysis/coach/lap/{id}`;
  - `/api/runtime/status`.
- **Replay:** carrega uma volta gravada e uma de referência, e libera os eventos do coach pelo tempo de volta (`useTelemetryStore.ts:641-685,1294-1351`).

## 2. Problemas encontrados

### A. Contradições com as decisões do projeto

1. **O mapa, o painel e o replay usam a projeção do runtime, e não a geometria oficial** (ADR 0002 e 0013):
   - a pista vem de `/api/track/geometry`, sem `geometry_id` (`routers/track.py:26-35`);
   - o `s` e o `p` vêm da linha central crua (`runtime_state.py:26-81`);
   - o mapa divide a pista em 50 microssetores por fração da spline (`TrackRenderer.tsx:1014`), e o coach em 60 de mesma distância.
2. **"Assisted Analysis" mostra ganho estimado:** `totalEstimatedGainS` é a soma dos ganhos por curva (`service.py:220,238-242`). O ADR 0012 manda mostrar diferença medida contra uma volta real.
3. **O coach ainda tem uma mensagem de "ideal":** "Volta fechada. X s acima do seu ideal…" (`driving_coach.py:732-746`). Ela só aparece no modo antigo, sem referência. No modo padrão, o coach usa `volta_ia` e `minha_melhor` e limita as frases a 3 por volta (`driving_coach.py:90,601-604`).
4. **O tempo de volta é calculado de 4 jeitos:**
   - diferença no store;
   - maior `lap_time` amostrado;
   - timestamp máximo menos mínimo (`racing_line_analysis.py:180-185`);
   - `lap_time_s` do store v2.

   O oficial é o `lap_time_s` do store v2, com o relógio zerado na linha.
5. **"Setor" quer dizer três coisas:**
   - "SET 1–3" são terços do progresso (`sectorTimes.ts`);
   - "SETOR N" no coach é o microssetor N de 60 (`CoachingFeed.tsx`);
   - os setores oficiais do jogo não aparecem.
6. **Os deltas por setor de "Compare" e "Linha" são estimados** por distância ÷ velocidade (`comparisonAnalysis.ts:200-203`; `racing_line_analysis.py:520-522`). Eles divergem do relógio, que é usado em "Lap Timing" e na comparação por setor.

### B. Dados fixos ou falsos na tela

- Três "AI RECOMMENDATIONS" fixas no "Session Debrief" (`AIDebriefPanel.tsx:110-114`).
- "SPATIAL" e "AI_CORE" sempre acesos, e "BUILD v13.0" fixo (`Header.tsx:51,102-103`).
- "GRAVAÇÃO 60 HZ" fixo, quando a taxa real vem em `sampleRateHz` (`LiveSessionStrip.tsx:98`).
- Fonte "F1-25 UDP" e "IRACING SDK", com Start e Stop chamando rotas que não existem (`ReplayControls.tsx:30-41,182-184`).
- "Neural-linked coaching // Priority enabled" (`AIEngineerPanel.tsx:88`).

### C. Depuração visível ao piloto

- **No mapa:**
  - "PERF" (FPS, heap, contadores de render);
  - os modos RAW, PTS, SEGS, SMTH e SPEED;
  - a legenda "VIS/RAW/MICRO";
  - "N m | N pts | source";
  - "World X/Y/Z" dos oponentes (`TrackRenderer.tsx:1610-1817`; `RacingLineOverlay.tsx:17-26,676`; `OverlayRenderer.tsx:715-748`).
- **Nos painéis:**
  - "LAP DBG" (`TelemetryTraces.tsx:470-503`);
  - "P n / REF n" (`LiveComparisonPanel.tsx:292-296`);
  - `JSON.stringify(evidence)` (`CoachingFeed.tsx:94`);
  - "Phase 13" (`SessionLapsPanel.tsx:510,605`).

### D. Informação repetida

- **Tempo de volta em 5 lugares:** cabeçalho, "Lap Timing", barra de replay, canto do mapa e "LAP COMPARISON".
- **Delta em 4 lugares.** Na barra de replay, "Delta" e "Lap Delta" mostram o mesmo valor (`useTelemetryStore.ts:887`).
- **Setores 1–3 em 3 painéis,** com 3 números diferentes. As tabelas "PERDAS/GANHOS" de "Compare" e "Linha" são quase iguais.
- **A fala do engenheiro sai em dois painéis ao mesmo tempo:** "AI Race Engineer" e "AI Coaching".

### E. Navegação

- O replay é iniciado na Análise, mas só toca na Pista. O app não troca de página sozinho (`SessionLapsPanel.tsx:313-370`).
- As abas ocultas da Pista continuam montadas e só somem por opacidade (`Dashboard.tsx:139-156`).

### F. Idioma e identidade

- **Português e inglês misturados, em geral sem acento.** Exemplos:
  - "Vehicle State" ao lado de "Comparacao por setor";
  - a aba "Analise assistida" abre o painel "Assisted Analysis".
- **Quatro nomes de produto:**
  - "Motorsport Intelligence Workstation";
  - "AT TELEM";
  - "Telemetria Assistida para Simulacao Automobilistica";
  - "Automobilista Telemetria".
- `<html lang="en">`.

### G. Desempenho

- **O mapa redesenha asfalto, pintura e zebras a cada quadro,** sem cache. O seletor do overlay faz o React renderizar a cada frame (`OverlayRenderer.tsx:382-536`; `TrackRenderer.tsx:841`).
- **A rota da linha de corrida trava o servidor por 1 a 1,8 s a cada 6 s.** Ela é `async` com chamada síncrona, como medido em `docs/mapa_dashboard_e_coach.md:199-213` (`routers/live.py:178-188`).

### H. Código sem uso

- **Componentes:** `CognitiveDashboard`, `GGDiagram`, `SessionTimeline` e `StabilityPanel`.
- **Funções mortas no mapa** (`OverlayRenderer.tsx:62-332`; `CarRenderer.tsx:198`).
- **Rotas:** cerca de 30 sem nenhum uso (debug, legacy, upload, duplicatas da análise assistida).
- **Globais em `window`** usadas como canal de dados: `__latestFrame`, `__latestOpponents`, `__telemetryPerf`, `__replayMapDiagnostics`.

### A conferir na implementação

- **Espelhamento (resolvido em 10/10):** o mapa principal usa `(x, −z)` com `scale(s, s)` (`spatialTransform.ts:39,58`; `CameraController.tsx:111,118`) e desenha o circuito no sentido horário. O minimapa e o relevo usam `scale(s, −s)` (`OverlayRenderer.tsx:698`; `TrackElevationRibbon.tsx:244`) e desenham no anti-horário, que é o sentido de Interlagos. **O mapa principal está espelhado;** o minimapa e o relevo estão certos.
- **Canto inferior direito do mapa:** lê `latestFrame` mesmo durante o replay (`MapOverlay.tsx:84`).
- **Frames ao vivo durante o replay:** continuam alterando o store, porque `addFrame` não confere se o replay está ativo.

## 3. O que já funciona e fica

- **O painel de evolução** segue os ADRs 0012 e 0015:
  - diferença para a volta da IA, com intervalo de 90%;
  - perda por curva e por microssetor;
  - evolução entre sessões.

  Falta mostrar o bloco `tecnica`, que já está no JSON (`relatorio_evolucao.py:123`).
- **O replay** libera os eventos do coach pelo tempo de volta.
- **O coach** mostra a referência (`volta_ia` ou `minha_melhor`) em texto.
- **O desenho do mapa** em canvas a 60 fps, com o asfalto e as zebras do próprio jogo.
- **As telas de diagnóstico,** úteis para o desenvolvimento.

## 4. Premissas do redesenho

1. **Monitor único de 27":** durante a volta o jogo ocupa a tela, então a dashboard é para antes e depois de pilotar. A ajuda durante a volta vai para dentro do jogo, pelo app do Custom Shaders Patch, que depende do ADR 0020.
2. **Uma fonte para cada número:**
   - geometria oficial (`geometry_id`);
   - `lap_time_s` do store v2;
   - 60 microssetores;
   - 14 curvas, de C01 a C14;
   - referência `volta_ia` ou `minha_melhor`.
3. **Diferença medida, nunca ganho prometido** (ADR 0012). Toda perda aparece com o intervalo, quando ele existe.
4. **Depuração só na tela Sistema.**
5. **Português com acento,** nomes técnicos, um nome de produto e tempos em M:SS,mmm.

## 5. Estrutura proposta

**Decisões do Eduardo (09/10):**

- O nome do produto é o do TCC: "Sistema de Telemetria e Otimização de Trajetórias".
- A estrutura das 5 telas é testada primeiro, no protótipo navegável `frontend/mockups/prototipo_dashboard.html` (opções A e B, dados reais de 04 e 05/10, sem backend).

**Regra do redesenho (09/10):** reaproveitar o que já existe e não construir backend. As únicas partes novas são as que corrigem uma medida errada, e elas usam números que o relatório de evolução já calcula.

**Decisão do Eduardo (11/10):** a aba "Coleta de dados" entra já no app atual, junto com o reempacotamento do app instalado (pedido 28), e ocupa o lugar da tela "Antes de pilotar". É a única exceção à regra de não construir backend: conferir se a gravação tem o que os modelos precisam exige ler a gravação.

**Decisões do Eduardo (14/10, pedido 29):**

- O redesenho segue a **opção A** do protótipo.
- **Paleta inspirada nas transmissões da F1,** sem a identidade oficial: nada de logotipo, marca, fonte proprietária ou cor de equipe.
- **Visual de vidro (glassmorphism)** nos recipientes. Gráficos, tabelas e mapas ficam sobre superfície opaca, para os números não perderem contraste.
- **Hero** no topo da tela Sessões, com dado real e o estado do backend na abertura.
- **Tela Ao vivo** e **realidade aumentada dentro do jogo como o rádio do engenheiro.** A realidade aumentada é a segunda exceção à regra de não construir backend e depende do ADR 0020.
- O redesenho usa a skill `frontend-design` (`.claude/skills/frontend-design`).

| Tela | Para quê | O que é reaproveitado | O que é novo |
|---|---|---|---|
| **Sessões** (início) | <br>• o hero (14/10); <br>• a lista de sessões, com voltas, melhor, mediana e diferença para a IA; <br>• a tendência entre sessões e o critério do ADR 0015 | <br>• o cartão "Sessoes gravadas" da `HomePage`, com `/api/sessions`; <br>• o `resumo.json` da evolução | só a montagem da tela |
| **Volta** | análise de uma volta contra a referência, com mapa, diferença acumulada, traços, 14 curvas e replay | <br>• mapa: `TrackRenderer` (canvas, asfalto e zebras do jogo); <br>• traços: `AssistedLapTraces` e `TelemetryTraces`; <br>• replay e frases do coach: `SessionLapsPanel`, `ReplayControls`, `/api/laps/{id}/replay` e `/api/analysis/coach/lap/{id}`; <br>• diferença pelo relógio do jogo: o cálculo do store (`calculateLapMetrics`, `useTelemetryStore.ts:863-891`) | <br>• a camada dos 60 microssetores no mapa, desenhada no front, com as cores do relatório; <br>• o eixo dos traços em metros, e não em %; <br>• a tabela das 14 curvas, com os números de `sessao_*.json` (`por_volta`) |
| **Evolução** | perda por curva entre sessões, diferenças consistentes e técnica de pilotagem | o `painel_evolucao.html` e os JSONs que ele já lê | o bloco `tecnica`, que já está no JSON |
| **Coleta de dados** (era "Antes de pilotar"; pedido 28) | conferir antes, durante e depois da sessão se a gravação tem o que os modelos precisam | <br>• o cartão "Estado da coleta" da `HomePage`; <br>• a `LiveSessionStrip`; <br>• `/api/runtime/status` e `/api/recording/status` | <br>• a taxa real no lugar do "60 HZ" fixo; <br>• o estado de cada canal, pelo registro do que os modelos precisam; <br>• o veredito de cada volta e da sessão |
| **Ao vivo** (14/10) | acompanhar a sessão em andamento e o que o rádio disse ao piloto | <br>• `/api/coleta/ao-vivo`; <br>• `/api/live/coach`; <br>• a visão "Volta com fantasma" do protótipo, ao vivo | <br>• as mensagens de rádio em sequência; <br>• o rádio dentro do jogo (realidade aumentada, ADR 0020) |
| **Sistema** | tudo o que é de desenvolvimento | a `DiagnosticsPage`, como está | <br>• recebe o PERF e os modos de depuração do mapa; <br>• o guia visual (pedido 29) |

**Backend:** só um jeito de o front ler os JSONs que `atualizar_coach` já grava em `data/ml/evolucao/`. Pode ser uma rota que devolve o arquivo ou uma leitura pelo Electron. Nenhum cálculo novo no servidor.

**As três vistas em que a medida muda, e por quê:**

1. **Diferença por relógio do jogo e por distância.** Ela substitui "Compare" e "Linha", que estimam o tempo por distância ÷ velocidade.
2. **As 14 curvas com os números do relatório,** que somam exatamente a diferença da volta. Elas substituem a "Analise assistida" (ganho estimado, contra o ADR 0012) e os três significados de "setor".
3. **Os 60 microssetores por distância,** os mesmos do coach. Eles substituem os 50 por fração da spline.

**Uma tela para depois, sem pedido ainda:** "Traçados", comparando a linha da IA, a sua mediana e a referência da F1 2023–25 (pedido 24).

## 6. Destino de cada parte atual

| Hoje | Destino |
|---|---|
| Início | vira **Sessões** |
| Pista: mapa | vai para **Volta**, na geometria oficial; a depuração vai para **Sistema** |
| Pista: "LAP COMPARISON" | vai para **Volta**, por distância (m) e contra a referência escolhida |
| Pista: "Lap Timing", "Vehicle State" e faixa ao vivo | saem. Durante a volta, a ajuda vai para dentro do jogo; antes de pilotar, a checagem fica em **Coleta de dados** |
| Pista: comparação por setor, "Compare" e "Linha" | saem. Os 3 jeitos de medir setor dão lugar às 14 curvas e aos 60 microssetores, com tempo do relógio |
| Pista: "AI Race Engineer", "Session Debrief" e cabeçalho | saem (dados fixos e repetidos) |
| Pista: "AI Coaching" | as frases ficam no replay da **Volta**, marcadas no mapa |
| Barra de replay | vai para **Volta** |
| Análise: "Voltas" | vira o seletor de sessão e volta, em **Sessões** e **Volta** |
| Análise: "Analise assistida" | sai, porque mostra ganho estimado. O diagnóstico por curva útil já está no relatório de evolução |
| Análise: "Tracados" e "Elevacao" | entram em **Volta** (traços) e no mapa (relevo) |
| Sistema | fica e recebe a depuração |
| Painel de evolução (HTML) | entra no app como **Evolução**, com o bloco `tecnica` |
| Componentes e rotas sem uso | saem num pedido de limpeza |

## 7. Ordem sugerida dos pedidos

Atualizada em 14/10, com as decisões do pedido 29:

1. **Base e sistema visual (pedido 29):**
   - paleta, fontes, vidro, componentes e guia visual;
   - roteador, idioma, nome do produto e `lang="pt-BR"`;
   - retirada dos dados fixos;
   - depuração para Sistema;
   - espelhamento do mapa principal;
   - hero e a casca da tela Ao vivo;
   - a leitura do CSP para a realidade aumentada.
2. **Realidade aumentada:** o rádio no jogo e a tela Ao vivo completa, depois do ADR 0020.
3. **Tela Volta**, montada com as peças da tabela da seção 5. O único acréscimo fora do front é a leitura dos JSONs da evolução.
4. **Evolução** dentro do app, a partir do `painel_evolucao.html`, com o bloco `tecnica`.
5. **Sessões.** A Coleta de dados já entrou no pedido 28.
6. **Limpeza** de componentes, rotas e globais sem uso.
7. **Instalador** com o redesenho.

Cada pedido mantém o que já foi validado: o coach, o store v2 e o relatório de evolução não mudam de regra.

### O que o pedido 29 entregou (14/10)

Item 1 da lista acima. Detalhes em `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md`; o sistema visual está em `docs/sistema_visual.md`.

- **Paleta, fontes, vidro, componentes e guia visual:**
  - a paleta está em variáveis (`frontend/src/theme/tokens.css`), e o Tailwind aponta para elas;
  - as fontes são arquivos locais com a licença OFL: Barlow Condensed, Instrument Sans e IBM Plex Mono;
  - o vidro vale só nos recipientes e respeita `prefers-reduced-transparency`; há também o botão "Sem transparência";
  - os componentes base estão em `components/ui/base.tsx`;
  - o guia visual fica em Sistema › Guia visual;
  - todo texto passa no AA (4,5:1) sobre o vidro.
- **Roteador, idioma, nome do produto e `lang="pt-BR"`:**
  - **o roteador:** endereço por hash (`#/sessoes`, `#/volta`…), que sobrevive ao recarregar. O trilho lateral deu lugar a uma barra de vidro no topo, com as seis telas: Sessões, Ao vivo, Volta, Evolução, Coleta de dados e Sistema;
  - **o idioma:** `lang="pt-BR"` e tempos em M:SS,mmm, com vírgula, também nas telas antigas;
  - **o nome do produto:** "Sistema de Telemetria e Otimização de Trajetórias", no título da janela (`desktop/main.js`) e na página. Saíram "Motorsport Intelligence Workstation", "AT TELEM" e "Telemetria Assistida para Simulacao Automobilistica". O `productName` do instalador não mudou.
- **Retirada dos dados fixos (problema B):**
  - as três "AI RECOMMENDATIONS" fixas;
  - "SPATIAL" e "AI_CORE" sempre acesos;
  - "BUILD v13.0";
  - a escolha de fonte "F1-25 UDP" e "IRACING SDK", com o Start e o Stop que chamavam `/api/streaming/*`, rota que não existe;
  - "Neural-linked coaching // Priority enabled".

  O "GRAVAÇÃO 60 HZ" já mostrava a taxa real desde o pedido 28.
- **Depuração para Sistema (problema C):** fora da tela Sistema, o mapa não mostra mais:
  - o PERF;
  - os modos DIAG, RAW, PTS, SEGS, SMTH e SPEED;
  - a legenda "VIS/RAW/MICRO";
  - o "N m | N pts | fonte";
  - o "World X/Y/Z" dos oponentes.

  Também saíram:
  - o "LAP DBG" dos traços;
  - o "P n / REF n";
  - o JSON do `evidence`;
  - "Phase 13", que agora se chama "portões de qualidade".

  Tudo isso está em Sistema › Depuração.
- **Espelhamento do mapa principal:**
  - **o que mudou:** a câmera usa `scale(s, −s)` (`CameraController.tsx`, `SENTIDO_DO_EIXO_Y`), e o mapa gira no anti-horário, como o minimapa e o relevo;
  - **o que vem junto:** a projeção dos oponentes acompanha, e os textos desenhados no mapa ficam em pé;
  - **a conferência:** foi feita com uma volta real, antes e depois.
- **Hero e casca da tela Ao vivo:**
  - **o hero:** fica no topo de Sessões. Mostra o estado real do `/api/health` enquanto o backend sobe, os números de dado real e a sua melhor volta traçada sobre as camadas do cache. Para isso, a janela do Electron agora abre antes de o backend responder;
  - **a casca do Ao vivo:** a gravação e os canais vêm de `/api/coleta/ao-vivo`, e o rádio de `/api/live/coach`.
- **A leitura do CSP para a realidade aumentada:** está no relatório do pedido 29 (Parte A).
- **O que fica para os próximos pedidos:**
  - Volta e Evolução ainda mostram o conteúdo antigo (Pista e Análise) dentro da casca nova;
  - a lista de Sessões é a do gravador, com a conferência da Coleta.

  O pedido 30 (complemento, 14/10) passa as três telas para o protótipo A.

### O que o pedido 30 entregou (14/10)

Complemento do pedido 29: as telas do protótipo A (`frontend/mockups/prototipo_dashboard.html`, opção A). Detalhes na seção "Complemento: pedido 30" de `docs/handoff/2026-10-14_29_redesenho-base_relatorio.md`.

- **Rotas novas, só de leitura** (`backend/routers/leitura.py`, com teste): `/api/evolucao/resumo`, `/api/evolucao/sessoes/{sessao}`, `/api/coach/referencias`, `/api/store/voltas/{lap_id}` e `/api/geometria/oficial`. Leem os arquivos do repositório configurado na Coleta; nenhuma calcula nada.
- **Sessões:** o hero, as sessões do relatório de evolução (com a faixa de voltas e o atalho para a melhor volta), a tendência com o critério do ADR 0015 e as gravações que ainda não entraram no relatório.
- **Volta:** a opção A inteira, na geometria oficial:
  - a barra de contexto e a escolha de sessão, volta e referência (volta da IA ou sua melhor);
  - a volta com fantasma: as camadas do cache, o traçado pelo pedal, o fantasma por curva ou na volta inteira, o relevo, a pista inteira, a leitura dos dois carros e o replay;
  - o mapa dos 60 microssetores, a tabela das 14 curvas e os traços por distância;
  - as medidas repetem o método do relatório de evolução (`frontend/src/volta/medidas.ts`), conferidas contra o `por_volta` oficial e contra o protótipo.
- **Evolução:** a tendência, a perda por curva entre sessões com a faixa de 90% e a técnica por curva.
- **Destinos da seção 6 cumpridos:**
  - Pista e Análise deixaram de ser telas;
  - a comparação por distância e o replay estão em Volta;
  - as frases do coach ficam embaixo do replay e marcadas no mapa (rota `/api/analysis/coach/lap/{id}`, que já existia);
  - os traçados e o relevo da Análise entraram em Volta;
  - o painel de evolução virou a tela Evolução, com o bloco `tecnica`.
- **O que fica para o pedido de limpeza:** `Dashboard.tsx`, `AnalysisPage.tsx` e os componentes que só eles usavam continuam no código, sem rota.

### O que o pedido 31 entregou (18/10)

O rádio do engenheiro e a tela Ao vivo completa (ADR 0020). Detalhes em `docs/realidade_aumentada.md` e em `docs/handoff/2026-10-15_31_radio-realidade-aumentada_relatorio.md`.

- **O rádio no backend** (`backend/core/radio/`):
  - a mensagem é montada uma vez, com microssetor a partir de 1, a curva C01 a C14 e o lado por extenso;
  - ela é entregue só nas janelas de rádio (as retas) ou com o resumo na linha;
  - a voz é a Microsoft Daniel do Windows, com uma vinheta gerada pelo código;
  - cada mensagem entregue fica no registro `data/radio/<sessão>.jsonl`.
- **O app do jogo:** `tools/csp_app/radio_engenheiro/`, com os scripts de instalar e remover, que só o Eduardo roda.
- **A tela Ao vivo:**
  - a volta com fantasma ao vivo, com o mesmo componente da tela Volta;
  - o rádio, com o texto pronto e o áudio;
  - a gravação e os canais.
- **A tela Volta:** as frases de uma volta gravada usam o texto pronto do backend e o `s` da geometria oficial. Antes, usavam o `s` do runtime.
- **A tela Sistema:** a mensagem de teste do rádio.
- **O hero:** os tempos das referências vêm do store v2, a mesma fonte da tela Volta.
- **Dois defeitos antigos corrigidos no caminho ao vivo:**
  - o coach ao vivo não achava o modelo, porque o quadro não traz a pista;
  - o barramento enchia o log a cada quadro (958 MB no app instalado).

### O que o pedido 35 entregou (18/10)

O rádio que analisa as voltas, o mapa ao vivo sem travar e o minimapa no jogo (ADR 0021). Detalhes em `docs/realidade_aumentada.md` e em `docs/handoff/2026-10-18_35_radio-que-analisa-e-minimapa_relatorio.md`.

- **O que o rádio diz** (`backend/core/radio/`):
  - a frase do coach diz a causa principal na voz: a freada (mais de 15 m) ou a mínima (mais de 8 km/h);
  - o resumo na linha diz a curva em que a volta mais perdeu;
  - a análise das voltas, o tipo novo: a cada 3 voltas válidas, até 2 curvas perdidas em 2 das 3, com a freada, a mínima, o acelerador cheio e o traçado;
  - a voz a 1,4x e, em cada mensagem, a primeira fala que cabe em cerca de 6, 7 ou 8 s;
  - a mensagem só sai quando a fala inteira cabe no que resta da janela, pela velocidade do carro.
- **A tela Ao vivo:**
  - o mapa não trava: a tela pede só os pontos novos (`/api/live/volta/novos`), cerca de 24 vezes por segundo, com respostas de cerca de 0,5 KB (eram 65 KB, 3 vezes por segundo);
  - o carro anda a cada quadro da tela, e a pista é desenhada uma vez num bitmap (a tela Volta usa o mesmo componente);
  - o cartão do rádio mostra a análise, com uma linha por curva.
- **O app do jogo** (`tools/csp_app/radio_engenheiro/`):
  - a voz tem três caminhos (a URL, o arquivo do backend e o áudio baixado para a pasta do app), com uma linha no log do CSP por mensagem;
  - o minimapa, uma segunda janela: a pista, o carro, o fantasma da referência pelo tempo, a diferença ao vivo e as curvas da última análise;
  - o mapa aproximado, uma terceira janela, pedida depois da primeira captura do jogo (21/10): a vista de perto da tela Volta, com a pista detalhada girando em volta do carro e os traçados pintados pelo pedal;
  - o FPS do jogo no log a cada 10 s, com cada mapa ligado ou desligado.
- **Para os testes sem o jogo:** o reprodutor de gravações (`/api/teste/*`, só com `AT_TESTE_REPRODUTOR=1`) toca uma sessão pelo caminho do jogo.
- **Falta:** o teste no jogo (Parte G), com o caminho da voz que funcionou e o custo do minimapa.
