$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== BACKEND DIFFUSERS CPU (ALTERNATIVO) ===" -ForegroundColor Cyan
Write-Host "Este caminho e secundario. O stable-diffusion.cpp/Vulkan e o recomendado sem CUDA." -ForegroundColor Yellow

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
& $Python -m pip install diffusers transformers accelerate safetensors
Write-Host "Diffusers CPU instalado. O modelo sera baixado no primeiro uso." -ForegroundColor Green
