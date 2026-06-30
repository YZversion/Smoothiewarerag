# Start the Smoothieware code KB TUI.
# Usage: from repo root or industrial-cpp-kb-lab/:  .\scripts\start_kb.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    Write-Host "Activating .venv..."
    . $venvActivate
} else {
    Write-Host "Warning: .venv not found — using current Python." -ForegroundColor Yellow
    Write-Host "Run .\scripts\setup_dev.ps1 to create the virtual environment." -ForegroundColor Yellow
}

$srcPath = Join-Path $ProjectRoot "src"
if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH"
} else {
    $env:PYTHONPATH = $srcPath
}

Write-Host "Starting TUI (Ctrl+C or Escape to quit)..."
try {
    python -m kb_cli
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "kb_cli exited with code $LASTEXITCODE"
    }
} catch {
    Write-Host ""
    Write-Host "Failed to start TUI: $_" -ForegroundColor Red
    Write-Host "Try: .\scripts\setup_dev.ps1" -ForegroundColor Yellow
    exit 1
}
