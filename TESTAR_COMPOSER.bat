@echo off
setlocal
cd /d "%~dp0"
title Corvo Image Engine - Teste Composer

if not exist ".venv\Scripts\python.exe" (
  echo Primeiro execute INICIAR.bat pelo menos uma vez para preparar o Python local.
  pause
  exit /b 1
)

.venv\Scripts\python.exe -m engine.selftest

echo.
echo As imagens foram salvas em outputs\selftest\
pause
endlocal
