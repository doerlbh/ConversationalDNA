#!/usr/bin/env bash
set -euo pipefail
dna_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$dna_root"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export DNA_DATABASE="$dna_root/app/demo.sqlite"
exec .venv/bin/python app/server.py --host 127.0.0.1 --port "${1:-8765}"
