#!/bin/bash

echo "🏎️  F1 Telemetry Analyzer - Frontend"
echo "=================================="

cd frontend

# Verificar se node_modules existe
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependências..."
    npm install
fi

# Rodar aplicação
echo ""
echo "🚀 Iniciando aplicação React..."
echo "📍 Frontend disponível em: http://localhost:5173"
echo ""
npm run dev
