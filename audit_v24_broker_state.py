#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit broker/state BOT-PIVOT V24.1 sans afficher .env."""
import json
from pathlib import Path
import requests
import BOT_PIVOT_06G2_execution_secure as G

headers = G.login()
base = getattr(G, "BASE_URL", "https://demo-api-capital.backend-capital.com/api/v1").rstrip("/")

positions = requests.get(base + "/positions", headers=headers, timeout=20).json().get("positions", []) or []
orders = requests.get(base + "/workingorders", headers=headers, timeout=20).json().get("workingOrders", []) or []

print("="*80)
print("POSITIONS BROKER")
print("="*80)
if not positions:
    print("Aucune position broker ouverte")
else:
    for p in positions:
        m = p.get("market", {}) or {}
        pos = p.get("position", {}) or {}
        print(json.dumps({
            "epic": m.get("epic"),
            "name": m.get("instrumentName"),
            "dealId": pos.get("dealId"),
            "direction": pos.get("direction"),
            "size": pos.get("size"),
            "level": pos.get("level"),
            "upl": pos.get("upl"),
            "createdDate": pos.get("createdDate"),
        }, indent=2, ensure_ascii=False))

print()
print("="*80)
print("WORKING ORDERS BROKER")
print("="*80)
if not orders:
    print("Aucun ordre pending broker")
else:
    for w in orders:
        wo = w.get("workingOrderData", {}) or {}
        m = w.get("marketData", {}) or {}
        print(json.dumps({
            "epic": wo.get("epic") or m.get("epic"),
            "name": m.get("instrumentName"),
            "dealId": wo.get("dealId"),
            "direction": wo.get("direction"),
            "size": wo.get("orderSize"),
            "level": wo.get("orderLevel"),
            "stopDistance": wo.get("stopDistance"),
            "createdDate": wo.get("createdDate"),
        }, indent=2, ensure_ascii=False))

print()
print("="*80)
print("LOCAL STATE / EXEC STATE")
print("="*80)
for label, path in [("STATE", G.B.STATE_FILE), ("EXEC", G.B.EXEC_STATE_FILE)]:
    try:
        data = json.loads(Path(path).read_text())
    except Exception as e:
        print(label, "ERREUR LECTURE", e)
        continue

    if label == "STATE":
        active = {a:s for a,s in data.get("assets", {}).items() if s.get("status") != "IDLE"}
        print("STATE actifs non-IDLE =", len(active), list(active.keys()))
    else:
        active = data.get("active", {}) or {}
        print("EXEC active =", len(active), list(active.keys()))
