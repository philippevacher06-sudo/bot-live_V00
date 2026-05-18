#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


LOG_DIR = Path("logs")
CYCLE_STATE = Path("data/cycles/cycle_state.json")
EXEC_STATE = Path("data/execution/cycle_execution_state.json")


def latest_log():
    logs = sorted(LOG_DIR.glob("BOT_PIVOT_07D_24_7_DEMO_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def count(pattern, text):
    return len(re.findall(pattern, text))


def state_counts():
    cycle_non_idle = 0
    exec_active = 0

    try:
        data = json.loads(CYCLE_STATE.read_text(encoding="utf-8"))
        for st in (data.get("assets") or {}).values():
            if st.get("status") != "IDLE":
                cycle_non_idle += 1
    except Exception:
        pass

    try:
        data = json.loads(EXEC_STATE.read_text(encoding="utf-8"))
        exec_active = len(data.get("active") or {})
    except Exception:
        pass

    return cycle_non_idle, exec_active


def main():
    log = latest_log()
    if not log:
        raise SystemExit("Aucun log BOT_PIVOT_07D_24_7_DEMO_*.log trouve.")

    text = log.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    print(f"LOG={log}")
    print()
    print("=== Bilan global ===")
    for label, pattern in [
        ("Cycles", r"07D .+ CYCLE"),
        ("Traceback", r"Traceback"),
        ("TimeoutError", r"TimeoutError"),
        ("HTTP 429", r"HTTP 429|too-many\.requests"),
        ("OPEN_L1", r"OPEN_L1"),
        ("PRICE_AUDIT", r"PRICE_AUDIT"),
        ("LIMIT_REQUEST", r"LIMIT_REQUEST"),
        ("LIMIT_OK", r"LIMIT_OK"),
        ("BASKET_FILL", r"BASKET_FILL"),
        ("BASKET_TP_OK", r"BASKET_TP_OK"),
        ("BASKET_REJECT", r"BASKET_REJECT"),
        ("BASKET_REJECT_STORM_GUARD", r"BASKET_REJECT_STORM_GUARD"),
        ("STORM_GUARD_CANCEL_PENDING", r"STORM_GUARD_CANCEL_PENDING"),
        ("BASKET_MAX_LOSS_CLOSE_OK", r"BASKET_MAX_LOSS_CLOSE_OK"),
        ("tick_trop_ancien", r"tick_trop_ancien"),
    ]:
        print(f"{label:30s}: {count(pattern, text)}")

    cycle_non_idle, exec_active = state_counts()
    print(f"{'CYCLE non-IDLE':30s}: {cycle_non_idle}")
    print(f"{'EXEC active':30s}: {exec_active}")

    reject_by_asset = Counter()
    limit_ok_by_asset = Counter()
    tick_old_by_asset = Counter()
    ratios = defaultdict(list)

    too_far_re = re.compile(
        r"^(?P<asset>\S+)\s+\|\s+BASKET_REJECT_BOLLINGER_TOO_FAR\s+\|.*?"
        r"dist=(?P<dist>[0-9.]+)\s+\|\s+max=(?P<max>[0-9.]+)"
    )

    for line in lines:
        if "BASKET_REJECT_BOLLINGER_TOO_FAR" in line:
            asset = line.split()[0]
            reject_by_asset[asset] += 1
            m = too_far_re.search(line)
            if m:
                dist = float(m.group("dist"))
                max_dist = float(m.group("max"))
                if max_dist > 0:
                    ratios[asset].append(dist / max_dist)

        if "LIMIT_OK" in line:
            limit_ok_by_asset[line.split()[0]] += 1

        if "tick_trop_ancien" in line:
            tick_old_by_asset[line.split()[0]] += 1

    print()
    print("=== BOLLINGER_TOO_FAR par actif ===")
    for asset, n in reject_by_asset.most_common():
        r = ratios.get(asset) or []
        med = median(r) if r else None
        med_txt = f" ratio_med={med:.2f}" if med is not None else ""
        print(f"{asset:10s} {n:5d}{med_txt}")

    print()
    print("=== LIMIT_OK par actif ===")
    for asset, n in limit_ok_by_asset.most_common():
        print(f"{asset:10s} {n:5d}")

    print()
    print("=== tick_trop_ancien par actif ===")
    for asset, n in tick_old_by_asset.most_common():
        print(f"{asset:10s} {n:5d}")

    print()
    print("=== Derniers evenements utiles ===")
    useful = [
        l for l in lines
        if re.search(
            r"OPEN_L1|PRICE_AUDIT|LIMIT_OK|BASKET_FILL|BASKET_TP_OK|"
            r"BASKET_REJECT|STORM_GUARD|MAX_LOSS|Traceback|TimeoutError|ERROR|Exception",
            l,
        )
    ]
    for line in useful[-120:]:
        print(line)


if __name__ == "__main__":
    main()
