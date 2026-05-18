# BOT_PIVOT_06F_execution.py
# Module 06F — exécution Capital.com verrouillée en DRY_RUN
# SEND_REAL_ORDERS = False => aucun ordre réel envoyé.

import os, json, time, argparse
from pathlib import Path
from datetime import datetime, timezone
import requests

import BOT_PIVOT_00_config as CFG

SEND_REAL_ORDERS = False

ENV_FILE = Path(".env")
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
MARKET_DIR = CFG.DATA_DIR / "markets"
EXEC_DIR = CFG.DATA_DIR / "execution"
OWNED_DEALS_FILE = EXEC_DIR / "bot_pivot_owned_deals.json"
EVENTS_FILE = EXEC_DIR / "execution_events.jsonl"

def utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def event(e):
    e["event_utc"] = utc()
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

def load_env():
    if not ENV_FILE.exists():
        raise FileNotFoundError(".env introuvable")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def login():
    api_key = os.environ.get("CAPITAL_API_KEY")
    identifier = os.environ.get("CAPITAL_IDENTIFIER") or os.environ.get("CAPITAL_LOGIN") or os.environ.get("CAPITAL_EMAIL")
    password = os.environ.get("CAPITAL_PASSWORD")

    if not api_key or not identifier or not password:
        raise RuntimeError("Variables .env manquantes")

    r = requests.post(
        f"{CFG.BASE_URL}/api/v1/session",
        headers={"X-CAP-API-KEY": api_key, "Content-Type": "application/json"},
        json={"identifier": identifier, "password": password, "encryptedPassword": False},
        timeout=15,
    )

    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login refusé HTTP {r.status_code} : {r.text[:300]}")

    return {
        "X-CAP-API-KEY": api_key,
        "CST": r.headers.get("CST"),
        "X-SECURITY-TOKEN": r.headers.get("X-SECURITY-TOKEN"),
        "Content-Type": "application/json",
    }

def api_get(headers, endpoint):
    r = requests.get(f"{CFG.BASE_URL}{endpoint}", headers=headers, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

def api_post(headers, endpoint, payload):
    if not SEND_REAL_ORDERS:
        return 0, {"DRY_RUN": True, "endpoint": endpoint, "payload": payload}

    r = requests.post(f"{CFG.BASE_URL}{endpoint}", headers=headers, json=payload, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

def api_delete(headers, endpoint):
    if not SEND_REAL_ORDERS:
        return 0, {"DRY_RUN": True, "endpoint": endpoint}

    r = requests.delete(f"{CFG.BASE_URL}{endpoint}", headers=headers, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

def load_signals():
    data = load_json(SIGNALS_FILE, {"signals": []})
    return {s["asset"]: s for s in data.get("signals", []) if s.get("asset")}

def get_market(asset):
    f = MARKET_DIR / f"market_{asset}.json"
    if not f.exists():
        return {"status": "UNKNOWN", "min_size": None}

    data = load_json(f, {})
    market = data.get("market", data)
    rules = market.get("dealingRules", {})
    instrument = market.get("instrument", {})
    snapshot = market.get("snapshot", {})

    min_deal = rules.get("minDealSize")
    if isinstance(min_deal, dict):
        min_size = min_deal.get("value")
    else:
        min_size = min_deal or instrument.get("minDealSize")

    status = snapshot.get("marketStatus") or market.get("marketStatus") or instrument.get("marketStatus") or "UNKNOWN"

    return {
        "status": status,
        "min_size": float(min_size) if min_size is not None else None,
    }

def size_for(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        base = float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01))
        mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
        return base * mult

def valid_signal(s):
    if not s:
        return False, "aucun signal"
    if s.get("decision") not in ["BUY", "SELL"]:
        return False, "pas BUY/SELL"
    if not s.get("spread_ok"):
        return False, "spread refusé"
    if s.get("mid") is None:
        return False, "prix manquant"

    age = float(s.get("age_sec", 999999))
    max_age = float(getattr(CFG, "MAX_TICK_AGE_SEC", 12))
    if age > max_age:
        return False, f"tick trop ancien {age:.1f}s>{max_age:.1f}s"

    return True, "OK"

def broker_positions(headers):
    status, data = api_get(headers, "/api/v1/positions")
    return status, data.get("positions", []), data

def position_epic(item):
    p = item.get("position", {}) or {}
    m = item.get("market", {}) or {}
    return m.get("epic") or p.get("epic")

def position_deal_id(item):
    p = item.get("position", {}) or {}
    return p.get("dealId")

def has_broker_position(asset, positions):
    for item in positions:
        if position_epic(item) == asset:
            return True
    return False

def build_open_payload(asset, direction, size):
    return {
        "epic": asset,
        "direction": direction,
        "size": size,
        "guaranteedStop": False,
    }

def plan_open(headers, assets):
    signals = load_signals()
    _, positions, _ = broker_positions(headers)

    print()
    print("=" * 150)
    print("06F — PLAN OPEN — DRY_RUN VERROUILLÉ")
    print("=" * 150)
    print("SEND_REAL_ORDERS =", SEND_REAL_ORDERS)
    print("-" * 150)
    print("ACTIF      | ACTION      | MARKET    | DIR  | SIZE       | RAISON / PAYLOAD")
    print("-" * 150)

    for asset in assets:
        market = get_market(asset)
        size = size_for(asset, 1)
        sig = signals.get(asset)

        if market["status"] != "TRADEABLE":
            print(f"{asset:10s} | SKIP        | {market['status']:9s} | --   | {size:<10.6f} | marché non tradeable")
            continue

        if market["min_size"] is None or size < market["min_size"]:
            print(f"{asset:10s} | SKIP        | {market['status']:9s} | --   | {size:<10.6f} | taille invalide min={market['min_size']}")
            continue

        if has_broker_position(asset, positions):
            print(f"{asset:10s} | SKIP        | {market['status']:9s} | --   | {size:<10.6f} | position broker déjà ouverte")
            continue

        ok, reason = valid_signal(sig)
        if not ok:
            print(f"{asset:10s} | WAIT        | {market['status']:9s} | --   | {size:<10.6f} | {reason}")
            continue

        direction = sig["decision"]
        payload = build_open_payload(asset, direction, size)

        status, data = api_post(headers, "/api/v1/positions", payload)

        event({
            "event": "OPEN_ATTEMPT",
            "asset": asset,
            "dry_run": not SEND_REAL_ORDERS,
            "status": status,
            "payload": payload,
            "response": data,
        })

        print(f"{asset:10s} | OPEN_PLAN   | {market['status']:9s} | {direction:4s} | {size:<10.6f} | {json.dumps(payload, ensure_ascii=False)}")

        # En réel plus tard : dealReference puis confirm, puis stockage dealId.
        if SEND_REAL_ORDERS:
            deal_ref = data.get("dealReference")
            if deal_ref:
                c_status, confirm = api_get(headers, f"/api/v1/confirms/{deal_ref}")
                owned = load_json(OWNED_DEALS_FILE, {"deals": []})
                owned["deals"].append({
                    "asset": asset,
                    "direction": direction,
                    "size": size,
                    "dealReference": deal_ref,
                    "confirm_status": c_status,
                    "confirm": confirm,
                    "created_utc": utc(),
                })
                save_json(OWNED_DEALS_FILE, owned)

    print("=" * 150)
    print("Aucun ordre envoyé tant que SEND_REAL_ORDERS=False.")

def show_positions(headers):
    status, positions, data = broker_positions(headers)

    print()
    print("=" * 120)
    print("06F — POSITIONS BROKER")
    print("=" * 120)
    print("HTTP :", status)

    if not positions:
        print("Aucune position ouverte.")
        print("=" * 120)
        return

    print("EPIC       | DIR  | SIZE       | LEVEL        | DEAL ID")
    print("-" * 120)

    for item in positions:
        p = item.get("position", {}) or {}
        epic = position_epic(item) or "--"
        direction = p.get("direction", "--")
        size = p.get("size", "--")
        level = p.get("level", p.get("openLevel", "--"))
        deal_id = p.get("dealId", "--")

        print(f"{str(epic)[:10]:10s} | {str(direction)[:4]:4s} | {str(size)[:10]:10s} | {str(level)[:12]:12s} | {deal_id}")

    print("=" * 120)

def close_owned(headers):
    owned = load_json(OWNED_DEALS_FILE, {"deals": []})
    deals = owned.get("deals", [])

    print()
    print("=" * 140)
    print("06F — CLOSE OWNED — DRY_RUN VERROUILLÉ")
    print("=" * 140)
    print("SEND_REAL_ORDERS =", SEND_REAL_ORDERS)

    if not deals:
        print("Aucun deal BOT-PIVOT enregistré. Rien à fermer.")
        print("=" * 140)
        return

    for d in deals:
        deal_id = d.get("dealId") or d.get("confirm", {}).get("dealId")
        asset = d.get("asset", "--")

        if not deal_id:
            print(f"{asset:10s} | SKIP | pas de dealId confirmé")
            continue

        status, data = api_delete(headers, f"/api/v1/positions/{deal_id}")

        event({
            "event": "CLOSE_ATTEMPT",
            "asset": asset,
            "dealId": deal_id,
            "dry_run": not SEND_REAL_ORDERS,
            "status": status,
            "response": data,
        })

        print(f"{asset:10s} | CLOSE_PLAN | dealId={deal_id} | response={json.dumps(data, ensure_ascii=False)[:200]}")

    print("=" * 140)
    print("Aucune fermeture envoyée tant que SEND_REAL_ORDERS=False.")

def parse_assets(raw):
    if raw.upper() == "ALL":
        return list(CFG.ASSETS)
    return [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["positions", "plan-open", "close-owned"], default="plan-open")
    parser.add_argument("--assets", default="ALL")
    args = parser.parse_args()

    EXEC_DIR.mkdir(parents=True, exist_ok=True)

    # Sécurité anti-429 :
    # si on demande close-owned mais qu'aucun deal BOT-PIVOT n'existe,
    # on ne crée pas de session Capital.com inutilement.
    if args.mode == "close-owned":
        owned = load_json(OWNED_DEALS_FILE, {"deals": []})
        if not owned.get("deals"):
            print()
            print("=" * 120)
            print("06F — CLOSE OWNED")
            print("=" * 120)
            print("Aucun deal BOT-PIVOT enregistré. Aucun login nécessaire. Rien à fermer.")
            print("=" * 120)
            return

    load_env()
    headers = login()

    assets = parse_assets(args.assets)

    if args.mode == "positions":
        show_positions(headers)
    elif args.mode == "close-owned":
        close_owned(headers)
    else:
        plan_open(headers, assets)

if __name__ == "__main__":
    main()
