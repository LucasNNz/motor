@echo off
setlocal
cd /d "%~dp0"
title Corvo Image Engine V0.9 - Instalar Anatomia
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows_anatomy.ps1"
if errorlevel 1 (
  echo.
  echo ERRO na instalacao da anatomia opcional.
  pause
  exit /b 1
)
echo.
pause
endlocal
