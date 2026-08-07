# 🏗️ Arquitetura do Sistema

## Visão Geral

```
┌──────────────────────────────────────────────────────────────────────┐
│                         ASSETTO CORSA (jogo)                          │
│  ┌────────────────────────┐        ┌───────────────────────────────┐ │
│  │ Memória compartilhada   │        │ apps/python/ac_opponents_      │ │
│  │ (telemetria do jogador) │        │ exporter (plugin do jogo)      │ │
│  └───────────┬─────────────┘        └────────────┬────────────────┘ │
└──────────────┼───────────────────────────────────┼───────────────────┘
               │ leitura direta                    │ UDP 127.0.0.1:8765
               ▼                                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI, main.py)                     │
│                                                                        │
│  core/assetto_adapter.py, ac_shared_memory.py, assetto_shared_memory_ │
│  gate.py            → leitura/validação da memória compartilhada      │
│  core/live/          → TelemetryRuntime, RuntimeState, lap_collector  │
│  core/opponents/      → OpponentsRuntime, buffer, receiver UDP        │
│  core/geometry/, kn5/ → reconstrução da pista a partir de .kn5/.ai    │
│  core/reconstruction/ → fallback: reconstrução por amostras de volta  │
│  core/cache/          → cache de geometria de pista em disco (JSON)   │
│                                                                        │
│  core/racing_line_analysis.py   → racing line ideal por microsetor    │
│  core/comparison_analysis.py    → comparação jogador x referência     │
│  core/car_physics.py            → estado físico (g-force, slip, etc.) │
│  core/assisted_analysis/        → classificação de erros de pilotagem │
│  core/external_references/      → referências reais (FastF1/Interlagos)│
│  core/data_quality/             → confiabilidade de telemetria/UDP    │
│  core/recording/                → gravação e persistência de sessões  │
│  core/websocket_server.py       → broadcast em tempo real (WS)        │
└───────────────────────┬────────────────────────────────────────────┘
                         │ REST (JSON) + WebSocket (/ws)
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  FRONTEND (React + Vite + TypeScript)                 │
│  ┌───────────────┐ ┌────────────────────┐ ┌────────────────────────┐ │
│  │ TrackRenderer │ │ RacingLineAnalysis  │ │ AssistedAnalysisPanel  │ │
│  │ (canvas 2D)   │ │ Panel / LiveCompari-│ │ CarPhysicsDebugPanel   │ │
│  │               │ │ sonPanel            │ │ SessionLapsPanel       │ │
│  └───────────────┘ └────────────────────┘ └────────────────────────┘ │
│              useTelemetryStore (Zustand) + useTelemetryWS             │
└───────────────────────┬────────────────────────────────────────────┘
                         │ carregado por
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│           DESKTOP SHELL (Electron) — desktop/main.js                  │
│  Inicia/monitora o backend empacotado (PyInstaller), detecta conflito │
│  de porta, expõe diagnóstico de runtime, carrega o frontend estático. │
└──────────────────────────────────────────────────────────────────────┘
```

O sistema **não depende de upload de arquivo**. A pista e a telemetria vêm
sempre da instância em execução do Assetto Corsa; CSVs só existem como
fixtures de teste e como fallback opcional em `/api/upload/telemetry`
(usado para reconstrução de pista a partir de amostras gravadas, não para o
fluxo principal).

## Fluxo de Dados

### 1. Telemetria do jogador (tempo real)

```
Assetto Corsa (memória compartilhada)
        │
        ▼
assetto_shared_memory_gate.py   → só libera leitura com o processo do jogo ativo
        │
        ▼
core/live/telemetry_runtime.py  → amostragem adaptativa (Hz variável conforme carga)
        │
        ▼
core/live/runtime_state.py + telemetry_buffer  → estado corrente + histórico em memória
        │
        ├──▶ core/car_physics.py            → g-force, slip, transferência de carga
        ├──▶ core/racing_line_analysis.py   → delta em relação à linha ideal
        ├──▶ core/comparison_analysis.py    → comparação por microsetor
        ├──▶ core/recording/                → grava a sessão em disco (DuckDB)
        └──▶ websocket_server.py            → broadcast para o frontend (/ws)
```

### 2. Telemetria dos oponentes

```
Plugin Python dentro do Assetto Corsa (tools/assetto_opponents_exporter)
        │  JSON via UDP, 127.0.0.1:8765
        ▼
core/opponents/opponents_receiver.py  → parsing + validação de pacotes
        │
        ▼
core/opponents/opponents_runtime.py + opponents_buffer.py
        │
        ├──▶ /api/live/opponents
        └──▶ websocket_server.py → broadcast para o frontend
```

### 3. Geometria da pista

```
Arquivos do Assetto Corsa (.kn5, fast_lane.ai)
        │
        ▼
core/track_file_resolver.py        → localiza os arquivos da pista instalada
        │
        ▼
core/kn5/  (kn5_reader, kn5_surface_extraction, track_edges_from_surface,
            track_surface_polygon)
        │
        ▼
core/geometry/track_geometry_provider.py  → monta centerline/bordas/curvatura
        │
        ▼
core/cache/track_cache.py          → cache em disco (evita reprocessar o KN5)
```

Para Interlagos especificamente existe uma geometria corrigida e travada em
`core/geometry/interlagos_track_only_fixed.py`, gerada offline pelos scripts
em `scripts/build_interlagos_*` — ela é carregada antes de qualquer cache do
usuário para garantir paridade visual entre o app instalado e o `main`.

### 4. Análise assistida pós-volta

```
Volta gravada (core/recording/session_repository.py)
        │
        ▼
core/assisted_analysis/lap_analysis_service.py
        │
        ├──▶ corner_segmentation.py + corner_metrics.py   → segmenta a volta em curvas
        ├──▶ driver_error_classifier.py                    → classifica erros por curva
        ├──▶ reference_lap_comparator.py                   → compara com volta de referência
        │        (interna ou externa via core/external_references, ex.: FastF1)
        └──▶ feedback_generator.py                          → gera texto de feedback
```

## Componentes Principais

### Backend

| Módulo | Responsabilidade |
| --- | --- |
| `core/live/` | Ingestão e amostragem adaptativa da telemetria do jogador |
| `core/opponents/` | Recepção UDP e buffer de estado dos oponentes |
| `core/geometry/`, `core/kn5/` | Reconstrução da geometria real da pista a partir dos arquivos do jogo |
| `core/racing_line_analysis.py` | Linha ideal por microsetor com base física |
| `core/comparison_analysis.py` | Comparação jogador × referência por microsetor |
| `core/car_physics.py` | Estado físico do carro (g, slip, transferência de carga) |
| `core/assisted_analysis/` | Classificação de erros de pilotagem e feedback pós-volta |
| `core/external_references/` | Importação de referências reais (FastF1) para Interlagos |
| `core/data_quality/` | Monitoramento de confiabilidade (telemetria, UDP, pista, volta) |
| `core/recording/` | Gravação, persistência e replay de sessões/voltas (DuckDB) |
| `core/websocket_server.py` | Broadcast em tempo real para o frontend |
| `main.py` | ~60 endpoints REST + endpoint WebSocket `/ws`, monta e conecta os módulos acima |
| `desktop_backend_runner.py` | Ponto de entrada usado no executável empacotado (PyInstaller) |

### Frontend

| Componente | Responsabilidade |
| --- | --- |
| `components/map/TrackRenderer.jsx` | Renderização 2D em canvas da pista, carro do jogador e oponentes |
| `components/RacingLineAnalysisPanel.tsx` | Visualização da racing line e ganhos por curva |
| `components/LiveComparisonPanel.tsx` | Comparação por microsetor em tempo real |
| `components/AssistedAnalysisPanel.tsx` | Feedback de pilotagem pós-volta |
| `components/CarPhysicsDebugPanel.tsx` | Depuração de física do carro |
| `components/SessionLapsPanel.tsx`, `ReplayControls.tsx` | Navegação e replay de sessões gravadas |
| `store/useTelemetryStore.ts` | Estado global (Zustand) |
| `hooks/useTelemetryWS.ts` | Cliente WebSocket, reconexão e parsing de mensagens |

### Desktop (Electron)

| Arquivo | Responsabilidade |
| --- | --- |
| `desktop/main.js` | Ciclo de vida da janela, autostart do backend empacotado, detecção de porta/health, IPC seguro |
| `desktop/preload.js` | Ponte segura entre o processo principal e o frontend (`window.desktopRuntime`) |
| `backend/packaging/` | Build do backend com PyInstaller (`automobilista-backend.exe`) |
| `desktop/package.json` (electron-builder) | Empacotamento final e instalador NSIS |

## Princípios de Design

- **Fonte da verdade é o jogo em execução**: pista e telemetria vêm sempre
  do Assetto Corsa (memória compartilhada, arquivos `.kn5`, UDP), nunca de
  upload manual.
- **Física real, sem valores mágicos**: racing line e comparação usam
  fórmulas físicas (`v² = μ·g·r`, transferência de carga, etc.), não
  escalonamento arbitrário da trajetória do jogador.
- **Separação de responsabilidades**: cada submódulo de `core/` tem uma
  única fonte de dados e uma única responsabilidade (ingestão, geometria,
  análise, persistência, broadcast).
- **Degradação graciosa**: sem o jogo aberto, o backend continua respondendo
  (`waiting`/mock) em vez de falhar; sem oponentes ativos, o app funciona
  só com o jogador.

## Tecnologias e Bibliotecas

### Backend
```
FastAPI      → Framework web assíncrono (REST + WebSocket)
Uvicorn      → Servidor ASGI
Pandas / NumPy / SciPy → Processamento numérico e geometria
DuckDB       → Persistência de sessões e voltas gravadas
Pydantic     → Validação de dados
FastF1       → Referências reais de telemetria para Interlagos
PyInstaller  → Empacotamento do backend como executável Windows
```

### Frontend
```
React 18 + TypeScript (migração de JS em andamento) → UI
Vite         → Build tool
Zustand      → Estado global
Plotly.js / Recharts → Gráficos
Axios        → Cliente HTTP REST
Canvas 2D (nativo) → Renderização do mapa da pista
```

### Desktop
```
Electron         → Shell desktop multiplataforma (build atual: Windows)
electron-builder → Empacotamento e instalador NSIS
```

## Segurança

- CORS configurado para desenvolvimento local.
- Validação de payloads de entrada (Pydantic, validação de pacotes UDP).
- Limites de tamanho e sanitização em uploads legados (fixtures/replay).
- Nenhuma credencial ou dado pessoal é coletado; todos os dados são locais.

## Performance

- Backend assíncrono (FastAPI/Uvicorn) com amostragem adaptativa da
  telemetria do jogador (ver `docs/phase15_runtime_sampling.md`).
- Broadcast via WebSocket em vez de polling para dados de alta frequência.
- Cache de geometria de pista em disco para evitar reprocessar arquivos KN5.
- Diagnóstico de performance dedicado em `/api/runtime/performance` e
  `tools/runtime_performance_probe.py`.

## Testes

134 testes automatizados (`backend/tests`, `unittest`) cobrem análise de
racing line, comparação, qualidade de dados, gravação de sessão, física do
carro, protocolo UDP de oponentes e o gate de memória compartilhada. Não há
testes automatizados de frontend nem CI configurado até o momento.

## Limitações e Débitos Técnicos Conhecidos

- **Migração TypeScript incompleta**: componentes `.jsx`/`.js` e
  `.tsx`/`.ts` coexistem; `npx tsc --noEmit` aponta erros de tipo reais que
  não bloqueiam o build (Vite não faz type-check completo).
- **Sem CI**: testes, build e type-check são executados manualmente.
- **Histórico do git**: commits antigos incluem artefatos grandes
  (ambiente virtual, cache do FastF1) que hoje estão no `.gitignore` mas
  continuam na história, inflando o tamanho do repositório.
- **Branches divergentes**: ver `BRANCH_STATUS.md` — várias branches têm
  trabalho não integrado ou conflitante com o `main` atual.

## Escalabilidade Futura

Possíveis melhorias:
- [ ] Suporte a outras pistas além de Interlagos com o mesmo pipeline KN5
- [ ] CI com testes de backend, build de frontend e type-check
- [ ] Conclusão da migração para TypeScript
- [ ] Assinatura digital do instalador e auto-update
- [ ] Suporte a outros simuladores além do Assetto Corsa
