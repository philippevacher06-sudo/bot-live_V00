#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -d venv ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

echo "== V24.2 VERIFY =="
echo "Dossier : $(pwd)"

echo "-- Compilation Python"
python -m py_compile \
  BOT_PIVOT_00_config.py \
  BOT_PIVOT_05_cycle_engine.py \
  BOT_PIVOT_06G2_execution_secure.py \
  BOT_PIVOT_06H_execution_demo_guarded.py \
  BOT_PIVOT_06G_execution_from_cycle_state.py

echo "-- Marqueurs V24.2"
grep -n "V24_2_VERSION" BOT_PIVOT_06G2_execution_secure.py
grep -n "def v242_validate_bollinger_limit_levels" BOT_PIVOT_06G2_execution_secure.py
grep -n "V242_BASKET_REJECT_MARGIN_GUARD" BOT_PIVOT_06G2_execution_secure.py
grep -n "V24_LIMIT_SIDE_GUARD_V242_NO_MOVE" BOT_PIVOT_06G2_execution_secure.py
grep -n '"OIL_CRUDE": 4' BOT_PIVOT_00_config.py

echo "-- Vérification TP broker conservé"
grep -n "V24_BROKER_UPL_TP_PATCH_V1" BOT_PIVOT_06G2_execution_secure.py
grep -n "source=BROKER_POSITION_UPL" BOT_PIVOT_06G2_execution_secure.py

echo "-- Vérification states locaux"
python - <<'PY'
import json
from pathlib import Path

cycle_path = Path("data/cycles/cycle_state.json")
exec_path = Path("data/execution/cycle_execution_state.json")

cycle = json.loads(cycle_path.read_text()) if cycle_path.exists() else {}
execs = json.loads(exec_path.read_text()) if exec_path.exists() else {}

non_idle = []
for asset, st in (cycle.get("assets", {}) or {}).items():
    if st.get("status") != "IDLE":
        non_idle.append((asset, st.get("status"), (st.get("cycle") or {}).get("direction")))

active = list((execs.get("active", {}) or {}).keys())
print("CYCLE non-IDLE =", non_idle)
print("EXEC active    =", active)

# Ne bloque pas l'installation si les states ne sont pas vides, mais l'affiche clairement.
if non_idle or active:
    print("ATTENTION: state local non vide. Ne pas relancer avant contrôle manuel Capital.com.")
PY

echo "== OK: V24.2 compilée et marqueurs présents =="
