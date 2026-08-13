$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RuntimeDir = Join-Path $ProjectRoot "runtime\sdcpp"
$ModelsDir = Join-Path $ProjectRoot "models"
$TempDir = Join-Path $ProjectRoot "runtime\_download"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null

Write-Host ""
Write-Host "=== IMAGE MOTOR MVP - SETUP CPU ===" -ForegroundColor Cyan
Write-Host "Este modo roda sem CUDA e sem depender da GPU. Pode ser bem mais lento." -ForegroundColor Yellow
Write-Host ""

Write-Host "[1/3] Consultando stable-diffusion.cpp..."
$headers = @{ "User-Agent" = "Image-Motor-MVP" }
$release = Invoke-RestMethod -Headers $headers -Uri "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest"

# Prefer explicit CPU/AVX2 builds. Fall back to a generic Windows x64 build,
# while excluding known GPU-specific archives.
$asset = $release.assets | Where-Object {
    $_.name -match "win.*(cpu|avx2|avx).*x64.*\.zip$"
} | Select-Object -First 1

if (-not $asset) {
    $asset = $release.assets | Where-Object {
        $_.name -match "win.*x64.*\.zip$" -and
        $_.name -notmatch "cuda|vulkan|rocm|sycl|hip"
    } | Select-Object -First 1
}

if (-not $asset) {
    Write-Host "Nao encontrei automaticamente um build CPU Windows x64." -ForegroundColor Red
    Write-Host "Assets encontrados:" -ForegroundColor Yellow
    $release.assets | ForEach-Object { Write-Host " - $($_.name)" }
    throw "Asset CPU nao localizado."
}

$zipPath = Join-Path $TempDir $asset.name
Write-Host "Baixando: $($asset.name)"
& curl.exe -L --fail --retry 3 --progress-bar -o $zipPath $asset.browser_download_url
if ($LASTEXITCODE -ne 0) { throw "Falha ao baixar stable-diffusion.cpp" }

Write-Host "[2/3] Extraindo motor..."
Get-ChildItem $RuntimeDir -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zipPath -DestinationPath $RuntimeDir -Force
Set-Content -Encoding UTF8 -Path (Join-Path $RuntimeDir "engine_mode.txt") -Value "cpu"

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
Write-Host "SETUP CPU CONCLUIDO." -ForegroundColor Green
Write-Host "Agora execute INICIAR.bat na raiz do projeto." -ForegroundColor Cyan
