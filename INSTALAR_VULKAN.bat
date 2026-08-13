@echo off
cd /d "%~dp0"
title Image Motor MVP - Setup Vulkan
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows_vulkan.ps1"
if errorlevel 1 (
  echo.
  echo O setup Vulkan falhou. Voce pode tentar INSTALAR_CPU.bat.
)
pause
