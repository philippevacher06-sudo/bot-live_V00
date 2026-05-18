#!/usr/bin/env bash
# V24.1 — Chargement robuste .env + curseurs de test démo
cd "$(dirname "$0")"

if [ -f ".env" ]; then
  set -a
  . ".env"
  set +a
fi

export CAPITAL_IDENTIFIER="${CAPITAL_IDENTIFIER:-$CAPITAL_LOGIN}"

# Curseurs individuels V24.1
export BOLLINGER_CURSOR="${BOLLINGER_CURSOR:-1.0}"
export TREND_ENTRY_CURSOR="${TREND_ENTRY_CURSOR:-0.8}"
export SAFETY_EXIT_CURSOR="${SAFETY_EXIT_CURSOR:-1.0}"

# Protection news paramétrable
export NEWS_WINDOW_BEFORE_MIN="${NEWS_WINDOW_BEFORE_MIN:-5}"
export NEWS_WINDOW_AFTER_MIN="${NEWS_WINDOW_AFTER_MIN:-5}"


cd "$(dirname "$0")" || exit 1

ASSETS="US500,US100,US30,DE40,FR40,UK100,J225,EURUSD,GBPUSD,USDJPY,EURJPY,GOLD,SILVER,OIL_CRUDE,BTCUSD,ETHUSD"
export ASSETS

MAX_CYCLES="${MAX_CYCLES:-999999}"
TICK_SECONDS="${TICK_STREAM_DURATION_SEC:-45}"
PRINT_EVERY=30
PAUSE_SECONDS="${CYCLE_PAUSE_SEC:-5}"
MIN_SPREAD_SAMPLES="${MIN_SPREAD_SAMPLES:-150}"

# Fraîcheur du contexte
REFRESH_MARKETS_SECONDS="${MARKETS_MAX_AGE_SEC:-7200}"
REFRESH_ZONES_SECONDS="${ZONES_MAX_AGE_SEC:-43200}"
REFRESH_HISTORY_SECONDS="${HISTORY_MAX_AGE_SEC:-86400}"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"

LOG="$LOG_DIR/BOT_PIVOT_07D_24_7_DEMO_$(date -u '+%Y%m%d_%H%M%S').log"

CLEANUP_DONE=0

cleanup_pending_on_exit() {
  local why="${1:-EXIT}"
  if [ "$CLEANUP_DONE" = "1" ]; then
    return 0
  fi
  CLEANUP_DONE=1

  echo "" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"
  echo "V2436 CLEANUP PENDING ON ${why} — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"

  V2437_EXIT_WHY="$why" python - <<'PY' 2>&1 | tee -a "$LOG"
import os
import json
import time
import BOT_PIVOT_06G_execution_from_cycle_state as B
import BOT_PIVOT_06G2_execution_secure as X

assets = [a.strip() for a in os.environ.get("ASSETS", "").split(",") if a.strip()]
reason = "V2436_RUN_SCRIPT_EXIT_PENDING_CLEANUP"

try:
    B.load_env()
    headers = B.login()
    X.SEND_REAL_ORDERS = True
    X.sync_base_flags()

    ps, positions, _ = B.broker_positions(headers)
    ws, wraw = B.api_get(headers, "/api/v1/workingorders")
    before_items = X.normalize_working_orders_response(wraw)
    print(json.dumps({
        "event": "V2436_EXIT_CLEANUP_BEFORE",
        "positions_status": ps,
        "positions_count": len(positions),
        "workingorders_status": ws,
        "workingorders_count": len(before_items),
    }, ensure_ascii=False))

    print(json.dumps({
        "event": "V2437_EXIT_CLEANUP_BEFORE",
        "version": os.environ.get("V2437_VERSION"),
        "run_id": os.environ.get("V2437_RUN_ID"),
        "why": os.environ.get("V2437_EXIT_WHY", "EXIT"),
        "positions_status": ps,
        "positions_count": len(positions),
        "workingorders_status": ws,
        "workingorders_count": len(before_items),
    }, ensure_ascii=False))

    results = []
    for asset in assets:
        res = X.v24_cancel_broker_pending_for_asset(
            headers=headers,
            asset=asset,
            direction=None,
            reason=reason,
        )
        if res:
            print(f"{asset:10s} | V2436_EXIT_PENDING_CLEANUP | count={len(res)}")
        results.append({"asset": asset, "results": res})

    ps2, positions2, _ = B.broker_positions(headers)
    ws2, wraw2 = B.api_get(headers, "/api/v1/workingorders")
    after_items = X.normalize_working_orders_response(wraw2)

    verify_results = []
    if str(os.environ.get("V2437_CLEANUP_VERIFY_LOOP", "1")).lower() not in ("0", "false", "no", "off"):
        for attempt in range(1, 4):
            if len(after_items) == 0:
                break
            print(json.dumps({
                "event": "V2437_EXIT_CLEANUP_VERIFY_RETRY",
                "attempt": attempt,
                "workingorders_count": len(after_items),
            }, ensure_ascii=False))
            for asset in assets:
                res = X.v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=None,
                    reason=f"{reason}_VERIFY_RETRY_{attempt}",
                )
                if res:
                    verify_results.append({"attempt": attempt, "asset": asset, "results": res})
            time.sleep(1)
            ps2, positions2, _ = B.broker_positions(headers)
            ws2, wraw2 = B.api_get(headers, "/api/v1/workingorders")
            after_items = X.normalize_working_orders_response(wraw2)

    print(json.dumps({
        "event": "V2436_EXIT_CLEANUP_AFTER",
        "positions_status": ps2,
        "positions_count": len(positions2),
        "workingorders_status": ws2,
        "workingorders_count": len(after_items),
        "results": results,
    }, ensure_ascii=False))

    final_event = "V2437_EXIT_CLEANUP_OK" if len(after_items) == 0 else "V2437_EXIT_CLEANUP_FAILED_PENDING_STILL_ALIVE"
    print(json.dumps({
        "event": final_event,
        "version": os.environ.get("V2437_VERSION"),
        "run_id": os.environ.get("V2437_RUN_ID"),
        "why": os.environ.get("V2437_EXIT_WHY", "EXIT"),
        "positions_status": ps2,
        "positions_count": len(positions2),
        "workingorders_status": ws2,
        "workingorders_count": len(after_items),
        "verify_results": verify_results,
    }, ensure_ascii=False))
except Exception as exc:
    print(json.dumps({
        "event": "V2436_EXIT_CLEANUP_ERROR",
        "error": str(exc),
    }, ensure_ascii=False))
PY

  echo "" | tee -a "$LOG"
  echo "V2437_RECONCILE_AFTER_EXIT_CLEANUP — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  python BOT_PIVOT_06G1_reconcile_broker.py 2>&1 | tee -a "$LOG" || true
}

trap 'cleanup_pending_on_exit SIGINT; exit 130' INT
trap 'cleanup_pending_on_exit SIGTERM; exit 143' TERM
trap 'cleanup_pending_on_exit EXIT' EXIT

CTX_DIR="data/context_refresh"
mkdir -p "$CTX_DIR"

MARKETS_TS="$CTX_DIR/last_markets_refresh.ts"
ZONES_TS="$CTX_DIR/last_zones_refresh.ts"
HISTORY_TS="$CTX_DIR/last_history_refresh.ts"

now_epoch() {
  date +%s
}

file_age_seconds() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo 999999999
  else
    echo $(( $(now_epoch) - $(cat "$f" 2>/dev/null || echo 0) ))
  fi
}

mark_done() {
  local f="$1"
  now_epoch > "$f"
}

refresh_markets() {
  echo "" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"
  echo "REFRESH CONTEXTE — 06C MARKET RULES — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"


echo "MODULE 00Z — SCALP ACTIVE GUARD"
python BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD.py || true
  python BOT_PIVOT_06C_market_rules.py --assets "$ASSETS" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}

  if [ "$rc" -eq 0 ]; then
    mark_done "$MARKETS_TS"
    echo "REFRESH 06C OK" | tee -a "$LOG"
  else
    echo "REFRESH 06C ECHEC rc=$rc" | tee -a "$LOG"
  fi
}

refresh_history() {
  echo "" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"
  echo "REFRESH CONTEXTE — 01 HISTORICAL M15 30D — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"

  python BOT_PIVOT_01_historical.py --assets "$ASSETS" --resolution MINUTE_15 --days 30 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}

  if [ "$rc" -eq 0 ]; then
    mark_done "$HISTORY_TS"
    echo "REFRESH 01 OK" | tee -a "$LOG"
    return 0
  else
    echo "REFRESH 01 ECHEC rc=$rc" | tee -a "$LOG"
    return 1
  fi
}

refresh_zones() {
  echo "" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"
  echo "REFRESH CONTEXTE — 02 ZONES / PIVOTS — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  echo "============================================================================================================" | tee -a "$LOG"

  python BOT_PIVOT_02_zones.py --assets "$ASSETS" 2>&1 | tee -a "$LOG"
  local rc=${PIPESTATUS[0]}

  if [ "$rc" -eq 0 ]; then
    mark_done "$ZONES_TS"
    echo "REFRESH 02 OK" | tee -a "$LOG"
  else
    echo "REFRESH 02 ECHEC rc=$rc" | tee -a "$LOG"
  fi
}

refresh_context_if_due() {
  local markets_age
  local zones_age
  local history_age

  markets_age=$(file_age_seconds "$MARKETS_TS")
  zones_age=$(file_age_seconds "$ZONES_TS")
  history_age=$(file_age_seconds "$HISTORY_TS")

  echo "" | tee -a "$LOG"
  echo "FRAÎCHEUR CONTEXTE :" | tee -a "$LOG"
  echo "- markets age : ${markets_age}s / seuil ${REFRESH_MARKETS_SECONDS}s" | tee -a "$LOG"
  echo "- zones age   : ${zones_age}s / seuil ${REFRESH_ZONES_SECONDS}s" | tee -a "$LOG"
  echo "- history age : ${history_age}s / seuil ${REFRESH_HISTORY_SECONDS}s" | tee -a "$LOG"

  if [ "$markets_age" -ge "$REFRESH_MARKETS_SECONDS" ]; then
    refresh_markets
  fi

  if [ "$history_age" -ge "$REFRESH_HISTORY_SECONDS" ]; then
    if refresh_history; then
      # Quand l’historique change, les zones doivent être recalculées immédiatement.
      refresh_zones
    fi
  elif [ "$zones_age" -ge "$REFRESH_ZONES_SECONDS" ]; then
    refresh_zones
  fi
}

echo "========================================================================================================================" | tee -a "$LOG"
echo "BOT_PIVOT_07D — DEMO 24/7" | tee -a "$LOG"
echo "Début UTC       : $(date -u '+%Y-%m-%d %H:%M:%S')" | tee -a "$LOG"
echo "Ordres          : DEMO Capital.com uniquement" | tee -a "$LOG"
echo "Actifs          : $ASSETS" | tee -a "$LOG"
echo "Max cycles      : $MAX_CYCLES" | tee -a "$LOG"
echo "Ticks secondes  : $TICK_SECONDS" | tee -a "$LOG"
echo "Pause secondes  : $PAUSE_SECONDS" | tee -a "$LOG"
echo "Refresh markets : ${REFRESH_MARKETS_SECONDS}s" | tee -a "$LOG"
echo "Refresh zones   : ${REFRESH_ZONES_SECONDS}s" | tee -a "$LOG"
echo "Refresh history : ${REFRESH_HISTORY_SECONDS}s" | tee -a "$LOG"
echo "Log             : $LOG" | tee -a "$LOG"
echo "========================================================================================================================" | tee -a "$LOG"

# Refresh initial obligatoire au démarrage
refresh_markets
if refresh_history; then
  refresh_zones
fi

i=0

while true; do
  i=$((i+1))

  echo "" | tee -a "$LOG"
  echo "########################################################################################################################" | tee -a "$LOG"
  echo "07D — CYCLE $i — $(date -u '+%Y-%m-%dT%H:%M:%SZ')" | tee -a "$LOG"
  echo "########################################################################################################################" | tee -a "$LOG"

  refresh_context_if_due

  echo "" | tee -a "$LOG"
  echo "MODULE 03 — TICKS" | tee -a "$LOG"
  python BOT_PIVOT_03_tick_stream.py --assets "$ASSETS" --seconds "$TICK_SECONDS" --print-every "$PRINT_EVERY" 2>&1 | tee -a "$LOG"

  echo "" | tee -a "$LOG"
  echo "MODULE 04 — SIGNAUX" | tee -a "$LOG"
  python BOT_PIVOT_04_signal_tick.py --assets "$ASSETS" --min-spread-samples "$MIN_SPREAD_SAMPLES" 2>&1 | tee -a "$LOG"

  echo "" | tee -a "$LOG"
  echo "MODULE 05 — CYCLE ENGINE" | tee -a "$LOG"
  python BOT_PIVOT_05_cycle_engine.py --assets "$ASSETS" 2>&1 | tee -a "$LOG"

  echo "" | tee -a "$LOG"
  echo "MODULE 06H — EXECUTION DEMO GARDEE" | tee -a "$LOG"
  python BOT_PIVOT_06H_execution_demo_guarded.py --real-demo --unlock OK_ENVOI_DEMO --max-cycles "$MAX_CYCLES" --assets "$ASSETS" 2>&1 | tee -a "$LOG"

  echo "" | tee -a "$LOG"
  echo "Pause ${PAUSE_SECONDS}s..." | tee -a "$LOG"
  sleep "$PAUSE_SECONDS"
done
