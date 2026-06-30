# One-time dev environment setup for industrial-cpp-kb-lab.
# Usage: from repo root or industrial-cpp-kb-lab/:  .\scripts\setup_dev.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$venvPath = Join-Path $ProjectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvActivate = Join-Path $venvPath "Scripts\Activate.ps1"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating .venv..."
    python -m venv .venv
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        Write-Host "Failed to create .venv. Is Python installed and on PATH?" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Reusing existing .venv"
}

Write-Host "Activating .venv..."
. $venvActivate

Write-Host "Installing requirements..."
pip install -r requirements.txt
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "pip install failed." -ForegroundColor Red
    exit 1
}

Write-Host "Compiling kb_cli..."
python -m compileall src/kb_cli
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Host "compileall failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Start the TUI with:"
Write-Host "  .\scripts\start_kb.ps1"
Write-Host ""
Write-Host "Or from industrial-cpp-kb-lab/:"
Write-Host "  .\kb          # same as .\kb tui"
Write-Host "  .\kb search `"query`""
Write-Host "  .\kb ask `"query`""
