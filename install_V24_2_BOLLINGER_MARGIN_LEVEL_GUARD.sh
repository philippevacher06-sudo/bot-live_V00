#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="${BOT_PIVOT_LIVE_DIR:-/home/philippe_vacher06/bot-pivot/live}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
BACKUP_DIR="$TARGET_DIR/backups/V24_1_BEFORE_V24_2_$STAMP"

echo "Install source : $SRC_DIR"
echo "Install target : $TARGET_DIR"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Target directory not found: $TARGET_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

for f in BOT_PIVOT_00_config.py BOT_PIVOT_05_cycle_engine.py BOT_PIVOT_06G2_execution_secure.py; do
  if [[ -f "$TARGET_DIR/$f" ]]; then
    cp -p "$TARGET_DIR/$f" "$BACKUP_DIR/$f"
  fi
done

cp -p "$SRC_DIR"/BOT_PIVOT_*.py "$TARGET_DIR"/
cp -p "$SRC_DIR"/run_BOT_PIVOT_07D_24_7_DEMO.sh "$TARGET_DIR"/ 2>/dev/null || true
cp -p "$SRC_DIR"/run_BOT_PIVOT_07D_SCALP_ACTIVE.sh "$TARGET_DIR"/ 2>/dev/null || true
cp -p "$SRC_DIR"/V24_2_VERIFY_LOCAL_STATE.py "$TARGET_DIR"/
cp -p "$SRC_DIR"/verify_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.sh "$TARGET_DIR"/
cp -p "$SRC_DIR"/relance_V24_2_DEMO.sh "$TARGET_DIR"/
cp -p "$SRC_DIR"/README_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.txt "$TARGET_DIR"/

chmod +x "$TARGET_DIR"/verify_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.sh
chmod +x "$TARGET_DIR"/relance_V24_2_DEMO.sh

cd "$TARGET_DIR"
if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "venv/bin/activate"
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" -m py_compile BOT_PIVOT_00_config.py BOT_PIVOT_05_cycle_engine.py BOT_PIVOT_06G2_execution_secure.py

echo "Install V24.2 OK"
echo "Backup: $BACKUP_DIR"
echo "Before relaunch, verify Capital.com demo manually: positions=0 and pending orders=0."
