# 🎮 Captura UDP de Telemetria em Tempo Real

## 📡 Visão Geral

O sistema agora inclui captura automática de telemetria diretamente dos jogos **F1 2025** e **Automobilista 2** via UDP.

## 🎯 Jogos Suportados

- **F1 2025**: Porta UDP 20777
- **Automobilista 2**: Porta UDP 5606

## 🚀 Como Usar

### Método 1: Via API (Recomendado)

```bash
# 1. Iniciar backend
cd backend
python main.py

# 2. Em outro terminal, iniciar captura
curl -X POST "http://localhost:8000/api/capture/start?game=F1-25"

# 3. Jogar o jogo (a telemetria será capturada automaticamente)

# 4. Parar captura e salvar CSV
curl -X POST "http://localhost:8000/api/capture/stop"

# 5. Verificar status
curl "http://localhost:8000/api/capture/status"
```

### Método 2: Script Standalone

```bash
cd backend/core
python udp_capture.py F1-25
# ou
python udp_capture.py AMS2
```

Pressione **CTRL+C** para parar e salvar o CSV.

## ⚙️ Configuração do Jogo

### F1 2025

1. Abra **Configurações → Telemetria**
2. Ative **UDP Telemetry**
3. Porta: **20777**
4. Formato: **2025**
5. IP: **127.0.0.1** (localhost)

### Automobilista 2

1. Abra **Configurações → Plugins**
2. Ative **Shared Memory**
3. Porta UDP: **5606**

## 📊 Dados Capturados

A cada pacote UDP, o sistema captura:

- **Tempo da sessão** (session_time)
- **Volta atual** (lap)
- **Posição X, Y, Z** (pos_x, pos_y, pos_z)
- **Velocidade** (speed em km/h)
- **Throttle** (acelerador 0.0-1.0)
- **Brake** (freio 0.0-1.0)

## 📁 Onde os CSVs são Salvos

```
data/telemetry_sessions/
├── telemetria_F1-25_1_21-04-2026_14-30.csv
├── telemetria_F1-25_2_21-04-2026_15-45.csv
└── telemetria_AMS2_1_21-04-2026_16-20.csv
```

## 🔄 Fluxo de Trabalho Completo

### 1. Configurar Jogo
```
Ativar UDP Telemetry no jogo
```

### 2. Iniciar Captura
```bash
curl -X POST "http://localhost:8000/api/capture/start?game=F1-25"
```

### 3. Jogar
```
Completar voltas no jogo
```

### 4. Parar e Salvar
```bash
curl -X POST "http://localhost:8000/api/capture/stop"
```

### 5. Carregar Track
```
Upload CSV da pista no frontend
```

### 6. Carregar Telemetria Capturada
```
Upload CSV salvo em data/telemetry_sessions/
```

### 7. Analisar
```
Visualizar raceline IA vs sua performance!
```

## 🛡️ Segurança

- ✅ Captura roda em thread separada (não bloqueia API)
- ✅ Timeout de 1s por pacote (não trava)
- ✅ Validação de tamanho de pacote
- ✅ Tratamento de erros robusto
- ✅ Logs detalhados de captura

## 📊 Monitoramento em Tempo Real

### Verificar Status
```bash
curl "http://localhost:8000/api/capture/status"
```

**Resposta:**
```json
{
  "running": true,
  "game": "F1-25",
  "port": 20777,
  "points_captured": 1250,
  "current_lap": 3,
  "current_speed": 285
}
```

## 🐛 Troubleshooting

### "Nenhum dado recebido"

1. Verificar se UDP Telemetry está **ativado** no jogo
2. Confirmar porta correta (20777 para F1 2025)
3. Verificar firewall não está bloqueando porta UDP

### "Porta já em uso"

```bash
# Linux/Mac
lsof -ti:20777 | xargs kill -9

# Windows
netstat -ano | findstr :20777
taskkill /PID <PID> /F
```

### "CSV vazio após captura"

- Certifique-se de ter completado **pelo menos uma volta**
- Pacotes de telemetria só são salvos quando o jogo envia dados de posição (packet ID 0)

## 💡 Dicas

1. **Melhor qualidade:** Complete 3-5 voltas antes de parar
2. **Dados limpos:** Evite pausar o jogo durante captura
3. **Comparação:** Capture múltiplas sessões para comparar evolução
4. **Backup:** CSVs são salvos automaticamente com timestamp

## 🎯 Exemplo Completo

```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Iniciar captura
curl -X POST "http://localhost:8000/api/capture/start?game=F1-25"

# Aguardar resposta
{
  "status": "success",
  "message": "Captura UDP iniciada para F1-25",
  "data": {
    "running": true,
    "game": "F1-25",
    "port": 20777,
    "points_captured": 0
  }
}

# Jogar o jogo (completar voltas)
# ...

# Verificar progresso
curl "http://localhost:8000/api/capture/status"

# Parar e salvar
curl -X POST "http://localhost:8000/api/capture/stop"

{
  "status": "success",
  "message": "Captura finalizada e CSV salvo",
  "data": {
    "csv_path": "data/telemetry_sessions/telemetria_F1-25_1_21-04-2026_14-30.csv",
    "points_captured": 3542
  }
}
```

---

**🎮 Agora você pode capturar telemetria real enquanto joga!**
