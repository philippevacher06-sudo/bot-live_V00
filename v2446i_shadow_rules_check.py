import os
import time
import importlib.util
import traceback

os.environ["V2446I_L1_MAX_MARGIN_EUR"] = "10"
os.environ["V2446I_L1_STOP_LOSS_EUR"] = "3"
os.environ["V2446I_BASKET_MAX_LOSS_EUR"] = "15"
os.environ["V2446I_BASKET_TAKE_PROFIT_EUR"] = "5"
os.environ["V2446I_MAX_LEGS"] = "5"
os.environ["V2446I_MARGIN_EUR_PER_1_SIZE"] = "300"
os.environ["V2446I_TIME_STOP_SEC"] = "14400"

def fake_pos(deal, side="BUY", upl=0.0, size=0.05, age_sec=60):
    now = time.time()
    old = now - age_sec
    return {
        "dealId": deal,
        "deal_id": deal,
        "epic": "ETHUSD",
        "instrumentName": "ETHUSD",
        "direction": side,
        "side": side,
        "size": size,
        "upl": upl,
        "profit": upl,
        "profitAndLoss": upl,
        "created_ts": old,
        "open_ts": old,
        "createdTimestamp": int(old * 1000),
        "market": {"epic": "ETHUSD"},
        "position": {
            "dealId": deal,
            "direction": side,
            "size": size,
            "upl": upl,
            "profit": upl,
            "profitAndLoss": upl,
            "created_ts": old,
            "createdTimestamp": int(old * 1000),
        },
    }

def show(name, ok, detail):
    print(("PASS" if ok else "FAIL"), name, detail)

try:
    spec = importlib.util.spec_from_file_location("runner_shadow", "BOT_PIVOT_24_4_forced_audit_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    events = []
    def shadow_log(event, **kw):
        events.append((event, kw))
        if event.startswith("RUNNER_V2446I") or event.startswith("RUNNER_ETH_BASKET") or event.startswith("RUNNER_RESET"):
            print("EVENT", event, kw)

    mod.log = shadow_log
    if hasattr(mod, "_v2446i_log"):
        mod._v2446i_log = shadow_log

    mod.api_delete = lambda headers, path: (200, {"shadow": True, "path": path})

    if hasattr(mod, "_v2446i_try_close"):
        mod._v2446i_try_close = lambda headers, pos: (True, {"shadow_close": True})
    if hasattr(mod, "_v2445_try_close"):
        mod._v2445_try_close = lambda pos: (True, {"shadow_close": True})

    if hasattr(mod, "_v2446i_close_all"):
        def fake_close_all(*args, **kwargs):
            return len(args[1]) if len(args) > 1 and isinstance(args[1], list) else 1, {
                "stage": "SHADOW_CLOSE_ALL",
                "args_len": len(args),
                "kwargs": kwargs,
            }
        mod._v2446i_close_all = fake_close_all

    print("SHADOW_IMPORT_OK")

    mod.asset_positions = lambda headers, asset: [fake_pos(f"d{i}", "BUY", 0.0) for i in range(5)]
    ok, info = mod.open_market_netting_safe(headers={"shadow": True}, side="BUY", size=0.25, signal={}, state={})
    show("MAX_LEGS_BLOCK", ok is False and info.get("reason") == "MAX_LEGS_REACHED", info)

    mod.asset_positions = lambda headers, asset: [fake_pos("d1", "BUY", 0.0)]
    ok, info = mod.open_market_netting_safe(headers={"shadow": True}, side="SELL", size=0.10, signal={}, state={})
    show("ANTI_YOYO_BLOCK", ok is False and info.get("reason") == "ANTI_YOYO_SIDE_LOCK", info)

    mod.asset_positions = lambda headers, asset: []
    ok, info = mod.open_market_netting_safe(headers={"shadow": True}, side="BUY", size=0.05, signal={}, state={})
    show("L1_MARGIN_BLOCK", ok is False and info.get("reason") == "L1_MARGIN_TOO_HIGH", info)

    def run_close_case(name, positions):
        before = len(events)
        try:
            closed, info = mod.close_winning_basket_if_needed({"shadow": True}, positions, {"bias": "BUY"})
            new_events = events[before:]
            decision = [x for x in new_events if x[0] == "RUNNER_ETH_BASKET_DECISION"]
            show(name, closed > 0 or bool(decision and decision[-1][1].get("ok")), {"closed": closed, "info": info, "decision": decision[-1][1] if decision else None})
        except Exception as exc:
            show(name, False, repr(exc))

    run_close_case("TP_BASKET_TRIGGER", [
        fake_pos("tp1", "BUY", 2.0),
        fake_pos("tp2", "BUY", 2.0),
        fake_pos("tp3", "BUY", 1.5),
    ])

    run_close_case("L1_STOP_TRIGGER", [
        fake_pos("sl1", "BUY", -3.2),
    ])

    run_close_case("BASKET_MAX_LOSS_TRIGGER", [
        fake_pos("loss1", "BUY", -5.0),
        fake_pos("loss2", "BUY", -5.0),
        fake_pos("loss3", "BUY", -5.5),
    ])

    run_close_case("TIME_STOP_TRIGGER", [
        fake_pos("time1", "BUY", -0.2, age_sec=15000),
        fake_pos("time2", "BUY", -0.2, age_sec=15000),
    ])

    print("SHADOW_DONE")

except Exception as exc:
    print("SHADOW_EXCEPTION", repr(exc))
    print(traceback.format_exc())
