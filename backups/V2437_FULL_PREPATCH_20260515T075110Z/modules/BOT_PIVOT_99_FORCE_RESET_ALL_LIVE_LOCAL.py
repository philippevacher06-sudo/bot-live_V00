#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
now = datetime.now(timezone.utc).isoformat()

cycle_path = Path("data/cycles/cycle_state.json")
exec_path = Path("data/execution/cycle_execution_state.json")

ASSETS = [
    "US500","US100","US30","DE40","FR40","UK100","J225",
    "EURUSD","GBPUSD","USDJPY","EURJPY",
    "GOLD","SILVER","OIL_CRUDE","BTCUSD","ETHUSD"
]

LIVE_KEYS = [
    "active",
    "pending",
    "working_orders",
    "orders",
    "positions",
    "open",
    "baskets",
    "basket",
]

def backup(path):
    if path.exists():
        dst = path.with_suffix(path.suffix + f".before_FORCE_RESET_ALL_LIVE_{stamp}.bak")
        shutil.copy2(path, dst)
        print(f"BACKUP {path} -> {dst}")

def load(path):
    return json.loads(path.read_text(errors="ignore"))

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

print("=" * 140)
print("FORCE RESET ALL LIVE LOCAL STATE")
print("=" * 140)
print("Aucun appel broker. Aucun ordre envoyé. À utiliser uniquement après POS=0 / PEND=0.")
print("UTC:", now)
print("=" * 140)

backup(cycle_path)
backup(exec_path)

# 1. Cycle state : tous les actifs à IDLE
if cycle_path.exists():
    data = load(cycle_path)
    old_assets = data.get("assets", {})

    assets = data.setdefault("assets", {})
    for asset in ASSETS:
        old = old_assets.get(asset, {})
        assets[asset] = {
            "status": "IDLE",
            "cycle": {},
            "manual_reset_utc": now,
            "manual_reset_reason": "FORCE_RESET_ALL_LIVE_BROKER_FLAT",
            "old_state_before_reset": old,
        }

    data["updated_utc"] = now
    data["manual_reset_utc"] = now
    data["manual_reset_reason"] = "FORCE_RESET_ALL_LIVE_BROKER_FLAT"

    save(cycle_path, data)
    print("CYCLE_STATE: tous les actifs -> IDLE")

# 2. Execution state : vider les conteneurs vivants
if exec_path.exists():
    data = load(exec_path)

    archive = data.setdefault("manual_flattened_before_patch", {})
    archive[f"FORCE_RESET_ALL_LIVE_{stamp}"] = {
        "utc": now,
        "reason": "FORCE_RESET_ALL_LIVE_BROKER_FLAT",
        "live_state_before_reset": {
            key: data.get(key)
            for key in LIVE_KEYS
            if key in data
        },
    }

    for key in LIVE_KEYS:
        if key in data:
            if isinstance(data[key], dict):
                print(f"EXEC_STATE: {key} dict vidé, len_before={len(data[key])}")
                data[key] = {}
            elif isinstance(data[key], list):
                print(f"EXEC_STATE: {key} list vidée, len_before={len(data[key])}")
                data[key] = []
            else:
                print(f"EXEC_STATE: {key} remplacé par dict vide, type_before={type(data[key]).__name__}")
                data[key] = {}

    data["updated_utc"] = now
    data["reset_utc"] = now
    data["reset_reason"] = "FORCE_RESET_ALL_LIVE_BROKER_FLAT"
    data["last_cleanup_reason"] = "FORCE_RESET_ALL_LIVE_BROKER_FLAT"

    save(exec_path, data)
    print("EXEC_STATE: états vivants vidés")

print("=" * 140)
print("RESET LOCAL COMPLET TERMINÉ")
print("=" * 140)
