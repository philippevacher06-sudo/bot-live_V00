import json
import math
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

import BOT_PIVOT_00_config as CFG
import BOT_PIVOT_06G_execution_from_cycle_state as B

TARGET_MARGIN_EUR = 20.0

ASSET_CLASSES = {
    "US500": "INDICES",
    "US100": "INDICES",
    "US30": "INDICES",
    "DE40": "INDICES",
    "FR40": "INDICES",
    "UK100": "INDICES",
    "J225": "INDICES",

    "EURUSD": "CURRENCIES",
    "GBPUSD": "CURRENCIES",
    "USDJPY": "CURRENCIES",
    "EURJPY": "CURRENCIES",

    "GOLD": "COMMODITIES",
    "SILVER": "COMMODITIES",
    "OIL_CRUDE": "COMMODITIES",

    "BTCUSD": "CRYPTOCURRENCIES",
    "ETHUSD": "CRYPTOCURRENCIES",
}

LEVERAGES = {
    "INDICES": 20,
    "CURRENCIES": 30,
    "COMMODITIES": 20,
    "CRYPTOCURRENCIES": 2,
}


def get_base_size(asset):
    if hasattr(CFG, "get_base_size"):
        return float(CFG.get_base_size(asset))
    if hasattr(CFG, "BASE_SIZES"):
        return float(CFG.BASE_SIZES[asset])
    if hasattr(CFG, "ASSET_BASE_SIZE"):
        return float(CFG.ASSET_BASE_SIZE[asset])
    raise RuntimeError(f"Taille de base introuvable pour {asset}")


def extract_rule_value(x):
    if isinstance(x, dict):
        for k in ("value", "min", "amount"):
            if k in x and x[k] is not None:
                try:
                    return float(x[k])
                except Exception:
                    pass
    try:
        return float(x)
    except Exception:
        return None


def recursive_find_key(obj, wanted):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() == wanted.lower():
                return v
            found = recursive_find_key(v, wanted)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = recursive_find_key(v, wanted)
            if found is not None:
                return found
    return None


def market_min_deal_size(asset):
    try:
        market = B._market_json(asset)
    except Exception:
        return None

    for key in ("minDealSize", "minimumDealSize", "minSize"):
        raw = recursive_find_key(market, key)
        val = extract_rule_value(raw)
        if val is not None and val > 0:
            return val

    return None


def price_from_history(asset):
    path = Path(f"data/history/{asset}_MINUTE_15_30d.json")
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    candles = data
    if isinstance(data, dict):
        for key in ("candles", "prices", "data", "history"):
            if isinstance(data.get(key), list):
                candles = data[key]
                break

    if not isinstance(candles, list) or not candles:
        return None

    last = candles[-1]
    if isinstance(last, dict):
        for key in ("close", "c", "last", "mid", "price"):
            if key in last and last[key] is not None:
                try:
                    return float(last[key])
                except Exception:
                    pass

        # Capital.com peut stocker closePrice sous forme bid/ask
        for key in ("closePrice", "close"):
            val = last.get(key)
            if isinstance(val, dict):
                bid = val.get("bid")
                ask = val.get("ask")
                if bid is not None and ask is not None:
                    return (float(bid) + float(ask)) / 2.0

    return None


def current_price(asset):
    try:
        market = B._market_json(asset)
        p = B._market_mid_price(market)
        if p and p > 0:
            return float(p)
    except Exception:
        pass

    p = price_from_history(asset)
    if p and p > 0:
        return float(p)

    return None


def decimals_from_step(step):
    s = f"{step:.10f}".rstrip("0").rstrip(".")
    if "." not in s:
        return 0
    return len(s.split(".")[1])


def round_to_step(value, step):
    if not step or step <= 0:
        return value

    d_value = Decimal(str(value))
    d_step = Decimal(str(step))
    rounded = (d_value / d_step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * d_step

    decimals = decimals_from_step(step)
    return float(round(float(rounded), decimals))


def recommended_size(asset, price, leverage):
    raw = TARGET_MARGIN_EUR * leverage / price

    min_size = market_min_deal_size(asset)

    # Si le broker donne un minimum, on l'utilise comme pas de taille.
    # Sinon on garde un pas prudent selon le type d'actif.
    if min_size is not None:
        step = min_size
    elif asset in ("EURUSD", "GBPUSD", "USDJPY", "EURJPY"):
        step = 100.0
    elif asset in ("BTCUSD",):
        step = 0.001
    elif asset in ("ETHUSD",):
        step = 0.01
    elif asset in ("OIL_CRUDE",):
        step = 1.0
    else:
        step = 0.01

    size = round_to_step(raw, step)

    if min_size is not None:
        size = max(size, min_size)

    return raw, size, step, min_size


def margin_estimate(price, size, leverage):
    return price * size / leverage


print("=" * 140)
print("AUDIT MARGE L1 — OBJECTIF ENVIRON 20 EUR PAR PREMIERE POSITION")
print("=" * 140)
print(f"{'ACTIF':10s} | {'CLASSE':16s} | {'PRIX':>12s} | {'LEV':>4s} | {'SIZE ACT.':>10s} | {'MARGE ACT.':>11s} | {'RAW SIZE':>10s} | {'SIZE 20€':>10s} | {'MARGE NEW':>11s} | {'STEP/MIN':>12s}")
print("-" * 140)

suggestions = {}

for asset in CFG.ASSETS:
    cls = ASSET_CLASSES.get(asset, "UNKNOWN")
    lev = LEVERAGES.get(cls)

    price = current_price(asset)
    cur_size = get_base_size(asset)

    if not price or not lev:
        print(f"{asset:10s} | {cls:16s} | {'N/A':>12s} | {'N/A':>4s} | {cur_size:10.6f} | {'N/A':>11s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>11s} | {'N/A':>12s}")
        continue

    cur_margin = margin_estimate(price, cur_size, lev)
    raw_size, new_size, step, min_size = recommended_size(asset, price, lev)
    new_margin = margin_estimate(price, new_size, lev)

    suggestions[asset] = new_size

    step_txt = f"{step:g}"
    if min_size is not None:
        step_txt += f"/{min_size:g}"

    print(
        f"{asset:10s} | {cls:16s} | {price:12.5f} | {lev:4.0f} | "
        f"{cur_size:10.6f} | {cur_margin:11.2f} | {raw_size:10.6f} | "
        f"{new_size:10.6f} | {new_margin:11.2f} | {step_txt:>12s}"
    )

print("=" * 140)
print("SUGGESTION BASE_SIZES / ASSET_BASE_SIZE")
print("-" * 140)
for asset, size in suggestions.items():
    if size >= 1:
        txt = str(int(size)) if abs(size - int(size)) < 1e-9 else str(size)
    else:
        txt = f"{size:.6f}".rstrip("0").rstrip(".")
    print(f'    "{asset}": {txt},')
print("=" * 140)
