#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live

echo "== V2446I apply patch =="
python3 apply_v2446i_rules.py

echo "== Stop runner safely =="
tmux kill-session -t v244_forced_runner 2>/dev/null || true
pkill -f BOT_PIVOT_24_4_forced_audit_runner 2>/dev/null || true
sleep 2

if pgrep -f BOT_PIVOT_24_4_forced_audit_runner >/dev/null; then
  echo "ABORT: runner encore actif"
  pgrep -af BOT_PIVOT_24_4_forced_audit_runner
  exit 1
fi

echo "== Start runner =="
rm -f data/execution/V244_FORCED_RUNNER_LOCK
tmux new-session -d -s v244_forced_runner "./run_V2446_ADVERSE_STEPS_ETH_BTC.sh 2>&1 | tee -a logs/v24_4_forced_audit/console_$(date +%Y%m%d_%H%M%S).log"
sleep 5

LOG=$(ls -t logs/v24_4_forced_audit/console_*.log | head -1)
echo "LOG=$LOG"

grep -E "RUNNER_V2446I_CASCADE_RULES_ACTIVE|RUNNER_V2446_ADVERSE_STEP_PATCH_ACTIVE|RUNNER_ADVERSE_STEP_EFFECTIVE_STEP|RUNNER_V2446I_DYNAMIC_STEP|RUNNER_ETH_BASKET_DECISION|RUNNER_V2446I_L1_MARGIN_CHECK|RUNNER_V2446I_OPEN_BLOCKED|RUNNER_V2446I_HARD_CLOSE|RUNNER_RESET_COOLDOWN|FIRST_OPEN|HARD_BLOCK|TypeError|NameError|Traceback|RUNNER_EXCEPTION" "$LOG" | tail -220
