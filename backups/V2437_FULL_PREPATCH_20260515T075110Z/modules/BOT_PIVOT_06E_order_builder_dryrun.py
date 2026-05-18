# BOT_PIVOT_06E_order_builder_dryrun.py
# Construction des ordres en DRY_RUN sur les 16 actifs.
# Aucun ordre envoyé.

import json
from datetime import datetime, timezone
import BOT_PIVOT_00_config as CFG

SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
MARKET_DIR = CFG.DATA_DIR / "markets"

def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def get_market(asset):
    f = MARKET_DIR / f"market_{asset}.json"
    if not f.exists():
        return {"status": "UNKNOWN", "min_size": None}

    data = json.loads(f.read_text(encoding="utf-8"))
    market = data.get("market", data)
    rules = market.get("dealingRules", {})
    instrument = market.get("instrument", {})
    snapshot = market.get("snapshot", {})

    min_deal = rules.get("minDealSize")
    if isinstance(min_deal, dict):
        min_size = min_deal.get("value")
    else:
        min_size = min_deal or instrument.get("minDealSize")

    status = (
        snapshot.get("marketStatus")
        or market.get("marketStatus")
        or instrument.get("marketStatus")
        or "UNKNOWN"
    )

    return {
        "status": status,
        "min_size": float(min_size) if min_size is not None else None
    }

def size_for(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        base = float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01))
        mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
        return base * mult

def load_signals():
    data = load_json(SIGNALS_FILE, {"signals": []})
    return {s["asset"]: s for s in data.get("signals", []) if s.get("asset")}

def valid_signal(signal):
    if not signal:
        return False, "aucun signal"

    if signal.get("decision") not in ["BUY", "SELL"]:
        return False, "pas BUY/SELL"

    if not signal.get("spread_ok"):
        return False, "spread refusé"

    if signal.get("mid") is None:
        return False, "prix manquant"

    age = float(signal.get("age_sec", 999999))
    max_age = float(getattr(CFG, "MAX_TICK_AGE_SEC", 12))

    if age > max_age:
        return False, f"tick trop ancien {age:.1f}s"

    return True, "OK"

def main():
    level = 1
    signals = load_signals()

    print()
    print("=" * 150)
    print("06E — ORDER BUILDER DRY_RUN — 16 ACTIFS")
    print("=" * 150)
    print("AUCUN ORDRE ENVOYÉ")
    print("-" * 150)
    print("ACTIF      | DECISION | MARKET    | SIZE       | MIN SIZE   | STATUS   | PAYLOAD / RAISON")
    print("-" * 150)

    for asset in CFG.ASSETS:
        market = get_market(asset)
        market_status = market["status"]
        min_size = market["min_size"]
        size = size_for(asset, level)
        signal = signals.get(asset)

        if min_size is None:
            print(f"{asset:10s} | --       | {market_status:9s} | {size:<10.6f} | --         | SKIP     | règles marché manquantes")
            continue

        if size < min_size:
            print(f"{asset:10s} | --       | {market_status:9s} | {size:<10.6f} | {min_size:<10.6f} | SKIP     | taille < min broker")
            continue

        if market_status != "TRADEABLE":
            print(f"{asset:10s} | --       | {market_status:9s} | {size:<10.6f} | {min_size:<10.6f} | SKIP     | marché non tradeable")
            continue

        ok, reason = valid_signal(signal)

        if not ok:
            print(f"{asset:10s} | --       | {market_status:9s} | {size:<10.6f} | {min_size:<10.6f} | WAIT     | {reason}")
            continue

        direction = signal["decision"]

        payload = {
            "epic": asset,
            "direction": direction,
            "size": size
        }

        print(
            f"{asset:10s} | "
            f"{direction:8s} | "
            f"{market_status:9s} | "
            f"{size:<10.6f} | "
            f"{min_size:<10.6f} | "
            f"DRY_RUN  | "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    print("=" * 150)
    print("Fin 06E :", utc_now())
    print("Aucun ordre n'a été envoyé.")

if __name__ == "__main__":
    main()
