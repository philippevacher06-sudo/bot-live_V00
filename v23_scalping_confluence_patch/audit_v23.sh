#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d venv ]; then
  source venv/bin/activate
fi

echo "================ COMPILATION ================"
python -m py_compile BOT_PIVOT_00_config.py && echo "Config OK"
python -m py_compile BOT_PIVOT_00B_pnl_eur.py && echo "00B PnL EUR OK"
python -m py_compile BOT_PIVOT_04B_context_score.py && echo "04B contexte OK"
python -m py_compile BOT_PIVOT_04_signal_tick.py && echo "04 signal OK"
python -m py_compile BOT_PIVOT_05_cycle_engine.py && echo "05 cycle OK"
python -m py_compile BOT_PIVOT_06G2_execution_secure.py && echo "06G2 OK"

echo
echo "================ AUDIT V23 — TAILLES + TP ================"
python - << 'PY'
import BOT_PIVOT_00_config as CFG
import BOT_PIVOT_05_cycle_engine as C

assets = list(CFG.ASSETS)

print("="*120)
print("AUDIT V23 — TAILLES x3 + TP PAR NIVEAU")
print("="*120)

print("TP_EUR_BY_LEVEL =", getattr(CFG, "TP_EUR_BY_LEVEL", None))
print("MIN_CONTEXT_SCORE_ENTRY =", getattr(CFG, "MIN_CONTEXT_SCORE_ENTRY", None))
print("MIN_CONTEXT_SCORE_NEXT_LEVEL =", getattr(CFG, "MIN_CONTEXT_SCORE_NEXT_LEVEL", None))
print("MIN_CONTEXT_SCORE_KEEP =", getattr(CFG, "MIN_CONTEXT_SCORE_KEEP", None))
print("CLOSE_WEAK_CONTEXT_AFTER_SEC =", getattr(CFG, "CLOSE_WEAK_CONTEXT_AFTER_SEC", None))

print("-"*120)
print(f"{'ACTIF':10s} | {'SIZE L1':>12s} | {'SIZE L2':>12s} | {'SIZE L3':>12s} | {'TP L1':>8s} | {'TP L2':>8s} | {'TP L3':>8s}")
print("-"*120)

for asset in assets:
    print(
        f"{asset:10s} | "
        f"{C.size_for(asset, 1):12.6f} | "
        f"{C.size_for(asset, 2):12.6f} | "
        f"{C.size_for(asset, 3):12.6f} | "
        f"{C.tp_for(1):8.2f} | "
        f"{C.tp_for(2):8.2f} | "
        f"{C.tp_for(3):8.2f}"
    )

print("="*120)
PY

echo
echo "================ CONTROLE PATCHS ================"
grep -nE "TP_EUR_BY_LEVEL|BASE_TP_EUR|MIN_CONTEXT_SCORE|CLOSE_WEAK_CONTEXT" BOT_PIVOT_00_config.py || true
grep -nE "BOT_PIVOT_04B_context_score|context_score|vwap_bias|camarilla_context" BOT_PIVOT_04_signal_tick.py || true
grep -nE "MIN_CONTEXT_SCORE|IDLE_CONTEXT_WEAK|HOLD_CONTEXT_WEAK|CLOSE_CONTEXT_WEAK|tp_for|PNL.pnl_eur" BOT_PIVOT_05_cycle_engine.py || true

echo
echo "================ MODULE 04 — TEST SANS ORDRE ================"
python BOT_PIVOT_04_signal_tick.py --assets ALL --min-spread-samples 20 || true

echo
echo "================ BROKER / RECONCILIATION ================"
python BOT_PIVOT_06B_account_positions.py || true
python BOT_PIVOT_06G1_reconcile_broker.py || true
