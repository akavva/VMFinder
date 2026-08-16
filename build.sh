#!/usr/bin/env bash
# Builds a standalone Linux binary (dist/vmfinder) that bundles Python,
# Flask, pyVmomi and the templates/ folder — no Python install needed
# on the target machine.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q pyinstaller

pyinstaller --onefile --name vmfinder \
    --add-data "templates:templates" \
    --collect-all pyVmomi \
    --collect-all pyVim \
    VMFinder.py

rm -rf build vmfinder.spec
echo
echo "Built: dist/vmfinder"
