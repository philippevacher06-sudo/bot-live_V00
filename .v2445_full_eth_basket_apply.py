from pathlib import Path
from datetime import datetime, timezone
import re

p = Path("BOT_PIVOT_24_4_forced_audit_runner.py")
b = "# === V2445_FULL_ETH_BASKET_TP_START ==="
e = "# === V2445_FULL_ETH_BASKET_TP_END ==="

code = r'''
# === V2445_FULL_ETH_BASKET_TP_START ===
import os as _v2445_os, time as _v2445_time
from datetime import datetime as _v2445_dt, timezone as _v2445_tz

def _v2445_bool(name, default=False):
    v = _v2445_os.getenv(name)
    return default if v is None else str(v).strip().lower() in ("1","true","yes","on","y")

def _v2445_float(name, default):
    try: return float(_v2445_os.getenv(name, str(default)))
    except Exception: return float(default)

def _v2445_int(name, default):
    try: return int(float(_v2445_os.getenv(name, str(default))))
    except Exception: return int(default)

_v2445_os.environ.setdefault("V244_MAX_OPEN_POSITIONS", "12")
_v2445_os.environ.setdefault("V244_MARGIN_DRIVEN_MODE", "1")
_v2445_os.environ.setdefault("V244_MAX_NET_EXPOSURE", "0")
_v2445_os.environ.setdefault("V244_CLOSE_FULL_ETH_BASKET_ENABLED", "1")
_v2445_os.environ.setdefault("V244_FULL_ETH_BASKET_TP_EUR", _v2445_os.getenv("V244_WIN_BASKET_TP_EUR", "1.0"))

try:
    MAX_OPEN_POSITIONS = _v2445_int("V244_MAX_OPEN_POSITIONS", 12)
    max_open_positions = MAX_OPEN_POSITIONS
    MARGIN_DRIVEN_MODE = True
    MAX_NET_EXPOSURE = 0.0
except Exception:
    pass

def _v2445_log(event, **fields):
    for name in ("audit", "audit_event", "log_event", "write_audit_event", "write_audit", "audit_log"):
        fn = globals().get(name)
        if callable(fn):
            for call in (
                lambda: fn(event, **fields),
                lambda: fn({"event": event, **fields}),
                lambda: fn(**{"event": event, **fields}),
            ):
                try:
                    call()
                    return
                except Exception:
                    pass
    ts = _v2445_dt.now(_v2445_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("ts_utc=%s | event=%s | %s" % (ts, event, " | ".join(f"{k}={v}" for k,v in fields.items())), flush=True)

def _v2445_get(obj, *keys):
    if obj is None:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if obj.get(k) not in (None, ""):
                return obj.get(k)
        for parent in ("position", "market", "raw"):
            child = obj.get(parent)
            if isinstance(child, dict):
                v = _v2445_get(child, *keys)
                if v not in (None, ""):
                    return v
    for k in keys:
        if hasattr(obj, k):
            v = getattr(obj, k)
            if v not in (None, ""):
                return v
    return None

def _v2445_num(v, default=0.0):
    try: return float(str(v).replace(",", "."))
    except Exception: return float(default)

def _v2445_epic(pos):
    return str(_v2445_get(pos, "epic", "instrumentEpic", "symbol") or "").upper()

def _v2445_deal_id(pos):
    return str(_v2445_get(pos, "dealId", "deal_id", "id") or "")

def _v2445_upl(pos):
    return _v2445_num(_v2445_get(pos, "upl", "profit", "profitAndLoss", "pnl"), 0.0)

def _v2445_created_ts(pos):
    raw = _v2445_get(pos, "createdDateUTC", "createdDate", "openTime", "created_at")
    if not raw:
        return None
    try:
        txt = str(raw).replace("Z", "+00:00")
        dt = _v2445_dt.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_v2445_tz.utc)
        return dt.timestamp()
    except Exception:
        return None

def _v2445_age(pos):
    ts = _v2445_created_ts(pos)
    return 999999.0 if ts is None else max(0.0, _v2445_time.time() - ts)

def _v2445_positions_from_result(res):
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("positions", "open_positions", "data"):
            v = res.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                vv = _v2445_positions_from_result(v)
                if vv:
                    return vv
    return []

def _v2445_extract_positions(args, kwargs):
    for k in ("positions", "open_positions", "asset_positions", "positions_after"):
        v = kwargs.get(k)
        if isinstance(v, list):
            return v
    for a in args:
        if isinstance(a, list):
            return a
        if isinstance(a, dict):
            v = _v2445_positions_from_result(a)
            if v:
                return v
    for name in ("get_open_positions", "get_positions", "api_get_positions", "fetch_positions"):
        fn = globals().get(name)
        if callable(fn):
            try:
                v = _v2445_positions_from_result(fn())
                if v:
                    return v
            except Exception:
                pass
    return []

def _v2445_result_ok(res):
    if res is None:
        return True
    if hasattr(res, "status_code"):
        return 200 <= int(res.status_code) < 300
    if isinstance(res, dict):
        st = res.get("status") or res.get("status_code")
        if st is not None:
            try: return 200 <= int(st) < 300
            except Exception: pass
        if res.get("errorCode") or res.get("error"):
            return False
    return True

def _v2445_try_close(pos):
    deal_id = _v2445_deal_id(pos)
    if not deal_id:
        return False, "NO_DEAL_ID"
    calls = []
    for name in ("close_position", "close_position_by_deal_id", "api_close_position", "delete_position"):
        fn = globals().get(name)
        if callable(fn):
            calls.append((name + "(pos)", lambda fn=fn: fn(pos)))
            calls.append((name + "(deal_id)", lambda fn=fn: fn(deal_id)))
            calls.append((name + "(dealId=)", lambda fn=fn: fn(dealId=deal_id)))
    fn = globals().get("api_delete")
    if callable(fn):
        for path in (f"/api/v1/positions/{deal_id}", f"/positions/{deal_id}", f"positions/{deal_id}", deal_id):
            calls.append((f"api_delete({path})", lambda fn=fn, path=path: fn(path)))
    last = "NO_CLOSE_FUNCTION"
    for label, call in calls:
        try:
            res = call()
            if _v2445_result_ok(res):
                return True, {"method": label, "response": res}
            last = {"method": label, "response": res}
        except Exception as exc:
            last = {"method": label, "error": repr(exc)}
    return False, last

_v2445_previous_close_winning_basket_if_needed = globals().get("close_winning_basket_if_needed")

def close_winning_basket_if_needed(*args, **kwargs):
    if not _v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True):
        if callable(_v2445_previous_close_winning_basket_if_needed):
            return _v2445_previous_close_winning_basket_if_needed(*args, **kwargs)
        return False

    asset = str(_v2445_os.getenv("V244_TRADED_ASSET", globals().get("TRADED_ASSET", "ETHUSD"))).upper()
    tp = _v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0)
    min_age = _v2445_float("V244_FULL_BASKET_MIN_AGE_SEC", 0.0)

    positions = _v2445_extract_positions(args, kwargs)
    eth_positions = [p for p in positions if _v2445_epic(p) == asset]
    total_upl = sum(_v2445_upl(p) for p in eth_positions)
    deal_ids = [_v2445_deal_id(p) for p in eth_positions if _v2445_deal_id(p)]
    too_young = [_v2445_deal_id(p) for p in eth_positions if _v2445_age(p) < min_age]

    reasons = []
    if not eth_positions: reasons.append("NO_ETH_POSITION")
    if total_upl < tp: reasons.append("TOTAL_UPL_BELOW_TP")
    if too_young: reasons.append("POSITION_TOO_YOUNG")

    ok = not reasons
    _v2445_log("RUNNER_ETH_BASKET_DECISION", asset=asset, ok=ok, reasons=reasons,
               open_eth_count=len(eth_positions), dealIds=deal_ids,
               total_upl=round(total_upl, 4), tp=tp, min_age_sec=min_age,
               max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12))

    if not ok:
        return False

    _v2445_log("RUNNER_ETH_BASKET_CLOSE_ALL_START", asset=asset,
               reason="TOTAL_ETH_BASKET_TP_REACHED", total_upl=round(total_upl, 4),
               tp=tp, count=len(eth_positions), dealIds=deal_ids)

    allow_names = ("ALLOW_DIRECT_LOSS_CLOSE", "V244_ALLOW_DIRECT_LOSS_CLOSE", "allow_direct_loss_close")
    old_globals = {n: globals().get(n, None) for n in allow_names}
    old_env = _v2445_os.environ.get("V244_ALLOW_DIRECT_LOSS_CLOSE")
    globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = True
    globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = set(deal_ids)
    for n in allow_names:
        globals()[n] = True
    _v2445_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = "1"

    all_ok = True
    try:
        for pos in eth_positions:
            did = _v2445_deal_id(pos)
            ok_close, info = _v2445_try_close(pos)
            all_ok = all_ok and bool(ok_close)
            _v2445_log("RUNNER_ETH_BASKET_CLOSE_RESULT", asset=asset, dealId=did,
                       upl=round(_v2445_upl(pos), 4), ok=ok_close, info=info)
    finally:
        globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = False
        globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = set()
        for n, v in old_globals.items():
            if v is None and n in globals():
                try: del globals()[n]
                except Exception: pass
            else:
                globals()[n] = v
        if old_env is None:
            _v2445_os.environ.pop("V244_ALLOW_DIRECT_LOSS_CLOSE", None)
        else:
            _v2445_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = old_env

    _v2445_log("RUNNER_ETH_BASKET_CLOSE_ALL_DONE", asset=asset, ok=all_ok,
               total_upl=round(total_upl, 4), count=len(eth_positions))
    return True

_v2445_log("RUNNER_V2445_FULL_ETH_BASKET_PATCH_ACTIVE",
           max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12),
           full_eth_basket_close_enabled=_v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True),
           full_eth_basket_tp_eur=_v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0))
# === V2445_FULL_ETH_BASKET_TP_END ===
'''

original = p.read_text()
backup = p.with_name(p.name + ".bak." + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".v2445")
backup.write_text(original)

s = original
if b in s and e in s:
    s = re.sub(re.escape(b) + r".*?" + re.escape(e) + r"\n?", "", s, flags=re.S)

m = re.search(r'\nif\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:', s)
if not m:
    raise SystemExit("ERREUR: bloc if __name__ == '__main__' introuvable")

s = s[:m.start()] + "\n\n" + code + "\n" + s[m.start():]
p.write_text(s)

print("OK patch V2445 applique")
print("backup:", backup)
