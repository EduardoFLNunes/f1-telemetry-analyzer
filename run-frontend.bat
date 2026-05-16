@echo off
echo.
echo 🏎️  F1 Telemetry Analyzer - Frontend
echo ==================================
echo.

cd frontend

REM Verificar se node_modules existe
if not exist "node_modules\" (
    echo 📦 Instalando dependências...
    npm install
)

REM Rodar aplicação
echo.
echo 🚀 Iniciando aplicação React...
echo 📍 Frontend disponível em: http://localhost:5173
echo.
npm run dev
