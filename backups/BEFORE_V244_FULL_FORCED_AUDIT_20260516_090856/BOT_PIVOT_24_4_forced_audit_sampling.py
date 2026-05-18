# BOT_PIVOT_24_4_forced_audit_sampling.py
# V24.4 — audit expérimental forcé : ouvertures/minute + fermeture par paire faible/forte

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FORCED_AUDIT_ENABLED = os.getenv("V244_FORCED_AUDIT_ENABLED", "1") == "1"
CLOSE_PAIR_RATIO_MIN = float(os.getenv("V244_CLOSE_PAIR_RATIO_MIN", "1.67"))
MARGIN_MAX_EUR = float(os.getenv("V244_MARGIN_MAX_EUR", "3000"))
MARGIN_SOFT_EUR = float(os.getenv("V244_MARGIN_SOFT_EUR", "2600"))

EXCLUDED_ASSETS = {
    x.strip().upper()
    for x in os.getenv("V244_EXCLUDED_ASSETS", "").split(",")
    if x.strip()
}

AUDIT_DIR = Path(os.getenv("V244_AUDIT_DIR", "logs/v24_4_forced_audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def audit_log(event: str, **kw: Any) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day = time.strftime("%Y%m%d", time.gmtime())
    payload = {"ts_utc": ts, "event": event}
    payload.update(kw)
    line = " | ".join(f"{k}={v}" for k, v in payload.items())
    p = AUDIT_DIR / f"V24_4_FORCED_AUDIT_{day}.log"
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_excluded_asset(asset: str) -> bool:
    return str(asset or "").upper() in EXCLUDED_ASSETS


def safety_banner() -> None:
    audit_log(
        "SAFETY_LOCK",
        mode="DEMO_ONLY",
        forced_audit_enabled=FORCED_AUDIT_ENABLED,
        close_pair_ratio_min=CLOSE_PAIR_RATIO_MIN,
        margin_max=MARGIN_MAX_EUR,
        margin_soft=MARGIN_SOFT_EUR,
        excluded_assets=",".join(sorted(EXCLUDED_ASSETS)) if EXCLUDED_ASSETS else "--",
    )


def _size(rec: Dict[str, Any]) -> float:
    for k in ("size", "deal_size", "quantity", "qty"):
        try:
            if rec.get(k) is not None:
                return abs(float(rec.get(k)))
        except Exception:
            pass
    return 0.0


def _upl(rec: Dict[str, Any]) -> float:
    for k in ("broker_upl", "upl", "profit", "pnl", "internal_pnl", "pnl_eur"):
        try:
            if rec.get(k) is not None:
                return float(rec.get(k))
        except Exception:
            pass
    return 0.0


def _id(rec: Dict[str, Any]) -> str:
    for k in ("brokerDealId", "dealId", "deal_id", "id", "ref"):
        if rec.get(k):
            return str(rec.get(k))
    return "UNKNOWN"


def select_close_pair_from_records(asset: str, records: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    Sélectionne une paire faible/forte dans les records d'exécution.
    Règle : forte >= faible * 1.67.
    """
    asset = str(asset or "").upper()

    if not FORCED_AUDIT_ENABLED:
        return None

    if is_excluded_asset(asset):
        audit_log("AUDIT_CLOSE_PAIR_SKIP", asset=asset, reason="EXCLUDED_ASSET")
        return None

    clean = []
    for r in records or []:
        rr = dict(r)
        rr["_size"] = _size(rr)
        rr["_upl"] = _upl(rr)
        rr["_id"] = _id(rr)
        if rr["_size"] > 0 and rr["_id"] != "UNKNOWN":
            clean.append(rr)

    if len(clean) < 2:
        audit_log("AUDIT_CLOSE_PAIR_NONE", asset=asset, reason="NOT_ENOUGH_RECORDS", count=len(clean))
        return None

    # On cherche une vraie paire faible/forte.
    best = None
    best_ratio = 0.0

    for weak in clean:
        for strong in clean:
            if weak["_id"] == strong["_id"]:
                continue

            weak_size = weak["_size"]
            strong_size = strong["_size"]

            if weak_size <= 0:
                continue

            ratio = strong_size / weak_size

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
    weak_size = _size(weak)
    strong_size = _size(strong)
    ratio = strong_size / weak_size if weak_size else 0.0

    audit_log(
        "AUDIT_CLOSE_PAIR_EXECUTE",
        asset=asset,
        weak_id=_id(weak),
        weak_size=weak_size,
        weak_upl=_upl(weak),
        strong_id=_id(strong),
        strong_size=strong_size,
        strong_upl=_upl(strong),
        ratio=round(ratio, 3),
        pair_upl=round(_upl(weak) + _upl(strong), 4),
        reason=reason,
    )


if __name__ == "__main__":
    safety_banner()
    print("V24.4 forced audit module OK")
