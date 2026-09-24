#!/usr/bin/env bash
# Rebuild only the paper: preserve manually revised text, references, and figures.
set -euo pipefail
dna_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if ! command -v latexmk >/dev/null 2>&1; then
  echo 'Install MacTeX (macOS) or TeX Live, including latexmk, then run this script again.' >&2
  exit 1
fi
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error "$dna_root/latex/main.tex"
cp "$dna_root/latex/main.pdf" "$dna_root/dna_eacl2027_draft.pdf"
printf '\nUpdated PDF: %s\n' "$dna_root/dna_eacl2027_draft.pdf"
