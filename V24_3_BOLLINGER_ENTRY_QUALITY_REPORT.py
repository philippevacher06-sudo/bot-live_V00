#!/usr/bin/env python3
# V24_3_BOLLINGER_ENTRY_QUALITY_REPORT.py
# Analyse qualité des entrées Bollinger V24.3 à partir des logs.
# Lecture seule. Aucun ordre. Aucun fichier modifié.

import re
import sys
import argparse
import statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

ASSETS = [
    "US500", "US100", "US30", "DE40", "FR40", "UK100", "J225",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY",
    "GOLD", "SILVER", "OIL_CRUDE", "BTCUSD", "ETHUSD",
]

EVENTS = [
    "OPEN_L1", "PRICE_AUDIT", "LIMIT_REQUEST", "LIMIT_OK", "LIMIT_REJECT",
    "BASKET_NEW", "BASKET_FILL", "BASKET_TP_OK",
    "BASKET_TP_BLOCKED_BROKER_UPL", "BASKET_TP_BLOCKED_NO_BROKER_UPL",
    "BASKET_REJECT", "BASKET_REJECT_BOLLINGER_TOO_FAR",
    "BASKET_REJECT_MARKETABLE_LIMIT", "BASKET_REJECT_LEVELS_COLLAPSED",
    "BASKET_REJECT_STORM_GUARD", "BASKET_PENDING_CANCEL",
    "BASKET_PARTIAL_PENDING_CANCEL", "BASKET_MAX_LOSS",
    "BROKER_EMPTY_RESET", "MARGIN_GUARD", "MARGIN_SELECTOR",
    "MARGIN_SELECTOR_CANCEL", "STORM_GUARD",
    "STORM_GUARD_CANCEL_PENDING", "STORM_GUARD_EMERGENCY_CLOSE",
    "TRUST_OK", "TRUST_FAIL_DRIFT", "TRUST_SKIP_NO_DATA", "BOLLINGER_TRUST",
]

ASSET_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in ASSETS) + r")\s*\|")
CYCLE_RE = re.compile(r"^07D — CYCLE\s+(?P<num>\d+)\s+—\s+(?P<ts>[0-9T:\-]+Z)")
LOG_TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?)")
KV_RE = re.compile(r"([A-Za-z0-9_]+)=([\-+]?[0-9]+(?:\.[0-9]+)?(?:[eE][\-+]?[0-9]+)?)")
DIRECTION_RE = re.compile(r"\|\s+(BUY|SELL|WAIT)\s+\|")
OPEN_RE = re.compile(r"\|\s+OPEN_L1\s+\|\s+(BUY|SELL)")
FILL_RE = re.compile(r"\|\s+BASKET_FILL\s+\|\s+(\d+)")
TP_RE = re.compile(r"BASKET_TP_OK.*?pnl=([\-+]?[0-9]+(?:\.[0-9]+)?)\s+target=([\-+]?[0-9]+(?:\.[0-9]+)?)")
PENDING_CANCEL_RE = re.compile(r"age=([0-9]+(?:\.[0-9]+)?)s\s+max=([0-9]+(?:\.[0-9]+)?)s")


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


def safe_ratio(num, den):
    try:
        if den == 0:
            return None
        return num / den
    except Exception:
        return None


def pct(x):
    if x is None:
        return "--"
    return f"{x*100:.1f}%"


def fmt_num(x, dec=2):
    if x is None:
        return "--"
    return f"{x:.{dec}f}"


def stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "mean": statistics.mean(values),
    }


def get_logs(hours=None, all_logs=False):
    logs = sorted(
        Path("logs").glob("BOT_PIVOT_07D_24_7_DEMO_*.log"),
        key=lambda p: p.stat().st_mtime,
    )
    if all_logs or hours is None:
        return logs
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    out = []
    for p in logs:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
        if mtime >= cutoff:
            out.append(p)
    return out


def analyse(logs):
    global_counts = Counter()
    per_asset = {a: Counter() for a in ASSETS}
    signal_counts = {a: Counter() for a in ASSETS}
    open_dir = {a: Counter() for a in ASSETS}
    price_audit = {a: [] for a in ASSETS}
    tp_ok = {a: [] for a in ASSETS}
    pending_cancel = {a: [] for a in ASSETS}
    recent_events = []
    recent_problem_cases = []
    cycles = 0

    for log in logs:
        try:
            lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue
        for line_no, line in enumerate(lines, start=1):
            cm = CYCLE_RE.match(line)
            if cm:
                cycles += 1
            asset_match = ASSET_RE.search(line)
            asset = asset_match.group(1) if asset_match else None
            for ev in EVENTS:
                if ev in line:
                    global_counts[ev] += 1
                    if asset:
                        per_asset[asset][ev] += 1
            for k in ["Traceback", "TimeoutError", "ERROR", "Exception"]:
                if k in line:
                    global_counts[k] += 1
            if asset:
                dm = DIRECTION_RE.search(line)
                if dm:
                    signal_counts[asset][dm.group(1)] += 1
                om = OPEN_RE.search(line)
                if om:
                    open_dir[asset][om.group(1)] += 1
                if "PRICE_AUDIT" in line:
                    kv = {k: float(v) for k, v in KV_RE.findall(line)}
                    record = {"line": line, "kv": kv}
                    if "dist" in kv:
                        record["dist"] = kv.get("dist")
                    if "max_dist" in kv:
                        record["max_dist"] = kv.get("max_dist")
                        record["dist_ratio"] = safe_ratio(kv.get("dist"), kv.get("max_dist"))
                    price_audit[asset].append(record)
                if "BASKET_TP_OK" in line:
                    m = TP_RE.search(line)
                    if m:
                        tp_ok[asset].append({"pnl": float(m.group(1)), "target": float(m.group(2))})
                if "BASKET_PENDING_CANCEL" in line or "BASKET_PARTIAL_PENDING_CANCEL" in line:
                    m = PENDING_CANCEL_RE.search(line)
                    pending_cancel[asset].append({
                        "kind": "partial" if "PARTIAL" in line else "full",
                        "age": float(m.group(1)) if m else None,
                        "max": float(m.group(2)) if m else None,
                    })
                useful = ["OPEN_L1", "PRICE_AUDIT", "LIMIT_OK", "BASKET_NEW", "BASKET_FILL",
                          "BASKET_TP_OK", "BASKET_TP_BLOCKED", "BASKET_REJECT",
                          "BASKET_PENDING_CANCEL", "BROKER_EMPTY_RESET",
                          "TRUST_OK", "TRUST_FAIL_DRIFT", "TRUST_SKIP_NO_DATA"]
                if any(u in line for u in useful):
                    recent_events.append((str(log), line_no, line))
                problem = ["BASKET_REJECT_BOLLINGER_TOO_FAR", "BASKET_PENDING_CANCEL",
                           "BASKET_PARTIAL_PENDING_CANCEL", "BASKET_TP_BLOCKED_NO_BROKER_UPL",
                           "BROKER_EMPTY_RESET", "TRUST_FAIL_DRIFT", "Traceback", "ERROR"]
                if any(p in line for p in problem):
                    recent_problem_cases.append((str(log), line_no, line))

    return {
        "cycles": cycles, "global_counts": global_counts, "per_asset": per_asset,
        "signal_counts": signal_counts, "open_dir": open_dir, "price_audit": price_audit,
        "tp_ok": tp_ok, "pending_cancel": pending_cancel,
        "recent_events": recent_events, "recent_problem_cases": recent_problem_cases,
    }


def print_global_report(r, logs):
    print("=" * 120)
    print("V24.3 — RAPPORT QUALITÉ DES ENTRÉES BOLLINGER")
    print(f"UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}")
    print(f"Logs analysés: {len(logs)}")
    for p in logs:
        print(f"  - {p}")
    print("=" * 120)
    print()

    gc = r["global_counts"]

    print("=== 1) SANTÉ TECHNIQUE ===")
    for k in ["Traceback", "TimeoutError", "ERROR", "Exception", "BROKER_EMPTY_RESET"]:
        print(f"{k:35s}: {gc.get(k, 0)}")
    print()

    print("=== 2) PIPELINE GLOBAL ===")
    keys = [
        "OPEN_L1",
        "PRICE_AUDIT",
        "LIMIT_REQUEST",
        "LIMIT_OK",
        "LIMIT_REJECT",
        "BASKET_NEW",
        "BASKET_FILL",
        "BASKET_TP_OK",
        "BASKET_TP_BLOCKED_BROKER_UPL",
        "BASKET_TP_BLOCKED_NO_BROKER_UPL",
        "BASKET_REJECT",
        "BASKET_REJECT_BOLLINGER_TOO_FAR",
        "BASKET_REJECT_MARKETABLE_LIMIT",
        "BASKET_REJECT_LEVELS_COLLAPSED",
        "BASKET_REJECT_STORM_GUARD",
        "BASKET_PENDING_CANCEL",
        "BASKET_PARTIAL_PENDING_CANCEL",
        "BASKET_MAX_LOSS",
        "MARGIN_GUARD",
        "MARGIN_SELECTOR",
        "MARGIN_SELECTOR_CANCEL",
        "STORM_GUARD",
        "STORM_GUARD_CANCEL_PENDING",
        "STORM_GUARD_EMERGENCY_CLOSE",
        "TRUST_OK",
        "TRUST_FAIL_DRIFT",
        "TRUST_SKIP_NO_DATA",
        "BOLLINGER_TRUST",
    ]

    for k in keys:
        print(f"{k:35s}: {gc.get(k, 0)}")

    open_l1 = gc.get("OPEN_L1", 0)
    limit_ok = gc.get("LIMIT_OK", 0)
    basket_new = gc.get("BASKET_NEW", 0)
    fill = gc.get("BASKET_FILL", 0)
    tp = gc.get("BASKET_TP_OK", 0)

    print()
    print("=== 3) FUNNEL GLOBAL ===")
    print(f"LIMIT_OK / OPEN_L1       : {limit_ok}/{open_l1} = {pct(safe_ratio(limit_ok, open_l1))}")
    print(f"BASKET_NEW / OPEN_L1     : {basket_new}/{open_l1} = {pct(safe_ratio(basket_new, open_l1))}")
    print(f"BASKET_FILL / BASKET_NEW : {fill}/{basket_new} = {pct(safe_ratio(fill, basket_new))}")
    print(f"TP_OK / BASKET_FILL      : {tp}/{fill} = {pct(safe_ratio(tp, fill))}")
    print()


def print_asset_table(r):
    print("=== 4) PIPELINE PAR ACTIF ===")

    header = (
        f"{'ACTIF':10s} "
        f"{'BUY':>4s} {'SELL':>4s} {'WAIT':>5s} | "
        f"{'OPEN':>5s} {'L_OK':>5s} {'NEW':>5s} {'FILL':>5s} {'TP':>4s} | "
        f"{'BB_FAR':>6s} {'PEND':>5s} {'PART':>5s} | "
        f"{'TR_OK':>5s} {'TR_FAIL':>7s} | "
        f"{'FILL/NEW':>8s} {'TP/FILL':>8s}"
    )

    print(header)
    print("-" * len(header))

    for a in ASSETS:
        c = r["per_asset"][a]
        s = r["signal_counts"][a]

        new = c.get("BASKET_NEW", 0)
        fill = c.get("BASKET_FILL", 0)
        tp = c.get("BASKET_TP_OK", 0)

        print(
            f"{a:10s} "
            f"{s.get('BUY',0):4d} {s.get('SELL',0):4d} {s.get('WAIT',0):5d} | "
            f"{c.get('OPEN_L1',0):5d} "
            f"{c.get('LIMIT_OK',0):5d} "
            f"{new:5d} "
            f"{fill:5d} "
            f"{tp:4d} | "
            f"{c.get('BASKET_REJECT_BOLLINGER_TOO_FAR',0):6d} "
            f"{c.get('BASKET_PENDING_CANCEL',0):5d} "
            f"{c.get('BASKET_PARTIAL_PENDING_CANCEL',0):5d} | "
            f"{c.get('TRUST_OK',0):5d} "
            f"{c.get('TRUST_FAIL_DRIFT',0):7d} | "
            f"{pct(safe_ratio(fill,new)):>8s} "
            f"{pct(safe_ratio(tp,fill)):>8s}"
        )

    print()


def print_price_audit_stats(r):
    print("=== 5) DISTANCES PRICE_AUDIT / BOLLINGER ===")
    print("Lecture : dist_ratio = dist / max_dist quand les deux champs existent dans le log.")
    print()

    header = (
        f"{'ACTIF':10s} {'N_AUDIT':>7s} "
        f"{'dist_med':>12s} {'dist_max':>12s} "
        f"{'ratio_med':>12s} {'ratio_max':>12s}"
    )

    print(header)
    print("-" * len(header))

    for a in ASSETS:
        records = r["price_audit"][a]

        dists = [x.get("dist") for x in records if x.get("dist") is not None]
        ratios = [x.get("dist_ratio") for x in records if x.get("dist_ratio") is not None]

        ds = stats(dists)
        rs = stats(ratios)

        print(
            f"{a:10s} "
            f"{len(records):7d} "
            f"{fmt_num(ds['median'] if ds else None, 6):>12s} "
            f"{fmt_num(ds['max'] if ds else None, 6):>12s} "
            f"{fmt_num(rs['median'] if rs else None, 2):>12s} "
            f"{fmt_num(rs['max'] if rs else None, 2):>12s}"
        )

    print()


def print_pending_tp_stats(r):
    print("=== 6) PENDING CANCEL / TP PAR ACTIF ===")

    header = (
        f"{'ACTIF':10s} "
        f"{'PEND_FULL':>9s} {'PEND_PART':>9s} "
        f"{'AGE_MED':>9s} {'AGE_MAX':>9s} | "
        f"{'TP_N':>5s} {'TP_PNL_MED':>10s} {'TP_TARGET_MED':>13s}"
    )

    print(header)
    print("-" * len(header))

    for a in ASSETS:
        pc = r["pending_cancel"][a]

        full = sum(1 for x in pc if x.get("kind") == "full")
        part = sum(1 for x in pc if x.get("kind") == "partial")

        ages = [x.get("age") for x in pc if x.get("age") is not None]
        ags = stats(ages)

        tps = r["tp_ok"][a]
        pnls = [x["pnl"] for x in tps]
        targets = [x["target"] for x in tps]

        ps = stats(pnls)
        ts = stats(targets)

        print(
            f"{a:10s} "
            f"{full:9d} {part:9d} "
            f"{fmt_num(ags['median'] if ags else None, 1):>9s} "
            f"{fmt_num(ags['max'] if ags else None, 1):>9s} | "
            f"{len(tps):5d} "
            f"{fmt_num(ps['median'] if ps else None, 2):>10s} "
            f"{fmt_num(ts['median'] if ts else None, 2):>13s}"
        )

    print()


def print_priorities(r):
    print("=== 7) PRIORITÉS AUTOMATIQUES ===")

    gc = r["global_counts"]
    priorities = []

    if gc.get("Traceback", 0) or gc.get("ERROR", 0) or gc.get("Exception", 0):
        priorities.append("CRITIQUE : corriger les erreurs techniques avant toute optimisation stratégique.")

    if gc.get("BASKET_TP_BLOCKED_NO_BROKER_UPL", 0):
        priorities.append("CRITIQUE : présence de NO_BROKER_UPL, vérifier réconciliation broker/local.")

    if gc.get("BROKER_EMPTY_RESET", 0):
        priorities.append("SURVEILLANCE : BROKER_EMPTY_RESET déclenché, vérifier qu'il nettoie correctement sans faux positif.")

    reject_bb = gc.get("BASKET_REJECT_BOLLINGER_TOO_FAR", 0)
    open_l1 = gc.get("OPEN_L1", 0)

    if reject_bb > 0 and reject_bb >= open_l1:
        priorities.append("STRATÉGIE : BOLLINGER_TOO_FAR domine ; réglage par actif des max_dist / buffer à étudier.")
    elif reject_bb > 0:
        priorities.append("STRATÉGIE : BOLLINGER_TOO_FAR existe ; analyser les actifs concernés uniquement.")

    new = gc.get("BASKET_NEW", 0)
    fill = gc.get("BASKET_FILL", 0)

    ratio_fill_new = safe_ratio(fill, new)
    if new >= 3 and ratio_fill_new is not None and ratio_fill_new < 0.35:
        priorities.append("STRATÉGIE : beaucoup de paniers posés mais peu remplis ; L1 probablement trop loin ou durée pending trop courte.")

    pending = gc.get("BASKET_PENDING_CANCEL", 0) + gc.get("BASKET_PARTIAL_PENDING_CANCEL", 0)

    if pending >= fill and pending > 0:
        priorities.append("STRATÉGIE : expirations pending importantes ; étudier durée pending et qualité du placement L1.")

    if gc.get("TRUST_FAIL_DRIFT", 0):
        priorities.append("STRATÉGIE : TRUST_FAIL_DRIFT présent ; corréler drift Bollinger avec fills et TP.")

    muted = []

    for a in ASSETS:
        c = r["per_asset"][a]
        s = r["signal_counts"][a]

        if c.get("OPEN_L1", 0) == 0 and c.get("BASKET_REJECT_BOLLINGER_TOO_FAR", 0) == 0:
            if s.get("BUY", 0) == 0 and s.get("SELL", 0) == 0:
                muted.append(a)

    if muted:
        priorities.append("DIAGNOSTIC : actifs muets ou très peu visibles côté signal : " + ", ".join(muted))

    if not priorities:
        priorities.append("Aucun point critique automatique. Continuer l'observation et augmenter l'échantillon.")

    for i, p in enumerate(priorities, start=1):
        print(f"{i}. {p}")

    print()


def print_recent_cases(r, limit):
    print(f"=== 8) DERNIERS CAS PROBLÉMATIQUES — {limit} lignes ===")

    for log, line_no, line in r["recent_problem_cases"][-limit:]:
        print(f"{Path(log).name}:{line_no}: {line}")

    print()
    print(f"=== 9) DERNIERS ÉVÉNEMENTS UTILES — {limit} lignes ===")

    for log, line_no, line in r["recent_events"][-limit:]:
        print(f"{Path(log).name}:{line_no}: {line}")

    print()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=12, help="nombre d'heures de logs à analyser, défaut 12")
    ap.add_argument("--all", action="store_true", help="analyse tous les logs disponibles")
    ap.add_argument("--recent", type=int, default=120, help="nombre de lignes récentes à afficher")
    ap.add_argument("--out", type=str, default="", help="chemin optionnel de sortie texte")
    args = ap.parse_args()

    logs = get_logs(hours=args.hours, all_logs=args.all)

    if not logs:
        print("Aucun log trouvé.")
        sys.exit(1)

    r = analyse(logs)

    print_global_report(r, logs)
    print_asset_table(r)
    print_price_audit_stats(r)
    print_pending_tp_stats(r)
    print_priorities(r)
    print_recent_cases(r, args.recent)


if __name__ == "__main__":
    main()
