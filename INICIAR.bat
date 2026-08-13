@echo off
setlocal
cd /d "%~dp0"
title Corvo Image Engine V0.4 - Composer

echo ==============================================
echo      CORVO IMAGE ENGINE V0.4 - COMPOSER
echo ==============================================
echo.
echo Motor principal: memoria visual + composicao.
echo CUDA nao e necessario para este MVP.
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente Python local...
  where py >nul 2>nul
  if %errorlevel%==0 (
    py -3.11 -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo ERRO: Python nao encontrado. Instale Python 3.11 ou 3.12 e tente novamente.
  pause
  exit /b 1
)

set PY=.venv\Scripts\python.exe

if not exist ".venv\.deps_ok_v04" (
  echo Instalando dependencias leves do Composer Engine...
  "%PY%" -m pip install --upgrade pip
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo ERRO ao instalar dependencias.
    pause
    exit /b 1
  )
  echo ok> .venv\.deps_ok_v04
)

if not exist "visual_bank\metadata.json" (
  echo Criando banco visual demo...
  "%PY%" -m engine.seed_visual_bank
)

start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8011"
"%PY%" -m uvicorn engine.server:app --host 127.0.0.1 --port 8011

endlocal
