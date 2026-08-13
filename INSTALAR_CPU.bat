@echo off
cd /d "%~dp0"
title Image Motor MVP - Setup CPU
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows_cpu.ps1"
pause
