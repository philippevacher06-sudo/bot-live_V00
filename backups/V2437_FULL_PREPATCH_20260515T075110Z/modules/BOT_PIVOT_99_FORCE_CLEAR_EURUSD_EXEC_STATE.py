#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

ASSET = "EURUSD"
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
now = datetime.now(timezone.utc).isoformat()

cycle_path = Path("data/cycles/cycle_state.json")
exec_path = Path("data/execution/cycle_execution_state.json")

LIVE_KEYS = ["active", "pending", "working_orders", "orders", "positions"]

def backup(path):
    if path.exists():
        dst = path.with_suffix(path.suffix + f".before_FORCE_CLEAR_{ASSET}_{stamp}.bak")
        shutil.copy2(path, dst)
        print(f"BACKUP {path} -> {dst}")

def load(path):
    return json.loads(path.read_text(errors="ignore"))

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def contains_asset(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).upper() == ASSET:
                return True
            if isinstance(v, str) and ASSET in v.upper():
                return True
            if contains_asset(v):
                return True
    elif isinstance(obj, list):
        return any(contains_asset(x) for x in obj)
    elif isinstance(obj, str):
        return ASSET in obj.upper()
    return False

def clear_asset_from_container(container):
    removed = []

    if isinstance(container, dict):
        for k in list(container.keys()):
            v = container[k]
            if str(k).upper() == ASSET or contains_asset(v):
                removed.append((k, v))
                container.pop(k, None)

    elif isinstance(container, list):
        kept = []
        for item in container:
            if contains_asset(item):
                removed.append(item)
            else:
                kept.append(item)
        container[:] = kept

    return removed

print("=" * 140)
print(f"FORCE CLEAR LOCAL EXEC STATE — {ASSET}")
print("=" * 140)
print("UTC:", now)
print("Action: nettoyage local uniquement. Aucun appel broker. Aucun ordre envoyé.")
print("=" * 140)

backup(cycle_path)
backup(exec_path)

# 1. cycle_state : remettre EURUSD à IDLE
if cycle_path.exists():
    data = load(cycle_path)
    assets = data.setdefault("assets", {})
    old = assets.get(ASSET)

    assets[ASSET] = {
        "status": "IDLE",
        "cycle": {},
        "manual_reset_utc": now,
        "manual_reset_reason": f"FORCE_CLEAR_{ASSET}_BROKER_FLAT",
        "old_state_before_reset": old,
    }

    data["updated_utc"] = now
    save(cycle_path, data)
    print(f"CYCLE_STATE: {ASSET} -> IDLE")

# 2. execution_state : supprimer EURUSD des conteneurs vivants
if exec_path.exists():
    data = load(exec_path)

    archive = data.setdefault("manual_flattened_before_patch", {})
    archive[f"{ASSET}_FORCE_CLEAR_{stamp}"] = {
        "utc": now,
        "asset": ASSET,
        "reason": f"FORCE_CLEAR_{ASSET}_BROKER_FLAT",
        "live_keys_before": {
            key: data.get(key)
            for key in LIVE_KEYS
            if key in data
        },
    }

    total_removed = 0

    for key in LIVE_KEYS:
        if key in data:
            removed = clear_asset_from_container(data[key])
            if removed:
                total_removed += len(removed)
                print(f"EXEC_STATE: supprimé {len(removed)} entrée(s) EURUSD dans {key}")

    data["updated_utc"] = now
    data["last_cleanup_reason"] = f"FORCE_CLEAR_{ASSET}_BROKER_FLAT"
    data["reset_reason"] = f"FORCE_CLEAR_{ASSET}_BROKER_FLAT"
    data["reset_utc"] = now

    save(exec_path, data)
    print(f"EXEC_STATE: total entrées supprimées = {total_removed}")

print("=" * 140)
print("FORCE CLEAR TERMINÉ")
print("=" * 140)
