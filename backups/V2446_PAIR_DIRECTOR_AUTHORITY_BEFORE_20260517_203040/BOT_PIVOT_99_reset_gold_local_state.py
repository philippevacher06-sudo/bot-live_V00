#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

ASSET = "GOLD"

cycle_path = Path("data/cycles/cycle_state.json")
exec_path = Path("data/execution/cycle_execution_state.json")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

def backup(path):
    if path.exists():
        b = path.with_suffix(path.suffix + f".before_manual_gold_reset_{stamp}.bak")
        shutil.copy2(path, b)
        print(f"BACKUP {path} -> {b}")

def load(path):
    return json.loads(path.read_text(errors="ignore"))

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

print("=" * 120)
print("RESET LOCAL STATE GOLD — À UTILISER SEULEMENT APRÈS POS=0 ET PEND=0 BROKER")
print("=" * 120)

backup(cycle_path)
backup(exec_path)

now = datetime.now(timezone.utc).isoformat()

# cycle_state
if cycle_path.exists():
    data = load(cycle_path)
    assets = data.setdefault("assets", {})
    state = assets.get(ASSET)

    if isinstance(state, dict):
        state["status"] = "IDLE"
        state["cycle"] = {}
        state["manual_reset_reason"] = "MANUAL_GOLD_PENDING_CANCELLED_BEFORE_V2432_PATCH"
        state["manual_reset_utc"] = now
        data["updated_utc"] = now
        print("CYCLE_STATE: GOLD -> IDLE")
    else:
        print("CYCLE_STATE: GOLD absent ou format inattendu.")

    save(cycle_path, data)

# execution_state
if exec_path.exists():
    data = load(exec_path)

    active = data.get("active")
    if isinstance(active, dict) and ASSET in active:
        removed = active.pop(ASSET)
        data.setdefault("manual_flattened_before_patch", {})
        data["manual_flattened_before_patch"][ASSET] = {
            "utc": now,
            "reason": "MANUAL_GOLD_PENDING_CANCELLED_BEFORE_V2432_PATCH",
            "removed_active": removed,
        }
        print("EXEC_STATE: GOLD retiré de active")
    else:
        print("EXEC_STATE: GOLD non présent dans active.")

    data["updated_utc"] = now
    data["reset_reason"] = "MANUAL_GOLD_PENDING_CANCELLED_BEFORE_V2432_PATCH"
    data["reset_utc"] = now
    save(exec_path, data)

print("=" * 120)
print("RESET LOCAL GOLD TERMINÉ")
print("=" * 120)
