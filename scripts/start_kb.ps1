# Launch TUI from repo root (forwards to industrial-cpp-kb-lab).
# Usage: from Smoothiewarerag/:  .\scripts\start_kb.ps1

$ErrorActionPreference = "Stop"

$LabRoot = Resolve-Path (Join-Path $PSScriptRoot "..\industrial-cpp-kb-lab")
$Target = Join-Path $LabRoot "scripts\start_kb.ps1"

if (-not (Test-Path $Target)) {
    Write-Host "Not found: $Target" -ForegroundColor Red
    Write-Host "Expected industrial-cpp-kb-lab next to this scripts/ folder." -ForegroundColor Yellow
    exit 1
}

& $Target
exit $LASTEXITCODE
