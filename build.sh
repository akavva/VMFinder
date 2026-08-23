#!/usr/bin/env bash
# Builds a standalone Linux binary (dist/vmfinder) that bundles Python,
# Flask, pyVmomi and the templates/ folder — no Python install needed
# on the target machine.
#
# A PyInstaller binary links the glibc of the machine that built it and will
# not start on anything older, so release builds run inside a manylinux_2_28
# container (glibc 2.28) to stay compatible with RHEL/Rocky 8, Ubuntu 20.04
# and Debian 10 — see .github/workflows/release.yml. Building locally is fine
# for local use; the binary is then only as portable as this machine's glibc.
#
# Set VMFINDER_VERSION to stamp a version into the binary (defaults to "dev").
# Set PYTHON to pick the interpreter used for the venv (defaults to python3).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VMFINDER_VERSION="${VMFINDER_VERSION:-dev}"

if [ ! -d .venv ]; then
    "$PYTHON" -m venv .venv
fi
source .venv/bin/activate
pip install -q -r requirements.txt
pip install -q pyinstaller

# Writes _version.py so --version, the startup log and the UI footer all
# report the right version. Also writes the Windows-only version_info.txt,
# which is cleaned up below.
python generate_version_info.py "$VMFINDER_VERSION"

pyinstaller --onefile --name vmfinder \
    --add-data "templates:templates" \
    --collect-all pyVmomi \
    --collect-all pyVim \
    VMFinder.py

rm -rf build vmfinder.spec version_info.txt
echo
echo "Built: dist/vmfinder ($VMFINDER_VERSION)"
