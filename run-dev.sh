#!/usr/bin/env bash
# Run straight from the source folder (for development). Creates ./.venv on first run.
set -euo pipefail
cd "$(dirname "$0")"
[[ -d .venv ]] || { python3 -m venv .venv && .venv/bin/pip install -q PySide6-Essentials psutil; }
exec .venv/bin/python -m capyrunner "$@"
