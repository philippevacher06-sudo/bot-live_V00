#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PATCH GLOBAL EXÉCUTION — BOT-PIVOT V24.1 SCALP ACTIVE

Corrige les bugs connus :
- matching taille broker tolérant
- LIMIT guard : BUY LIMIT sous BID, SELL LIMIT au-dessus ASK
- STOP guard : guaranteedStop=false sur actifs problématiques
- retry broker sur error.validation.limit.price et error.invalid.stoploss.*
- vérifie la présence des protections broker/state déjà ajoutées

Ne force pas CAPITAL_IDENTIFIER.
"""
from pathlib import Path
from datetime import datetime
import shutil, sys

TARGET = Path("BOT_PIVOT_06G2_execution_secure.py")
MARKER = "V24_SCALP_ACTIVE_GLOBAL_HELPERS_V3"

HELPERS = r'''
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
    # Important : ne pas ajouter de clés custom au payload broker.
    if not isinstance(payload, dict):
        return payload
    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    direction = str(payload.get("direction") or "").upper()
    if not asset or direction not in ("BUY", "SELL") or "level" not in payload:
        return payload
    try:
        old_level = float(payload.get("level"))
    except Exception:
        return payload
    bid, ask, spread, src = v24sa_latest_bid_ask(asset)
    if bid is None or ask is None:
        try:
            print(f"{asset:10s} | V24_LIMIT_SIDE_GUARD_SKIP | {direction:4s} | src={src}")
        except Exception:
            pass
        return payload
    gap = v24sa_limit_gap(asset, spread)
    new_level = old_level
    changed = False
    if direction == "BUY":
        max_level = bid - gap
        if old_level >= max_level:
            new_level = max_level
            changed = True
    else:
        min_level = ask + gap
        if old_level <= min_level:
            new_level = min_level
            changed = True
    if not changed:
        return payload
    new_level = v24sa_round(asset, new_level)
    tick = v24sa_tick(asset)
    if direction == "BUY" and new_level >= bid:
        new_level = v24sa_round(asset, bid - max(gap, tick))
    if direction == "SELL" and new_level <= ask:
        new_level = v24sa_round(asset, ask + max(gap, tick))
    clean = dict(payload)
    clean["level"] = new_level
    try:
        print(f"{asset:10s} | V24_LIMIT_SIDE_GUARD | {direction:4s} | old={old_level} new={new_level} bid={bid} ask={ask} gap={gap}")
    except Exception:
        pass
    return clean


def v24sa_guard_stop(payload):
    if not isinstance(payload, dict):
        return payload
    asset = str(payload.get("epic") or payload.get("asset") or "").upper()
    if not asset:
        return payload
    disabled = v24sa_env_csv_set(
        "V24_DISABLE_GUARANTEED_STOP_ASSETS",
        "EURJPY,USDJPY,GOLD,OIL_CRUDE,OIL_BRENT,BTCUSD,ETHUSD,J225,SILVER"
    )
    if asset in disabled and payload.get("guaranteedStop") is True:
        clean = dict(payload)
        clean["guaranteedStop"] = False
        try:
            print(f"{asset:10s} | V24_STOP_GUARD | guaranteedStop=false | stopDistance={clean.get('stopDistance')}")
        except Exception:
            pass
        return clean
    return payload


def v24sa_guard_working_payload(payload):
    payload = v24sa_guard_limit_side(payload)
    payload = v24sa_guard_stop(payload)
    return payload


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
    elif "error.invalid.stoploss" in err:
        retry_payload = dict(payload)
        retry_payload["guaranteedStop"] = False
        reason = "STOPLOSS_GUARANTEED_FALSE"
    if retry_payload is None:
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
'''

def die(msg):
    print("ERREUR PATCH:", msg)
    sys.exit(1)

def main():
    if not TARGET.exists():
        die(f"{TARGET} introuvable")
    s = TARGET.read_text()
    backup = TARGET.with_suffix(TARGET.suffix + ".bak_global_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(TARGET, backup)
    print("Backup créé:", backup)
    changed = False

    if "size_tol = max(0.02" in s:
        print("OK size_tol déjà présent")
    else:
        old = '''    try:
        if abs(float(size) - float(active_exec.get("size"))) > 1e-9:
            return False
    except Exception:
        return False
'''
        new = '''    try:
        expected_size = float(active_exec.get("size"))
        actual_size = float(size)
        size_tol = max(0.02, abs(expected_size) * 0.03, 1e-9)
        if abs(actual_size - expected_size) > size_tol:
            return False
    except Exception:
        return False
'''
        if old in s:
            s = s.replace(old, new, 1)
            changed = True
            print("PATCH size_tol ajouté")
        else:
            print("WARN size_tol: ancien bloc strict non trouvé")

    if MARKER in s:
        print("OK helpers globaux déjà présents")
    else:
        anchor = "\ndef v24_process_basket("
        if anchor not in s:
            anchor = "\ndef main("
        if anchor not in s:
            die("point d'insertion helper introuvable")
        pos = s.index(anchor)
        s = s[:pos] + "\n" + HELPERS + "\n" + s[pos:]
        changed = True
        print("PATCH helpers globaux ajoutés")

    if "v24sa_retry_working_order(headers, payload, status, data)" in s:
        print("OK guard/retry workingorders déjà présent")
    else:
        line = '    status, data = B.api_post(headers, "/api/v1/workingorders", payload)\n'
        repl = '''    payload = v24sa_guard_working_payload(payload)
    status, data = B.api_post(headers, "/api/v1/workingorders", payload)
    status, data, payload = v24sa_retry_working_order(headers, payload, status, data)
'''
        if line not in s:
            die("ligne B.api_post /workingorders introuvable")
        s = s.replace(line, repl, 1)
        changed = True
        print("PATCH guard/retry workingorders ajouté")

    expected = [
        "BASKET_EMPTY_RESET_BLOCKED",
        "V24_ORPHAN_WORKING_ORDER_CLEANUP_BEFORE_RESET",
        "V24_BASKET_TP_FAIL_CANCEL_PENDING_TO_FREE_MARGIN",
        "BASKET_PARTIAL_PENDING_CANCEL",
        "broker_cleanup_results",
    ]
    missing = [m for m in expected if m not in s]
    if missing:
        print("ATTENTION protections manquantes:", ", ".join(missing))
    else:
        print("OK protections broker/state principales présentes")

    if changed:
        TARGET.write_text(s)
        print("PATCH ÉCRIT:", TARGET)
    else:
        print("Aucun changement nécessaire")

if __name__ == "__main__":
    main()
