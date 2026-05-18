#!/usr/bin/env python3
# BOT_PIVOT_06G2_execution_secure.py
# Exécution sécurisée BOT-PIVOT.
# Bloc 1/3 : fondations + résolution du vrai dealId broker.

import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone

import BOT_PIVOT_06G_execution_from_cycle_state as B
import BOT_PIVOT_00B_pnl_eur as PNL


SEND_REAL_ORDERS = False
V242_VERSION_TAG = "BOT_PIVOT_V24_3_DEMO_STORM_TUNING_REPORT"
_V2436_RUNTIME_HEADERS = None
_V2436_RUNTIME_ASSETS = []
_V2436_CLEANUP_RUNNING = False


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sync_base_flags():
    """
    06G2 pilote l'ancien module 06G uniquement comme librairie API.
    On synchronise son flag pour que api_post/api_delete envoient réellement
    uniquement quand 06H aura explicitement activé SEND_REAL_ORDERS.
    """
    B.SEND_REAL_ORDERS = SEND_REAL_ORDERS


def v2436_env_bool(name, default=False):
    raw = os.getenv(str(name), "1" if default else "0")
    return str(raw).strip().lower() in ("1", "true", "yes", "y", "on")


def v2436_env_float(name, default):
    try:
        return float(os.getenv(str(name), default))
    except Exception:
        return float(default)


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
    """
    Curseur V24.1 réglable par paliers de 0.1 :
    0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5.

    En dessous de 1.0 = plus agressif / permissif.
    Au-dessus de 1.0 = plus strict / défensif.
    """
    raw = v241_clamp(v241_env_float(name, default), min_value, max_value)

    # Arrondi au palier de 0.1 le plus proche.
    stepped = round(raw * 10.0) / 10.0

    return round(v241_clamp(stepped, min_value, max_value), 1)


def v241_bollinger_cursor():
    return v241_cursor("BOLLINGER_CURSOR", 1.0, 0.5, 1.5)


def v2435d_bollinger_buffer_cursor():
    # V24.3.5D_BUFFER_ONLY_CURSOR
    # Agit uniquement sur le buffer Bollinger, pas sur le step L2/L3.
    # 1.0 = comportement actuel ; 0.5 = buffer divise par 2 ; 0.0 = colle a la bande.
    return v241_cursor("BOLLINGER_BUFFER_CURSOR", 1.0, 0.0, 1.5)


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


# ============================================================
# V24.2 -- PRICE_AUDIT + Bollinger level guard
# ============================================================

def v242_float_or_none(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def v242_latest_stream_tick(asset):
    import json
    from pathlib import Path

    paths = []
    try:
        paths.append(Path(B.CFG.DATA_DIR) / "ticks" / "signals_latest.json")
    except Exception:
        pass
    paths.append(Path("data/ticks/signals_latest.json"))
    paths.append(Path("data_sample/ticks/signals_latest.json"))

    seen = set()
    for path in paths:
        try:
            path = Path(path)
            if str(path) in seen:
                continue
            seen.add(str(path))
            if not path.exists():
                continue

            data = json.loads(path.read_text(encoding="utf-8"))
            signals = data.get("signals", []) if isinstance(data, dict) else data
            if not isinstance(signals, list):
                continue

            for sig in signals:
                if str(sig.get("asset", "")).upper() == str(asset).upper():
                    return {
                        "bid": v242_float_or_none(sig.get("bid")),
                        "ask": v242_float_or_none(sig.get("ask")),
                        "mid": v242_float_or_none(sig.get("mid")),
                        "spread": v242_float_or_none(sig.get("spread")),
                        "age_sec": v242_float_or_none(sig.get("age_sec") or sig.get("age")),
                        "decision": sig.get("decision"),
                        "source": str(path),
                    }
        except Exception:
            continue

    return {
        "bid": None,
        "ask": None,
        "mid": None,
        "spread": None,
        "age_sec": None,
        "decision": None,
        "source": "UNAVAILABLE",
    }


def v242_price_audit(asset, direction, cycle, bands, levels):
    asset = str(asset).upper()
    direction = str(direction).upper()
    stream = v242_latest_stream_tick(asset)

    snapshot_bid = None
    snapshot_ask = None
    snapshot_error = None
    try:
        snapshot_bid, snapshot_ask = v24_market_bid_ask(asset)
    except Exception as exc:
        snapshot_error = str(exc)

    low_side = None
    high_side = None
    spread = None
    if snapshot_bid is not None and snapshot_ask is not None:
        low_side = min(float(snapshot_bid), float(snapshot_ask))
        high_side = max(float(snapshot_bid), float(snapshot_ask))
        spread = abs(high_side - low_side)

    l1 = v242_float_or_none(levels.get("L1"))
    l2 = v242_float_or_none(levels.get("L2"))
    l3 = v242_float_or_none(levels.get("L3"))
    raw_l1 = v242_float_or_none(levels.get("raw_L1_before_scalp_clamp"))
    if raw_l1 is None:
        raw_l1 = l1

    distance_to_market = None
    if l1 is not None and low_side is not None and high_side is not None:
        if direction == "BUY":
            distance_to_market = low_side - l1
        elif direction == "SELL":
            distance_to_market = l1 - high_side

    audit = {
        "version": V242_VERSION_TAG,
        "asset": asset,
        "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
        "direction": direction,
        "stream_bid": stream.get("bid"),
        "stream_ask": stream.get("ask"),
        "stream_mid": stream.get("mid"),
        "stream_spread": stream.get("spread"),
        "stream_age_sec": stream.get("age_sec"),
        "stream_decision": stream.get("decision"),
        "stream_source": stream.get("source"),
        "snapshot_bid": snapshot_bid,
        "snapshot_ask": snapshot_ask,
        "snapshot_spread": spread,
        "snapshot_error": snapshot_error,
        "BB_LOW": v242_float_or_none(bands.get("lower") if isinstance(bands, dict) else None),
        "BB_MID": v242_float_or_none(bands.get("middle") if isinstance(bands, dict) else None),
        "BB_HIGH": v242_float_or_none(bands.get("upper") if isinstance(bands, dict) else None),
        "raw_L1": raw_l1,
        "final_L1": l1,
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "buffer": v242_float_or_none(levels.get("buffer")),
        "step": v242_float_or_none(levels.get("step")),
        "distance_to_market": distance_to_market,
        "scalp_clamp_applied": bool(levels.get("scalp_clamp_applied", False)),
    }

    v24_event_safe({"event": "PRICE_AUDIT", **audit})

    try:
        print(
            f"{asset:10s} | PRICE_AUDIT | {direction:4s} | "
            f"stream_bid={audit['stream_bid']} stream_ask={audit['stream_ask']} "
            f"snapshot_bid={audit['snapshot_bid']} snapshot_ask={audit['snapshot_ask']} "
            f"BB_LOW={audit['BB_LOW']} BB_MID={audit['BB_MID']} BB_HIGH={audit['BB_HIGH']} "
            f"L1={audit['L1']} L2={audit['L2']} L3={audit['L3']} "
            f"dist={audit['distance_to_market']}"
        )
    except Exception:
        pass

    return audit


def v242_level_guard_min_distance(asset, spread, step):
    import os

    asset = str(asset).upper()
    env_keys = (
        f"V242_MARKETABLE_MIN_DISTANCE_{asset}",
        f"MARKETABLE_MIN_DISTANCE_{asset}",
        "V242_MARKETABLE_MIN_DISTANCE",
    )
    for key in env_keys:
        raw = os.environ.get(key)
        if raw not in (None, ""):
            try:
                return max(0.0, float(str(raw).replace(",", ".")))
            except Exception:
                pass

    spread = abs(float(spread or 0.0))
    step = abs(float(step or 0.0))

    try:
        # Keep the pre-send validation aligned with the legacy broker side gap,
        # but reject instead of moving the level later.
        return max(0.0, float(v24sa_limit_gap(asset, spread)))
    except Exception:
        return max(spread * 1.5, step * 0.05, 1e-10)


def v242_level_guard_min_step(asset, step):
    import os

    asset = str(asset).upper()
    raw = os.environ.get(f"V242_LEVEL_MIN_STEP_{asset}") or os.environ.get("V242_LEVEL_MIN_STEP")
    if raw not in (None, ""):
        try:
            return max(0.0, float(str(raw).replace(",", ".")))
        except Exception:
            pass

    ratio_raw = os.environ.get("V242_LEVEL_MIN_STEP_RATIO", "0.95")
    try:
        ratio = float(str(ratio_raw).replace(",", "."))
    except Exception:
        ratio = 0.95

    return max(abs(float(step or 0.0)) * ratio, 1e-10)


def v242_reject_bollinger_too_far_enabled():
    import os
    return str(os.environ.get("V242_REJECT_BOLLINGER_TOO_FAR", "1")).strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
        "on",
    )


def v24_validate_bollinger_limit_levels(asset, direction, levels, price_audit=None, cycle_id=None):
    asset = str(asset).upper()
    direction = str(direction).upper()
    levels = dict(levels or {})

    try:
        l1 = float(levels["L1"])
        l2 = float(levels["L2"])
        l3 = float(levels["L3"])
    except Exception as exc:
        return {
            "ok": False,
            "reason": "BASKET_REJECT_BAD_LIMIT_LEVELS",
            "detail": f"MISSING_OR_INVALID_LEVELS:{exc}",
        }

    step = abs(float(levels.get("step") or abs(l1 - l2)))

    # V24.3.5H_STREAM_PRICE_GUARD:
    # En DEMO collecte, le signal vient du stream. On utilise donc le stream
    # pour le guard prix si disponible, afin d'eviter les rejets sur snapshot stale.
    try:
        stream_bid = stream_ask = None
        snapshot_bid = snapshot_ask = None
        if price_audit:
            if price_audit.get("stream_bid") is not None and price_audit.get("stream_ask") is not None:
                stream_bid = float(price_audit["stream_bid"])
                stream_ask = float(price_audit["stream_ask"])
            if price_audit.get("snapshot_bid") is not None and price_audit.get("snapshot_ask") is not None:
                snapshot_bid = float(price_audit["snapshot_bid"])
                snapshot_ask = float(price_audit["snapshot_ask"])

        use_stream_guard = str(__import__("os").getenv("V2435H_USE_STREAM_PRICE_GUARD", "0")).lower() in (
            "1", "true", "yes", "y", "on"
        )

        if use_stream_guard and stream_bid is not None and stream_ask is not None:
            raw_bid, raw_ask = stream_bid, stream_ask
        elif snapshot_bid is not None and snapshot_ask is not None:
            raw_bid, raw_ask = snapshot_bid, snapshot_ask
        else:
            raw_bid, raw_ask = v24_market_bid_ask(asset)
    except Exception as exc:
        return {
            "ok": False,
            "reason": "BASKET_REJECT_BAD_LIMIT_LEVELS",
            "detail": f"MARKET_PRICE_UNAVAILABLE:{exc}",
        }

    low_side = min(float(raw_bid), float(raw_ask))
    high_side = max(float(raw_bid), float(raw_ask))
    spread = abs(high_side - low_side)
    min_distance = v242_level_guard_min_distance(asset, spread, step)
    min_step = v242_level_guard_min_step(asset, step)

    if direction == "BUY":
        distance_to_market = low_side - l1
        if distance_to_market <= min_distance:
            reason = "BASKET_REJECT_MARKETABLE_LIMIT"
            detail = f"BUY_L1_TOO_CLOSE_OR_ABOVE_MARKET distance={distance_to_market:.10f} min={min_distance:.10f}"
        elif (l1 - l2) < min_step or (l2 - l3) < min_step:
            reason = "BASKET_REJECT_LEVELS_COLLAPSED"
            detail = f"BUY_STEPS_COLLAPSED d12={l1-l2:.10f} d23={l2-l3:.10f} min_step={min_step:.10f}"
        else:
            reason = None
            detail = None
    elif direction == "SELL":
        distance_to_market = l1 - high_side
        if distance_to_market <= min_distance:
            reason = "BASKET_REJECT_MARKETABLE_LIMIT"
            detail = f"SELL_L1_TOO_CLOSE_OR_BELOW_MARKET distance={distance_to_market:.10f} min={min_distance:.10f}"
        elif (l2 - l1) < min_step or (l3 - l2) < min_step:
            reason = "BASKET_REJECT_LEVELS_COLLAPSED"
            detail = f"SELL_STEPS_COLLAPSED d12={l2-l1:.10f} d23={l3-l2:.10f} min_step={min_step:.10f}"
        else:
            reason = None
            detail = None
    else:
        return {
            "ok": False,
            "reason": "BASKET_REJECT_BAD_LIMIT_LEVELS",
            "detail": f"INVALID_DIRECTION:{direction}",
        }

    max_dist = float(v241_max_l1_distance(asset))

    # V24.3.6:
    # Les ordres trop loin de Bollinger ne doivent plus jamais etre autorises
    # par le sampler demo. L'ancien mode "warning" peut etre reactive
    # explicitement, mais le defaut est fail-closed.
    demo_force_samples = str(os.getenv("V2435F_DEMO_FORCE_ENTRY_SAMPLES", "0")).lower() in (
        "1", "true", "yes", "y", "on"
    )
    hard_distance_guard = v2436_env_bool("V2436_HARD_BOLLINGER_DISTANCE_GUARD", True)

    if (
        reason is None
        and v242_reject_bollinger_too_far_enabled()
        and max_dist > 0.0
        and distance_to_market > max_dist
    ):
        detail = f"distance={distance_to_market:.10f} max_dist={max_dist:.10f}"
        if demo_force_samples and not hard_distance_guard:
            v24_event_safe({
                "event": "BASKET_DEMO_SAMPLE_BB_TOO_FAR_WARN",
                "asset": asset,
                "cycle_id": cycle_id,
                "direction": direction,
                "distance_to_market": distance_to_market,
                "max_bollinger_distance": max_dist,
            })
            print(
                f"{asset:10s} | BASKET_DEMO_SAMPLE_BB_TOO_FAR_WARN | 1-3 | {direction:4s} | "
                f"L1={l1} L2={l2} L3={l3} | DEMO_SAMPLE | {detail} ordre autorise"
            )
        else:
            reason = "BASKET_REJECT_BOLLINGER_TOO_FAR"

    result = {
        "ok": reason is None,
        "reason": reason or "OK",
        "detail": detail,
        "asset": asset,
        "cycle_id": cycle_id,
        "direction": direction,
        "snapshot_bid": raw_bid,
        "snapshot_ask": raw_ask,
        "low_side": low_side,
        "high_side": high_side,
        "spread": spread,
        "min_distance": min_distance,
        "min_step": min_step,
        "max_bollinger_distance": max_dist,
        "distance_to_market": distance_to_market,
        "L1": l1,
        "L2": l2,
        "L3": l3,
        "step": step,
    }

    if not result["ok"]:
        v24_event_safe({"event": result["reason"], **result})
        try:
            print(
                f"{asset:10s} | {result['reason']} | 1-3 | {direction:4s} | "
                f"L1={l1} L2={l2} L3={l3} | "
                f"market_bid={raw_bid} market_ask={raw_ask} | {detail}"
            )
        except Exception:
            pass

    return result


def v2436_validate_entry_stream_guard(asset, direction, cycle, price_audit):
    """
    Refuse d'armer un panier LIMIT si le signal stream courant est absent,
    WAIT, ou oppose a la direction du cycle. Cela evite de transformer une
    vieille intention Bollinger en ordre broker vivant.
    """
    if not v2436_env_bool("V2436_REQUIRE_STREAM_SIGNAL_FOR_LIMIT", True):
        return {"ok": True, "reason": "DISABLED"}

    direction = str(direction or "").upper()
    decision = None
    if isinstance(price_audit, dict):
        decision = price_audit.get("stream_decision")
    decision = str(decision or "").strip().upper()

    no_entry = {"", "WAIT", "IDLE", "NO_SIGNAL", "NONE", "HOLD"}
    buy_opposed = {"SELL", "SHORT", "TREND_DOWN", "DOWN"}
    sell_opposed = {"BUY", "LONG", "TREND_UP", "UP"}

    reason = None
    if decision in no_entry:
        reason = "BASKET_REJECT_STREAM_NO_ENTRY"
    elif direction == "BUY" and decision in buy_opposed:
        reason = "BASKET_REJECT_STREAM_OPPOSED"
    elif direction == "SELL" and decision in sell_opposed:
        reason = "BASKET_REJECT_STREAM_OPPOSED"

    result = {
        "ok": reason is None,
        "reason": reason or "OK",
        "asset": asset,
        "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
        "direction": direction,
        "stream_decision": decision,
    }

    if reason:
        result["detail"] = f"stream_decision={decision} direction={direction}"
        v24_event_safe({"event": reason, **result})
        try:
            print(
                f"{asset:10s} | {reason} | 1-3 | {direction:4s} | "
                f"--         | FILTER    | {result['detail']} aucun ordre envoye"
            )
        except Exception:
            pass

    return result


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
    buffer_cursor = v2435d_bollinger_buffer_cursor()

    # V24.3.5D_BUFFER_ONLY_CURSOR :
    # BOLLINGER_CURSOR continue de piloter le step.
    # BOLLINGER_BUFFER_CURSOR rapproche uniquement L1 de la bande Bollinger.
    buffer = base_buffer * bollinger_cursor * buffer_cursor
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
        "buffer_cursor": buffer_cursor,
        "decimals": decimals,
    }



# ============================================================
# V24.2 -- ancien clamp scalp Bollinger L1 neutralise
# ============================================================
# Objectif V24.2 :
# - conserver Bollinger comme ancre logique
# - ne plus deformer L1 vers le prix courant
# - rejeter proprement via BASKET_REJECT_BOLLINGER_TOO_FAR si besoin
#
# BOLLINGER_CURSOR < 1.0 : plus agressif, L1 plus proche
# BOLLINGER_CURSOR = 1.0 : réglage normal
# BOLLINGER_CURSOR > 1.0 : plus défensif, L1 plus éloigné
# ============================================================

V241_MAX_L1_DISTANCE_BY_ASSET = {
    # SCALP ACTIVE agressif — L1 proche du prix
    "US500": 4.0,
    "US100": 8.0,
    "US30": 24.3,  # V24.3 demo: +35% sur rejet borderline.
    "DE40": 8.0,
    "FR40": 5.0,
    "FRA40": 5.0,
    "UK100": 6.0,
    "J225": 35.0,

    "EURUSD": 0.000243,  # V24.3 demo: +35% sur rejet borderline.
    "GBPUSD": 0.00020,
    "USDJPY": 0.025,
    "EURJPY": 0.0405,  # V24.3 demo: +35% sur rejet borderline.

    "GOLD": 3.0,
    "SILVER": 0.35,
    "OIL_CRUDE": 0.15,
    "OIL_BRENT": 0.15,

    "BTCUSD": 50.0,
    "ETHUSD": 10.8,  # V24.3 demo: +35% sur rejet borderline.
}

V241_LEVEL_DECIMALS_BY_ASSET = {
    "US500": 1,
    "US100": 1,
    "US30": 1,
    "DE40": 1,
    "FR40": 1,
    "FRA40": 1,
    "UK100": 1,
    "J225": 1,

    "EURUSD": 5,
    "GBPUSD": 5,
    "USDJPY": 3,
    "EURJPY": 3,

    "GOLD": 2,
    "SILVER": 3,
    "OIL_CRUDE": 2,
    "OIL_BRENT": 2,

    "BTCUSD": 2,
    "ETHUSD": 2,
}

def v241_max_l1_distance(asset):
    import os

    asset = str(asset).upper()
    base = float(V241_MAX_L1_DISTANCE_BY_ASSET.get(asset, 0.0))

    for key in (
        f"V241_MAX_L1_DISTANCE_{asset}",
        f"MAX_L1_DISTANCE_{asset}",
        f"V24_MAX_L1_DISTANCE_{asset}",
    ):
        val = os.environ.get(key)
        if val not in (None, ""):
            try:
                base = float(str(val).replace(",", "."))
                break
            except Exception:
                pass

    return base * float(v241_bollinger_cursor())

def v241_level_decimals(asset):
    return int(V241_LEVEL_DECIMALS_BY_ASSET.get(str(asset).upper(), 5))

def v241_apply_bollinger_scalp_clamp(asset, direction, levels, cycle_id=None):
    # V24.2: clamp neutralise. On ne rapproche plus un niveau Bollinger
    # vers le prix courant. La validation V24.2 rejette le panier si L1 est
    # trop loin, marketable, ou si L1/L2/L3 sont ecrases.
    out = dict(levels or {})
    out["raw_L1_before_scalp_clamp"] = out.get("L1")
    out["scalp_clamp_applied"] = False
    out["scalp_clamp_disabled_v24_2"] = True
    return out


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

    enriched = dict(cycle)
    enriched["bb_lower_m5"] = float(bands["lower"])
    enriched["bb_middle_m5"] = float(bands["middle"])

    enriched["bb_upper_m5"] = float(bands["upper"])
    levels["raw_L1_before_scalp_clamp"] = levels.get("L1")
    levels["scalp_clamp_applied"] = False
    levels["final_L1_after_v24_2_guard"] = levels.get("L1")

    # V24.1 — filtre Bollinger trop serrée.
    # Refuse le panier si l'écartement BB haute/basse est insuffisant
    # ou trop proche du spread réel.
    bb_check = v241_bb_width_check(
        asset,
        enriched["bb_lower_m5"],
        enriched["bb_upper_m5"],
    )

    enriched["bb_width_m5"] = float(bb_check["width"])
    enriched["bb_min_absolute_width_m5"] = float(bb_check["min_absolute"])
    enriched["bb_spread_m5_check"] = float(bb_check["spread"])
    enriched["bb_min_spread_width_m5"] = float(bb_check["min_spread"])
    enriched["bb_width_required_m5"] = float(bb_check["required"])

    # V24.3.1 - Bollinger width observe only.
    # Mesure uniquement, aucune decision changee.
    if v24_bool_env("V243_BOLLINGER_OBSERVE_LOG", True):
        try:
            _bb_width = float(bb_check["width"])
            _bb_required = float(bb_check["required"])
            _bb_ratio = (_bb_width / _bb_required) if _bb_required > 0 else 0.0
            print(
                f"{asset:10s} | BOLLINGER_WIDTH_OBSERVE | --  | {str(enriched.get('direction', '--')):4s} | "
                f"--         | FILTER    | "
                f"width={_bb_width:.5f} required={_bb_required:.5f} ratio={_bb_ratio:.3f} "
                f"ok={bool(bb_check.get('ok'))} "
                f"abs_min={float(bb_check.get('min_absolute', 0.0)):.5f} "
                f"spread_min={float(bb_check.get('min_spread', 0.0)):.5f}"
            )
        except Exception as _e:
            print(f"{asset:10s} | BOLLINGER_WIDTH_OBSERVE_ERROR | --  | ---- | --         | FILTER    | err={_e}")

    if not bb_check["ok"]:
        print(
            f"{asset:10s} | BOLLINGER_WIDTH_TOO_SMALL | --  | {str(enriched.get('direction', '--')):4s} | "
            f"--         | FILTER    | "
            f"width={bb_check['width']:.5f} required={bb_check['required']:.5f} "
            f"abs_min={bb_check['min_absolute']:.5f} spread={bb_check['spread']:.5f}"
        )

        event({
            "event": "V24_BOLLINGER_WIDTH_TOO_SMALL",
            "asset": asset,
            "cycle_id": enriched.get("cycle_id"),
            "direction": enriched.get("direction"),
            "bb_lower_m5": enriched.get("bb_lower_m5"),
            "bb_upper_m5": enriched.get("bb_upper_m5"),
            "bb_width_m5": bb_check["width"],
            "bb_width_required_m5": bb_check["required"],
            "bb_min_absolute_width_m5": bb_check["min_absolute"],
            "bb_spread_m5_check": bb_check["spread"],
            "bb_min_spread_width_m5": bb_check["min_spread"],
        })

        raise RuntimeError(
            f"BOLLINGER_WIDTH_TOO_SMALL {asset}: "
            f"width={bb_check['width']:.5f} required={bb_check['required']:.5f}"
        )

    price_audit = v242_price_audit(
        asset=asset,
        direction=direction,
        cycle=cycle,
        bands=bands,
        levels=levels,
    )
    stream_guard = v2436_validate_entry_stream_guard(
        asset=asset,
        direction=direction,
        cycle=cycle,
        price_audit=price_audit,
    )
    enriched["v2436_stream_entry_guard"] = stream_guard

    if not stream_guard.get("ok"):
        raise RuntimeError(
            f"{stream_guard.get('reason')} {asset}: "
            f"{stream_guard.get('detail')}"
        )

    level_guard = v24_validate_bollinger_limit_levels(
        asset=asset,
        direction=direction,
        levels=levels,
        price_audit=price_audit,
        cycle_id=cycle.get("cycle_id"),
    )

    enriched["price_audit"] = price_audit
    enriched["v242_level_guard"] = level_guard

    if not level_guard.get("ok"):
        raise RuntimeError(
            f"{level_guard.get('reason')} {asset}: "
            f"{level_guard.get('detail')}"
        )

    enriched["bollinger_limit_levels"] = levels

    # V24.3.1 - Bollinger entry observe only.
    # Mesure uniquement du placement L1/L2/L3, aucune decision changee.
    if v24_bool_env("V243_BOLLINGER_ENTRY_OBSERVE_LOG", True):
        try:
            def _lvl_val(container, key):
                if not isinstance(container, dict):
                    return None
                return (
                    container.get(key)
                    or container.get(str(key))
                    or container.get(f"L{key}")
                    or container.get(f"l{key}")
                )

            _l1 = _lvl_val(levels, 1)
            _l2 = _lvl_val(levels, 2)
            _l3 = _lvl_val(levels, 3)

            _bb_low = enriched.get("bb_lower_m5")
            _bb_mid = enriched.get("bb_middle_m5")
            _bb_high = enriched.get("bb_upper_m5")
            _bb_width = enriched.get("bb_width_m5")
            _bb_req = enriched.get("bb_width_required_m5")

            _dist = None
            _max_dist = None
            try:
                if isinstance(level_guard, dict):
                    _dist = level_guard.get("distance_to_market")
                    _max_dist = level_guard.get("max_bollinger_distance")
            except Exception:
                pass

            _ratio = None
            try:
                _ratio = float(_dist) / float(_max_dist) if _dist is not None and _max_dist not in (None, 0) else None
            except Exception:
                _ratio = None

            _ratio_s = "none" if _ratio is None else f"{_ratio:.3f}"
            _dist_s = "none" if _dist is None else f"{float(_dist):.10f}"
            _max_s = "none" if _max_dist is None else f"{float(_max_dist):.10f}"

            print(
                f"{asset:10s} | BOLLINGER_ENTRY_OBSERVE | --  | {str(enriched.get('direction', '--')):4s} | "
                f"--         | OBSERVE   | "
                f"BB_LOW={float(_bb_low):.5f} BB_MID={float(_bb_mid):.5f} BB_HIGH={float(_bb_high):.5f} "
                f"width={float(_bb_width):.5f} required={float(_bb_req):.5f} "
                f"L1={_l1} L2={_l2} L3={_l3} "
                f"dist={_dist_s} max_dist={_max_s} dist_ratio={_ratio_s}"
            )
        except Exception as _e:
            print(f"{asset:10s} | BOLLINGER_ENTRY_OBSERVE_ERROR | --  | ---- | --         | OBSERVE   | err={_e}")
    enriched["v242_levels_validated"] = True

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
        "price_audit": price_audit,
        "level_guard": level_guard,
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

    # V24.3.3_TARGETED_LIMIT_ARMING_DISTANCE
    # Filtre d'armement uniquement : ne change pas les niveaux, tailles, TP, stops ni guards.
    # Si L1 est trop loin du prix courant pour un panier scalp, on n'envoie aucun LIMIT broker.
    try:
        import os as _v2433_os

        _v2433_enabled = str(
            _v2433_os.getenv("V2433_LIMIT_ARMING_ENABLED", "1")
        ).strip().lower() not in ("0", "false", "no", "off")

        _v2433_mult = float(
            _v2433_os.getenv("V2433_LIMIT_ARMING_STEP_MULT", "1.5")
        )

        _l1 = levels.get("L1")
        _l2 = levels.get("L2")
        _dist = None
        _max_dist_old = None

        if isinstance(level_guard, dict):
            _dist = level_guard.get("distance_to_market")
            _max_dist_old = level_guard.get("max_bollinger_distance")

        if _v2433_enabled and _l1 is not None and _l2 is not None and _dist is not None:
            _l1f = float(_l1)
            _l2f = float(_l2)
            _distf = float(_dist)
            _stepf = abs(_l2f - _l1f)

            if _stepf > 0:
                _allowed = _stepf * _v2433_mult
                _ratio = _distf / _stepf

                if _distf > _allowed:
                    print(
                        f"{asset:10s} | BASKET_ARMING_DELAYED | "
                        f"1-3 | {direction:4s} | --         | FILTER    | "
                        f"reason=TOO_FAR_FOR_ARMING "
                        f"L1={_l1f} L2={_l2f} "
                        f"dist={_distf:.10f} step={_stepf:.10f} "
                        f"max_allowed={_allowed:.10f} "
                        f"dist_step_ratio={_ratio:.3f} "
                        f"mult={_v2433_mult:.3f} "
                        f"old_max_dist={_max_dist_old} "
                        f"aucun ordre envoye"
                    )

                    try:
                        v24_event_safe({
                            "event": "BASKET_ARMING_DELAYED",
                            "asset": asset,
                            "cycle_id": cycle.get("cycle_id"),
                            "direction": direction,
                            "L1": _l1f,
                            "L2": _l2f,
                            "distance_to_market": _distf,
                            "step": _stepf,
                            "max_allowed": _allowed,
                            "dist_step_ratio": _ratio,
                            "mult": _v2433_mult,
                            "old_max_bollinger_distance": _max_dist_old,
                            "reason": "TOO_FAR_FOR_ARMING",
                        })
                    except Exception:
                        pass

                    return None

    except Exception as _e:
        print(
            f"{asset:10s} | BASKET_ARMING_CHECK_ERROR | "
            f"1-3 | {direction:4s} | --         | FILTER    | err={_e} allow_by_safety=False"
        )
        if v2436_env_bool("V2436_ARMING_CHECK_FAIL_CLOSED", True):
            try:
                v24_event_safe({
                    "event": "BASKET_ARMING_CHECK_ERROR_BLOCKED",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "direction": direction,
                    "error": str(_e),
                })
            except Exception:
                pass
            return None

    return enriched




# ============================================================
# V24.1 — Filtre largeur Bollinger minimale par actif
# ============================================================

V241_MIN_BB_WIDTH_BY_ASSET = {
    "US500": 10.0,
    "US100": 30.0,
    "US30": 50.0,
    "DE40": 30.0,
    "FR40": 15.0,
    "FRA40": 15.0,
    "UK100": 20.0,
    "J225": 100.0,

    "EURUSD": 0.00040,
    "GBPUSD": 0.00050,
    "USDJPY": 0.080,
    "EURJPY": 0.100,

    "GOLD": 8.0,
    "SILVER": 1.0,
    "OIL_CRUDE": 0.50,
    "OIL_BRENT": 0.50,

    "BTCUSD": 150.0,
    "ETHUSD": 15.0,
}


def v241_env_float_local(name, default):
    import os
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


def v241_min_bb_width(asset):
    import os
    asset = str(asset).upper()

    # Override possible sans modifier le code :
    # MIN_BB_WIDTH_BTCUSD=200
    env_name = f"MIN_BB_WIDTH_{asset}"
    try:
        if os.environ.get(env_name) is not None:
            return float(os.environ.get(env_name))
    except Exception:
        pass

    return float(V241_MIN_BB_WIDTH_BY_ASSET.get(asset, 0.0))


def v241_bb_width_spread_mult():
    # Sécurité complémentaire :
    # la Bollinger doit être au moins 3 fois plus large que le spread.
    return max(1.0, v241_env_float_local("MIN_BB_WIDTH_SPREAD_MULT", 3.0))


def v241_bb_width_check(asset, lower, upper):
    lower = float(lower)
    upper = float(upper)
    width = abs(upper - lower)

    min_absolute = v241_min_bb_width(asset)

    try:
        raw_bid, raw_ask = v24_market_bid_ask(asset)
        spread = abs(float(raw_ask) - float(raw_bid))
    except Exception:
        spread = 0.0

    min_spread = spread * v241_bb_width_spread_mult()
    required = max(float(min_absolute), float(min_spread))

    return {
        "ok": width >= required,
        "width": float(width),
        "min_absolute": float(min_absolute),
        "spread": float(spread),
        "min_spread": float(min_spread),
        "required": float(required),
    }




# ============================================================
# V24.1 — Stop broker airbag global panier
# ============================================================

def v241_stop_airbag_step_mult():
    # Distance supplémentaire au-delà de L3.
    # 1.5 = stop sous/au-dessus de L3 à 1,5 step.
    return max(0.5, v241_env_float_local("STOP_AIRBAG_STEP_MULT", 1.5))


def v241_stop_airbag_spread_mult():
    # Sécurité minimale liée au spread.
    return max(1.0, v241_env_float_local("STOP_AIRBAG_SPREAD_MULT", 3.0))


def v241_broker_min_stop_distance(asset):
    """
    Lecture prudente des règles broker Capital.com.
    Selon les marchés, le nom de règle peut varier.
    """
    try:
        market = B._market_json(asset)
        rules = market.get("dealingRules", {}) or {}

        asset_key = str(asset or "").upper()
        disable_gs = v24sa_env_csv_set(
            "V24_DISABLE_GUARANTEED_STOP_ASSETS",
            "EURUSD,GBPUSD,EURJPY,USDJPY,OIL_CRUDE,OIL_BRENT,BTCUSD,ETHUSD,J225,SILVER"
        )

        if asset_key in disable_gs:
            keys = [
                "minStopDistance",
                "minStopOrProfitDistance",
                "minNormalStopOrLimitDistance",
            ]
        else:
            keys = [
                "minGuaranteedStopDistance",
                "minStopDistance",
                "minStopOrProfitDistance",
                "minGuaranteedStopOrProfitDistance",
                "minNormalStopOrLimitDistance",
            ]

        vals = []

        for k in keys:
            if k in rules:
                value, unit = B._rule_value(rules.get(k))
                if value is not None:
                    vals.append(float(value))

        return max(vals) if vals else 0.0

    except Exception:
        return 0.0


def v241_round_stop_distance(asset, distance):
    """
    Arrondit le stopDistance au pas broker si disponible.
    """
    distance = float(distance)

    try:
        market = B._market_json(asset)
        rules = market.get("dealingRules", {}) or {}
        step_value, step_unit = B._rule_value(rules.get("minStepDistance"))

        if step_value is not None:
            return float(B._round_up_to_step(distance, float(step_value)))

    except Exception:
        pass

    return round(distance, 10)


def v241_apply_global_airbag_stop(asset, direction, payload, bollinger_levels, current_level):
    """
    Applique un stopDistance global panier.

    BUY :
    - L1/L2/L3 partagent un stop théorique sous L3.

    SELL :
    - L1/L2/L3 partagent un stop théorique au-dessus de L3.

    Le broker reçoit un stopDistance propre à chaque jambe,
    mais le niveau de stop final est aligné autour du même airbag global.
    """
    direction = str(direction).upper()
    current_level = int(current_level)

    l1 = float(bollinger_levels["L1"])
    l2 = float(bollinger_levels["L2"])
    l3 = float(bollinger_levels["L3"])
    entry_level = float(payload["level"])

    step = abs(l2 - l1)
    if step <= 0:
        step = abs(l3 - l1) / 2.0

    try:
        raw_bid, raw_ask = v24_market_bid_ask(asset)
        spread = abs(float(raw_ask) - float(raw_bid))
    except Exception:
        spread = 0.0

    min_stop = v241_broker_min_stop_distance(asset)

    extra = max(
        float(step) * v241_stop_airbag_step_mult(),
        float(spread) * v241_stop_airbag_spread_mult(),
        float(min_stop),
    )

    if direction == "BUY":
        global_stop_level = l3 - extra
        stop_distance = entry_level - global_stop_level
    else:
        global_stop_level = l3 + extra
        stop_distance = global_stop_level - entry_level

    stop_distance = max(float(stop_distance), float(min_stop), 0.00000001)
    stop_distance = v241_round_stop_distance(asset, stop_distance)

    # On impose uniquement stopDistance.
    # stopLevel éventuel supprimé pour éviter conflit payload broker.
    payload.pop("stopLevel", None)
    payload["stopDistance"] = float(stop_distance)

    print(
        f"{asset:10s} | GLOBAL_AIRBAG_STOP | L{current_level:<3} | {direction:4s} | "
        f"entry={entry_level:.6f} stopLevel≈{global_stop_level:.6f} "
        f"stopDistance={stop_distance:.6f} step={step:.6f} spread={spread:.6f} minStop={min_stop:.6f}"
    )

    try:
        event({
            "event": "V24_GLOBAL_AIRBAG_STOP",
            "asset": asset,
            "direction": direction,
            "level": current_level,
            "entry_level": entry_level,
            "global_stop_level": global_stop_level,
            "stop_distance": stop_distance,
            "step": step,
            "spread": spread,
            "min_stop": min_stop,
            "stop_airbag_step_mult": v241_stop_airbag_step_mult(),
            "stop_airbag_spread_mult": v241_stop_airbag_spread_mult(),
        })
    except Exception:
        pass

    return payload


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

    # V24.1 — stop broker airbag global panier.
    # Le stop doit protéger l'ensemble du panier, pas couper L1 trop tôt.
    payload = v241_apply_global_airbag_stop(
        asset=asset,
        direction=direction,
        payload=payload,
        bollinger_levels=bollinger_levels,
        current_level=level,
    )

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

    try:
        if cycle.get("bollinger_limit_levels") and cycle.get("v242_levels_validated"):
            enriched_cycle = cycle
        else:
            enriched_cycle = v24_enrich_cycle_with_bollinger_m5(headers, cycle)
    except RuntimeError as e:
        reject_prefixes = (
            "BOLLINGER_WIDTH_TOO_SMALL",
            "BASKET_REJECT_BOLLINGER_TOO_FAR",
            "BASKET_REJECT_BAD_LIMIT_LEVELS",
            "BASKET_REJECT_LEVELS_COLLAPSED",
            "BASKET_REJECT_MARKETABLE_LIMIT",
            "BASKET_REJECT_STREAM_NO_ENTRY",
            "BASKET_REJECT_STREAM_OPPOSED",
        )
        if str(e).startswith(reject_prefixes):
            _asset = str(cycle.get("asset", locals().get("asset", "?"))) if isinstance(cycle, dict) else str(locals().get("asset", "?"))
            _direction = str(cycle.get("direction", locals().get("direction", "?"))) if isinstance(cycle, dict) else str(locals().get("direction", "?"))
            _level = locals().get("level", cycle.get("level", None) if isinstance(cycle, dict) else None)
            _reason = str(e).split(" ", 1)[0]

            print(
                f"{_asset:10s} | {_reason[:28]:28s} | -- | {_direction:4s} | "
                f"--         | TRADEABLE | {e}"
            )

            return False, {
                "asset": _asset,
                "direction": _direction,
                "level": _level,
                "status": "SKIPPED",
                "event": _reason,
                "reason": str(e),
            }
        raise


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
        "price_audit": cycle.get("price_audit"),
        "level_guard": cycle.get("v242_level_guard"),
        "requested_limit_level": payload.get("level"),
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
            "requested_limit_price": payload.get("level"),
            "price_audit": cycle.get("price_audit"),
            "level_guard": cycle.get("v242_level_guard"),
              "broker_tp_distance": None,
              "software_tp_note": "NO_BROKER_TP__BASKET_SOFTWARE_TP_ONLY",
            "payload": payload,
            "created_utc": utc(),
            "dry_run": True,
        }

    payload = v24sa_guard_working_payload(payload)
    stop_too_wide, stop_info = v2436_payload_stop_too_wide(payload)
    if stop_too_wide:
        v2436_print_stop_too_wide_block(stop_info, "LIMIT_REQUEST")
        reason = "LIMIT_REJECT_STOP_DISTANCE_TOO_WIDE"
        event({
            "event": reason,
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "payload": payload,
            "stop_guard": stop_info,
            "reason": reason,
        })
        return False, {
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "status": "SKIPPED",
            "event": reason,
            "reason": reason,
            "payload": payload,
            "stop_guard": stop_info,
        }

    status, data = B.api_post(headers, "/api/v1/workingorders", payload)
    status, data, payload = v24sa_retry_working_order(headers, payload, status, data)
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
        "requested_limit_price": payload.get("level"),
        "price_audit": cycle.get("price_audit"),
        "level_guard": cycle.get("v242_level_guard"),
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



def normalize_working_orders_response(data):
    return working_order_items(data)


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
    Match prudent et tolérant :
    - asset / epic
    - direction
    - niveau LIMIT prioritaire
    - taille avec tolérance broker

    Important :
    Capital.com peut arrondir une taille locale 0.4499999999 en 0.44.
    Un matching trop strict crée des ordres orphelins.
    """
    d = working_order_data(item)

    epic = d.get("epic") or item.get("epic")
    direction = d.get("direction") or item.get("direction")
    size = d.get("orderSize") or d.get("size") or item.get("orderSize") or item.get("size")
    level = d.get("orderLevel") or d.get("level") or item.get("orderLevel") or item.get("level")

    if epic != active_exec.get("asset"):
        return False

    if str(direction).upper() != str(active_exec.get("direction")).upper():
        return False

    # Niveau LIMIT : critère prioritaire après asset/direction.
    try:
        expected_level = float(active_exec.get("limit_price"))
        actual_level = float(level)
        level_tol = max(1e-8, abs(expected_level) * 1e-7)
        if abs(actual_level - expected_level) > level_tol:
            return False
    except Exception:
        return False

    # Taille : tolérance volontairement souple à cause des arrondis broker.
    try:
        expected_size = float(active_exec.get("size"))
        actual_size = float(size)
        size_tol = max(0.02, abs(expected_size) * 0.03, 1e-9)
        if abs(actual_size - expected_size) > size_tol:
            return False
    except Exception:
        return False

    return True


def v24_broker_positions_for_asset_from_list(positions, asset, direction=None):
    """
    Filtre les positions broker pour un actif.
    Utilisé avant tout reset local dangereux.
    """
    out = []
    for p in positions or []:
        if not isinstance(p, dict):
            continue
        m = p.get("market", {}) or {}
        pos = p.get("position", {}) or {}
        epic = m.get("epic") or pos.get("epic") or p.get("epic") or ""
        name = m.get("instrumentName") or ""

        if epic != asset and asset not in str(epic) and asset not in str(name):
            continue

        if direction:
            pdir = pos.get("direction") or p.get("direction") or ""
            if str(pdir).upper() != str(direction).upper():
                continue

        out.append(p)

    return out


def v24_broker_pending_orders_for_asset(headers, asset, direction=None):
    """
    Relit directement /workingorders côté broker pour savoir si un actif
    a encore des ordres LIMIT en attente.
    """
    status, data = B.api_get(headers, "/api/v1/workingorders")
    items = normalize_working_orders_response(data)
    out = []

    for item in items:
        if not isinstance(item, dict):
            continue

        d = working_order_data(item)
        m = item.get("marketData", {}) or item.get("market", {}) or {}

        epic = d.get("epic") or item.get("epic") or m.get("epic") or ""
        name = m.get("instrumentName") or ""

        if epic != asset and asset not in str(epic) and asset not in str(name):
            continue

        odir = d.get("direction") or item.get("direction") or ""
        if direction and str(odir).upper() != str(direction).upper():
            continue

        out.append(item)

    return out, status, data


def v24_cancel_broker_pending_for_asset(headers, asset, direction=None, reason="V24_BROKER_PENDING_CLEANUP"):
    """
    Annule tous les working orders broker encore actifs pour l'actif.
    Sert de filet de sécurité contre les ordres orphelins.
    """
    orders, status, raw = v24_broker_pending_orders_for_asset(
        headers=headers,
        asset=asset,
        direction=direction,
    )

    results = []
    for item in orders:
        working_id = working_order_deal_id(item)
        d = working_order_data(item)

        if not working_id:
            results.append({
                "ok": False,
                "reason": "NO_WORKING_ID_FOR_BROKER_PENDING_CLEANUP",
                "item": item,
            })
            continue

        try:
            ok_cancel, cancel_info = cancel_working_order_secure(
                headers=headers,
                asset=asset,
                working_id=working_id,
                reason=reason,
                old_exec={
                    "asset": asset,
                    "direction": d.get("direction") or direction,
                    "size": d.get("orderSize") or d.get("size"),
                    "limit_price": d.get("orderLevel") or d.get("level"),
                    "workingDealId": working_id,
                },
            )
        except Exception as e:
            ok_cancel, cancel_info = False, {"exception": str(e)}

        results.append({
            "working_id": working_id,
            "ok": bool(ok_cancel),
            "info": cancel_info,
        })

    return results



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
    c["software_leg_reference_tp_eur"] = float(0.20 * level)
    c["basket_level"] = level
    c["basket_mode"] = True

    return c


def v24_open_basket_limits_secure(headers, asset, cycle, market_status):
    """
    Pose les 3 LIMIT V24.2 apres validation globale du panier.
    Aucun ordre broker ne part tant que L1/L2/L3 ne sont pas tous valides.
    """
    try:
        cycle = v24_enrich_cycle_with_bollinger_m5(headers, cycle)
    except RuntimeError as e:
        reason = str(e).split(" ", 1)[0]
        if reason.startswith("BOLLINGER_WIDTH_TOO_SMALL"):
            reason = "BOLLINGER_WIDTH_TOO_SMALL"
        if not (
            reason.startswith("BASKET_REJECT_")
            or reason == "BOLLINGER_WIDTH_TOO_SMALL"
        ):
            raise

        event({
            "event": "V24_BASKET_PRECHECK_REJECT",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
            "direction": cycle.get("direction") if isinstance(cycle, dict) else None,
            "reason": str(e),
            "reject_event": reason,
        })
        print(
            f"{asset:10s} | BASKET_REJECT | 1-3 | {cycle.get('direction', '--') if isinstance(cycle, dict) else '--':4s} | "
            f"{float(cycle.get('size', 0.0)) if isinstance(cycle, dict) else 0.0:<10.6f} | {market_status:9s} | "
            f"precheck={reason} aucun ordre envoye"
        )
        return False, {
            "reason": reason,
            "detail": str(e),
            "asset": asset,
            "cycle_id": cycle.get("cycle_id") if isinstance(cycle, dict) else None,
            "direction": cycle.get("direction") if isinstance(cycle, dict) else None,
            "status": "SKIPPED",
        }

    if not cycle:
        reason = "BOLLINGER_M5_UNAVAILABLE_OR_INVALID"
        return False, {
            "reason": reason,
            "asset": asset,
            "cycle_id": None,
            "status": "SKIPPED",
        }

    levels = {}
    ok_any = False
    rejects = []

    def v2435_l123_atomic_abort(failed_level, failed_record):
        # V24.3.5_L123_ATOMIC_BASKET:
        # stop au premier rejet, aucun panier partiel accepte.
        reason = (
            "BASKET_L123_ABORT_L1_REJECT"
            if int(failed_level) == 1 and not levels
            else "BASKET_L123_ATOMIC_CANCEL"
        )

        cancel_results = []
        broker_cleanup_results = []
        orphan_close_results = []

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
                    reason=reason,
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
                    "reason": "NO_WORKING_ID_TO_CANCEL_AFTER_L123_ATOMIC_REJECT",
                    "record": rec,
                })

        if levels:
            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=cycle.get("direction"),
                    reason=reason + "_BROKER_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            orphan_close_results = v24_close_orphan_positions_after_partial_reject(
                headers=headers,
                asset=asset,
                reason=reason + "_ORPHAN_CLOSE",
                levels=levels,
            )

        event({
            "event": reason,
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "direction": cycle.get("direction"),
            "failed_level": int(failed_level),
            "failed_record": failed_record,
            "levels": levels,
            "rejects": rejects,
            "cancel_results": cancel_results,
            "broker_cleanup_results": broker_cleanup_results,
            "orphan_close_results": orphan_close_results,
        })

        print(
            f"{asset:10s} | {reason} | 1-3 | {cycle.get('direction'):4s} | "
            f"{float(cycle.get('size', 0.0)):<10.6f} | {market_status:9s} | "
            f"failed=L{int(failed_level)} acceptes={len(levels)} rejetes={len(rejects)}"
        )

        return False, {
            "reason": reason,
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "failed_level": int(failed_level),
            "failed_record": failed_record,
            "levels": levels,
            "rejects": rejects,
            "cancel_results": cancel_results,
            "broker_cleanup_results": broker_cleanup_results,
            "orphan_close_results": orphan_close_results,
            "status": "ABORTED",
        }

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
            continue

        rejects.append({
            "level": basket_level,
            "record": record,
        })
        return v2435_l123_atomic_abort(basket_level, record)

    if len(levels) != 3:
        rejects.append({
            "level": "1-3",
            "record": {
                "reason": "V2435_L123_ATOMIC_INCOMPLETE_AFTER_LOOP",
                "levels_count": len(levels),
            },
        })
        return v2435_l123_atomic_abort(0, rejects[-1]["record"])


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


def v24_bool_env(name, default=True):
    import os
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def v24_float_or_none(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def v24_position_pnl_candidates(item):
    """
    Recherche prudente des champs PnL éventuellement fournis par Capital.com.
    On ne les utilise pas encore pour fermer : on les logue pour comparaison.
    """
    out = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                full = f"{path}.{key}" if path else key
                lk = key.lower()

                if any(s in lk for s in ("pnl", "profit", "loss", "upl", "unreal")):
                    val = v24_float_or_none(v)
                    if val is not None:
                        out.append({"path": full, "value": val})

                if isinstance(v, (dict, list)):
                    walk(v, full)

        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, (dict, list)):
                    walk(v, f"{path}[{i}]")

    walk(item)
    return out[:20]


def v24_leg_pnl_detail(asset, direction, entry_price, current_price, size):
    """
    Audit PnL V24.1.

    Prix :
    - BUY valorisé à la sortie au BID / côté bas
    - SELL valorisé à la sortie à l'ASK / côté haut

    Calcul :
    - méthode distance_for_target_eur
    - méthode centrale PNL.pnl_eur
    - brut indicatif
    - PnL retenu = minimum conservateur entre les méthodes EUR disponibles
    """
    entry_price = float(entry_price)
    current_price = float(current_price)
    size = float(size)
    d = str(direction).upper()

    if d == "BUY":
        price_move = current_price - entry_price
    else:
        price_move = entry_price - current_price

    raw_price_times_size = float(price_move * size)

    pnl_distance = None
    one_eur_distance = None
    distance_error = None

    try:
        one_eur_distance = float(PNL.profit_distance_for_target_eur(asset, size, 1.0))
        if one_eur_distance > 0:
            pnl_distance = float(price_move / one_eur_distance)
    except Exception as e:
        distance_error = str(e)

    pnl_module = None
    module_error = None

    try:
        pnl_module = float(PNL.pnl_eur(asset, d, entry_price, current_price, size))
    except Exception as e:
        module_error = str(e)

    eur_candidates = []
    if pnl_distance is not None:
        eur_candidates.append(float(pnl_distance))
    if pnl_module is not None:
        eur_candidates.append(float(pnl_module))

    if eur_candidates:
        # Pour ne pas fermer trop tôt, on retient le plus conservateur.
        pnl_selected = float(min(eur_candidates))
        pnl_source = "CONSERVATIVE_MIN_DISTANCE_MODULE"
    else:
        pnl_selected = float(raw_price_times_size)
        pnl_source = "FALLBACK_RAW_PRICE_TIMES_SIZE"

    return {
        "asset": asset,
        "direction": d,
        "entry_price": float(entry_price),
        "current_price": float(current_price),
        "size": float(size),
        "price_move": float(price_move),
        "raw_price_times_size": float(raw_price_times_size),
        "one_eur_distance": one_eur_distance,
        "pnl_distance_eur": pnl_distance,
        "pnl_module_eur": pnl_module,
        "pnl_selected_eur": pnl_selected,
        "pnl_source": pnl_source,
        "distance_error": distance_error,
        "module_error": module_error,
    }


def v24_leg_pnl_eur(asset, direction, entry_price, current_price, size):
    return float(
        v24_leg_pnl_detail(
            asset=asset,
            direction=direction,
            entry_price=entry_price,
            current_price=current_price,
            size=size,
        )["pnl_selected_eur"]
    )


# ============================================================
# V24_BROKER_UPL_TP_PATCH_V1
# Source de vérité TP panier = Capital.com position.upl
# ============================================================

def v24_pick_broker_upl_eur(candidates):
    """
    Extrait le PnL broker réel depuis les candidats retournés par
    v24_position_pnl_candidates(), en privilégiant position.upl.

    Retourne None si aucun PnL broker fiable n'est disponible.
    """
    for c in candidates or []:
        try:
            path = str(c.get("path", "")).lower()
            if "position.upl" not in path and not path.endswith(".upl") and "upl" not in path:
                continue

            val = c.get("value")
            if val is None:
                continue

            if isinstance(val, str):
                val = val.replace(",", ".").strip()

            return float(val)
        except Exception:
            continue

    return None


def v24_basket_current_pnl(asset, basket_exec, broker_items=None):
    """
    Calcule le PnL global du panier sur les niveaux OPEN_POSITION.

    Règle prix :
    - BUY sort au BID / côté bas
    - SELL sort à l'ASK / côté haut

    Règle sécurité :
    - PnL retenu = calcul EUR conservateur
    - audit détaillé logué pour comparaison avec Capital.com
    """
    raw_bid, raw_ask = v24_market_bid_ask(asset)

    low_side = min(float(raw_bid), float(raw_ask))
    high_side = max(float(raw_bid), float(raw_ask))

    broker_items = broker_items or []
    broker_by_deal = {}

    for item in broker_items:
        try:
            did = pos_deal_id(item)
            if did:
                broker_by_deal[did] = item
        except Exception:
            pass

    total = 0.0
    open_count = 0
    audit_legs = []
    broker_upl_total = 0.0
    broker_upl_count = 0
    broker_upl_missing = 0

    for level_key, rec in basket_exec.get("levels", {}).items():
        if rec.get("status") != "OPEN_POSITION":
            continue

        direction = rec.get("direction")
        entry = rec.get("brokerEntryPrice")
        size = rec.get("size")

        if entry is None or size is None:
            rec["last_pnl_error"] = "MISSING_ENTRY_OR_SIZE"
            continue

        # BUY se ferme au côté bas du spread.
        # SELL se ferme au côté haut du spread.
        current = low_side if direction == "BUY" else high_side
        price_side = "BID_LOW_SIDE_FOR_BUY" if direction == "BUY" else "ASK_HIGH_SIDE_FOR_SELL"

        detail = v24_leg_pnl_detail(asset, direction, entry, current, size)
        pnl = float(detail["pnl_selected_eur"])

        broker_deal_id = rec.get("brokerDealId") or rec.get("dealId")
        broker_item = broker_by_deal.get(broker_deal_id)
        broker_pnl_candidates = v24_position_pnl_candidates(broker_item) if broker_item else []
        broker_upl_eur = v24_pick_broker_upl_eur(broker_pnl_candidates)

        if broker_upl_eur is None:
            broker_upl_missing += 1
        else:
            broker_upl_total += float(broker_upl_eur)
            broker_upl_count += 1

        rec["last_pnl_eur"] = float(pnl)
        rec["last_pnl_detail"] = detail
        rec["last_broker_pnl_candidates"] = broker_pnl_candidates
        rec["last_broker_upl_eur"] = broker_upl_eur
        rec["last_price_used"] = float(current)
        rec["last_raw_bid"] = float(raw_bid)
        rec["last_raw_ask"] = float(raw_ask)
        rec["last_price_side"] = price_side

        total += float(pnl)
        open_count += 1

        audit_legs.append({
            "level": str(level_key),
            "direction": direction,
            "entry": float(entry),
            "size": float(size),
            "raw_bid": float(raw_bid),
            "raw_ask": float(raw_ask),
            "exit_used": float(current),
            "price_side": price_side,
            "pnl_selected_eur": float(pnl),
            "pnl_distance_eur": detail.get("pnl_distance_eur"),
            "pnl_module_eur": detail.get("pnl_module_eur"),
            "raw_price_times_size": detail.get("raw_price_times_size"),
            "pnl_source": detail.get("pnl_source"),
            "broker_upl_eur": broker_upl_eur,
            "broker_pnl_candidates": broker_pnl_candidates[:5],
        })

    target = float(0.20 * open_count) if open_count > 0 else None
    broker_upl_total_complete = (
        float(broker_upl_total)
        if open_count > 0 and broker_upl_count >= open_count
        else None
    )

    basket_exec["last_pnl_audit"] = {
        "asset": asset,
        "raw_bid": float(raw_bid),
        "raw_ask": float(raw_ask),
        "low_side": float(low_side),
        "high_side": float(high_side),
        "open_count": int(open_count),
        "target": target,
        "total_selected_eur": float(total),
        "total_internal_eur": float(total),
        "total_broker_upl_eur": broker_upl_total_complete,
        "broker_upl_partial_total_eur": float(broker_upl_total),
        "broker_upl_count": int(broker_upl_count),
        "broker_upl_missing": int(broker_upl_missing),
        "tp_decision_source": "BROKER_POSITION_UPL" if broker_upl_total_complete is not None else "NO_BROKER_UPL_BLOCK_TP",
        "tp_decision_pnl_eur": broker_upl_total_complete,
        "legs": audit_legs,
        "checked_utc": utc(),
    }

    if open_count > 0 and v24_bool_env("V24_PNL_AUDIT", True):
        broker_upl_log = "none" if broker_upl_total_complete is None else f"{broker_upl_total_complete:.4f}"

        for leg in audit_legs:
            broker_short = ",".join(
                f"{x.get('path')}={x.get('value')}"
                for x in leg.get("broker_pnl_candidates", [])[:3]
            ) or "none"

            print(
                f"{asset:10s} | PNL_AUDIT_LEG | L{leg['level']:<3} | {str(leg['direction']):4s} | "
                f"entry={leg['entry']:.6f} size={leg['size']:.6f} "
                f"bid={leg['raw_bid']:.6f} ask={leg['raw_ask']:.6f} "
                f"exit={leg['exit_used']:.6f} side={leg['price_side']} "
                f"pnl_sel={leg['pnl_selected_eur']:.4f} "
                f"pnl_dist={leg['pnl_distance_eur']} "
                f"pnl_mod={leg['pnl_module_eur']} "
                f"raw={leg['raw_price_times_size']} "
                f"src={leg['pnl_source']} "
                f"broker_upl={leg.get('broker_upl_eur')} "
                f"broker={broker_short}"
            )

        print(
            f"{asset:10s} | PNL_AUDIT_TOTAL | 1-3 | {str(basket_exec.get('direction', '--')):4s} | "
            f"open={open_count} pnl={total:.4f} broker_upl={broker_upl_log} target={target}"
        )

        try:
            event({
                "event": "V24_BASKET_PNL_AUDIT",
                "asset": asset,
                "cycle_id": basket_exec.get("cycle_id"),
                "audit": basket_exec.get("last_pnl_audit"),
            })
        except Exception:
            pass

    return total, open_count, target



# ============================================================
# V24.1 — sécurité anti-jambe orpheline après panier partiel rejeté
# ============================================================

def v24_broker_positions_for_asset(headers, asset):
    """
    Relit les positions broker et retourne uniquement celles de l'actif.
    Utilisé après un BASKET_REJECT partiel, car un LIMIT accepté peut être exécuté
    avant que le bot ait fini d'annuler le panier.
    """
    import requests

    base = (
        getattr(B, "BASE_URL", None)
        or globals().get("BASE_URL")
        or "https://demo-api-capital.backend-capital.com/api/v1"
    )

    try:
        r = requests.get(base.rstrip("/") + "/positions", headers=headers, timeout=20)
        status = r.status_code
        data = r.json()
    except Exception as e:
        info = {
            "ok": False,
            "asset": asset,
            "reason": "FETCH_POSITIONS_EXCEPTION",
            "exception": str(e),
            "utc": utc(),
        }
        event({"event": "V24_FETCH_POSITIONS_FOR_ORPHAN_FAILED", **info})
        return [], info

    positions = []
    for item in data.get("positions", []) or []:
        market = item.get("market", {}) or {}
        pos = item.get("position", {}) or {}
        epic = market.get("epic") or pos.get("epic")
        if epic == asset:
            positions.append(item)

    info = {
        "ok": status == 200,
        "asset": asset,
        "http_status": status,
        "count": len(positions),
        "utc": utc(),
    }

    return positions, info


def v24_close_orphan_positions_after_partial_reject(headers, asset, reason, levels=None):
    """
    Sécurité forte :
    si un panier LIMIT est partiellement rejeté, un ordre accepté peut avoir été
    exécuté avant son annulation. On relit alors le broker et on ferme toute
    position orpheline sur cet actif.
    """
    import time

    results = []
    closed_ids = set()

    # Plusieurs scans courts : Capital.com peut transformer un working order
    # accepté en position avec un léger délai.
    for attempt, delay in enumerate((0.25, 0.75, 1.25), start=1):
        time.sleep(delay)

        positions, fetch_info = v24_broker_positions_for_asset(headers, asset)

        event({
            "event": "V24_BASKET_REJECT_ORPHAN_SCAN",
            "asset": asset,
            "attempt": attempt,
            "fetch_info": fetch_info,
            "positions_count": len(positions),
            "reason": reason,
            "utc": utc(),
        })

        if not positions:
            continue

        for item in positions:
            market = item.get("market", {}) or {}
            pos = item.get("position", {}) or {}

            deal_id = pos.get("dealId") or item.get("dealId")
            if not deal_id:
                results.append({
                    "attempt": attempt,
                    "ok": False,
                    "reason": "ORPHAN_POSITION_WITHOUT_DEAL_ID",
                    "position": v24_json_safe(item),
                })
                continue

            if deal_id in closed_ids:
                continue

            old_exec = {
                "asset": asset,
                "brokerDealId": deal_id,
                "dealId": deal_id,
                "direction": pos.get("direction"),
                "size": pos.get("size"),
                "brokerEntryPrice": pos.get("level"),
                "status": "ORPHAN_POSITION_AFTER_BASKET_REJECT",
                "market": market,
                "position": pos,
            }

            print(
                f"{asset:10s} | BASKET_REJECT_ORPHAN_FOUND | --  | "
                f"{str(pos.get('direction', '--')):4s} | "
                f"{float(pos.get('size') or 0.0):<10.6f} | TRADEABLE | "
                f"deal={short_id(deal_id)} level={pos.get('level')}"
            )

            try:
                ok_close, close_info, positions_after = close_deal_secure(
                    headers=headers,
                    asset=asset,
                    deal_id=deal_id,
                    reason=reason,
                    old_exec=old_exec,
                )
            except Exception as e:
                ok_close, close_info, positions_after = False, {"exception": str(e)}, None

            closed_ids.add(deal_id)

            safe_info = v24_json_safe(close_info)

            event_name = (
                "V24_BASKET_REJECT_ORPHAN_CLOSE_OK"
                if ok_close
                else "V24_BASKET_REJECT_ORPHAN_CLOSE_FAILED"
            )

            event({
                "event": event_name,
                "asset": asset,
                "attempt": attempt,
                "dealId": deal_id,
                "direction": pos.get("direction"),
                "size": pos.get("size"),
                "level": pos.get("level"),
                "reason": reason,
                "close_info": safe_info,
                "utc": utc(),
            })

            print(
                f"{asset:10s} | "
                f"{'BASKET_REJECT_ORPHAN_CLOSE_OK' if ok_close else 'BASKET_REJECT_ORPHAN_CLOSE_FAIL'} | "
                f"--  | {str(pos.get('direction', '--')):4s} | "
                f"{float(pos.get('size') or 0.0):<10.6f} | TRADEABLE | "
                f"deal={short_id(deal_id)} reason={reason}"
            )

            results.append({
                "attempt": attempt,
                "ok": bool(ok_close),
                "dealId": deal_id,
                "direction": pos.get("direction"),
                "size": pos.get("size"),
                "level": pos.get("level"),
                "close_info": safe_info,
            })

    return results


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




# ============================================================
# V24.1 — garde-fous paniers LIMIT ratés / vides
# ============================================================

def v241_env_float(name, default):
    import os
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


def v24_pending_basket_max_age_sec():
    # Un panier LIMIT non exécuté ne doit pas bloquer la marge trop longtemps.
    return max(30.0, v241_env_float("PENDING_BASKET_MAX_AGE_SEC", 180.0))


def v24_tp_safety_margin_eur():
    # Le PnL est déjà conservateur : BUY au BID, SELL à l'ASK.
    # On ne rajoute pas 0,05 € par défaut, sinon le +0,20 devient +0,25.
    return max(0.0, v241_env_float("V24_TP_SAFETY_MARGIN_EUR", 0.0))


# ============================================================
# V24.2 -- global margin guard
# ============================================================

def v242_max_margin_cfd_eur():
    import os
    raw = os.environ.get("MAX_MARGIN_CFD_EUR") or os.environ.get("V242_MAX_MARGIN_CFD_EUR") or "3000"
    try:
        return float(str(raw).replace(",", "."))
    except Exception:
        return 3000.0


def v242_min_available_to_trade_eur():
    import os
    raw = os.environ.get("MIN_AVAILABLE_TO_TRADE_EUR") or os.environ.get("V242_MIN_AVAILABLE_TO_TRADE_EUR") or "500"
    try:
        return float(str(raw).replace(",", "."))
    except Exception:
        return 500.0


def v242_pick_first_float(*values):
    for value in values:
        try:
            if value is None:
                continue
            return float(value)
        except Exception:
            continue
    return None


def v242_account_float(account, keys):
    if not isinstance(account, dict):
        return None

    balance = account.get("balance", {}) or {}
    if not isinstance(balance, dict):
        balance = {}

    candidates = []
    for key in keys:
        candidates.append(account.get(key))
        candidates.append(balance.get(key))

    return v242_pick_first_float(*candidates)


def v242_fetch_account_margin_snapshot(headers):
    max_margin = v242_max_margin_cfd_eur()
    min_available = v242_min_available_to_trade_eur()

    if not SEND_REAL_ORDERS or headers is None:
        return {
            "ok": True,
            "source": "DRY_RUN",
            "margin_cfd_eur": None,
            "available_to_trade_eur": None,
            "account_value_eur": None,
            "max_margin_cfd_eur": max_margin,
            "min_available_to_trade_eur": min_available,
            "block_new_baskets": False,
            "pressure": False,
        }

    status, data = B.api_get(headers, "/api/v1/accounts")
    accounts = data.get("accounts", []) if isinstance(data, dict) else []

    if status not in (200, 201, 202) or not accounts:
        snapshot = {
            "ok": False,
            "source": "GET_ACCOUNTS_FAILED",
            "http_status": status,
            "response": data,
            "margin_cfd_eur": None,
            "available_to_trade_eur": None,
            "account_value_eur": None,
            "max_margin_cfd_eur": max_margin,
            "min_available_to_trade_eur": min_available,
            "block_new_baskets": True,
            "pressure": True,
            "block_reasons": ["ACCOUNT_MARGIN_UNAVAILABLE"],
        }
        v24_event_safe({"event": "MARGIN_GUARD_ACCOUNT_FETCH_FAILED", **snapshot})
        return snapshot

    account = None
    for candidate in accounts:
        if v242_account_float(candidate, (
            "available",
            "availableToTrade",
            "availableToDeal",
            "cashAvailable",
        )) is not None:
            account = candidate
            break

    if account is None:
        account = accounts[0]
    account_value = v242_account_float(account, (
        "balance",
        "accountValue",
        "equity",
        "deposit",
        "availableBalance",
    ))
    available = v242_account_float(account, (
        "available",
        "availableToTrade",
        "availableToDeal",
        "cashAvailable",
    ))
    explicit_margin = v242_account_float(account, (
        "margin",
        "marginUsed",
        "usedMargin",
        "marginRequirement",
        "reserved",
    ))

    margin_cfd = explicit_margin
    if margin_cfd is None and account_value is not None and available is not None:
        margin_cfd = max(0.0, float(account_value) - float(available))

    block_reasons = []
    if margin_cfd is not None and margin_cfd >= max_margin:
        block_reasons.append("MARGIN_CFD_TOO_HIGH")
    if available is not None and available < min_available:
        block_reasons.append("AVAILABLE_TO_TRADE_TOO_LOW")

    snapshot = {
        "ok": True,
        "source": "GET_ACCOUNTS",
        "account_id": account.get("accountId"),
        "account_name": account.get("accountName") or account.get("accountType"),
        "currency": account.get("currency") or (account.get("balance", {}) or {}).get("currency"),
        "margin_cfd_eur": margin_cfd,
        "available_to_trade_eur": available,
        "account_value_eur": account_value,
        "max_margin_cfd_eur": max_margin,
        "min_available_to_trade_eur": min_available,
        "block_new_baskets": bool(block_reasons),
        "pressure": bool(block_reasons),
        "block_reasons": block_reasons,
    }

    v24_event_safe({"event": "MARGIN_GUARD_SNAPSHOT", **snapshot})
    return snapshot


def v242_margin_guard_blocks_new_basket(snapshot):
    if not isinstance(snapshot, dict):
        return False, []
    return bool(snapshot.get("block_new_baskets")), list(snapshot.get("block_reasons") or [])


def v242_margin_guard_pressure(snapshot):
    if not isinstance(snapshot, dict):
        return False
    return bool(snapshot.get("pressure"))




# ============================================================
# V24.3 -- sélection marge uniquement au-dessus du seuil 3100
# ============================================================

def v243_margin_selector_enabled():
    return v243_bool_env("V243_MARGIN_SELECTOR_ENABLED", True)


def v243_margin_selector_threshold_eur():
    return v243_env_float("V243_MARGIN_SELECTOR_THRESHOLD_EUR", 3100.0)


def v243_margin_selector_cooldown_sec():
    return max(0.0, v243_env_float("V243_MARGIN_SELECTOR_COOLDOWN_SEC", 45.0))


def v243_margin_selector_active(snapshot):
    if not v243_margin_selector_enabled():
        return False
    if not isinstance(snapshot, dict):
        return False
    margin = snapshot.get("margin_cfd_eur")
    if margin is None:
        return False
    try:
        return float(margin) >= float(v243_margin_selector_threshold_eur())
    except Exception:
        return False


def v243_margin_selector_recent_cancel(exec_state):
    if not isinstance(exec_state, dict):
        return False
    last = exec_state.get("v243_margin_selector_last_cancel_utc")
    if not last:
        return False
    return v24_age_sec_from_iso(last) < v243_margin_selector_cooldown_sec()


def v243_margin_selector_pending_count(active_exec):
    levels = (active_exec or {}).get("levels") or {}
    return len([
        rec for rec in levels.values()
        if isinstance(rec, dict) and str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])


def v243_margin_selector_l1_ratio(active_exec):
    try:
        levels = active_exec.get("levels") or {}
        rec = levels.get("1") or levels.get(1) or next(iter(levels.values()))
        guard = rec.get("level_guard") or {}
        dist = abs(float(guard.get("distance_to_market")))
        max_dist = abs(float(guard.get("max_bollinger_distance")))
        if max_dist > 0:
            return dist / max_dist
    except Exception:
        return None
    return None


def v243_margin_selector_keep_score(asset, active_exec):
    asset = str(asset).upper()
    ratio = v243_margin_selector_l1_ratio(active_exec)
    age = v24_age_sec_from_iso((active_exec or {}).get("created_utc"))

    ratio_score = 0.0
    if ratio is not None:
        ratio_score = max(0.0, 2.0 - min(2.0, float(ratio))) * 100.0

    age_score = max(0.0, 300.0 - float(age)) / 30.0

    asset_bonus = {
        "ETHUSD": 14.0,
        "US30": 12.0,
        "EURUSD": 10.0,
        "EURJPY": 10.0,
        "OIL_CRUDE": 6.0,
    }.get(asset, 0.0)

    risk_penalty = {
        "SILVER": 35.0,
        "BTCUSD": 25.0,
        "J225": 18.0,
        "GOLD": 12.0,
        "US100": 10.0,
    }.get(asset, 0.0)

    return float(ratio_score + age_score + asset_bonus - risk_penalty)


def v243_margin_selector_worst_pending(exec_state, positions=None):
    rows = []

    for asset, rec in list((exec_state.get("active") or {}).items()):
        if not isinstance(rec, dict) or rec.get("basket_mode") != "V24_BASKET_LIMIT":
            continue

        pending_count = v243_margin_selector_pending_count(rec)
        if pending_count <= 0:
            continue

        try:
            broker_open_count = len(positions_for_asset(asset, positions or []))
        except Exception:
            broker_open_count = 0

        try:
            local_open_count = int(rec.get("last_open_count") or 0)
        except Exception:
            local_open_count = 0

        # On ne sélectionne que les paniers sans position ouverte.
        if max(broker_open_count, local_open_count) > 0:
            continue

        rows.append({
            "asset": asset,
            "record": rec,
            "pending_count": pending_count,
            "age_sec": v24_age_sec_from_iso(rec.get("created_utc")),
            "ratio": v243_margin_selector_l1_ratio(rec),
            "score": v243_margin_selector_keep_score(asset, rec),
        })

    if not rows:
        return None

    rows.sort(key=lambda r: (float(r.get("score") or 0.0), -float(r.get("age_sec") or 0.0)))
    return rows[0]

def v242_print_margin_guard_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return
    try:
        print(
            "MARGIN_GUARD | "
            f"margin_cfd={snapshot.get('margin_cfd_eur')} "
            f"max={snapshot.get('max_margin_cfd_eur')} "
            f"available={snapshot.get('available_to_trade_eur')} "
            f"min_available={snapshot.get('min_available_to_trade_eur')} "
            f"block={snapshot.get('block_new_baskets')} "
            f"reasons={','.join(snapshot.get('block_reasons') or [])}"
        )
    except Exception:
        pass


def v24_age_sec_from_iso(iso_text):
    from datetime import datetime, timezone
    if not iso_text:
        return 0.0
    try:
        s = str(iso_text).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return 0.0


# ============================================================
# V24.2.1 -- STORM GUARD / PANIC GUARD
# ============================================================

def v243_bool_env(name, default=True):
    import os
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def v243_env_float(name, default):
    import os
    raw = os.environ.get(name, str(default))
    try:
        return float(str(raw).replace(",", "."))
    except Exception:
        return float(default)


def v243_env_int(name, default):
    import os
    raw = os.environ.get(name, str(default))
    try:
        return int(float(str(raw).replace(",", ".")))
    except Exception:
        return int(default)


def v243_asset_env_float(prefix, asset, default):
    import os
    asset = str(asset).upper()
    for key in (f"{prefix}_{asset}", prefix):
        raw = os.environ.get(key)
        if raw not in (None, ""):
            try:
                return float(str(raw).replace(",", "."))
            except Exception:
                pass
    return float(default)


def v243_storm_guard_enabled():
    return v243_bool_env("V243_STORM_GUARD_ENABLED", True)


def v243_tick_tail_lines(path, max_lines):
    from pathlib import Path

    path = Path(path)
    if not path.exists():
        return []

    max_lines = max(100, int(max_lines))
    block_size = 65536
    blocks = []
    newline_count = 0

    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            pos = f.tell()

            while pos > 0 and newline_count <= max_lines:
                read_size = min(block_size, pos)
                pos -= read_size
                f.seek(pos)
                block = f.read(read_size)
                blocks.append(block)
                newline_count += block.count(b"\n")

        data = b"".join(reversed(blocks)).decode("utf-8", errors="ignore")
        return data.splitlines()[-max_lines:]
    except Exception:
        return []


def v243_latest_ticks_file():
    from pathlib import Path

    candidates = []
    try:
        tick_dir = Path(B.CFG.TICKS_DIR)
        candidates.extend(tick_dir.glob("ticks_*.jsonl"))
    except Exception:
        pass

    candidates.extend(Path("data/ticks").glob("ticks_*.jsonl"))

    candidates = [p for p in candidates if p.exists()]
    if not candidates:
        return None

    try:
        return max(candidates, key=lambda p: p.stat().st_mtime)
    except Exception:
        return candidates[-1]


def v243_recent_ticks_by_asset(assets, lookback_sec=None, max_lines=None):
    if lookback_sec is None:
        lookback_sec = v243_env_float("V243_STORM_LOOKBACK_SEC", 90.0)
    if max_lines is None:
        max_lines = v243_env_int("V243_STORM_TICK_TAIL_LINES", 20000)

    wanted = {str(a).upper() for a in assets}
    out = {a: [] for a in wanted}
    path = v243_latest_ticks_file()
    if not path:
        return out, "NO_TICKS_FILE"

    for line in v243_tick_tail_lines(path, max_lines=max_lines):
        try:
            row = json.loads(line)
        except Exception:
            continue

        asset = str(row.get("epic") or row.get("asset") or "").upper()
        if asset not in wanted:
            continue

        age_sec = v24_age_sec_from_iso(row.get("received_utc") or row.get("utc") or row.get("timestamp"))
        if age_sec > float(lookback_sec):
            continue

        try:
            mid = float(row.get("mid"))
        except Exception:
            continue

        out.setdefault(asset, []).append({
            "mid": mid,
            "bid": v242_float_or_none(row.get("bid")),
            "ask": v242_float_or_none(row.get("ask")),
            "spread": v242_float_or_none(row.get("spread")),
            "age_sec": float(age_sec),
        })

    return out, str(path)


def v243_asset_step(asset):
    asset = str(asset).upper()
    cfg = BOLLINGER_BASKET_CONFIG.get(asset) or BOLLINGER_BASKET_CONFIG.get("_DEFAULT", {})
    try:
        return abs(float(cfg.get("step", 0.0)) * float(v241_bollinger_cursor()))
    except Exception:
        return 0.0


def v243_asset_storm_profile(asset, ticks_by_asset):
    asset = str(asset).upper()
    sig = v24_latest_signal_for_asset(asset)
    ticks = list((ticks_by_asset or {}).get(asset) or [])

    reasons = []
    details = {}

    spread = v24_sig_float(sig, ["spread"], None)
    spread_median = v24_sig_float(sig, ["spread_median", "spread_med", "median_spread"], None)
    spread_ratio = None

    if spread is not None and spread_median is not None and spread_median > 0:
        spread_ratio = float(spread) / float(spread_median)
        spread_mult = v243_asset_env_float("V243_STORM_SPREAD_MULT", asset, 3.0)
        if spread_ratio >= spread_mult:
            reasons.append(f"SPREAD_EXPLOSION:{spread_ratio:.2f}x")

    step = max(v243_asset_step(asset), 1e-12)
    move_points = None
    range_points = None

    if len(ticks) >= 3:
        mids = [float(t["mid"]) for t in ticks if t.get("mid") is not None]
        if len(mids) >= 3:
            move_points = abs(mids[-1] - mids[0])
            range_points = max(mids) - min(mids)

            move_mult = v243_asset_env_float("V243_STORM_MOVE_STEP_MULT", asset, 2.5)
            range_mult = v243_asset_env_float("V243_STORM_RANGE_STEP_MULT", asset, 3.0)

            if move_points >= step * move_mult:
                reasons.append(f"FAST_MOVE:{move_points:.10g}>={step * move_mult:.10g}")

            if range_points >= step * range_mult:
                reasons.append(f"FAST_RANGE:{range_points:.10g}>={step * range_mult:.10g}")

    details.update({
        "asset": asset,
        "alarm": bool(reasons),
        "reasons": reasons,
        "spread": spread,
        "spread_median": spread_median,
        "spread_ratio": spread_ratio,
        "step": step,
        "tick_count_recent": len(ticks),
        "move_points": move_points,
        "range_points": range_points,
        "signal_age_sec": v24_sig_float(sig, ["age_sec", "tick_age_sec"], None),
    })

    return details


def v243_build_storm_snapshot(assets):
    if not v243_storm_guard_enabled():
        return {"enabled": False, "global_storm": False, "asset_profiles": {}, "alerts": []}

    ticks_by_asset, tick_source = v243_recent_ticks_by_asset(assets)
    profiles = {}
    alerts = []

    for asset in assets:
        profile = v243_asset_storm_profile(asset, ticks_by_asset)
        profiles[str(asset).upper()] = profile
        if profile.get("alarm"):
            alerts.append(str(asset).upper())

    alert_set = set(alerts)
    index_assets = {"US500", "US100", "US30", "DE40", "FR40", "UK100", "J225"}
    index_alerts = sorted(alert_set & index_assets)
    oil_alert = "OIL_CRUDE" in alert_set or "OIL_BRENT" in alert_set
    gold_alert = "GOLD" in alert_set

    global_count = v243_env_int("V243_STORM_GLOBAL_ALERT_COUNT", 4)
    systemic_combo = (
        (oil_alert and gold_alert and bool(index_alerts))
        or
        ((oil_alert or gold_alert) and len(index_alerts) >= 2 and len(alerts) >= 3)
    )
    global_storm = len(alerts) >= global_count or systemic_combo

    snapshot = {
        "enabled": True,
        "global_storm": bool(global_storm),
        "alerts": alerts,
        "alert_count": len(alerts),
        "index_alerts": index_alerts,
        "oil_alert": bool(oil_alert),
        "gold_alert": bool(gold_alert),
        "systemic_combo": bool(systemic_combo),
        "tick_source": tick_source,
        "asset_profiles": profiles,
        "utc": utc(),
    }

    v24_event_safe({"event": "STORM_GUARD_SNAPSHOT", **snapshot})
    return snapshot


def v243_print_storm_guard_snapshot(snapshot):
    if not isinstance(snapshot, dict) or not snapshot.get("enabled", False):
        print("STORM_GUARD | enabled=False")
        return

    alerts = snapshot.get("alerts") or []
    mode = "GLOBAL" if snapshot.get("global_storm") else ("LOCAL" if alerts else "OFF")
    try:
        print(
            "STORM_GUARD | "
            f"mode={mode} alerts={len(alerts)} "
            f"assets={','.join(alerts[:8])} "
            f"systemic={snapshot.get('systemic_combo')}"
        )
    except Exception:
        pass


def v243_storm_guard_blocks_asset(snapshot, asset):
    if not isinstance(snapshot, dict) or not snapshot.get("enabled", False):
        return False, []

    asset = str(asset).upper()
    if snapshot.get("global_storm"):
        return True, ["GLOBAL_STORM"] + list(snapshot.get("alerts") or [])

    profile = (snapshot.get("asset_profiles") or {}).get(asset) or {}
    if profile.get("alarm"):
        return True, list(profile.get("reasons") or ["ASSET_STORM"])

    return False, []


def v243_storm_emergency_close_enabled():
    return v243_bool_env("V243_STORM_EMERGENCY_CLOSE_ENABLED", True)


def v243_storm_max_loss_eur(open_count):
    per_leg = v243_env_float("V243_STORM_MAX_LOSS_PER_OPEN_LEG_EUR", 0.60)
    minimum = v243_env_float("V243_STORM_MAX_LOSS_MIN_EUR", 0.80)
    return max(float(minimum), max(1, int(open_count or 0)) * float(per_leg))


def v243_max_loss_guard_enabled():
    return v243_bool_env("V243_MAX_LOSS_GUARD_ENABLED", True)


def v243_basket_max_loss_eur(open_count):
    count = max(1, min(3, int(open_count or 1)))

    explicit = {
        1: v243_env_float("V243_MAX_LOSS_1_OPEN_EUR", 1.50),
        2: v243_env_float("V243_MAX_LOSS_2_OPEN_EUR", 3.00),
        3: v243_env_float("V243_MAX_LOSS_3_OPEN_EUR", 5.00),
    }

    # Compatibilite avec l'ancien reglage lineaire.
    # Si l'utilisateur force V243_MAX_LOSS_PER_OPEN_LEG_EUR, il reprend la main.
    import os
    if os.environ.get("V243_MAX_LOSS_PER_OPEN_LEG_EUR") not in (None, ""):
        per_leg = v243_env_float("V243_MAX_LOSS_PER_OPEN_LEG_EUR", 1.50)
        minimum = v243_env_float("V243_MAX_LOSS_MIN_EUR", 1.50)
        return max(float(minimum), count * float(per_leg))

    return abs(float(explicit[count]))


def v24_cancel_all_pending_limits(headers, asset, levels, reason):
    cancel_results = []

    for level_key, rec in list(levels.items()):
        if not str(rec.get("status", "")).startswith("PENDING_LIMIT"):
            continue

        working_id = rec.get("workingDealId")

        if not working_id:
            try:
                resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, rec)
            except Exception as e:
                resolved_id, resolve_reason, resolve_response = None, f"RESOLVE_EXCEPTION:{e}", None

            if resolved_id:
                rec["workingDealId"] = resolved_id
                rec["workingDealId_source"] = resolve_reason
                rec["workingDealId_resolved_utc"] = utc()
                working_id = resolved_id
            else:
                if str(resolve_reason) == "NO_MATCHING_WORKING_ORDER":
                    rec["status"] = "CANCELLED_PENDING_LIMIT"
                    rec["cancel_reason"] = "GHOST_PENDING_NO_BROKER_WORKING_ORDER"
                    rec["cancel_requested_utc"] = utc()
                    rec["ghost_pending_detected_utc"] = utc()
                    cancel_results.append({
                        "level": level_key,
                        "ok": True,
                        "reason": "GHOST_PENDING_NO_BROKER_WORKING_ORDER",
                        "resolve_reason": resolve_reason,
                    })
                    continue

                cancel_results.append({
                    "level": level_key,
                    "ok": False,
                    "reason": "NO_WORKING_ID_TO_CANCEL",
                    "resolve_reason": resolve_reason,
                })
                continue

        try:
            ok_cancel, cancel_info = cancel_working_order_secure(
                headers=headers,
                asset=asset,
                working_id=working_id,
                reason=reason,
                old_exec=rec,
            )
        except Exception as e:
            ok_cancel, cancel_info = False, {"exception": str(e)}

        rec["cancel_requested_utc"] = utc()
        rec["cancel_reason"] = reason
        rec["status"] = "CANCELLED_PENDING_LIMIT" if ok_cancel else "CANCEL_FAILED_PENDING_LIMIT"

        cancel_results.append({
            "level": level_key,
            "ok": bool(ok_cancel),
            "workingDealId": working_id,
            "info": cancel_info,
        })

    return cancel_results




# ============================================================
# V24.1 — invalidation panier ouvert quand le signal est mort
# ============================================================

def v24_latest_signal_for_asset(asset):
    import json
    from pathlib import Path

    paths = []

    try:
        paths.append(Path(B.CFG.DATA_DIR) / "ticks" / "signals_latest.json")
    except Exception:
        pass

    paths.append(Path("data/ticks/signals_latest.json"))

    seen = set()

    for path in paths:
        try:
            path = Path(path)
            if str(path) in seen:
                continue
            seen.add(str(path))

            if not path.exists():
                continue

            data = json.loads(path.read_text())

            if isinstance(data, dict):
                signals = data.get("signals", [])
            elif isinstance(data, list):
                signals = data
            else:
                signals = []

            for sig in signals:
                if str(sig.get("asset", "")).upper() == str(asset).upper():
                    return sig

        except Exception:
            continue

    return {}


def v24_sig_float(sig, keys, default=None):
    for k in keys:
        try:
            if sig.get(k) is not None:
                return float(sig.get(k))
        except Exception:
            pass
    return default


def v24_sig_text(sig, keys, default=""):
    for k in keys:
        try:
            if sig.get(k) is not None:
                return str(sig.get(k))
        except Exception:
            pass
    return str(default)


def v24_open_signal_lost_grace_sec():
    # Temps minimum avant de fermer un panier ouvert simplement parce que
    # le signal est repassé WAIT / NO_SIGNAL.
    return max(30.0, v241_env_float("V24_OPEN_SIGNAL_LOST_GRACE_SEC", 120.0))


def v24_signal_lost_min_loss_eur():
    # Si signal perdu et perte au moins égale à ce seuil, on coupe.
    return max(0.0, v241_env_float("V24_SIGNAL_LOST_MIN_LOSS_EUR", 0.20))


def v24_opposite_signal_min_loss_eur():
    # Signal franchement opposé : on coupe plus vite.
    return max(0.0, v241_env_float("V24_OPPOSITE_SIGNAL_MIN_LOSS_EUR", 0.10))


def v24_breakout_min_loss_eur():
    # Phase/VWAP opposés ou breakout contre panier.
    return max(0.0, v241_env_float("V24_BREAKOUT_MIN_LOSS_EUR", 0.20))


def v24_signal_max_age_for_invalidation_sec():
    # On n'invalide pas une position sur un signal trop vieux.
    return max(5.0, v241_env_float("V24_INVALIDATION_MAX_SIGNAL_AGE_SEC", 20.0))


def v24_open_basket_invalidation_reason(asset, direction, active_exec, cycle, pnl_total, open_count):
    """
    Décide si un panier déjà ouvert doit être fermé parce que le signal initial
    est mort ou inversé.

    Cas couverts :
    - signal opposé
    - phase opposée + VWAP opposé
    - breakout contre la position
    - signal disparu trop longtemps avec perte
    """
    if open_count <= 0:
        return None

    direction = str(direction).upper()
    sig = v24_latest_signal_for_asset(asset)

    if not sig:
        return None

    decision = v24_sig_text(sig, ["decision", "signal"], "WAIT").upper()
    phase = v24_sig_text(sig, ["phase", "market_phase"], "").upper()
    vwap = v24_sig_text(sig, ["vwap_bias", "vwap", "vwap_direction"], "").upper()
    reason = v24_sig_text(sig, ["reason", "context", "summary"], "")
    signal_age = v24_sig_float(sig, ["age_sec", "tick_age_sec"], None)

    if signal_age is not None and signal_age > v24_signal_max_age_for_invalidation_sec():
        return None

    basket_age = v24_age_sec_from_iso(active_exec.get("created_utc"))

    range_pos = v24_sig_float(
        sig,
        ["range_position", "range_pos", "rpos", "R.Pos", "r_pos"],
        None,
    )

    opposite_decision = (
        (direction == "BUY" and decision == "SELL")
        or
        (direction == "SELL" and decision == "BUY")
    )

    phase_against = (
        (direction == "BUY" and phase == "TREND_DOWN")
        or
        (direction == "SELL" and phase == "TREND_UP")
    )

    vwap_against = (
        (direction == "BUY" and vwap == "SELL")
        or
        (direction == "SELL" and vwap == "BUY")
    )

    breakout_against = False

    if range_pos is not None:
        # SELL en haut puis breakout haussier : danger.
        if direction == "SELL" and range_pos >= 95 and phase == "TREND_UP":
            breakout_against = True

        # BUY en bas puis breakout baissier : danger.
        if direction == "BUY" and range_pos <= 5 and phase == "TREND_DOWN":
            breakout_against = True

    signal_lost = decision in ("WAIT", "IDLE", "NO_SIGNAL", "NONE", "")

    if opposite_decision and pnl_total <= -v24_opposite_signal_min_loss_eur():
        return (
            "V24_OPEN_BASKET_OPPOSITE_SIGNAL_CLOSE"
            f"|decision={decision}|phase={phase}|vwap={vwap}|pnl={pnl_total:.4f}"
        )

    if phase_against and vwap_against and pnl_total <= -v24_breakout_min_loss_eur():
        return (
            "V24_OPEN_BASKET_PHASE_VWAP_AGAINST_CLOSE"
            f"|decision={decision}|phase={phase}|vwap={vwap}|pnl={pnl_total:.4f}"
        )

    if breakout_against and pnl_total <= -v24_breakout_min_loss_eur():
        return (
            "V24_OPEN_BASKET_BREAKOUT_AGAINST_CLOSE"
            f"|range_pos={range_pos}|phase={phase}|pnl={pnl_total:.4f}"
        )

    if signal_lost and basket_age >= v24_open_signal_lost_grace_sec() and pnl_total <= -v24_signal_lost_min_loss_eur():
        return (
            "V24_OPEN_BASKET_SIGNAL_LOST_CLOSE"
            f"|decision={decision}|age={basket_age:.1f}s|phase={phase}|vwap={vwap}|reason={reason}|pnl={pnl_total:.4f}"
        )

    return None



# =============================================================================
# V24_SCALP_ACTIVE_GLOBAL_HELPERS_V3
# =============================================================================

def v24sa_env_bool(name, default=False):
    try:
        import os
        val = str(os.getenv(name, str(default))).strip().lower()
        return val in ("1", "true", "yes", "y", "on")
    except Exception:
        return bool(default)


def v24sa_env_float(name, default):
    try:
        import os
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def v24sa_env_csv_set(name, default_csv):
    try:
        import os
        raw = os.getenv(name, default_csv)
        return {x.strip().upper() for x in str(raw).split(",") if x.strip()}
    except Exception:
        return {x.strip().upper() for x in str(default_csv).split(",") if x.strip()}


def v24sa_decimals(asset):
    asset = str(asset or "").upper()
    table = {
        "US500": 1, "US100": 1, "US30": 1, "DE40": 1, "FR40": 1, "FRA40": 1,
        "UK100": 1, "J225": 0,
        "EURUSD": 5, "GBPUSD": 5, "USDJPY": 3, "EURJPY": 3,
        "GOLD": 2, "SILVER": 3, "OIL_CRUDE": 2, "OIL_BRENT": 2,
        "BTCUSD": 1, "ETHUSD": 2,
    }
    return table.get(asset, 5)


def v24sa_tick(asset):
    return 10 ** (-int(v24sa_decimals(asset)))


def v24sa_round(asset, level):
    return round(float(level), int(v24sa_decimals(asset)))


def v24sa_latest_bid_ask(asset):
    import json
    from pathlib import Path
    asset = str(asset or "").upper()
    path = Path("data/ticks/signals_latest.json")
    if not path.exists():
        return None, None, None, "NO_SIGNALS_FILE"
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None, None, None, "SIGNALS_PARSE_ERROR"

    rows = []
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        if isinstance(data.get("signals"), list):
            rows = data.get("signals")
        elif isinstance(data.get("assets"), dict):
            for k, v in data.get("assets", {}).items():
                if isinstance(v, dict):
                    r = dict(v)
                    r.setdefault("asset", k)
                    rows.append(r)
        else:
            rows = [data]

    for row in rows:
        if not isinstance(row, dict):
            continue
        a = str(row.get("asset") or row.get("epic") or row.get("symbol") or "").upper()
        if a != asset:
            continue

        def get_float(*keys):
            for key in keys:
                val = row.get(key)
                if val is None:
                    continue
                try:
                    return float(val)
                except Exception:
                    pass
            return None

        bid = get_float("bid", "signal_bid", "last_bid")
        ask = get_float("ask", "signal_ask", "last_ask")
        mid = get_float("mid", "signal_mid", "price", "last")
        spread = get_float("spread", "signal_spread")

        if bid is None and ask is None and mid is not None and spread is not None:
            bid = mid - spread / 2.0
            ask = mid + spread / 2.0
        elif bid is None and ask is not None and spread is not None:
            bid = ask - spread
        elif ask is None and bid is not None and spread is not None:
            ask = bid + spread

        if bid is not None and ask is not None:
            return float(bid), float(ask), abs(float(ask) - float(bid)), "signals_latest"

    return None, None, None, "ASSET_NOT_FOUND_IN_SIGNALS"


def v24sa_limit_gap(asset, spread):
    asset = str(asset or "").upper()
    spread = abs(float(spread or 0.0))
    mult = v24sa_env_float("V24_LIMIT_GUARD_SPREAD_MULT", 1.5)
    min_gap = {
        "US500": 0.8, "US100": 2.0, "US30": 3.0, "DE40": 2.0,
        "FR40": 1.0, "FRA40": 1.0, "UK100": 1.0, "J225": 10.0,
        "EURUSD": 0.00005, "GBPUSD": 0.00005, "USDJPY": 0.010, "EURJPY": 0.010,
        "GOLD": 0.50, "SILVER": 0.05, "OIL_CRUDE": 0.05, "OIL_BRENT": 0.05,
        "BTCUSD": 5.0, "ETHUSD": 1.0,
    }.get(asset, v24sa_tick(asset))
    return max(v24sa_tick(asset), spread * mult, min_gap)


def v24sa_guard_limit_side(payload):
    # V24.2: do not move a LIMIT automatically after validation.
    # Marketable or collapsed levels must be rejected before broker send.
    if not isinstance(payload, dict):
        return payload
    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    direction = str(payload.get("direction") or "").upper()
    try:
        level = float(payload.get("level")) if "level" in payload else None
    except Exception:
        level = payload.get("level")
    try:
        print(f"{asset:10s} | V24_LIMIT_SIDE_GUARD_V242_NO_MOVE | {direction:4s} | level={level}")
    except Exception:
        pass
    return payload


def v24sa_guard_stop(payload):
    """
    V24 SCALP ACTIVE — STOP GUARD COMPLET

    Règles :
    - GOLD : guaranteedStop forcé à true, car Capital.com peut l'exiger.
    - Actifs problématiques : guaranteedStop false pour éviter min/max guaranteed stop.
    - Le stopDistance reste conservé : le stop broker reste l'airbag.
    """
    if not isinstance(payload, dict):
        return payload

    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    if not asset:
        return payload

    force_gs = v24sa_env_csv_set(
        "V24_FORCE_GUARANTEED_STOP_ASSETS",
        "GOLD"
    )

    disable_gs = v24sa_env_csv_set(
        "V24_DISABLE_GUARANTEED_STOP_ASSETS",
        "EURUSD,GBPUSD,EURJPY,USDJPY,OIL_CRUDE,OIL_BRENT,BTCUSD,ETHUSD,J225,SILVER"
    )

    clean = dict(payload)

    if asset in force_gs:
        clean["guaranteedStop"] = True
        try:
            print(
                f"{asset:10s} | V24_STOP_GUARD_FORCE | "
                f"guaranteedStop=true | stopDistance={clean.get('stopDistance')}"
            )
        except Exception:
            pass
        return clean

    if asset in disable_gs and clean.get("guaranteedStop") is True:
        clean["guaranteedStop"] = False
        try:
            print(
                f"{asset:10s} | V24_STOP_GUARD | "
                f"guaranteedStop=false | stopDistance={clean.get('stopDistance')}"
            )
        except Exception:
            pass
        return clean

    return clean


def v24sa_guard_working_payload(payload):
    payload = v24sa_guard_limit_side(payload)
    payload = v24sa_guard_stop(payload)
    return payload


def v2436_max_stop_distance(asset):
    asset = str(asset or "").upper()
    defaults = {
        "EURUSD": 0.0120,
        "GBPUSD": 0.0120,
    }
    default = defaults.get(asset, 0.0)
    return v2436_env_float(f"V2436_MAX_STOP_DISTANCE_{asset}", default)


def v2436_payload_stop_too_wide(payload):
    if not isinstance(payload, dict):
        return False, None

    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    cap = v2436_max_stop_distance(asset)
    if cap <= 0:
        return False, None

    try:
        stop_distance = float(payload.get("stopDistance") or 0.0)
    except Exception:
        return False, None

    if stop_distance > cap:
        return True, {
            "asset": asset,
            "direction": str(payload.get("direction") or "").upper(),
            "level": payload.get("level"),
            "stopDistance": stop_distance,
            "maxStopDistance": cap,
            "reason": "STOP_DISTANCE_TOO_WIDE",
        }

    return False, None


def v2436_print_stop_too_wide_block(info, context):
    try:
        print(
            f"{str(info.get('asset') or ''):10s} | V2436_STOP_TOO_WIDE_BLOCK | "
            f"{str(info.get('direction') or ''):4s} | context={context} "
            f"level={info.get('level')} stopDistance={info.get('stopDistance')} "
            f"max={info.get('maxStopDistance')} aucun ordre envoye"
        )
    except Exception:
        pass


def v24sa_required_stop_extra(asset):
    """
    Marge ajoutée au niveau stop exigé par Capital.com.
    Objectif : ne pas retenter pile à la limite broker.
    """
    asset = str(asset or "").upper()
    return {
        "US500": 2.0,
        "US100": 5.0,
        "US30": 12.0,
        "DE40": 5.0,
        "FR40": 3.0,
        "FRA40": 3.0,
        "UK100": 3.0,
        "J225": 30.0,

        "EURUSD": 0.00015,
        "GBPUSD": 0.00015,
        "USDJPY": 0.050,
        "EURJPY": 0.050,

        "GOLD": 8.0,
        "SILVER": 0.20,
        "OIL_CRUDE": 0.30,
        "OIL_BRENT": 0.30,

        "BTCUSD": 100.0,
        "ETHUSD": 6.0,
    }.get(asset, max(v24sa_tick(asset) * 10, 0.0001))


def v24sa_parse_required_stop_level(err):
    """
    Extrait le niveau imposé par Capital.com depuis :
    error.invalid.stoploss.minvalue: 4751.17
    error.invalid.stoploss.maxvalue: 4647.79
    """
    import re
    txt = str(err or "")
    m = re.search(r"invalid\.stoploss\.(minvalue|maxvalue)\s*:\s*([0-9]+(?:\.[0-9]+)?)", txt)
    if not m:
        return None, None
    return m.group(1), float(m.group(2))


def v24sa_adjust_stopdistance_from_broker_error(payload, err):
    """
    Si Capital.com donne un minvalue/maxvalue, on élargit stopDistance.
    BUY  : stop sous le prix.
    SELL : stop au-dessus du prix.
    """
    if not isinstance(payload, dict):
        return payload, False

    kind, required_level = v24sa_parse_required_stop_level(err)
    if kind is None or required_level is None:
        return payload, False

    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    direction = str(payload.get("direction") or "").upper()

    try:
        level = float(payload.get("level"))
    except Exception:
        return payload, False

    try:
        old_distance = float(payload.get("stopDistance") or 0.0)
    except Exception:
        old_distance = 0.0

    extra = v24sa_required_stop_extra(asset)
    new_distance = abs(required_level - level) + extra
    new_distance = max(new_distance, old_distance)

    decimals = max(2, v24sa_decimals(asset))
    new_distance = round(float(new_distance), decimals)

    clean = dict(payload)
    clean["stopDistance"] = new_distance

    try:
        print(
            f"{asset:10s} | V24_DYNAMIC_STOP_DISTANCE | {direction:4s} | "
            f"old={old_distance} new={new_distance} required_level={required_level} "
            f"kind={kind} extra={extra}"
        )
    except Exception:
        pass

    return clean, True



def v24sa_error_text(data):
    try:
        if isinstance(data, dict):
            return str(data.get("errorCode") or data.get("message") or data)
        return str(data)
    except Exception:
        return ""


def v24sa_retry_working_order(headers, payload, status, data):
    try:
        code = int(status)
    except Exception:
        return status, data, payload
    if code not in (400, 403):
        return status, data, payload
    err = v24sa_error_text(data)
    if not err or not v24sa_env_bool("V24_LIMIT_STOP_RETRY", True):
        return status, data, payload
    retry_payload = None
    reason = None
    if "error.validation.limit.price" in err:
        retry_payload = v24sa_guard_working_payload(dict(payload))
        reason = "LIMIT_PRICE_SIDE_GUARD"

    elif (
        "guaranteed-stop-loss.required" in err
        or "guaranteed.stop.loss.required" in err
        or "guaranteed-stop-loss" in err
    ):
        retry_payload = dict(payload)
        retry_payload["guaranteedStop"] = True
        reason = "STOPLOSS_GUARANTEED_REQUIRED_TRUE"

    elif "error.invalid.stoploss" in err or "invalid.stoploss" in err:
        retry_payload = dict(payload)
        asset_retry = str(retry_payload.get("epic") or "").upper()
        force_retry = v24sa_env_csv_set("V24_FORCE_GUARANTEED_STOP_ASSETS", "GOLD")

        if asset_retry in force_retry:
            retry_payload["guaranteedStop"] = True
            reason = "STOPLOSS_RETRY_FORCE_GUARANTEED_TRUE"
        else:
            retry_payload["guaranteedStop"] = False
            reason = "STOPLOSS_RETRY_GUARANTEED_FALSE"

    if retry_payload is None:
        return status, data, payload
    stop_too_wide, stop_info = v2436_payload_stop_too_wide(retry_payload)
    if stop_too_wide:
        v2436_print_stop_too_wide_block(stop_info, "WORKING_ORDER_RETRY")
        v24_event_safe({
            "event": "V2436_STOP_TOO_WIDE_RETRY_BLOCKED",
            "payload": retry_payload,
            "stop_guard": stop_info,
            "old_status": status,
            "old_response": data,
        })
        return status, data, payload
    try:
        asset = str(retry_payload.get("epic") or "")
        direction = str(retry_payload.get("direction") or "")
        print(f"{asset:10s} | V24_WORKING_ORDER_RETRY | {direction:4s} | reason={reason} old_error={err}")
    except Exception:
        pass
    try:
        retry_status, retry_data = B.api_post(headers, "/api/v1/workingorders", retry_payload)
    except Exception as exc:
        try:
            print(f"V24_WORKING_ORDER_RETRY_EXCEPTION | {exc}")
        except Exception:
            pass
        return status, data, payload
    retry_err = v24sa_error_text(retry_data)

    # V24 SCALP ACTIVE — deuxième tentative si le broker donne enfin
    # le niveau stop min/max exact à respecter.
    if int(retry_status) in (400, 403) and "invalid.stoploss" in retry_err:
        second_payload, second_adjusted = v24sa_adjust_stopdistance_from_broker_error(dict(retry_payload), retry_err)
        if second_adjusted:
            stop_too_wide, stop_info = v2436_payload_stop_too_wide(second_payload)
            if stop_too_wide:
                v2436_print_stop_too_wide_block(stop_info, "WORKING_ORDER_SECOND_RETRY")
                v24_event_safe({
                    "event": "V2436_STOP_TOO_WIDE_SECOND_RETRY_BLOCKED",
                    "payload": second_payload,
                    "stop_guard": stop_info,
                    "old_status": retry_status,
                    "old_response": retry_data,
                })
                return retry_status, retry_data, retry_payload
            try:
                asset2 = str(second_payload.get("epic") or "")
                direction2 = str(second_payload.get("direction") or "")
                print(
                    f"{asset2:10s} | V24_WORKING_ORDER_SECOND_RETRY | {direction2:4s} | "
                    f"reason=DYNAMIC_STOP_DISTANCE old_error={retry_err}"
                )
                second_status, second_data = B.api_post(headers, "/api/v1/workingorders", second_payload)
                print(
                    f"{asset2:10s} | V24_WORKING_ORDER_SECOND_RETRY_RESULT | {direction2:4s} | "
                    f"HTTP={second_status} data={second_data}"
                )
                return second_status, second_data, second_payload
            except Exception as exc:
                try:
                    print(f"V24_WORKING_ORDER_SECOND_RETRY_EXCEPTION | {exc}")
                except Exception:
                    pass

    if int(retry_status) in (400, 403) and "error.invalid.stoploss" in retry_err and v24sa_env_bool("V24_ALLOW_NO_STOP_LAST_RETRY", False):
        last_payload = dict(retry_payload)
        for key in ("stopDistance", "stopLevel", "stopAmount", "guaranteedStop"):
            last_payload.pop(key, None)
        try:
            asset = str(last_payload.get("epic") or "")
            direction = str(last_payload.get("direction") or "")
            print(f"{asset:10s} | V24_STOP_GUARD_LAST_RETRY_NO_STOP | {direction:4s} | old_error={retry_err}")
            last_status, last_data = B.api_post(headers, "/api/v1/workingorders", last_payload)
            return last_status, last_data, last_payload
        except Exception:
            return retry_status, retry_data, retry_payload
    try:
        asset = str(retry_payload.get("epic") or "")
        direction = str(retry_payload.get("direction") or "")
        print(f"{asset:10s} | V24_WORKING_ORDER_RETRY_RESULT | {direction:4s} | HTTP={retry_status} data={retry_data}")
    except Exception:
        pass
    return retry_status, retry_data, retry_payload

# =============================================================================
# FIN V24_SCALP_ACTIVE_GLOBAL_HELPERS_V3
# =============================================================================


def v24_process_basket(headers, asset, cycle, active_exec, broker_items, broker_ids, positions, market_status, exec_state, margin_snapshot=None, storm_snapshot=None):
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
                f"deal={short_id(deal_id)} limit={matched_rec.get('limit_price')} entry={broker_entry_price}"
            )

            event({
                "event": "V24_BASKET_LEVEL_FILLED",
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "level": int(matched_key),
                "direction": direction,
                "brokerDealId": deal_id,
                "brokerEntryPrice": broker_entry_price,
                "requested_limit_price": matched_rec.get("limit_price"),
                "price_audit": matched_rec.get("price_audit"),
            })

    # 3. Calcul PnL global.
    pnl_total, open_count, target = v24_basket_current_pnl(asset, active_exec, broker_items=broker_items)

    active_exec["last_basket_pnl_eur"] = float(pnl_total)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_target_tp_eur"] = target

    pnl_audit = active_exec.get("last_pnl_audit") or {}
    broker_upl_total_for_tp = pnl_audit.get("total_broker_upl_eur")
    broker_upl_count_for_tp = int(pnl_audit.get("broker_upl_count") or 0)

    tp_broker_ready = (
        open_count > 0
        and target is not None
        and broker_upl_total_for_tp is not None
        and broker_upl_count_for_tp >= int(open_count)
    )

    tp_decision_pnl = float(broker_upl_total_for_tp) if tp_broker_ready else None

    active_exec["last_tp_decision_source"] = (
        "BROKER_POSITION_UPL" if tp_broker_ready else "NO_BROKER_UPL_BLOCK_TP"
    )
    active_exec["last_tp_decision_pnl_eur"] = tp_decision_pnl
    active_exec["last_internal_pnl_eur"] = float(pnl_total)
    active_exec["last_broker_upl_total_eur"] = broker_upl_total_for_tp
    active_exec["last_broker_upl_count"] = broker_upl_count_for_tp
    active_exec["last_check_utc"] = utc()

    # V24.3.1 - TP LADDER AUDIT LOG ONLY
    # Prouve explicitement open=1/2/3 => target=0.20/0.40/0.60.
    # Aucun changement de decision, aucun appel API supplementaire.
    if open_count > 0 and v24_bool_env("V243_TP_LADDER_CHECK_LOG", True):
        try:
            ladder_margin = float(v24_tp_safety_margin_eur())
        except Exception:
            ladder_margin = 0.0

        try:
            ladder_threshold = float(target) + float(ladder_margin) if target is not None else None
        except Exception:
            ladder_threshold = None

        if target is None:
            ladder_decision = "NO_TARGET"
        elif not tp_broker_ready:
            ladder_decision = "HOLD_NO_BROKER_UPL"
        elif tp_decision_pnl is not None and ladder_threshold is not None and float(tp_decision_pnl) >= float(ladder_threshold):
            ladder_decision = "TP_READY"
        else:
            ladder_decision = "HOLD_BELOW_TARGET"

        target_s = "None" if target is None else f"{float(target):.4f}"
        threshold_s = "None" if ladder_threshold is None else f"{float(ladder_threshold):.4f}"
        broker_upl_s = "none" if broker_upl_total_for_tp is None else f"{float(broker_upl_total_for_tp):.4f}"
        tp_pnl_s = "none" if tp_decision_pnl is None else f"{float(tp_decision_pnl):.4f}"
        source_s = "BROKER_POSITION_UPL" if tp_broker_ready else "NO_BROKER_UPL_BLOCK_TP"

        print(
            f"{asset:10s} | BASKET_TP_LADDER_CHECK | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | "
            f"open={int(open_count)} expected_target={target_s} threshold={threshold_s} "
            f"broker_upl={broker_upl_s} tp_pnl={tp_pnl_s} "
            f"broker_count={int(broker_upl_count_for_tp)}/{int(open_count)} "
            f"internal={float(pnl_total):.4f} margin={float(ladder_margin):.4f} "
            f"decision={ladder_decision} source={source_s}"
        )

    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)

    pending_count = len([
        rec for rec in levels.values()
        if str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])

    # V24.3.5J - TP broker close proof.
    # Broker UPL is the only TP truth. Internal PnL stays audit-only.
    if (
        open_count > 0
        and v24_bool_env("V2435J_TP_MATRIX_CLOSE_PROOF", True)
        and tp_broker_ready
        and target is not None
        and tp_decision_pnl is not None
    ):
        try:
            tp_margin = float(v24_tp_safety_margin_eur())
        except Exception:
            tp_margin = 0.0

        try:
            tp_threshold = float(target) + float(tp_margin)
        except Exception:
            tp_threshold = None

        if tp_threshold is not None and float(tp_decision_pnl) >= float(tp_threshold):
            tp_reason = "V2435J_TP_BROKER_CLOSE_PROOF"
            trigger_utc = utc()

            active_exec["tp_matrix_trigger_utc"] = trigger_utc
            active_exec["tp_matrix_broker_upl_eur"] = float(tp_decision_pnl)
            active_exec["tp_matrix_target_eur"] = float(target)
            active_exec["tp_matrix_threshold_eur"] = float(tp_threshold)
            active_exec["tp_matrix_open_count"] = int(open_count)
            active_exec["tp_matrix_pending_count"] = int(pending_count)

            print(
                f"{asset:10s} | TP_MATRIX_TRIGGER | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"open={int(open_count)} broker_upl={float(tp_decision_pnl):.4f} "
                f"target={float(target):.4f} threshold={float(tp_threshold):.4f} "
                f"broker_count={int(broker_upl_count_for_tp)}/{int(open_count)} "
                f"internal={float(pnl_total):.4f} source=BROKER_POSITION_UPL"
            )

            event({
                "event": "TP_MATRIX_TRIGGER",
                "asset": asset,
                "cycle_id": active_exec.get("cycle_id"),
                "direction": direction,
                "open_count": int(open_count),
                "pending_count": int(pending_count),
                "broker_upl": float(tp_decision_pnl),
                "target": float(target),
                "threshold": float(tp_threshold),
                "internal_pnl": float(pnl_total),
                "source": "BROKER_POSITION_UPL",
            })

            cancel_results = []
            broker_cleanup_results = []

            if pending_count > 0:
                try:
                    cancel_results = v24_cancel_all_pending_limits(
                        headers=headers,
                        asset=asset,
                        levels=levels,
                        reason=tp_reason + "_CANCEL_PENDING",
                    )
                except Exception as e:
                    cancel_results = [{"ok": False, "exception": str(e)}]

                try:
                    broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                        headers=headers,
                        asset=asset,
                        direction=direction,
                        reason=tp_reason + "_BROKER_PENDING_SWEEP",
                    )
                except Exception as e:
                    broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["tp_matrix_cancel_results"] = cancel_results
            active_exec["tp_matrix_broker_cleanup_results"] = broker_cleanup_results

            print(
                f"{asset:10s} | TP_MATRIX_CLOSE_REQUEST | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"open={int(open_count)} pending={int(pending_count)} "
                f"broker_upl={float(tp_decision_pnl):.4f} target={float(target):.4f} "
                f"reason={tp_reason}"
            )

            event({
                "event": "TP_MATRIX_CLOSE_REQUEST",
                "asset": asset,
                "cycle_id": active_exec.get("cycle_id"),
                "direction": direction,
                "open_count": int(open_count),
                "pending_count": int(pending_count),
                "broker_upl": float(tp_decision_pnl),
                "target": float(target),
                "threshold": float(tp_threshold),
                "cancel_results": v24_json_safe(cancel_results),
                "broker_cleanup_results": v24_json_safe(broker_cleanup_results),
                "reason": tp_reason,
            })

            try:
                ok_close, close_info, positions_after = v24_close_basket_secure(
                    headers=headers,
                    asset=asset,
                    basket_exec=active_exec,
                    reason=tp_reason,
                )
            except Exception as e:
                ok_close, close_info, positions_after = False, {"exception": str(e)}, None

            safe_close_info = v24_json_safe(close_info)

            proof_status = "from_close"
            proof_positions = positions_after
            if proof_positions is None:
                try:
                    proof_status, proof_positions, _ = fetch_positions(headers)
                except Exception as e:
                    proof_status = f"fetch_error:{e}"
                    proof_positions = None

            try:
                broker_after_count = len(positions_for_asset(asset, proof_positions or []))
            except Exception:
                broker_after_count = -1

            close_verified = bool(ok_close) and int(broker_after_count) == 0

            active_exec["tp_matrix_close_verified"] = bool(close_verified)
            active_exec["tp_matrix_close_ok_raw"] = bool(ok_close)
            active_exec["tp_matrix_broker_after_count"] = int(broker_after_count)
            active_exec["tp_matrix_close_info"] = safe_close_info
            active_exec["tp_matrix_close_utc"] = utc()

            if close_verified:
                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": tp_reason,
                    "closed_utc": utc(),
                    "close_info": safe_close_info,
                })
                exec_state.setdefault("active", {}).pop(asset, None)

                reset_cycle_idle(asset, tp_reason)
                B.save_json(B.EXEC_STATE_FILE, exec_state)

                print(
                    f"{asset:10s} | TP_MATRIX_CLOSE_OK | 1-3 | {direction:4s} | "
                    f"--         | {market_status:9s} | "
                    f"broker_upl={float(tp_decision_pnl):.4f} target={float(target):.4f} "
                    f"threshold={float(tp_threshold):.4f} broker_after={int(broker_after_count)} "
                    f"verified=True status={proof_status}"
                )

                print(
                    f"{asset:10s} | BASKET_TP_OK | 1-3 | {direction:4s} | "
                    f"--         | {market_status:9s} | "
                    f"pnl={float(tp_decision_pnl):.4f} target={float(target):.4f} "
                    f"internal={float(pnl_total):.4f} source=BROKER_POSITION_UPL "
                    f"close=TP_MATRIX_CLOSE_OK"
                )

                event({
                    "event": "TP_MATRIX_CLOSE_OK",
                    "asset": asset,
                    "cycle_id": active_exec.get("cycle_id"),
                    "direction": direction,
                    "broker_upl": float(tp_decision_pnl),
                    "target": float(target),
                    "threshold": float(tp_threshold),
                    "open_count": int(open_count),
                    "pending_count": int(pending_count),
                    "broker_after": int(broker_after_count),
                    "close_info": safe_close_info,
                    "reason": tp_reason,
                })

                return True, proof_positions

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | TP_MATRIX_CLOSE_FAIL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"broker_upl={float(tp_decision_pnl):.4f} target={float(target):.4f} "
                f"threshold={float(tp_threshold):.4f} ok_close={bool(ok_close)} "
                f"broker_after={int(broker_after_count)} status={proof_status}"
            )

            event({
                "event": "TP_MATRIX_CLOSE_FAIL",
                "asset": asset,
                "cycle_id": active_exec.get("cycle_id"),
                "direction": direction,
                "broker_upl": float(tp_decision_pnl),
                "target": float(target),
                "threshold": float(tp_threshold),
                "open_count": int(open_count),
                "pending_count": int(pending_count),
                "ok_close": bool(ok_close),
                "broker_after": int(broker_after_count),
                "close_info": safe_close_info,
                "reason": tp_reason,
            })

            return True, proof_positions if proof_positions is not None else positions


    # V24.3 -- anti-zombie local : jambes OPEN localement mais disparues côté broker.
    if open_count > 0 and not broker_items:
        fresh_status, fresh_positions, fresh_raw = fetch_positions(headers)
        fresh_broker_items = positions_for_asset(asset, fresh_positions)

        if fresh_status in (200, 201, 202) and not fresh_broker_items:
            reason = "V243_BROKER_EMPTY_LOCAL_ZOMBIE_RESET"

            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason=reason + "_PENDING_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["broker_empty_reset_reason"] = reason
            active_exec["broker_empty_reset_utc"] = utc()
            active_exec["broker_empty_reset_open_count"] = int(open_count)
            active_exec["broker_empty_reset_pending_count"] = int(pending_count)
            active_exec["broker_empty_reset_fetch_status"] = fresh_status
            active_exec["broker_empty_reset_cleanup_results"] = broker_cleanup_results
            active_exec["broker_empty_reset_last_broker_upl_total_eur"] = broker_upl_total_for_tp
            active_exec["broker_empty_reset_last_target_tp_eur"] = target
            active_exec["broker_empty_reset_last_internal_pnl_eur"] = float(pnl_total)
            active_exec["broker_empty_reset_last_broker_upl_count"] = int(broker_upl_count_for_tp)

            exec_state.setdefault("orphaned_resets", []).append({
                **active_exec,
                "orphaned_reason": reason,
                "orphaned_utc": utc(),
            })
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            broker_empty_upl_s = "none" if broker_upl_total_for_tp is None else f"{float(broker_upl_total_for_tp):.4f}"
            broker_empty_target_s = "none" if target is None else f"{float(target):.4f}"

            print(
                f"{asset:10s} | BROKER_EMPTY_RESET | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"local_open={open_count} broker_open=0 pending={pending_count} "
                f"last_broker_upl={broker_empty_upl_s} target={broker_empty_target_s} "
                f"broker_count={broker_upl_count_for_tp}/{open_count} internal={float(pnl_total):.4f} "
                f"reason={reason}"
            )

            event({
                "event": "BROKER_EMPTY_RESET",
                "asset": asset,
                "cycle_id": active_exec.get("cycle_id"),
                "direction": direction,
                "local_open_count": int(open_count),
                "pending_count": int(pending_count),
                "fetch_status": fresh_status,
                "cleanup_results": broker_cleanup_results,
                "reason": reason,
            })

            return True, fresh_positions

        active_exec["broker_empty_reset_blocked_utc"] = utc()
        active_exec["broker_empty_reset_blocked_status"] = fresh_status
        active_exec["broker_empty_reset_blocked_broker_count"] = len(fresh_broker_items)
        exec_state.setdefault("active", {})[asset] = active_exec
        B.save_json(B.EXEC_STATE_FILE, exec_state)

    storm_blocked, storm_reasons = v243_storm_guard_blocks_asset(storm_snapshot, asset)

    if storm_blocked and pending_count > 0:
        reason = "V243_STORM_GUARD_CANCEL_PENDING"

        cancel_results = v24_cancel_all_pending_limits(
            headers=headers,
            asset=asset,
            levels=levels,
            reason=reason,
        )

        try:
            broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                headers=headers,
                asset=asset,
                direction=direction,
                reason=reason + "_BROKER_SWEEP",
            )
        except Exception as e:
            broker_cleanup_results = [{"ok": False, "exception": str(e)}]

        active_exec["storm_guard_reasons"] = storm_reasons
        active_exec["storm_guard_cancel_results"] = cancel_results
        active_exec["storm_guard_broker_cleanup_results"] = broker_cleanup_results
        active_exec["storm_guard_cancel_utc"] = utc()

        event({
            "event": "STORM_GUARD_CANCEL_PENDING",
            "asset": asset,
            "cycle_id": active_exec.get("cycle_id"),
            "direction": direction,
            "open_count": open_count,
            "pending_count": pending_count,
            "storm_reasons": storm_reasons,
            "cancel_results": cancel_results,
            "broker_cleanup_results": broker_cleanup_results,
        })

        print(
            f"{asset:10s} | STORM_GUARD_CANCEL_PENDING | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | "
            f"open={open_count} pending={pending_count} reasons={','.join(storm_reasons[:4])}"
        )

        if open_count <= 0:
            exec_state.setdefault("cancelled", []).append({
                **active_exec,
                "cancelled_reason": reason,
                "cancelled_utc": utc(),
            })
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)
            return True, positions

        exec_state.setdefault("active", {})[asset] = active_exec
        B.save_json(B.EXEC_STATE_FILE, exec_state)

    if storm_blocked and open_count > 0 and v243_storm_emergency_close_enabled():
        storm_loss_limit = v243_storm_max_loss_eur(open_count)

        if broker_upl_total_for_tp is None:
            print(
                f"{asset:10s} | STORM_GUARD_CLOSE_BLOCKED_NO_BROKER_UPL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | limit=-{storm_loss_limit:.4f} reasons={','.join(storm_reasons[:4])}"
            )
        elif float(broker_upl_total_for_tp) <= -float(storm_loss_limit):
            ok, close_info, positions_after = v24_close_basket_secure(
                headers=headers,
                asset=asset,
                basket_exec=active_exec,
                reason="V243_STORM_GUARD_EMERGENCY_CLOSE",
            )

            active_exec["storm_guard_emergency_close_utc"] = utc()
            active_exec["storm_guard_emergency_close_reasons"] = storm_reasons
            active_exec["storm_guard_emergency_close_broker_upl"] = float(broker_upl_total_for_tp)
            active_exec["storm_guard_emergency_close_loss_limit"] = float(storm_loss_limit)

            if ok:
                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": "V243_STORM_GUARD_EMERGENCY_CLOSE",
                    "closed_utc": utc(),
                    "close_info": close_info,
                })
                exec_state.setdefault("active", {}).pop(asset, None)

                reset_cycle_idle(asset, "V243_STORM_GUARD_EMERGENCY_CLOSE")
                B.save_json(B.EXEC_STATE_FILE, exec_state)

                print(
                    f"{asset:10s} | STORM_GUARD_EMERGENCY_CLOSE_OK | 1-3 | {direction:4s} | "
                    f"--         | {market_status:9s} | broker_upl={float(broker_upl_total_for_tp):.4f} "
                    f"limit=-{storm_loss_limit:.4f} reasons={','.join(storm_reasons[:4])}"
                )

                event({
                    "event": "STORM_GUARD_EMERGENCY_CLOSE_OK",
                    "asset": asset,
                    "cycle_id": active_exec.get("cycle_id"),
                    "direction": direction,
                    "broker_upl": float(broker_upl_total_for_tp),
                    "loss_limit": float(storm_loss_limit),
                    "storm_reasons": storm_reasons,
                    "close_info": close_info,
                })

                return True, positions_after

            print(
                f"{asset:10s} | STORM_GUARD_EMERGENCY_CLOSE_FAIL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | broker_upl={float(broker_upl_total_for_tp):.4f} "
                f"limit=-{storm_loss_limit:.4f}"
            )

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)
            return True, positions

    if open_count > 0 and v243_max_loss_guard_enabled():
        max_loss_eur = v243_basket_max_loss_eur(open_count)

        if broker_upl_total_for_tp is None:
            print(
                f"{asset:10s} | BASKET_MAX_LOSS_BLOCKED_NO_BROKER_UPL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | limit=-{max_loss_eur:.4f}"
            )
        elif float(broker_upl_total_for_tp) <= -float(max_loss_eur):
            try:
                max_loss_cancel_results = v24_cancel_all_pending_limits(
                    headers=headers,
                    asset=asset,
                    levels=levels,
                    reason="V243_BASKET_MAX_LOSS_CANCEL_PENDING",
                )
                active_exec["max_loss_cancel_results"] = max_loss_cancel_results
            except Exception as e:
                active_exec["max_loss_cancel_error"] = str(e)

            ok, close_info, positions_after = v24_close_basket_secure(
                headers=headers,
                asset=asset,
                basket_exec=active_exec,
                reason="V243_BASKET_MAX_LOSS_BROKER_UPL",
            )

            active_exec["max_loss_broker_upl"] = float(broker_upl_total_for_tp)
            active_exec["max_loss_limit_eur"] = float(max_loss_eur)
            active_exec["max_loss_open_count"] = int(open_count)
            active_exec["max_loss_utc"] = utc()

            if ok:
                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": "V243_BASKET_MAX_LOSS_BROKER_UPL",
                    "closed_utc": utc(),
                    "close_info": close_info,
                })
                exec_state.setdefault("active", {}).pop(asset, None)

                reset_cycle_idle(asset, "V243_BASKET_MAX_LOSS_BROKER_UPL")
                B.save_json(B.EXEC_STATE_FILE, exec_state)

                print(
                    f"{asset:10s} | BASKET_MAX_LOSS_CLOSE_OK | 1-3 | {direction:4s} | "
                    f"--         | {market_status:9s} | broker_upl={float(broker_upl_total_for_tp):.4f} "
                    f"limit=-{max_loss_eur:.4f} open={open_count}"
                )

                event({
                    "event": "BASKET_MAX_LOSS_CLOSE_OK",
                    "asset": asset,
                    "cycle_id": active_exec.get("cycle_id"),
                    "direction": direction,
                    "broker_upl": float(broker_upl_total_for_tp),
                    "loss_limit": float(max_loss_eur),
                    "open_count": int(open_count),
                    "close_info": close_info,
                })

                return True, positions_after

            print(
                f"{asset:10s} | BASKET_MAX_LOSS_CLOSE_FAIL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | broker_upl={float(broker_upl_total_for_tp):.4f} "
                f"limit=-{max_loss_eur:.4f}"
            )

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)
            return True, positions

    # 4. Invalidation panier ouvert si le signal initial est mort.
    invalidation_reason = v24_open_basket_invalidation_reason(
        asset=asset,
        direction=direction,
        active_exec=active_exec,
        cycle=cycle,
        pnl_total=float(pnl_total),
        open_count=int(open_count),
    )

    if invalidation_reason:
        # On annule d'abord les LIMIT encore en attente, puis on ferme les jambes ouvertes.
        try:
            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=invalidation_reason,
            )
            active_exec["invalidation_cancel_results"] = cancel_results
        except Exception as e:
            active_exec["invalidation_cancel_error"] = str(e)

        ok, close_info, positions_after = v24_close_basket_secure(
            headers=headers,
            asset=asset,
            basket_exec=active_exec,
            reason=invalidation_reason,
        )

        active_exec["invalidation_reason"] = invalidation_reason
        active_exec["invalidation_utc"] = utc()
        active_exec["invalidation_pnl_eur"] = float(pnl_total)
        active_exec["invalidation_open_count"] = int(open_count)

        if ok:
            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": invalidation_reason,
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

            reset_cycle_idle(asset, invalidation_reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_INVALIDATION_CLOSE_OK | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | pnl={pnl_total:.4f} reason={invalidation_reason}"
            )

            try:
                event({
                    "event": "V24_OPEN_BASKET_INVALIDATION_CLOSE_OK",
                    "asset": asset,
                    "cycle_id": active_exec.get("cycle_id"),
                    "direction": direction,
                    "pnl_total": float(pnl_total),
                    "open_count": int(open_count),
                    "reason": invalidation_reason,
                    "close_info": close_info,
                })
            except Exception:
                pass

            return True, positions_after

        print(
            f"{asset:10s} | BASKET_INVALIDATION_CLOSE_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} reason={invalidation_reason}"
        )

        exec_state.setdefault("active", {})[asset] = active_exec
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions

    # 5. TP panier global.
    tp_safety_margin = v24_tp_safety_margin_eur()

    if (
        open_count > 0
        and target is not None
        and tp_broker_ready
        and float(tp_decision_pnl) >= (target + tp_safety_margin)
    ):
        ok, close_info, positions_after = v24_close_basket_secure(
            headers=headers,
            asset=asset,
            basket_exec=active_exec,
            reason="V24_BASKET_GLOBAL_TP",
        )

        if ok:
            # TP atteint : on ferme les positions puis on nettoie aussi
            # les LIMIT restants du panier côté broker.
            try:
                tp_pending_cancel_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason="V24_BASKET_GLOBAL_TP_CANCEL_REMAINING_PENDING",
                )
                active_exec["tp_pending_cancel_results"] = tp_pending_cancel_results
            except Exception as e:
                active_exec["tp_pending_cancel_error"] = str(e)

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
                f"--         | {market_status:9s} | pnl={float(tp_decision_pnl):.4f} target={target:.4f} "
                f"internal={pnl_total:.4f} source=BROKER_POSITION_UPL"
            )

            return True, positions_after

        # Si le TP est atteint mais que la fermeture échoue,
        # on garde le panier actif, mais on annule les pending restants
        # pour éviter d'ajouter L2/L3 trop tard.
        try:
            tp_fail_cancel_results = v24_cancel_broker_pending_for_asset(
                headers=headers,
                asset=asset,
                direction=direction,
                reason="V24_BASKET_TP_FAIL_CANCEL_PENDING_TO_FREE_MARGIN",
            )
            active_exec["tp_fail_pending_cancel_results"] = tp_fail_cancel_results
        except Exception as e:
            active_exec["tp_fail_pending_cancel_error"] = str(e)

        active_exec["last_tp_fail_utc"] = utc()
        active_exec["last_tp_fail_pnl_eur"] = float(pnl_total)
        active_exec["last_tp_fail_target_eur"] = float(target)

        exec_state.setdefault("active", {})[asset] = active_exec

        print(
            f"{asset:10s} | BASKET_TP_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
        )
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions

    # 5. Blocage TP si le PnL interne dit TP mais que le broker ne confirme pas.
    if open_count > 0 and target is not None and pnl_total >= (target + tp_safety_margin):
        if not tp_broker_ready:
            print(
                f"{asset:10s} | BASKET_TP_BLOCKED_NO_BROKER_UPL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | internal={pnl_total:.4f} "
                f"broker_upl=None target={target:.4f}"
            )
        elif float(tp_decision_pnl) < (target + tp_safety_margin):
            print(
                f"{asset:10s} | BASKET_TP_BLOCKED_BROKER_UPL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | internal={pnl_total:.4f} "
                f"broker_upl={float(tp_decision_pnl):.4f} target={target:.4f}"
            )

    # 5. Maintien panier.
    pending_count = len([
        rec for rec in levels.values()
        if str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])

    active_exec["last_pending_count"] = int(pending_count)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_basket_age_sec"] = float(v24_age_sec_from_iso(active_exec.get("created_utc")))
    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)


    # V24.3 DEMO -- si marge >= 3100, on ne coupe qu'un mauvais panier pending-only.
    if pending_count > 0 and v243_margin_selector_active(margin_snapshot):
        selector_row = v243_margin_selector_worst_pending(exec_state, positions)
        selector_asset = selector_row.get("asset") if selector_row else None

        if v243_margin_selector_recent_cancel(exec_state):
            print(
                f"{asset:10s} | MARGIN_SELECTOR_KEEP_COOLDOWN | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | margin={margin_snapshot.get('margin_cfd_eur')} "
                f"threshold={v243_margin_selector_threshold_eur()}"
            )

        elif selector_asset != asset:
            print(
                f"{asset:10s} | MARGIN_SELECTOR_KEEP | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | margin={margin_snapshot.get('margin_cfd_eur')} "
                f"worst={selector_asset} threshold={v243_margin_selector_threshold_eur()}"
            )

        else:
            reason = "V243_MARGIN_SELECTOR_CANCEL_WORST_PENDING"

            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason=reason + "_BROKER_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["margin_selector_cancel_results"] = cancel_results
            active_exec["margin_selector_broker_cleanup_results"] = broker_cleanup_results
            active_exec["margin_selector_cancel_utc"] = utc()
            active_exec["margin_selector_reason"] = reason
            active_exec["margin_selector_score"] = selector_row.get("score")
            active_exec["margin_selector_ratio"] = selector_row.get("ratio")
            active_exec["margin_selector_age_sec"] = selector_row.get("age_sec")
            active_exec["margin_selector_snapshot"] = margin_snapshot

            exec_state["v243_margin_selector_last_cancel_utc"] = utc()
            exec_state["v243_margin_selector_last_cancel_asset"] = asset

            exec_state.setdefault("cancelled", []).append({
                **active_exec,
                "cancelled_reason": reason,
                "cancelled_utc": utc(),
            })
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)

            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | MARGIN_SELECTOR_CANCEL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | margin={margin_snapshot.get('margin_cfd_eur')} "
                f"threshold={v243_margin_selector_threshold_eur()} pending={pending_count} "
                f"score={float(selector_row.get('score') or 0.0):.1f} ratio={selector_row.get('ratio')}"
            )

            event({
                "event": "MARGIN_SELECTOR_CANCEL",
                "asset": asset,
                "cycle_id": active_exec.get("cycle_id"),
                "direction": direction,
                "pending_count": pending_count,
                "margin_snapshot": margin_snapshot,
                "selector_row": selector_row,
                "cancel_results": cancel_results,
                "broker_cleanup_results": broker_cleanup_results,
            })

            return True, positions


    # V24.2 -- pression marge globale : on garde les positions ouvertes,
    # mais on libere les ordres pending L2/L3/L1 qui consomment la marge.
    if pending_count > 0 and v242_margin_guard_pressure(margin_snapshot) and not v243_margin_selector_active(margin_snapshot):
        reason = "V24_MARGIN_GUARD_PRESSURE_CANCEL_PENDING"

        cancel_results = v24_cancel_all_pending_limits(
            headers=headers,
            asset=asset,
            levels=levels,
            reason=reason,
        )

        try:
            broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                headers=headers,
                asset=asset,
                direction=direction,
                reason=reason + "_BROKER_SWEEP",
            )
        except Exception as e:
            broker_cleanup_results = [{"ok": False, "exception": str(e)}]

        active_exec["margin_guard_snapshot"] = margin_snapshot
        active_exec["margin_guard_cancel_results"] = cancel_results
        active_exec["margin_guard_broker_cleanup_results"] = broker_cleanup_results
        active_exec["margin_guard_cancel_utc"] = utc()
        active_exec["margin_guard_cancel_reason"] = reason

        event({
            "event": "MARGIN_GUARD_CANCEL_PENDING",
            "asset": asset,
            "cycle_id": active_exec.get("cycle_id"),
            "direction": direction,
            "open_count": open_count,
            "pending_count": pending_count,
            "margin_snapshot": margin_snapshot,
            "cancel_results": cancel_results,
            "broker_cleanup_results": broker_cleanup_results,
        })

        print(
            f"{asset:10s} | MARGIN_GUARD_CANCEL_PENDING | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | "
            f"open={open_count} pending={pending_count} "
            f"margin={margin_snapshot.get('margin_cfd_eur') if isinstance(margin_snapshot, dict) else None} "
            f"available={margin_snapshot.get('available_to_trade_eur') if isinstance(margin_snapshot, dict) else None}"
        )

        if open_count <= 0:
            exec_state.setdefault("cancelled", []).append({
                **active_exec,
                "cancelled_reason": reason,
                "cancelled_utc": utc(),
            })
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)
        else:
            exec_state.setdefault("active", {})[asset] = active_exec

        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions

    # V24.1 SCALP ACTIVE — panier partiel :
    # une position est ouverte, mais L2/L3 restent en attente.
    # Ces pending restants ne doivent pas traîner trop longtemps.
    # V24.3.5B_KEEP_REINFORCEMENTS:
    # Partial basket: one or more legs are open and reinforcement limits remain pending.
    # Do not auto-cancel L2/L3 by age anymore. Margin guard above remains priority.
    if open_count > 0 and pending_count > 0:
        age_sec = v24_age_sec_from_iso(active_exec.get("created_utc"))
        reason = "V24_3_5B_KEEP_REINFORCEMENTS_NO_AUTO_CANCEL"

        active_exec["partial_pending_keep_enabled"] = True
        active_exec["partial_pending_keep_reason"] = reason
        active_exec["partial_pending_keep_age_sec"] = age_sec
        active_exec["partial_pending_keep_utc"] = utc()
        active_exec["partial_pending_keep_open_count"] = int(open_count)
        active_exec["partial_pending_keep_pending_count"] = int(pending_count)
        exec_state.setdefault("active", {})[asset] = active_exec

        event({
            "event": "BASKET_PARTIAL_PENDING_KEEP",
            "asset": asset,
            "cycle_id": active_exec.get("cycle_id"),
            "direction": direction,
            "open_count": open_count,
            "pending_count": pending_count,
            "age_sec": age_sec,
            "reason": reason,
        })

        print(
            f"{asset:10s} | BASKET_PARTIAL_PENDING_KEEP | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | "
            f"open={open_count} pending={pending_count} age={age_sec:.1f}s reason={reason}"
        )

        B.save_json(B.EXEC_STATE_FILE, exec_state)


    # V24.1 — panier vide localement.
    # Sécurité critique : avant de supprimer EXEC_STATE, on vérifie le broker.
    if open_count <= 0 and pending_count <= 0:
        broker_positions_left = v24_broker_positions_for_asset_from_list(
            positions=positions,
            asset=asset,
            direction=None,
        )

        broker_pending_left, broker_pending_status, broker_pending_raw = v24_broker_pending_orders_for_asset(
            headers=headers,
            asset=asset,
            direction=direction,
        )

        if broker_positions_left or broker_pending_left:
            reason = "V24_BASKET_EMPTY_RESET_BLOCKED_BROKER_NOT_EMPTY"

            cleanup_results = []
            if broker_pending_left:
                cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason="V24_ORPHAN_WORKING_ORDER_CLEANUP_BEFORE_RESET",
                )

            active_exec["empty_reset_blocked_reason"] = reason
            active_exec["empty_reset_blocked_utc"] = utc()
            active_exec["broker_positions_left_count"] = len(broker_positions_left)
            active_exec["broker_pending_left_count"] = len(broker_pending_left)
            active_exec["orphan_pending_cleanup_results"] = cleanup_results

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_EMPTY_RESET_BLOCKED | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"broker_positions={len(broker_positions_left)} "
                f"broker_pending={len(broker_pending_left)} "
                f"cleanup={len(cleanup_results)}"
            )

            return True, positions

        reason = "V24_BASKET_EMPTY_RESET"
        exec_state.setdefault("cancelled", []).append({
            **active_exec,
            "cancelled_reason": reason,
            "cancelled_utc": utc(),
        })
        exec_state.setdefault("active", {}).pop(asset, None)
        reset_cycle_idle(asset, reason)
        B.save_json(B.EXEC_STATE_FILE, exec_state)

        print(
            f"{asset:10s} | BASKET_EMPTY_RESET | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | broker confirmé vide -> EXEC supprimé"
        )
        return True, positions

    # V24.1 — panier raté : aucune jambe ouverte, ordres LIMIT encore en attente.
    # Si le cycle moteur est repassé IDLE ou si le panier est trop vieux,
    # on annule les LIMIT pour libérer la marge.
    if open_count <= 0 and pending_count > 0:
        age_sec = v24_age_sec_from_iso(active_exec.get("created_utc"))
        max_age = v24_pending_basket_max_age_sec()
        cycle_missing = bool(cycle.get("cycle_missing"))

        if cycle_missing or age_sec >= max_age:
            reason = "V24_PENDING_BASKET_SIGNAL_LOST_CANCEL" if cycle_missing else "V24_PENDING_BASKET_EXPIRED_CANCEL"

            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            # Filet de sécurité broker : même si le matching local rate
            # à cause d'un arrondi de taille, on annule aussi les vrais
            # working orders encore présents côté Capital.com.
            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason=reason + "_BROKER_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["cancel_results"] = cancel_results
            active_exec["broker_cleanup_results"] = broker_cleanup_results
            active_exec["cancelled_reason"] = reason
            active_exec["cancelled_utc"] = utc()
            active_exec["last_basket_age_sec"] = float(age_sec)

            exec_state.setdefault("cancelled", []).append(active_exec)
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_PENDING_CANCEL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"open=0 pending={pending_count} age={age_sec:.1f}s max={max_age:.1f}s reason={reason}"
            )
            return True, positions

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
    margin_snapshot = v242_fetch_account_margin_snapshot(headers)
    storm_snapshot = v243_build_storm_snapshot(assets)

    print()
    print("=" * 170)
    print("06G2 — EXECUTION SECURISEE — BLOC 3/3 — OPEN + CLOSE CONFIRMES")
    print("=" * 170)
    print("SEND_REAL_ORDERS      :", SEND_REAL_ORDERS)
    print("Positions broker HTTP :", status)
    v242_print_margin_guard_snapshot(margin_snapshot)
    v243_print_storm_guard_snapshot(storm_snapshot)
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
                        margin_snapshot=margin_snapshot,
                        storm_snapshot=storm_snapshot,
                    )

                    positions = positions_after if positions_after is not None else positions

                    still_active = asset in exec_state.get("active", {})

                    if still_active:
                        print(
                            f"{asset:10s} | BASKET_KEEP | 1-3 | {active_exec.get('direction', '--'):4s} | "
                            f"--         | TRADEABLE | cycle moteur IDLE ignoré, panier conservé"
                        )
                    else:
                        print(
                            f"{asset:10s} | BASKET_PROCESSED_REMOVED | 1-3 | {active_exec.get('direction', '--'):4s} | "
                            f"--         | TRADEABLE | panier traité puis supprimé/annulé"
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
                margin_snapshot=margin_snapshot,
                storm_snapshot=storm_snapshot,
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

            storm_blocked, storm_reasons = v243_storm_guard_blocks_asset(storm_snapshot, asset)
            if storm_blocked:
                reason = "BASKET_REJECT_STORM_GUARD"
                detail = ",".join(storm_reasons[:8]) or "STORM_GUARD"

                print(
                    f"{asset:10s} | {reason} | 1-3 | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | {detail}"
                )

                event({
                    "event": reason,
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "direction": direction,
                    "size": size,
                    "storm_reasons": storm_reasons,
                    "storm_snapshot": storm_snapshot,
                })

                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "reason": reason,
                    "detail": detail,
                    "utc": utc(),
                })

                reset_cycle_idle(asset, reason)
                B.save_json(B.EXEC_STATE_FILE, exec_state)
                continue

            margin_blocked, margin_reasons = v242_margin_guard_blocks_new_basket(margin_snapshot)
            if margin_blocked:
                reason = "BASKET_REJECT_MARGIN_GUARD"
                detail = ",".join(margin_reasons) or "MARGIN_GUARD"

                print(
                    f"{asset:10s} | {reason} | 1-3 | {direction:4s} | "
                    f"{size:<10.6f} | {market_status:9s} | "
                    f"{detail} margin={margin_snapshot.get('margin_cfd_eur')} "
                    f"available={margin_snapshot.get('available_to_trade_eur')}"
                )

                event({
                    "event": reason,
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "direction": direction,
                    "size": size,
                    "margin_snapshot": margin_snapshot,
                    "reasons": margin_reasons,
                })

                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "reason": reason,
                    "detail": detail,
                    "margin_snapshot": margin_snapshot,
                    "utc": utc(),
                })

                reset_cycle_idle(asset, reason)
                B.save_json(B.EXEC_STATE_FILE, exec_state)
                continue

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


def v2436_cleanup_all_broker_pending(headers, assets, reason):
    if not SEND_REAL_ORDERS or headers is None:
        return []

    results = []
    for asset in assets:
        asset = str(asset).upper()
        try:
            cancelled = v24_cancel_broker_pending_for_asset(
                headers=headers,
                asset=asset,
                direction=None,
                reason=reason,
            )
        except Exception as exc:
            cancelled = [{"ok": False, "exception": str(exc)}]
        results.append({"asset": asset, "cancel_results": cancelled})
        try:
            if cancelled:
                print(
                    f"{asset:10s} | V2436_EXIT_PENDING_CLEANUP | --  | ---- | "
                    f"--         | BROKER    | cancel_results={len(cancelled)} reason={reason}"
                )
        except Exception:
            pass

    try:
        v24_event_safe({
            "event": "V2436_EXIT_PENDING_CLEANUP_DONE",
            "reason": reason,
            "results": results,
        })
    except Exception:
        pass

    return results


def v2436_signal_handler(signum, frame):
    global _V2436_CLEANUP_RUNNING
    if _V2436_CLEANUP_RUNNING:
        raise KeyboardInterrupt

    _V2436_CLEANUP_RUNNING = True
    reason = f"V2436_SIGNAL_{int(signum)}_CLEANUP"
    try:
        print(f"V2436_SIGNAL_HANDLER | signal={signum} | cleanup pending broker orders")
        v2436_cleanup_all_broker_pending(
            headers=_V2436_RUNTIME_HEADERS,
            assets=_V2436_RUNTIME_ASSETS,
            reason=reason,
        )
    finally:
        raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default="ALL")
    parser.add_argument("--mode", choices=["status", "plan"], default="status")
    args = parser.parse_args()

    assets = parse_assets(args.assets)

    if args.mode == "status":
        show_status_only(assets)
        return

    global _V2436_RUNTIME_HEADERS, _V2436_RUNTIME_ASSETS
    _V2436_RUNTIME_ASSETS = list(assets)

    if SEND_REAL_ORDERS:
        load_env()
        headers = login()
    else:
        headers = None

    _V2436_RUNTIME_HEADERS = headers

    if v2436_env_bool("V2436_CLEANUP_PENDING_ON_SIGNAL", True):
        try:
            signal.signal(signal.SIGINT, v2436_signal_handler)
            signal.signal(signal.SIGTERM, v2436_signal_handler)
        except Exception:
            pass

    try:
        execute_from_cycle(headers, assets)
    finally:
        if v2436_env_bool("V2436_CLEANUP_PENDING_ON_EXIT", False):
            v2436_cleanup_all_broker_pending(
                headers=headers,
                assets=assets,
                reason="V2436_NORMAL_EXIT_PENDING_CLEANUP",
            )


if __name__ == "__main__":
    main()
