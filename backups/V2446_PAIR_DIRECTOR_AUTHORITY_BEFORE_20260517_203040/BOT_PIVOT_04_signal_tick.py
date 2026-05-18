# BOT_PIVOT_04_signal_tick.py
# Module 04 — Signal tick
#
# Rôle :
# - lire les ticks JSONL produits par BOT_PIVOT_03_tick_stream.py
# - charger les zones produites par BOT_PIVOT_02_zones.py
# - calculer RangePositionTick sur les ticks récents
# - détecter zone support/résistance
# - détecter micro-rebond / micro-rejet
# - appliquer filtre spread appris
# - produire un signal théorique : BUY / SELL / WAIT
#
# Ce module ne trade pas.

import argparse
import glob
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import BOT_PIVOT_00_config as CFG
import BOT_PIVOT_04B_context_score as CTX


def parse_assets(raw: str) -> List[str]:
    if not raw or str(raw).strip().upper() == "ALL":
        return list(CFG.ASSETS)

    return [
        item.strip().upper()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    ]


def parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None

    text = str(value).replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def latest_tick_file() -> Optional[Path]:
    files = sorted(glob.glob(str(CFG.TICKS_DIR / "ticks_*.jsonl")))

    if not files:
        return None

    return Path(files[-1])


def load_ticks(path: Path, assets: List[str], max_lines: int = 50000) -> Dict[str, List[Dict[str, Any]]]:
    data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    if not path.exists():
        return data

    lines = path.read_text(encoding="utf-8").splitlines()

    if len(lines) > max_lines:
        lines = lines[-max_lines:]

    allowed = set(assets)

    for line in lines:
        if not line.strip():
            continue

        try:
            tick = json.loads(line)
        except Exception:
            continue

        epic = tick.get("epic")

        if epic not in allowed:
            continue

        if tick.get("mid") is None or tick.get("spread") is None:
            continue

        dt = parse_dt(tick.get("received_utc", ""))

        if dt is None:
            continue

        tick["_dt"] = dt

        try:
            tick["mid"] = float(tick["mid"])
            tick["bid"] = float(tick["bid"])
            tick["ask"] = float(tick["ask"])
            tick["spread"] = float(tick["spread"])
        except Exception:
            continue

        data[epic].append(tick)

    for epic in data:
        data[epic].sort(key=lambda t: t["_dt"])

    return data


def load_zones(asset: str) -> List[Dict[str, Any]]:
    path = CFG.ZONES_DIR / f"zones_{asset}.json"

    if not path.exists():
        return []

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    zones = payload.get("zones", [])

    clean = []

    for z in zones:
        if z.get("low") is None or z.get("high") is None:
            continue

        try:
            z["low"] = float(z["low"])
            z["high"] = float(z["high"])
            z["center"] = float(z.get("center", (z["low"] + z["high"]) / 2))
            z["score"] = float(z.get("score", 0))
        except Exception:
            continue

        clean.append(z)

    return clean


def recent_ticks(ticks: List[Dict[str, Any]], lookback_minutes: float) -> List[Dict[str, Any]]:
    if not ticks:
        return []

    last_dt = ticks[-1]["_dt"]
    cutoff = last_dt.timestamp() - lookback_minutes * 60

    return [t for t in ticks if t["_dt"].timestamp() >= cutoff]


def range_position_tick(ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
    mids = [t["mid"] for t in ticks]

    if not mids:
        return {
            "ok": False,
            "low": None,
            "high": None,
            "current": None,
            "range_position": None,
            "range_width": None,
        }

    low = min(mids)
    high = max(mids)
    current = mids[-1]
    width = high - low

    if width <= 0:
        pos = 50.0
    else:
        pos = (current - low) / width * 100.0

    return {
        "ok": True,
        "low": low,
        "high": high,
        "current": current,
        "range_position": pos,
        "range_width": width,
    }


def median_spread(ticks: List[Dict[str, Any]]) -> Optional[float]:
    spreads = [t["spread"] for t in ticks if t.get("spread") is not None and t["spread"] >= 0]

    if not spreads:
        return None

    return statistics.median(spreads)


def spread_filter_ok(ticks: List[Dict[str, Any]], min_samples: int) -> Tuple[bool, Optional[float], str]:
    if not ticks:
        return False, None, "NO_TICKS"

    med = median_spread(ticks)
    current = ticks[-1]["spread"]

    if med is None:
        return False, None, "NO_MEDIAN"

    if len(ticks) < min_samples:
        return False, med, f"LEARNING_{len(ticks)}/{min_samples}"

    max_mult = float(getattr(CFG, "SPREAD_MAX_MULTIPLIER", 2.5))

    if current <= med * max_mult:
        return True, med, "OK"

    return False, med, "SPREAD_TOO_HIGH"


def micro_rebound(ticks: List[Dict[str, Any]], min_ticks: int) -> bool:
    """
    BUY :
    - les derniers ticks doivent remonter
    - et le prix actuel doit être au-dessus du plus bas très récent
    """
    need = max(2, int(min_ticks))

    if len(ticks) < need + 2:
        return False

    mids = [t["mid"] for t in ticks]
    last = mids[-need:]

    rising = all(last[i] > last[i - 1] for i in range(1, len(last)))

    recent_low = min(mids[-(need + 3):])

    return rising and mids[-1] > recent_low


def micro_reject(ticks: List[Dict[str, Any]], min_ticks: int) -> bool:
    """
    SELL :
    - les derniers ticks doivent redescendre
    - et le prix actuel doit être sous le plus haut très récent
    """
    need = max(2, int(min_ticks))

    if len(ticks) < need + 2:
        return False

    mids = [t["mid"] for t in ticks]
    last = mids[-need:]

    falling = all(last[i] < last[i - 1] for i in range(1, len(last)))

    recent_high = max(mids[-(need + 3):])

    return falling and mids[-1] < recent_high


def find_touching_zones(mid: float, zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    touched = []

    for z in zones:
        if z["low"] <= mid <= z["high"]:
            touched.append(z)

    touched.sort(
        key=lambda z: (
            0 if "LOCAL+PSYCHO" in z.get("scope", "") else
            1 if "LOCAL" in z.get("scope", "") else
            2 if "PSYCHO" in z.get("scope", "") else
            3,
            -float(z.get("score", 0)),
        )
    )

    return touched


def build_signal_for_asset(
    asset: str,
    ticks_all: List[Dict[str, Any]],
    lookback_minutes: float,
    min_ticks: int,
    min_spread_samples: int,
) -> Dict[str, Any]:

    zones = load_zones(asset)

    ticks_recent = recent_ticks(ticks_all, lookback_minutes)

    if not ticks_recent:
        return {
            "asset": asset,
            "decision": "NO_TICKS",
            "reason": "aucun tick récent",
            "tick_count": 0,
        }

    last = ticks_recent[-1]
    mid = last["mid"]

    rpt = range_position_tick(ticks_recent)

    age_sec = (datetime.now(timezone.utc) - last["_dt"]).total_seconds()
    max_age_sec = float(getattr(CFG, "MAX_TICK_AGE_SEC", 5))

    spread_ok, spread_med, spread_reason = spread_filter_ok(ticks_recent, min_spread_samples)

    if age_sec > max_age_sec:
        return {
            "asset": asset,
            "decision": "WAIT",
            "reason": f"tick_trop_ancien_{age_sec:.1f}s>{max_age_sec:.1f}s",
            "tick_count": len(ticks_recent),
            "lookback_minutes": lookback_minutes,
            "age_sec": age_sec,
            "bid": last["bid"],
            "ask": last["ask"],
            "mid": mid,
            "spread": last["spread"],
            "spread_median": spread_med,
            "spread_ok": False,
            "range_low": rpt["low"],
            "range_high": rpt["high"],
            "range_width": rpt["range_width"],
            "range_position": rpt["range_position"],
            "micro_rebound": False,
            "micro_reject": False,
            "zones_touched": 0,
            "chosen_zone": None,
        }

    touched = find_touching_zones(mid, zones)

    support_zone = None
    resistance_zone = None
    active_zone = None

    for z in touched:
        z_type = z.get("type")

        if z_type == "active" and active_zone is None:
            active_zone = z

        if z_type == "support" and support_zone is None:
            support_zone = z

        if z_type == "resistance" and resistance_zone is None:
            resistance_zone = z

    buy_rebound = micro_rebound(ticks_recent, min_ticks)
    sell_reject = micro_reject(ticks_recent, min_ticks)

    range_pos = rpt["range_position"]

    buy_zone = support_zone or active_zone
    sell_zone = resistance_zone or active_zone

    buy_ready = (
        spread_ok
        and buy_zone is not None
        and range_pos is not None
        and range_pos <= float(getattr(CFG, "RANGE_BUY_THRESHOLD", 20.0))
        and buy_rebound
    )

    sell_ready = (
        spread_ok
        and sell_zone is not None
        and range_pos is not None
        and range_pos >= float(getattr(CFG, "RANGE_SELL_THRESHOLD", 80.0))
        and sell_reject
    )

    if buy_ready:
        decision = "BUY"
        chosen_zone = buy_zone
        reason = "support/active + RangePosition bas + micro-rebond + spread OK"

    elif sell_ready:
        decision = "SELL"
        chosen_zone = sell_zone
        reason = "résistance/active + RangePosition haut + micro-rejet + spread OK"

    else:
        decision = "WAIT"
        chosen_zone = touched[0] if touched else None

        blockers = []

        if not spread_ok:
            blockers.append(f"spread={spread_reason}")

        if not touched:
            blockers.append("hors_zone")

        if range_pos is not None:
            if buy_zone is not None and range_pos > float(getattr(CFG, "RANGE_BUY_THRESHOLD", 20.0)):
                blockers.append("range_pas_assez_bas")
            if sell_zone is not None and range_pos < float(getattr(CFG, "RANGE_SELL_THRESHOLD", 80.0)):
                blockers.append("range_pas_assez_haut")

        if buy_zone is not None and not buy_rebound:
            blockers.append("pas_micro_rebond")

        if sell_zone is not None and not sell_reject:
            blockers.append("pas_micro_rejet")

        reason = ", ".join(blockers) if blockers else "conditions non réunies"

    context = CTX.score_signal(
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
        "decision": decision,
        "reason": reason,
        "tick_count": len(ticks_recent),
        "lookback_minutes": lookback_minutes,
        "age_sec": age_sec,
        "bid": last["bid"],
        "ask": last["ask"],
        "mid": mid,
        "spread": last["spread"],
        "spread_median": spread_med,
        "spread_ok": spread_ok,
        "range_low": rpt["low"],
        "range_high": rpt["high"],
        "range_width": rpt["range_width"],
        "range_position": range_pos,
        "micro_rebound": buy_rebound,
        "micro_reject": sell_reject,
        "zones_touched": len(touched),
        "chosen_zone": chosen_zone,
        "context_score": context.get("score", 0),
        "context_ok": context.get("ok", False),
        "context_summary": context.get("summary", ""),
        "vwap": context.get("vwap"),
        "vwap_bias": context.get("vwap_bias", "UNKNOWN"),
        "phase": context.get("phase", "UNKNOWN"),
        "camarilla_context": context.get("camarilla_context", "NONE"),
        "camarilla": context.get("camarilla", {}),
    }


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "--"

    if isinstance(value, float):
        return f"{value:.{digits}f}"

    return str(value)


def print_signals(signals: List[Dict[str, Any]]) -> None:
    print()
    print("=" * 170)
    print("SIGNAL TICK — Module 04")
    print("=" * 170)
    print(
        "ACTIF      | DECISION | SCORE | VWAP     | PHASE      | CAM                  | MID          | R.Pos | R.Width     | Spread   | Med      | SprOK | Age   | Zone | Micro BUY | Micro SELL | Raison"
    )
    print("-" * 170)

    for s in signals:
        zone = s.get("chosen_zone")
        zone_txt = "--"

        if zone:
            zone_txt = f"{zone.get('scope','?')}:{zone.get('type','?')}"

            if zone.get("psycho_level") is not None:
                zone_txt += f":{zone.get('psycho_level')}"

        print(
            f"{s.get('asset','?'):10s} | "
            f"{s.get('decision','?'):8s} | "
            f"{fmt(s.get('context_score'), 0):>5s} | "
            f"{str(s.get('vwap_bias','--'))[:8]:8s} | "
            f"{str(s.get('phase','--'))[:10]:10s} | "
            f"{str(s.get('camarilla_context','--'))[:20]:20s} | "
            f"{fmt(s.get('mid'), 6):12s} | "
            f"{fmt(s.get('range_position'), 1):5s} | "
            f"{fmt(s.get('range_width'), 6):11s} | "
            f"{fmt(s.get('spread'), 6):8s} | "
            f"{fmt(s.get('spread_median'), 6):8s} | "
            f"{str(s.get('spread_ok')):5s} | "
            f"{fmt(s.get('age_sec'), 1):5s} | "
            f"{zone_txt[:24]:24s} | "
            f"{str(s.get('micro_rebound')):9s} | "
            f"{str(s.get('micro_reject')):10s} | "
            f"{s.get('reason','')}"
        )

    print("=" * 170)


def save_snapshot(signals: List[Dict[str, Any]]) -> Path:
    out = {
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "signals": signals,
    }

    path = CFG.TICKS_DIR / "signals_latest.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="BOT_PIVOT_04 — Signal tick")

    parser.add_argument(
        "--assets",
        default=",".join(CFG.ASSETS),
        help="Liste d'actifs séparés par virgule",
    )

    parser.add_argument(
        "--tick-file",
        default="",
        help="Fichier ticks JSONL. Vide = dernier fichier data/ticks/ticks_*.jsonl",
    )

    parser.add_argument(
        "--lookback-minutes",
        type=float,
        default=float(getattr(CFG, "RANGE_LOOKBACK_MINUTES", 14)),
        help="Fenêtre RangePositionTick en minutes",
    )

    parser.add_argument(
        "--min-ticks",
        type=int,
        default=int(getattr(CFG, "MICRO_REVERSAL_MIN_TICKS", 2)),
        help="Nombre de ticks pour micro-rebond/rejet",
    )

    parser.add_argument(
        "--min-spread-samples",
        type=int,
        default=20,
        help="Minimum de ticks récents pour valider le spread en test",
    )

    args = parser.parse_args()
    assets = parse_assets(args.assets)

    tick_path = Path(args.tick_file) if args.tick_file else latest_tick_file()

    if not tick_path:
        raise RuntimeError("Aucun fichier ticks trouvé dans data/ticks/.")

    data = load_ticks(tick_path, assets)

    signals = []

    for asset in assets:
        signals.append(
            build_signal_for_asset(
                asset=asset,
                ticks_all=data.get(asset, []),
                lookback_minutes=args.lookback_minutes,
                min_ticks=args.min_ticks,
                min_spread_samples=args.min_spread_samples,
            )
        )

    print(f"Fichier ticks utilisé : {tick_path}")
    print_signals(signals)

    out_path = save_snapshot(signals)
    print(f"Snapshot signaux : {out_path}")


if __name__ == "__main__":
    main()
