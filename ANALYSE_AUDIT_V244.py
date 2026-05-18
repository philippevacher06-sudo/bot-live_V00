#!/usr/bin/env python3
from __future__ import annotations

import ast
import glob
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

EVENT_RE = re.compile(r"(?:^|\s\|\s)event=([A-Z0-9_]+)")
TS_RE = re.compile(r"ts_utc=([0-9T:\-]+Z)")
FIELD_RE = re.compile(r"(?:^|\s\|\s)([a-zA-Z0-9_]+)=")

def latest_audit_log() -> Path:
    matches = glob.glob("logs/v24_4_forced_audit/V24_4_FORCED_AUDIT_*.log")
    if not matches:
        raise SystemExit("Aucun audit log trouve")
    return Path(max(matches, key=lambda p: Path(p).stat().st_mtime))

def parse_ts(line: str):
    m = TS_RE.search(line)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return None

def parse_event(line: str) -> str:
    m = EVENT_RE.search(line)
    return m.group(1) if m else "UNKNOWN"

def parse_fields(line: str) -> dict:
    matches = list(FIELD_RE.finditer(line))
    out = {}
    for i, m in enumerate(matches):
        key = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(line)
        value = line[start:end].strip()
        if value.endswith("|"):
            value = value[:-1].strip()
        out[key] = value
    return out

def as_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def literal_dict(text: str) -> dict:
    try:
        v = ast.literal_eval(text)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}

def minute_bucket(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%MZ")

log_path = latest_audit_log()
lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()

events = Counter()
starts = []
account_modes = []
opens = []
open_by_minute = Counter()
blocked = Counter()
close_losses = []
closes = []
gold_mentions = []
gold_suspicious = []
force_open_lines = []
order_type_lines = []
errors = []
locks = []
signal_biases = Counter()
signal_bars = Counter()
max_net_abs = 0.0
last_status = {}

for idx, line in enumerate(lines, start=1):
    event = parse_event(line)
    fields = parse_fields(line)
    ts = parse_ts(line)
    events[event] += 1

    if "GOLD" in line:
        gold_mentions.append((idx, event, line[:500]))
        if "CLOSE" in event or "DELETE" in line:
            gold_suspicious.append((idx, event, line[:700]))

    if "'forceOpen': True" in line or '"forceOpen": true' in line:
        force_open_lines.append((idx, event))

    if "'orderType': 'MARKET'" in line or '"orderType": "MARKET"' in line:
        order_type_lines.append((idx, event))

    if event == "RUNNER_V2442_NETTING_M15_START":
        starts.append((idx, fields))

    if event == "RUNNER_ACCOUNT_MODE":
        account_modes.append((idx, fields.get("hedgingMode"), fields.get("preferences", "")[:200]))

    if event == "RUNNER_M15_VWAP_SIGNAL":
        signal_biases[fields.get("bias", "UNKNOWN")] += 1
        if fields.get("signal_bar_ts"):
            signal_bars[fields["signal_bar_ts"]] += 1

    if event == "RUNNER_STATUS":
        last_status = fields
        max_net_abs = max(max_net_abs, abs(as_float(fields.get("net_exposure"))))

    if event == "RUNNER_OPEN_RESULT":
        info = literal_dict(fields.get("info", ""))
        side = fields.get("side")
        size = as_float(fields.get("size"))
        ok = fields.get("ok")
        net_after = as_float(info.get("net_after"))
        opens.append((idx, ts, side, size, ok, net_after))
        if ts and ok == "True":
            open_by_minute[minute_bucket(ts)] += 1

    if event == "RUNNER_OPEN_BLOCKED":
        blocked[fields.get("reason", "UNKNOWN")] += 1

    if event in {"RUNNER_CLOSE_BY_AGE", "RUNNER_WINNER_CLOSE_RESULT"}:
        closes.append((idx, event, line[:800]))
        m = re.search(r"'profit':\s*([-0-9.]+)", line)
        if m and as_float(m.group(1)) < 0:
            close_losses.append((idx, event, as_float(m.group(1)), line[:900]))

    if event in {"RUNNER_LOCKED", "RUNNER_HALTED_BY_LOCK"}:
        locks.append((idx, event, line[:700]))

    if "errorCode" in line or "429" in line or event == "RUNNER_EXCEPTION":
        errors.append((idx, event, line[:700]))

print("=" * 72)
print(f"AUDIT LOG: {log_path}")
print(f"LIGNES: {len(lines)}")
print("=" * 72)

print("\nDEMARRAGES")
for idx, f in starts[-8:]:
    print(f"ligne {idx}: target_openings_per_min={f.get('target_openings_per_min')} one_order_per_signal_bar={f.get('one_order_per_signal_bar')} close_winners_enabled={f.get('close_winners_enabled')} max_net_exposure={f.get('max_net_exposure')}")

print("\nMODE COMPTE")
for idx, hedging, prefs in account_modes[-5:]:
    print(f"ligne {idx}: hedgingMode={hedging} prefs={prefs}")

print("\nEVENEMENTS TOP 20")
for k, v in events.most_common(20):
    print(f"{k}: {v}")

print("\nOUVERTURES")
print(f"total RUNNER_OPEN_RESULT: {len(opens)}")
for idx, ts, side, size, ok, net_after in opens[-15:]:
    ts_s = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S") if ts else "?"
    print(f"ligne {idx}: {ts_s} {side} size={size} ok={ok} net_after={net_after}")

print("\nOUVERTURES PAR MINUTE")
for minute, count in open_by_minute.most_common(15):
    flag = "  ALERTE >2/min" if count > 2 else ""
    print(f"{minute}: {count}{flag}")

print("\nBLOCAGES")
for k, v in blocked.most_common():
    print(f"{k}: {v}")

print("\nSIGNAL")
for k, v in signal_biases.most_common():
    print(f"{k}: {v}")
print("bougies les plus repetees:")
for k, v in signal_bars.most_common(8):
    print(f"{k}: {v}")

print("\nEXPOSITION DERNIER ETAT")
print(f"max_abs_net_exposure={max_net_abs}")
if last_status:
    print(f"dernier: bias={last_status.get('signal_bias')} net={last_status.get('net_exposure')} side={last_status.get('net_side')} open_positions={last_status.get('open_positions')} opens_last_60s={last_status.get('opens_last_60s')}")

print("\nFERMETURES")
print(f"fermetures detectees: {len(closes)}")
print(f"fermetures perdantes detectees: {len(close_losses)}")
for idx, event, profit, snippet in close_losses[-10:]:
    print(f"ALERTE ligne {idx}: {event} profit={profit} :: {snippet}")

print("\nPAYLOAD")
print(f"forceOpen=True occurrences: {len(force_open_lines)}")
print(f"dernieres forceOpen: {force_open_lines[-8:]}")
print(f"orderType=MARKET occurrences: {len(order_type_lines)}")
print(f"dernieres orderType: {order_type_lines[-8:]}")

print("\nGOLD")
print(f"mentions GOLD: {len(gold_mentions)}")
print(f"actions GOLD suspectes close/delete: {len(gold_suspicious)}")
for idx, event, snippet in gold_suspicious[-10:]:
    print(f"ALERTE ligne {idx}: {event} :: {snippet}")

print("\nLOCKS / ERREURS")
print(f"locks: {len(locks)}")
for idx, event, snippet in locks[-10:]:
    print(f"ligne {idx}: {event} :: {snippet}")
print(f"erreurs/429/errorCode: {len(errors)}")
for idx, event, snippet in errors[-10:]:
    print(f"ligne {idx}: {event} :: {snippet}")

print("\nLECTURE RAPIDE")
if close_losses:
    print("PRIORITE: fermeture perdante detectee. Supprimer/desactiver toute logique CLOSE_BY_AGE.")
if gold_suspicious:
    print("ALERTE: action suspecte sur GOLD detectee.")
if open_by_minute and max(open_by_minute.values()) > 2:
    print("ALERTE: au moins une minute depasse 2 ouvertures.")
if force_open_lines:
    print("INFO: forceOpen apparait dans le log. Verifier que c'est uniquement avant le patch.")
if not close_losses and not gold_suspicious:
    print("OK: pas de fermeture perdante ni action GOLD suspecte detectee.")
