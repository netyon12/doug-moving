@echo off
REM ========================================
REM   DOUG MOVING - Inicializacao Automatica
REM ========================================

echo.
echo ========================================
echo   DOUG MOVING
echo   Ambiente de Desenvolvimento
echo ========================================
echo.

REM Verificar se venv existe
if not exist "venv\Scripts\python.exe" (
    echo ❌ Ambiente virtual nao encontrado!
    echo.
    echo Execute primeiro:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Ativar ambiente virtual
echo [1/3] Ativando ambiente virtual...
call venv\Scripts\activate.bat

if errorlevel 1 (
    echo ❌ Erro ao ativar ambiente virtual!
    echo.
    echo Tente executar como Administrador:
    echo   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    echo.
    pause
    exit /b 1
)

echo      ✅ Ambiente virtual ativado!
echo.

REM Verificar se .env existe
if not exist ".env" (
    echo ⚠️  Arquivo .env nao encontrado!
    echo    Crie um arquivo .env baseado no .env.example
    echo.
    pause
    exit /b 1
)

echo [2/3] Carregando configuracoes...
echo      ✅ Arquivo .env encontrado!
echo.

REM Mostrar informacoes
echo [3/3] Iniciando aplicacao Flask...
echo.
echo ========================================
echo   Acesse: http://localhost:5000
echo   Pressione Ctrl+C para parar
echo ========================================
echo.

REM Rodar aplicacao
python run.py

REM Desativar venv ao sair
deactivate

echo.
echo ========================================
echo   Aplicacao encerrada
echo ========================================
echo.
pause

