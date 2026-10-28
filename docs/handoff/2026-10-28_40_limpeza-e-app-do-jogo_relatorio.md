# Relatório do pedido 40: limpeza e app do jogo 0.4.1 (PARCIAL)

- **Pedido:** `docs/prompts/2026-10-28_40_limpeza-e-app-do-jogo.md`
- **Branch:** `etapa/limpeza-e-app-do-jogo`, criada de `develop` (`4782aefb`). **Sem merge em `develop`.**
- **Commits:**
  - `30f9fd86` docs: pedido 40
  - `869dae13` Pedido 40, Parte B: o app do jogo 0.4.1 em develop (merge de `etapa/radio-unidades-e-replay`, só o `0092ed38`)
  - `01d99c95` Pedido 40, Parte B: a versão 0.4.1 do app do jogo em `realidade_aumentada.md`
  - mais o commit deste relatório
- **Handoff:** só este relatório. O CSV das remoções ainda não foi gravado.
- **A pasta:** voltou para `etapa/m1-modelo-do-carro`.

**O trabalho parou no meio porque o limite de uso da sessão acabou.** Fizeram-se a Parte A, a Parte B e o levantamento da Parte C. Nada foi removido nem corrigido.

## Parte A: o antes, em `develop`

As sessões dos pedidos 38 e 39 estavam paradas, e não havia trava do git. Na árvore, só o pedido e uma pasta `recordings/` na raiz (não rastreada e não ignorada; a linha do `.gitignore` tem uma tabulação na frente). Não mexi nela.

| Suíte | Antes |
|---|---|
| Backend (`pytest tests`, na pasta `backend`) | 794 passando, 9 min 8 s |
| `vitest run` | 189 testes em 17 arquivos, todos passando |
| `tsc --noEmit` | sem erros |
| `npm test` (desktop) | 4 testes, todos passando |
| `conferir_lua.py` (0.4.0) | 0 erros de léxico, blocos ok, 45 chamadas da API e 11 métodos, todos no SDK |

## Parte B: o app do jogo 0.4.1 (feita)

- `git log develop..etapa/radio-unidades-e-replay` mostrou só o `0092ed38`. O merge trouxe `manifest.ini` (`VERSION = 0.4.1`) e 37 linhas no `radio_engenheiro.lua`.
- `conferir_lua.py` depois do merge: 0 erros de léxico, blocos ok, 45 chamadas da API e 12 métodos (entrou o `move`), todos no SDK do CSP.
- `docs/realidade_aumentada.md`, seção 5: a versão e a correção da janela salva fora da tela.
- Não rodei o `instalar.ps1` nem escrevi na pasta do jogo.

## Parte C: o levantamento (feito; nada removido)

**Front, sem nenhum caminho a partir de `main.tsx`:**
- `Dashboard.tsx` e `pages/AnalysisPage.tsx`;
- os componentes `AIDebriefPanel`, `AIEngineerPanel`, `AssistedAnalysisPanel`, `AssistedLapTraces`, `CoachingFeed`, `CognitiveDashboard`, `ElevationProfile`, `GGDiagram`, `Header`, `LiveComparisonPanel`, `LiveTelemetryPanels` (onde está o `StabilityPanel`), `RacingLineAnalysisPanel`, `ReplayControls`, `SectorComparison`, `SessionLapsPanel`, `SessionTimeline` e `TelemetryTraces`;
- `types/racingLine.ts`, `utils/comparisonAnalysis.ts` e `utils/sectorTimes.ts`.

Dois testes só cobrem código morto: `CoachingFeed.test.ts` (12 testes) e `sectorTimes.test.ts` (17). Saem junto com o código.

**Funções mortas do mapa:**
- `OverlayRenderer.tsx`:
  - o bloco do relevo (`trackHasRelief`, `reliefRange`, `getReliefCache` e o que só eles usam). O `reliefColorAt` só é usado pelo `ElevationProfile`, que sai;
  - `getTrackSurfaceCache`, `strokePolylineSegments`, `drawPitVisualGeometry` e o que só eles usam.
- `CarRenderer.tsx`: `drawTrajectory`.

**Métodos do `client.ts` que o código vivo não chama:** `uploadTrack`, `uploadTelemetry`, `getTrackData`, `getCurrentTrack`, `getTrackCache`, `getCarState`, `getLiveTelemetry`, `getLiveComparison`, `getSession`, `getSessionLap`, `getOfflineLap`, `getOfflineLapSummary`, `getOfflineLapSamples`, `getTelemetryData`, `getAiRaceline`, `getComparison`, `getTrackLimits`, `listAssistedAnalysisLaps`, `getAssistedLapTelemetry`, `getAssistedAnalysis`, `requestAssistedAnalysis`, `getLiveVolta`, `listExternalReferences` e `importFastF1Reference`.

**Rotas (são 94 no backend):**
- **Sem nenhum uso** (candidatas a sair):
  - `/api/analysis/comparison` e `/api/analysis/racing-line`;
  - `/api/assisted-analysis/laps` e `/api/assisted-analysis/laps/{id}/analysis` (GET e POST);
  - as 8 rotas `/api/debug/*`;
  - `GET /api/live/source`, `/api/live/comparison` e `POST /api/live/telemetry`;
  - `/api/recording/start` e `/api/recording/stop`;
  - `/api/telemetry/live`;
  - `/api/track/reconstruct`, `/api/track/current`, `/api/track/cache` (GET e POST) e `/api/car/state`;
  - `/api/validation/laps`, `/api/validation/track` e `/api/validation/udp`;
  - `/api/upload/telemetry` e `/api/upload/track`;
  - `/api/data/track`, `/api/data/telemetry`, `/api/data/ai-raceline` e `/api/data/track-limits`;
  - `/api/sessions/{id}`, `/api/sessions/{id}/laps/{n}` e `/api/laps/{id}`.
- **Ficam, porque um teste ou um script as usa:**
  - `/api/analysis/assisted/lap/{id}` (GET, POST e telemetry) e `/api/laps/{id}/summary`, `/samples` e `/replay`: `test_assisted_analysis_validation_flow.py`;
  - `POST /api/live/source/{s}`: `test_assetto_shared_memory_gate.py`;
  - `GET /api/live/telemetry` e `/api/live/opponents`: `test_udp_integration_contract.py`;
  - `/api/references/external/fastf1/import`: `test_external_references.py`;
  - `/api/data/comparison`: `backend/test_api_comparison.py`;
  - `/api/test/simulate`: `backend/stress_test.py`;
  - `/api/runtime/performance`: um teste e `tools/runtime_performance_probe.py`;
  - `/api/teste/*`: a ferramenta de teste do pedido 35.
- **Na dúvida, ficam:** `GET /api/references/external` e `/{id}`, que fazem par com a rota de importar, que tem teste.

**Globais em `window`:** os quatro têm leitores vivos (`TrackRenderer`, `DesktopRuntimePanel`), então ficam.

## Parte D: o que já foi investigado

1. **O gravador junta passagens:**
   - **A causa:** na gravação `2026-10-04_02-24-04` (linha 125.041 do `player.jsonl`), o contador cai de 14 para 1 um quadro antes de o relógio zerar. O `RecordingRuntime._should_rotate` exige as duas coisas no mesmo quadro, então a pasta nova nunca abre.
   - **A correção proposta:** abrir a pasta nova quando o contador diminuir, sem mudar o formato.
   - **O que essa correção não pega:** um reinício durante a volta 1 não muda o contador e não dá para detectar.
2. **A rota das frases do coach:** o `LapLoader` só recebe `data/recordings` do repositório. O `ml.config.recordings_roots()` dá as duas pastas, e o `list_all_sessions` dá a regra do nome repetido. Ainda não está ligado.
3. a 7. **Não começados.**

## O que falta

- **Parte C:** remover, gravar o CSV, rodar as suítes, o teste de ponta a ponta e o build do front.
- **Parte D:** os itens 1 a 7.
- **Parte E:** a documentação.
- **Parte F:** o merge em `develop`.
