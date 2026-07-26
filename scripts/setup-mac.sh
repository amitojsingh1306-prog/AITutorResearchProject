#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if command -v python3.11 >/dev/null 2>&1; then
  PYTHON_BIN="python3.11"
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  echo "Python 3.11 or 3.12 is required. Install one, then rerun this script."
  exit 1
fi

"$PYTHON_BIN" -m venv .venv-mac
. .venv-mac/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt

echo "macOS environment ready: .venv-mac"
echo "Activate with: source .venv-mac/bin/activate"
