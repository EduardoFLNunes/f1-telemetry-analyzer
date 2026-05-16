#!/bin/bash

echo "🏎️  F1 Telemetry Analyzer - Backend"
echo "=================================="

cd backend

# Verificar se venv existe
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativar venv
echo "🔧 Ativando ambiente virtual..."
source venv/bin/activate

# Instalar dependências
echo "📥 Instalando dependências..."
pip install -r requirements.txt

# Rodar servidor
echo ""
echo "🚀 Iniciando servidor FastAPI..."
echo "📍 Backend disponível em: http://localhost:8000"
echo ""
python main.py
