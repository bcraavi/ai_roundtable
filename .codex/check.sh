#!/usr/bin/env bash
set -euo pipefail
cloud_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$cloud_root"
export CI=true
export NEXT_TELEMETRY_DISABLED=1
export ENVIRONMENT=test
export MPLBACKEND=Agg
if [ ! -f .venv/bin/activate ]; then echo "Run bash .codex/setup.sh first" >&2; exit 1; fi
. .venv/bin/activate
python3 .codex/verify.py
cloud_status=0
cloud_run() {
  printf "%s\n" "Running: $1"
  if bash -c "$1"; then return 0; else cloud_status=1; fi
}
cloud_run 'python -m unittest discover -s tests -v'
exit "$cloud_status"
