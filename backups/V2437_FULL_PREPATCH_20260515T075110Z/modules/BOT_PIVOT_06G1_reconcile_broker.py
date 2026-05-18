#!/usr/bin/env python3
# 06G1 - Diagnostic broker / interne - lecture seule
# V24.3.1 - pending-aware : positions broker + working orders broker

from collections import defaultdict
import BOT_PIVOT_06G_execution_from_cycle_state as B

ASSETS = list(B.CFG.ASSETS)

def short(x):
    if not x:
        return "--"
    x = str(x)
    return x[:6] + "..." + x[-4:] if len(x) > 14 else x

def pos_epic(item):
    return B.broker_position_epic(item)

def pos_deal(item):
    return B.broker_position_deal_id(item)

def pos_dir(item):
    return item.get("position", {}).get("direction")

def pos_size(item):
    return item.get("position", {}).get("size")

def items(data):
    if isinstance(data, dict):
        return data.get("workingOrders") or data.get("workingorders") or data.get("orders") or []
    return data if isinstance(data, list) else []

def wo_data(x):
    if not isinstance(x, dict):
        return {}
    return x.get("workingOrderData") or x.get("workingOrder") or x or {}

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

def wo_deal(x):
    d = wo_data(x)
    return d.get("dealId") or d.get("workingOrderId") or (x.get("dealId") if isinstance(x, dict) else None)

def local_exec_counts(e):
    if not e:
        return 0, 0, 0
    levels = e.get("levels") or {}
    if not isinstance(levels, dict):
        return 0, 0, 0

    open_n = 0
    pending_n = 0
    other_n = 0

    for _, rec in levels.items():
        st = str(rec.get("status", ""))
        if st == "OPEN_POSITION":
            open_n += 1
        elif st.startswith("PENDING_LIMIT"):
            pending_n += 1
        else:
            other_n += 1

    return open_n, pending_n, other_n

def exec_txt(e):
    if not e:
        return "--"
    open_n, pending_n, other_n = local_exec_counts(e)
    direction = e.get("direction", "--")
    cycle = short(e.get("cycle_id"))
    return f"{direction} open={open_n} pending={pending_n} other={other_n} cycle={cycle}"

def cycle_txt(c):
    if not c:
        return "--"
    return f"L{c.get('level')} {c.get('direction')} size={c.get('size')}"

def main():
    print("=" * 140)
    print("BOT_PIVOT_06G1 - RECONCILIATION LECTURE SEULE - V24.3.1 PENDING-AWARE")
    print("=" * 140)
    print("Aucun ordre envoye.")
    print()

    B.load_env()
    headers = B.login()

    status, positions, _ = B.broker_positions(headers)

    try:
        wo_status, wo_raw = B.api_get(headers, "/api/v1/workingorders")
        working_orders = items(wo_raw)
    except Exception as e:
        wo_status = "ERR"
        working_orders = []
        print("GET /workingorders erreur :", e)

    cycles = B.current_cycles()
    exec_state = B.load_json(B.EXEC_STATE_FILE, {"active": {}})
    active = exec_state.get("active", {})

    pos_by_asset = defaultdict(list)
    for p in positions:
        epic = pos_epic(p)
        if epic:
            pos_by_asset[epic].append(p)

    wo_by_asset = defaultdict(list)
    for w in working_orders:
        epic = wo_epic(w)
        if epic:
            wo_by_asset[epic].append(w)

    print("GET /positions     :", status)
    print("Total positions    :", len(positions))
    print("GET /workingorders :", wo_status)
    print("Total pending      :", len(working_orders))
    print()

    print(f"{'ACTIF':10s} | {'POS':>3s} | {'PEND':>4s} | {'CYCLE':26s} | {'EXEC_STATE':46s} | ANOMALIE")
    print("-" * 140)

    for asset in ASSETS:
        bpos = pos_by_asset.get(asset, [])
        bpend = wo_by_asset.get(asset, [])
        c = cycles.get(asset)
        e = active.get(asset)

        local_open, local_pending, local_other = local_exec_counts(e)
        anomalies = []

        if len(bpos) > 1:
            anomalies.append("MULTI_POS_BROKER")
        if bpos and not e:
            anomalies.append("BROKER_POS_NON_SUIVI")
        if bpend and not e:
            anomalies.append("BROKER_PENDING_NON_SUIVI")
        if e and not bpos and not bpend:
            anomalies.append("LOCAL_ACTIVE_SANS_BROKER")
        if local_open > 0 and not bpos:
            anomalies.append("LOCAL_OPEN_ABSENT_BROKER")
        if local_pending > 0 and not bpend:
            anomalies.append("LOCAL_PENDING_ABSENT_BROKER")
        if bpos and not c:
            anomalies.append("BROKER_POS_ALORS_CYCLE_IDLE")
        if bpend and not c:
            anomalies.append("BROKER_PENDING_ALORS_CYCLE_IDLE")
        if c and e and c.get("cycle_id") != e.get("cycle_id"):
            anomalies.append("CYCLE_ID_DIFF")

        if e:
            levels = e.get("levels") or {}
            local_working_ids = []
            local_deal_ids = []

            if isinstance(levels, dict):
                for _, rec in levels.items():
                    if rec.get("workingDealId"):
                        local_working_ids.append(rec.get("workingDealId"))
                    if rec.get("brokerDealId") or rec.get("dealId"):
                        local_deal_ids.append(rec.get("brokerDealId") or rec.get("dealId"))

            broker_pos_deals = [pos_deal(x) for x in bpos]
            broker_pending_deals = [wo_deal(x) for x in bpend]

            for did in local_deal_ids:
                if did and did not in broker_pos_deals:
                    anomalies.append("LOCAL_DEAL_ABSENT_POS")

            for wid in local_working_ids:
                if wid and wid not in broker_pending_deals:
                    anomalies.append("LOCAL_WORKING_ID_ABSENT_PENDING")

        print(
            f"{asset:10s} | {len(bpos):>3d} | {len(bpend):>4d} | "
            f"{cycle_txt(c):26s} | {exec_txt(e):46s} | "
            f"{', '.join(sorted(set(anomalies))) if anomalies else 'OK'}"
        )

        for p in bpos:
            print(
                f"{'':10s} | {'':3s} | {'':4s} | "
                f"broker position -> {pos_dir(p)} size={pos_size(p)} deal={short(pos_deal(p))}"
            )

        for w in bpend:
            print(
                f"{'':10s} | {'':3s} | {'':4s} | "
                f"broker pending  -> {wo_dir(w)} size={wo_size(w)} level={wo_level(w)} deal={short(wo_deal(w))}"
            )

    print("=" * 140)

if __name__ == "__main__":
    main()
