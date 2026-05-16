# 🏗️ Arquitetura do Sistema

## Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                      USUÁRIO / BROWSER                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   FRONTEND (React + Vite)                    │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │UploadPanel │  │  TrackMap  │  │ ComparisonPanel      │  │
│  │            │  │  (Plotly)  │  │ + TelemetryCharts    │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
│                         │                                     │
│                    API Client (Axios)                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ REST API (JSON)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI)                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    main.py                           │   │
│  │  • POST /api/upload/track                           │   │
│  │  • POST /api/upload/telemetry                       │   │
│  │  • GET  /api/data/track                             │   │
│  │  • GET  /api/data/telemetry                         │   │
│  │  • GET  /api/data/ai-raceline                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                         │                                     │
│  ┌──────────────┬──────────────┬─────────────────────┐     │
│  │              │              │                       │     │
│  ▼              ▼              ▼                       │     │
│  TrackMap    Telemetry    RacelineAI                 │     │
│  Generator   Processor    (Física Real)              │     │
│  │            │            │                           │     │
│  │            │            │                           │     │
│  • Geometria • Valida    • Calcula apex              │     │
│  • Bordas    • Limpa     • Outside→Apex→Outside      │     │
│  • Curvaturas• Melhor    • v² = μ*g*r                │     │
│  • Corners     volta     • Splines                    │     │
│              • Métricas  • Insights                   │     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    DADOS (CSV Files)                         │
│  • Track CSV      (x, y, width_left, width_right)          │
│  • Telemetry CSV  (time, lap, pos, speed, inputs)          │
└─────────────────────────────────────────────────────────────┘
```

## Fluxo de Dados

### 1. Upload Track

```
User → Frontend → POST /api/upload/track
                    ↓
                TrackMapGenerator
                    ↓
                • Lê CSV
                • Calcula bordas (geometria vetorial)
                • Identifica curvas (curvatura)
                • Gera trackmap completo
                    ↓
                Retorna TrackData
                    ↓
                Frontend renderiza mapa
```

### 2. Upload Telemetry

```
User → Frontend → POST /api/upload/telemetry
                    ↓
                TelemetryProcessor
                    ↓
                • Valida dados
                • Identifica melhor volta
                • Calcula métricas
                • Analisa driving style
                    ↓
                RacelineAI
                    ↓
                • Calcula apex ideal (geometria)
                • Gera raceline (outside→apex→outside)
                • Calcula velocidades (física)
                • Gera insights
                    ↓
                Retorna TelemetryData + AIRaceline
                    ↓
                Frontend renderiza comparação
```

## Componentes Principais

### Backend Core

1. **trackmap.py**
   - Input: CSV da pista
   - Output: Geometria completa da pista
   - Tecnologia: NumPy (vetores), Pandas

2. **telemetry.py**
   - Input: CSV de telemetria
   - Output: Dados limpos + métricas
   - Tecnologia: Pandas, NumPy

3. **raceline_ai.py**
   - Input: TrackData + TelemetryData
   - Output: Raceline ideal + insights
   - Tecnologia: NumPy, SciPy (splines)

### Frontend Components

1. **TrackMap.jsx**
   - Renderiza mapa 2D interativo
   - Visualiza track + player + IA
   - Tecnologia: Plotly.js

2. **ComparisonPanel.jsx**
   - Mostra métricas comparativas
   - Exibe insights da IA
   - Tecnologia: React

3. **TelemetryCharts.jsx**
   - Gráficos de velocidade/throttle/brake
   - Delta tempo
   - Tecnologia: Plotly.js

4. **UploadPanel.jsx**
   - Drag & drop de CSVs
   - Validação de formato
   - Tecnologia: React

## Princípios de Design

### Backend
- **Separação de responsabilidades**: Cada módulo tem função única
- **Física real**: Sem valores mágicos
- **Validação**: Todos os inputs são validados
- **API RESTful**: Endpoints claros e padronizados

### Frontend
- **Componentização**: UI modular e reutilizável
- **Estado centralizado**: Gerenciamento limpo de dados
- **UX fluida**: Feedback visual em todas as ações
- **Responsivo**: Funciona em diferentes tamanhos de tela

## Tecnologias e Bibliotecas

### Backend
```
FastAPI      → Framework web assíncrono
Pandas       → Manipulação de dados tabulares
NumPy        → Cálculos matemáticos e vetoriais
SciPy        → Interpolação (splines) e otimização
Pydantic     → Validação de dados
Uvicorn      → Servidor ASGI
```

### Frontend
```
React        → Framework UI
Vite         → Build tool moderno
Plotly.js    → Gráficos interativos
Axios        → Cliente HTTP
Lucide React → Ícones
```

## Segurança

- CORS configurado para desenvolvimento local
- Validação de tipos de arquivo
- Sanitização de inputs
- Limites de tamanho de arquivo

## Performance

- Backend assíncrono (FastAPI)
- Frontend com Virtual DOM (React)
- Gráficos renderizados no cliente (Plotly)
- Cache de cálculos onde possível

## Escalabilidade Futura

Possíveis melhorias:
- [ ] Suporte a múltiplas pistas simultâneas
- [ ] Banco de dados (PostgreSQL)
- [ ] Cache distribuído (Redis)
- [ ] Autenticação de usuários
- [ ] Histórico de voltas
- [ ] Comparação entre pilotos
- [ ] Export de relatórios PDF
- [ ] Machine Learning para predições
