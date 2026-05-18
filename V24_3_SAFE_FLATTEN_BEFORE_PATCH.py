import json
import time
import sys
from pathlib import Path
from datetime import datetime, timezone
import requests

import BOT_PIVOT_06G_execution_from_cycle_state as B

CONFIRM = "YES_FLATTEN_DEMO"

def utc():
    return datetime.now(timezone.utc).isoformat()

def items(data):
    if isinstance(data, dict):
        return data.get("workingOrders") or data.get("workingorders") or data.get("orders") or []
    return data if isinstance(data, list) else []

def wo_data(x):
    if not isinstance(x, dict):
        return {}
    return x.get("workingOrderData") or x.get("workingOrder") or x or {}

def wo_deal_id(x):
    d = wo_data(x)
    return d.get("dealId") or d.get("workingOrderId") or (x.get("dealId") if isinstance(x, dict) else None)

def wo_epic(x):
    d = wo_data(x)
    m = x.get("marketData", {}) if isinstance(x, dict) else {}
    m2 = x.get("market", {}) if isinstance(x, dict) else {}
    return d.get("epic") or m.get("epic") or m2.get("epic")

def wo_dir(x):
    return wo_data(x).get("direction")

def wo_size(x):
    d = wo_data(x)
    return d.get("orderSize") or d.get("size")

def wo_level(x):
    d = wo_data(x)
    return d.get("orderLevel") or d.get("level")

def pos_deal_id(p):
    try:
        return B.broker_position_deal_id(p)
    except Exception:
        return (
            p.get("position", {}).get("dealId")
            or p.get("dealId")
            or p.get("positionData", {}).get("dealId")
        )

def pos_epic(p):
    try:
        return B.broker_position_epic(p)
    except Exception:
        return (
            p.get("market", {}).get("epic")
            or p.get("marketData", {}).get("epic")
            or p.get("position", {}).get("epic")
            or p.get("epic")
        )

def pos_dir(p):
    return p.get("position", {}).get("direction") or p.get("direction")

def pos_size(p):
    return p.get("position", {}).get("size") or p.get("size")

def api_delete(headers, path):
    url = B.CFG.BASE_URL.rstrip("/") + path
    r = requests.delete(url, headers=headers, timeout=20)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:1000]}
    return r.status_code, data

def api_get_raw(headers, path):
    status, data = B.api_get(headers, path)
    return status, data

def print_broker_state(headers, title):
    st_pos, positions, _ = B.broker_positions(headers)
    st_wo, wo_raw = api_get_raw(headers, "/api/v1/workingorders")
    orders = items(wo_raw)

    print()
    print("=" * 120)
    print(title)
    print("=" * 120)
    print("POSITIONS HTTP :", st_pos, "count =", len(positions))
    for p in positions:
        print(
            "POSITION",
            "epic=", pos_epic(p),
            "dir=", pos_dir(p),
            "size=", pos_size(p),
            "dealId=", pos_deal_id(p),
        )

    print("PENDING HTTP   :", st_wo, "count =", len(orders))
    for o in orders:
        print(
            "PENDING ",
            "epic=", wo_epic(o),
            "dir=", wo_dir(o),
            "size=", wo_size(o),
            "level=", wo_level(o),
            "dealId=", wo_deal_id(o),
        )

    return positions, orders

def backup_file(path):
    p = Path(path)
    if not p.exists():
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = p.with_name(p.name + f".backup_manual_flatten_{ts}")
    backup.write_bytes(p.read_bytes())
    return backup

def reset_local_state():
    print()
    print("=" * 120)
    print("RESET LOCAL STATE — cycles + execution")
    print("=" * 120)

    # execution state
    exec_file = Path(B.EXEC_STATE_FILE)
    if exec_file.exists():
        backup = backup_file(exec_file)
        data = json.loads(exec_file.read_text(encoding="utf-8"))

        active = data.get("active", {})
        if active:
            archive = data.setdefault("manual_flattened_before_patch", [])
            archive.append({
                "utc": utc(),
                "reason": "MANUAL_FLATTEN_BEFORE_PATCH",
                "active_before_reset": active,
            })
            data["active"] = {}
            exec_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print("EXEC reset OK | active vidé | backup =", backup)
        else:
            print("EXEC déjà vide | backup =", backup)

    # cycle state
    state_file = Path(B.STATE_FILE)
    if state_file.exists():
        backup = backup_file(state_file)
        data = json.loads(state_file.read_text(encoding="utf-8"))

        changed = 0
        assets = data.get("assets", {})
        if isinstance(assets, dict):
            for asset, st in assets.items():
                if not isinstance(st, dict):
                    continue
                was_active = (
                    st.get("status") not in (None, "", "IDLE")
                    or bool(st.get("cycle"))
                )
                if was_active:
                    st["manual_flatten_before_patch_previous"] = {
                        "utc": utc(),
                        "status": st.get("status"),
                        "cycle": st.get("cycle"),
                    }
                    st["status"] = "IDLE"
                    st["cycle"] = {}
                    changed += 1

        data["updated_utc"] = utc()
        state_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("CYCLE reset OK | actifs remis IDLE =", changed, "| backup =", backup)

def main():
    B.load_env()

    base = str(B.CFG.BASE_URL)
    print("BASE_URL =", base)

    if "demo-api" not in base:
        print()
        print("SECURITE : BASE_URL ne semble PAS etre la demo.")
        print("ABORT.")
        sys.exit(2)

    print()
    print("Ce script va annuler les pending et fermer toutes les positions du compte DEMO.")
    typed = input(f"Pour confirmer, tape exactement {CONFIRM} : ").strip()
    if typed != CONFIRM:
        print("Confirmation incorrecte. Aucun ordre envoye.")
        sys.exit(3)

    headers = B.login()

    positions, orders = print_broker_state(headers, "ETAT BROKER AVANT FLATTEN")

    print()
    print("=" * 120)
    print("ANNULATION DES WORKING ORDERS / PENDING")
    print("=" * 120)

    for o in orders:
        did = wo_deal_id(o)
        if not did:
            print("SKIP pending sans dealId :", o)
            continue

        print("DELETE workingorder", wo_epic(o), wo_dir(o), "size=", wo_size(o), "level=", wo_level(o), "dealId=", did)
        st, data = api_delete(headers, f"/api/v1/workingorders/{did}")
        print(" -> HTTP", st, json.dumps(data, ensure_ascii=False)[:500])
        time.sleep(0.25)

    time.sleep(1)

    positions, orders = print_broker_state(headers, "ETAT APRES ANNULATION PENDING")

    print()
    print("=" * 120)
    print("FERMETURE DES POSITIONS OUVERTES")
    print("=" * 120)

    for p in positions:
        did = pos_deal_id(p)
        if not did:
            print("SKIP position sans dealId :", p)
            continue

        print("DELETE position", pos_epic(p), pos_dir(p), "size=", pos_size(p), "dealId=", did)
        st, data = api_delete(headers, f"/api/v1/positions/{did}")
        print(" -> HTTP", st, json.dumps(data, ensure_ascii=False)[:500])
        time.sleep(0.35)

    # Vérification finale avec 3 tentatives
    final_positions = []
    final_orders = []
    for attempt in range(1, 4):
        time.sleep(2)
        final_positions, final_orders = print_broker_state(headers, f"VERIFICATION FINALE tentative {attempt}/3")
        if len(final_positions) == 0 and len(final_orders) == 0:
            break

    if len(final_positions) > 0 or len(final_orders) > 0:
        print()
        print("ATTENTION : BROKER PAS ENCORE FLAT.")
        print("Positions restantes :", len(final_positions))
        print("Pending restants    :", len(final_orders))
        print("Ne patche pas tant que ce n'est pas a zero.")
        sys.exit(10)

    print()
    print("BROKER FLAT OK : 0 position, 0 pending.")

    reset_local_state()

    print()
    print("=" * 120)
    print("SAFE_FLATTEN_OK")
    print("=" * 120)

if __name__ == "__main__":
    main()
