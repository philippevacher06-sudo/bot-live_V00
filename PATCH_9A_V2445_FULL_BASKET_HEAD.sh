#!/usr/bin/env bash
set -euo pipefail
cd /home/philippe_vacher06/bot-pivot/live

cat > .v2445_full_eth_basket_apply.py <<'PY'
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
PY

echo "OK 1/3 cree"
