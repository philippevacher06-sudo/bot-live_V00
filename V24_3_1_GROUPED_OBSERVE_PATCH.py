from pathlib import Path

def replace_once(s, old, new, label):
    if old not in s:
        raise SystemExit(f"MARKER INTROUVABLE: {label}")
    return s.replace(old, new, 1)

# ============================================================
# 1) Patch 06G2 : TP ladder + Bollinger observe + reset detail
# ============================================================

p = Path("BOT_PIVOT_06G2_execution_secure.py")
s = p.read_text(encoding="utf-8")

# --- TP ladder check log only ---
if "BASKET_TP_LADDER_CHECK" not in s:
    old = '''    active_exec["last_check_utc"] = utc()

    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)
'''
    new = '''    active_exec["last_check_utc"] = utc()

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
'''
    s = replace_once(s, old, new, "06G2 TP ladder")
    print("06G2: TP ladder check ajoute")
else:
    print("06G2: TP ladder check deja present")

# --- Bollinger width observe ---
if "BOLLINGER_WIDTH_OBSERVE" not in s:
    old = '    enriched["bb_width_required_m5"] = float(bb_check["required"])\n'
    new = '''    enriched["bb_width_required_m5"] = float(bb_check["required"])

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
'''
    s = replace_once(s, old, new, "06G2 width observe")
    print("06G2: Bollinger width observe ajoute")
else:
    print("06G2: Bollinger width observe deja present")

# --- Bollinger entry observe ---
if "BOLLINGER_ENTRY_OBSERVE" not in s:
    old = '    enriched["bollinger_limit_levels"] = levels\n'
    new = '''    enriched["bollinger_limit_levels"] = levels

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
'''
    s = replace_once(s, old, new, "06G2 entry observe")
    print("06G2: Bollinger entry observe ajoute")
else:
    print("06G2: Bollinger entry observe deja present")

# --- Broker empty reset detail ---
if "broker_empty_reset_last_broker_upl_total_eur" not in s:
    old = '''            active_exec["broker_empty_reset_cleanup_results"] = broker_cleanup_results
'''
    new = '''            active_exec["broker_empty_reset_cleanup_results"] = broker_cleanup_results
            active_exec["broker_empty_reset_last_broker_upl_total_eur"] = broker_upl_total_for_tp
            active_exec["broker_empty_reset_last_target_tp_eur"] = target
            active_exec["broker_empty_reset_last_internal_pnl_eur"] = float(pnl_total)
            active_exec["broker_empty_reset_last_broker_upl_count"] = int(broker_upl_count_for_tp)
'''
    s = replace_once(s, old, new, "06G2 reset fields")

    old2 = '''            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BROKER_EMPTY_RESET | 1-3 | {direction:4s} | "
'''
    new2 = '''            B.save_json(B.EXEC_STATE_FILE, exec_state)

            broker_empty_upl_s = "none" if broker_upl_total_for_tp is None else f"{float(broker_upl_total_for_tp):.4f}"
            broker_empty_target_s = "none" if target is None else f"{float(target):.4f}"

            print(
                f"{asset:10s} | BROKER_EMPTY_RESET | 1-3 | {direction:4s} | "
'''
    s = replace_once(s, old2, new2, "06G2 reset print vars")

    old3 = '''                f"local_open={open_count} broker_open=0 pending={pending_count} reason={reason}"
'''
    new3 = '''                f"local_open={open_count} broker_open=0 pending={pending_count} "
                f"last_broker_upl={broker_empty_upl_s} target={broker_empty_target_s} "
                f"broker_count={broker_upl_count_for_tp}/{open_count} internal={float(pnl_total):.4f} "
                f"reason={reason}"
'''
    s = replace_once(s, old3, new3, "06G2 reset print detail")
    print("06G2: broker empty reset enrichi")
else:
    print("06G2: broker empty reset deja enrichi")

p.write_text(s, encoding="utf-8")
print("06G2_PATCH_OK")

# ============================================================
# 2) Remplacement 06G1 : reconcile pending-aware
# ============================================================

Path("BOT_PIVOT_06G1_reconcile_broker.py").write_text(r'''#!/usr/bin/env python3
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
''', encoding="utf-8")
print("06G1: pending-aware remplace")

# ============================================================
# 3) Patch 06C : soft fail HTTP 429
# ============================================================

p06c = Path("BOT_PIVOT_06C_market_rules.py")
c = p06c.read_text(encoding="utf-8")

if "class RateLimitError" not in c:
    c = replace_once(
        c,
        'ENV_FILE = Path(".env")\n',
        'ENV_FILE = Path(".env")\n\nclass RateLimitError(RuntimeError):\n    pass\n',
        "06C RateLimitError",
    )

if "REFRESH_06C_RATE_LIMIT" not in c:
    c = replace_once(
        c,
        '''    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login refusé HTTP {r.status_code} : {r.text[:300]}")
''',
        '''    if r.status_code == 429:
        raise RateLimitError(f"Login refuse HTTP 429 : {r.text[:300]}")

    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login refusé HTTP {r.status_code} : {r.text[:300]}")
''',
        "06C login 429",
    )

    c = replace_once(
        c,
        '''    load_env()
    headers = login()

    print()
''',
        '''    load_env()

    try:
        headers = login()
    except RateLimitError as e:
        print()
        print("=" * 120)
        print("REFRESH_06C_RATE_LIMIT | HTTP 429 | contexte marche conserve | aucun ordre envoye")
        print(str(e)[:500])
        print("=" * 120)
        return

    print()
''',
        "06C main soft fail",
    )

p06c.write_text(c, encoding="utf-8")
print("06C: HTTP 429 soft-fail ajoute")

print("PATCH_GROUPED_OK")
