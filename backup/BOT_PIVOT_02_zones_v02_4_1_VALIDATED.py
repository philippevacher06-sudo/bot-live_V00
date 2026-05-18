# BOT_PIVOT_02_zones.py
# Module 02.4 — Zones GLOBAL + LOCAL + PSYCHO + CONFLUENCE
# Stratégie : Zones + RangePositionTick + Cycle séquentiel 5 niveaux
#
# Objectif :
# - Garder les zones MAJOR 30 jours.
# - Ajouter les zones LOCAL 3 jours pour le scalping.
# - Ajouter les prix psychologiques : 7400, 7450, 10000, etc.
# - Détecter les confluences LOCAL/MAJOR + PSYCHO.
# - Éviter les zones qui se marchent dessus.
#
# Ce module ne trade pas.
# Il ne lance aucun ordre.
# Il prépare seulement data/zones/zones_ACTIF.json.

import argparse
import glob
import json
import logging
import math
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import BOT_PIVOT_00_config as CFG


# ============================================================
# RÉGLAGES v02.4
# ============================================================

ATR_PERIOD = 96
LOCAL_DAYS = 3

# Profil de prix / TPO simplifié
SMOOTH_RADIUS = 2
BUCKET_ATR_DIVISOR = 10.0
MIN_BUCKETS = 400
MAX_BUCKETS = 2500

# Détection de pics
PEAK_MIN_RATIO_OF_MAX = 0.15
PEAK_MIN_RADIUS = 3
VALLEY_RATIO = 0.55

# Zones naturelles avec garde-fous ATR
ZONE_MIN_ATR = 0.60
ZONE_MAX_ATR = 2.30
CENTER_MIN_DISTANCE_ATR = 0.95

# Zones locales : priorité scalping
LOCAL_NEAR_DISTANCE_ATR = 10.0
LOCAL_SUPPORTS = 4
LOCAL_RESISTANCES = 4
LOCAL_ACTIVE = 2

# Zones majeures : contexte
MAJOR_STRONG_ZONES = 4

# Prix psychologiques
PSYCHO_TARGET_ATR = 8.0
PSYCHO_SCAN_ATR = 25.0
PSYCHO_MINOR_WIDTH_ATR = 0.85
PSYCHO_MAJOR_WIDTH_ATR = 1.05
PSYCHO_BIG_WIDTH_ATR = 1.25
PSYCHO_MAX_STANDALONE = 6

# Score / sélection
DEFAULT_TOP = 14
OVERLAP_RATIO_LIMIT = 0.35


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("BOT_PIVOT_02_ZONES")


# ============================================================
# OUTILS
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_assets(raw: str) -> List[str]:
    return [
        item.strip().upper()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    ]


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0:
        return default
    return a / b


def parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None

    text = str(value).strip().replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        try:
            dt = datetime.fromisoformat(text[:19])
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


# ============================================================
# HISTORIQUE
# ============================================================

def find_history_file(asset: str, resolution: str, days: int) -> Optional[Path]:
    exact = CFG.HISTORY_DIR / f"{asset}_{resolution}_{days}d.json"

    if exact.exists():
        return exact

    pattern = str(CFG.HISTORY_DIR / f"{asset}_{resolution}_*d.json")
    matches = sorted(glob.glob(pattern))

    if matches:
        return Path(matches[-1])

    return None


def clean_candles(raw_candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []

    for c in raw_candles:
        if (
            c.get("high_mid") is not None
            and c.get("low_mid") is not None
            and c.get("close_mid") is not None
        ):
            cleaned.append(c)

    cleaned.sort(key=lambda c: str(c.get("snapshotTimeUTC") or c.get("snapshotTime") or ""))

    return cleaned


def load_history(asset: str, resolution: str, days: int) -> Tuple[Path, List[Dict[str, Any]], Dict[str, Any]]:
    path = find_history_file(asset, resolution, days)

    if not path:
        raise FileNotFoundError(
            f"Aucun fichier historique trouvé pour {asset} en {resolution}. "
            "Lance d'abord BOT_PIVOT_01_historical.py."
        )

    payload = load_json(path)
    candles = clean_candles(payload.get("candles", []))

    if len(candles) < 50:
        raise RuntimeError(
            f"{asset} : historique insuffisant ({len(candles)} bougies)."
        )

    return path, candles, payload


def local_candles_from_days(candles: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    if not candles:
        return []

    last_dt = parse_time(candles[-1].get("snapshotTimeUTC") or candles[-1].get("snapshotTime"))

    if last_dt is None:
        fallback_count = min(len(candles), max(80, days * 24 * 4))
        return candles[-fallback_count:]

    cutoff = last_dt - timedelta(days=days)

    recent = []
    for c in candles:
        dt = parse_time(c.get("snapshotTimeUTC") or c.get("snapshotTime"))
        if dt is not None and dt >= cutoff:
            recent.append(c)

    if len(recent) >= 50:
        return recent

    fallback_count = min(len(candles), max(80, days * 24 * 4))
    return candles[-fallback_count:]


# ============================================================
# ATR
# ============================================================

def candle_low_high_close(candle: Dict[str, Any]) -> Tuple[float, float, float]:
    low = float(candle["low_mid"])
    high = float(candle["high_mid"])
    close = float(candle["close_mid"])

    if low > high:
        low, high = high, low

    return low, high, close


def true_ranges(candles: List[Dict[str, Any]]) -> List[float]:
    ranges: List[float] = []
    previous_close: Optional[float] = None

    for candle in candles:
        low, high, close = candle_low_high_close(candle)

        if previous_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )

        if tr > 0:
            ranges.append(tr)

        previous_close = close

    return ranges


def calculate_atr(candles: List[Dict[str, Any]], period: int = ATR_PERIOD) -> float:
    trs = true_ranges(candles)

    if not trs:
        return 0.0

    recent = trs[-period:] if len(trs) >= period else trs
    atr = sum(recent) / len(recent)
    med = statistics.median(recent)

    if med > 0:
        atr = min(atr, med * 2.5)
        atr = max(atr, med * 0.4)

    return atr


# ============================================================
# PROFIL DE PRIX
# ============================================================

def smooth_counts(counts: List[int], radius: int) -> List[float]:
    if radius <= 0:
        return [float(c) for c in counts]

    out: List[float] = []

    for i in range(len(counts)):
        left = max(0, i - radius)
        right = min(len(counts), i + radius + 1)
        window = counts[left:right]
        out.append(sum(window) / len(window))

    return out


def build_profile(candles: List[Dict[str, Any]], atr: float) -> Dict[str, Any]:
    lows = []
    highs = []

    for c in candles:
        low, high, _ = candle_low_high_close(c)
        lows.append(low)
        highs.append(high)

    price_min = min(lows)
    price_max = max(highs)

    if price_max <= price_min:
        raise RuntimeError("Plage de prix invalide.")

    price_range = price_max - price_min

    if atr > 0:
        raw_bucket_width = atr / BUCKET_ATR_DIVISOR
        bucket_count = int(price_range / raw_bucket_width)
        bucket_count = max(MIN_BUCKETS, min(MAX_BUCKETS, bucket_count))
    else:
        bucket_count = int(getattr(CFG, "PRICE_BUCKETS", 500))
        bucket_count = max(MIN_BUCKETS, min(MAX_BUCKETS, bucket_count))

    bucket_width = price_range / bucket_count
    counts = [0 for _ in range(bucket_count)]

    for c in candles:
        low, high, _ = candle_low_high_close(c)

        start_idx = int((low - price_min) / bucket_width)
        end_idx = int((high - price_min) / bucket_width)

        start_idx = max(0, min(bucket_count - 1, start_idx))
        end_idx = max(0, min(bucket_count - 1, end_idx))

        for idx in range(start_idx, end_idx + 1):
            counts[idx] += 1

    return {
        "price_min": price_min,
        "price_max": price_max,
        "price_range": price_range,
        "bucket_count": bucket_count,
        "bucket_width": bucket_width,
        "counts": counts,
        "smoothed_counts": smooth_counts(counts, SMOOTH_RADIUS),
    }


def price_at(price_min: float, bucket_width: float, idx: int) -> float:
    return price_min + idx * bucket_width


def bucket_center(price_min: float, bucket_width: float, idx: int) -> float:
    return price_min + (idx + 0.5) * bucket_width


# ============================================================
# DÉTECTION PROFIL
# ============================================================

def is_local_peak(values: List[float], idx: int, radius: int) -> bool:
    current = values[idx]
    left = max(0, idx - radius)
    right = min(len(values) - 1, idx + radius)

    for j in range(left, right + 1):
        if j == idx:
            continue
        if values[j] > current:
            return False

    return True


def find_left_valley(values: List[float], peak_idx: int, peak_value: float) -> int:
    limit = peak_value * VALLEY_RATIO
    best_idx = peak_idx
    best_value = peak_value

    i = peak_idx
    while i > 0:
        i -= 1

        if values[i] < best_value:
            best_value = values[i]
            best_idx = i

        if values[i] <= limit:
            return i

        if i < peak_idx - 1 and values[i] > values[i + 1] and best_idx != peak_idx:
            return best_idx

    return best_idx


def find_right_valley(values: List[float], peak_idx: int, peak_value: float) -> int:
    limit = peak_value * VALLEY_RATIO
    best_idx = peak_idx
    best_value = peak_value

    i = peak_idx
    while i < len(values) - 1:
        i += 1

        if values[i] < best_value:
            best_value = values[i]
            best_idx = i

        if values[i] <= limit:
            return i

        if i > peak_idx + 1 and values[i] > values[i - 1] and best_idx != peak_idx:
            return best_idx

    return best_idx


def classify_zone(low: float, high: float, last_close: float) -> str:
    if low <= last_close <= high:
        return "active"

    if high < last_close:
        return "support"

    return "resistance"


def normalize_zone_with_atr(
    low: float,
    high: float,
    center: float,
    atr: float,
    price_min: float,
    price_max: float,
) -> Tuple[float, float]:
    if atr <= 0:
        return low, high

    min_width = atr * ZONE_MIN_ATR
    max_width = atr * ZONE_MAX_ATR

    width = high - low

    if width < min_width:
        low = center - min_width / 2.0
        high = center + min_width / 2.0

    elif width > max_width:
        low = center - max_width / 2.0
        high = center + max_width / 2.0

    low = max(price_min, low)
    high = min(price_max, high)

    return low, high


def make_profile_zone(
    profile: Dict[str, Any],
    peak_idx: int,
    atr: float,
    last_close: float,
    scope: str,
) -> Dict[str, Any]:
    price_min = profile["price_min"]
    price_max = profile["price_max"]
    bucket_width = profile["bucket_width"]
    raw_counts = profile["counts"]
    smoothed = profile["smoothed_counts"]

    peak_value = smoothed[peak_idx]
    left_idx = find_left_valley(smoothed, peak_idx, peak_value)
    right_idx = find_right_valley(smoothed, peak_idx, peak_value)

    low = price_at(price_min, bucket_width, left_idx)
    high = price_at(price_min, bucket_width, right_idx + 1)
    center = bucket_center(price_min, bucket_width, peak_idx)

    low, high = normalize_zone_with_atr(
        low=low,
        high=high,
        center=center,
        atr=atr,
        price_min=price_min,
        price_max=price_max,
    )

    center = (low + high) / 2.0

    nucleus_left = max(0, peak_idx - PEAK_MIN_RADIUS)
    nucleus_right = min(len(raw_counts) - 1, peak_idx + PEAK_MIN_RADIUS)
    strength_sum = sum(raw_counts[nucleus_left:nucleus_right + 1])

    return {
        "scope": scope,
        "base_scope": scope,
        "type": classify_zone(low, high, last_close),
        "low": low,
        "high": high,
        "center": center,
        "width": high - low,
        "atr": atr,
        "width_atr": safe_div(high - low, atr, 0.0),
        "strength": int(strength_sum),
        "peak_count": int(raw_counts[peak_idx]),
        "peak_smoothed": round(float(peak_value), 4),
        "bucket_index": peak_idx,
        "distance_points_from_last_close": center - last_close,
        "distance_atr_from_last_close": safe_div(center - last_close, atr, 0.0),
        "distance_pct_from_last_close": safe_div(center - last_close, last_close, 0.0),
        "confluence": False,
        "psycho_level": None,
        "psycho_rank": None,
        "psycho_step": None,
        "score": 0.0,
    }


def build_profile_candidates(profile: Dict[str, Any], atr: float, last_close: float, scope: str) -> List[Dict[str, Any]]:
    smoothed = profile["smoothed_counts"]
    raw_counts = profile["counts"]

    if not smoothed:
        return []

    max_smoothed = max(smoothed)

    if max_smoothed <= 0:
        return []

    min_peak = max(3.0, max_smoothed * PEAK_MIN_RATIO_OF_MAX)
    candidates: List[Dict[str, Any]] = []

    for idx, value in enumerate(smoothed):
        if value < min_peak:
            continue

        if not is_local_peak(smoothed, idx, PEAK_MIN_RADIUS):
            continue

        candidates.append(make_profile_zone(profile, idx, atr, last_close, scope))

    if len(candidates) < 8:
        ordered = sorted(range(len(raw_counts)), key=lambda i: raw_counts[i], reverse=True)

        for idx in ordered[:100]:
            if raw_counts[idx] <= 0:
                continue

            zone = make_profile_zone(profile, idx, atr, last_close, scope)

            if not any(abs(zone["center"] - z["center"]) <= atr * CENTER_MIN_DISTANCE_ATR for z in candidates):
                candidates.append(zone)

            if len(candidates) >= 30:
                break

    return candidates


# ============================================================
# PRIX PSYCHOLOGIQUES
# ============================================================

def nice_step(value: float) -> float:
    if value <= 0:
        return 1.0

    exp = math.floor(math.log10(value))
    candidates = []

    for e in range(exp - 3, exp + 4):
        for m in [1, 2, 5, 10]:
            candidates.append(m * (10 ** e))

    candidates = sorted(set(c for c in candidates if c > 0))
    return min(candidates, key=lambda c: abs(c - value))


def is_multiple_of_step(level: float, step: float) -> bool:
    if step <= 0:
        return False

    ratio = level / step
    return abs(ratio - round(ratio)) < 1e-7


def psycho_steps_from_atr(atr: float) -> Dict[str, float]:
    target = max(atr * PSYCHO_TARGET_ATR, 1e-12)

    minor = nice_step(target)
    medium = nice_step(minor * 2.0)
    major = nice_step(minor * 5.0)

    if medium <= minor:
        medium = minor * 2.0

    if major <= medium:
        major = medium * 2.5

    return {
        "target": target,
        "minor": minor,
        "medium": medium,
        "major": major,
    }


def make_psycho_zone(level: float, atr: float, last_close: float, steps: Dict[str, float]) -> Dict[str, Any]:
    if is_multiple_of_step(level, steps["major"]):
        rank = "BIG"
        width = atr * PSYCHO_BIG_WIDTH_ATR
        rank_score = 900
        step = steps["major"]
    elif is_multiple_of_step(level, steps["medium"]):
        rank = "MAJOR"
        width = atr * PSYCHO_MAJOR_WIDTH_ATR
        rank_score = 650
        step = steps["medium"]
    else:
        rank = "MINOR"
        width = atr * PSYCHO_MINOR_WIDTH_ATR
        rank_score = 450
        step = steps["minor"]

    low = level - width / 2.0
    high = level + width / 2.0

    return {
        "scope": "PSYCHO",
        "base_scope": "PSYCHO",
        "type": classify_zone(low, high, last_close),
        "low": low,
        "high": high,
        "center": level,
        "width": width,
        "atr": atr,
        "width_atr": safe_div(width, atr, 0.0),
        "strength": rank_score,
        "peak_count": 0,
        "peak_smoothed": 0.0,
        "bucket_index": None,
        "distance_points_from_last_close": level - last_close,
        "distance_atr_from_last_close": safe_div(level - last_close, atr, 0.0),
        "distance_pct_from_last_close": safe_div(level - last_close, last_close, 0.0),
        "confluence": False,
        "psycho_level": level,
        "psycho_rank": rank,
        "psycho_step": step,
        "score": 0.0,
    }


def build_psycho_zones(last_close: float, atr: float) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    if atr <= 0 or last_close <= 0:
        return [], {"target": 0.0, "minor": 0.0, "medium": 0.0, "major": 0.0}

    steps = psycho_steps_from_atr(atr)
    minor = steps["minor"]

    scan = max(atr * PSYCHO_SCAN_ATR, minor * 3.0)

    start = math.floor((last_close - scan) / minor) * minor
    end = math.ceil((last_close + scan) / minor) * minor

    zones: List[Dict[str, Any]] = []
    level = start

    # Protection boucle flottante.
    max_iter = 500
    n = 0

    while level <= end + minor / 2.0 and n < max_iter:
        if level > 0:
            zones.append(make_psycho_zone(level, atr, last_close, steps))
        level += minor
        n += 1

    return zones, steps


# ============================================================
# CONFLUENCE / CHEVAUCHEMENT
# ============================================================

def intervals_overlap(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    left = max(a["low"], b["low"])
    right = min(a["high"], b["high"])

    overlap = max(0.0, right - left)
    smaller = max(1e-12, min(a["width"], b["width"]))

    return overlap / smaller


def close_or_overlap(a: Dict[str, Any], b: Dict[str, Any], atr: float) -> bool:
    if intervals_overlap(a, b) > 0:
        return True

    if atr > 0 and abs(a["center"] - b["center"]) <= atr * 0.65:
        return True

    return False


def apply_psycho_confluence(zones: List[Dict[str, Any]], psycho_zones: List[Dict[str, Any]], atr: float) -> None:
    for zone in zones:
        matches = [
            p for p in psycho_zones
            if close_or_overlap(zone, p, atr)
        ]

        if not matches:
            continue

        best = sorted(
            matches,
            key=lambda p: (
                0 if p["psycho_rank"] == "BIG" else 1 if p["psycho_rank"] == "MAJOR" else 2,
                abs(p["center"] - zone["center"]),
            )
        )[0]

        zone["confluence"] = True
        zone["psycho_level"] = best["psycho_level"]
        zone["psycho_rank"] = best["psycho_rank"]
        zone["psycho_step"] = best["psycho_step"]

        if "PSYCHO" not in zone["scope"]:
            zone["scope"] = f"{zone['base_scope']}+PSYCHO"


def zone_priority(zone: Dict[str, Any], last_close: float) -> float:
    distance_atr = abs(zone.get("distance_atr_from_last_close", 0.0))
    proximity = max(0.0, 300.0 - distance_atr * 25.0)

    scope = zone.get("scope", "")
    base = 0.0

    if "LOCAL" in scope:
        base += 1000.0

    if "PSYCHO" in scope:
        base += 650.0

    if "MAJOR" in scope and "LOCAL" not in scope:
        base += 350.0

    rank = zone.get("psycho_rank")

    if rank == "BIG":
        base += 450.0
    elif rank == "MAJOR":
        base += 300.0
    elif rank == "MINOR":
        base += 150.0

    strength = min(float(zone.get("strength", 0)), 1000.0) * 0.35

    return base + proximity + strength


def merge_zones(a: Dict[str, Any], b: Dict[str, Any], last_close: float, atr: float) -> Dict[str, Any]:
    total_strength = a["strength"] + b["strength"]

    if total_strength > 0:
        center = (
            a["center"] * a["strength"]
            + b["center"] * b["strength"]
        ) / total_strength
    else:
        center = (a["center"] + b["center"]) / 2.0

    low = min(a["low"], b["low"])
    high = max(a["high"], b["high"])

    if atr > 0 and high - low > atr * ZONE_MAX_ATR:
        low = center - (atr * ZONE_MAX_ATR) / 2.0
        high = center + (atr * ZONE_MAX_ATR) / 2.0

    scope_parts = []
    for item in [a["scope"], b["scope"]]:
        for part in item.split("+"):
            if part not in scope_parts:
                scope_parts.append(part)

    scope = "+".join(scope_parts)

    psycho_level = a.get("psycho_level") or b.get("psycho_level")
    psycho_rank = a.get("psycho_rank") or b.get("psycho_rank")
    psycho_step = a.get("psycho_step") or b.get("psycho_step")

    if a.get("psycho_rank") == "BIG" or b.get("psycho_rank") == "BIG":
        psycho_rank = "BIG"
    elif a.get("psycho_rank") == "MAJOR" or b.get("psycho_rank") == "MAJOR":
        psycho_rank = "MAJOR"

    return {
        "scope": scope,
        "base_scope": scope,
        "type": classify_zone(low, high, last_close),
        "low": low,
        "high": high,
        "center": center,
        "width": high - low,
        "atr": atr,
        "width_atr": safe_div(high - low, atr, 0.0),
        "strength": total_strength,
        "peak_count": max(a.get("peak_count") or 0, b.get("peak_count") or 0),
        "peak_smoothed": max(a.get("peak_smoothed") or 0, b.get("peak_smoothed") or 0),
        "bucket_index": a.get("bucket_index") if a["strength"] >= b["strength"] else b.get("bucket_index"),
        "distance_points_from_last_close": center - last_close,
        "distance_atr_from_last_close": safe_div(center - last_close, atr, 0.0),
        "distance_pct_from_last_close": safe_div(center - last_close, last_close, 0.0),
        "confluence": "PSYCHO" in scope,
        "psycho_level": psycho_level,
        "psycho_rank": psycho_rank,
        "psycho_step": psycho_step,
        "score": 0.0,
    }


def deduplicate(zones: List[Dict[str, Any]], last_close: float, atr: float) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []

    ordered = sorted(
        zones,
        key=lambda z: zone_priority(z, last_close),
        reverse=True,
    )

    for zone in ordered:
        merged = False

        for i, existing in enumerate(selected):
            same_type = zone["type"] == existing["type"] or "active" in [zone["type"], existing["type"]]
            center_close = atr > 0 and abs(zone["center"] - existing["center"]) < atr * CENTER_MIN_DISTANCE_ATR
            overlap_big = intervals_overlap(zone, existing) >= OVERLAP_RATIO_LIMIT

            if same_type and (center_close or overlap_big):
                selected[i] = merge_zones(existing, zone, last_close, atr)
                merged = True
                break

        if not merged:
            selected.append(zone)

    for z in selected:
        z["score"] = round(zone_priority(z, last_close), 4)

    return selected




def remove_duplicate_psycho_levels(zones: List[Dict[str, Any]], last_close: float) -> List[Dict[str, Any]]:
    """
    Nettoyage final :
    si plusieurs zones portent le même niveau psychologique,
    on garde uniquement la meilleure.
    Exemple : deux zones autour de 7350 -> on garde la plus pertinente.
    """
    kept_without_psycho: List[Dict[str, Any]] = []
    best_by_psycho: Dict[Tuple[float, str], Dict[str, Any]] = {}

    for zone in zones:
        level = zone.get("psycho_level")

        if level is None:
            kept_without_psycho.append(zone)
            continue

        try:
            key_level = round(float(level), 8)
        except Exception:
            kept_without_psycho.append(zone)
            continue

        key = (key_level, zone.get("type", ""))

        current = best_by_psycho.get(key)

        if current is None:
            best_by_psycho[key] = zone
            continue

        zone_score = zone_priority(zone, last_close)
        current_score = zone_priority(current, last_close)

        if zone_score > current_score:
            best_by_psycho[key] = zone

    return kept_without_psycho + list(best_by_psycho.values())


def select_final_zones(
    local_candidates: List[Dict[str, Any]],
    global_candidates: List[Dict[str, Any]],
    psycho_zones: List[Dict[str, Any]],
    last_close: float,
    atr_local: float,
    atr_global: float,
    top_n: int,
) -> List[Dict[str, Any]]:
    atr_ref = atr_local if atr_local > 0 else atr_global

    apply_psycho_confluence(local_candidates, psycho_zones, atr_ref)
    apply_psycho_confluence(global_candidates, psycho_zones, atr_ref)

    local_clean = deduplicate(local_candidates, last_close, atr_ref)
    global_clean = deduplicate(global_candidates, last_close, atr_global if atr_global > 0 else atr_ref)

    near_limit = atr_ref * LOCAL_NEAR_DISTANCE_ATR if atr_ref > 0 else abs(last_close) * 0.01

    local_active = [z for z in local_clean if z["type"] == "active"]
    local_supports = [
        z for z in local_clean
        if z["type"] == "support" and abs(z["center"] - last_close) <= near_limit
    ]
    local_resistances = [
        z for z in local_clean
        if z["type"] == "resistance" and abs(z["center"] - last_close) <= near_limit
    ]

    local_active = sorted(local_active, key=lambda z: zone_priority(z, last_close), reverse=True)[:LOCAL_ACTIVE]
    local_supports = sorted(local_supports, key=lambda z: abs(z["center"] - last_close))[:LOCAL_SUPPORTS]
    local_resistances = sorted(local_resistances, key=lambda z: abs(z["center"] - last_close))[:LOCAL_RESISTANCES]

    major = sorted(global_clean, key=lambda z: zone_priority(z, last_close), reverse=True)[:MAJOR_STRONG_ZONES]

    # PSYCHO standalone : utiles surtout au-dessus du prix si aucune résistance locale n'existe.
    psycho_near = [
        p for p in psycho_zones
        if abs(p["center"] - last_close) <= atr_ref * PSYCHO_SCAN_ATR
    ]
    psycho_near = sorted(psycho_near, key=lambda z: zone_priority(z, last_close), reverse=True)[:PSYCHO_MAX_STANDALONE]

    combined = local_active + local_supports + local_resistances + psycho_near + major
    final = deduplicate(combined, last_close, atr_ref)

    final = remove_duplicate_psycho_levels(final, last_close)
    final = sorted(final, key=lambda z: zone_priority(z, last_close), reverse=True)[:top_n]
    final = sorted(final, key=lambda z: z["center"])

    for idx, zone in enumerate(final, start=1):
        zone["rank_by_price"] = idx
        zone["low"] = round(zone["low"], 6)
        zone["high"] = round(zone["high"], 6)
        zone["center"] = round(zone["center"], 6)
        zone["width"] = round(zone["width"], 6)
        zone["atr"] = round(zone["atr"], 6)
        zone["width_atr"] = round(zone["width_atr"], 4)
        zone["distance_points_from_last_close"] = round(zone["distance_points_from_last_close"], 6)
        zone["distance_atr_from_last_close"] = round(zone["distance_atr_from_last_close"], 4)
        zone["distance_pct_from_last_close"] = round(zone["distance_pct_from_last_close"], 6)

        if isinstance(zone.get("psycho_level"), float):
            zone["psycho_level"] = round(zone["psycho_level"], 8)

        if isinstance(zone.get("psycho_step"), float):
            zone["psycho_step"] = round(zone["psycho_step"], 8)

    return final


# ============================================================
# CONSTRUCTION PAR ACTIF
# ============================================================

def build_zones_for_asset(asset: str, candles_30d: List[Dict[str, Any]], top_n: int) -> Dict[str, Any]:
    candles_local = local_candles_from_days(candles_30d, LOCAL_DAYS)

    last_close = float(candles_30d[-1]["close_mid"])

    atr_global = calculate_atr(candles_30d, ATR_PERIOD)
    atr_local = calculate_atr(candles_local, ATR_PERIOD)

    if atr_local <= 0:
        atr_local = atr_global

    profile_global = build_profile(candles_30d, atr_global)
    profile_local = build_profile(candles_local, atr_local)

    global_candidates = build_profile_candidates(profile_global, atr_global, last_close, "MAJOR")
    local_candidates = build_profile_candidates(profile_local, atr_local, last_close, "LOCAL")

    psycho_zones, psycho_steps = build_psycho_zones(last_close, atr_local if atr_local > 0 else atr_global)

    zones = select_final_zones(
        local_candidates=local_candidates,
        global_candidates=global_candidates,
        psycho_zones=psycho_zones,
        last_close=last_close,
        atr_local=atr_local,
        atr_global=atr_global,
        top_n=top_n,
    )

    supports = sum(1 for z in zones if z["type"] == "support")
    resistances = sum(1 for z in zones if z["type"] == "resistance")
    active = sum(1 for z in zones if z["type"] == "active")
    local_count = sum(1 for z in zones if "LOCAL" in z["scope"])
    major_count = sum(1 for z in zones if "MAJOR" in z["scope"])
    psycho_count = sum(1 for z in zones if "PSYCHO" in z["scope"])
    confluence_count = sum(1 for z in zones if z.get("confluence"))

    return {
        "asset": asset,
        "created_utc": utc_now_iso(),
        "source": "BOT_PIVOT_02_zones.py",
        "version": "02.4_global_local_psycho_confluence",
        "method": "global_30d_local_3d_tpo_atr_psychological_levels",
        "history_resolution": CFG.HISTORY_RESOLUTION,
        "history_days": CFG.HISTORY_DAYS,
        "local_days": LOCAL_DAYS,
        "candles_30d_count": len(candles_30d),
        "candles_local_count": len(candles_local),
        "last_close": round(last_close, 6),
        "atr_period": ATR_PERIOD,
        "atr_global_m15": round(atr_global, 6),
        "atr_local_m15": round(atr_local, 6),
        "psycho_steps": {
            "target": round(psycho_steps.get("target", 0.0), 8),
            "minor": round(psycho_steps.get("minor", 0.0), 8),
            "medium": round(psycho_steps.get("medium", 0.0), 8),
            "major": round(psycho_steps.get("major", 0.0), 8),
        },
        "global_profile": {
            "price_min": round(profile_global["price_min"], 6),
            "price_max": round(profile_global["price_max"], 6),
            "bucket_count": profile_global["bucket_count"],
            "bucket_width": round(profile_global["bucket_width"], 8),
            "candidates_count": len(global_candidates),
        },
        "local_profile": {
            "price_min": round(profile_local["price_min"], 6),
            "price_max": round(profile_local["price_max"], 6),
            "bucket_count": profile_local["bucket_count"],
            "bucket_width": round(profile_local["bucket_width"], 8),
            "candidates_count": len(local_candidates),
        },
        "psycho_candidates_count": len(psycho_zones),
        "zones_count": len(zones),
        "supports_count": supports,
        "resistances_count": resistances,
        "active_count": active,
        "local_zones_count": local_count,
        "major_zones_count": major_count,
        "psycho_zones_count": psycho_count,
        "confluence_count": confluence_count,
        "rules": {
            "local_days": LOCAL_DAYS,
            "zone_min_atr": ZONE_MIN_ATR,
            "zone_max_atr": ZONE_MAX_ATR,
            "center_min_distance_atr": CENTER_MIN_DISTANCE_ATR,
            "local_near_distance_atr": LOCAL_NEAR_DISTANCE_ATR,
            "psycho_target_atr": PSYCHO_TARGET_ATR,
            "psycho_scan_atr": PSYCHO_SCAN_ATR,
            "psycho_minor_width_atr": PSYCHO_MINOR_WIDTH_ATR,
            "psycho_major_width_atr": PSYCHO_MAJOR_WIDTH_ATR,
            "psycho_big_width_atr": PSYCHO_BIG_WIDTH_ATR,
        },
        "zones": zones,
    }


# ============================================================
# TRAITEMENT
# ============================================================

def process_asset(asset: str, top_n: int) -> bool:
    try:
        history_path, candles, history_payload = load_history(
            asset=asset,
            resolution=CFG.HISTORY_RESOLUTION,
            days=CFG.HISTORY_DAYS,
        )

        result = build_zones_for_asset(
            asset=asset,
            candles_30d=candles,
            top_n=top_n,
        )

        result["history_file"] = str(history_path)
        result["history_from_utc"] = history_payload.get("from_utc")
        result["history_to_utc"] = history_payload.get("to_utc")

        out_path = CFG.ZONES_DIR / f"zones_{asset}.json"
        save_json(out_path, result)

        log.info(
            f"[OK] {asset:10s} | zones={result['zones_count']:2d} "
            f"| local={result['local_zones_count']} "
            f"| major={result['major_zones_count']} "
            f"| psycho={result['psycho_zones_count']} "
            f"| confl={result['confluence_count']} "
            f"| S={result['supports_count']} R={result['resistances_count']} A={result['active_count']} "
            f"| close={result['last_close']} "
            f"| ATR local={result['atr_local_m15']} "
            f"| psycho minor={result['psycho_steps']['minor']} "
            f"| fichier={out_path}"
        )

        return True

    except Exception as exc:
        log.error(f"[ERREUR] {asset} : {exc}")
        return False


def print_summary(assets: List[str]) -> None:
    print()
    print("============================================================")
    print("SYNTHÈSE DES ZONES — v02.4 GLOBAL + LOCAL + PSYCHO")
    print("============================================================")

    for asset in assets:
        path = CFG.ZONES_DIR / f"zones_{asset}.json"

        if not path.exists():
            print(f"{asset:10s} | aucun fichier zones")
            continue

        data = load_json(path)
        zones = data.get("zones", [])
        steps = data.get("psycho_steps", {})

        print()
        print(
            f"{asset} | close={data.get('last_close')} | "
            f"ATR local={data.get('atr_local_m15')} | "
            f"psycho minor={steps.get('minor')} medium={steps.get('medium')} major={steps.get('major')} | "
            f"zones={len(zones)} | confluences={data.get('confluence_count')}"
        )
        print("-" * 142)

        for z in zones:
            psycho = ""
            if z.get("psycho_level") is not None:
                psycho = f" | psycho={z.get('psycho_level')} {z.get('psycho_rank')}"

            print(
                f"{z['scope']:<14s} | "
                f"{z['type'].upper():10s} | "
                f"{z['low']:>12} -> {z['high']:<12} | "
                f"centre={z['center']:<12} | "
                f"larg={z['width']:<9} | "
                f"{z['width_atr']:<5} ATR | "
                f"force={z['strength']:<6} | "
                f"dist={z['distance_atr_from_last_close']:<7} ATR | "
                f"score={z['score']:<8}"
                f"{psycho}"
            )

    print()
    print("============================================================")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    CFG.ensure_directories()

    parser = argparse.ArgumentParser(
        description="BOT_PIVOT_02.4 — zones globales/locales + prix psychologiques"
    )

    parser.add_argument(
        "--assets",
        default=",".join(CFG.ASSETS),
        help="Liste d'actifs séparés par virgule",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP,
        help="Nombre maximum de zones par actif",
    )

    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Ne pas afficher la synthèse finale",
    )

    args = parser.parse_args()
    assets = parse_assets(args.assets)

    log.info("============================================================")
    log.info("BOT_PIVOT_02_ZONES v02.4 GLOBAL + LOCAL + PSYCHO")
    log.info("Rôle : zones majeures 30j + locales 3j + prix psychologiques")
    log.info(f"Actifs      : {', '.join(assets)}")
    log.info(f"Historique  : {CFG.HISTORY_RESOLUTION} sur {CFG.HISTORY_DAYS} jours")
    log.info(f"Local       : {LOCAL_DAYS} jours")
    log.info(f"Zones max   : {args.top}")
    log.info(f"Sortie      : {CFG.ZONES_DIR}")
    log.info("============================================================")

    ok_count = 0
    error_count = 0

    for asset in assets:
        success = process_asset(asset, top_n=args.top)

        if success:
            ok_count += 1
        else:
            error_count += 1

    log.info("============================================================")
    log.info(f"TERMINÉ — OK: {ok_count} | ERREURS: {error_count}")
    log.info("============================================================")

    if not args.no_summary:
        print_summary(assets)


if __name__ == "__main__":
    main()
