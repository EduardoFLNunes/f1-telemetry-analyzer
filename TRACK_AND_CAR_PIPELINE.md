# Como a pista e o carro sao criados no projeto

Este documento descreve a arquitetura atual do `f1-telemetry-analyzer` para:

- criar a geometria da pista;
- ler e posicionar o carro;
- manter pista, carro, projecao e visual separados;
- documentar os artefatos debug da pitlane de Interlagos.

Ele tambem registra as regras de seguranca que foram estabelecidas durante a implementacao.

## Resumo Executivo

A pista ativa nao vem mais de CSV e nao deve ser criada a partir do caminho dirigido pelo piloto.

O modelo atual separa quatro coisas:

- `TrackPhysicsGeometry`: geometria fisica/autoritativa da pista, usada para projecao, distancia ao longo da pista e `lateralOffset`.
- `TrackVisualGeometry`: geometria visual, usada apenas para desenhar a pista de forma limpa no frontend.
- `DriverTrajectory`: rastro real do carro, usado somente como debug/replay/racing line, nunca como pista.
- `CarState`: estado vivo do carro vindo do Assetto Corsa Shared Memory.

O sistema canonico de coordenadas do mapa e:

```text
mapX = worldX
mapY = -worldZ
```

O carro visual usa sempre `car.mapPosition`.

`projectedPosition` e apenas a posicao mais proxima na centerline fisica da pista, usada para debug, telemetria e calculo de `lateralOffset`. Ela nao deve ser usada para desenhar o marcador visual do carro.

## Fontes De Verdade

### Pista Principal

A fonte autoritativa da pista principal e:

```text
Assetto Corsa track files
KN5 visual track mesh
surfaces.ini
fast_lane.ai somente como referencia longitudinal
```

No caso validado de Interlagos:

```text
track: vhe_interlagos
layout: gp
main visual KN5: vhe_interlagos.kn5
geometry surfaces: ROAD, CURB, KERB
reference AI line: gp/ai/fast_lane.ai
```

O driver path nao entra como pista.

### Carro

A fonte primaria do carro e:

```text
Assetto Corsa Shared Memory
```

O leitor ativo deve ser `assetto_corsa` quando o shared memory esta disponivel. CSV/replay existe apenas como fallback/debug explicito.

### Pitlane

A pitlane de Interlagos foi extraida como debug/export only.

A fonte confiavel da pitlane e:

```text
1pitlane001
1pitlane002
1pitlane003
```

`pit_lane.ai` foi validada como rota diagnostica, nao como centerline fisica da pitlane.

## Arquivos Principais

### Backend

```text
backend/main.py
```

Responsavel por inicializar a fonte de telemetria, carregar a geometria ativa, expor APIs e manter o runtime.

```text
backend/core/telemetry/telemetry_reader_impl.py
```

Define leitores de telemetria e `TelemetrySourceManager`.

```text
backend/core/live/runtime_state.py
```

Mantem a geometria ativa, o estado do carro, a engine de projecao e o ultimo estado projetado.

```text
backend/core/geometry/track_geometry_provider.py
```

Contem os providers de geometria:

- `Kn5SurfaceTrackGeometryProvider`
- `CacheTrackGeometryProvider`
- `DebugTrajectoryTrackGeometryProvider`

O provider KN5 e o caminho principal para Assetto Corsa.

```text
backend/core/geometry/track_geometry_cleanup.py
```

Pós-processamento da geometria fisica final: remove saltos, reamostra por distancia e suaviza sem trocar a fonte autoritativa.

```text
backend/core/geometry/track_visual_geometry.py
```

Cria geometria visual separada, incluindo ribbon visual, para desenhar a pista sem usar diretamente todos os recortes do mesh fisico.

```text
backend/core/projection/spatial_projection.py
```

Projeta o carro contra a centerline fisica por nearest-segment projection.

```text
backend/core/track_file_resolver.py
```

Resolve a pasta da pista atual no Assetto Corsa a partir do shared memory/config.

```text
backend/core/debug/pitlane_debug.py
```

Carrega artefatos debug ja exportados da pitlane e monta payloads para overlay visual. Nao altera runtime.

### Frontend

```text
frontend/src/components/map/TrackRenderer.jsx
```

Renderizador principal do mapa. Coordena camera, canvas, debug layers e desenho do carro.

```text
frontend/src/components/map/OverlayRenderer.jsx
```

Desenha pista, bordas, centerline, HUD e debug de projecao.

```text
frontend/src/components/map/CarRenderer.jsx
```

Desenha o carro usando `frame.mapPosition`.

```text
frontend/src/components/map/CameraController.jsx
```

Controla overview/follow camera com easing.

```text
frontend/src/hooks/useInterpolatedCarState.ts
```

Interpola visualmente o carro usando `mapPosition`, sem substituir pela projecao.

```text
frontend/src/store/useTelemetryStore.ts
```

Armazena frame vivo, historico e metricas de telemetria/render.

```text
frontend/src/components/map/PitLaneOverlay.jsx
frontend/src/components/map/PitLaneDebugPanel.jsx
frontend/src/hooks/usePitLaneDebugData.ts
```

Camada debug opcional para visualizar pitlane raw, manual 05_05, candidatos, transicao de saida e artefatos locais.

## Como A Pista Principal E Criada

### 1. Detectar Fonte De Telemetria

Durante o startup, o backend usa `TelemetrySourceManager` para escolher a fonte:

- se `TELEMETRY_SOURCE=assetto_corsa`, usa shared memory ou falha;
- se `TELEMETRY_SOURCE=replay`, usa CSV explicitamente;
- se `TELEMETRY_SOURCE=auto`, usa Assetto Corsa quando disponivel;
- replay so entra automaticamente se fallback estiver explicitamente permitido.

No modo live correto, a resposta deve indicar:

```json
{
  "source": "assetto_corsa",
  "ac_available": true
}
```

### 2. Resolver Arquivos Da Pista

`TrackFileResolver` usa dados do shared memory:

- `trackName`
- `trackConfig`
- `acInstallPath`
- `gameCode`
- `source`

Depois resolve:

```text
<AC_ROOT>/content/tracks/<trackName>
models_<trackConfig>.ini
models.ini
data/surfaces.ini
ai/fast_lane.ai
ai/pit_lane.ai
KN5 files
```

O endpoint de auditoria e:

```text
GET /api/debug/track-file-manifest
```

### 3. Inspecionar E Extrair KN5

O pipeline validado inspeciona os KN5s e identifica meshes/materials candidatos.

Para Interlagos, a conclusao foi:

- `vhe_interlagos.kn5` contem meshes validos para ROAD/CURB/KERB;
- `obj_collider.kn5` nao expos ROAD/CURB/KERB como fonte primaria de superficie dirigivel;
- `obj_collider.kn5` fica como diagnostico, nao como fonte principal.

Arquivos relacionados:

```text
backend/core/kn5/kn5_reader.py
backend/core/kn5/kn5_models.py
backend/core/kn5/kn5_inventory.py
backend/core/kn5/kn5_surface_extraction.py
```

Endpoints:

```text
GET /api/debug/kn5-inventory
GET /api/debug/kn5-surface-candidates
```

### 4. Construir TrackSurfacePolygon

Os meshes ROAD/CURB/KERB sao projetados para 2D:

```text
mapX = worldX
mapY = -worldZ
```

Isso gera uma sopa de triangulos da superficie valida da pista.

Export validado:

```text
data/debug/track_surface_triangles_vhe_interlagos.json
data/debug/track_surface_bounds_vhe_interlagos.json
data/debug/track_surface_preview_vhe_interlagos.svg
```

Endpoint:

```text
GET /api/debug/track-surface-polygon
```

### 5. Limpar Componentes E Extrair Corredor Principal

Foi feita analise de componentes conectados para separar:

- componente principal da pista;
- ilhas/auxiliares;
- loops internos;
- contornos pequenos.

O objetivo foi evitar que ilhas ou buracos internos contaminassem a largura da pista.

Arquivos:

```text
data/debug/track_surface_components_vhe_interlagos.json
data/debug/track_boundary_loops_vhe_interlagos.json
```

### 6. Usar fast_lane.ai Apenas Como Referencia Longitudinal

`fast_lane.ai` fornece a ordem ao longo da volta, mas nao vira centerline final.

O algoritmo:

1. amostra pontos da fast lane;
2. calcula tangente;
3. calcula normal;
4. faz raycast lateral contra a TrackSurfacePolygon;
5. seleciona o intervalo dentro da superficie que contem o ponto da fast lane;
6. extrai `left_edge`, `right_edge`, `local_width`;
7. define `centerline = midpoint(left_edge, right_edge)`.

Regra importante:

```text
Nao escolher simplesmente a intersecao esquerda/direita mais proxima global.
Escolher o intervalo de superficie que contem a fast_lane.
```

Isso corrigiu contaminacoes por loops internos.

Arquivos:

```text
data/debug/track_edges_interval_raycast_vhe_interlagos.json
data/debug/track_edges_interval_raycast_preview_vhe_interlagos.svg
```

### 7. Pós-processamento Da Geometria Fisica

Depois da extracao KN5, a geometria fisica passa por cleanup opcional:

```text
TRACK_GEOMETRY_CLEANUP_ENABLED=true
TRACK_GEOMETRY_TARGET_SPACING=1.5
TRACK_GEOMETRY_SMOOTHING_WINDOW=5
```

Resultado validado:

- pontos brutos: 2680;
- pontos limpos: aproximadamente 2897;
- maior segmento limpo: aproximadamente 1.5 m;
- loop fechado;
- left/right consistente;
- largura plausivel.

Cache principal:

```text
data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json
```

### 8. TrackPhysicsGeometry

A geometria fisica exporta:

- `centerline`
- `boundsLeft`
- `boundsRight`
- `localWidth`
- `normals`
- `curvature`
- `distance`
- `p`
- `bounds`
- `closedLoop`
- `metadata`

Ela e usada para:

- nearest-point projection;
- `distanceAlongTrack`;
- `spline_t`/`p`;
- `lateralOffset`;
- debug fisico;
- limites futuros.

Ela nao deve ser modificada por:

- DriverTrajectory;
- pitlane debug;
- visual ribbon;
- mirror frontend.

### 9. TrackVisualGeometry

Foi criada uma geometria visual separada para reduzir recortes e artefatos do mesh fisico.

Ela e visual-only.

Ela pode conter:

- `visualGeometry.centerline`
- `visualGeometry.leftEdge`
- `visualGeometry.rightEdge`
- `visualGeometry.width`
- `visualRibbonGeometry`
- `visualRenderMode`
- metadados como `visualVersion`, `visualOnly`, `physicsUnaffected`

Render modes:

```text
polygon
ribbon
```

O modo ribbon desenha a pista como um stroke grosso sobre uma centerline visual suavizada, estilo overlay/SimHub.

Importante:

```text
TrackVisualGeometry nao altera projecao, lateralOffset ou fisica.
```

## Como O Carro E Criado

### 1. Leitura Do Assetto Corsa Shared Memory

`ACSharedMemoryReader` usa `AssettoAdapter` para ler dados vivos:

- posicao world `x`, `y`, `z`;
- velocidade;
- heading/yaw;
- throttle;
- brake;
- steer;
- gear;
- rpm;
- lap;
- sector;
- lap distance percent;
- track name/config;
- car model;
- install path.

Esses dados viram `TelemetrySample`.

Arquivo:

```text
backend/core/telemetry/telemetry_reader_impl.py
```

### 2. Ingestao No Runtime

O backend chama:

```text
ingest_one_active_sample()
```

Esse metodo:

1. le uma amostra ativa;
2. adiciona ao `TelemetryBuffer`;
3. chama `runtime_state.update_car(sample)`;
4. devolve o frame processado.

### 3. Criar mapPosition Real Do Carro

O carro visual e sempre criado a partir da posicao real em world-space:

```text
mapPosition.x = worldPositionX
mapPosition.y = -worldPositionZ
```

Quando nao existe pista/projecao carregada, o backend ainda retorna:

```json
{
  "mapPosition": {
    "x": "worldPositionX",
    "y": "-worldPositionZ"
  },
  "projectedPosition": null,
  "lateralOffset": null
}
```

### 4. Projetar O Carro Na Pista

Quando existe `ProjectionEngine`, `RuntimeState.update_car()` chama:

```text
projection_engine.project_car(worldPositionX, worldPositionZ)
```

O resultado inclui:

- `mapPosition`: posicao visual real do carro;
- `projectedPosition`: ponto mais proximo na centerline;
- `projectedWorldPosition`;
- `distanceAlongTrack`;
- `spline_t`;
- `p`;
- `lateralOffset`;
- `trackHeading`;
- `nearestSegmentIndex`;
- vetores de debug.

Regra critica:

```text
O marcador visual do carro nao usa projectedPosition.
```

`projectedPosition` so aparece em debug/projecao.

### 5. Estado Do Carro Exposto Pela API

Endpoints principais:

```text
GET /api/car/state
GET /api/live/telemetry
GET /api/telemetry/live
```

Campos importantes:

```json
{
  "mapPosition": {"x": "...", "y": "..."},
  "projectedPosition": {"x": "...", "y": "..."},
  "lateralOffset": "...",
  "distanceAlongTrack": "...",
  "heading": "...",
  "speedKmh": "...",
  "projectionDebug": "..."
}
```

### 6. Frontend E Interpolacao

O frontend recebe telemetria e armazena em:

```text
frontend/src/store/useTelemetryStore.ts
```

O hook:

```text
frontend/src/hooks/useInterpolatedCarState.ts
```

suaviza o movimento visual do carro por `requestAnimationFrame`.

Ele interpola:

- `mapPosition`;
- `heading`;
- alguns campos dinamicos.

Ele nao usa `projectedPosition` como posicao visual.

O desenho do carro acontece em:

```text
frontend/src/components/map/CarRenderer.jsx
```

e usa:

```text
frame.mapPosition
```

## Como Pista E Carro Ficam Alinhados

O alinhamento existe porque ambos usam o mesmo map-space:

```text
pista: pontos KN5 projetados para mapX=worldX, mapY=-worldZ
carro: shared memory worldX/worldZ projetado para mapX=worldX, mapY=-worldZ
```

A projecao do carro e feita sobre a centerline fisica fixa.

Isso significa:

- o carro pode sair da pista;
- o carro pode tocar zebra;
- o carro pode ficar lateralmente distante da centerline;
- a pista nao se move com o carro;
- `lateralOffset` muda quando o carro se desloca lateralmente;
- DriverTrajectory nao altera a pista.

## Espelhamento Visual

O mirror horizontal e apenas visual e aplicado em screen-space/canvas final.

Ele nao altera:

- `mapPosition`;
- `projectedPosition`;
- TrackGeometry;
- lateralOffset;
- bounds fisicos;
- backend.

Pipeline correto:

```text
map point -> camera/worldToScreen -> screen-space mirror -> draw
```

No Canvas:

```js
ctx.translate(canvas.width, 0)
ctx.scale(-1, 1)
drawMapLayers()
```

HUD/textos nao devem ser espelhados.

## Pitlane De Interlagos

### O Que Foi Validado

A pitlane foi construida como debug/export, nao runtime.

Fonte:

```text
1pitlane001
1pitlane002
1pitlane003
```

Arquivos base:

```text
data/debug/interlagos_pitlane_surface_boundary.json
data/debug/interlagos_pitlane_surface_derived_geometry.json
data/debug/interlagos_pitlane_trim_candidates_minimal.json
data/debug/interlagos_pitlane_trimmed_manual_05_05.json
data/debug/interlagos_pitlane_manual_trim_final_report.json
```

### PitLaneGeometryRaw

Geometria completa derivada da superficie `1pitlane*`.

Uso:

```text
auditoria/debug
```

Nao e usada no runtime.

### PitLaneGeometryTrimmedManual 05_05

Candidata manual validada:

```text
manualTrimSelected = candidate_05_05
aggressiveTrimRejected = true
runtimeChanged = false
readyForRuntimeIntegration = false
```

Metricas:

```text
rawPointCount = 192
trimmedPointCount = 182
rawLengthMeters = 384.44
trimmedLengthMeters = 364.48
removedStartMeters = 9.98
removedEndMeters = 9.98
```

Entrada:

```text
manual_05_05 start = (-339.274471, -425.069001)
distancia ate main centerline ~= 28.08 m
distancia ate main edge ~= 21.22 m
largura media ~= 15.20 m
```

Saida:

```text
manual_05_05 end = (-432.446484, -75.929951)
distancia ate main centerline ~= 16.71 m
distancia ate main edge ~= 10.92 m
largura media ~= 6.00 m
```

Conclusao:

```text
Entrada esta mais clara e separada.
Saida e estreita e proxima da pista principal.
```

### Pit Exit Zone

Foi criado diagnostico debug-only para a saida da pitlane:

```text
data/debug/interlagos_pit_exit_core_problem_analysis.json
data/debug/interlagos_pit_exit_core_problem_analysis.svg
data/debug/interlagos_maintrack_pit_exit_zone_candidate.json
data/debug/interlagos_maintrack_pit_exit_zone_candidate.svg
data/debug/interlagos_pit_exit_transition_geometry.json
data/debug/interlagos_pit_exit_transition_geometry.svg
```

Diagnostico:

```text
pitManualEnd = (-432.446484, -75.929951)
nearest main point ~= index 1479, distancia ~= 16.71 m
direction-compatible merge point ~= index 2697, distancia ~= 50.15 m
suspected false chicane indices ~= 1435-1491
transition length ~= 58.78 m
runtimeChanged = false
```

Essas geometrias sao apenas debug:

- `MainTrackExitZoneCandidate`
- `PitExitTransitionGeometry`

Elas nao alteram a MainTrack autoritativa.

## APIs Importantes

### Runtime

```text
GET /health
GET /api/track/current
GET /api/car/state
GET /api/live/telemetry
GET /api/telemetry/live
GET /api/live/source
```

### Debug De Geometria

```text
GET /api/debug/track-file-manifest
GET /api/debug/kn5-inventory
GET /api/debug/kn5-surface-candidates
GET /api/debug/track-surface-polygon
GET /api/debug/track-edges-from-surface
GET /api/debug/track-geometry-quality
GET /api/debug/track-geometry-cleaned
GET /api/debug/track-visual-geometry
```

### Debug De Pitlane

```text
GET /api/debug/pitlane/current
GET /api/debug/pitlane/overview
GET /api/debug/pitlane/validation-metadata
```

## Caches E Exports

### Track Cache

```text
data/cache/tracks/
```

Cache ativo validado:

```text
data/cache/tracks/vhe_interlagos_gp_kn5_surface_interval_cleaned_geometry.json
```

### Debug

```text
data/debug/
```

Contem:

- inventarios KN5;
- triangulos de superficie;
- componentes;
- boundary loops;
- previews SVG;
- relatorios de largura;
- analises da pitlane;
- diagnosticos de saida da pitlane.

## Variaveis De Configuracao Relevantes

### Telemetria

```text
TELEMETRY_SOURCE=auto|assetto_corsa|replay|mock
ALLOW_REPLAY_FALLBACK=true|false
ASSETTO_CORSA_ROOT=<path>
```

### Geometria Fisica

```text
TRACK_GEOMETRY_CLEANUP_ENABLED=true
TRACK_GEOMETRY_TARGET_SPACING=1.5
TRACK_GEOMETRY_SMOOTHING_WINDOW=5
TRACK_KN5_STRICT_MAIN_TRACK=false
DEBUG_ALLOW_TRAJECTORY_TRACK=false
```

### Geometria Visual

```text
TRACK_VISUAL_GEOMETRY_ENABLED=true
TRACK_VISUAL_RENDER_MODE=ribbon
TRACK_VISUAL_USE_ROAD_ONLY=false
TRACK_VISUAL_WIDTH_MEDIAN_WINDOW=9
TRACK_VISUAL_WIDTH_SMOOTHING_WINDOW=11
TRACK_VISUAL_CENTERLINE_SMOOTHING_ENABLED=true
TRACK_VISUAL_NORMAL_RECOMPUTE=true
```

### Frontend

```text
VITE_MIRROR_MAP_X=true|false
```

O mirror e visual/screen-space.

## Regras Que Nao Devem Ser Quebradas

1. CSV nao e fonte de verdade da pista.
2. DriverTrajectory nao e TrackGeometry.
3. Backend e dono dos calculos espaciais.
4. Frontend renderiza geometria processada.
5. `mapPosition` e a posicao visual real do carro.
6. `projectedPosition` e debug/projecao, nao posicao visual.
7. Pista e carro compartilham `mapX=worldX`, `mapY=-worldZ`.
8. Projecao usa nearest segment, nao porcentagem de progresso.
9. TrackPhysicsGeometry fica fixa enquanto o carro se move.
10. TrackVisualGeometry nao altera fisica.
11. Pitlane atual e debug/export only.
12. PitExitTransitionGeometry nao entra no runtime.

## Como Validar Rapidamente

1. Backend:

```text
GET /api/live/source
```

Esperado em live:

```json
{
  "source": "assetto_corsa",
  "activeTrackReady": true
}
```

2. Track atual:

```text
GET /api/track/current
```

Conferir:

```text
provider = kn5_surface_interval
geometrySource = assetto_corsa_track_files
centerlineCount > 0
closedLoop = true
visualGeometry presente quando habilitado
```

3. Carro:

```text
GET /api/telemetry/live
```

Conferir:

```text
mapPosition muda com o carro real
projectedPosition fica na centerline
lateralOffset muda quando o carro muda lateralmente
```

4. Frontend:

```text
http://127.0.0.1:5173/
```

Conferir:

- carro desenhado por `mapPosition`;
- debug de projecao separado;
- pista visual renderizada por `visualGeometry`;
- fisica aparece apenas se debug ligado;
- pitlane aparece apenas em `Debug > Pit`.

## Estado Atual Da Pitlane

A pitlane esta pronta para validacao humana em overlay/debug.

Ela nao esta pronta para runtime por dois motivos:

1. a saida e estreita e proxima da pista principal;
2. a transicao de merge ainda e apenas candidata debug.

O proximo passo seguro seria validar visualmente:

- `interlagos_pit_exit_core_problem_analysis.svg`;
- `interlagos_maintrack_pit_exit_zone_candidate.svg`;
- `interlagos_pit_exit_transition_geometry.svg`;
- overlay `Debug > Pit > Exit`.

Somente depois disso uma integracao runtime poderia ser planejada.

