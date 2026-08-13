$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RuntimeDir = Join-Path $ProjectRoot "runtime\sdcpp"
$ModelsDir = Join-Path $ProjectRoot "models"
$TempDir = Join-Path $ProjectRoot "runtime\_download"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

Write-Host ""
Write-Host "=== IMAGE MOTOR MVP - SETUP VULKAN ===" -ForegroundColor Cyan
Write-Host "Este modo NAO precisa de CUDA. Usa Vulkan quando a GPU/driver permitem." -ForegroundColor Yellow
Write-Host ""

Write-Host "[1/3] Consultando a versao mais recente do stable-diffusion.cpp..."
$headers = @{ "User-Agent" = "Image-Motor-MVP" }
$release = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest"

$asset = $release.assets | Where-Object {
    $_.name -match "win.*vulkan.*x64.*\.zip$"
} | Select-Object -First 1

if (-not $asset) {
    Write-Host "Nao encontrei automaticamente um ZIP Vulkan x64 no release atual." -ForegroundColor Red
    Write-Host "Assets encontrados:" -ForegroundColor Yellow
    $release.assets | ForEach-Object { Write-Host " - $($_.name)" }
    throw "Asset Vulkan nao localizado."
}

$zipPath = Join-Path $TempDir $asset.name
Write-Host "Baixando: $($asset.name)"
& curl.exe -L --fail --retry 3 --progress-bar -o $zipPath $asset.browser_download_url
if ($LASTEXITCODE -ne 0) { throw "Falha ao baixar stable-diffusion.cpp" }

Write-Host "[2/3] Extraindo motor..."
Get-ChildItem $RuntimeDir -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zipPath -DestinationPath $RuntimeDir -Force
Set-Content -Encoding UTF8 -Path (Join-Path $RuntimeDir "engine_mode.txt") -Value "vulkan"

$server = Get-ChildItem $RuntimeDir -Recurse -Filter "sd-server.exe" | Select-Object -First 1
if (-not $server) { throw "sd-server.exe nao apareceu depois da extracao." }
Write-Host "Motor encontrado em: $($server.FullName)" -ForegroundColor Green

$modelPath = Join-Path $ModelsDir "sd_turbo.safetensors"
if (-not (Test-Path $modelPath)) {
    Write-Host "[3/3] Baixando SD-Turbo (~5.2 GB). Isto acontece uma vez..."
    $modelUrl = "https://huggingface.co/stabilityai/sd-turbo/resolve/main/sd_turbo.safetensors?download=true"
    & curl.exe -L --fail --retry 3 --progress-bar -o $modelPath $modelUrl
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $modelPath -Force -ErrorAction SilentlyContinue
        throw "Falha ao baixar SD-Turbo."
    }
} else {
    Write-Host "[3/3] Modelo ja existe. Pulando download." -ForegroundColor Green
}

Write-Host ""
Write-Host "SETUP VULKAN CONCLUIDO." -ForegroundColor Green
Write-Host "Agora execute INICIAR.bat na raiz do projeto." -ForegroundColor Cyan
Write-Host "Se o driver Vulkan nao funcionar, use setup_windows_cpu.ps1." -ForegroundColor Yellow
