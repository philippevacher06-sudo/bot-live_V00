#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import argparse
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
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", errors="ignore")
            try:
                out = json.loads(raw) if raw.strip() else {}
            except Exception:
                out = {"raw": raw}
            return r.status, dict(r.headers), out
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            out = json.loads(raw) if raw.strip() else {}
        except Exception:
            out = {"raw": raw}
        return e.code, dict(e.headers), out
    except Exception as exc:
        return 0, {}, {"error": str(exc)}

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

def g(d, *path):
    cur = d
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return None
    return cur

def first_value(d, paths):
    for path in paths:
        v = g(d, *path)
        if v is not None:
            return v
    return None

def short_id(v):
    if not v:
        return "?"
    s = str(v)
    if len(s) <= 14:
        return s
    return s[:8] + "..." + s[-4:]

def list_positions(headers):
    status, h, data = request_json("GET", "/positions", headers=headers)
    if status != 200:
        raise SystemExit(f"GET /positions FAIL HTTP={status} data={data}")

    rows = data.get("positions")
    if rows is None:
        rows = data.get("position")
    if rows is None:
        rows = []

    return rows

def list_working_orders(headers):
    status, h, data = request_json("GET", "/workingorders", headers=headers)
    if status != 200:
        raise SystemExit(f"GET /workingorders FAIL HTTP={status} data={data}")

    rows = data.get("workingOrders")
    if rows is None:
        rows = data.get("workingorders")
    if rows is None:
        rows = data.get("orders")
    if rows is None:
        rows = []

    return rows

def position_deal_id(row):
    return first_value(row, [
        ("position", "dealId"),
        ("dealId",),
        ("id",),
    ])

def position_text(row):
    vals = []
    paths = [
        ("market", "epic"),
        ("market", "instrumentName"),
        ("market", "marketName"),
        ("epic",),
        ("instrumentName",),
        ("marketName",),
        ("position", "direction"),
        ("position", "size"),
        ("position", "level"),
        ("position", "upl"),
    ]
    for p in paths:
        v = g(row, *p)
        if v is not None:
            vals.append(str(v))
    return " ".join(vals)

def order_deal_id(row):
    return first_value(row, [
        ("workingOrderData", "dealId"),
        ("dealId",),
        ("id",),
    ])

def order_text(row):
    vals = []
    paths = [
        ("workingOrderData", "epic"),
        ("marketData", "epic"),
        ("marketData", "instrumentName"),
        ("marketData", "marketName"),
        ("epic",),
        ("instrumentName",),
        ("marketName",),
        ("workingOrderData", "direction"),
        ("workingOrderData", "size"),
        ("workingOrderData", "level"),
        ("workingOrderData", "orderLevel"),
    ]
    for p in paths:
        v = g(row, *p)
        if v is not None:
            vals.append(str(v))
    return " ".join(vals)

def cancel_working_order(headers, deal_id):
    return request_json("DELETE", f"/workingorders/{deal_id}", headers=headers)

def close_position(headers, deal_id):
    return request_json("DELETE", f"/positions/{deal_id}", headers=headers)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--yes", action="store_true", help="Exécute vraiment les annulations/fermetures.")
    parser.add_argument("--passes", type=int, default=3, help="Nombre de passages de sécurité.")
    parser.add_argument("--sleep", type=float, default=1.5, help="Pause entre les passages.")
    args = parser.parse_args()

    print("=" * 150)
    print("BOT_PIVOT_99_TOTAL_FLATTEN_BROKER — RESET TOTAL BROKER")
    print("=" * 150)
    print("Action : annuler TOUS les working orders + fermer TOUTES les positions visibles sur le compte Capital.com.")
    print("Mode   :", "EXECUTION RÉELLE" if args.yes else "DRY-RUN / LECTURE SEULE")
    print("UTC    :", datetime.now(timezone.utc).isoformat())
    print("=" * 150)

    headers = login()

    total_cancel_ok = 0
    total_cancel_fail = 0
    total_close_ok = 0
    total_close_fail = 0

    for p in range(1, args.passes + 1):
        print("")
        print("-" * 150)
        print(f"PASSAGE {p}/{args.passes}")
        print("-" * 150)

        positions = list_positions(headers)
        orders = list_working_orders(headers)

        print(f"Positions ouvertes broker : {len(positions)}")
        for row in positions:
            deal_id = position_deal_id(row)
            print(f"POSITION dealId={short_id(deal_id)} | {position_text(row)}")

        print(f"Working orders broker     : {len(orders)}")
        for row in orders:
            deal_id = order_deal_id(row)
            print(f"PENDING  dealId={short_id(deal_id)} | {order_text(row)}")

        if not args.yes:
            print("")
            print("DRY-RUN : aucune action envoyée. Relancer avec --yes pour exécuter.")
            return

        # 1. Annuler les pending d'abord
        for row in orders:
            deal_id = order_deal_id(row)
            if not deal_id:
                print(f"CANCEL_SKIP dealId introuvable | {order_text(row)}")
                total_cancel_fail += 1
                continue

            status, h, data = cancel_working_order(headers, deal_id)
            if status in (200, 201, 202, 204):
                print(f"CANCEL_OK   dealId={short_id(deal_id)} HTTP={status}")
                total_cancel_ok += 1
            else:
                print(f"CANCEL_FAIL dealId={short_id(deal_id)} HTTP={status} data={data}")
                total_cancel_fail += 1

        # 2. Fermer les positions ensuite
        for row in positions:
            deal_id = position_deal_id(row)
            if not deal_id:
                print(f"CLOSE_SKIP dealId introuvable | {position_text(row)}")
                total_close_fail += 1
                continue

            status, h, data = close_position(headers, deal_id)
            if status in (200, 201, 202, 204):
                print(f"CLOSE_OK   dealId={short_id(deal_id)} HTTP={status}")
                total_close_ok += 1
            else:
                print(f"CLOSE_FAIL dealId={short_id(deal_id)} HTTP={status} data={data}")
                total_close_fail += 1

        time.sleep(args.sleep)

    print("")
    print("=" * 150)
    print("RÉSULTAT ACTIONS")
    print("=" * 150)
    print(f"cancel_ok   : {total_cancel_ok}")
    print(f"cancel_fail : {total_cancel_fail}")
    print(f"close_ok    : {total_close_ok}")
    print(f"close_fail  : {total_close_fail}")

    positions_after = list_positions(headers)
    orders_after = list_working_orders(headers)

    print("")
    print("=" * 150)
    print("ÉTAT BROKER FINAL")
    print("=" * 150)
    print(f"Positions ouvertes restantes : {len(positions_after)}")
    for row in positions_after:
        print(f"REMAINING_POSITION dealId={short_id(position_deal_id(row))} | {position_text(row)}")

    print(f"Working orders restants      : {len(orders_after)}")
    for row in orders_after:
        print(f"REMAINING_PENDING dealId={short_id(order_deal_id(row))} | {order_text(row)}")

    if len(positions_after) == 0 and len(orders_after) == 0:
        print("")
        print("BROKER_FLAT_OK : POS=0 / PEND=0")
    else:
        print("")
        print("BROKER_NOT_FLAT : il reste des positions ou pending. Ne pas relancer le bot.")

if __name__ == "__main__":
    main()
