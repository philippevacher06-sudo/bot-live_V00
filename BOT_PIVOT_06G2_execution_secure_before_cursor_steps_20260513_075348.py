#!/usr/bin/env python3
# BOT_PIVOT_06G2_execution_secure.py
# Exécution sécurisée BOT-PIVOT.
# Bloc 1/3 : fondations + résolution du vrai dealId broker.

import argparse
import json
import time
from datetime import datetime, timezone

import BOT_PIVOT_06G_execution_from_cycle_state as B
import BOT_PIVOT_00B_pnl_eur as PNL


SEND_REAL_ORDERS = False


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sync_base_flags():
    """
    06G2 pilote l'ancien module 06G uniquement comme librairie API.
    On synchronise son flag pour que api_post/api_delete envoient réellement
    uniquement quand 06H aura explicitement activé SEND_REAL_ORDERS.
    """
    B.SEND_REAL_ORDERS = SEND_REAL_ORDERS


def load_env():
    return B.load_env()


def login():
    return B.login()


def parse_confirm(confirm):
    return B.parse_confirm(confirm)



def v24_json_safe(obj, _seen=None):
    """
    Convertit dict/list en structure JSON-safe et coupe les références circulaires.
    """
    if _seen is None:
        _seen = set()

    oid = id(obj)
    if isinstance(obj, (dict, list, tuple, set)):
        if oid in _seen:
            return "<CIRCULAR_REF>"
        _seen.add(oid)

    if isinstance(obj, dict):
        return {
            str(k): v24_json_safe(v, _seen)
            for k, v in obj.items()
        }

    if isinstance(obj, (list, tuple, set)):
        return [
            v24_json_safe(v, _seen)
            for v in obj
        ]

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj

    try:
        return str(obj)
    except Exception:
        return "<UNSERIALIZABLE>"


def event(payload):
    payload = dict(payload)
    payload.setdefault("module", "06G2")
    payload.setdefault("utc", utc())
    return B.event(v24_json_safe(payload))


def parse_assets(raw):
    if raw.upper() == "ALL":
        return list(B.CFG.ASSETS)
    return [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]


def short_id(x):
    if not x:
        return "--"
    x = str(x)
    return x[:6] + "..." + x[-4:] if len(x) > 14 else x


def pos_epic(item):
    return B.broker_position_epic(item)


def pos_deal_id(item):
    return B.broker_position_deal_id(item)


def pos_direction(item):
    p = item.get("position", {}) if isinstance(item, dict) else {}
    return p.get("direction") or item.get("direction")


def pos_size(item):
    p = item.get("position", {}) if isinstance(item, dict) else {}
    return p.get("size") or item.get("size")


def pos_entry(item):
    p = item.get("position", {}) if isinstance(item, dict) else {}
    return p.get("level") or p.get("entryLevel") or p.get("openLevel")


def fetch_positions(headers):
    sync_base_flags()
    if not SEND_REAL_ORDERS:
        return "DRY_RUN", [], {}
    return B.broker_positions(headers)


def positions_for_asset(asset, positions):
    return [p for p in positions if pos_epic(p) == asset]


def deal_ids_for_asset(asset, positions):
    out = []
    for p in positions_for_asset(asset, positions):
        did = pos_deal_id(p)
        if did:
            out.append(did)
    return out


def broker_has_deal_id(deal_id, positions):
    if not deal_id:
        return False
    return deal_id in [pos_deal_id(p) for p in positions]


def same_size(a, b, tol=1e-9):
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def resolve_real_broker_deal_id(asset, before_positions, after_positions, expected_direction, expected_size):
    """
    Point critique du 06G2.

    Le dealId retourné par GET /confirms peut être différent du dealId réellement
    visible dans GET /positions. Donc 06G2 ne doit pas stocker aveuglément le
    dealId du confirm.

    Méthode :
    - on prend les positions broker AVANT l'ouverture ;
    - on prend les positions broker APRÈS l'ouverture ;
    - on cherche le nouveau dealId apparu chez le broker ;
    - on stocke CE dealId-là dans execution_state.
    """
    before_ids = set(deal_ids_for_asset(asset, before_positions))
    after_items = positions_for_asset(asset, after_positions)

    new_items = []
    for item in after_items:
        did = pos_deal_id(item)
        if did and did not in before_ids:
            new_items.append(item)

    details = {
        "asset": asset,
        "before_ids": list(before_ids),
        "after_ids": deal_ids_for_asset(asset, after_positions),
        "expected_direction": expected_direction,
        "expected_size": expected_size,
        "new_count": len(new_items),
        "new_items": [
            {
                "dealId": pos_deal_id(x),
                "direction": pos_direction(x),
                "size": pos_size(x),
                "entry": pos_entry(x),
            }
            for x in new_items
        ],
    }

    if len(new_items) == 1:
        return pos_deal_id(new_items[0]), "NEW_BROKER_DEAL_UNIQUE", details

    matched = []
    for item in new_items:
        if pos_direction(item) == expected_direction and same_size(pos_size(item), expected_size):
            matched.append(item)

    if len(matched) == 1:
        return pos_deal_id(matched[0]), "NEW_BROKER_DEAL_MATCH_DIR_SIZE", details

    if len(new_items) == 0:
        return None, "NO_NEW_BROKER_DEAL_VISIBLE", details

    return None, "AMBIGUOUS_NEW_BROKER_DEALS", details




def broker_min_profit_distance(asset):
    """
    Distance minimale de take-profit autorisée par Capital.com.
    """
    market = B._market_json(asset)
    rules = market.get("dealingRules", {}) or {}

    min_rule = rules.get("minStopOrProfitDistance")
    min_value, min_unit = B._rule_value(min_rule)

    if min_value is None:
        raise RuntimeError(f"Distance minimale TP introuvable pour {asset}")

    price = B._market_mid_price(market)

    if "PERCENT" in min_unit:
        distance = price * float(min_value) / 100.0
    else:
        distance = float(min_value)

    distance *= 1.10

    step_value, step_unit = B._rule_value(rules.get("minStepDistance"))

    if step_value is not None:
        distance = B._round_up_to_step(distance, float(step_value))
    else:
        distance = round(distance, 10)

    return distance


def cycle_target_tp_eur(cycle):
    """
    TP stratégique du cycle en euros.
    Priorité au tp_eur produit par le module 05.
    """
    for key in ("tp_eur", "target_tp_eur", "take_profit_eur"):
        if cycle.get(key) is not None:
            return float(cycle[key])

    level = int(cycle.get("level", 1))
    base = float(getattr(B.CFG, "BASE_TP_EUR", 0.10))
    multipliers = getattr(B.CFG, "LEVEL_MULTIPLIERS", {})

    try:
        mult = float(multipliers.get(level, 2 ** (level - 1)))
    except Exception:
        mult = float(2 ** (level - 1))

    return base * mult


def take_profit_distance(cycle):
    """
    TP broker réel :
    - basé sur l'objectif en euros du cycle
    - converti en distance prix par la taille
    - jamais inférieur au minimum broker
    """
    asset = cycle["asset"]
    size = float(cycle["size"])

    if size <= 0:
        raise RuntimeError(f"Taille invalide pour TP broker {asset}: {size}")

    target_eur = cycle_target_tp_eur(cycle)
    desired_distance = PNL.profit_distance_for_target_eur(asset, size, target_eur)

    min_distance = broker_min_profit_distance(asset)
    distance = max(desired_distance, min_distance)

    market = B._market_json(asset)
    rules = market.get("dealingRules", {}) or {}
    step_value, step_unit = B._rule_value(rules.get("minStepDistance"))

    if step_value is not None:
        distance = B._round_up_to_step(distance, float(step_value))
    else:
        distance = round(distance, 10)

    return distance


def build_open_payload_secure(cycle):
    """
    Payload 06G2 sécurisé :
    - stop garanti
    - stopDistance conservé
    - aucun TP broker individuel
    """
    payload = B.build_open_payload(cycle)

    # V24.1 : aucune sortie par TP broker individuel.
    # La sortie doit rester logicielle et cumulée côté panier.
    for k in ("profitDistance", "profitLevel", "profitAmount", "takeProfitLevel"):
        payload.pop(k, None)

    return payload



def v24_market_bid_ask(asset):
    """
    Récupère bid / ask depuis le market JSON Capital.com.
    """
    market = B._market_json(asset) or {}
    snap = market.get("snapshot") or market.get("market", {}).get("snapshot") or market

    bid = snap.get("bid")
    ask = snap.get("ask")

    if ask is None:
        ask = snap.get("offer")
    if ask is None:
        ask = snap.get("ofr")

    if bid is None or ask is None:
        raise RuntimeError(f"Bid/Ask introuvable pour {asset}: {snap}")

    bid = float(bid)
    ask = float(ask)

    if bid <= 0 or ask <= 0 or ask < bid:
        raise RuntimeError(f"Bid/Ask incohérent pour {asset}: bid={bid}, ask={ask}")

    return bid, ask


def v24_round_limit_price(asset, direction, price):
    """
    Arrondit le prix LIMIT selon le minStepDistance broker.
    BUY  : arrondi vers le bas.
    SELL : arrondi vers le haut.
    """
    market = B._market_json(asset) or {}
    rules = market.get("dealingRules", {}) or {}
    step_value, step_unit = B._rule_value(rules.get("minStepDistance"))

    price = float(price)

    if step_value is None:
        return round(price, 10)

    step = float(step_value)

    if step <= 0:
        return round(price, 10)

    if direction == "BUY":
        rounded = int(price / step) * step
        return round(float(rounded), 10)

    return float(B._round_up_to_step(price, step))


def v24_limit_price(asset, direction, basket_level):
    """
    V24 Basket Limit robuste.

    Règle broker :
    - BUY LIMIT  : niveau obligatoirement sous le prix actuel.
    - SELL LIMIT : niveau obligatoirement au-dessus du prix actuel.

    On ne fait plus confiance au nom bid/ask seul : on prend low_side / high_side.
    Cela évite les inversions de snapshot selon les actifs.
    """
    raw_bid, raw_ask = v24_market_bid_ask(asset)

    raw_bid = float(raw_bid)
    raw_ask = float(raw_ask)

    low_side = min(raw_bid, raw_ask)
    high_side = max(raw_bid, raw_ask)

    spread = abs(high_side - low_side)

    if spread <= 0:
        ref = max(abs(high_side), abs(low_side), 1.0)
        spread = max(ref * 0.00001, 0.00001)

    level = int(basket_level)

    # Offsets renforcés après rejet L1 trop proche :
    # L1 = 4 x spread
    # L2 = 6 x spread
    # L3 = 8 x spread
    multipliers = {
        1: 4.0,
        2: 6.0,
        3: 8.0,
    }

    mult = multipliers.get(level, float(2 * level + 2))
    offset = spread * mult

    direction = str(direction).upper()

    if direction == "BUY":
        price = low_side - offset
    else:
        price = high_side + offset

    rounded = v24_round_limit_price(asset, direction, price)

    # Sécurité finale après arrondi :
    # l'arrondi ne doit jamais remettre le LIMIT du mauvais côté.
    if direction == "BUY" and float(rounded) >= low_side:
        rounded = v24_round_limit_price(asset, direction, low_side - spread * (mult + 2.0))

    if direction == "SELL" and float(rounded) <= high_side:
        rounded = v24_round_limit_price(asset, direction, high_side + spread * (mult + 2.0))

    return rounded




# ============================================================
# V24.1 BOT-PIVOT BOLLINGER
# Ancrage L1/L2/L3 sur Bollinger M5
# ============================================================

V24_BOLLINGER_CACHE = {}

BOLLINGER_BASKET_CONFIG = {
    "_DEFAULT": {"buffer": 1.0, "step": 5.0, "decimals": 2},

    "US500": {"buffer": 5.0, "step": 5.0, "decimals": 1},
    "US100": {"buffer": 5.0, "step": 15.0, "decimals": 1},
    "US30": {"buffer": 10.0, "step": 25.0, "decimals": 1},
    "DE40": {"buffer": 5.0, "step": 15.0, "decimals": 1},
    "FRA40": {"buffer": 5.0, "step": 7.0, "decimals": 1},
    "FR40": {"buffer": 5.0, "step": 7.0, "decimals": 1},
    "UK100": {"buffer": 5.0, "step": 10.0, "decimals": 1},
    "J225": {"buffer": 10.0, "step": 50.0, "decimals": 1},

    "GOLD": {"buffer": 2.0, "step": 5.0, "decimals": 2},
    "SILVER": {"buffer": 0.5, "step": 0.5, "decimals": 3},
    "OIL_BRENT": {"buffer": 0.1, "step": 0.25, "decimals": 2},
    "OIL_CRUDE": {"buffer": 0.1, "step": 0.25, "decimals": 2},
    "NATURALGAS": {"buffer": 0.01, "step": 0.05, "decimals": 3},

    "EURUSD": {"buffer": 0.0001, "step": 0.0003, "decimals": 5},
    "GBPUSD": {"buffer": 0.00012, "step": 0.00035, "decimals": 5},
    "USDJPY": {"buffer": 0.01, "step": 0.05, "decimals": 3},
    "EURJPY": {"buffer": 0.015, "step": 0.06, "decimals": 3},

    "ETHUSD": {"buffer": 5.0, "step": 5.0, "decimals": 2},
    "BTCUSD": {"buffer": 10.0, "step": 50.0, "decimals": 2},
}


# ============================================================
# V24.1 — CURSEURS INDIVIDUELS PARAMÉTRABLES
# ============================================================
# BOLLINGER_CURSOR :
#   agit sur buffer/step Bollinger.
#   0.5 = très agressif, niveaux plus proches.
#   1.0 = réglage validé.
#   1.5 = plus strict, niveaux plus éloignés.
#
# TREND_ENTRY_CURSOR :
#   réservé au filtre de tendance d'entrée.
#
# SAFETY_EXIT_CURSOR :
#   réservé au garde-fou logiciel après entrée.
#
# NEWS_WINDOW_BEFORE_MIN / NEWS_WINDOW_AFTER_MIN :
#   fenêtre de protection autour des annonces macro.
# ============================================================

def v241_env_float(name, default):
    import os
    raw = os.environ.get(name, str(default))
    try:
        return float(raw)
    except Exception:
        return float(default)


def v241_env_int(name, default):
    import os
    raw = os.environ.get(name, str(default))
    try:
        return int(float(raw))
    except Exception:
        return int(default)


def v241_clamp(value, min_value, max_value):
    return max(float(min_value), min(float(max_value), float(value)))


def v241_cursor(name, default=1.0, min_value=0.5, max_value=1.5):
    return v241_clamp(v241_env_float(name, default), min_value, max_value)


def v241_bollinger_cursor():
    return v241_cursor("BOLLINGER_CURSOR", 1.0, 0.5, 1.5)


def v241_trend_entry_cursor():
    return v241_cursor("TREND_ENTRY_CURSOR", 1.0, 0.5, 1.5)


def v241_safety_exit_cursor():
    return v241_cursor("SAFETY_EXIT_CURSOR", 1.0, 0.5, 1.5)


def v241_news_window_before_min():
    return v241_env_int("NEWS_WINDOW_BEFORE_MIN", 5)


def v241_news_window_after_min():
    return v241_env_int("NEWS_WINDOW_AFTER_MIN", 5)


def v24_event_safe(payload):
    try:
        event(payload)
    except Exception:
        pass


def v24_extract_close_price(item):
    if not isinstance(item, dict):
        return None

    close_price = item.get("closePrice") or item.get("close") or item.get("c")

    if isinstance(close_price, dict):
        bid = close_price.get("bid")
        ask = close_price.get("ask")
        last = close_price.get("lastTraded") or close_price.get("last")

        if bid is not None and ask is not None:
            return (float(bid) + float(ask)) / 2.0
        if bid is not None:
            return float(bid)
        if ask is not None:
            return float(ask)
        if last is not None:
            return float(last)

    if close_price is not None:
        return float(close_price)

    return None


def v24_api_get_prices_m5(headers, asset, max_points=60):
    import time
    import requests
    import BOT_PIVOT_00_config as CFG_LOCAL

    cache_key = (str(asset).upper(), "M5", int(max_points))
    now = time.time()

    cached = V24_BOLLINGER_CACHE.get(cache_key)
    if cached and now - cached.get("ts", 0) < 45:
        return cached.get("closes", [])

    base_url = getattr(CFG_LOCAL, "BASE_URL", "https://demo-api-capital.backend-capital.com")
    url = f"{base_url}/api/v1/prices/{asset}?resolution=MINUTE_5&max={int(max_points)}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        try:
            data = r.json()
        except Exception:
            data = {}

        if r.status_code not in (200, 201, 202):
            v24_event_safe({
                "event": "V24_BOLLINGER_M5_FETCH_FAIL",
                "asset": asset,
                "status": r.status_code,
                "response": data,
            })
            return []

        prices = data.get("prices") or data.get("candles") or data.get("data") or []

        closes = []
        for item in prices:
            close = v24_extract_close_price(item)
            if close is not None:
                closes.append(float(close))

        V24_BOLLINGER_CACHE[cache_key] = {
            "ts": now,
            "closes": closes,
        }

        return closes

    except Exception as e:
        v24_event_safe({
            "event": "V24_BOLLINGER_M5_EXCEPTION",
            "asset": asset,
            "error": str(e),
        })
        return []


def v24_compute_bollinger_bands(closes, period=20, mult=2.0):
    if not closes or len(closes) < period:
        return None

    sample = [float(x) for x in closes[-period:]]
    middle = sum(sample) / float(period)
    variance = sum((x - middle) ** 2 for x in sample) / float(period)
    std = variance ** 0.5

    return {
        "middle": middle,
        "upper": middle + float(mult) * std,
        "lower": middle - float(mult) * std,
    }


def v24_compute_bollinger_limit_levels(asset, direction, bb_lower_m5, bb_upper_m5):
    asset_key = str(asset).upper()
    conf = BOLLINGER_BASKET_CONFIG.get(asset_key, BOLLINGER_BASKET_CONFIG["_DEFAULT"])

    base_buffer = float(conf["buffer"])
    base_step = float(conf["step"])
    decimals = int(conf.get("decimals", 2))

    bollinger_cursor = v241_bollinger_cursor()

    buffer = base_buffer * bollinger_cursor
    step = base_step * bollinger_cursor

    direction = str(direction).upper()

    if direction == "BUY":
        l1 = float(bb_lower_m5) - buffer
        l2 = l1 - step
        l3 = l1 - 2.0 * step
    elif direction == "SELL":
        l1 = float(bb_upper_m5) + buffer
        l2 = l1 + step
        l3 = l1 + 2.0 * step
    else:
        raise ValueError(f"Direction invalide : {direction}")

    return {
        "L1": round(l1, decimals),
        "L2": round(l2, decimals),
        "L3": round(l3, decimals),
        "buffer": buffer,
        "step": step,
        "base_buffer": base_buffer,
        "base_step": base_step,
        "bollinger_cursor": bollinger_cursor,
        "decimals": decimals,
    }


def v24_enrich_cycle_with_bollinger_m5(headers, cycle):
    asset = cycle.get("asset")
    direction = str(cycle.get("direction", "")).upper()

    closes = v24_api_get_prices_m5(headers, asset, max_points=60)
    bands = v24_compute_bollinger_bands(closes, period=20, mult=2.0)

    if not bands:
        v24_event_safe({
            "event": "V24_BOLLINGER_M5_UNAVAILABLE",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "direction": direction,
            "closes_count": len(closes) if closes else 0,
        })
        return None

    levels = v24_compute_bollinger_limit_levels(
        asset=asset,
        direction=direction,
        bb_lower_m5=bands["lower"],
        bb_upper_m5=bands["upper"],
    )

    # Sécurité broker : si le niveau Bollinger est du mauvais côté du prix,
    # on ne revient PAS à l'ancien calcul spread. On skippe le panier.
    try:
        raw_bid, raw_ask = v24_market_bid_ask(asset)
        low_side = min(float(raw_bid), float(raw_ask))
        high_side = max(float(raw_bid), float(raw_ask))

        if direction == "BUY" and float(levels["L1"]) >= low_side:
            v24_event_safe({
                "event": "V24_BOLLINGER_L1_WRONG_SIDE",
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "direction": direction,
                "L1": levels.get("L1"),
                "low_side": low_side,
            })
            return None

        if direction == "SELL" and float(levels["L1"]) <= high_side:
            v24_event_safe({
                "event": "V24_BOLLINGER_L1_WRONG_SIDE",
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "direction": direction,
                "L1": levels.get("L1"),
                "high_side": high_side,
            })
            return None

    except Exception as e:
        v24_event_safe({
            "event": "V24_BOLLINGER_SIDE_CHECK_FAIL",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "direction": direction,
            "error": str(e),
        })
        return None

    enriched = dict(cycle)
    enriched["bb_lower_m5"] = float(bands["lower"])
    enriched["bb_middle_m5"] = float(bands["middle"])
    enriched["bb_upper_m5"] = float(bands["upper"])
    enriched["bollinger_limit_levels"] = levels

    v24_event_safe({
        "event": "V24_BOLLINGER_LIMIT_LEVELS",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "direction": direction,
        "bb_lower_m5": enriched["bb_lower_m5"],
        "bb_middle_m5": enriched["bb_middle_m5"],
        "bb_upper_m5": enriched["bb_upper_m5"],
        "L1": levels.get("L1"),
        "L2": levels.get("L2"),
        "L3": levels.get("L3"),
        "buffer": levels.get("buffer"),
        "step": levels.get("step"),
    })

    print(
        f"{asset:10s} | BOLLINGER_M5 | "
        f"{direction:4s} | "
        f"BB_LOW={enriched['bb_lower_m5']:.5f} | "
        f"BB_MID={enriched['bb_middle_m5']:.5f} | "
        f"BB_HIGH={enriched['bb_upper_m5']:.5f} | "
        f"L1={levels.get('L1')} | L2={levels.get('L2')} | L3={levels.get('L3')} | "
        f"BUFFER={levels.get('buffer')} | STEP={levels.get('step')}"
    )

    return enriched


def build_limit_payload_secure(cycle, basket_level=None):
    """
    Payload V24 LIMIT :
    - ordre LIMIT broker
    - stop conservé comme airbag
    - aucun profitDistance individuel
    """
    asset = cycle["asset"]
    direction = cycle["direction"]
    level = int(basket_level or cycle.get("level", 1))

    payload = B.build_open_payload(cycle)

    # En V24, le TP est panier global, pas TP broker individuel par jambe.
    for k in ("profitDistance", "profitLevel", "profitAmount"):
        payload.pop(k, None)

    payload["epic"] = asset
    payload["direction"] = direction
    payload["size"] = float(cycle["size"])
    payload["type"] = "LIMIT"
    bollinger_levels = cycle.get("bollinger_limit_levels") or {}
    bollinger_key = f"L{level}"

    if bollinger_key not in bollinger_levels:
        raise ValueError(
            f"Niveau Bollinger {bollinger_key} manquant pour {asset} "
            f"cycle_id={cycle.get('cycle_id')}"
        )

    payload["level"] = float(bollinger_levels[bollinger_key])

    # V24.1 BOT-PIVOT BOLLINGER :
    # aucun TP broker individuel par jambe.
    # La sortie se fait uniquement par TP logiciel cumulé du panier :
    # 1 jambe ouverte = +0.20 €
    # 2 jambes ouvertes = +0.40 €
    # 3 jambes ouvertes = +0.60 €
    for k in ("profitDistance", "profitLevel", "profitAmount", "takeProfitLevel"):
        payload.pop(k, None)



    return payload


def place_limit_order_secure(headers, asset, cycle, market_status, basket_level=None):
    """
    Pose un ordre LIMIT via /api/v1/workingorders.
    Attention : cela crée un ordre en attente, pas encore une position ouverte.
    """
    sync_base_flags()

    level = int(basket_level or cycle.get("level", 1))
    direction = cycle["direction"]
    size = float(cycle["size"])

    enriched_cycle = v24_enrich_cycle_with_bollinger_m5(headers, cycle)

    if not enriched_cycle:
        reason = "BOLLINGER_M5_UNAVAILABLE_OR_INVALID"
        event({
            "event": "LIMIT_SKIP",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "reason": reason,
        })
        print(
            f"{asset:10s} | LIMIT_SKIP    | "
            f"{level:<3} | {direction:4s} | {size:<10.6f} | "
            f"{market_status:9s} | {reason}"
        )
        return False, {
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": "SKIPPED",
            "reason": reason,
            "created_utc": utc(),
        }

    cycle = enriched_cycle
    payload = build_limit_payload_secure(cycle, basket_level=level)

    event({
        "event": "LIMIT_REQUEST",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "level": level,
        "direction": direction,
        "size": size,
        "payload": payload,
        "dry_run": not SEND_REAL_ORDERS,
    })

    print(
        f"{asset:10s} | LIMIT_REQUEST | "
        f"{level:<3} | {direction:4s} | {size:<10.6f} | "
        f"{market_status:9s} | {json.dumps(payload, ensure_ascii=False)}"
    )

    if not SEND_REAL_ORDERS:
        dry_ref = f"DRY_LIMIT_{asset}_L{level}_{direction}_{cycle.get('cycle_id')}"
        return True, {
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": "PENDING_LIMIT_DRY_RUN",
            "workingDealReference": dry_ref,
            "workingDealId": dry_ref,
            "limit_price": payload.get("level"),
        "broker_tp_distance": payload.get("profitDistance"),
        "broker_tp_eur": cycle.get("broker_tp_eur", 0.20),
            "payload": payload,
            "created_utc": utc(),
            "dry_run": True,
        }

    status, data = B.api_post(headers, "/api/v1/workingorders", payload)
    deal_ref = data.get("dealReference") if isinstance(data, dict) else None

    if status not in (200, 201, 202) or not deal_ref:
        reason = f"LIMIT_REJECT_HTTP_{status}"
        event({
            "event": "LIMIT_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": status,
            "payload": payload,
            "response": data,
            "reason": reason,
        })

        print(
            f"{asset:10s} | LIMIT_REJECT  | "
            f"{level:<3} | {direction:4s} | {size:<10.6f} | "
            f"{market_status:9s} | HTTP {status} | {data}"
        )

        return False, {
            "reason": reason,
            "response": data,
            "payload": payload,
        }

    record = {
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "level": level,
        "direction": direction,
        "size": size,
        "status": "PENDING_LIMIT",
        "workingDealReference": deal_ref,
        "workingDealId": None,
        "workingDealId_source": "PENDING_RESOLVE_FROM_GET_WORKINGORDERS",
        "limit_price": payload.get("level"),
        "payload": payload,
        "created_utc": utc(),
        "dry_run": False,
    }

    event({
        "event": "LIMIT_PLACED_OK",
        **record,
        "response": data,
    })

    print(
        f"{asset:10s} | LIMIT_OK      | "
        f"{level:<3} | {direction:4s} | {size:<10.6f} | "
        f"{market_status:9s} | ref={short_id(deal_ref)} limit={payload.get('level')}"
    )

    return True, record



def open_cycle_secure(headers, asset, cycle, market_status, before_positions):
    """
    Ouverture sécurisée 06G2.
    Ne stocke jamais aveuglément le dealId du confirm.
    Stocke le vrai dealId visible dans GET /positions.
    """
    sync_base_flags()

    level = int(cycle["level"])
    direction = cycle["direction"]
    size = float(cycle["size"])

    payload = build_open_payload_secure(cycle)

    status, data = B.api_post(headers, "/api/v1/positions", payload)

    event({
        "event": "OPEN_REQUEST",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "level": level,
        "direction": direction,
        "size": size,
        "status": status,
        "payload": payload,
        "response": data,
        "dry_run": not SEND_REAL_ORDERS,
    })

    print(
        f"{asset:10s} | OPEN_REQUEST   | "
        f"{level:<3} | {direction:4s} | {size:<10.6f} | "
        f"{market_status:9s} | {json.dumps(payload, ensure_ascii=False)}"
    )

    if not SEND_REAL_ORDERS:
        dry_deal_id = f"DRY_{asset}_L{level}_{direction}_{cycle.get('cycle_id')}"
        return True, {
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "dealReference": None,
            "dealId": dry_deal_id,
            "brokerDealId": dry_deal_id,
            "open_status": "DRY_RUN",
            "confirm_status": "DRY_RUN",
            "confirm": {"DRY_RUN": True},
            "opened_utc": utc(),
            "dry_run": True,
        }, before_positions

    if status not in (200, 201, 202):
        reason = f"OPEN_REJECT_HTTP_{status}"
        event({
            "event": "OPEN_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": status,
            "payload": payload,
            "response": data,
            "reason": reason,
        })
        B.reset_cycle_after_reject(asset, reason, data)

        print(
            f"{asset:10s} | OPEN_REJECT    | "
            f"{level:<3} | {direction:4s} | {size:<10.6f} | "
            f"{market_status:9s} | HTTP {status}"
        )
        return False, {"reason": reason, "response": data}, before_positions

    deal_ref = data.get("dealReference") if isinstance(data, dict) else None

    if not deal_ref:
        reason = "OPEN_REJECT_NO_DEAL_REFERENCE"
        event({
            "event": "OPEN_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": status,
            "payload": payload,
            "response": data,
            "reason": reason,
        })
        B.reset_cycle_after_reject(asset, reason, data)

        print(
            f"{asset:10s} | OPEN_REJECT    | "
            f"{level:<3} | {direction:4s} | {size:<10.6f} | "
            f"{market_status:9s} | pas de dealReference"
        )
        return False, {"reason": reason, "response": data}, before_positions

    time.sleep(0.30)
    confirm_status, confirm = B.api_get(headers, f"/api/v1/confirms/{deal_ref}")
    confirm_deal_id = parse_confirm(confirm)

    # Le point critique : récupérer le vrai dealId broker via GET /positions.
    after_positions = before_positions
    real_broker_deal_id = None
    resolve_reason = None
    resolve_details = None

    for attempt in range(1, 8):
        time.sleep(0.40)
        _, after_positions, _ = fetch_positions(headers)

        real_broker_deal_id, resolve_reason, resolve_details = resolve_real_broker_deal_id(
            asset=asset,
            before_positions=before_positions,
            after_positions=after_positions,
            expected_direction=direction,
            expected_size=size,
        )

        if real_broker_deal_id:
            break

    if not real_broker_deal_id:
        reason = f"OPEN_REJECT_REAL_BROKER_DEAL_NOT_RESOLVED_{resolve_reason}"
        event({
            "event": "OPEN_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": status,
            "payload": payload,
            "response": data,
            "dealReference": deal_ref,
            "confirm_status": confirm_status,
            "confirm": confirm,
            "confirm_dealId": confirm_deal_id,
            "resolve_reason": resolve_reason,
            "resolve_details": resolve_details,
            "reason": reason,
        })
        B.reset_cycle_after_reject(asset, reason, confirm)

        print(
            f"{asset:10s} | OPEN_REJECT    | "
            f"{level:<3} | {direction:4s} | {size:<10.6f} | "
            f"{market_status:9s} | vrai dealId broker introuvable : {resolve_reason}"
        )
        return False, {"reason": reason, "details": resolve_details}, after_positions

    # Récupération du vrai prix d'entrée broker depuis GET /positions.
    real_broker_position = None
    for item in positions_for_asset(asset, after_positions):
        if pos_deal_id(item) == real_broker_deal_id:
            real_broker_position = item
            break

    try:
        broker_entry_price = (
            float(pos_entry(real_broker_position))
            if real_broker_position is not None and pos_entry(real_broker_position) is not None
            else None
        )
    except Exception:
        broker_entry_price = None

    try:
        theoretical_entry_price = float(cycle.get("entry_price"))
    except Exception:
        theoretical_entry_price = None

    if broker_entry_price is not None and theoretical_entry_price is not None:
        entry_slippage_points = broker_entry_price - theoretical_entry_price
    else:
        entry_slippage_points = None

    record = {
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "level": level,
        "direction": direction,
        "size": size,
        "entry_price_theoretical": theoretical_entry_price,
        "brokerEntryPrice": broker_entry_price,
        "brokerEntryPrice_source": (
            "GET_POSITIONS_AFTER_OPEN_LEVEL"
            if broker_entry_price is not None
            else "UNAVAILABLE"
        ),
        "entry_slippage_points": entry_slippage_points,
        "dealReference": deal_ref,
        "confirmDealId": confirm_deal_id,
        "dealId": real_broker_deal_id,
        "brokerDealId": real_broker_deal_id,
        "dealId_source": "GET_POSITIONS_AFTER_OPEN",
        "resolve_reason": resolve_reason,
        "open_status": status,
        "confirm_status": confirm_status,
        "confirm": confirm,
        "opened_utc": utc(),
        "dry_run": False,
    }

    event({
        "event": "OPEN_VERIFIED_OK",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "level": level,
        "direction": direction,
        "size": size,
        "dealReference": deal_ref,
        "confirmDealId": confirm_deal_id,
        "brokerDealId": real_broker_deal_id,
        "brokerEntryPrice": broker_entry_price,
        "entry_price_theoretical": theoretical_entry_price,
        "entry_slippage_points": entry_slippage_points,
        "resolve_reason": resolve_reason,
    })

    print(
        f"{asset:10s} | OPEN_OK        | "
        f"{level:<3} | {direction:4s} | {size:<10.6f} | "
        f"{market_status:9s} | "
        f"brokerDealId={short_id(real_broker_deal_id)} "
        f"confirmDealId={short_id(confirm_deal_id)} "
        f"brokerEntry={broker_entry_price} "
        f"theoreticalEntry={theoretical_entry_price} "
        f"slip={entry_slippage_points}"
    )

    return True, record, after_positions




def reset_cycle_idle(asset, reason):
    """
    Remet un cycle à IDLE quand la position broker a disparu
    par TP broker, stop broker ou fermeture manuelle.
    """
    state = B.load_json(B.STATE_FILE, {"assets": {}})
    state.setdefault("assets", {})
    state["assets"].setdefault(asset, {})
    state["assets"][asset]["status"] = "IDLE"
    state["assets"][asset]["cycle"] = None
    state["assets"][asset]["last_event"] = reason
    state["assets"][asset]["last_event_utc"] = utc()
    state["updated_utc"] = utc()
    B.save_json(B.STATE_FILE, state)





def working_order_items(data):
    """
    Normalise la réponse GET /api/v1/workingorders.
    Capital.com peut encapsuler les ordres dans workingOrders.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("workingOrders", "workingorders", "orders", "items"):
            val = data.get(key)
            if isinstance(val, list):
                return val

        if isinstance(data.get("workingOrderData"), dict):
            return [data]

    return []


def working_order_data(item):
    if not isinstance(item, dict):
        return {}
    return item.get("workingOrderData") or item.get("workingOrder") or item


def working_order_deal_id(item):
    d = working_order_data(item)
    return (
        d.get("dealId")
        or d.get("workingOrderId")
        or d.get("id")
        or item.get("dealId")
        or item.get("workingOrderId")
        or item.get("id")
    )


def working_order_matches_exec(item, active_exec):
    """
    Match prudent :
    - asset / epic
    - direction
    - size
    - limit_price / orderLevel
    """
    d = working_order_data(item)

    epic = d.get("epic") or item.get("epic")
    direction = d.get("direction") or item.get("direction")
    size = d.get("orderSize") or d.get("size") or item.get("orderSize") or item.get("size")
    level = d.get("orderLevel") or d.get("level") or item.get("orderLevel") or item.get("level")

    if epic != active_exec.get("asset"):
        return False

    if direction != active_exec.get("direction"):
        return False

    try:
        if abs(float(size) - float(active_exec.get("size"))) > 1e-9:
            return False
    except Exception:
        return False

    try:
        expected_level = float(active_exec.get("limit_price"))
        if abs(float(level) - expected_level) > 1e-8:
            return False
    except Exception:
        return False

    return True


def resolve_working_order_id(headers, active_exec):
    """
    Retrouve le vrai dealId du working order via GET /api/v1/workingorders.
    Retourne : working_id, reason, response
    """
    existing = active_exec.get("workingDealId")
    if existing:
        return existing, "ALREADY_PRESENT", None

    status, data = B.api_get(headers, "/api/v1/workingorders")

    if status not in (200, 201, 202):
        return None, f"GET_WORKINGORDERS_HTTP_{status}", data

    matches = []
    for item in working_order_items(data):
        if working_order_matches_exec(item, active_exec):
            wid = working_order_deal_id(item)
            if wid:
                matches.append((wid, item))

    if len(matches) == 1:
        return matches[0][0], "MATCH_ASSET_DIRECTION_SIZE_LEVEL", data

    if len(matches) > 1:
        return None, "MULTIPLE_WORKING_ORDER_MATCHES", data

    return None, "NO_MATCHING_WORKING_ORDER", data



def cancel_working_order_secure(headers, asset, working_id, reason, old_exec=None):
    """
    V24 Basket Limit :
    Annule un ordre LIMIT/STOP en attente via DELETE /api/v1/workingorders/{dealId}.
    Ne doit pas être utilisé pour fermer une position ouverte.
    """
    sync_base_flags()

    if not working_id:
        info = {
            "ok": False,
            "asset": asset,
            "working_id": working_id,
            "reason": "NO_WORKING_ORDER_ID",
            "cancel_reason": reason,
            "old_exec": old_exec,
        }
        event({"event": "CANCEL_LIMIT_FAILED", **info})
        return False, info

    if not SEND_REAL_ORDERS:
        info = {
            "ok": True,
            "asset": asset,
            "working_id": working_id,
            "reason": "DRY_RUN",
            "cancel_reason": reason,
            "old_exec": old_exec,
            "dry_run": True,
        }
        event({"event": "CANCEL_LIMIT_OK_DRY_RUN", **info})
        return True, info

    status, response = B.api_delete(headers, f"/api/v1/workingorders/{working_id}")

    ok = status in (200, 201, 202, 404)

    info = {
        "ok": ok,
        "asset": asset,
        "working_id": working_id,
        "cancel_reason": reason,
        "old_exec": old_exec,
        "delete_status": status,
        "delete_response": response,
        "dry_run": False,
    }

    event({
        "event": "CANCEL_LIMIT_OK" if ok else "CANCEL_LIMIT_FAILED",
        **info,
    })

    return ok, info



def close_deal_secure(headers, asset, deal_id, reason, old_exec=None):
    """
    Fermeture sécurisée :
    - DELETE /positions/{vrai_brokerDealId}
    - éventuel GET /confirms
    - relecture GET /positions
    - validation seulement si le dealId a disparu.
    """
    sync_base_flags()

    if not deal_id:
        info = {
            "ok": False,
            "asset": asset,
            "dealId": deal_id,
            "reason": "NO_DEAL_ID",
            "close_reason": reason,
            "old_exec": old_exec,
        }
        event({"event": "CLOSE_FAILED", **info})
        return False, info, None

    if not SEND_REAL_ORDERS:
        info = {
            "ok": True,
            "asset": asset,
            "dealId": deal_id,
            "reason": "DRY_RUN",
            "close_reason": reason,
            "old_exec": old_exec,
            "dry_run": True,
        }
        event({"event": "CLOSE_OK_DRY_RUN", **info})
        return True, info, []

    delete_status, delete_response = B.api_delete(headers, f"/api/v1/positions/{deal_id}")

    deal_ref = None
    if isinstance(delete_response, dict):
        deal_ref = delete_response.get("dealReference")

    confirm_status = None
    confirm = None

    if delete_status in (200, 201, 202) and deal_ref:
        time.sleep(0.30)
        confirm_status, confirm = B.api_get(headers, f"/api/v1/confirms/{deal_ref}")

    positions_after = []
    verify_status = None
    verified_closed = False
    remaining_ids = []

    for attempt in range(1, 8):
        time.sleep(0.40)
        verify_status, positions_after, _ = fetch_positions(headers)
        remaining_ids = deal_ids_for_asset(asset, positions_after)

        if not broker_has_deal_id(deal_id, positions_after):
            verified_closed = True
            break

    ok = delete_status in (200, 201, 202, 404) and verified_closed

    info = {
        "ok": ok,
        "asset": asset,
        "dealId": deal_id,
        "close_reason": reason,
        "old_exec": old_exec,
        "delete_status": delete_status,
        "delete_response": delete_response,
        "dealReference": deal_ref,
        "confirm_status": confirm_status,
        "confirm": confirm,
        "verify_status": verify_status,
        "verified_closed": verified_closed,
        "remaining_ids_for_asset": remaining_ids,
        "dry_run": False,
    }

    event({
        "event": "CLOSE_VERIFIED_OK" if ok else "CLOSE_FAILED",
        **info,
    })

    return ok, info, positions_after




def v24_leg_cycle(base_cycle, basket_level):
    """
    Fabrique une jambe L1/L2/L3 à partir du cycle moteur.
    L1 = taille base
    L2 = taille base x 2
    L3 = taille base x 3
    """
    level = int(basket_level)
    c = dict(base_cycle)
    base_size = float(base_cycle.get("size", 0.0))

    c["level"] = level
    c["size"] = float(base_size * level)
    c["tp_eur"] = float(0.20 * level)
    c["broker_tp_eur"] = 0.20
    c["basket_level"] = level
    c["basket_mode"] = True

    return c


def v24_open_basket_limits_secure(headers, asset, cycle, market_status):
    """
    Pose directement les 3 LIMIT V24 :
    L1 = 2 x spread
    L2 = 4 x spread
    L3 = 6 x spread
    """
    levels = {}
    ok_any = False
    rejects = []

    for basket_level in (1, 2, 3):
        leg_cycle = v24_leg_cycle(cycle, basket_level)

        ok, record = place_limit_order_secure(
            headers=headers,
            asset=asset,
            cycle=leg_cycle,
            market_status=market_status,
            basket_level=basket_level,
        )

        if ok:
            levels[str(basket_level)] = record
            ok_any = True
        else:
            rejects.append({
                "level": basket_level,
                "record": record,
            })

    # V24 sécurité :
    # Pas de panier partiel. Si un niveau est rejeté, on annule les LIMIT déjà posés.
    if rejects:
        cancel_results = []

        for level_key, rec in list(levels.items()):
            working_id = rec.get("workingDealId")

            if not working_id:
                resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, rec)
                if resolved_id:
                    rec["workingDealId"] = resolved_id
                    rec["workingDealId_source"] = resolve_reason
                    rec["workingDealId_resolved_utc"] = utc()
                    working_id = resolved_id

            if working_id:
                ok_cancel, cancel_info = cancel_working_order_secure(
                    headers=headers,
                    asset=asset,
                    working_id=working_id,
                    reason="V24_BASKET_PARTIAL_REJECT_CANCEL",
                    old_exec=rec,
                )
                cancel_results.append({
                    "level": level_key,
                    "ok": ok_cancel,
                    "info": cancel_info,
                })
            else:
                cancel_results.append({
                    "level": level_key,
                    "ok": False,
                    "reason": "NO_WORKING_ID_TO_CANCEL_AFTER_PARTIAL_REJECT",
                    "record": rec,
                })

        event({
            "event": "V24_BASKET_PARTIAL_REJECT_CANCELLED",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "direction": cycle.get("direction"),
            "levels": levels,
            "rejects": rejects,
            "cancel_results": cancel_results,
        })

        print(
            f"{asset:10s} | BASKET_REJECT | 1-3 | {cycle.get('direction'):4s} | "
            f"{float(cycle.get('size', 0.0)):<10.6f} | {market_status:9s} | "
            f"panier partiel annulé | acceptés={len(levels)} rejetés={len(rejects)}"
        )

        return False, {
            "reason": "V24_BASKET_PARTIAL_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "levels": levels,
            "rejects": rejects,
            "cancel_results": cancel_results,
        }

    basket_record = {
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "direction": cycle.get("direction"),
        "status": "BASKET_ACTIVE",
        "basket_mode": "V24_BASKET_LIMIT",
        "levels": levels,
        "rejects": rejects,
        "created_utc": utc(),
        "target_mode": "BASKET_GLOBAL_TP",
    }

    event({
        "event": "V24_BASKET_LIMIT_CREATED",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "direction": cycle.get("direction"),
        "levels": levels,
        "rejects": rejects,
        "ok_any": ok_any,
    })

    print(
        f"{asset:10s} | BASKET_NEW  | 1-3 | {cycle.get('direction'):4s} | "
        f"{float(cycle.get('size', 0.0)):<10.6f} | {market_status:9s} | "
        f"LIMITS posés={len(levels)} rejetés={len(rejects)}"
    )

    return ok_any, basket_record


def v24_pos_direction(item):
    d = item.get("position") if isinstance(item, dict) else {}
    if not isinstance(d, dict):
        d = {}
    return (
        d.get("direction")
        or item.get("direction")
        or d.get("side")
        or item.get("side")
    )


def v24_pos_size(item):
    d = item.get("position") if isinstance(item, dict) else {}
    if not isinstance(d, dict):
        d = {}
    return (
        d.get("size")
        or d.get("dealSize")
        or item.get("size")
        or item.get("dealSize")
    )


def v24_position_matches_level(item, level_record):
    """
    Match assez strict :
    même direction + même taille.
    """
    try:
        item_dir = v24_pos_direction(item)
        item_size = float(v24_pos_size(item))
        rec_dir = level_record.get("direction")
        rec_size = float(level_record.get("size"))

        if item_dir != rec_dir:
            return False

        if abs(item_size - rec_size) > 1e-9:
            return False

        return True
    except Exception:
        return False


def v24_leg_pnl_eur(asset, direction, entry_price, current_price, size):
    """
    PnL panier en euros.
    Utilise la conversion existante de BOT_PIVOT_00B_pnl_eur via profit_distance_for_target_eur.
    """
    entry_price = float(entry_price)
    current_price = float(current_price)
    size = float(size)

    if direction == "BUY":
        price_move = current_price - entry_price
    else:
        price_move = entry_price - current_price

    try:
        one_eur_distance = float(PNL.profit_distance_for_target_eur(asset, size, 1.0))
        if one_eur_distance > 0:
            return float(price_move / one_eur_distance)
    except Exception:
        pass

    # Fallback brut si conversion indisponible.
    return float(price_move * size)


def v24_basket_current_pnl(asset, basket_exec):
    """
    Calcule le PnL global du panier sur les niveaux OPEN_POSITION.
    BUY sort au BID.
    SELL sort à l'ASK.
    """
    raw_bid, raw_ask = v24_market_bid_ask(asset)

    # V24 sécurité :
    # Pour éviter une fermeture faussement gagnante à cause d'un bid/ask inversé
    # ou mal interprété, on valorise toujours de façon conservatrice.
    low_side = min(float(raw_bid), float(raw_ask))
    high_side = max(float(raw_bid), float(raw_ask))

    total = 0.0
    open_count = 0

    for level_key, rec in basket_exec.get("levels", {}).items():
        if rec.get("status") != "OPEN_POSITION":
            continue

        direction = rec.get("direction")
        entry = rec.get("brokerEntryPrice")
        size = rec.get("size")

        if entry is None or size is None:
            continue

        # BUY se ferme au côté bas du spread.
        # SELL se ferme au côté haut du spread.
        current = low_side if direction == "BUY" else high_side
        pnl = v24_leg_pnl_eur(asset, direction, entry, current, size)

        rec["last_pnl_eur"] = float(pnl)
        rec["last_price_used"] = float(current)
        rec["last_raw_bid"] = float(raw_bid)
        rec["last_raw_ask"] = float(raw_ask)
        rec["last_price_side"] = "LOW_SIDE_FOR_BUY" if direction == "BUY" else "HIGH_SIDE_FOR_SELL"

        total += float(pnl)
        open_count += 1

    target = float(0.20 * open_count) if open_count > 0 else None

    return total, open_count, target


def v24_close_basket_secure(headers, asset, basket_exec, reason):
    """
    Ferme toutes les jambes OPEN_POSITION et annule les LIMIT encore en attente.
    """
    levels = basket_exec.get("levels", {})
    results = []
    ok_all = True
    last_positions_after = None

    for level_key, rec in list(levels.items()):
        status = rec.get("status")

        if status == "OPEN_POSITION":
            deal_id = rec.get("brokerDealId") or rec.get("dealId")

            ok, info, positions_after = close_deal_secure(
                headers=headers,
                asset=asset,
                deal_id=deal_id,
                reason=reason,
                old_exec=rec,
            )

            rec["closed_utc"] = utc()
            safe_info = v24_json_safe(info)
            rec["close_info"] = safe_info
            rec["status"] = "CLOSED" if ok else "CLOSE_FAILED"

            results.append({
                "level": level_key,
                "action": "CLOSE_POSITION",
                "ok": ok,
                "info": safe_info,
            })

            if positions_after is not None:
                last_positions_after = positions_after

            if not ok:
                ok_all = False

        elif str(status).startswith("PENDING_LIMIT"):
            working_id = rec.get("workingDealId")

            if not working_id:
                resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, rec)
                if resolved_id:
                    rec["workingDealId"] = resolved_id
                    rec["workingDealId_source"] = resolve_reason
                    rec["workingDealId_resolved_utc"] = utc()
                    working_id = resolved_id

            if working_id:
                ok, info = cancel_working_order_secure(
                    headers=headers,
                    asset=asset,
                    working_id=working_id,
                    reason=reason,
                    old_exec=rec,
                )

                rec["closed_utc"] = utc()
                safe_info = v24_json_safe(info)
                rec["cancel_info"] = safe_info
                rec["status"] = "CANCELLED" if ok else "CANCEL_FAILED"

                results.append({
                    "level": level_key,
                    "action": "CANCEL_LIMIT",
                    "ok": ok,
                    "info": safe_info,
                })

                if not ok:
                    ok_all = False
            else:
                rec["status"] = "CANCEL_BLOCKED_NO_WORKING_ID"
                ok_all = False

                results.append({
                    "level": level_key,
                    "action": "CANCEL_LIMIT",
                    "ok": False,
                    "reason": "NO_WORKING_ID",
                })

    info = {
        "ok": ok_all,
        "asset": asset,
        "reason": reason,
        "basket_exec": v24_json_safe(basket_exec),
        "results": results,
        "utc": utc(),
    }

    event({
        "event": "V24_BASKET_CLOSE_DONE" if ok_all else "V24_BASKET_CLOSE_PARTIAL_FAIL",
        **info,
    })

    return ok_all, info, last_positions_after


def v24_process_basket(headers, asset, cycle, active_exec, broker_items, broker_ids, positions, market_status, exec_state):
    """
    Gestion complète du panier V24 :
    - résolution workingDealId des LIMIT
    - détection des LIMIT remplis
    - calcul PnL global
    - fermeture globale au TP panier
    """
    levels = active_exec.setdefault("levels", {})
    direction = active_exec.get("direction") or cycle.get("direction")

    # 1. Résoudre les vrais workingDealId des LIMIT en attente.
    for level_key, rec in levels.items():
        if str(rec.get("status", "")).startswith("PENDING_LIMIT") and not rec.get("workingDealId"):
            resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, rec)

            if resolved_id:
                rec["workingDealId"] = resolved_id
                rec["workingDealId_source"] = resolve_reason
                rec["workingDealId_resolved_utc"] = utc()

                print(
                    f"{asset:10s} | BASKET_ID_OK | {int(level_key):<3} | {direction:4s} | "
                    f"{float(rec.get('size', 0.0)):<10.6f} | {market_status:9s} | "
                    f"workingId={short_id(resolved_id)}"
                )

                event({
                    "event": "V24_BASKET_WORKING_ID_RESOLVED",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": int(level_key),
                    "workingDealId": resolved_id,
                    "resolve_reason": resolve_reason,
                })
            else:
                rec["workingDealId_resolve_last_reason"] = resolve_reason
                rec["workingDealId_resolve_last_utc"] = utc()

    # 2. Associer les positions broker apparues aux niveaux LIMIT.
    already_tracked = {
        rec.get("brokerDealId")
        for rec in levels.values()
        if rec.get("brokerDealId")
    }

    for item in broker_items:
        deal_id = pos_deal_id(item)
        if not deal_id or deal_id in already_tracked:
            continue

        matched_key = None
        matched_rec = None

        for level_key, rec in levels.items():
            if not str(rec.get("status", "")).startswith("PENDING_LIMIT"):
                continue

            if v24_position_matches_level(item, rec):
                matched_key = level_key
                matched_rec = rec
                break

        if matched_rec is not None:
            try:
                broker_entry_price = (
                    float(pos_entry(item))
                    if pos_entry(item) is not None
                    else None
                )
            except Exception:
                broker_entry_price = None

            matched_rec["status"] = "OPEN_POSITION"
            matched_rec["brokerDealId"] = deal_id
            matched_rec["dealId"] = deal_id
            matched_rec["dealId_source"] = "GET_POSITIONS_AFTER_LIMIT_FILL_BASKET"
            matched_rec["brokerEntryPrice"] = broker_entry_price
            matched_rec["brokerEntryPrice_source"] = (
                "GET_POSITIONS_AFTER_LIMIT_FILL_LEVEL"
                if broker_entry_price is not None
                else "UNAVAILABLE"
            )
            matched_rec["filled_utc"] = utc()

            print(
                f"{asset:10s} | BASKET_FILL | {int(matched_key):<3} | {direction:4s} | "
                f"{float(matched_rec.get('size', 0.0)):<10.6f} | {market_status:9s} | "
                f"deal={short_id(deal_id)} entry={broker_entry_price}"
            )

            event({
                "event": "V24_BASKET_LEVEL_FILLED",
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "level": int(matched_key),
                "direction": direction,
                "brokerDealId": deal_id,
                "brokerEntryPrice": broker_entry_price,
            })

    # 3. Calcul PnL global.
    pnl_total, open_count, target = v24_basket_current_pnl(asset, active_exec)

    active_exec["last_basket_pnl_eur"] = float(pnl_total)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_target_tp_eur"] = target
    active_exec["last_check_utc"] = utc()

    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)

    # 4. TP panier global.
    tp_safety_margin = 0.05

    if open_count > 0 and target is not None and pnl_total >= (target + tp_safety_margin):
        ok, close_info, positions_after = v24_close_basket_secure(
            headers=headers,
            asset=asset,
            basket_exec=active_exec,
            reason="V24_BASKET_GLOBAL_TP",
        )

        if ok:
            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": "V24_BASKET_GLOBAL_TP",
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

            reset_cycle_idle(asset, "V24_BASKET_GLOBAL_TP")

            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_TP_OK | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
            )

            return True, positions_after

        print(
            f"{asset:10s} | BASKET_TP_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
        )
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions

    # 5. Maintien panier.
    pending_count = len([
        rec for rec in levels.values()
        if str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])

    print(
        f"{asset:10s} | BASKET_HOLD | 1-3 | {direction:4s} | "
        f"--         | {market_status:9s} | "
        f"open={open_count} pending={pending_count} pnl={pnl_total:.4f} target={target}"
    )

    event({
        "event": "V24_BASKET_HOLD",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id"),
        "direction": direction,
        "open_count": open_count,
        "pending_count": pending_count,
        "pnl_total": pnl_total,
        "target": target,
    })

    return True, positions



def execute_from_cycle(headers, assets):
    """
    06G2 bloc 3/3 :
    - ouverture sécurisée avec vrai brokerDealId ;
    - fermeture confirmée obligatoire ;
    - changement de niveau sécurisé ;
    - anti-empilement broker.
    """
    sync_base_flags()

    cycles = B.current_cycles()
    exec_state = B.load_json(B.EXEC_STATE_FILE, {"active": {}, "closed": [], "rejected": []})
    exec_state.setdefault("active", {})
    exec_state.setdefault("closed", [])
    exec_state.setdefault("rejected", [])

    status, positions, _ = fetch_positions(headers)

    print()
    print("=" * 170)
    print("06G2 — EXECUTION SECURISEE — BLOC 3/3 — OPEN + CLOSE CONFIRMES")
    print("=" * 170)
    print("SEND_REAL_ORDERS      :", SEND_REAL_ORDERS)
    print("Positions broker HTTP :", status)
    print("-" * 170)
    print("ACTIF      | ACTION         | LVL | DIR  | SIZE       | MARKET    | RAISON / PAYLOAD")
    print("-" * 170)

    for asset in assets:
        cycle = cycles.get(asset)
        active_exec = exec_state.get("active", {}).get(asset)

        broker_items = positions_for_asset(asset, positions)
        broker_ids = deal_ids_for_asset(asset, positions)

        # 1. Aucun cycle interne : si exec_state suit une position, on la ferme.
        if not cycle:
            if active_exec:
                # V24 Basket Limit complet :
                # Une fois le panier créé dans EXEC, le cycle moteur ne doit plus pouvoir
                # fermer L1 ni annuler L2/L3 parce qu'il repasse IDLE.
                # EXEC devient la source de vérité du panier.
                if active_exec.get("basket_mode") == "V24_BASKET_LIMIT":
                    synthetic_cycle = {
                        "asset": asset,
                        "cycle_id": active_exec.get("cycle_id"),
                        "direction": active_exec.get("direction"),
                        "basket_mode": True,
                    }

                    handled, positions_after = v24_process_basket(
                        headers=headers,
                        asset=asset,
                        cycle=synthetic_cycle,
                        active_exec=active_exec,
                        broker_items=broker_items,
                        broker_ids=broker_ids,
                        positions=positions,
                        market_status="TRADEABLE",
                        exec_state=exec_state,
                    )

                    positions = positions_after if positions_after is not None else positions

                    print(
                        f"{asset:10s} | BASKET_KEEP | 1-3 | {active_exec.get('direction', '--'):4s} | "
                        f"--         | TRADEABLE | cycle moteur IDLE ignoré, panier conservé"
                    )

                    B.save_json(B.EXEC_STATE_FILE, exec_state)
                    continue

                # V24 Basket Limit :
                # Si le cycle moteur a disparu alors qu'un LIMIT est encore en attente,
                # on annule le working order au lieu d'appeler close_deal_secure().
                if str(active_exec.get("status", "")).startswith("PENDING_LIMIT"):
                    working_id = active_exec.get("workingDealId")
                    reason = "CYCLE_IDLE_CANCEL_PENDING_LIMIT"

                    if not working_id:
                        resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, active_exec)

                        if resolved_id:
                            active_exec["workingDealId"] = resolved_id
                            active_exec["workingDealId_source"] = resolve_reason
                            active_exec["workingDealId_resolved_utc"] = utc()
                            exec_state.setdefault("active", {})[asset] = active_exec
                            B.save_json(B.EXEC_STATE_FILE, exec_state)
                            working_id = resolved_id
                        else:
                            active_exec["cancel_blocked_reason"] = "WORKING_ID_NOT_RESOLVED"
                            active_exec["workingDealId_resolve_last_reason"] = resolve_reason
                            active_exec["workingDealId_resolve_last_utc"] = utc()
                            exec_state.setdefault("active", {})[asset] = active_exec
                            B.save_json(B.EXEC_STATE_FILE, exec_state)

                            print(
                                f"{asset:10s} | CANCEL_LIMIT_WAIT_ID | --  | --   | --         | --        | "
                                f"workingDealId introuvable, ordre LIMIT conservé localement | {resolve_reason}"
                            )

                            event({
                                "event": "CANCEL_PENDING_LIMIT_BLOCKED_WORKING_ID_NOT_RESOLVED",
                                "asset": asset,
                                "active_exec": active_exec,
                                "resolve_reason": resolve_reason,
                            })
                            continue

                    ok, cancel_info = cancel_working_order_secure(
                        headers=headers,
                        asset=asset,
                        working_id=working_id,
                        reason=reason,
                        old_exec=active_exec,
                    )

                    if not ok:
                        print(
                            f"{asset:10s} | CANCEL_LIMIT_FAIL | --  | --   | --         | --        | "
                            f"working={short_id(working_id)} non annulé, local conservé"
                        )
                        B.save_json(B.EXEC_STATE_FILE, exec_state)
                        continue

                    exec_state.setdefault("closed", []).append({
                        **active_exec,
                        "closed_reason": reason,
                        "closed_utc": utc(),
                        "cancel_info": cancel_info,
                    })
                    exec_state.setdefault("active", {}).pop(asset, None)

                    print(
                        f"{asset:10s} | CANCEL_LIMIT_OK | --  | --   | --         | --        | "
                        f"working={short_id(working_id)} annulé car cycle IDLE"
                    )

                    B.save_json(B.EXEC_STATE_FILE, exec_state)
                    continue

                tracked_id = active_exec.get("brokerDealId") or active_exec.get("dealId")

                ok, close_info, positions_after = close_deal_secure(
                    headers=headers,
                    asset=asset,
                    deal_id=tracked_id,
                    reason="CYCLE_IDLE",
                    old_exec=active_exec,
                )

                if not ok:
                    print(
                        f"{asset:10s} | CLOSE_IDLE_FAIL | --  | --   | --         | --        | "
                        f"deal={short_id(tracked_id)} non fermé, local conservé"
                    )
                    B.save_json(B.EXEC_STATE_FILE, exec_state)
                    continue

                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": "CYCLE_IDLE",
                    "closed_utc": utc(),
                    "close_info": close_info,
                })
                exec_state.setdefault("active", {}).pop(asset, None)

                print(
                    f"{asset:10s} | CLOSE_IDLE_OK | --  | --   | --         | --        | "
                    f"deal={short_id(tracked_id)} fermé confirmé"
                )

                positions = positions_after if positions_after is not None else fetch_positions(headers)[1]

            elif broker_items:
                print(
                    f"{asset:10s} | IDLE_BROKER  | --  | --   | --         | --        | "
                    f"{len(broker_items)} position(s) broker non suivie(s), aucune action"
                )
                event({
                    "event": "IDLE_WITH_BROKER_POSITION",
                    "asset": asset,
                    "broker_ids": broker_ids,
                })
            else:
                print(f"{asset:10s} | IDLE         | --  | --   | --         | --        | aucun cycle")

            continue

        # 2. Cycle interne présent.
        level = int(cycle["level"])
        direction = cycle["direction"]
        size = float(cycle["size"])

        market = B.get_market(asset)
        market_status = market["status"]
        min_size = market["min_size"]

        if market_status != "TRADEABLE":
            print(
                f"{asset:10s} | SKIP_MARKET  | {level:<3} | {direction:4s} | "
                f"{size:<10.6f} | {market_status:9s} | marché non tradeable"
            )
            continue

        if min_size is None or size < min_size:
            print(
                f"{asset:10s} | SKIP_SIZE    | {level:<3} | {direction:4s} | "
                f"{size:<10.6f} | {market_status:9s} | min broker={min_size}"
            )
            continue

        # V24 Basket Limit :
        # Un ordre LIMIT posé via /workingorders n'est pas encore une position broker.
        # Tant que l'ordre n'est pas exécuté, il ne faut surtout pas remettre le cycle à IDLE.
        if active_exec and str(active_exec.get("status", "")).startswith("PENDING_LIMIT"):
            pending_level = int(active_exec.get("level", level))
            pending_ref = active_exec.get("workingDealReference") or active_exec.get("workingDealId")

            # V24 : si le vrai workingDealId n'est pas encore connu,
            # on tente de le résoudre via GET /api/v1/workingorders.
            if not active_exec.get("workingDealId"):
                resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, active_exec)

                if resolved_id:
                    active_exec["workingDealId"] = resolved_id
                    active_exec["workingDealId_source"] = resolve_reason
                    active_exec["workingDealId_resolved_utc"] = utc()
                    exec_state.setdefault("active", {})[asset] = active_exec
                    B.save_json(B.EXEC_STATE_FILE, exec_state)
                    pending_ref = resolved_id

                    print(
                        f"{asset:10s} | LIMIT_ID_OK  | {pending_level:<3} | {direction:4s} | "
                        f"{float(active_exec.get('size', size)):<10.6f} | {market_status:9s} | "
                        f"workingId={short_id(resolved_id)}"
                    )

                    event({
                        "event": "LIMIT_WORKING_ID_RESOLVED",
                        "asset": asset,
                        "cycle_id": cycle.get("cycle_id"),
                        "level": pending_level,
                        "direction": direction,
                        "workingDealId": resolved_id,
                        "resolve_reason": resolve_reason,
                    })
                else:
                    active_exec["workingDealId_resolve_last_reason"] = resolve_reason
                    active_exec["workingDealId_resolve_last_utc"] = utc()
                    exec_state.setdefault("active", {})[asset] = active_exec
                    B.save_json(B.EXEC_STATE_FILE, exec_state)

                    event({
                        "event": "LIMIT_WORKING_ID_NOT_RESOLVED_YET",
                        "asset": asset,
                        "cycle_id": cycle.get("cycle_id"),
                        "level": pending_level,
                        "direction": direction,
                        "resolve_reason": resolve_reason,
                    })

            if len(broker_items) == 0:
                print(
                    f"{asset:10s} | HOLD_LIMIT   | {pending_level:<3} | {direction:4s} | "
                    f"{float(active_exec.get('size', size)):<10.6f} | {market_status:9s} | "
                    f"ordre LIMIT en attente ref={short_id(pending_ref)}"
                )
                event({
                    "event": "HOLD_PENDING_LIMIT",
                    "asset": asset,
                    "cycle": cycle,
                    "active_exec": active_exec,
                    "working_ref": pending_ref,
                })
                continue

            if len(broker_items) == 1:
                broker_id = broker_ids[0] if broker_ids else None
                broker_item = broker_items[0]

                try:
                    broker_entry_price = (
                        float(pos_entry(broker_item))
                        if pos_entry(broker_item) is not None
                        else None
                    )
                except Exception:
                    broker_entry_price = None

                active_exec["status"] = "OPEN_POSITION"
                active_exec["brokerDealId"] = broker_id
                active_exec["dealId"] = broker_id
                active_exec["dealId_source"] = "GET_POSITIONS_AFTER_LIMIT_FILL"
                active_exec["brokerEntryPrice"] = broker_entry_price
                active_exec["brokerEntryPrice_source"] = (
                    "GET_POSITIONS_AFTER_LIMIT_FILL_LEVEL"
                    if broker_entry_price is not None
                    else "UNAVAILABLE"
                )
                active_exec["filled_utc"] = utc()

                exec_state.setdefault("active", {})[asset] = active_exec

                # Synchronisation du cycle moteur avec le prix réel de remplissage du LIMIT.
                if broker_entry_price is not None:
                    try:
                        previous_entry_price = cycle.get("entry_price")
                        cycle["entry_price_theoretical"] = previous_entry_price
                        cycle["entry_price"] = float(broker_entry_price)
                        cycle["entry_price_source"] = "BROKER_LIMIT_FILL_LEVEL"
                        cycle["entry_price_synced_utc"] = utc()

                        cycle_state = B.load_json(B.STATE_FILE, default={"assets": {}})
                        asset_state = cycle_state.setdefault("assets", {}).setdefault(asset, {})
                        current_cycle = asset_state.setdefault("cycle", {})

                        if current_cycle.get("cycle_id") == cycle.get("cycle_id"):
                            current_cycle.update(cycle)
                        else:
                            asset_state["cycle"] = cycle

                        B.save_json(B.STATE_FILE, cycle_state)

                    except Exception as e:
                        event({
                            "event": "LIMIT_FILL_ENTRY_SYNC_FAILED",
                            "asset": asset,
                            "cycle_id": cycle.get("cycle_id"),
                            "level": pending_level,
                            "direction": direction,
                            "brokerEntryPrice": broker_entry_price,
                            "error": str(e),
                        })

                B.save_json(B.EXEC_STATE_FILE, exec_state)

                print(
                    f"{asset:10s} | LIMIT_FILLED | {pending_level:<3} | {direction:4s} | "
                    f"{float(active_exec.get('size', size)):<10.6f} | {market_status:9s} | "
                    f"deal={short_id(broker_id)} brokerEntry={broker_entry_price}"
                )

                event({
                    "event": "LIMIT_FILLED_TO_OPEN_POSITION",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": pending_level,
                    "direction": direction,
                    "brokerDealId": broker_id,
                    "brokerEntryPrice": broker_entry_price,
                    "active_exec": active_exec,
                })

                continue

            print(
                f"{asset:10s} | LIMIT_AMBIG  | {pending_level:<3} | {direction:4s} | "
                f"{float(active_exec.get('size', size)):<10.6f} | {market_status:9s} | "
                f"{len(broker_items)} positions broker après LIMIT, intervention manuelle requise"
            )
            event({
                "event": "PENDING_LIMIT_AMBIGUOUS_BROKER_POSITIONS",
                "asset": asset,
                "cycle": cycle,
                "active_exec": active_exec,
                "broker_ids": broker_ids,
            })
            continue


        # V24 Basket Limit complet :
        # Si l'actif est géré en panier, on autorise plusieurs jambes broker
        # et on délègue toute la logique à v24_process_basket().
        if active_exec and active_exec.get("basket_mode") == "V24_BASKET_LIMIT":
            handled, positions_after = v24_process_basket(
                headers=headers,
                asset=asset,
                cycle=cycle,
                active_exec=active_exec,
                broker_items=broker_items,
                broker_ids=broker_ids,
                positions=positions,
                market_status=market_status,
                exec_state=exec_state,
            )
            positions = positions_after if positions_after is not None else positions
            continue

        # 3. Plusieurs positions broker sur le même actif : blocage total.
        if len(broker_items) > 1:
            print(
                f"{asset:10s} | BLOCK_MULTI  | {level:<3} | {direction:4s} | "
                f"{size:<10.6f} | {market_status:9s} | {len(broker_items)} positions broker, ouverture interdite"
            )
            event({
                "event": "BLOCK_MULTIPLE_BROKER_POSITIONS",
                "asset": asset,
                "cycle": cycle,
                "broker_ids": broker_ids,
            })
            continue

        # 4. Une position broker existe.
        if len(broker_items) == 1:
            broker_id = broker_ids[0] if broker_ids else None

            if not active_exec:
                print(
                    f"{asset:10s} | SKIP_BROKER | {level:<3} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | broker déjà exposé deal={short_id(broker_id)}"
                )
                event({
                    "event": "SKIP_BROKER_POSITION_EXISTS_NO_EXEC",
                    "asset": asset,
                    "cycle": cycle,
                    "broker_ids": broker_ids,
                })
                continue

            tracked_id = active_exec.get("brokerDealId") or active_exec.get("dealId")

            if tracked_id != broker_id:
                print(
                    f"{asset:10s} | DESYNC_ID    | {level:<3} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | exec={short_id(tracked_id)} broker={short_id(broker_id)}"
                )
                event({
                    "event": "DESYNC_EXEC_BROKER_DEALID",
                    "asset": asset,
                    "cycle": cycle,
                    "active_exec": active_exec,
                    "broker_ids": broker_ids,
                })
                continue

            same_cycle = active_exec.get("cycle_id") == cycle.get("cycle_id")
            same_level = int(active_exec.get("level", -1)) == level

            if same_cycle and same_level:
                print(
                    f"{asset:10s} | HOLD_EXEC    | {level:<3} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | niveau déjà exécuté deal={short_id(tracked_id)}"
                )
                continue

            # 5. Niveau changé : fermeture confirmée obligatoire.
            old_level = active_exec.get("level")

            ok, close_info, positions_after = close_deal_secure(
                headers=headers,
                asset=asset,
                deal_id=tracked_id,
                reason="LEVEL_CHANGED",
                old_exec=active_exec,
            )

            if not ok:
                print(
                    f"{asset:10s} | CLOSE_FAIL   | {old_level}->{level:<1} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | deal={short_id(tracked_id)} non fermé, OPEN bloqué"
                )
                B.save_json(B.EXEC_STATE_FILE, exec_state)
                continue

            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": "LEVEL_CHANGED",
                "new_level": level,
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)
            active_exec = None

            print(
                f"{asset:10s} | CLOSE_OK     | {old_level}->{level:<1} | {direction:4s} | "
                f"{size:<10.6f} | {market_status:9s} | deal={short_id(tracked_id)} fermé confirmé"
            )

            positions = positions_after if positions_after is not None else fetch_positions(headers)[1]

            broker_items = positions_for_asset(asset, positions)
            broker_ids = deal_ids_for_asset(asset, positions)

            if broker_items:
                print(
                    f"{asset:10s} | BLOCK_AFTER | {level:<3} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | broker encore exposé ids={','.join(short_id(x) for x in broker_ids)}"
                )
                event({
                    "event": "BLOCK_OPEN_AFTER_CLOSE_REMAINING_BROKER_POSITION",
                    "asset": asset,
                    "cycle": cycle,
                    "broker_ids": broker_ids,
                })
                continue

        # 6. Aucune position broker : ouverture autorisée.
        broker_items = positions_for_asset(asset, positions)

        if len(broker_items) == 0:
            if active_exec:
                tracked_id = active_exec.get("brokerDealId") or active_exec.get("dealId")
                reason = "BROKER_POSITION_DISAPPEARED_TP_STOP_OR_MANUAL"

                print(
                    f"{asset:10s} | BROKER_CLOSED | {level:<3} | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | deal={short_id(tracked_id)} disparu, cycle remis IDLE"
                )

                event({
                    "event": "BROKER_POSITION_DISAPPEARED",
                    "asset": asset,
                    "cycle": cycle,
                    "active_exec": active_exec,
                    "brokerDealId": tracked_id,
                    "reason": reason,
                })

                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": reason,
                    "closed_utc": utc(),
                })
                exec_state.setdefault("active", {}).pop(asset, None)

                reset_cycle_idle(asset, reason)
                B.save_json(B.EXEC_STATE_FILE, exec_state)
                continue

            # V24 Basket Limit complet :

            # On pose directement L1 + L2 + L3 en vrais ordres LIMIT broker.

            ok, record = v24_open_basket_limits_secure(

                headers=headers,

                asset=asset,

                cycle=cycle,

                market_status=market_status,

            )


            if ok:

                exec_state.setdefault("active", {})[asset] = record

                B.save_json(B.EXEC_STATE_FILE, exec_state)

            else:

                exec_state.setdefault("rejected", []).append({

                    "asset": asset,

                    "cycle_id": cycle.get("cycle_id"),

                    "level": level,

                    "direction": direction,

                    "size": size,

                    "reason": "V24_BASKET_LIMIT_REJECTED_OR_PARTIAL_REJECT",

                    "record": record,

                    "utc": utc(),

                })

                reset_cycle_idle(asset, "V24_BASKET_LIMIT_REJECTED_OR_PARTIAL_REJECT")

                B.save_json(B.EXEC_STATE_FILE, exec_state)


            continue

            if ok:
                exec_state.setdefault("active", {})[asset] = record

                # Synchronisation du cycle moteur avec le vrai prix d'entrée broker.
                # Après ouverture confirmée, le PnL du moteur doit utiliser le level réel Capital.com.
                broker_entry_price = record.get("brokerEntryPrice")
                if broker_entry_price is not None:
                    try:
                        previous_entry_price = cycle.get("entry_price")
                        cycle["entry_price_theoretical"] = previous_entry_price
                        cycle["entry_price"] = float(broker_entry_price)
                        cycle["entry_price_source"] = "BROKER_POSITION_LEVEL"
                        cycle["entry_price_synced_utc"] = utc()

                        # Sauvegarde robuste du cycle_state après correction du vrai prix broker.
                        # On ne dépend pas d'une variable locale 'state' inexistante.
                        cycle_state = B.load_json(B.STATE_FILE, default={"assets": {}})
                        asset_state = cycle_state.setdefault("assets", {}).setdefault(asset, {})

                        # On ne remplace que le cycle courant correspondant.
                        current_cycle = asset_state.setdefault("cycle", {})
                        if current_cycle.get("cycle_id") == cycle.get("cycle_id"):
                            current_cycle.update(cycle)
                        else:
                            # Sécurité : si le cycle_id a changé entre-temps, on force quand même
                            # la sauvegarde du cycle actif que l'exécution vient réellement d'ouvrir.
                            asset_state["cycle"] = cycle

                        B.save_json(B.STATE_FILE, cycle_state)

                        event({
                            "event": "SYNC_CYCLE_ENTRY_PRICE_FROM_BROKER",
                            "asset": asset,
                            "cycle_id": cycle.get("cycle_id"),
                            "level": level,
                            "direction": direction,
                            "previous_entry_price": previous_entry_price,
                            "brokerEntryPrice": broker_entry_price,
                            "entry_slippage_points": record.get("entry_slippage_points"),
                        })

                        print(
                            f"{asset:10s} | ENTRY_SYNC   | "
                            f"{level:<3} | {direction:4s} | "
                            f"entry {previous_entry_price} -> broker {broker_entry_price} | "
                            f"slip={record.get('entry_slippage_points')}"
                        )
                    except Exception as e:
                        event({
                            "event": "SYNC_CYCLE_ENTRY_PRICE_FAILED",
                            "asset": asset,
                            "cycle_id": cycle.get("cycle_id"),
                            "level": level,
                            "direction": direction,
                            "brokerEntryPrice": broker_entry_price,
                            "error": str(e),
                        })
                        print(
                            f"{asset:10s} | ENTRY_SYNC_FAIL | "
                            f"{level:<3} | {direction:4s} | brokerEntry={broker_entry_price} | {e}"
                        )
                positions = positions_after
            else:
                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "rejected_utc": utc(),
                    "details": record,
                })
                positions = positions_after

    B.save_json(B.EXEC_STATE_FILE, exec_state)

    print("=" * 170)
    print("06G2 bloc 3/3 terminé : ouverture + fermeture sécurisées, anti-empilement actif.")
    print("Execution state :", B.EXEC_STATE_FILE)
    print("=" * 170)

def show_status_only(assets):
    sync_base_flags()

    print("=" * 140)
    print("BOT_PIVOT_06G2 — BLOC 1/3 — STATUS OUTILS")
    print("=" * 140)
    print("SEND_REAL_ORDERS :", SEND_REAL_ORDERS)
    print("Actifs           :", ",".join(assets))
    print("Note             : bloc 1/3, aucune exécution de cycle.")
    print("=" * 140)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default="ALL")
    parser.add_argument("--mode", choices=["status", "plan"], default="status")
    args = parser.parse_args()

    assets = parse_assets(args.assets)

    if args.mode == "status":
        show_status_only(assets)
        return

    if SEND_REAL_ORDERS:
        load_env()
        headers = login()
    else:
        headers = None

    execute_from_cycle(headers, assets)


if __name__ == "__main__":
    main()
