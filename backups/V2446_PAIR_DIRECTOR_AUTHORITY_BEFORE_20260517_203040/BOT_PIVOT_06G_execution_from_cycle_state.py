# BOT_PIVOT_06G_execution_from_cycle_state.py
# Exécution basée sur le cycle_state du module 05
# Verrouillé en DRY_RUN.
#
# Principe :
# - Le module 04 donne les signaux.
# - Le module 05 décide du cycle, du niveau, de la taille, du sens.
# - Le module 06G prépare l'exécution à partir du module 05.
#
# Aucun ordre réel tant que SEND_REAL_ORDERS=False.

import os
import json
import argparse
import math
from pathlib import Path
from datetime import datetime, timezone

import requests
import BOT_PIVOT_00_config as CFG

SEND_REAL_ORDERS = False

ENV_FILE = Path(".env")

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
MARKET_DIR = CFG.DATA_DIR / "markets"
EXEC_DIR = CFG.DATA_DIR / "execution"
EXEC_STATE_FILE = EXEC_DIR / "cycle_execution_state.json"
EVENTS_FILE = EXEC_DIR / "execution_from_cycle_events.jsonl"

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


def reset_cycle_after_reject(asset, reason, broker_response=None):
    """
    Sécurité anti-cycle fantôme :
    si Capital.com refuse l'ordre ou si aucun dealId n'est confirmé,
    l'actif est remis en IDLE pour empêcher la martingale virtuelle.
    """
    state = load_json(STATE_FILE, {"updated_utc": utc(), "assets": {}})
    assets = state.setdefault("assets", {})
    old_slot = assets.get(asset, {})

    assets[asset] = {
        "status": "IDLE",
        "cycle": None,
        "last_event": reason,
        "last_event_utc": utc(),
        "last_reject": {
            "old_status": old_slot.get("status"),
            "old_cycle": old_slot.get("cycle"),
            "broker_response": broker_response,
        },
    }

    state["updated_utc"] = utc()
    save_json(STATE_FILE, state)


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
    """
    Connexion Capital.com.

    Compatibilité V24.1 :
    - CAPITAL_LOGIN est accepté comme identifiant principal.
    - CAPITAL_IDENTIFIER reste accepté en fallback.
    """
    api_key = os.environ.get("CAPITAL_API_KEY")
    identifier = (
        os.environ.get("CAPITAL_LOGIN")
        or os.environ.get("CAPITAL_IDENTIFIER")
        or os.environ.get("CAPITAL_EMAIL")
    )
    password = os.environ.get("CAPITAL_PASSWORD")

    missing = []
    if not api_key:
        missing.append("CAPITAL_API_KEY")
    if not identifier:
        missing.append("CAPITAL_LOGIN ou CAPITAL_IDENTIFIER")
    if not password:
        missing.append("CAPITAL_PASSWORD")

    if missing:
        raise RuntimeError("Variables .env manquantes : " + ", ".join(missing))

    url = f"{CFG.BASE_URL}/api/v1/session"

    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "identifier": identifier,
        "password": password,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)

    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login Capital.com refusé HTTP {r.status_code} : {r.text[:300]}")

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
        return 0, {
            "DRY_RUN": True,
            "endpoint": endpoint,
            "payload": payload,
        }

    r = requests.post(f"{CFG.BASE_URL}{endpoint}", headers=headers, json=payload, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

def api_delete(headers, endpoint):
    if not SEND_REAL_ORDERS:
        return 0, {
            "DRY_RUN": True,
            "endpoint": endpoint,
        }

    r = requests.delete(f"{CFG.BASE_URL}{endpoint}", headers=headers, timeout=15)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

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

    status = (
        snapshot.get("marketStatus")
        or market.get("marketStatus")
        or instrument.get("marketStatus")
        or "UNKNOWN"
    )

    return {
        "status": status,
        "min_size": float(min_size) if min_size is not None else None,
    }

def broker_positions(headers):
    status, data = api_get(headers, "/api/v1/positions")
    return status, data.get("positions", []), data

def broker_position_epic(item):
    p = item.get("position", {}) or {}
    m = item.get("market", {}) or {}
    return m.get("epic") or p.get("epic")

def broker_position_deal_id(item):
    p = item.get("position", {}) or {}
    return p.get("dealId")

def broker_has_asset(asset, positions):
    for item in positions:
        if broker_position_epic(item) == asset:
            return True
    return False

def _rule_value(rule):
    """
    Capital.com renvoie souvent les règles sous forme :
    {"unit": "PERCENTAGE", "value": 0.1}
    ou parfois directement une valeur numérique.
    """
    if isinstance(rule, dict):
        return rule.get("value"), str(rule.get("unit", "POINTS")).upper()
    if rule is not None:
        return rule, "POINTS"
    return None, "POINTS"


def _round_up_to_step(value, step):
    if step is None or step <= 0:
        return round(float(value), 10)

    value = float(value)
    step = float(step)

    rounded = math.ceil(value / step) * step

    # Déduire un nombre raisonnable de décimales depuis le pas broker
    s = f"{step:.12f}".rstrip("0")
    decimals = len(s.split(".")[1]) if "." in s else 0

    return round(rounded, decimals + 2)


def _market_json(asset):
    f = MARKET_DIR / f"market_{asset}.json"
    if not f.exists():
        raise RuntimeError(
            f"Règles marché absentes pour {asset}. "
            f"Lancer d'abord BOT_PIVOT_06C_market_rules.py."
        )

    data = load_json(f, {})
    market = data.get("market", data) if isinstance(data, dict) else {}
    if not isinstance(market, dict):
        raise RuntimeError(f"JSON marché invalide pour {asset}")

    return market


def _market_mid_price(market):
    snapshot = market.get("snapshot", {}) if isinstance(market, dict) else {}

    bid = snapshot.get("bid")
    ask = snapshot.get("offer") or snapshot.get("ask") or snapshot.get("ofr")

    if bid is not None and ask is not None:
        return (float(bid) + float(ask)) / 2.0

    if bid is not None:
        return float(bid)

    if ask is not None:
        return float(ask)

    raise RuntimeError("Prix bid/ask introuvable pour calcul stop garanti")


def guaranteed_stop_distance(asset):
    market = _market_json(asset)
    rules = market.get("dealingRules", {}) or {}
    instrument = market.get("instrument", {}) or {}

    allowed = instrument.get("guaranteedStopAllowed")
    if allowed is False:
        raise RuntimeError(f"Stop garanti non autorisé pour {asset}")

    min_rule = (
        rules.get("minGuaranteedStopDistance")
        or rules.get("minControlledRiskStopDistance")
        or rules.get("minStopOrProfitDistance")
    )

    min_value, min_unit = _rule_value(min_rule)

    if min_value is None:
        raise RuntimeError(f"Distance minimale de stop garanti introuvable pour {asset}")

    price = _market_mid_price(market)

    if "PERCENT" in min_unit:
        distance = price * float(min_value) / 100.0
    else:
        distance = float(min_value)

    # Marge de sécurité pour éviter un rejet si le prix bouge entre calcul et ordre.
    safety_mult = float(getattr(CFG, "GUARANTEED_STOP_SAFETY_MULT", 1.20))
    distance *= safety_mult

    step_value, step_unit = _rule_value(rules.get("minStepDistance"))

    if step_value is not None:
        distance = _round_up_to_step(distance, float(step_value))
    else:
        distance = round(distance, 10)

    return distance


def build_open_payload(cycle):
    asset = cycle["asset"]
    direction = cycle["direction"]
    size = float(cycle["size"])

    stop_distance = guaranteed_stop_distance(asset)

    return {
        "epic": asset,
        "direction": direction,
        "size": size,
        "guaranteedStop": True,
        "stopDistance": stop_distance,
    }

def parse_confirm(confirm):
    if not isinstance(confirm, dict):
        return None

    return (
        confirm.get("dealId")
        or confirm.get("affectedDeals", [{}])[0].get("dealId")
        if confirm.get("affectedDeals")
        else None
    )

def current_cycles():
    state = load_json(STATE_FILE, {"assets": {}})
    out = {}

    for asset, slot in state.get("assets", {}).items():
        cycle = slot.get("cycle")
        if slot.get("status") == "IN_POSITION" and cycle:
            out[asset] = cycle

    return out

def execute_from_cycle(headers, assets):
    cycles = current_cycles()
    exec_state = load_json(EXEC_STATE_FILE, {"active": {}, "closed": []})

    if SEND_REAL_ORDERS:
        status, positions, _ = broker_positions(headers)
    else:
        status = "SKIPPED_DRY_RUN_NO_LOGIN"
        positions = []

    print()
    print("=" * 160)
    mode_label = "ORDRES DEMO ACTIFS" if SEND_REAL_ORDERS else "DRY_RUN"
    print(f"06G — EXECUTION DEPUIS CYCLE_STATE — {mode_label}")
    print("=" * 160)
    print("SEND_REAL_ORDERS =", SEND_REAL_ORDERS)
    print("Positions broker HTTP :", status)
    print("-" * 160)
    print("ACTIF      | ACTION          | LVL | DIR  | SIZE       | MARKET    | RAISON / PAYLOAD")
    print("-" * 160)

    for asset in assets:
        cycle = cycles.get(asset)
        active_exec = exec_state.get("active", {}).get(asset)

        # 1. Aucun cycle ouvert côté module 05
        if not cycle:
            if active_exec:
                deal_id = active_exec.get("dealId")
                if deal_id:
                    status, data = api_delete(headers, f"/api/v1/positions/{deal_id}")

                    event({
                        "event": "CLOSE_BECAUSE_CYCLE_IDLE",
                        "asset": asset,
                        "dealId": deal_id,
                        "dry_run": not SEND_REAL_ORDERS,
                        "status": status,
                        "response": data,
                    })

                    print(f"{asset:10s} | CLOSE_IDLE      | --  | --   | --         | --        | dealId={deal_id}")
                else:
                    print(f"{asset:10s} | CLEAR_LOCAL     | --  | --   | --         | --        | actif sans cycle, dealId manquant")

                exec_state.setdefault("closed", []).append({
                    **active_exec,
                    "closed_reason": "CYCLE_IDLE",
                    "closed_utc": utc(),
                    "dry_run": not SEND_REAL_ORDERS,
                })
                exec_state.setdefault("active", {}).pop(asset, None)

            else:
                print(f"{asset:10s} | IDLE            | --  | --   | --         | --        | aucun cycle")
            continue

        level = int(cycle["level"])
        direction = cycle["direction"]
        size = float(cycle["size"])

        market = get_market(asset)
        market_status = market["status"]
        min_size = market["min_size"]

        # 2. Marché non tradable
        if market_status != "TRADEABLE":
            print(f"{asset:10s} | SKIP_MARKET     | {level:<3} | {direction:4s} | {size:<10.6f} | {market_status:9s} | marché non tradeable")
            continue

        # 3. Taille non valide
        if min_size is None or size < min_size:
            print(f"{asset:10s} | SKIP_SIZE       | {level:<3} | {direction:4s} | {size:<10.6f} | {market_status:9s} | min broker={min_size}")
            continue

        # 4. Déjà exécuté au même niveau
        if active_exec:
            same_cycle = active_exec.get("cycle_id") == cycle.get("cycle_id")
            same_level = int(active_exec.get("level", -1)) == level

            if same_cycle and same_level:
                print(f"{asset:10s} | HOLD_EXECUTED   | {level:<3} | {direction:4s} | {size:<10.6f} | {market_status:9s} | niveau déjà exécuté")
                continue

            # Niveau changé : il faut fermer l'ancien niveau avant d'ouvrir le nouveau.
            old_deal_id = active_exec.get("dealId")

            if old_deal_id:
                status, data = api_delete(headers, f"/api/v1/positions/{old_deal_id}")

                event({
                    "event": "CLOSE_OLD_LEVEL",
                    "asset": asset,
                    "old_level": active_exec.get("level"),
                    "new_level": level,
                    "dealId": old_deal_id,
                    "dry_run": not SEND_REAL_ORDERS,
                    "status": status,
                    "response": data,
                })

                print(f"{asset:10s} | CLOSE_OLD_LVL   | {active_exec.get('level')}->{level:<1} | {direction:4s} | {size:<10.6f} | {market_status:9s} | close dealId={old_deal_id}")
            else:
                print(f"{asset:10s} | NEED_CLOSE      | {active_exec.get('level')}->{level:<1} | {direction:4s} | {size:<10.6f} | {market_status:9s} | ancien niveau sans dealId")

            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": "LEVEL_CHANGED",
                "new_level": level,
                "closed_utc": utc(),
                "dry_run": not SEND_REAL_ORDERS,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

        # 5. Sécurité : si une position broker existe déjà sur cet actif et n'est pas suivie par BOT-PIVOT
        if broker_has_asset(asset, positions) and not active_exec:
            print(f"{asset:10s} | SKIP_BROKERPOS  | {level:<3} | {direction:4s} | {size:<10.6f} | {market_status:9s} | position broker déjà présente")
            continue

        # 6. Préparer ouverture du niveau courant
        payload = build_open_payload(cycle)
        status, data = api_post(headers, "/api/v1/positions", payload)

        event({
            "event": "OPEN_FROM_CYCLE",
            "asset": asset,
            "cycle_id": cycle.get("cycle_id"),
            "level": level,
            "direction": direction,
            "size": size,
            "dry_run": not SEND_REAL_ORDERS,
            "status": status,
            "payload": payload,
            "response": data,
        })

        print(
            f"{asset:10s} | OPEN_FROM_CYC  | "
            f"{level:<3} | "
            f"{direction:4s} | "
            f"{size:<10.6f} | "
            f"{market_status:9s} | "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

        # 7. Stockage exécution
        # En réel : dealReference + confirm.
        # En DRY_RUN : faux dealId local pour éviter de rouvrir le même niveau à chaque boucle.
        if SEND_REAL_ORDERS:
            deal_ref = data.get("dealReference") if isinstance(data, dict) else None
            confirm_status = None
            confirm = None
            deal_id = None

            if status not in (200, 201):
                reason = f"OPEN_REJECT_HTTP_{status}"
                print(
                    f"{asset:10s} | OPEN_REJECT   | "
                    f"{level:<3} | {direction:4s} | {size:<10.6f} | "
                    f"{market_status:9s} | HTTP {status} | {json.dumps(data, ensure_ascii=False)[:200]}"
                )

                event({
                    "event": "OPEN_REJECT",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "dry_run": False,
                    "status": status,
                    "payload": payload,
                    "response": data,
                    "reason": reason,
                })

                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "open_status": status,
                    "response": data,
                    "rejected_utc": utc(),
                    "reason": reason,
                    "dry_run": False,
                })

                exec_state.setdefault("active", {}).pop(asset, None)
                reset_cycle_after_reject(asset, reason, data)
                continue

            if not deal_ref:
                reason = "OPEN_REJECT_NO_DEAL_REFERENCE"
                print(
                    f"{asset:10s} | OPEN_REJECT   | "
                    f"{level:<3} | {direction:4s} | {size:<10.6f} | "
                    f"{market_status:9s} | pas de dealReference"
                )

                event({
                    "event": "OPEN_REJECT",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "dry_run": False,
                    "status": status,
                    "payload": payload,
                    "response": data,
                    "reason": reason,
                })

                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "open_status": status,
                    "response": data,
                    "rejected_utc": utc(),
                    "reason": reason,
                    "dry_run": False,
                })

                exec_state.setdefault("active", {}).pop(asset, None)
                reset_cycle_after_reject(asset, reason, data)
                continue

            confirm_status, confirm = api_get(headers, f"/api/v1/confirms/{deal_ref}")
            deal_id = parse_confirm(confirm)

            if not deal_id:
                reason = "OPEN_REJECT_NO_CONFIRMED_DEALID"
                print(
                    f"{asset:10s} | OPEN_REJECT   | "
                    f"{level:<3} | {direction:4s} | {size:<10.6f} | "
                    f"{market_status:9s} | confirm sans dealId"
                )

                event({
                    "event": "OPEN_REJECT",
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "dry_run": False,
                    "status": status,
                    "payload": payload,
                    "response": data,
                    "dealReference": deal_ref,
                    "confirm_status": confirm_status,
                    "confirm": confirm,
                    "reason": reason,
                })

                exec_state.setdefault("rejected", []).append({
                    "asset": asset,
                    "cycle_id": cycle.get("cycle_id"),
                    "level": level,
                    "direction": direction,
                    "size": size,
                    "open_status": status,
                    "dealReference": deal_ref,
                    "confirm_status": confirm_status,
                    "confirm": confirm,
                    "rejected_utc": utc(),
                    "reason": reason,
                    "dry_run": False,
                })

                exec_state.setdefault("active", {}).pop(asset, None)
                reset_cycle_after_reject(asset, reason, confirm)
                continue

            exec_state.setdefault("active", {})[asset] = {
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "level": level,
                "direction": direction,
                "size": size,
                "dealReference": deal_ref,
                "dealId": deal_id,
                "open_status": status,
                "confirm_status": confirm_status,
                "confirm": confirm,
                "opened_utc": utc(),
                "dry_run": False,
            }
        else:
            dry_deal_id = f"DRY_{asset}_L{level}_{direction}_{cycle.get('cycle_id')}"
            exec_state.setdefault("active", {})[asset] = {
                "asset": asset,
                "cycle_id": cycle.get("cycle_id"),
                "level": level,
                "direction": direction,
                "size": size,
                "dealReference": None,
                "dealId": dry_deal_id,
                "open_status": "DRY_RUN",
                "confirm_status": "DRY_RUN",
                "confirm": {"DRY_RUN": True},
                "opened_utc": utc(),
                "dry_run": True,
            }

    save_json(EXEC_STATE_FILE, exec_state)

    print("=" * 160)
    if SEND_REAL_ORDERS:
        print("Mode ORDRES DEMO ACTIFS : aucun ordre envoyé si aucun cycle actif.")
    else:
        print("Aucun ordre réel envoyé tant que SEND_REAL_ORDERS=False.")
    print("Execution state :", EXEC_STATE_FILE)

def show_cycle_state(assets):
    cycles = current_cycles()

    print()
    print("=" * 130)
    print("06G — CYCLES ACTIFS DU MODULE 05")
    print("=" * 130)
    print("ACTIF      | LVL | DIR  | SIZE       | ENTRY        | TP €     | CYCLE")
    print("-" * 130)

    for asset in assets:
        c = cycles.get(asset)
        if not c:
            print(f"{asset:10s} | --  | --   | --         | --           | --       | aucun cycle")
            continue

        print(
            f"{asset:10s} | "
            f"{int(c['level']):<3} | "
            f"{c['direction']:4s} | "
            f"{float(c['size']):<10.6f} | "
            f"{float(c['entry_price']):<12.6f} | "
            f"{float(c['tp_eur']):<8.4f} | "
            f"{c.get('cycle_id')}"
        )

    print("=" * 130)

def parse_assets(raw):
    if raw.upper() == "ALL":
        return list(CFG.ASSETS)
    return [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["status", "plan"], default="plan")
    parser.add_argument("--assets", default="ALL")
    args = parser.parse_args()

    EXEC_DIR.mkdir(parents=True, exist_ok=True)
    assets = parse_assets(args.assets)

    if args.mode == "status":
        show_cycle_state(assets)
        return

    if SEND_REAL_ORDERS:
        load_env()
        headers = login()
    else:
        headers = None

    execute_from_cycle(headers, assets)

if __name__ == "__main__":
    main()
