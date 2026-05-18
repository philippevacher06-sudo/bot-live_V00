#!/usr/bin/env bash
set -e
cd /home/philippe_vacher06/bot-pivot/live
echo "== Compilation execution =="
python -m py_compile BOT_PIVOT_06G2_execution_secure.py
echo "Compilation OK"
echo
echo "== Compilation guard =="
python -m py_compile BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD.py
echo "Guard OK"
echo
echo "== Marqueurs globaux =="
grep -nE "V24_SCALP_ACTIVE_GLOBAL_HELPERS_V3|v24sa_guard_working_payload|v24sa_retry_working_order|V24_LIMIT_SIDE_GUARD|V24_STOP_GUARD|V24_WORKING_ORDER_RETRY|size_tol|BASKET_EMPTY_RESET_BLOCKED|V24_ORPHAN_WORKING_ORDER_CLEANUP_BEFORE_RESET|V24_BASKET_TP_FAIL_CANCEL_PENDING_TO_FREE_MARGIN|BASKET_PARTIAL_PENDING_CANCEL|broker_cleanup_results" BOT_PIVOT_06G2_execution_secure.py || true
echo
echo "== Runner guard =="
grep -nE "SCALP_ACTIVE_GUARD|BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD" run_BOT_PIVOT_07D_24_7_DEMO.sh || true
echo
echo "== Lanceur scalp active =="
ls -lh run_BOT_PIVOT_07D_SCALP_ACTIVE.sh || true
