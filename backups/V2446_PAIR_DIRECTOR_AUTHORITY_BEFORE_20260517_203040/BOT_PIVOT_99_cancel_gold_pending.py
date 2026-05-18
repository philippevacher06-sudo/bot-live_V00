#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime, timezone

BASE_URL = os.getenv("CAPITAL_BASE_URL", "https://demo-api-capital.backend-capital.com/api/v1")

def load_dotenv_silent(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

def first_env(*names):
    for n in names:
        v = os.getenv(n)
        if v:
            return v
    return None

def request_json(method, path, headers=None, body=None):
    url = BASE_URL.rstrip("/") + path
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    for k, v in (headers or {}).items():
        req.add_header(k, v)

    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            out = json.loads(raw) if raw.strip() else {}
            return r.status, dict(r.headers), out
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            out = json.loads(raw) if raw.strip() else {}
        except Exception:
            out = {"raw": raw}
        return e.code, dict(e.headers), out

def login():
    load_dotenv_silent()

    api_key = first_env("CAPITAL_API_KEY", "X_CAP_API_KEY", "API_KEY")
    identifier = first_env("CAPITAL_IDENTIFIER", "CAPITAL_LOGIN", "CAPITAL_EMAIL", "IDENTIFIER", "LOGIN")
    password = first_env("CAPITAL_PASSWORD", "CAPITAL_API_PASSWORD", "PASSWORD")

    if not api_key or not identifier or not password:
        raise SystemExit("ERREUR: identifiants Capital.com absents. Ne pas afficher le .env ; vérifier seulement qu'il existe.")

    status, headers, data = request_json(
        "POST",
        "/session",
        headers={"X-CAP-API-KEY": api_key},
        body={"identifier": identifier, "password": password},
    )

    if status not in (200, 201):
        raise SystemExit(f"LOGIN_FAIL HTTP {status}: {data}")

    cst = headers.get("CST")
    token = headers.get("X-SECURITY-TOKEN")

    if not cst or not token:
        raise SystemExit("LOGIN_FAIL: CST ou X-SECURITY-TOKEN manquant.")

    return {
        "X-CAP-API-KEY": api_key,
        "CST": cst,
        "X-SECURITY-TOKEN": token,
    }

def get_nested(d, *paths):
    for path in paths:
        cur = d
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok:
            return cur
    return None

def order_asset_text(order):
    parts = []
    for path in [
        ("workingOrderData", "epic"),
        ("marketData", "epic"),
        ("epic",),
        ("instrumentName",),
        ("marketData", "instrumentName"),
        ("marketData", "marketName"),
        ("marketName",),
    ]:
        v = get_nested(order, path)
        if v is not None:
            parts.append(str(v))
    return " ".join(parts).upper()

def order_deal_id(order):
    return get_nested(
        order,
        ("workingOrderData", "dealId"),
        ("dealId",),
        ("id",),
    )

def order_level(order):
    return get_nested(
        order,
        ("workingOrderData", "level"),
        ("workingOrderData", "orderLevel"),
        ("level",),
        ("orderLevel",),
    )

def order_direction(order):
    return get_nested(
        order,
        ("workingOrderData", "direction"),
        ("direction",),
    )

def order_size(order):
    return get_nested(
        order,
        ("workingOrderData", "size"),
        ("size",),
    )

def list_working_orders(headers):
    status, h, data = request_json("GET", "/workingorders", headers=headers)
    if status != 200:
        raise SystemExit(f"GET_WORKINGORDERS_FAIL HTTP {status}: {data}")

    orders = data.get("workingOrders")
    if orders is None:
        orders = data.get("workingorders")
    if orders is None:
        orders = data.get("orders")
    if orders is None:
        orders = []

    return orders

def is_gold_order(order):
    txt = order_asset_text(order)
    # Filtre volontairement strict : on accepte GOLD ou XAU dans l'identification broker.
    return "GOLD" in txt or "XAU" in txt

def delete_order(headers, deal_id):
    status, h, data = request_json("DELETE", f"/workingorders/{deal_id}", headers=headers)
    return status, data

def main():
    print("=" * 140)
    print("BOT_PIVOT_99_cancel_gold_pending.py — ANNULATION FORCÉE DES PENDING GOLD")
    print("=" * 140)
    print("Aucune position n'est fermée par ce script. Il annule seulement les working orders GOLD.")
    print("Date UTC:", datetime.now(timezone.utc).isoformat())
    print("")

    headers = login()
    orders = list_working_orders(headers)

    print(f"Total working orders broker: {len(orders)}")

    if not orders:
        print("Aucun pending broker à annuler.")
        return

    gold_orders = []
    non_gold_orders = []

    for o in orders:
        if is_gold_order(o):
            gold_orders.append(o)
        else:
            non_gold_orders.append(o)

    print(f"Working orders GOLD détectés     : {len(gold_orders)}")
    print(f"Working orders non-GOLD détectés : {len(non_gold_orders)}")
    print("")

    if non_gold_orders:
        print("ABORT: des pending non-GOLD existent. Je refuse d'annuler à l'aveugle.")
        for o in non_gold_orders:
            print("NON_GOLD:", order_asset_text(o), "dealId=", order_deal_id(o), "dir=", order_direction(o), "size=", order_size(o), "level=", order_level(o))
        raise SystemExit(2)

    if not gold_orders:
        print("Aucun pending GOLD détecté.")
        return

    print("Pending GOLD à annuler :")
    for o in gold_orders:
        print(
            "GOLD_PENDING",
            "dealId=", order_deal_id(o),
            "dir=", order_direction(o),
            "size=", order_size(o),
            "level=", order_level(o),
            "asset_text=", order_asset_text(o),
        )

    print("")
    print("Annulation en cours...")
    ok = 0
    fail = 0

    for o in gold_orders:
        deal_id = order_deal_id(o)
        if not deal_id:
            print("SKIP: dealId introuvable pour", o)
            fail += 1
            continue

        status, data = delete_order(headers, deal_id)
        if status in (200, 201, 202, 204):
            print(f"CANCEL_OK dealId={deal_id} HTTP={status} response={data}")
            ok += 1
        else:
            print(f"CANCEL_FAIL dealId={deal_id} HTTP={status} response={data}")
            fail += 1

    print("")
    print("=" * 140)
    print(f"RÉSULTAT: cancel_ok={ok} cancel_fail={fail}")
    print("=" * 140)

    # Relecture broker
    orders_after = list_working_orders(headers)
    gold_after = [o for o in orders_after if is_gold_order(o)]
    print(f"Working orders broker après annulation: {len(orders_after)}")
    print(f"Working orders GOLD après annulation  : {len(gold_after)}")

    if gold_after:
        print("ATTENTION: il reste des pending GOLD:")
        for o in gold_after:
            print(
                "REMAINING_GOLD",
                "dealId=", order_deal_id(o),
                "dir=", order_direction(o),
                "size=", order_size(o),
                "level=", order_level(o),
            )

if __name__ == "__main__":
    main()
