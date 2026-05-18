#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

ASSET = "EURUSD"

cycle_path = Path("data/cycles/cycle_state.json")
exec_path = Path("data/execution/cycle_execution_state.json")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
now = datetime.now(timezone.utc).isoformat()

def backup(path):
    if path.exists():
        b = path.with_suffix(path.suffix + f".before_RESET_{ASSET}_{stamp}.bak")
        shutil.copy2(path, b)
        print(f"BACKUP {path} -> {b}")

def load_json(path):
    return json.loads(path.read_text(errors="ignore"))

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

print("=" * 130)
print(f"RESET LOCAL {ASSET} ONLY — broker déjà plat obligatoire")
print("=" * 130)
print("UTC:", now)

backup(cycle_path)
backup(exec_path)

# cycle_state
if cycle_path.exists():
    data = load_json(cycle_path)
    assets = data.setdefault("assets", {})
    old_state = assets.get(ASSET, {})

    assets[ASSET] = {
        "status": "IDLE",
        "cycle": {},
        "manual_reset_utc": now,
        "manual_reset_reason": f"LOCAL_GHOST_RESET_{ASSET}_BROKER_FLAT",
        "old_state_before_reset": old_state,
    }

    data["updated_utc"] = now
    save_json(cycle_path, data)
    print(f"CYCLE_STATE: {ASSET} -> IDLE")

# execution_state
if exec_path.exists():
    data = load_json(exec_path)

    archive = data.setdefault("manual_flattened_before_patch", {})
    archive[f"{ASSET}_{stamp}"] = {
        "utc": now,
        "asset": ASSET,
        "reason": f"LOCAL_GHOST_RESET_{ASSET}_BROKER_FLAT",
        "old_active": data.get("active", {}).get(ASSET) if isinstance(data.get("active"), dict) else None,
        "old_pending": data.get("pending", {}).get(ASSET) if isinstance(data.get("pending"), dict) else None,
        "old_working_orders": data.get("working_orders", {}).get(ASSET) if isinstance(data.get("working_orders"), dict) else None,
        "old_orders": data.get("orders", {}).get(ASSET) if isinstance(data.get("orders"), dict) else None,
        "old_positions": data.get("positions", {}).get(ASSET) if isinstance(data.get("positions"), dict) else None,
    }

    for key in ["active", "pending", "working_orders", "orders", "positions"]:
        if isinstance(data.get(key), dict) and ASSET in data[key]:
            data[key].pop(ASSET, None)
            print(f"EXEC_STATE: supprimé {ASSET} de {key}")

    data["updated_utc"] = now
    data["last_cleanup_reason"] = f"LOCAL_GHOST_RESET_{ASSET}_BROKER_FLAT"
    save_json(exec_path, data)

print("=" * 130)
print(f"RESET LOCAL {ASSET} TERMINÉ")
print("=" * 130)
