#!/usr/bin/env python3
# V24_3_BOLLINGER_AUDIT_V2.py
# Audit Bollinger avec horodatage strict + triple source bid / ask / mid.
# Lecture seule. Aucun ordre. Aucun fichier modifié.

import re
import sys
import statistics
from pathlib import Path
from datetime import datetime, timezone

import requests

import BOT_PIVOT_06G_execution_from_cycle_state as B


ASSETS = [
    "US500", "US100", "US30", "DE40", "FR40", "UK100", "J225",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY",
    "GOLD", "SILVER", "OIL_CRUDE", "BTCUSD", "ETHUSD",
]

PERIOD = 20
MULT = 2.0

# 0.01 % du BB_MID
TOLERANCE_PCT = 0.0001

# Au-delà de 90 secondes, on ne conclut pas.
STALE_THRESHOLD_SEC = 90.0

LOG_GLOB = "logs/BOT_PIVOT_07D_24_7_DEMO_*.log"

LOG_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)"
)

CYCLE_TS_RE = re.compile(
    r"^07D — CYCLE\s+\d+\s+—\s+(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z"
)

PRICE_AUDIT_RE = re.compile(
    r"(?P<asset>\S+)\s+\|\s+PRICE_AUDIT\s+\|.*?"
    r"BB_LOW=(?P<bb_low>[0-9eE\.\+\-]+)\s+"
    r"BB_MID=(?P<bb_mid>[0-9eE\.\+\-]+)\s+"
    r"BB_HIGH=(?P<bb_high>[0-9eE\.\+\-]+)"
)


def latest_log():
    logs = sorted(
        Path(".").glob(LOG_GLOB),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return logs[0] if logs else None


def parse_dt(raw):
    if not raw:
        return None

    raw = raw.strip().replace(",", ".").replace(" ", "T")

    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(raw)
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def parse_log_line_time(line):
    m = LOG_TS_RE.match(line)
    if not m:
        return None
    return parse_dt(m.group("ts"))


def parse_cycle_time(line):
    m = CYCLE_TS_RE.match(line)
    if not m:
        return None
    return parse_dt(m.group("ts") + "Z")


def last_price_audit_per_asset(log_path):
    """
    Retourne :
    {
      asset: {
        bb_low, bb_mid, bb_high,
        ts_utc,
        ts_source,
        line_no
      }
    }
    """

    out = {}

    if not log_path or not log_path.exists():
        return out

    current_ts = None
    current_ts_source = None
    current_cycle_ts = None

    with log_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, start=1):
            cycle_ts = parse_cycle_time(line)
            if cycle_ts:
                current_cycle_ts = cycle_ts
                current_ts = cycle_ts
                current_ts_source = "cycle_header"

            log_ts = parse_log_line_time(line)
            if log_ts:
                current_ts = log_ts
                current_ts_source = "log_prefix"

            m = PRICE_AUDIT_RE.search(line)
            if not m:
                continue

            asset = m.group("asset").upper()

            ts = current_ts or current_cycle_ts
            ts_source = current_ts_source or ("cycle_header" if current_cycle_ts else "unknown")

            try:
                out[asset] = {
                    "bb_low": float(m.group("bb_low")),
                    "bb_mid": float(m.group("bb_mid")),
                    "bb_high": float(m.group("bb_high")),
                    "ts_utc": ts,
                    "ts_source": ts_source,
                    "line_no": line_no,
                    "raw_line": line.strip(),
                }
            except Exception:
                pass

    return out


def fetch_m5_candles(headers, base_url, asset, max_candles=40):
    url = f"{base_url.rstrip('/')}/api/v1/prices/{asset}"
    params = {
        "resolution": "MINUTE_5",
        "max": max_candles,
    }

    try:
        r = requests.get(url, headers=headers, params=params, timeout=20)
    except Exception as e:
        return None, f"REQ_ERR {e}", None

    if r.status_code != 200:
        return None, f"HTTP {r.status_code} {r.text[:250]}", None

    try:
        data = r.json()
    except Exception as e:
        return None, f"JSON_ERR {e}", None

    prices = data.get("prices") or []

    rows = []

    for item in prices:
        close_price = item.get("closePrice") or {}

        if not isinstance(close_price, dict):
            continue

        bid = close_price.get("bid")
        ask = close_price.get("ask")

        if bid is None or ask is None:
            continue

        try:
            bid = float(bid)
            ask = float(ask)
        except Exception:
            continue

        t = item.get("snapshotTimeUTC") or item.get("snapshotTime") or ""

        rows.append({
            "time": t,
            "bid": bid,
            "ask": ask,
            "mid": (bid + ask) / 2.0,
        })

    rows = sorted(rows, key=lambda x: x.get("time") or "")

    series = {
        "bid": [r["bid"] for r in rows],
        "ask": [r["ask"] for r in rows],
        "mid": [r["mid"] for r in rows],
    }

    last_time = rows[-1]["time"] if rows else None

    return series, "OK", last_time


def bollinger(closes, period=20, mult=2.0, ddof=0):
    if len(closes) < period:
        return None

    window = closes[-period:]
    mid = sum(window) / period

    if ddof == 0:
        sd = statistics.pstdev(window)
    else:
        sd = statistics.stdev(window)

    return mid - mult * sd, mid, mid + mult * sd


def max_abs_diff(bot, audit):
    if bot is None or audit is None:
        return None

    audit_low, audit_mid, audit_high = audit

    return max(
        abs(bot["bb_low"] - audit_low),
        abs(bot["bb_mid"] - audit_mid),
        abs(bot["bb_high"] - audit_high),
    )


def within_tol(bot, audit, tol):
    if bot is None or audit is None:
        return False

    audit_low, audit_mid, audit_high = audit

    pairs = [
        (bot["bb_low"], audit_low),
        (bot["bb_mid"], audit_mid),
        (bot["bb_high"], audit_high),
    ]

    return all(abs(a - b) <= tol for a, b in pairs)


def classify(bot, series):
    if bot is None:
        return "NO_BOT_DATA", [], None

    bot_mid = bot["bb_mid"]

    if bot_mid == 0:
        return "NO_BOT_DATA", [], None

    tol = abs(bot_mid) * TOLERANCE_PCT

    matches = []
    best = None

    for source in ("mid", "bid", "ask"):
        closes = series.get(source, [])

        if len(closes) < PERIOD + 1:
            continue

        variants = [
            ("INCL", closes),
            ("EXCL", closes[:-1]),
        ]

        for mode, sub_closes in variants:
            for ddof, ddof_label in [(0, "POP"), (1, "SAMPLE")]:
                band = bollinger(sub_closes, PERIOD, MULT, ddof=ddof)

                if band is None:
                    continue

                diff = max_abs_diff(bot, band)

                label = f"MATCH_{source.upper()}_{mode}"
                if ddof_label == "SAMPLE":
                    label += "_SAMPLE"

                if best is None or diff < best["diff"]:
                    best = {
                        "label": label,
                        "source": source,
                        "mode": mode,
                        "ddof": ddof_label,
                        "band": band,
                        "diff": diff,
                    }

                if within_tol(bot, band, tol):
                    matches.append(label)

    if not matches:
        return "MISMATCH_TOTAL", [], best

    # Priorité logique : mid > bid > ask, population > sample, INCL avant EXCL.
    priority = []

    for source in ("MID", "BID", "ASK"):
        for mode in ("INCL", "EXCL"):
            priority.append(f"MATCH_{source}_{mode}")
            priority.append(f"MATCH_{source}_{mode}_SAMPLE")

    for wanted in priority:
        if wanted in matches:
            return wanted, matches, best

    return matches[0], matches, best


def decimals_for(ref):
    if ref is None:
        return 4

    a = abs(float(ref))

    if a < 10:
        return 6

    if a < 1000:
        return 4

    return 2


def fmt(x, dec):
    if x is None:
        return "--"
    return f"{x:.{dec}f}"


def fmt_age(age):
    if age is None:
        return "--"
    return f"{age:.0f}s"


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)

    print("=" * 140)
    print("V24.3 BOLLINGER AUDIT V2 — horodatage strict + sources bid / ask / mid")
    print("Lecture seule : aucun ordre, aucune modification.")
    print(f"UTC audit            : {now.isoformat()}")
    print(f"Période Bollinger    : {PERIOD}")
    print(f"Multiplicateur       : {MULT}")
    print(f"Tolérance MATCH      : {TOLERANCE_PCT * 100:.5f}% du BB_MID")
    print(f"Seuil STALE_AUDIT    : {STALE_THRESHOLD_SEC:.0f}s")
    print("=" * 140)

    B.load_env()
    headers = B.login()
    base_url = getattr(B, "BASE_URL", "https://demo-api-capital.backend-capital.com")

    log_path = latest_log()
    print(f"LOG utilisé          : {log_path}")

    bot_audits = last_price_audit_per_asset(log_path)
    print(f"PRICE_AUDIT trouvés  : {len(bot_audits)}/{len(ASSETS)} actifs")

    ages = []

    for asset in ASSETS:
        rec = bot_audits.get(asset)

        if rec and rec.get("ts_utc"):
            ages.append((now - rec["ts_utc"]).total_seconds())

    if ages:
        ages_sorted = sorted(ages)
        median_age = ages_sorted[len(ages_sorted) // 2]

        print(
            f"Âge PRICE_AUDIT      : "
            f"min={ages_sorted[0]:.0f}s  médian={median_age:.0f}s  max={ages_sorted[-1]:.0f}s"
        )

        if median_age > STALE_THRESHOLD_SEC * 2:
            print()
            print("!" * 140)
            print("ATTENTION : la majorité des PRICE_AUDIT est ancienne.")
            print("Les comparaisons STALE_AUDIT ne doivent pas être utilisées pour conclure.")
            print("Idéal : relancer ce script juste après un cycle bot contenant des PRICE_AUDIT frais.")
            print("!" * 140)

    print()

    header = (
        f"{'ACTIF':10s} "
        f"{'AGE':>7s} "
        f"{'TS_SRC':12s} "
        f"{'API_LAST':19s} "
        f"{'N':>3s} | "
        f"{'BOT_LOW':>14s} {'BOT_MID':>14s} {'BOT_HIGH':>14s} | "
        f"{'STATUS':28s} | "
        f"{'BEST_NEAR':24s} {'DIFF':>10s} | "
        f"{'AUTRES_MATCHS'}"
    )

    print(header)
    print("-" * len(header))

    summary = {}

    for asset in ASSETS:
        series, fetch_status, api_last = fetch_m5_candles(
            headers=headers,
            base_url=base_url,
            asset=asset,
            max_candles=40,
        )

        n = 0 if series is None else len(series.get("mid", []))

        bot = bot_audits.get(asset)

        age = None
        age_str = "--"
        ts_source = "--"

        if bot and bot.get("ts_utc"):
            age = (now - bot["ts_utc"]).total_seconds()
            age_str = fmt_age(age)
            ts_source = bot.get("ts_source") or "--"

        if series is None or n < PERIOD + 1:
            status = "INSUFFICIENT_API_DATA"
            summary[status] = summary.get(status, 0) + 1

            print(
                f"{asset:10s} "
                f"{age_str:>7s} "
                f"{ts_source[:12]:12s} "
                f"{(api_last or '--')[:19]:19s} "
                f"{n:3d} | "
                f"{'--':>14s} {'--':>14s} {'--':>14s} | "
                f"{status:28s} | "
                f"{fetch_status[:24]:24s} {'--':>10s} | "
            )
            continue

        if bot is None:
            status = "NO_BOT_DATA"
            summary[status] = summary.get(status, 0) + 1
            dec = decimals_for(series["mid"][-1])

            print(
                f"{asset:10s} "
                f"{age_str:>7s} "
                f"{ts_source[:12]:12s} "
                f"{(api_last or '--')[:19]:19s} "
                f"{n:3d} | "
                f"{'--':>14s} {'--':>14s} {'--':>14s} | "
                f"{status:28s} | "
                f"{'--':24s} {'--':>10s} | "
            )
            continue

        if age is not None and age > STALE_THRESHOLD_SEC:
            status = "STALE_AUDIT"
            matches = []
            best_status, matches_tmp, best = classify(bot, series)
            summary[status] = summary.get(status, 0) + 1
        else:
            status, matches, best = classify(bot, series)
            summary[status] = summary.get(status, 0) + 1

        dec = decimals_for(bot["bb_mid"])

        best_label = "--"
        best_diff = None

        if best:
            best_label = best["label"]
            best_diff = best["diff"]

        autres = ""

        if matches and len(matches) > 1:
            autres = " / ".join(m for m in matches if m != status)

        print(
            f"{asset:10s} "
            f"{age_str:>7s} "
            f"{ts_source[:12]:12s} "
            f"{(api_last or '--')[:19]:19s} "
            f"{n:3d} | "
            f"{fmt(bot['bb_low'], dec):>14s} "
            f"{fmt(bot['bb_mid'], dec):>14s} "
            f"{fmt(bot['bb_high'], dec):>14s} | "
            f"{status:28s} | "
            f"{best_label[:24]:24s} "
            f"{fmt(best_diff, dec):>10s} | "
            f"{autres}"
        )

    print("-" * len(header))
    print()
    print("RÉSUMÉ :")

    for k, v in sorted(summary.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {k:30s}: {v}")

    print()
    print("LECTURE :")
    print("  MATCH_MID_INCL        : le bot matche mid=(bid+ask)/2 avec bougie M5 en cours incluse.")
    print("  MATCH_MID_EXCL        : le bot matche mid=(bid+ask)/2 avec bougie M5 en cours exclue.")
    print("  MATCH_BID_*           : le bot matche bid seul.")
    print("  MATCH_ASK_*           : le bot matche ask seul.")
    print("  *_SAMPLE              : match seulement avec écart-type sample ddof=1.")
    print("  STALE_AUDIT           : PRICE_AUDIT trop ancien, comparaison non fiable.")
    print("  MISMATCH_TOTAL        : aucune variante bid/ask/mid incl/excl ne matche.")
    print("  NO_BOT_DATA           : pas de PRICE_AUDIT récent ou existant pour cet actif dans le log.")
    print()
    print("IMPORTANT : Capital.com ne donne pas directement ses bandes Bollinger UI via API.")
    print("Ce script vérifie la cohérence du bot avec les bougies M5 API Capital.com.")
    print("Si l'UI Capital.com diffère encore, elle peut utiliser une source ou une règle différente.")
    print("=" * 140)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
