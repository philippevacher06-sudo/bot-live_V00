#!/usr/bin/env bash
set -e
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate
python -m py_compile BOT_PIVOT_06G2_execution_secure.py
printf '\nCompilation OK\n\n'
grep -nE "size_tol|BASKET_EMPTY_RESET_BLOCKED|V24_ORPHAN_WORKING_ORDER_CLEANUP_BEFORE_RESET|V24_BASKET_TP_FAIL_CANCEL_PENDING|BASKET_PARTIAL_PENDING_CANCEL|PARTIAL_BASKET_PENDING_MAX_AGE_SEC|broker_cleanup_results|tp_pending_cancel_results" BOT_PIVOT_06G2_execution_secure.py || true
