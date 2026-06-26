#!/usr/bin/env bash
# Mirror GitHub Actions eval job locally (Linux/macOS/WSL).
# Usage: from industrial-cpp-kb-lab/:  bash scripts/ci_build_and_eval.sh

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -d repos/Smoothieware/src ]]; then
  echo "Cloning Smoothieware (shallow)..."
  mkdir -p repos
  git clone --depth 1 https://github.com/Smoothieware/Smoothieware.git repos/Smoothieware
fi

pip install -r requirements.txt
python src/01_scan_files.py
python src/02_extract_symbols.py
python src/03_build_chunks.py
python src/03_build_callgraph.py
python src/03_search.py --eval
python src/run_regression.py --skip-llm --top-k 8

echo "CI mirror: PASS"
