# 🏎️ F1 Telemetry Analyzer - AI Raceline

Sistema completo de análise de telemetria de corrida com IA de raceline ideal baseada em **princípios reais de física e corrida**.

## 🎯 Características

### ✅ CORRETO - Implementação Baseada em Princípios Reais

- **Trackmap gerado EXCLUSIVAMENTE do CSV da pista** (nunca da raceline)
- **IA de raceline baseada em física real**:
  - Velocidade em curva: `v² = μ * g * r` (grip × gravidade × raio)
  - Racing line: Outside → Apex → Outside
  - Apex calculado geometricamente (20-40% da largura interna)
  - Considera curvatura, raio e forças laterais
- **SEM valores mágicos**: Sem scaling 0.96, sem ruído aleatório, sem offsets arbitrários
- **Análise real de performance**: Driving style, track limits, métricas detalhadas
- **✨ NOVO: Captura UDP em tempo real** de F1 2025 e Automobilista 2

### 🚫 Evitado - Implementações Incorretas

❌ Trackmap derivado da raceline  
❌ Raceline automaticamente no "meio da pista"  
❌ Valores mágicos (0.96, ruído aleatório)  
❌ IA que só escala dados sem física  

## 📦 Estrutura do Projeto

```
f1-telemetry-ai/
├── backend/                    # FastAPI Backend
│   ├── main.py                 # API principal
│   ├── core/
│   │   ├── trackmap.py         # Geração de trackmap
│   │   ├── telemetry.py        # Processamento de telemetria
│   │   └── raceline_ai.py      # IA de raceline ideal
│   └── requirements.txt
│
├── frontend/                   # React + Vite Frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── TrackMap.jsx    # Visualização do mapa
│   │   │   ├── TelemetryCharts.jsx
│   │   │   ├── ComparisonPanel.jsx
│   │   │   └── UploadPanel.jsx
│   │   ├── api/
│   │   │   └── client.js       # Cliente API
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── data/                       # Dados de exemplo
│   └── SaoPaulo.csv            # Pista de Interlagos
│
├── README.md
├── .gitignore
├── run-backend.sh              # Script para rodar backend (Linux/Mac)
├── run-frontend.sh             # Script para rodar frontend (Linux/Mac)
├── run-backend.bat             # Script para rodar backend (Windows)
└── run-frontend.bat            # Script para rodar frontend (Windows)
```

## 🚀 Instalação e Execução

### Pré-requisitos

- **Python 3.9+**
- **Node.js 18+** e npm
- Sistema operacional: Windows, Linux ou macOS

### 1️⃣ Backend (FastAPI)

```bash
# Navegar para o diretório do backend
cd backend

# Criar ambiente virtual (opcional mas recomendado)
python -m venv venv

# Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Rodar servidor
python main.py
```

O backend estará rodando em: **http://localhost:8000**

### 2️⃣ Frontend (React + Vite)

```bash
# Navegar para o diretório do frontend (em outro terminal)
cd frontend

# Instalar dependências
npm install

# Rodar aplicação
npm run dev
```

O frontend estará rodando em: **http://localhost:5173**

### 🎮 Uso Rápido (Scripts)

**Linux/Mac:**
```bash
# Terminal 1 - Backend
./run-backend.sh

# Terminal 2 - Frontend
./run-frontend.sh
```

**Windows:**
```cmd
# Terminal 1 - Backend
run-backend.bat

# Terminal 2 - Frontend
run-frontend.bat
```

## 📊 Como Usar

### Passo 1: Carregar Pista

1. Acesse http://localhost:5173
2. Faça upload do CSV da pista (ex: `data/SaoPaulo.csv`)
3. O sistema gerará o trackmap real

**Formato do CSV da Pista:**
```csv
# x_m,y_m,w_tr_right_m,w_tr_left_m
-0.518788,-0.519763,7.241,7.513
0.755319,-5.352122,7.156,7.327
...
```

### Passo 2: Carregar Telemetria

1. Faça upload do CSV de telemetria do jogador
2. O sistema processará automaticamente e gerará a raceline ideal

**Formato do CSV de Telemetria:**
```csv
session_time,lap,pos_x,pos_z,speed,throttle,brake
0.0,1,-123.45,456.78,120,0.85,0.0
0.05,1,-123.50,456.90,125,0.90,0.0
...
```

### Passo 3: Análise

O sistema mostrará:

- **Mapa interativo** com trackmap, raceline do jogador e raceline ideal da IA
- **Comparação de tempos** (player vs IA)
- **Métricas detalhadas**: velocidade, throttle, freio, delta
- **Insights da IA**: sugestões de melhoria baseadas em análise física
- **Driving style**: classificação (agressivo/suave/conservador)
- **Oportunidades de melhoria**: curvas específicas onde ganhar tempo

## 🧠 Como Funciona a IA

### 1. Análise da Pista
- Identifica curvas e retas usando curvatura geométrica
- Calcula apex ideal para cada curva (maximiza raio)
- Determina direção das curvas (esquerda/direita)

### 2. Geração da Raceline Ideal
- **Outside → Apex → Outside**: Princípio clássico de racing line
- Apex posicionado 20-40% da largura interna
- Trajetória suavizada com splines

### 3. Cálculo de Velocidade Ideal
- Baseado em física: `v = √(μ * g * r)`
  - μ = grip factor (1.5-2.0 para F1)
  - g = gravidade (9.81 m/s²)
  - r = raio da curva (1/curvatura)
- Considera limites de aceleração (~1.5g) e frenagem (~4.5g)
- Suaviza transições para serem realistas

### 4. Análise Comparativa
- Compara trajetória do jogador vs ideal
- Identifica áreas de melhoria
- Gera insights acionáveis

## 📝 Estrutura dos Dados

### Track Data (Pista)
```json
{
  "name": "Interlagos",
  "centerline": {"x": [...], "y": [...]},
  "left_edge": {"x": [...], "y": [...]},
  "right_edge": {"x": [...], "y": [...]},
  "curvatures": [...],
  "corners": [
    {
      "corner_id": 1,
      "apex_idx": 123,
      "direction": "left",
      "curvature": 0.015
    }
  ],
  "length_meters": 4309.0
}
```

### Telemetry Data (Jogador)
```json
{
  "best_lap_time": 72.345,
  "best_lap_number": 3,
  "best_lap_data": {
    "x": [...],
    "z": [...],
    "speed": [...],
    "throttle": [...],
    "brake": [...],
    "distance": [...]
  },
  "metrics": {
    "avg_speed": 185.5,
    "max_speed": 310.2,
    "full_throttle_pct": 45.3
  },
  "driving_style": {
    "classification": "suave",
    "description": "Transições graduais..."
  }
}
```

### AI Raceline (IA)
```json
{
  "trajectory": {"x": [...], "z": [...], "distance": [...]},
  "speed": [...],
  "throttle": [...],
  "brake": [...],
  "estimated_time": 70.123,
  "insights": [
    "Velocidade média 5.2 km/h abaixo do ideal...",
    "Tente levar mais velocidade nas curvas..."
  ],
  "improvements": [
    {
      "corner": 1,
      "current": 145.0,
      "target": 160.0,
      "gain": 15.0,
      "suggestion": "Curva 1: Carregue 15 km/h a mais"
    }
  ]
}
```

## 🔧 API Endpoints

### Backend (FastAPI)

**Base URL:** `http://localhost:8000`

#### Upload Track
```http
POST /api/upload/track
Content-Type: multipart/form-data
Body: file (CSV)
```

#### Upload Telemetry
```http
POST /api/upload/telemetry
Content-Type: multipart/form-data
Body: file (CSV)
```

#### Get Track Data
```http
GET /api/data/track
```

#### Get Telemetry Data
```http
GET /api/data/telemetry
```

#### Get AI Raceline
```http
GET /api/data/ai-raceline
```

#### Get Full Comparison
```http
GET /api/data/comparison
```

## 🎨 Tecnologias Utilizadas

### Backend
- **FastAPI**: Framework web moderno e rápido
- **Pandas**: Manipulação de dados
- **NumPy**: Cálculos matemáticos e vetoriais
- **SciPy**: Interpolação e otimização

### Frontend
- **React 18**: Framework UI
- **Vite**: Build tool rápido
- **Plotly.js**: Visualizações interativas
- **Axios**: Cliente HTTP
- **Lucide React**: Ícones

## 🔬 Princípios Científicos

### Física das Corridas
1. **Força Lateral Máxima**: `F_lat = m * v² / r`
2. **Velocidade em Curva**: `v_max = √(μ * g * r)`
3. **Raio Ótimo**: Maximizar raio = maximizar velocidade
4. **Momentum**: Conservar velocidade ao longo da pista

### Geometria da Pista
1. **Vetor Tangente**: Direção da trajetória
2. **Vetor Normal**: Perpendicular à trajetória
3. **Curvatura**: `κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)`
4. **Raio**: `r = 1 / κ`

## 🐛 Troubleshooting

### Backend não inicia
```bash
# Verificar instalação do Python
python --version

# Reinstalar dependências
pip install --upgrade -r requirements.txt
```

### Frontend não compila
```bash
# Limpar cache e reinstalar
rm -rf node_modules package-lock.json
npm install
```

### CORS Error
Certifique-se de que:
1. Backend está rodando em `http://localhost:8000`
2. Frontend está rodando em `http://localhost:5173`
3. Ambos estão rodando simultaneamente

### CSV Inválido
Verifique que:
- CSV da pista tem colunas: `# x_m, y_m, w_tr_right_m, w_tr_left_m`
- CSV de telemetria tem: `session_time, lap, pos_x, pos_z, speed, throttle, brake`
- Arquivos estão em UTF-8

## 📄 Licença

Este projeto é um exemplo educacional de análise de telemetria com IA.

## 👨‍💻 Desenvolvimento

### Adicionar Nova Pista

1. Coloque o CSV da pista em `data/`
2. Formato obrigatório: `x_m, y_m, w_tr_right_m, w_tr_left_m`
3. Faça upload pela interface

### Melhorar a IA

A IA está em `backend/core/raceline_ai.py`. Áreas de melhoria:

- Ajustar `GRIP_FACTOR` (1.5-2.0)
- Modificar posição do apex (20-40% default)
- Refinar limites de aceleração/frenagem
- Adicionar análise de setores

### Customizar Frontend

Estilos estão nos arquivos `.css` de cada componente. Cores principais:

- Purple/AI: `#9d4edd`, `#c77dff`
- Player: `#ffd000`
- Green: `#00e676`
- Red: `#e8192c`

## 🙏 Agradecimentos

Baseado em princípios de:
- Física de corridas de motorsport
- Geometria diferencial
- Análise de telemetria profissional
- FastF1 (inspiração de estrutura de dados)

---

**Desenvolvido com foco em precisão física e análise real de performance.**
