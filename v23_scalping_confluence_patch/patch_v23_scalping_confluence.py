#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch BOT-PIVOT V23 — Scalping Confluence Demo.
À lancer depuis /home/philippe_vacher06/bot-pivot/live via install_v23_scalping_confluence.sh.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
STAMP = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

REQUIRED = [
    "BOT_PIVOT_00_config.py",
    "BOT_PIVOT_00B_pnl_eur.py",
    "BOT_PIVOT_04_signal_tick.py",
    "BOT_PIVOT_05_cycle_engine.py",
    "BOT_PIVOT_06G2_execution_secure.py",
]

for name in REQUIRED:
    if not (ROOT / name).exists():
        raise SystemExit(f"Fichier requis introuvable : {name}")


def backup(path: Path) -> None:
    dst = path.with_name(path.name + f".BAK_V23_{STAMP}")
    shutil.copy2(path, dst)
    print(f"Backup : {dst.name}")


for name in ["BOT_PIVOT_00_config.py", "BOT_PIVOT_04_signal_tick.py", "BOT_PIVOT_05_cycle_engine.py"]:
    backup(ROOT / name)

CONTEXT_MODULE = r'''# BOT_PIVOT_04B_context_score.py
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
        score -= 2
        parts.append("phase_up_contre:-2")
    elif phase == "TREND_DOWN" and decision == "BUY":
        score -= 2
        parts.append("phase_down_contre:-2")
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
        "ok": score >= int(getattr(CFG, "MIN_CONTEXT_SCORE_ENTRY", 3)),
        "summary": "; ".join(parts),
        "vwap": vwap,
        "vwap_bias": vwap_bias,
        "phase": phase,
        "camarilla_context": cam_context,
        "camarilla": cam,
    }
'''

(ROOT / "BOT_PIVOT_04B_context_score.py").write_text(CONTEXT_MODULE, encoding="utf-8")
print("Créé : BOT_PIVOT_04B_context_score.py")

# -----------------------------------------------------------------------------
# Config patch
# -----------------------------------------------------------------------------
p = ROOT / "BOT_PIVOT_00_config.py"
s = p.read_text(encoding="utf-8")

s = re.sub(r"BASE_TP_EUR\s*=\s*[0-9.]+", "BASE_TP_EUR = 0.30", s)

tp_block = '''TP_EUR_BY_LEVEL = {
    1: 0.30,
    2: 0.60,
    3: 1.50,
    4: 3.00,
    5: 6.00,
}'''

if "TP_EUR_BY_LEVEL" in s:
    s = re.sub(r"TP_EUR_BY_LEVEL\s*=\s*\{.*?\}", tp_block, s, flags=re.S)
else:
    s += "\n\n# V23 — TP explicite par niveau\n" + tp_block + "\n"

constants = {
    "MIN_CONTEXT_SCORE_ENTRY": "3",
    "MIN_CONTEXT_SCORE_NEXT_LEVEL": "3",
    "MIN_CONTEXT_SCORE_KEEP": "2",
    "CLOSE_WEAK_CONTEXT_AFTER_SEC": "300",
}

for name, value in constants.items():
    if re.search(rf"^{name}\s*=", s, flags=re.M):
        s = re.sub(rf"^{name}\s*=.*$", f"{name} = {value}", s, flags=re.M)
    else:
        s += f"\n{name} = {value}\n"

sizes = {
    "US500": "0.15",
    "US100": "0.042",
    "US30": "0.024",
    "DE40": "0.051",
    "FR40": "0.15",
    "UK100": "0.12",
    "J225": "0.30",
    "EURUSD": "1500",
    "GBPUSD": "1200",
    "USDJPY": "1800",
    "EURJPY": "1800",
    "GOLD": "0.27",
    "SILVER": "15",
    "OIL_CRUDE": "12",
    "BTCUSD": "0.0018",
    "ETHUSD": "0.06",
}

missing = []
for asset, value in sizes.items():
    pattern = rf'("{asset}"\s*:\s*)[0-9]+(?:\.[0-9]+)?'
    s, n = re.subn(pattern, rf'\g<1>{value}', s, count=1)
    if n != 1:
        missing.append(asset)

if missing:
    raise SystemExit("Tailles non modifiées dans la config : " + ", ".join(missing))

s = re.sub(
    r"return\s+BASE_TP_EUR\s*\*\s*get_level_multiplier\(level\)",
    "return TP_EUR_BY_LEVEL.get(level, BASE_TP_EUR * get_level_multiplier(level))",
    s,
)

p.write_text(s, encoding="utf-8")
print("Patch config : TP par niveau + tailles x3 + seuils contexte")

# -----------------------------------------------------------------------------
# Module 04 patch
# -----------------------------------------------------------------------------
p = ROOT / "BOT_PIVOT_04_signal_tick.py"
s = p.read_text(encoding="utf-8")

if "import BOT_PIVOT_04B_context_score as CTX" not in s:
    s = s.replace(
        "import BOT_PIVOT_00_config as CFG",
        "import BOT_PIVOT_00_config as CFG\nimport BOT_PIVOT_04B_context_score as CTX",
    )

needle = '''    return {
        "asset": asset,
        "decision": decision,'''

replacement = '''    context = CTX.score_signal(
        asset=asset,
        decision=decision,
        ticks_all=ticks_all,
        ticks_recent=ticks_recent,
        mid=mid,
        chosen_zone=chosen_zone,
        range_position=range_pos,
        micro_rebound=buy_rebound,
        micro_reject=sell_reject,
    )

    return {
        "asset": asset,
        "decision": decision,'''

if needle not in s:
    raise SystemExit("Module 04 : point d'insertion contexte introuvable")

s = s.replace(needle, replacement, 1)

needle = '''        "chosen_zone": chosen_zone,
    }'''

replacement = '''        "chosen_zone": chosen_zone,
        "context_score": context.get("score", 0),
        "context_ok": context.get("ok", False),
        "context_summary": context.get("summary", ""),
        "vwap": context.get("vwap"),
        "vwap_bias": context.get("vwap_bias", "UNKNOWN"),
        "phase": context.get("phase", "UNKNOWN"),
        "camarilla_context": context.get("camarilla_context", "NONE"),
        "camarilla": context.get("camarilla", {}),
    }'''

idx = s.rfind(needle)
if idx == -1:
    raise SystemExit("Module 04 : bloc retour final introuvable")
s = s[:idx] + replacement + s[idx + len(needle):]

s = s.replace(
    '        "ACTIF      | DECISION | MID          | R.Pos | R.Width     | Spread   | Med      | SprOK | Age   | Zone | Micro BUY | Micro SELL | Raison"',
    '        "ACTIF      | DECISION | SCORE | VWAP     | PHASE      | CAM                  | MID          | R.Pos | R.Width     | Spread   | Med      | SprOK | Age   | Zone | Micro BUY | Micro SELL | Raison"',
)

s = s.replace(
    '''            f"{s.get('asset','?'):10s} | "
            f"{s.get('decision','?'):8s} | "
            f"{fmt(s.get('mid'), 6):12s} | "''',
    '''            f"{s.get('asset','?'):10s} | "
            f"{s.get('decision','?'):8s} | "
            f"{fmt(s.get('context_score'), 0):>5s} | "
            f"{str(s.get('vwap_bias','--'))[:8]:8s} | "
            f"{str(s.get('phase','--'))[:10]:10s} | "
            f"{str(s.get('camarilla_context','--'))[:20]:20s} | "
            f"{fmt(s.get('mid'), 6):12s} | "''',
)

p.write_text(s, encoding="utf-8")
print("Patch module 04 : score contexte ajouté")

# -----------------------------------------------------------------------------
# Module 05 patch
# -----------------------------------------------------------------------------
p = ROOT / "BOT_PIVOT_05_cycle_engine.py"
s = p.read_text(encoding="utf-8")

anchor = 'NEXT_LEVEL_MIN_LOSS_EUR = float(getattr(CFG, "NEXT_LEVEL_MIN_LOSS_EUR", 0.10))'
insert = '''NEXT_LEVEL_MIN_LOSS_EUR = float(getattr(CFG, "NEXT_LEVEL_MIN_LOSS_EUR", 0.10))
MIN_CONTEXT_SCORE_ENTRY = int(getattr(CFG, "MIN_CONTEXT_SCORE_ENTRY", 3))
MIN_CONTEXT_SCORE_NEXT_LEVEL = int(getattr(CFG, "MIN_CONTEXT_SCORE_NEXT_LEVEL", 3))
MIN_CONTEXT_SCORE_KEEP = int(getattr(CFG, "MIN_CONTEXT_SCORE_KEEP", 2))
CLOSE_WEAK_CONTEXT_AFTER_SEC = float(getattr(CFG, "CLOSE_WEAK_CONTEXT_AFTER_SEC", 300))
TP_EUR_BY_LEVEL = getattr(CFG, "TP_EUR_BY_LEVEL", {})'''

if "MIN_CONTEXT_SCORE_ENTRY" not in s:
    if anchor not in s:
        raise SystemExit("Module 05 : point insertion constantes contexte introuvable")
    s = s.replace(anchor, insert, 1)

old_tp = '''def tp_for(level, coeff=1.0):
    return float(BASE_TP_EUR * level_multiplier(level) * coeff)'''

new_tp = '''def tp_for(level, coeff=1.0):
    level = int(level)
    if isinstance(TP_EUR_BY_LEVEL, dict) and level in TP_EUR_BY_LEVEL:
        return float(TP_EUR_BY_LEVEL[level])
    return float(BASE_TP_EUR * level_multiplier(level))'''

if old_tp not in s:
    raise SystemExit("Module 05 : fonction tp_for ancienne introuvable")
s = s.replace(old_tp, new_tp, 1)

marker = '''def signal_reason(sig):
    return str(val(sig, ["reason", "raison", "why"], ""))'''

helpers = '''def signal_reason(sig):
    return str(val(sig, ["reason", "raison", "why"], ""))


def signal_context_score(sig):
    x = val(sig, ["context_score", "score_confluence", "score"], 0)
    try:
        return float(x)
    except Exception:
        return 0.0


def signal_context_summary(sig):
    return str(val(sig, ["context_summary", "context", "score_reason"], ""))


def signal_context_phase(sig):
    return str(val(sig, ["phase"], "UNKNOWN"))


def signal_context_vwap(sig):
    return str(val(sig, ["vwap_bias"], "UNKNOWN"))'''

if "def signal_context_score" not in s:
    if marker not in s:
        raise SystemExit("Module 05 : point insertion helpers contexte introuvable")
    s = s.replace(marker, helpers, 1)

old_open = '''                c = new_cycle(asset, decision, current_price, level=1)
                set_position(state, asset, c, "OPEN_L1")'''

new_open = '''                ctx_score = signal_context_score(sig)
                ctx_summary = signal_context_summary(sig)

                if ctx_score < MIN_CONTEXT_SCORE_ENTRY:
                    print(
                        f"{asset:10s} | IDLE_CONTEXT_WEAK | "
                        f"signal {decision} ignoré | "
                        f"score={ctx_score:.0f}<{MIN_CONTEXT_SCORE_ENTRY} | "
                        f"{ctx_summary}"
                    )
                    set_idle(state, asset, "IDLE_CONTEXT_WEAK")
                    continue

                c = new_cycle(asset, decision, current_price, level=1)
                set_position(state, asset, c, "OPEN_L1")'''

if old_open not in s:
    raise SystemExit("Module 05 : bloc ouverture L1 introuvable")
s = s.replace(old_open, new_open, 1)

start = s.find("        if age >= MAX_LIFE_SEC:")
end = s.find("        # 6. Maintien normal", start)
if start == -1 or end == -1:
    raise SystemExit("Module 05 : bloc timeout / NEXT_LEVEL introuvable")

new_block = '''        if age >= MAX_LIFE_SEC:
            ctx_score = signal_context_score(sig)
            ctx_summary = signal_context_summary(sig)
            same_direction_signal = decision == direction

            if pnl >= 0:
                if age >= CLOSE_WEAK_CONTEXT_AFTER_SEC and ctx_score < MIN_CONTEXT_SCORE_KEEP:
                    print(
                        f"{asset:10s} | CLOSE_TIME_POSITIVE | "
                        f"L{level} | {direction:4s} | "
                        f"pnl={pnl:.4f} | score={ctx_score:.0f}<{MIN_CONTEXT_SCORE_KEEP} | "
                        f"age={age:.1f}s | sortie scalp temps/contexte"
                    )
                    set_idle(state, asset, "CLOSE_TIME_POSITIVE")
                    continue

                print(
                    f"{asset:10s} | HOLD_POSITIVE | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f} | "
                    f"tp={tp:.4f} | "
                    f"score={ctx_score:.0f} | "
                    f"age={age:.1f}s | pas de renforcement"
                )
                continue

            if pnl > -NEXT_LEVEL_MIN_LOSS_EUR:
                if age >= CLOSE_WEAK_CONTEXT_AFTER_SEC and ctx_score < MIN_CONTEXT_SCORE_KEEP:
                    print(
                        f"{asset:10s} | CLOSE_SMALL_LOSS_TIMEOUT | "
                        f"L{level} | {direction:4s} | "
                        f"pnl={pnl:.4f} | score={ctx_score:.0f}<{MIN_CONTEXT_SCORE_KEEP} | "
                        f"age={age:.1f}s | petite perte + contexte faible"
                    )
                    set_idle(state, asset, "CLOSE_SMALL_LOSS_TIMEOUT")
                    continue

                print(
                    f"{asset:10s} | HOLD_SMALL_LOSS | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f} | "
                    f"seuil_next=-{NEXT_LEVEL_MIN_LOSS_EUR:.4f} | "
                    f"score={ctx_score:.0f} | "
                    f"age={age:.1f}s | perte trop faible"
                )
                continue

            if (not same_direction_signal) or ctx_score < MIN_CONTEXT_SCORE_NEXT_LEVEL:
                if age >= CLOSE_WEAK_CONTEXT_AFTER_SEC:
                    print(
                        f"{asset:10s} | CLOSE_CONTEXT_WEAK_TIMEOUT | "
                        f"L{level} | {direction:4s} | "
                        f"pnl={pnl:.4f} | score={ctx_score:.0f}<{MIN_CONTEXT_SCORE_NEXT_LEVEL} | "
                        f"signal={decision} | age={age:.1f}s | pas de renforcement, sortie scalp"
                    )
                    set_idle(state, asset, "CLOSE_CONTEXT_WEAK_TIMEOUT")
                    continue

                print(
                    f"{asset:10s} | HOLD_CONTEXT_WEAK | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f} | score={ctx_score:.0f}<{MIN_CONTEXT_SCORE_NEXT_LEVEL} | "
                    f"signal={decision} | age={age:.1f}s | {ctx_summary}"
                )
                continue

            next_level = level + 1

            if next_level > MAX_LEVEL:
                print(
                    f"{asset:10s} | HOLD_MAX     | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f}"
                )
                continue

            coeff = drift_coeff(direction, entry, current_price)
            c = new_cycle(
                asset,
                direction,
                current_price,
                level=next_level,
                coeff=coeff,
                cycle_id=cycle.get("cycle_id"),
            )
            set_position(state, asset, c, "NEXT_LEVEL")

            print(
                f"{asset:10s} | NEXT_LEVEL   | "
                f"L{level}->L{next_level} | "
                f"{direction:4s} | "
                f"pnl={pnl:.4f} | "
                f"seuil_next=-{NEXT_LEVEL_MIN_LOSS_EUR:.4f} | "
                f"score={ctx_score:.0f} | "
                f"coeff={coeff:.3f} | "
                f"size={float(c['size']):.6f} | "
                f"tp={float(c['tp_eur']):.4f}"
            )
            continue

'''

s = s[:start] + new_block + s[end:]

p.write_text(s, encoding="utf-8")
print("Patch module 05 : entrée/renforcement scorés + sortie contexte faible")

print("Patch V23 terminé.")
