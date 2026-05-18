# BOT_PIVOT_24_4_forced_audit_sampling.py
# V24.4 — audit expérimental forcé ETHUSD
# Objectif : information / audit, pas performance.

from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FORCED_AUDIT_ENABLED = os.getenv("V244_FORCED_AUDIT_ENABLED", "1") == "1"
DEMO_ONLY_LOCK = os.getenv("V244_DEMO_ONLY_LOCK", "1") == "1"

TRADED_ASSET = os.getenv("V244_TRADED_ASSET", "ETHUSD").upper()
CONFIRM_ASSET = os.getenv("V244_CONFIRM_ASSET", "BTCUSD").upper()

TARGET_OPENINGS_PER_MIN = int(os.getenv("V244_TARGET_OPENINGS_PER_MIN", "2"))
CLOSE_PAIR_RATIO_MIN = float(os.getenv("V244_CLOSE_PAIR_RATIO_MIN", "1.67"))

MARGIN_MAX_EUR = float(os.getenv("V244_MARGIN_MAX_EUR", "3000"))
MARGIN_SOFT_EUR = float(os.getenv("V244_MARGIN_SOFT_EUR", "2600"))

EXCLUDED_ASSETS = {
    x.strip().upper()
    for x in os.getenv("V244_EXCLUDED_ASSETS", "GOLD").split(",")
    if x.strip()
}

AUDIT_DIR = Path(os.getenv("V244_AUDIT_DIR", "logs/v24_4_forced_audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = Path(os.getenv("V244_STATE_FILE", "data/execution/v24_4_forced_audit_state.json"))
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

SIZE_SEQUENCE = [
    float(x.strip())
    for x in os.getenv("V244_SIZE_SEQUENCE", "0.06,0.10,0.12,0.18").split(",")
    if x.strip()
]

SIDE_MODE = os.getenv("V244_SIDE_MODE", "ALTERNATE").upper()


def now_ts() -> float:
    return time.time()


def audit_log(event: str, **kw: Any) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day = time.strftime("%Y%m%d", time.gmtime())
    payload = {"ts_utc": ts, "event": event}
    payload.update(kw)
    line = " | ".join(f"{k}={v}" for k, v in payload.items())
    p = AUDIT_DIR / f"V24_4_FORCED_AUDIT_{day}.log"
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"opens": [], "seq": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"opens": [], "seq": 0}


def save_state(st: Dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_excluded_asset(asset: str) -> bool:
    return str(asset or "").upper() in EXCLUDED_ASSETS


def safety_banner() -> None:
    audit_log(
        "SAFETY_LOCK",
        mode="DEMO_ONLY" if DEMO_ONLY_LOCK else "UNLOCKED",
        forced_audit_enabled=FORCED_AUDIT_ENABLED,
        traded_asset=TRADED_ASSET,
        confirm_asset=CONFIRM_ASSET,
        target_openings_per_min=TARGET_OPENINGS_PER_MIN,
        close_pair_ratio_min=CLOSE_PAIR_RATIO_MIN,
        margin_max=MARGIN_MAX_EUR,
        margin_soft=MARGIN_SOFT_EUR,
        excluded_assets=",".join(sorted(EXCLUDED_ASSETS)) if EXCLUDED_ASSETS else "--",
        size_sequence=",".join(str(x) for x in SIZE_SEQUENCE),
    )


def count_opens_last_60s() -> int:
    st = load_state()
    t = now_ts()
    return sum(1 for o in st.get("opens", []) if t - float(o.get("ts", 0)) <= 60)


def register_open(asset: str, side: str, size: float, reason: str, extra: Optional[Dict[str, Any]] = None) -> None:
    asset = str(asset or "").upper()
    if is_excluded_asset(asset):
        audit_log("AUDIT_OPEN_IGNORED", asset=asset, reason="EXCLUDED_ASSET")
        return

    st = load_state()
    t = now_ts()
    opens = st.setdefault("opens", [])
    opens.append({
        "ts": t,
        "asset": asset,
        "side": side,
        "size": float(size),
        "reason": reason,
        "extra": extra or {},
    })
    st["opens"] = [o for o in opens if t - float(o.get("ts", 0)) <= 600]
    save_state(st)

    audit_log(
        "AUDIT_OPEN_REGISTER",
        asset=asset,
        side=side,
        size=size,
        reason=reason,
        openings_last_60s=count_opens_last_60s(),
    )


def next_forced_order() -> Tuple[str, float, int]:
    st = load_state()
    seq = int(st.get("seq", 0) or 0)

    if SIDE_MODE == "BUY_ONLY":
        side = "BUY"
    elif SIDE_MODE == "SELL_ONLY":
        side = "SELL"
    else:
        side = "BUY" if seq % 2 == 0 else "SELL"

    size = SIZE_SEQUENCE[seq % len(SIZE_SEQUENCE)] if SIZE_SEQUENCE else 0.06

    st["seq"] = seq + 1
    save_state(st)

    return side, float(size), seq


def missing_openings() -> int:
    return max(0, TARGET_OPENINGS_PER_MIN - count_opens_last_60s())


def _nested_position(rec: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(rec.get("position"), dict):
        return rec["position"]
    return rec


def rec_asset(rec: Dict[str, Any]) -> str:
    pos = _nested_position(rec)
    for k in ("asset", "epic", "market", "symbol"):
        if rec.get(k):
            return str(rec.get(k)).upper()
        if pos.get(k):
            return str(pos.get(k)).upper()
    return ""


def rec_id(rec: Dict[str, Any]) -> str:
    pos = _nested_position(rec)
    for k in ("brokerDealId", "dealId", "deal_id", "id", "ref"):
        if rec.get(k):
            return str(rec.get(k))
        if pos.get(k):
            return str(pos.get(k))
    return "UNKNOWN"


def rec_size(rec: Dict[str, Any]) -> float:
    pos = _nested_position(rec)
    for k in ("size", "deal_size", "quantity", "qty"):
        try:
            if rec.get(k) is not None:
                return abs(float(rec.get(k)))
        except Exception:
            pass
        try:
            if pos.get(k) is not None:
                return abs(float(pos.get(k)))
        except Exception:
            pass
    return 0.0


def rec_upl(rec: Dict[str, Any]) -> float:
    pos = _nested_position(rec)
    for k in ("broker_upl", "upl", "profit", "pnl", "internal_pnl", "pnl_eur"):
        try:
            if rec.get(k) is not None:
                return float(rec.get(k))
        except Exception:
            pass
        try:
            if pos.get(k) is not None:
                return float(pos.get(k))
        except Exception:
            pass
    return 0.0


def select_close_pair_from_records(asset: str, records: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    asset = str(asset or "").upper()

    if not FORCED_AUDIT_ENABLED:
        return None

    if is_excluded_asset(asset):
        audit_log("AUDIT_CLOSE_PAIR_SKIP", asset=asset, reason="EXCLUDED_ASSET")
        return None

    clean = []
    for r in records or []:
        rr = dict(r)
        rr["_id"] = rec_id(rr)
        rr["_asset"] = rec_asset(rr) or asset
        rr["_size"] = rec_size(rr)
        rr["_upl"] = rec_upl(rr)

        if rr["_asset"] != asset:
            continue
        if rr["_id"] == "UNKNOWN":
            continue
        if rr["_size"] <= 0:
            continue

        clean.append(rr)

    if len(clean) < 2:
        audit_log("AUDIT_CLOSE_PAIR_NONE", asset=asset, reason="NOT_ENOUGH_RECORDS", count=len(clean))
        return None

    best = None
    best_ratio = 0.0

    for weak in clean:
        for strong in clean:
            if weak["_id"] == strong["_id"]:
                continue

            weak_size = weak["_size"]
            strong_size = strong["_size"]
            ratio = strong_size / weak_size if weak_size else 0.0

            if ratio >= CLOSE_PAIR_RATIO_MIN and ratio > best_ratio:
                best_ratio = ratio
                best = (weak, strong)

    if not best:
        audit_log(
            "AUDIT_CLOSE_PAIR_NONE",
            asset=asset,
            reason="NO_VALID_WEAK_STRONG_RATIO",
            ratio_min=CLOSE_PAIR_RATIO_MIN,
            records=len(clean),
            sizes=",".join(str(x["_size"]) for x in clean),
        )
        return None

    weak, strong = best

    audit_log(
        "AUDIT_CLOSE_PAIR_SELECT",
        asset=asset,
        weak_id=weak["_id"],
        weak_size=weak["_size"],
        weak_upl=weak["_upl"],
        strong_id=strong["_id"],
        strong_size=strong["_size"],
        strong_upl=strong["_upl"],
        ratio=round(best_ratio, 3),
        pair_upl=round(weak["_upl"] + strong["_upl"], 4),
        reason="VALID_WEAK_STRONG_PAIR",
    )

    return weak, strong


def register_close_pair(asset: str, weak: Dict[str, Any], strong: Dict[str, Any], reason: str) -> None:
    weak_size = rec_size(weak)
    strong_size = rec_size(strong)
    ratio = strong_size / weak_size if weak_size else 0.0

    audit_log(
        "AUDIT_CLOSE_PAIR_EXECUTE",
        asset=asset,
        weak_id=rec_id(weak),
        weak_size=weak_size,
        weak_upl=rec_upl(weak),
        strong_id=rec_id(strong),
        strong_size=strong_size,
        strong_upl=rec_upl(strong),
        ratio=round(ratio, 3),
        pair_upl=round(rec_upl(weak) + rec_upl(strong), 4),
        reason=reason,
    )


if __name__ == "__main__":
    safety_banner()
    print("V24.4 forced audit module OK")
