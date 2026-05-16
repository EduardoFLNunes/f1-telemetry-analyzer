@echo off
echo.
echo 🏎️  F1 Telemetry Analyzer - Backend
echo ==================================
echo.

cd backend

REM Verificar se venv existe
if not exist "venv\" (
    echo 📦 Criando ambiente virtual...
    python -m venv venv
)

REM Ativar venv
echo 🔧 Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Instalar dependências
echo 📥 Instalando dependências...
pip install -r requirements.txt

REM Rodar servidor
echo.
echo 🚀 Iniciando servidor FastAPI...
echo 📍 Backend disponível em: http://localhost:8000
echo.
python main.py
