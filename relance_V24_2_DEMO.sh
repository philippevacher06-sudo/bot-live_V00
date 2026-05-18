#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${BOT_PIVOT_LIVE_DIR:-/home/philippe_vacher06/bot-pivot/live}"
SESSION="${BOT_PIVOT_TMUX_SESSION:-botpivot24}"
RUN_SCRIPT="${BOT_PIVOT_RUN_SCRIPT:-./run_BOT_PIVOT_07D_SCALP_ACTIVE.sh}"

cd "$TARGET_DIR"

echo "V24.2 relaunch target: $TARGET_DIR"
echo "tmux session        : $SESSION"
echo "run script          : $RUN_SCRIPT"
echo "Manual broker check required before relaunch: Capital.com positions=0 and pending orders=0."

if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

./verify_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.sh

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session already exists: $SESSION" >&2
  echo "Attach with: tmux attach -t $SESSION" >&2
  exit 1
fi

tmux new-session -d -s "$SESSION" "cd '$TARGET_DIR' && source venv/bin/activate && $RUN_SCRIPT"
echo "Relaunch OK: tmux attach -t $SESSION"
