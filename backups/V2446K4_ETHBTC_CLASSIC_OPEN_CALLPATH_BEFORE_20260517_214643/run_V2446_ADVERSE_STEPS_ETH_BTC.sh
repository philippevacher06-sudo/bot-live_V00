#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live

echo "============================================================"
echo "RUN V2446 — ETH/BTC — ADVERSE PRICE STEPS"
echo "============================================================"

# Charger les identifiants Capital.com sans les afficher
set -a
. ./.env
set +a

# Sécurité générale
export V244_FORCED_AUDIT_ENABLED=1
export V244_DEMO_ONLY_LOCK=1
export V244_AUDIT_DIR=logs/v24_4_forced_audit

# Actifs
export V244_TRADED_ASSET=ETHUSD

# V2446K3_STATE_PER_ASSET
# Chaque paire doit avoir son propre état adverse-step.
# Sinon un actif peut hériter du last_step_level d'un autre actif.
mkdir -p data/execution
export V2446_ADVERSE_STATE_FILE="data/execution/v2446_adverse_steps_state_${V244_TRADED_ASSET}.json"
export V244_CONFIRM_ASSET=BTCUSD
export V244_EXCLUDED_ASSETS=GOLD

# GOLD protégé / mode forcé
export V244_DISABLE_CLASSIC_BASKET_OPEN=1

# Marge
export V244_MARGIN_MAX_EUR=3000
export V244_MARGIN_SOFT_EUR=2600
export V244_CLOSE_PAIR_RATIO_MIN=1.67

# Cadence : plus de limite 2/min
export V244_TARGET_OPENINGS_PER_MIN=99999

# Plafond positions ETH
export V244_MAX_OPEN_POSITIONS=12

# Boucle rapide mais pas absurde pour éviter 429
export V244_RUNNER_SLEEP_SEC=3

# Stops broker
export V244_GUARANTEED_STOP=1
export V244_STOP_DISTANCE=25

# Ancienne variable conservée si le runner la lit encore
export V244_MAX_POSITION_AGE_SEC=25

# Activation réelle du patch V2446
export V244_ENTRY_MODE=ADVERSE_PRICE_STEPS
export V244_PRICE_STEP_POINTS=1.0

echo "CONFIG:"
echo "  TRADED_ASSET=$V244_TRADED_ASSET"
echo "  CONFIRM_ASSET=$V244_CONFIRM_ASSET"
echo "  EXCLUDED_ASSETS=$V244_EXCLUDED_ASSETS"
echo "  TARGET_OPENINGS_PER_MIN=$V244_TARGET_OPENINGS_PER_MIN"
echo "  MAX_OPEN_POSITIONS=$V244_MAX_OPEN_POSITIONS"
echo "  RUNNER_SLEEP_SEC=$V244_RUNNER_SLEEP_SEC"
echo "  ENTRY_MODE=$V244_ENTRY_MODE"
echo "  PRICE_STEP_POINTS=$V244_PRICE_STEP_POINTS"
echo "============================================================"

python3 BOT_PIVOT_24_4_forced_audit_runner.py
