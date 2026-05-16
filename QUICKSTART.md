# 🚀 Guia de Início Rápido

## Execução Imediata (2 Comandos)

### Linux/macOS

```bash
# Terminal 1 - Backend
./run-backend.sh

# Terminal 2 - Frontend (abrir outro terminal)
./run-frontend.sh
```

### Windows

```cmd
# Terminal 1 - Backend
run-backend.bat

# Terminal 2 - Frontend (abrir outro terminal)
run-frontend.bat
```

## Acesso

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Teste Rápido

1. Abra http://localhost:5173
2. Upload `data/SaoPaulo.csv` (pista)
3. Upload `data/example_telemetry.csv` (telemetria de exemplo)
4. Visualize a análise!

## Arquivos de Teste Incluídos

- **data/SaoPaulo.csv**: Pista de Interlagos (Brasil)
- **data/example_telemetry.csv**: Telemetria de exemplo

## Problemas Comuns

### "Port already in use"

**Backend (porta 8000):**
```bash
# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Frontend (porta 5173):**
```bash
# Linux/Mac
lsof -ti:5173 | xargs kill -9

# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F
```

### Python não encontrado

```bash
# Verificar instalação
python --version
# ou
python3 --version

# Se não estiver instalado, baixar em:
# https://www.python.org/downloads/
```

### Node não encontrado

```bash
# Verificar instalação
node --version

# Se não estiver instalado, baixar em:
# https://nodejs.org/
```

## Estrutura Visual

```
Aplicação Web
├─ Header: Logo "RACELINE AI"
├─ Main
│  ├─ Mapa (esquerda): TrackMap 3D interativo
│  └─ Sidebar (direita)
│     ├─ Comparação de Tempos (Player vs IA)
│     ├─ Métricas de Performance
│     ├─ Insights da IA
│     ├─ Oportunidades de Melhoria
│     ├─ Estilo de Pilotagem
│     └─ Gráficos (Velocidade, Throttle, Freio, Delta)
└─ Footer: Informações do sistema
```

## Fluxo de Uso

1. **Upload Track CSV** → Sistema gera trackmap
2. **Upload Telemetry CSV** → Sistema processa e gera IA
3. **Visualização** → Mapa + Gráficos + Insights
4. **Análise** → Identificar onde melhorar
5. **Repetir** → Carregar nova telemetria e comparar

## Suporte

- README.md completo com documentação detalhada
- Código documentado em cada arquivo
- API docs automática em `/docs`
