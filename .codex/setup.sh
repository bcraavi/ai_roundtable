#!/usr/bin/env bash
set -euo pipefail
cloud_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$cloud_root"
export CI=true
export NEXT_TELEMETRY_DISABLED=1
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip check
printf "%s\n" "Setup complete. Run bash .codex/check.sh. Services are started separately."
