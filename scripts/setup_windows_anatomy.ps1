$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ModelsDir = Join-Path $ProjectRoot "models"
$ModelPath = Join-Path $ModelsDir "pose_landmarker.task"
$ModelUrl = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"

Write-Host ""
Write-Host "=== CORVO IMAGE ENGINE V0.9 - ANATOMIA OPCIONAL ===" -ForegroundColor Cyan
Write-Host "Instala MediaPipe Pose Landmarker para localizar rosto, maos, bracos, torso e pernas." -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $VenvPython)) {
    Write-Host "Ambiente .venv nao encontrado. Execute INICIAR.bat uma vez e tente novamente." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null

Write-Host "[1/2] Instalando pacote mediapipe..."
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements-anatomy.txt")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar mediapipe." }

if (-not (Test-Path $ModelPath)) {
    Write-Host "[2/2] Baixando Pose Landmarker Lite oficial..."
    & curl.exe -L --fail --retry 3 --progress-bar -o $ModelPath $ModelUrl
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $ModelPath -Force -ErrorAction SilentlyContinue
        throw "Falha ao baixar pose_landmarker.task."
    }
} else {
    Write-Host "[2/2] pose_landmarker.task ja existe. Pulando download." -ForegroundColor Green
}

Write-Host ""
Write-Host "ANATOMIA OPCIONAL INSTALADA." -ForegroundColor Green
Write-Host "Reabra o INICIAR.bat. O painel deve mostrar anatomia: POSE PRONTA." -ForegroundColor Cyan
