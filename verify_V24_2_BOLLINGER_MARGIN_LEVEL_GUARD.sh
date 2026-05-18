#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m py_compile \
  BOT_PIVOT_00_config.py \
  BOT_PIVOT_05_cycle_engine.py \
  BOT_PIVOT_06G2_execution_secure.py

"$PYTHON_BIN" V24_2_VERIFY_LOCAL_STATE.py

echo "V24.2 verify OK"
