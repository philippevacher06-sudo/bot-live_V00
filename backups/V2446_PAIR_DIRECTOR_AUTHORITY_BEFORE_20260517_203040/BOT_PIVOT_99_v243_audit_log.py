#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Audit log non invasif pour BOT-PIVOT / Bot Pivot Bollinger V24.3.x.

Ce module :
- ne lit pas le .env
- n'appelle pas l'API broker
- n'envoie aucun ordre
- ne ferme aucune position
- ne modifie aucun état JSON
- analyse seulement les logs locaux
"""

import re
from pathlib import Path
from datetime import datetime
from collections import Counter, deque


ASSETS = [
    "US500", "US100", "US30", "DE40", "FR40", "UK100", "J225",
    "EURUSD", "GBPUSD", "USDJPY", "EURJPY",
    "GOLD", "SILVER", "OIL_CRUDE", "BTCUSD", "ETHUSD"
]

MICROTOUCHES = [
    "BASKET_TP_LADDER_CHECK",
    "BOLLINGER_WIDTH_OBSERVE",
    "BOLLINGER_ENTRY_OBSERVE",
    "BROKER_EMPTY_RESET",
    "REFRESH_06C_RATE_LIMIT",
    "RateLimitError",
]

EVENTS = [
    "OPEN_L1",
    "PRICE_AUDIT",
    "BOLLINGER_M5",
    "BOLLINGER_WIDTH_OBSERVE",
    "BOLLINGER_ENTRY_OBSERVE",
    "BOLLINGER_TOO_FAR",
    "BOLLINGER_WIDTH_TOO_SMALL",
    "MARKETABLE_LIMIT",
    "LIMIT_OK",
    "LIMIT_REJECT",
    "BASKET_NEW",
    "BASKET_FILL",
    "BASKET_TP_LADDER_CHECK",
    "BASKET_TP_OK",
    "BASKET_TP_BLOCKED",
    "BASKET_TP_BLOCKED_BROKER_UPL",
    "BASKET_PENDING_CANCEL",
    "BASKET_PARTIAL_CANCEL",
    "BASKET_REJECT",
    "BASKET_KEEP",
    "BROKER_EMPTY_RESET",
    "PNL_AUDIT_TOTAL",
    "GLOBAL_AIRBAG_STOP",
    "MAX_LOSS",
    "STORM",
    "MARGIN",
]

SEVERE_PATTERNS = [
    "Traceback",
    "ERROR",
    "Exception",
    "SyntaxError",
    "NameError",
    "TypeError",
    "KeyError",
    "ValueError",
    "CRITICAL",
]


def latest_log():
    logs_dir = Path("logs")
    files = sorted(
        logs_dir.glob("BOT_PIVOT_07D_24_7_DEMO_*.log"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return None
    return files[0]


def read_text_lines(path: Path):
    try:
        return path.read_text(errors="ignore").splitlines()
    except Exception as exc:
        return [f"READ_ERROR {path}: {exc}"]


def asset_for_line(line: str):
    for asset in ASSETS:
        if line.startswith(asset):
            return asset
        if line.startswith(f"{asset:<10s}"):
            return asset
        if re.match(rf"^{re.escape(asset)}\s+\|", line):
            return asset
    return None


def parse_kv(line: str):
    """
    Parse les fragments key=value présents dans une ligne de log.
    Exemple : width=77.53955 required=30.00000 ratio=2.585 ok=True
    """
    out = {}
    pattern = r"([A-Za-z_][A-Za-z0-9_]*)=('[^']*'|\"[^\"]*\"|[^\s|,;]+)"
    for key, value in re.findall(pattern, line):
        value = value.strip().strip("'").strip('"')
        out[key] = value
    return out


def as_float(value):
    try:
        if value is None:
            return None
        value = str(value).replace(",", ".")
        return float(value)
    except Exception:
        return None


def short_line(line: str, max_len=210):
    line = line.replace("\t", " ").strip()
    if len(line) <= max_len:
        return line
    return line[:max_len - 3] + "..."


class Report:
    def __init__(self):
        self.rows = []

    def emit(self, text=""):
        self.rows.append(str(text))

    def section(self, title):
        self.emit("")
        self.emit("=" * 160)
        self.emit(title)
        self.emit("=" * 160)

    def subsection(self, title):
        self.emit("")
        self.emit("-" * 160)
        self.emit(title)
        self.emit("-" * 160)

    def text(self):
        return "\n".join(self.rows)


def classify_asset(stats):
    if stats["BASKET_TP_OK"] > 0 or stats["BASKET_FILL"] > 0:
        return "VIT_REELLEMENT"
    if stats["BASKET_NEW"] > 0 or stats["LIMIT_OK"] > 0:
        return "POSE_DES_LIMITS"
    if stats["OPEN_L1"] > 0 and (
        stats["BASKET_REJECT"] > 0
        or stats["BOLLINGER_TOO_FAR"] > 0
        or stats["BOLLINGER_WIDTH_TOO_SMALL"] > 0
        or stats["MARKETABLE_LIMIT"] > 0
    ):
        return "SIGNAUX_MAIS_REJETES"
    if stats["OPEN_L1"] > 0:
        return "SIGNAUX_OPEN_L1"
    if stats["SIGNAL_ROWS"] > 0:
        return "DORT_MAIS_ANALYSE"
    return "INVISIBLE"


def audit_log(log_path: Path, args, report: Report):
    lines = read_text_lines(log_path)

    report.section("AUDIT BOT-PIVOT V24.3.x - LOG")
    report.emit(f"Date audit              : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.emit(f"Log analysé             : {log_path}")
    report.emit(f"Nombre de lignes         : {len(lines)}")
    if lines:
        report.emit(f"Première ligne           : {short_line(lines[0])}")
        report.emit(f"Dernière ligne           : {short_line(lines[-1])}")

    stats = {asset: Counter() for asset in ASSETS}
    micro_counts = Counter()
    severe_counts = Counter()
    severe_lines = []
    recent_by_asset = {asset: deque(maxlen=args.tail_events) for asset in ASSETS}
    width_obs = {asset: deque(maxlen=8) for asset in ASSETS}
    entry_obs = {asset: deque(maxlen=12) for asset in ASSETS}
    ladder_obs = {asset: deque(maxlen=8) for asset in ASSETS}
    margin_guard_lines = deque(maxlen=30)
    global_recent = deque(maxlen=args.tail_global)

    for idx, line in enumerate(lines, 1):
        asset = asset_for_line(line)

        for pat in SEVERE_PATTERNS:
            if pat in line:
                severe_counts[pat] += 1
                severe_lines.append((idx, line))

        for mt in MICROTOUCHES:
            if mt in line:
                micro_counts[mt] += 1

        if any(k in line for k in ["MARGIN", "STORM", "MAX_LOSS", "GLOBAL_AIRBAG_STOP"]):
            margin_guard_lines.append((idx, line))

        if asset:
            if re.search(r"\|\s+BUY\b", line):
                stats[asset]["BUY_ROWS"] += 1
                stats[asset]["SIGNAL_ROWS"] += 1
            elif re.search(r"\|\s+SELL\b", line):
                stats[asset]["SELL_ROWS"] += 1
                stats[asset]["SIGNAL_ROWS"] += 1
            elif re.search(r"\|\s+WAIT\b", line):
                stats[asset]["WAIT_ROWS"] += 1
                stats[asset]["SIGNAL_ROWS"] += 1

            matched_event = False
            for ev in EVENTS:
                if ev in line:
                    stats[asset][ev] += 1
                    matched_event = True

            if matched_event:
                recent_by_asset[asset].append((idx, line))
                global_recent.append((idx, line))

            if "BOLLINGER_WIDTH_OBSERVE" in line:
                width_obs[asset].append((idx, parse_kv(line), line))

            if "BOLLINGER_ENTRY_OBSERVE" in line:
                entry_obs[asset].append((idx, parse_kv(line), line))

            if "BASKET_TP_LADDER_CHECK" in line:
                ladder_obs[asset].append((idx, parse_kv(line), line))

    report.subsection("Santé générale du log")
    if not severe_counts:
        report.emit("OK santé : aucun Traceback / ERROR / Exception / SyntaxError / NameError / TypeError détecté.")
    else:
        report.emit("ATTENTION : anomalies détectées.")
        for key, count in severe_counts.most_common():
            report.emit(f"{key:20s} : {count}")
        report.emit("")
        report.emit("Dernières anomalies :")
        for idx, line in severe_lines[-30:]:
            report.emit(f"L{idx:<8d} {short_line(line)}")

    report.subsection("Présence des microtouches V24.3.1")
    for mt in MICROTOUCHES:
        count = micro_counts.get(mt, 0)
        status = "OK" if count > 0 else "ABSENT_SUR_CE_LOG"
        report.emit(f"{mt:35s} : {count:6d} | {status}")

    report.subsection("Couverture et activité par actif")
    header = (
        f"{'ACTIF':10s} | {'SIG':>5s} | {'BUY':>5s} | {'SELL':>5s} | {'WAIT':>5s} | "
        f"{'OPEN':>5s} | {'NEW':>4s} | {'LIM':>4s} | {'FILL':>5s} | {'TP':>3s} | "
        f"{'TP_BLK':>6s} | {'REJ':>5s} | {'TOO_FAR':>7s} | {'W_SMALL':>7s} | "
        f"{'MKT':>4s} | {'PEND_CAN':>8s} | STATUT"
    )
    report.emit(header)
    report.emit("-" * len(header))

    invisible = []
    dormant = []
    rejected = []
    limit_assets = []
    real_assets = []

    for asset in ASSETS:
        s = stats[asset]
        statut = classify_asset(s)

        if statut == "INVISIBLE":
            invisible.append(asset)
        elif statut == "DORT_MAIS_ANALYSE":
            dormant.append(asset)
        elif statut == "SIGNAUX_MAIS_REJETES":
            rejected.append(asset)
        elif statut == "POSE_DES_LIMITS":
            limit_assets.append(asset)
        elif statut == "VIT_REELLEMENT":
            real_assets.append(asset)

        report.emit(
            f"{asset:10s} | "
            f"{s['SIGNAL_ROWS']:5d} | "
            f"{s['BUY_ROWS']:5d} | "
            f"{s['SELL_ROWS']:5d} | "
            f"{s['WAIT_ROWS']:5d} | "
            f"{s['OPEN_L1']:5d} | "
            f"{s['BASKET_NEW']:4d} | "
            f"{s['LIMIT_OK']:4d} | "
            f"{s['BASKET_FILL']:5d} | "
            f"{s['BASKET_TP_OK']:3d} | "
            f"{s['BASKET_TP_BLOCKED'] + s['BASKET_TP_BLOCKED_BROKER_UPL']:6d} | "
            f"{s['BASKET_REJECT']:5d} | "
            f"{s['BOLLINGER_TOO_FAR']:7d} | "
            f"{s['BOLLINGER_WIDTH_TOO_SMALL']:7d} | "
            f"{s['MARKETABLE_LIMIT']:4d} | "
            f"{s['BASKET_PENDING_CANCEL']:8d} | "
            f"{statut}"
        )

    report.emit("")
    report.emit(f"Actifs invisibles             : {', '.join(invisible) if invisible else 'aucun'}")
    report.emit(f"Actifs dormants analysés      : {', '.join(dormant) if dormant else 'aucun'}")
    report.emit(f"Actifs avec signaux rejetés   : {', '.join(rejected) if rejected else 'aucun'}")
    report.emit(f"Actifs qui posent des LIMIT   : {', '.join(limit_assets) if limit_assets else 'aucun'}")
    report.emit(f"Actifs avec fills / TP        : {', '.join(real_assets) if real_assets else 'aucun'}")

    report.subsection("Résumé global lifecycle")
    global_life = Counter()
    for asset in ASSETS:
        for ev in EVENTS:
            global_life[ev] += stats[asset][ev]

    important = [
        "OPEN_L1",
        "LIMIT_OK",
        "LIMIT_REJECT",
        "BASKET_NEW",
        "BASKET_FILL",
        "BASKET_TP_LADDER_CHECK",
        "BASKET_TP_OK",
        "BASKET_TP_BLOCKED",
        "BASKET_TP_BLOCKED_BROKER_UPL",
        "BASKET_PENDING_CANCEL",
        "BASKET_REJECT",
        "BOLLINGER_TOO_FAR",
        "BOLLINGER_WIDTH_TOO_SMALL",
        "MARKETABLE_LIMIT",
        "BROKER_EMPTY_RESET",
    ]
    for ev in important:
        report.emit(f"{ev:35s} : {global_life[ev]:6d}")

    report.subsection("Simulation V24.3.2 - LIMIT_ARMING_DISTANCE sur BOLLINGER_ENTRY_OBSERVE")
    report.emit(f"Règle simulée : distance_to_L1 <= step × {args.arm_mult}")
    report.emit("Lecture : si dist/step > curseur, le panier aurait été retardé en V24.3.2.")
    report.emit("")

    found_entry = False
    header = (
        f"{'ACTIF':10s} | {'LIGNE':>8s} | {'L1':>14s} | {'L2':>14s} | "
        f"{'STEP':>12s} | {'DIST':>12s} | {'DIST/STEP':>10s} | {'DECISION V24.3.2':>18s}"
    )
    report.emit(header)
    report.emit("-" * len(header))

    for asset in ASSETS:
        for idx, kv, raw in list(entry_obs[asset]):
            l1 = as_float(kv.get("L1"))
            l2 = as_float(kv.get("L2"))
            dist = as_float(kv.get("dist"))

            if l1 is not None and l2 is not None:
                step = abs(l2 - l1)
            else:
                step = None

            if step and step > 0 and dist is not None:
                ratio = dist / step
                decision = "AUTORISER" if ratio <= args.arm_mult else "RETARDER"
                found_entry = True
                report.emit(
                    f"{asset:10s} | {idx:8d} | {l1:14.6f} | {l2:14.6f} | "
                    f"{step:12.6f} | {dist:12.6f} | {ratio:10.3f} | {decision:>18s}"
                )
            else:
                found_entry = True
                report.emit(
                    f"{asset:10s} | {idx:8d} | {'?':>14s} | {'?':>14s} | "
                    f"{'?':>12s} | {'?':>12s} | {'?':>10s} | {'DONNEES_INCOMPLETES':>18s}"
                )

    if not found_entry:
        report.emit("Aucun BOLLINGER_ENTRY_OBSERVE trouvé sur ce log.")

    report.subsection("Dernières observations Bollinger width")
    found_width = False
    for asset in ASSETS:
        if not width_obs[asset]:
            continue
        found_width = True
        report.emit("")
        report.emit(f"{asset}:")
        for idx, kv, raw in list(width_obs[asset])[-5:]:
            width = kv.get("width", "?")
            required = kv.get("required", "?")
            ratio = kv.get("ratio", "?")
            ok = kv.get("ok", "?")
            report.emit(f"  L{idx:<8d} width={width} required={required} ratio={ratio} ok={ok}")

    if not found_width:
        report.emit("Aucun BOLLINGER_WIDTH_OBSERVE trouvé sur ce log.")

    report.subsection("Derniers contrôles TP ladder")
    found_ladder = False
    for asset in ASSETS:
        if not ladder_obs[asset]:
            continue
        found_ladder = True
        report.emit("")
        report.emit(f"{asset}:")
        for idx, kv, raw in list(ladder_obs[asset])[-5:]:
            open_legs = kv.get("open", kv.get("open_legs", "?"))
            target = kv.get("target", kv.get("expected_target", "?"))
            broker = kv.get("broker_upl", kv.get("upl", "?"))
            internal = kv.get("internal", "?")
            report.emit(f"  L{idx:<8d} open={open_legs} target={target} broker_upl={broker} internal={internal}")
            report.emit(f"           {short_line(raw, 260)}")

    if not found_ladder:
        report.emit("Aucun BASKET_TP_LADDER_CHECK trouvé sur ce log. Normal s'il n'y a eu aucun fill.")

    report.subsection("Guards / marge / storm / max loss")
    if margin_guard_lines:
        for idx, line in margin_guard_lines:
            report.emit(f"L{idx:<8d} {short_line(line)}")
    else:
        report.emit("Aucune ligne MARGIN / STORM / MAX_LOSS / GLOBAL_AIRBAG_STOP trouvée sur ce log.")

    report.subsection("Derniers événements globaux")
    if global_recent:
        for idx, line in global_recent:
            report.emit(f"L{idx:<8d} {short_line(line)}")
    else:
        report.emit("Aucun événement global détecté.")

    report.subsection("Derniers événements par actif")
    for asset in ASSETS:
        report.emit("")
        report.emit(f"{asset}:")
        if not recent_by_asset[asset]:
            report.emit("  Aucun événement récent.")
            continue
        for idx, line in recent_by_asset[asset]:
            report.emit(f"  L{idx:<8d} {short_line(line)}")
