# Mirror GitHub Actions eval job locally (Windows PowerShell).
# Usage: from industrial-cpp-kb-lab/:  .\scripts\ci_build_and_eval.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path "repos\Smoothieware\src")) {
    Write-Host "Cloning Smoothieware (shallow)..."
    New-Item -ItemType Directory -Force -Path repos | Out-Null
    git clone --depth 1 https://github.com/Smoothieware/Smoothieware.git repos/Smoothieware
}

pip install -r requirements.txt
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py
python src/03_build_callgraph.py
python src/03_search.py --eval
python src/run_regression.py --skip-llm --top-k 8

Write-Host "CI mirror: PASS"
