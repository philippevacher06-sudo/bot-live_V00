#!/usr/bin/env python3
from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()
RUNNER = ROOT / "BOT_PIVOT_24_4_forced_audit_runner.py"
ADVERSE = ROOT / "v2446_adverse_steps_patch.py"


PATCH_MARK_START = "# === V2446I_ETH_BTC_CASCADE_RULES_START ==="
PATCH_MARK_END = "# === V2446I_ETH_BTC_CASCADE_RULES_END ==="


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def backup(path: Path) -> Path:
    if not path.exists():
        fail(f"file not found: {path}")
    ts = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dst = path.with_name(f"{path.name}.before_v2446i_{ts}.bak")
    shutil.copy2(path, dst)
    print(f"BACKUP {path.name} -> {dst.name}")
    return dst


def replace_block(text: str, block: str) -> str:
    if PATCH_MARK_START in text:
        pattern = re.compile(
            re.escape(PATCH_MARK_START) + r".*?" + re.escape(PATCH_MARK_END),
            re.DOTALL,
        )
        text2, n = pattern.subn(block.strip("\n"), text, count=1)
        if n != 1:
            fail("existing V2446I block found but replacement failed")
        return text2

    main_anchor = 'if __name__ == "__main__":'
    idx = text.find(main_anchor)
    if idx < 0:
        fail('main anchor not found: if __name__ == "__main__":')
    return text[:idx].rstrip() + "\n\n\n" + block.strip("\n") + "\n\n\n" + text[idx:]


def patch_adverse(text: str) -> str:
    original = text

    # Force neutral legacy defaults. V2446I sets the actual adverse step from
    # current price * V2446I_STEP_PCT after the patch has read live prices.
    text = re.sub(
        r'_envf\("V244_PRICE_STEP_POINTS",\s*1\.0\)',
        '_envf("V244_PRICE_STEP_POINTS", 0.0)',
        text,
    )
    text = re.sub(
        r'_envf\("V244_PRICE_STEP_POINTS",\s*2\.0\)',
        '_envf("V244_PRICE_STEP_POINTS", 0.0)',
        text,
    )
    text = re.sub(
        r'_envf\("V244_MIN_EFFECTIVE_STEP_POINTS",\s*2\.0\)',
        '_envf("V244_MIN_EFFECTIVE_STEP_POINTS", 0.0)',
        text,
    )
    text = re.sub(
        r'_envf\("V244_SPREAD_STEP_MULT",\s*1\.5\)',
        '_envf("V244_SPREAD_STEP_MULT", 0.0)',
        text,
    )

    # If the dynamic spread block is present, make sure spread multiplication can
    # be disabled cleanly by V244_SPREAD_STEP_MULT=0.0.
    old = """    if spreads:
        avg_spread = sum(spreads) / len(spreads)
        step = max(step, avg_spread * spread_step_mult)
"""
    new = """    if spreads and spread_step_mult > 0:
        avg_spread = sum(spreads) / len(spreads)
        step = max(step, avg_spread * spread_step_mult)
    elif spreads:
        avg_spread = sum(spreads) / len(spreads)
"""
    if old in text:
        text = text.replace(old, new, 1)

    if "RUNNER_ETH_EMPTY_RESET_ABORTED_POSITIONS_REAPPEARED" not in text:
        old2 = """    if ps and st.get("eth_empty_confirmations"):
        st2 = dict(st)
        for k in ("eth_empty_confirmations", "eth_empty_confirm_required", "eth_empty_confirm_since"):
            st2.pop(k, None)
        st2["updated_ts"] = time.time()
        _write(st2)
        st = st2
        _audit("RUNNER_ETH_EMPTY_RESET_CONFIRMATION_CLEARED", asset=a, side=s, open_positions=len(ps))
"""
        new2 = """    if ps and st.get("eth_empty_confirmations"):
        _audit(
            "RUNNER_ETH_EMPTY_RESET_ABORTED_POSITIONS_REAPPEARED",
            asset=a,
            side=s,
            open_positions=len(ps),
            confirmations=st.get("eth_empty_confirmations"),
            state=st,
        )
        st2 = dict(st)
        for k in ("eth_empty_confirmations", "eth_empty_confirm_required", "eth_empty_confirm_since"):
            st2.pop(k, None)
        st2["updated_ts"] = time.time()
        _write(st2)
        st = st2
        _audit("RUNNER_ETH_EMPTY_RESET_CONFIRMATION_CLEARED", asset=a, side=s, open_positions=len(ps))
"""
        if old2 in text:
            text = text.replace(old2, new2, 1)
        else:
            print("WARN adverse abort-log anchor not found; abort log not added")

    if "RUNNER_V2446I_DYNAMIC_STEP" not in text:
        anchor = "    # Etat persistant V2446 : c'est notre garde-fou dur.\n"
        dynamic = """    step_pct = _envf("V2446I_STEP_PCT", 0.0007)
    if c is not None and step_pct > 0:
        previous_step = step
        step = abs(float(c)) * step_pct
        _audit(
            "RUNNER_V2446I_DYNAMIC_STEP",
            asset=a,
            side=s,
            current_level=c,
            step_pct=step_pct,
            previous_step=previous_step,
            dynamic_step=step,
        )

"""
        if anchor in text:
            text = text.replace(anchor, dynamic + anchor, 1)
        else:
            fail("adverse dynamic-step anchor not found")

    if text == original:
        print("WARN adverse patch made no text changes; file may already be patched")
    return text


RUNNER_BLOCK = r'''
# === V2446I_ETH_BTC_CASCADE_RULES_START ===
# V2446I hard floors + anti-yoyo wrapper.
# This block deliberately wraps existing runner functions instead of replacing the
# whole loop. It is idempotent and controlled by V2446I_CASCADE_ENABLED.
import os as _v2446i_os
import time as _v2446i_time


def _v2446i_bool(name, default=True):
    v = _v2446i_os.getenv(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _v2446i_float(name, default):
    try:
        return float(_v2446i_os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _v2446i_optional_float(name):
    v = _v2446i_os.getenv(name)
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _v2446i_int(name, default):
    try:
        return int(float(_v2446i_os.getenv(name, str(default))))
    except Exception:
        return int(default)


def _v2446i_log(event, **kw):
    fn = globals().get("log")
    if callable(fn):
        try:
            return fn(event, **kw)
        except Exception:
            pass
    try:
        print(f"event={event} | " + " | ".join(f"{k}={v!r}" for k, v in kw.items()), flush=True)
    except Exception:
        pass


def _v2446i_asset():
    return str(_v2446i_os.getenv("V244_TRADED_ASSET", globals().get("ASSET", "ETHUSD"))).upper()


def _v2446i_epic(pos):
    fn = globals().get("_v2445_epic")
    if callable(fn):
        try:
            return str(fn(pos)).upper()
        except Exception:
            pass
    if not isinstance(pos, dict):
        return ""
    return str(
        pos.get("epic")
        or pos.get("market", {}).get("epic")
        or pos.get("instrument", {}).get("epic")
        or ""
    ).upper()


def _v2446i_deal_id(pos):
    fn = globals().get("_v2445_deal_id")
    if callable(fn):
        try:
            return fn(pos)
        except Exception:
            pass
    if not isinstance(pos, dict):
        return None
    return pos.get("dealId") or pos.get("deal_id") or pos.get("position", {}).get("dealId")


def _v2446i_direction(pos):
    if not isinstance(pos, dict):
        return None
    return str(
        pos.get("direction")
        or pos.get("side")
        or pos.get("position", {}).get("direction")
        or ""
    ).upper() or None


def _v2446i_upl(pos):
    fn = globals().get("_v2445_upl")
    if callable(fn):
        try:
            return float(fn(pos))
        except Exception:
            pass
    if not isinstance(pos, dict):
        return 0.0
    for k in ("upl", "profit", "profitLoss", "unrealizedProfitLoss"):
        try:
            v = pos.get(k)
            if v is not None:
                return float(v)
        except Exception:
            pass
    try:
        return float(pos.get("position", {}).get("upl") or 0.0)
    except Exception:
        return 0.0


def _v2446i_age(pos):
    fn = globals().get("_v2445_age")
    if callable(fn):
        try:
            return float(fn(pos))
        except Exception:
            pass
    return 0.0


def _v2446i_result_ok(res):
    fn = globals().get("_v2445_result_ok")
    if callable(fn):
        try:
            return bool(fn(res))
        except Exception:
            pass
    if res is None:
        return True
    if hasattr(res, "status_code"):
        try:
            return 200 <= int(res.status_code) < 300
        except Exception:
            return False
    if isinstance(res, tuple) and res:
        try:
            return 200 <= int(res[0]) < 300
        except Exception:
            return False
    if isinstance(res, dict):
        st = res.get("status") or res.get("status_code")
        if st is not None:
            try:
                return 200 <= int(st) < 300
            except Exception:
                return False
        if res.get("errorCode") or res.get("error"):
            return False
    return True


def _v2446i_extract_positions(args, kwargs):
    fn = globals().get("_v2445_extract_positions")
    if callable(fn):
        try:
            out = fn(args, kwargs)
            if isinstance(out, list):
                return out
        except Exception:
            pass
    for v in list(kwargs.values()) + list(args):
        if isinstance(v, list):
            return v
    return []


def _v2446i_extract_headers(args, kwargs):
    h = kwargs.get("headers")
    if isinstance(h, dict):
        return h
    if args and isinstance(args[0], dict):
        return args[0]
    return None


def _v2446i_eth_positions(positions):
    asset = _v2446i_asset()
    return [p for p in (positions or []) if _v2446i_epic(p) == asset]


def _v2446i_try_close(pos, headers):
    deal_id = _v2446i_deal_id(pos)
    if not deal_id:
        return False, "NO_DEAL_ID"

    calls = []
    for name in ("close_position", "close_position_by_deal_id", "api_close_position", "delete_position"):
        fn = globals().get(name)
        if callable(fn):
            calls.append((name + "(pos)", lambda fn=fn, pos=pos: fn(pos)))
            calls.append((name + "(deal_id)", lambda fn=fn, deal_id=deal_id: fn(deal_id)))
            calls.append((name + "(dealId=)", lambda fn=fn, deal_id=deal_id: fn(dealId=deal_id)))

    fn = globals().get("api_delete")
    if callable(fn):
        if headers:
            for path in (f"/api/v1/positions/{deal_id}", f"/positions/{deal_id}", f"positions/{deal_id}", deal_id):
                calls.append((f"api_delete({path})", lambda fn=fn, headers=headers, path=path: fn(headers, path)))
        else:
            calls.append(("api_delete(SKIPPED_NO_HEADERS)", lambda: {"status": 0, "error": "NO_HEADERS"}))

    last = "NO_CLOSE_FUNCTION"
    for label, call in calls:
        try:
            res = call()
            if _v2446i_result_ok(res):
                return True, {"method": label, "response": res}
            last = {"method": label, "response": res}
        except Exception as exc:
            last = {"method": label, "error": repr(exc)}
    return False, last


def _v2446i_start_cooldown(reason):
    globals()["_V2446I_RESET_COOLDOWN_UNTIL"] = _v2446i_time.time() + _v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0)
    _v2446i_log(
        "RUNNER_RESET_COOLDOWN_STARTED",
        asset=_v2446i_asset(),
        reason=reason,
        cooldown_sec=_v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0),
        reset_cooldown_until=globals().get("_V2446I_RESET_COOLDOWN_UNTIL"),
    )


def _v2446i_close_all(headers, eth_positions, reason, total_upl):
    asset = _v2446i_asset()
    deal_ids = [_v2446i_deal_id(p) for p in eth_positions if _v2446i_deal_id(p)]
    _v2446i_log(
        "RUNNER_V2446I_HARD_CLOSE_ALL_START",
        asset=asset,
        reason=reason,
        total_upl=round(total_upl, 4),
        count=len(eth_positions),
        dealIds=deal_ids,
    )

    all_ok = True
    for pos in eth_positions:
        did = _v2446i_deal_id(pos)
        ok_close, info = _v2446i_try_close(pos, headers)
        all_ok = all_ok and bool(ok_close)
        _v2446i_log(
            "RUNNER_V2446I_HARD_CLOSE_RESULT",
            asset=asset,
            dealId=did,
            upl=round(_v2446i_upl(pos), 4),
            ok=ok_close,
            info=info,
        )

    _v2446i_log(
        "RUNNER_V2446I_HARD_CLOSE_ALL_DONE",
        asset=asset,
        ok=all_ok,
        reason=reason,
        total_upl=round(total_upl, 4),
        count=len(eth_positions),
    )
    if all_ok:
        _v2446i_start_cooldown(reason)
    return len(eth_positions) if all_ok else 0, {
        "stage": "V2446I_HARD_CLOSE_ALL",
        "ok": all_ok,
        "reason": reason,
        "closed_count": len(eth_positions) if all_ok else 0,
        "total_upl": round(total_upl, 4),
        "dealIds": deal_ids,
    }


_v2446i_previous_close_winning_basket_if_needed = globals().get("close_winning_basket_if_needed")


def close_winning_basket_if_needed(*args, **kwargs):
    if not _v2446i_bool("V2446I_CASCADE_ENABLED", True):
        if callable(_v2446i_previous_close_winning_basket_if_needed):
            return _v2446i_previous_close_winning_basket_if_needed(*args, **kwargs)
        return 0, {"stage": "V2446I_DISABLED_NO_PREVIOUS_CLOSE"}

    headers = _v2446i_extract_headers(args, kwargs)
    positions = _v2446i_extract_positions(args, kwargs)
    eth_positions = _v2446i_eth_positions(positions)
    total_upl = sum(_v2446i_upl(p) for p in eth_positions)
    count = len(eth_positions)

    tp = _v2446i_float("V2446I_BASKET_TAKE_PROFIT_EUR", 5.0)
    l1_stop = abs(_v2446i_float("V2446I_L1_STOP_LOSS_EUR", 3.0))
    max_loss = abs(_v2446i_float("V2446I_BASKET_MAX_LOSS_EUR", 15.0))
    max_legs = _v2446i_int("V2446I_MAX_LEGS", 5)
    time_stop = _v2446i_float("V2446I_TIME_STOP_SEC", 14400.0)
    max_age = max([_v2446i_age(p) for p in eth_positions] or [0.0])

    reasons = []
    close_reason = None
    if not eth_positions:
        reasons.append("NO_ETH_POSITION")
    if count > 0 and total_upl >= tp:
        close_reason = "BASKET_TAKE_PROFIT_REACHED"
    elif count == 1 and total_upl <= -l1_stop:
        close_reason = "L1_STOP_LOSS_REACHED"
    elif count >= 2 and total_upl <= -max_loss:
        close_reason = "BASKET_MAX_LOSS_REACHED"
    elif count > 0 and time_stop > 0 and max_age >= time_stop and total_upl < 0:
        close_reason = "TIME_STOP_LOSS_REACHED"

    if close_reason is None:
        if count > 0 and total_upl < tp:
            reasons.append("TOTAL_UPL_BELOW_TP")
        if count >= max_legs:
            reasons.append("MAX_LEGS_REACHED")

    _v2446i_log(
        "RUNNER_ETH_BASKET_DECISION",
        asset=_v2446i_asset(),
        ok=bool(close_reason),
        close_reason=close_reason,
        reasons=reasons,
        open_eth_count=count,
        dealIds=[_v2446i_deal_id(p) for p in eth_positions if _v2446i_deal_id(p)],
        total_upl=round(total_upl, 4),
        tp=tp,
        l1_stop=-l1_stop,
        basket_max_loss=-max_loss,
        max_age_sec=round(max_age, 2),
        time_stop_sec=time_stop,
        max_open_positions=max_legs,
    )

    if close_reason:
        return _v2446i_close_all(headers, eth_positions, close_reason, total_upl)

    return 0, {
        "stage": "V2446I_BASKET_NOT_READY",
        "reasons": reasons,
        "total_upl": round(total_upl, 4),
        "tp": tp,
        "max_open_positions": max_legs,
    }


_v2446i_previous_open_market_netting_safe = globals().get("open_market_netting_safe")


def _v2446i_l1_margin_estimate(size):
    per_one = _v2446i_optional_float("V2446I_MARGIN_EUR_PER_1_SIZE")
    if per_one is None:
        return None
    try:
        return float(size) * per_one
    except Exception:
        return None


def open_market_netting_safe(*args, **kwargs):
    if not _v2446i_bool("V2446I_CASCADE_ENABLED", True):
        if callable(_v2446i_previous_open_market_netting_safe):
            return _v2446i_previous_open_market_netting_safe(*args, **kwargs)
        return False, {"reason": "V2446I_DISABLED_NO_PREVIOUS_OPEN"}

    if not callable(_v2446i_previous_open_market_netting_safe):
        return False, {"reason": "NO_PREVIOUS_OPEN_MARKET_NETTING_SAFE"}

    headers = kwargs.get("headers")
    if not isinstance(headers, dict) and args and isinstance(args[0], dict):
        headers = args[0]
    side = str(kwargs.get("side") or (args[1] if len(args) > 1 else "")).upper()
    size = kwargs.get("size", args[2] if len(args) > 2 else None)
    asset = _v2446i_asset()
    max_legs = _v2446i_int("V2446I_MAX_LEGS", 5)
    l1_max_margin = _v2446i_float("V2446I_L1_MAX_MARGIN_EUR", 10.0)
    l1_max_size = _v2446i_optional_float("V2446I_L1_MAX_SIZE")

    positions = []
    fn_pos = globals().get("asset_positions")
    if callable(fn_pos) and headers:
        try:
            positions = fn_pos(headers, asset)
        except Exception as exc:
            _v2446i_log("RUNNER_V2446I_POSITION_READ_ERROR", asset=asset, exception=repr(exc))
    eth_positions = _v2446i_eth_positions(positions)
    count = len(eth_positions)

    cooldown_until = float(globals().get("_V2446I_RESET_COOLDOWN_UNTIL") or 0.0)
    now = _v2446i_time.time()
    if cooldown_until > now and count == 0:
        _v2446i_log(
            "RUNNER_RESET_COOLDOWN_ACTIVE",
            asset=asset,
            side=side,
            remaining_sec=round(cooldown_until - now, 2),
        )
        return False, {"reason": "RESET_COOLDOWN_ACTIVE", "remaining_sec": round(cooldown_until - now, 2)}
    if cooldown_until and cooldown_until <= now:
        globals()["_V2446I_RESET_COOLDOWN_UNTIL"] = 0.0
        _v2446i_log("RUNNER_RESET_COOLDOWN_DONE", asset=asset)

    if count >= max_legs:
        _v2446i_log(
            "RUNNER_V2446I_OPEN_BLOCKED_MAX_LEGS",
            asset=asset,
            side=side,
            open_eth_count=count,
            max_legs=max_legs,
        )
        return False, {"reason": "MAX_LEGS_REACHED", "open_eth_count": count, "max_legs": max_legs}

    existing_sides = sorted(set(filter(None, [_v2446i_direction(p) for p in eth_positions])))
    if count > 0 and side in ("BUY", "SELL") and existing_sides and side not in existing_sides:
        _v2446i_log(
            "RUNNER_V2446I_OPEN_BLOCKED_ANTI_YOYO",
            asset=asset,
            requested_side=side,
            existing_sides=existing_sides,
            open_eth_count=count,
        )
        return False, {"reason": "ANTI_YOYO_SIDE_LOCK", "existing_sides": existing_sides}

    if count == 0:
        margin_est = _v2446i_l1_margin_estimate(size)
        if l1_max_size is not None:
            try:
                if float(size) > l1_max_size:
                    _v2446i_log(
                        "RUNNER_V2446I_L1_SIZE_REDUCED",
                        asset=asset,
                        side=side,
                        old_size=size,
                        new_size=l1_max_size,
                    )
                    kwargs["size"] = l1_max_size
                    size = l1_max_size
                    margin_est = _v2446i_l1_margin_estimate(size)
            except Exception:
                pass
        _v2446i_log(
            "RUNNER_V2446I_L1_MARGIN_CHECK",
            asset=asset,
            side=side,
            size=size,
            margin_estimate_eur=margin_est,
            max_margin_eur=l1_max_margin,
            margin_policy="ESTIMATED_IF_V2446I_MARGIN_EUR_PER_1_SIZE_SET",
        )
        if margin_est is not None and margin_est > l1_max_margin:
            return False, {
                "reason": "L1_MARGIN_TOO_HIGH",
                "margin_estimate_eur": margin_est,
                "max_margin_eur": l1_max_margin,
            }

    return _v2446i_previous_open_market_netting_safe(*args, **kwargs)


_v2446i_previous_sync_state_with_broker_exposure = globals().get("sync_state_with_broker_exposure")


def sync_state_with_broker_exposure(state, net, net_side):
    had_state = bool((state or {}).get("active_bias")) or int((state or {}).get("sequence_count") or 0) != 0
    if callable(_v2446i_previous_sync_state_with_broker_exposure):
        state2 = _v2446i_previous_sync_state_with_broker_exposure(state, net, net_side)
    else:
        state2 = state
    if had_state and str(net_side).upper() == "FLAT":
        _v2446i_start_cooldown("BROKER_FLAT_EXPOSURE")
    return state2


_v2446i_os.environ["V244_PRICE_STEP_POINTS"] = "0.0"
_v2446i_os.environ["V244_MIN_EFFECTIVE_STEP_POINTS"] = "0.0"
_v2446i_os.environ["V244_SPREAD_STEP_MULT"] = _v2446i_os.getenv("V2446I_SPREAD_STEP_MULT", "0.0")
_v2446i_os.environ["V244_MAX_OPEN_POSITIONS"] = _v2446i_os.getenv("V2446I_MAX_LEGS", "5")
_v2446i_os.environ["V244_FULL_ETH_BASKET_TP_EUR"] = _v2446i_os.getenv("V2446I_BASKET_TAKE_PROFIT_EUR", "5.0")
_v2446i_os.environ["V2446I_STEP_PCT"] = _v2446i_os.getenv("V2446I_STEP_PCT", "0.0007")

_v2446i_log(
    "RUNNER_V2446I_CASCADE_RULES_ACTIVE",
    asset=_v2446i_asset(),
    l1_max_margin_eur=_v2446i_float("V2446I_L1_MAX_MARGIN_EUR", 10.0),
    l1_stop_loss_eur=-abs(_v2446i_float("V2446I_L1_STOP_LOSS_EUR", 3.0)),
    basket_max_loss_eur=-abs(_v2446i_float("V2446I_BASKET_MAX_LOSS_EUR", 15.0)),
    basket_take_profit_eur=_v2446i_float("V2446I_BASKET_TAKE_PROFIT_EUR", 5.0),
    max_legs=_v2446i_int("V2446I_MAX_LEGS", 5),
    step_pct=_v2446i_float("V2446I_STEP_PCT", 0.0007),
    step_pct_display="0.07%",
    reset_cooldown_sec=_v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0),
    time_stop_sec=_v2446i_float("V2446I_TIME_STOP_SEC", 14400.0),
)
# === V2446I_ETH_BTC_CASCADE_RULES_END ===
'''


def patch_runner(text: str) -> str:
    required = [
        "def close_winning_basket_if_needed",
        "def open_market_netting_safe",
        "def sync_state_with_broker_exposure",
        'if __name__ == "__main__":',
    ]
    for token in required:
        if token not in text:
            fail(f"runner anchor missing: {token}")
    return replace_block(text, RUNNER_BLOCK)


def py_compile(path: Path) -> None:
    subprocess.run([sys.executable, "-m", "py_compile", str(path)], check=True)
    print(f"PY_COMPILE_OK {path.name}")


def main() -> None:
    if not RUNNER.exists() or not ADVERSE.exists():
        fail("run this script from /home/philippe_vacher06/bot-pivot/live")

    backup(RUNNER)
    backup(ADVERSE)

    adverse_text = ADVERSE.read_text(encoding="utf-8")
    ADVERSE.write_text(patch_adverse(adverse_text), encoding="utf-8")
    print("PATCHED v2446_adverse_steps_patch.py")

    runner_text = RUNNER.read_text(encoding="utf-8")
    RUNNER.write_text(patch_runner(runner_text), encoding="utf-8")
    print("PATCHED BOT_PIVOT_24_4_forced_audit_runner.py")

    py_compile(ADVERSE)
    py_compile(RUNNER)
    print("PATCH_OK V2446I_CASCADE_RULES")


if __name__ == "__main__":
    main()
