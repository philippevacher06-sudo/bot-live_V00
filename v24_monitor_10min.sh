#!/usr/bin/env bash
set -u

OUT="logs/V24_MONITOR_$(date +"%Y%m%d_%H%M%S").txt"
echo "Monitor écrit dans : $OUT"

for i in $(seq 1 20); do
  TS=$(date +"%Y-%m-%d %H:%M:%S")
  LOG=$(ls -t logs/BOT_PIVOT_07D_24_7_DEMO_*.log | head -1)

  {
    echo
    echo "===================================================================================================="
    echo "MONITOR PASS $i/20 — $TS"
    echo "===================================================================================================="
    echo "LOG=$LOG"
    echo

    python audit_v24_global_state.py

    echo
    echo "----------------------------------------------------------------------------------------------------"
    echo "DERNIERS EVENTS PNL / CLOSE / HOLD"
    echo "----------------------------------------------------------------------------------------------------"
    grep -nE "US30|GOLD|OIL_CRUDE|BASKET_FILL|PNL_AUDIT_TOTAL|BASKET_TP_OK|BASKET_TP_FAIL|BASKET_HOLD|BASKET_PENDING_CANCEL|CLOSE|CLOSE_OK|CLOSE_FAIL|V24_OPEN_BASKET|SIGNAL_LOST|OPPOSITE_SIGNAL|target|pnl|open=|pending=" "$LOG" | tail -180
  } >> "$OUT" 2>&1

  sleep 30
done

echo "FIN MONITOR : $OUT"
