import re
import argparse
from pathlib import Path
from collections import defaultdict

parser = argparse.ArgumentParser()
parser.add_argument("--logs", default="logs/BOT_PIVOT_07D_24_7_DEMO_*.log")
parser.add_argument("--last", type=int, default=5)
args = parser.parse_args()

logs = sorted(Path(".").glob(args.logs), key=lambda p: p.stat().st_mtime)[-args.last:]

pnl_total_re = re.compile(
    r"^([A-Z0-9_]+)\s+\| PNL_AUDIT_TOTAL .* open=(\d+) pnl=([\-0-9.]+) broker_upl=([\-0-9.]+|none) target=([\-0-9.]+|None|null)"
)

tp_ok_re = re.compile(
    r"^([A-Z0-9_]+)\s+\| BASKET_TP_OK .* pnl=([\-0-9.]+) target=([\-0-9.]+).*source=([A-Z0-9_]+)"
)

tp_block_re = re.compile(
    r"^([A-Z0-9_]+)\s+\| BASKET_TP_BLOCKED_BROKER_UPL .* internal=([\-0-9.]+) broker_upl=([\-0-9.]+) target=([\-0-9.]+)"
)

fill_re = re.compile(
    r"^([A-Z0-9_]+)\s+\| BASKET_FILL \| (\d+) .*"
)

summary = defaultdict(lambda: {"tp_ok": 0, "bad_target": 0, "bad_source": 0, "pnl_below": 0})
blocked = defaultdict(int)
fills = defaultdict(int)
events = []

for log in logs:
    lines = log.read_text(errors="ignore").splitlines()
    last_total = {}

    for i, line in enumerate(lines, start=1):
        m = pnl_total_re.search(line)
        if m:
            asset, open_count, pnl, broker_upl, target = m.groups()
            last_total[asset] = {
                "line": i,
                "open": int(open_count),
                "pnl": pnl,
                "broker_upl": broker_upl,
                "target": target,
                "raw": line,
                "log": str(log),
            }
            continue

        m = fill_re.search(line)
        if m:
            asset, level = m.groups()
            fills[(asset, int(level))] += 1
            continue

        m = tp_block_re.search(line)
        if m:
            asset, internal, broker_upl, target = m.groups()
            try:
                blocked[float(target)] += 1
            except Exception:
                blocked[target] += 1
            continue

        m = tp_ok_re.search(line)
        if m:
            asset, pnl, target, source = m.groups()
            ctx = last_total.get(asset)

            open_count = ctx["open"] if ctx else None
            expected = round(0.20 * open_count, 2) if open_count else None

            try:
                pnl_f = float(pnl)
                target_f = float(target)
            except Exception:
                pnl_f = None
                target_f = None

            ok_target = expected is not None and target_f is not None and abs(target_f - expected) < 0.001
            ok_source = source == "BROKER_POSITION_UPL"
            ok_pnl = pnl_f is not None and target_f is not None and pnl_f + 1e-9 >= target_f

            key = open_count if open_count is not None else "UNKNOWN"
            summary[key]["tp_ok"] += 1
            if not ok_target:
                summary[key]["bad_target"] += 1
            if not ok_source:
                summary[key]["bad_source"] += 1
            if not ok_pnl:
                summary[key]["pnl_below"] += 1

            events.append({
                "log": str(log),
                "line": i,
                "asset": asset,
                "open": open_count,
                "expected": expected,
                "target": target,
                "pnl": pnl,
                "source": source,
                "ok_target": ok_target,
                "ok_source": ok_source,
                "ok_pnl": ok_pnl,
                "tp_line": line,
                "ctx_line": ctx["raw"] if ctx else None,
            })

print("=" * 120)
print("V24.3 — TP LADDER AUDIT")
print("=" * 120)
print("Logs analysés :")
for p in logs:
    print(" -", p)
print()

print("=== Fills observés par niveau ===")
for (asset, level), n in sorted(fills.items()):
    print(f"{asset:10s} L{level}: {n}")
print()

print("=== TP bloqués par target ===")
for target, n in sorted(blocked.items(), key=lambda x: str(x[0])):
    print(f"target={target}: blocked={n}")
print()

print("=== Résumé TP_OK par nombre de jambes ouvertes ===")
for open_count in sorted(summary.keys(), key=lambda x: 99 if x == "UNKNOWN" else x):
    s = summary[open_count]
    expected = "?" if open_count == "UNKNOWN" else f"{0.20 * open_count:.2f}"
    print(
        f"open={open_count} expected={expected} "
        f"TP_OK={s['tp_ok']} bad_target={s['bad_target']} "
        f"bad_source={s['bad_source']} pnl_below_target={s['pnl_below']}"
    )
print()

print("=== Détail TP_OK ===")
for e in events:
    print("-" * 120)
    print(
        f"{e['log']}:{e['line']} | {e['asset']} | open={e['open']} "
        f"expected={e['expected']} target={e['target']} pnl={e['pnl']} "
        f"source={e['source']} "
        f"ok_target={e['ok_target']} ok_source={e['ok_source']} ok_pnl={e['ok_pnl']}"
    )
    if e["ctx_line"]:
        print("CTX:", e["ctx_line"])
    print("TP :", e["tp_line"])

print()
print("=" * 120)
print("LECTURE")
print("=" * 120)
print("open=1 doit viser 0.20")
print("open=2 doit viser 0.40")
print("open=3 doit viser 0.60")
print("La preuve est complète seulement si on observe TP_OK pour chaque open_count avec source=BROKER_POSITION_UPL.")
