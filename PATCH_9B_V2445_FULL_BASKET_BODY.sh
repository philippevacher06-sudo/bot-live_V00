#!/usr/bin/env bash
set -euo pipefail
cd /home/philippe_vacher06/bot-pivot/live

cat >> .v2445_full_eth_basket_apply.py <<'PY'

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
PY

echo "OK 2/3 cree"
