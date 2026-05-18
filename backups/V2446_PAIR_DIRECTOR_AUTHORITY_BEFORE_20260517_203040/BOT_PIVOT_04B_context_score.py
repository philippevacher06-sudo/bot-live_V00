# BOT_PIVOT_04B_context_score.py
# V23 — Contexte scalping : VWAP tick approximé + Camarilla + phase + score

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import BOT_PIVOT_00_config as CFG


def parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def price_value(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, dict):
        vals = []
        for k in ("mid", "lastTraded", "bid", "ask"):
            try:
                if x.get(k) is not None:
                    vals.append(float(x[k]))
            except Exception:
                pass
        if "bid" in x and "ask" in x:
            try:
                return (float(x["bid"]) + float(x["ask"])) / 2.0
            except Exception:
                pass
        if vals:
            return sum(vals) / len(vals)
    try:
        return float(x)
    except Exception:
        return None


def candle_ohlc(c: Dict[str, Any]) -> Optional[Tuple[datetime, float, float, float]]:
    dt = None
    for k in ("snapshotTimeUTC", "snapshotTime", "time", "timestamp", "date", "datetime"):
        dt = parse_dt(c.get(k))
        if dt:
            break

    high = price_value(c.get("high") or c.get("highPrice"))
    low = price_value(c.get("low") or c.get("lowPrice"))
    close = price_value(c.get("close") or c.get("closePrice"))

    if dt is None or high is None or low is None or close is None:
        return None

    return dt, float(high), float(low), float(close)


def history_path(asset: str) -> Path:
    if hasattr(CFG, "HISTORY_DIR"):
        return CFG.HISTORY_DIR / f"{asset}_MINUTE_15_30d.json"
    return CFG.DATA_DIR / "history" / f"{asset}_MINUTE_15_30d.json"


def load_history_candles(asset: str) -> List[Tuple[datetime, float, float, float]]:
    path = history_path(asset)
    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(raw, dict):
        rows = raw.get("candles") or raw.get("prices") or raw.get("data") or raw.get("items") or []
    elif isinstance(raw, list):
        rows = raw
    else:
        rows = []

    out = []
    for c in rows:
        if not isinstance(c, dict):
            continue
        item = candle_ohlc(c)
        if item:
            out.append(item)

    out.sort(key=lambda x: x[0])
    return out


def previous_session_hlc(asset: str) -> Optional[Tuple[float, float, float]]:
    candles = load_history_candles(asset)
    if len(candles) < 10:
        return None

    last_day = candles[-1][0].date()
    previous = [x for x in candles if x[0].date() < last_day]

    if not previous:
        return None

    prev_day = previous[-1][0].date()
    day_rows = [x for x in previous if x[0].date() == prev_day]

    if not day_rows:
        return None

    high = max(x[1] for x in day_rows)
    low = min(x[2] for x in day_rows)
    close = day_rows[-1][3]

    if high <= low:
        return None

    return high, low, close


def camarilla_levels(asset: str) -> Dict[str, Optional[float]]:
    hlc = previous_session_hlc(asset)
    if not hlc:
        return {"h3": None, "h4": None, "l3": None, "l4": None}

    high, low, close = hlc
    rng = high - low

    return {
        "h3": close + rng * 1.1 / 4.0,
        "h4": close + rng * 1.1 / 2.0,
        "l3": close - rng * 1.1 / 4.0,
        "l4": close - rng * 1.1 / 2.0,
    }


def session_ticks(ticks_all: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not ticks_all:
        return []

    last_dt = ticks_all[-1].get("_dt")
    if not last_dt:
        return ticks_all[-300:]

    day = last_dt.date()
    rows = [t for t in ticks_all if t.get("_dt") and t["_dt"].date() == day]
    return rows if rows else ticks_all[-300:]


def tick_vwap_approx(ticks: List[Dict[str, Any]]) -> Optional[float]:
    mids = []
    for t in ticks:
        try:
            mids.append(float(t["mid"]))
        except Exception:
            pass

    if not mids:
        return None

    # Approximation faute de volume exploitable dans le flux tick CFD.
    return sum(mids) / len(mids)


def ema(values: List[float], period: int) -> List[float]:
    if not values:
        return []

    alpha = 2.0 / (period + 1.0)
    out = [values[0]]

    for v in values[1:]:
        out.append(alpha * v + (1.0 - alpha) * out[-1])

    return out


def detect_phase(ticks: List[Dict[str, Any]]) -> str:
    mids = []
    for t in ticks[-400:]:
        try:
            mids.append(float(t["mid"]))
        except Exception:
            pass

    if len(mids) < 60:
        return "UNKNOWN"

    e20 = ema(mids, 20)
    e50 = ema(mids, 50)

    if len(e50) < 20:
        return "UNKNOWN"

    slope = e50[-1] - e50[-15]
    tol = max(abs(mids[-1]) * 0.00003, 1e-9)

    if e20[-1] > e50[-1] and slope > tol:
        return "TREND_UP"

    if e20[-1] < e50[-1] and slope < -tol:
        return "TREND_DOWN"

    if abs(e20[-1] - e50[-1]) <= tol * 2:
        return "RANGE"

    return "TRANSITION"


def near(price: float, level: Optional[float], tol: float) -> bool:
    if level is None:
        return False
    return abs(price - level) <= tol


def score_signal(
    asset: str,
    decision: str,
    ticks_all: List[Dict[str, Any]],
    ticks_recent: List[Dict[str, Any]],
    mid: float,
    chosen_zone: Optional[Dict[str, Any]],
    range_position: Optional[float],
    micro_rebound: bool,
    micro_reject: bool,
) -> Dict[str, Any]:

    decision = str(decision).upper()
    st = session_ticks(ticks_all)
    vwap = tick_vwap_approx(st)
    phase = detect_phase(st if st else ticks_recent)

    try:
        spread = float(ticks_recent[-1].get("spread", 0.0))
    except Exception:
        spread = 0.0

    band = max(spread * 2.0, abs(mid) * 0.0002)

    if vwap is None:
        vwap_bias = "UNKNOWN"
    elif mid > vwap + band:
        vwap_bias = "BUY"
    elif mid < vwap - band:
        vwap_bias = "SELL"
    else:
        vwap_bias = "NEUTRAL"

    cam = camarilla_levels(asset)
    cam_tol = max(spread * 5.0, abs(mid) * 0.0005)

    score = 0
    parts = []

    if decision not in ("BUY", "SELL"):
        return {
            "score": 0,
            "ok": False,
            "summary": f"decision={decision}; vwap={vwap_bias}; phase={phase}",
            "vwap": vwap,
            "vwap_bias": vwap_bias,
            "phase": phase,
            "camarilla_context": "NO_SIGNAL",
            "camarilla": cam,
        }

    score += 1
    parts.append("trigger_M1:+1")

    ztype = chosen_zone.get("type") if isinstance(chosen_zone, dict) else None

    if decision == "BUY" and ztype in ("support", "active"):
        score += 1
        parts.append(f"zone_{ztype}:+1")
    elif decision == "SELL" and ztype in ("resistance", "active"):
        score += 1
        parts.append(f"zone_{ztype}:+1")

    if decision == "BUY" and micro_rebound:
        score += 1
        parts.append("micro_rebond:+1")
    elif decision == "SELL" and micro_reject:
        score += 1
        parts.append("micro_rejet:+1")

    if vwap_bias == decision:
        score += 2
        parts.append("vwap_ok:+2")
    elif vwap_bias in ("BUY", "SELL") and vwap_bias != decision:
        score -= 2
        parts.append("vwap_contre:-2")
    else:
        parts.append(f"vwap_{vwap_bias}:0")

    phase_veto = False

    if phase == "TREND_UP" and decision == "BUY":
        score += 2
        parts.append("phase_up_ok:+2")
    elif phase == "TREND_DOWN" and decision == "SELL":
        score += 2
        parts.append("phase_down_ok:+2")
    elif phase == "RANGE":
        score += 1
        parts.append("phase_range:+1")
    elif phase == "TREND_UP" and decision == "SELL":
        score -= 4
        phase_veto = True
        parts.append("PHASE_VETO_sell_contre_trend_up:-4")
    elif phase == "TREND_DOWN" and decision == "BUY":
        score -= 4
        phase_veto = True
        parts.append("PHASE_VETO_buy_contre_trend_down:-4")
    else:
        parts.append(f"phase_{phase}:0")

    cam_context = "NONE"
    h3 = cam.get("h3")
    h4 = cam.get("h4")
    l3 = cam.get("l3")
    l4 = cam.get("l4")

    if decision == "BUY":
        if near(mid, l3, cam_tol):
            score += 1
            cam_context = "BUY_L3_REBOND"
            parts.append("cam_l3:+1")
        elif h4 is not None and mid > h4 and phase == "TREND_UP":
            score += 1
            cam_context = "BUY_H4_BREAKOUT"
            parts.append("cam_h4_breakout:+1")
        elif near(mid, h3, cam_tol) or near(mid, h4, cam_tol):
            score -= 1
            cam_context = "BUY_ZONE_HAUTE_DANGER"
            parts.append("cam_haute:-1")
        elif l4 is not None and mid < l4:
            score -= 1
            cam_context = "BUY_SOUS_L4_DANGER"
            parts.append("cam_sous_l4:-1")

    if decision == "SELL":
        if near(mid, h3, cam_tol):
            score += 1
            cam_context = "SELL_H3_REJET"
            parts.append("cam_h3:+1")
        elif l4 is not None and mid < l4 and phase == "TREND_DOWN":
            score += 1
            cam_context = "SELL_L4_BREAKOUT"
            parts.append("cam_l4_breakout:+1")
        elif near(mid, l3, cam_tol) or near(mid, l4, cam_tol):
            score -= 1
            cam_context = "SELL_ZONE_BASSE_DANGER"
            parts.append("cam_basse:-1")
        elif h4 is not None and mid > h4:
            score -= 1
            cam_context = "SELL_AU_DESSUS_H4_DANGER"
            parts.append("cam_haut_h4:-1")

    return {
        "score": int(score),
        "ok": (not phase_veto) and score >= int(getattr(CFG, "MIN_CONTEXT_SCORE_ENTRY", 3)),
        "phase_veto": phase_veto,
        "summary": "; ".join(parts),
        "vwap": vwap,
        "vwap_bias": vwap_bias,
        "phase": phase,
        "camarilla_context": cam_context,
        "camarilla": cam,
    }
