# 🏎️ F1 TELEMETRY ANALYZER - AI RACELINE
## Sistema Completo de Análise de Telemetria com IA

**Versão:** 1.0.0  
**Status:** ✅ Completo e Pronto para Uso  
**Tamanho:** ~54KB (compactado)

---

## 📦 CONTEÚDO DO PROJETO

### Estrutura de Arquivos (26 arquivos principais)

```
f1-telemetry-ai/
│
├── 📖 DOCUMENTAÇÃO
│   ├── README.md           ← Documentação completa (4.600 palavras)
│   ├── QUICKSTART.md       ← Guia de início rápido
│   └── ARCHITECTURE.md     ← Arquitetura técnica do sistema
│
├── 🐍 BACKEND (FastAPI)
│   ├── main.py                     ← API principal (7 endpoints)
│   ├── requirements.txt            ← Dependências Python
│   └── core/
│       ├── trackmap.py             ← Geração de trackmap (geometria)
│       ├── telemetry.py            ← Processamento de telemetria
│       └── raceline_ai.py          ← IA de raceline (física real)
│
├── ⚛️ FRONTEND (React + Vite)
│   ├── package.json                ← Dependências Node.js
│   ├── vite.config.js              ← Configuração build
│   ├── index.html                  ← HTML base
│   └── src/
│       ├── main.jsx                ← Entry point
│       ├── App.jsx                 ← Componente principal
│       ├── api/client.js           ← Cliente HTTP
│       └── components/
│           ├── TrackMap.jsx        ← Mapa 2D interativo
│           ├── ComparisonPanel.jsx ← Métricas comparativas
│           ├── TelemetryCharts.jsx ← Gráficos de dados
│           └── UploadPanel.jsx     ← Upload de CSVs
│
├── 📊 DADOS DE EXEMPLO
│   ├── SaoPaulo.csv                ← Pista de Interlagos (864 pontos)
│   └── example_telemetry.csv       ← Telemetria de exemplo
│
├── 🚀 SCRIPTS DE EXECUÇÃO
│   ├── run-backend.sh              ← Linux/Mac backend
│   ├── run-frontend.sh             ← Linux/Mac frontend
│   ├── run-backend.bat             ← Windows backend
│   └── run-frontend.bat            ← Windows frontend
│
└── ⚙️ CONFIGURAÇÃO
    └── .gitignore                  ← Arquivos ignorados no Git
```

---

## ⚡ EXECUÇÃO RÁPIDA (2 COMANDOS)

### Windows
```cmd
# Terminal 1 - Backend
run-backend.bat

# Terminal 2 - Frontend
run-frontend.bat
```

### Linux/macOS
```bash
# Terminal 1 - Backend
./run-backend.sh

# Terminal 2 - Frontend
./run-frontend.sh
```

### Acesso
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

---

## 🎯 FUNCIONALIDADES PRINCIPAIS

### ✅ Backend (FastAPI)
- [x] Upload de CSV da pista
- [x] Upload de CSV de telemetria
- [x] Geração de trackmap real (geometria vetorial)
- [x] Processamento de telemetria (limpeza + validação)
- [x] IA de raceline ideal (física real, sem valores mágicos)
- [x] Cálculo de métricas de performance
- [x] Análise de driving style
- [x] Insights acionáveis
- [x] API RESTful completa

### ✅ Frontend (React)
- [x] Interface moderna e responsiva
- [x] Upload drag & drop de CSVs
- [x] Mapa 2D interativo (Plotly.js)
- [x] Visualização de trackmap + raceline player + raceline IA
- [x] Painel de comparação de tempos
- [x] Gráficos de velocidade, throttle, freio, delta
- [x] Exibição de insights da IA
- [x] Animação de volta
- [x] UX fluida com feedback visual

---

## 🧠 TECNOLOGIA DA IA

### Princípios Físicos REAIS (não valores mágicos)

1. **Velocidade em Curva**
   ```
   v_max = √(μ × g × r)
   
   onde:
   μ = grip factor (1.5-2.0 para F1)
   g = gravidade (9.81 m/s²)
   r = raio da curva (1/curvatura)
   ```

2. **Racing Line Clássica**
   ```
   Outside → Apex → Outside
   
   - Apex = ponto que maximiza raio
   - Posicionado 20-40% da largura interna
   ```

3. **Curvatura Geométrica**
   ```
   κ = |x'y'' - y'x''| / (x'² + y'²)^(3/2)
   ```

4. **Limites Físicos**
   ```
   Aceleração máxima: ~1.5g (14.7 m/s²)
   Frenagem máxima: ~4.5g (44.1 m/s²)
   ```

### 🚫 NÃO Usamos
- ❌ Scaling arbitrário (0.96)
- ❌ Ruído aleatório
- ❌ Raceline no "meio da pista"
- ❌ Valores mágicos
- ❌ Trackmap derivado da raceline

---

## 📋 PRÉ-REQUISITOS

- **Python 3.9+**
- **Node.js 18+** e npm
- **Sistema**: Windows, Linux ou macOS

---

## 📊 FORMATOS DE DADOS

### CSV da Pista
```csv
# x_m,y_m,w_tr_right_m,w_tr_left_m
-0.52,-0.52,7.24,7.51
0.76,-5.35,7.16,7.33
...
```

### CSV de Telemetria
```csv
session_time,lap,pos_x,pos_z,speed,throttle,brake
0.000,1,-0.52,-0.52,85,0.75,0.0
0.050,1,0.75,-5.35,95,0.85,0.0
...
```

---

## 🎨 DESIGN E UX

### Paleta de Cores
- **Background**: `#05060f` (dark blue)
- **Purple/IA**: `#9d4edd`, `#c77dff`
- **Player**: `#ffd000` (yellow)
- **Success**: `#00e676` (green)
- **Danger**: `#e8192c` (red)

### Fontes
- **Títulos/Dados**: Orbitron (monospace futurista)
- **Corpo**: Inter (sans-serif moderno)

---

## 📚 DOCUMENTAÇÃO

### Arquivos Incluídos
1. **README.md**: Documentação completa (4.600 palavras)
2. **QUICKSTART.md**: Guia de início rápido
3. **ARCHITECTURE.md**: Arquitetura técnica
4. **INDEX.md**: Este arquivo (visão geral)

### API Endpoints (7 rotas)
```
GET  /                      → Health check
POST /api/upload/track      → Upload CSV pista
POST /api/upload/telemetry  → Upload CSV telemetria
GET  /api/data/track        → Obter trackmap
GET  /api/data/telemetry    → Obter telemetria processada
GET  /api/data/ai-raceline  → Obter raceline IA
GET  /api/data/comparison   → Obter comparação completa
```

---

## 🔧 TROUBLESHOOTING

### Porta em Uso
```bash
# Backend (8000)
lsof -ti:8000 | xargs kill -9  # Linux/Mac
netstat -ano | findstr :8000   # Windows

# Frontend (5173)
lsof -ti:5173 | xargs kill -9  # Linux/Mac
netstat -ano | findstr :5173   # Windows
```

### Reinstalar Dependências
```bash
# Backend
cd backend
pip install --upgrade -r requirements.txt

# Frontend
cd frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 📈 ROADMAP FUTURO

Possíveis melhorias:
- [ ] Suporte a múltiplas pistas
- [ ] Banco de dados (PostgreSQL)
- [ ] Autenticação de usuários
- [ ] Histórico de voltas
- [ ] Comparação entre pilotos
- [ ] Export de relatórios PDF
- [ ] Machine Learning avançado

---

## 📄 LICENÇA

Projeto educacional de código aberto.

---

## 🙏 CRÉDITOS

Desenvolvido com foco em:
- Física de corridas real
- Geometria diferencial
- Análise de telemetria profissional
- Princípios de engenharia de software

**Inspirações:**
- FastF1 (estrutura de dados)
- Motorsport profissional (princípios físicos)
- Análise de telemetria F1

---

## 📞 SUPORTE

- 📖 Leia README.md completo
- 🚀 Siga QUICKSTART.md
- 🏗️ Consulte ARCHITECTURE.md
- 🔍 API Docs em /docs

---

**Status do Projeto:** ✅ COMPLETO E PRONTO PARA USO

**Última Atualização:** Abril 2026

---

Desenvolvido com ❤️ para análise precisa de telemetria de corrida
