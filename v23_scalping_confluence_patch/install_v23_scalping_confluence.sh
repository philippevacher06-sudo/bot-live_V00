#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d venv ]; then
  source venv/bin/activate
fi

echo "Arrêt éventuel de la session tmux botpivot24..."
tmux kill-session -t botpivot24 2>/dev/null || true

echo "Installation V23 Scalping Confluence..."
python v23_scalping_confluence_patch/patch_v23_scalping_confluence.py

echo "Compilation..."
python -m py_compile BOT_PIVOT_00_config.py
python -m py_compile BOT_PIVOT_00B_pnl_eur.py
python -m py_compile BOT_PIVOT_04B_context_score.py
python -m py_compile BOT_PIVOT_04_signal_tick.py
python -m py_compile BOT_PIVOT_05_cycle_engine.py
python -m py_compile BOT_PIVOT_06G2_execution_secure.py

echo "Installation V23 terminée. Lance ensuite : bash v23_scalping_confluence_patch/audit_v23.sh"
