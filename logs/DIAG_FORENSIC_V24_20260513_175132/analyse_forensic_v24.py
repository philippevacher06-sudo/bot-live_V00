from pathlib import Path
import re, json
from collections import Counter, defaultdict

ROOT = Path(".")
logs = sorted(Path("logs").glob("BOT_PIVOT_07D_24_7_DEMO_*.log"), key=lambda p: p.stat().st_mtime)

assets = [
    "US500","US100","US30","DE40","FR40","UK100","J225",
    "EURUSD","GBPUSD","USDJPY","EURJPY","GOLD","SILVER",
    "OIL_CRUDE","BTCUSD","ETHUSD"
]

events = [
    "OPEN_L1","LIMIT_REQUEST","LIMIT_OK","LIMIT_REJECT",
    "BASKET_NEW","BASKET_ID_OK","BASKET_HOLD","BASKET_FILL",
    "PNL_AUDIT_TOTAL","BASKET_TP_OK","BASKET_TP_FAIL",
    "BASKET_PENDING_CANCEL","BASKET_PARTIAL_PENDING_CANCEL","BASKET_REJECT",
    "CLOSE","CLOSE_OK","CLOSE_FAIL",
    "V24_OPEN_BASKET_OPPOSITE_SIGNAL_CLOSE",
    "V24_OPEN_BASKET_SIGNAL_LOST_CLOSE",
    "V24_OPEN_BASKET_PHASE_VWAP_AGAINST_CLOSE",
    "V24_OPEN_BASKET_BREAKOUT_AGAINST_CLOSE",
    "V24_DYNAMIC_STOP_DISTANCE",
    "V24_WORKING_ORDER_RETRY",
    "V24_WORKING_ORDER_SECOND_RETRY",
    "V24_WORKING_ORDER_SECOND_RETRY_RESULT",
    "Traceback","ERROR","Exception","429","too-many.requests",
]

stats = {a: Counter() for a in assets}
pnl_rows = defaultdict(list)
all_lines = []

def parse_float(pattern, text):
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None

def parse_int(pattern, text):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None

for log in logs:
    try:
        lines = log.read_text(errors="ignore").splitlines()
    except Exception:
        continue

    for i, line in enumerate(lines, 1):
        all_lines.append((log.name, i, line))

        for a in assets:
            if a in line:
                for ev in events:
                    if ev in line:
                        stats[a][ev] += 1

                if "PNL_AUDIT_TOTAL" in line:
                    row = {
                        "asset": a,
                        "log": log.name,
                        "line": i,
                        "open": parse_int(r"open=(\d+)", line),
                        "pnl": parse_float(r"pnl=([-+]?\d+(?:\.\d+)?)", line),
                        "target": parse_float(r"target=([-+]?\d+(?:\.\d+)?)", line),
                        "text": line,
                    }
                    if row["pnl"] is not None:
                        pnl_rows[a].append(row)

print("="*150)
print("RAPPORT FORENSIC V24 OFFLINE")
print("="*150)
print()

print("LOGS ANALYSÉS")
print("-"*150)
for log in logs:
    print(f"{log} | {log.stat().st_size/1024:.1f} KB")
print()

print("ÉTAT LOCAL JSON — SANS API BROKER")
print("-"*150)
for label, path in [
    ("cycle_state", Path("data/cycles/cycle_state.json")),
    ("execution_state", Path("data/execution/cycle_execution_state.json")),
    ("signals_latest", Path("data/ticks/signals_latest.json")),
]:
    print()
    print(f"### {label}: {path}")
    if not path.exists():
        print("Fichier absent.")
        continue
    try:
        data = json.loads(path.read_text(errors="ignore"))
        if label == "cycle_state":
            assets_state = data.get("assets", {})
            non_idle = {a:s for a,s in assets_state.items() if s.get("status") != "IDLE"}
            print("updated_utc:", data.get("updated_utc"))
            print("non-IDLE:", list(non_idle.keys()))
            for a,s in non_idle.items():
                print(a, json.dumps(s, ensure_ascii=False)[:1200])
        elif label == "execution_state":
            active = data.get("active", {})
            print("active:", list(active.keys()))
            for a,r in active.items():
                print(a, json.dumps(r, ensure_ascii=False)[:1600])
        else:
            if isinstance(data, list):
                print("signals count:", len(data))
                for r in data[:5]:
                    print(json.dumps(r, ensure_ascii=False)[:800])
            else:
                print(json.dumps(data, ensure_ascii=False)[:2000])
    except Exception as e:
        print("Erreur lecture JSON:", e)

print()
print("="*150)
print("TABLEAU GLOBAL PAR ACTIF")
print("="*150)
header = (
    f"{'ACTIF':10s} {'OPEN':>5s} {'OK':>5s} {'REJ':>5s} {'NEW':>5s} {'HOLD':>5s} "
    f"{'FILL':>5s} {'PNL':>5s} {'TP_OK':>6s} {'TP_FAIL':>7s} {'PEND_CAN':>9s} "
    f"{'REJECT':>7s} {'CLOSES':>7s} {'DYNSTOP':>7s} {'2RETRY':>7s}"
)
print(header)
print("-"*len(header))

for a in assets:
    s = stats[a]
    close_total = s["CLOSE"] + s["CLOSE_OK"] + s["CLOSE_FAIL"]
    total = sum(s.values()) + len(pnl_rows[a])
    if total == 0:
        continue
    print(
        f"{a:10s} "
        f"{s['OPEN_L1']:5d} {s['LIMIT_OK']:5d} {s['LIMIT_REJECT']:5d} "
        f"{s['BASKET_NEW']:5d} {s['BASKET_HOLD']:5d} {s['BASKET_FILL']:5d} "
        f"{s['PNL_AUDIT_TOTAL']:5d} {s['BASKET_TP_OK']:6d} {s['BASKET_TP_FAIL']:7d} "
        f"{s['BASKET_PENDING_CANCEL']:9d} {s['BASKET_REJECT']:7d} {close_total:7d} "
        f"{s['V24_DYNAMIC_STOP_DISTANCE']:7d} {s['V24_WORKING_ORDER_SECOND_RETRY']:7d}"
    )

print()
print("="*150)
print("PNL MAX / MIN / DERNIER VU PAR LE BOT")
print("="*150)
for a in assets:
    rows = pnl_rows[a]
    if not rows:
        continue
    best = max(rows, key=lambda r: r["pnl"])
    worst = min(rows, key=lambda r: r["pnl"])
    last = rows[-1]
    hit = [r for r in rows if r["target"] is not None and r["pnl"] >= r["target"]]
    print()
    print(f"{a}")
    print(f"  lectures PNL : {len(rows)}")
    print(f"  MAX  pnl={best['pnl']} open={best['open']} target={best['target']} | {best['log']}:{best['line']}")
    print(f"       {best['text']}")
    print(f"  MIN  pnl={worst['pnl']} open={worst['open']} target={worst['target']} | {worst['log']}:{worst['line']}")
    print(f"       {worst['text']}")
    print(f"  LAST pnl={last['pnl']} open={last['open']} target={last['target']} | {last['log']}:{last['line']}")
    print(f"       {last['text']}")
    print(f"  PNL >= target vus par le bot : {len(hit)}")
    for r in hit[-10:]:
        print(f"       HIT {r['log']}:{r['line']} pnl={r['pnl']} target={r['target']} | {r['text']}")

print()
print("="*150)
print("SUSPECTS — PNL >= TARGET SANS TP_OK RAPIDE")
print("="*150)
for a, rows in pnl_rows.items():
    for r in rows:
        if r["target"] is None or r["pnl"] < r["target"]:
            continue
        # Cherche TP_OK dans les 80 lignes suivantes du même log pour le même actif
        found = False
        for log_name, ln, line in all_lines:
            if log_name == r["log"] and r["line"] < ln <= r["line"] + 80 and a in line and "BASKET_TP_OK" in line:
                found = True
                break
        if not found:
            print(f"{a} | {r['log']}:{r['line']} | pnl={r['pnl']} target={r['target']} <<< PAS DE TP_OK DANS LES 80 LIGNES")
            print("   ", r["text"])

print()
print("="*150)
print("SUSPECTS — TP_OK ALORS QUE DERNIER PNL CONNU < TARGET")
print("="*150)
last_pnl = {}
for log_name, ln, line in all_lines:
    for a in assets:
        if a not in line:
            continue
        if "PNL_AUDIT_TOTAL" in line:
            row = {
                "log": log_name,
                "line": ln,
                "open": parse_int(r"open=(\d+)", line),
                "pnl": parse_float(r"pnl=([-+]?\d+(?:\.\d+)?)", line),
                "target": parse_float(r"target=([-+]?\d+(?:\.\d+)?)", line),
                "text": line,
            }
            if row["pnl"] is not None:
                last_pnl[a] = row
        if "BASKET_TP_OK" in line:
            prev = last_pnl.get(a)
            print()
            print(f"{log_name}:{ln}:{line}")
            if prev:
                flag = ""
                if prev["target"] is not None and prev["pnl"] < prev["target"]:
                    flag = " <<< SUSPECT"
                print(f"  Dernier PNL: pnl={prev['pnl']} target={prev['target']} open={prev['open']} {flag}")
                print(f"  {prev['log']}:{prev['line']}:{prev['text']}")
            else:
                print("  Aucun PNL précédent trouvé.")

print()
print("="*150)
print("FERMETURES / INVALIDATIONS / CANCELS")
print("="*150)
close_keys = [
    "BASKET_TP_OK","BASKET_TP_FAIL","CLOSE_OK","CLOSE_FAIL",
    "V24_OPEN_BASKET_OPPOSITE_SIGNAL_CLOSE",
    "V24_OPEN_BASKET_SIGNAL_LOST_CLOSE",
    "V24_OPEN_BASKET_PHASE_VWAP_AGAINST_CLOSE",
    "V24_OPEN_BASKET_BREAKOUT_AGAINST_CLOSE",
    "BASKET_PENDING_CANCEL","BASKET_PARTIAL_PENDING_CANCEL",
]
for log_name, ln, line in all_lines:
    if any(k in line for k in close_keys):
        print(f"{log_name}:{ln}:{line}")

print()
print("="*150)
print("REJETS / ERREURS BROKER / 429")
print("="*150)
err_keys = ["LIMIT_REJECT","invalid.stoploss","guaranteed-stop-loss","Traceback","ERROR","Exception","429","too-many.requests"]
for log_name, ln, line in all_lines:
    if any(k in line for k in err_keys):
        print(f"{log_name}:{ln}:{line}")

print()
print("="*150)
print("BLOCS CONTEXTE — GOLD / US30 / OIL_CRUDE / US500 / GBPUSD")
print("="*150)
focus_assets = ["GOLD","US30","OIL_CRUDE","US500","GBPUSD"]
focus_keys = ["OPEN_L1","BASKET_FILL","PNL_AUDIT_TOTAL","BASKET_TP_OK","BASKET_TP_FAIL","CLOSE","V24_OPEN_BASKET","BASKET_PENDING_CANCEL"]
for fa in focus_assets:
    print()
    print("#"*150)
    print("FOCUS", fa)
    print("#"*150)
    hits = []
    for idx, (log_name, ln, line) in enumerate(all_lines):
        if fa in line and any(k in line for k in focus_keys):
            hits.append((idx, log_name, ln, line))
    for idx, log_name, ln, line in hits[-25:]:
        print()
        print(f"--- {fa} autour de {log_name}:{ln} ---")
        for j in range(max(0, idx-8), min(len(all_lines), idx+12)):
            lgn, lno, txt = all_lines[j]
            if lgn == log_name:
                print(f"{lgn}:{lno}:{txt}")
