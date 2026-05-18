from pathlib import Path
from collections import defaultdict, Counter, deque
from datetime import datetime, timezone
import re
import sys

ASSETS = [
    "US500","US100","US30","DE40","FR40","UK100","J225",
    "EURUSD","GBPUSD","USDJPY","EURJPY",
    "GOLD","SILVER","OIL_CRUDE","BTCUSD","ETHUSD"
]

def latest_log():
    logs = sorted(Path("logs").glob("BOT_PIVOT_07D_24_7_DEMO_*.log"))
    if not logs:
        raise SystemExit("Aucun log trouvé")
    return logs[-1]

log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_log()
lines = log_path.read_text(errors="ignore").splitlines()

cycle_re = re.compile(r"07D — CYCLE\s+(\d+)\s+—\s+([0-9T:\-]+Z)")
asset_re = re.compile(r"^([A-Z0-9_ ]{10}) \| ([A-Z0-9_]+)")
fill_re = re.compile(r"\| BASKET_FILL \|\s+(\d+)")
limit_re = re.compile(r"\| (LIMIT_REQUEST|LIMIT_OK|LIMIT_REJECT)\s+\|\s+(\d+)")
ladder_re = re.compile(
    r"BASKET_TP_LADDER_CHECK.*open=(\d+) expected_target=([0-9.]+).*"
    r"broker_upl=(none|-?[0-9.]+).*tp_pnl=(none|-?[0-9.]+).*"
    r"broker_count=(\d+)/(\d+).*decision=([A-Z_]+)"
)
tp_matrix_re = re.compile(
    r"(TP_MATRIX_TRIGGER|TP_MATRIX_CLOSE_OK|TP_MATRIX_CLOSE_FAIL).*"
    r"open=(\d+) expected_target=([0-9.]+).*broker_upl=(-?[0-9.]+).*"
)
bb_re = re.compile(
    r"BOLLINGER_ENTRY_OBSERVE.*\|\s+(BUY|SELL)\s+\|.*"
    r"width=([0-9.]+) required=([0-9.]+).*"
    r"dist=([0-9.]+).*dist_ratio=([0-9.]+)"
)
arming_re = re.compile(
    r"BASKET_ARMING_DELAYED.*dist_step_ratio=([0-9.]+).*mult=([0-9.]+)"
)

global_counts = Counter()
asset_counts = {a: Counter() for a in ASSETS}
asset_last = {a: deque(maxlen=12) for a in ASSETS}
last_events = deque(maxlen=80)

cycles = []
errors = []
bb_stats = defaultdict(list)
arming_stats = defaultdict(list)
tp_ladder_samples = defaultdict(list)
tp_matrix_samples = defaultdict(list)

for idx, line in enumerate(lines, start=1):
    m = cycle_re.search(line)
    if m:
        cycles.append((int(m.group(1)), m.group(2), idx))
        global_counts["cycles"] += 1
        continue

    if re.search(r"Traceback|ERROR|Exception|SyntaxError|NameError|TypeError|IndentationError", line):
        errors.append((idx, line))

    am = asset_re.search(line)
    if not am:
        continue

    asset = am.group(1).strip()
    event = am.group(2).strip()
    if asset not in asset_counts:
        continue

    asset_counts[asset][event] += 1
    global_counts[event] += 1

    important = any(k in line for k in [
        "BASKET_NEW", "BASKET_FILL", "BASKET_TP_OK",
        "TP_MATRIX_TRIGGER", "TP_MATRIX_CLOSE_OK", "TP_MATRIX_CLOSE_FAIL",
        "BASKET_TP_BLOCKED", "LIMIT_REJECT", "BASKET_L123",
        "BASKET_ARMING_DELAYED", "BOLLINGER_ENTRY_OBSERVE",
        "V2437_BB_DISTANCE_AUDIT",
        "V2437_ORDER_INTENT", "V2437_ORDER_RESPONSE",
        "V2437_ORDER_ACCEPTED", "V2437_ORDER_REJECTED",
        "V2437_EXIT_CLEANUP_BEFORE", "V2437_EXIT_CLEANUP_OK",
        "V2437_EXIT_CLEANUP_FAILED_PENDING_STILL_ALIVE",
        "V2437_RECONCILE_AFTER_EXIT_CLEANUP",
        "BASKET_PARTIAL_PENDING_CANCEL", "BASKET_PARTIAL_PENDING_KEEP",
        "BASKET_PENDING_CANCEL"
    ])
    if important:
        asset_last[asset].append((idx, line))
        last_events.append((idx, line))

    lm = limit_re.search(line)
    if lm:
        evt, lvl = lm.group(1), lm.group(2)
        asset_counts[asset][f"{evt}_L{lvl}"] += 1
        global_counts[f"{evt}_L{lvl}"] += 1

    fm = fill_re.search(line)
    if fm:
        lvl = fm.group(1)
        asset_counts[asset][f"BASKET_FILL_L{lvl}"] += 1
        global_counts[f"BASKET_FILL_L{lvl}"] += 1

    bm = bb_re.search(line)
    if bm:
        direction, width, required, dist, dist_ratio = bm.groups()
        bb_stats[asset].append({
            "direction": direction,
            "width": float(width),
            "required": float(required),
            "dist": float(dist),
            "dist_ratio": float(dist_ratio),
            "line": idx,
        })

    arm = arming_re.search(line)
    if arm:
        ratio, mult = arm.groups()
        arming_stats[asset].append({
            "ratio": float(ratio),
            "mult": float(mult),
            "line": idx,
        })

    lad = ladder_re.search(line)
    if lad:
        open_count, target, broker_upl, tp_pnl, bc1, bc2, decision = lad.groups()
        key = f"open={open_count} target={target} decision={decision}"
        asset_counts[asset][f"TP_LADDER_{key}"] += 1
        global_counts[f"TP_LADDER_{key}"] += 1
        if len(tp_ladder_samples[key]) < 5:
            tp_ladder_samples[key].append((idx, line))

    tm = tp_matrix_re.search(line)
    if tm:
        evt, open_count, target, broker_upl = tm.groups()
        key = f"{evt} open={open_count} target={target}"
        asset_counts[asset][key] += 1
        global_counts[key] += 1
        if len(tp_matrix_samples[key]) < 5:
            tp_matrix_samples[key].append((idx, line))

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

duration_min = None
if len(cycles) >= 2:
    start_dt = parse_dt(cycles[0][1])
    end_dt = parse_dt(cycles[-1][1])
    duration_min = max(0.01, (end_dt - start_dt).total_seconds() / 60)

def rate(n):
    if not duration_min:
        return "n/a"
    return f"{n / duration_min * 60:.2f}/h"

print("=" * 140)
print("BOT-PIVOT — DASHBOARD LOG")
print("=" * 140)
print(f"LOG              : {log_path}")
print(f"LIGNES           : {len(lines)}")
print(f"CYCLES           : {global_counts['cycles']}")
if cycles:
    print(f"PREMIER CYCLE    : {cycles[0][0]} — {cycles[0][1]}")
    print(f"DERNIER CYCLE    : {cycles[-1][0]} — {cycles[-1][1]}")
if duration_min:
    print(f"DUREE LOG        : {duration_min:.1f} min")
    print(f"RYTHME CYCLES    : {rate(global_counts['cycles'])}")
print(f"ERREURS          : {len(errors)}")
print()

print("=" * 140)
print("SYNTHESE FREQUENCE")
print("=" * 140)
for k in [
    "BASKET_NEW",
    "BASKET_FILL",
    "BASKET_FILL_L1",
    "BASKET_FILL_L2",
    "BASKET_FILL_L3",
    "BASKET_TP_OK",
    "TP_MATRIX_TRIGGER",
    "TP_MATRIX_CLOSE_OK",
    "TP_MATRIX_CLOSE_FAIL",
    "BASKET_TP_BLOCKED_BROKER_UPL",
    "BASKET_TP_BLOCKED_NO_BROKER_UPL",
    "BASKET_PARTIAL_PENDING_KEEP",
    "BASKET_PARTIAL_PENDING_CANCEL",
    "BASKET_PENDING_CANCEL",
    "BASKET_ARMING_DELAYED",
    "V2437_BB_DISTANCE_AUDIT",
    "V2437_ORDER_INTENT",
    "V2437_ORDER_RESPONSE",
    "V2437_ORDER_ACCEPTED",
    "V2437_ORDER_REJECTED",
    "V2437_EXIT_CLEANUP_BEFORE",
    "V2437_EXIT_CLEANUP_OK",
    "V2437_EXIT_CLEANUP_FAILED_PENDING_STILL_ALIVE",
    "V2437_RECONCILE_AFTER_EXIT_CLEANUP",
    "BASKET_REJECT",
    "BOLLINGER_ENTRY_OBSERVE",
    "LIMIT_REQUEST",
    "LIMIT_OK",
    "LIMIT_REJECT",
    "BASKET_L123_ABORT_L1_REJECT",
    "BASKET_L123_ATOMIC_CANCEL",
]:
    print(f"{k:35s} {global_counts[k]:6d}   {rate(global_counts[k])}")

print()
print("=" * 140)
print("PAR ACTIF — FLUX L1/L2/L3 / TP / REJETS")
print("=" * 140)
header = (
    f"{'ACTIF':10s} {'NEW':>4s} {'FILL':>4s} "
    f"{'F1':>3s} {'F2':>3s} {'F3':>3s} "
    f"{'TP':>3s} {'MTRIG':>5s} {'MCLOSE':>6s} "
    f"{'BLOCK':>5s} {'BB':>4s} {'ARM':>4s} {'LREJ':>5s} {'L123':>5s} {'PCAN':>5s}"
)
print(header)
print("-" * len(header))

for asset in ASSETS:
    c = asset_counts[asset]
    block = c["BASKET_TP_BLOCKED_BROKER_UPL"] + c["BASKET_TP_BLOCKED_NO_BROKER_UPL"]
    lrej = c["LIMIT_REJECT"]
    l123 = c["BASKET_L123_ABORT_L1_REJECT"] + c["BASKET_L123_ATOMIC_CANCEL"]
    mclose = sum(v for k, v in c.items() if k.startswith("TP_MATRIX_CLOSE_OK"))
    mtrig = sum(v for k, v in c.items() if k.startswith("TP_MATRIX_TRIGGER"))
    print(
        f"{asset:10s} {c['BASKET_NEW']:4d} {c['BASKET_FILL']:4d} "
        f"{c['BASKET_FILL_L1']:3d} {c['BASKET_FILL_L2']:3d} {c['BASKET_FILL_L3']:3d} "
        f"{c['BASKET_TP_OK']:3d} {mtrig:5d} {mclose:6d} "
        f"{block:5d} {c['BOLLINGER_ENTRY_OBSERVE']:4d} {c['BASKET_ARMING_DELAYED']:4d} "
        f"{lrej:5d} {l123:5d} {c['BASKET_PARTIAL_PENDING_CANCEL']:5d}"
    )

print()
print("=" * 140)
print("BOLLINGER — DERNIERES OBSERVATIONS")
print("=" * 140)
for asset in ASSETS:
    if not bb_stats[asset]:
        continue
    last = bb_stats[asset][-1]
    avg_dist_ratio = sum(x["dist_ratio"] for x in bb_stats[asset]) / len(bb_stats[asset])
    print(
        f"{asset:10s} count={len(bb_stats[asset]):3d} "
        f"last_dir={last['direction']:4s} width={last['width']:.6f} required={last['required']:.6f} "
        f"dist_ratio_last={last['dist_ratio']:.3f} dist_ratio_avg={avg_dist_ratio:.3f} line={last['line']}"
    )

print()
print("=" * 140)
print("ARMING DELAYED — DISTANCE L1 TROP LOIN")
print("=" * 140)
for asset in ASSETS:
    if not arming_stats[asset]:
        continue
    last = arming_stats[asset][-1]
    avg_ratio = sum(x["ratio"] for x in arming_stats[asset]) / len(arming_stats[asset])
    print(
        f"{asset:10s} count={len(arming_stats[asset]):3d} "
        f"ratio_last={last['ratio']:.3f} ratio_avg={avg_ratio:.3f} mult={last['mult']:.3f} line={last['line']}"
    )

print()
print("=" * 140)
print("TP MATRIX — PREUVES TP")
print("=" * 140)
for key in sorted(tp_matrix_samples):
    print("-" * 140)
    print(key)
    for idx, line in tp_matrix_samples[key]:
        print(f"{idx}: {line}")

print()
print("=" * 140)
print("TP LADDER — ECHANTILLONS")
print("=" * 140)
for key in sorted(tp_ladder_samples):
    print("-" * 140)
    print(key)
    for idx, line in tp_ladder_samples[key]:
        print(f"{idx}: {line}")

print()
print("=" * 140)
print("DERNIERS EVENEMENTS IMPORTANTS")
print("=" * 140)
for idx, line in last_events:
    print(f"{idx}: {line}")

print()
print("=" * 140)
print("SANTE")
print("=" * 140)
if errors:
    for idx, line in errors[-30:]:
        print(f"{idx}: {line}")
else:
    print("Aucune erreur critique détectée dans ce log.")
