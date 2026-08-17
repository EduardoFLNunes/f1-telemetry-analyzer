# 🏎️ Automobilista Telemetria — Telemetria Assistida para Simulação Automobilística

Trabalho de Conclusão de Curso: um sistema de telemetria assistida para simulação
automobilística, usando **Assetto Corsa** como simulador e o autódromo de
**Interlagos** como ambiente de testes.

O sistema lê a telemetria do carro do jogador diretamente da memória
compartilhada do Assetto Corsa em tempo real, recebe a telemetria dos
oponentes por UDP, reconstrói a geometria da pista a partir dos arquivos 3D
do próprio jogo (KN5), e oferece análise de racing line, comparação por
microsetor e feedback assistido de pilotagem pós-volta — tudo através de um
aplicativo desktop (Electron) ou de um dashboard web.

> Este README descreve a arquitetura atual do projeto (Phase 15.1). Ele **não**
> usa upload de CSV nem pistas geradas manualmente — esse fluxo existia nas
> fases iniciais do projeto e foi substituído pela captura em tempo real.

## 🎯 O que o sistema faz

- **Telemetria em tempo real do jogador**: lê posição, velocidade, inputs e
  física do carro direto da memória compartilhada do Assetto Corsa (sem
  arquivos intermediários).
- **Telemetria dos oponentes**: recebe dados de outros carros na pista via um
  exportador Python que roda dentro do próprio Assetto Corsa
  (`tools/assetto_opponents_exporter/`), enviado por UDP para o backend.
- **Geometria de pista real**: a pista (centerline, bordas, largura,
  curvatura) é reconstruída a partir dos arquivos `.kn5`/`fast_lane.ai` do
  Assetto Corsa — não de um CSV nem da trajetória do jogador.
- **Racing Line e análise comparativa**: calcula a linha ideal por microsetor
  e compara contra a volta do jogador, com base física (não em valores
  mágicos).
- **Análise assistida pós-volta**: classifica erros de pilotagem (frenagem,
  entrada/saída de curva, uso de acelerador) comparando com uma volta de
  referência e com dados reais externos (FastF1) para Interlagos.
- **Gravação e replay de sessões**: sessões e voltas são persistidas
  (DuckDB) e podem ser reproduzidas depois, offline, no mesmo mapa.
- **Diagnóstico de qualidade de dados**: monitoramento de confiabilidade da
  telemetria do jogador, dos oponentes (UDP) e validação da pista/volta.
- **Aplicativo desktop**: empacotado com Electron + PyInstaller + instalador
  NSIS para Windows, com autostart do backend e diagnóstico de runtime.

## 🏗️ Arquitetura resumida

```
Assetto Corsa (memória compartilhada + exportador UDP de oponentes)
        │
        ▼
Backend (FastAPI) ── WebSocket + REST ──▶ Frontend (React + Vite + TS)
        │                                        │
        ▼                                        ▼
Cache/DB local (DuckDB, cache de pista)   Electron shell (app desktop)
```

Veja o detalhamento completo em [ARCHITECTURE.md](ARCHITECTURE.md).

## 📦 Estrutura do Projeto

```
f1-telemetry-analyzer/
├── backend/                    # FastAPI backend
│   ├── main.py                  # API principal (~60 endpoints)
│   ├── desktop_backend_runner.py # entry point usado no build PyInstaller
│   ├── core/
│   │   ├── assetto_adapter.py, ac_shared_memory.py, assetto_shared_memory_gate.py
│   │   ├── live/                # runtime de telemetria do jogador (WS + polling)
│   │   ├── opponents/           # runtime de telemetria dos oponentes (UDP)
│   │   ├── geometry/, kn5/      # reconstrução da pista a partir dos arquivos do jogo
│   │   ├── racing_line_analysis.py, comparison_analysis.py, car_physics.py
│   │   ├── assisted_analysis/   # feedback de pilotagem pós-volta
│   │   ├── data_quality/        # monitoramento de confiabilidade
│   │   ├── external_references/ # referências reais (FastF1) para Interlagos
│   │   ├── recording/           # gravação e persistência de sessões/voltas
│   │   └── websocket_server.py
│   ├── packaging/               # build do executável (PyInstaller)
│   └── tests/                    # 245 testes automatizados (unittest)
│
├── frontend/                    # React + Vite (migração JS → TS em andamento)
│   └── src/
│       ├── components/           # painéis (Racing Line, Comparação, Análise Assistida...)
│       ├── components/map/       # renderização 2D em canvas do mapa da pista
│       ├── test/                 # canvas de mentira usado pelos testes (Vitest)
│       ├── store/                # estado global (Zustand)
│       └── hooks/useTelemetryWS.ts # cliente WebSocket
│
├── desktop/                     # Shell Electron + empacotamento (electron-builder/NSIS)
│   ├── main.js, preload.js
│   └── dist/                     # instaladores gerados (.exe)
│
├── tools/
│   ├── assetto_opponents_exporter/ # plugin Python que roda dentro do Assetto Corsa
│   ├── runtime_performance_probe.py
│   └── send_fake_opponents_udp.py
│
├── scripts/                     # scripts de geração/validação da geometria de Interlagos
├── docs/                        # notas técnicas por fase (empacotamento, performance)
└── data/                        # cache de pista, fixtures de teste, referências externas
```

## 🚀 Como executar

### Requisitos

- **Assetto Corsa** instalado (Steam) — necessário para telemetria real do
  jogador e dos oponentes. Sem o jogo aberto, o backend ainda sobe, mas fica
  em modo de espera (`waiting`/mock).
- **Python 3.9+**
- **Node.js 18+** e npm
- Windows (o empacotamento desktop/instalador é Windows-only hoje; backend e
  frontend também rodam em Linux/macOS em modo desenvolvimento)

### Opção 1 — Aplicativo desktop (recomendado)

Instalador pronto (gerado por fase) em `desktop/dist/*.exe`, ou para
desenvolver o shell Electron:

```bash
cd desktop
npm install
npm run desktop:dev
```

Isso abre o Electron carregando o Vite dev server. Para simular o
empacotamento final sem instalar:

```bash
cd frontend && npm run build
cd ../desktop && npm run desktop:prod
```

Detalhes completos de build/instalador em
[docs/phase12_desktop_packaging_plan.md](docs/phase12_desktop_packaging_plan.md).

### Opção 2 — Backend e frontend manualmente (desenvolvimento)

```bash
# Terminal 1 — Backend
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python main.py                # http://localhost:8000 (docs em /docs)

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Os scripts legados `run-backend.bat/.sh` e `run-frontend.bat/.sh` continuam
funcionando e fazem exatamente isso.

### Configurar o Assetto Corsa

1. Abra o Assetto Corsa e carregue Interlagos (`ks_interlagos`).
2. Para telemetria dos **oponentes**, copie o plugin Python
   `tools/assetto_opponents_exporter/` para
   `<Assetto Corsa>/apps/python/ac_opponents_exporter/` e ative-o no menu de
   apps do jogo (envia dados por UDP em `127.0.0.1:8765`).
3. A telemetria do **jogador** é lida automaticamente via memória
   compartilhada — não precisa de plugin.

Guia detalhado em [docs/phase12_assetto_plugin_setup.md](docs/phase12_assetto_plugin_setup.md).

## 🧪 Testes

```bash
cd backend
python -m unittest discover -s tests
```

245 testes cobrem análise de racing line, comparação, qualidade de dados,
gravação de sessão, física do carro, telemetria de oponentes e o gate de
memória compartilhada.

```bash
cd frontend
npm test          # 103 testes (Vitest)
npm run build     # build de produção
npx tsc --noEmit  # checagem de tipos (não está em CI ainda — rodar manualmente)
```

Os testes de frontend cobrem a matemática que o usuário enxerga: a câmera da
fita 3D (altura sobe na tela, o chão não inclina junto, uma volta da câmera por
volta da pista), a câmera follow do mapa (segue sem girar, centraliza o carro),
o rastro e a leitura de transmissão, o desenho do mapa (ordem das camadas de
tinta, preenchimento even-odd do asfalto, afinamento no zoom out, mini-mapa) e o
replay offline de sessões gravadas — este último roda inteiro sem o Assetto
Corsa aberto.

## 🔧 Principais endpoints da API

Base local: `http://127.0.0.1:8000` (docs interativas em `/docs`).

```
GET  /api/health, /api/runtime/status
GET  /api/live/telemetry, /api/live/opponents, /api/live/player-physics
GET  /api/live/racing-line, /api/live/comparison, /api/live/coach
POST /api/recording/start, /api/recording/stop
GET  /api/sessions, /api/sessions/{id}/laps, /api/laps/{lap_id}/replay
GET  /api/assisted-analysis/laps, /api/analysis/assisted/lap/{lapId}
GET  /api/validation/data-quality, /api/validation/track
GET  /api/references/external  (referências FastF1 para Interlagos)
```

## 🎨 Tecnologias

**Backend:** FastAPI, Pandas, NumPy, SciPy, DuckDB, Pydantic, Uvicorn,
FastF1 (referências externas), PyInstaller (empacotamento).

**Frontend:** React 18, TypeScript (migração de JS em andamento), Vite,
Zustand, Plotly.js / Recharts, Axios, Lucide React.

**Desktop:** Electron, electron-builder (instalador NSIS).

## 📝 Status do projeto

O sistema está na Phase 15.1 (diagnóstico e otimização de amostragem em
tempo real). O empacotamento desktop está validado como instalador real do
Windows. Pontos conhecidos em aberto:

- Migração do frontend de JavaScript para TypeScript ainda incompleta
  (alguns componentes `.jsx`/`.js` convivem com `.tsx`/`.ts`).
- Não há CI configurado; testes e build são executados manualmente.
- `BRANCH_STATUS.md` documenta branches antigas com trabalho não integrado —
  não fazer merge direto delas sem revisão.

## 🙏 Contexto acadêmico

Projeto desenvolvido como Trabalho de Conclusão de Curso, com foco em
telemetria assistida e análise de performance baseada em física real
(sem valores mágicos ou escalonamentos arbitrários), usando Interlagos como
ambiente de validação.
