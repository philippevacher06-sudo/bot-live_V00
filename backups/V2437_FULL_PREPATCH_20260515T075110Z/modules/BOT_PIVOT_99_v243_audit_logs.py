#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BOT_PIVOT_99_v243_audit_logs.py

Lanceur non invasif pour BOT-PIVOT / Bot Pivot Bollinger V24.3.x.

Ce script :
- ne lit pas le .env
- n'appelle pas l'API broker
- n'envoie aucun ordre
- ne ferme aucune position
- ne modifie aucun état JSON
- analyse seulement les logs et fichiers d'état locaux
"""

import argparse
import json
import sys
from pathlib import Path
from collections import Counter

from BOT_PIVOT_99_v243_audit_log import (
    ASSETS,
    Report,
    audit_log,
    latest_log,
)


STATE_FILES = {
    "cycle_state": Path("data/cycles/cycle_state.json"),
    "execution_state": Path("data/execution/cycle_execution_state.json"),
    "signals_latest": Path("data/ticks/signals_latest.json"),
}


def read_json(path: Path):
    try:
        if not path.exists():
            return None, f"ABSENT: {path}"
        return json.loads(path.read_text(errors="ignore")), None
    except Exception as exc:
        return None, f"JSON_READ_ERROR {path}: {exc}"


def audit_state_files(report: Report):
    report.section("AUDIT FICHIERS D'ÉTAT LOCAUX")

    path = STATE_FILES["cycle_state"]
    data, err = read_json(path)
    report.subsection(str(path))
    if err:
        report.emit(err)
    else:
        report.emit(f"updated_utc : {data.get('updated_utc', '?')}")
        assets = data.get("assets", {})
        report.emit(f"Nombre actifs dans cycle_state : {len(assets)}")

        status_count = Counter()
        non_idle = []

        for asset, state in assets.items():
            status = state.get("status", "?")
            status_count[status] += 1
            if status not in ("IDLE", "WAIT", "?", None):
                non_idle.append((asset, state))

        report.emit("Répartition status :")
        for status, count in status_count.most_common():
            report.emit(f"  {status:25s} : {count}")

        if non_idle:
            report.emit("")
            report.emit("Actifs non IDLE / à surveiller :")
            for asset, state in non_idle:
                cycle = state.get("cycle", {})
                report.emit(
                    f"  {asset:10s} status={state.get('status')} "
                    f"direction={cycle.get('direction')} "
                    f"level={cycle.get('level')} "
                    f"entry={cycle.get('entry_price')} "
                    f"source={cycle.get('entry_price_source')}"
                )
        else:
            report.emit("Aucun actif non-IDLE détecté dans cycle_state.")

    path = STATE_FILES["execution_state"]
    data, err = read_json(path)
    report.subsection(str(path))
    if err:
        report.emit(err)
    else:
        report.emit("Clés racine : " + ", ".join(sorted(data.keys())))

        for key in ["active", "pending", "baskets", "working_orders", "orders", "positions"]:
            obj = data.get(key)
            if isinstance(obj, dict):
                report.emit(f"{key:20s} : dict len={len(obj)}")
                for i, (asset, value) in enumerate(obj.items()):
                    if i >= 12:
                        report.emit("  ...")
                        break
                    if isinstance(value, dict):
                        report.emit(
                            f"  {asset:10s} status={value.get('status')} "
                            f"direction={value.get('direction')} "
                            f"open={value.get('open')} "
                            f"pending={value.get('pending')} "
                            f"target={value.get('target')} "
                            f"upl={value.get('broker_upl') or value.get('upl')}"
                        )
                    else:
                        report.emit(f"  {asset:10s} {str(value)[:180]}")
            elif isinstance(obj, list):
                report.emit(f"{key:20s} : list len={len(obj)}")
                for row in obj[:12]:
                    report.emit(f"  {str(row)[:220]}")

    path = STATE_FILES["signals_latest"]
    data, err = read_json(path)
    report.subsection(str(path))
    if err:
        report.emit(err)
    else:
        if isinstance(data, dict):
            rows = data.get("signals") or data.get("assets") or []
            if isinstance(rows, dict):
                rows = list(rows.values())
        elif isinstance(data, list):
            rows = data
        else:
            rows = []

        report.emit(f"Nombre de signaux lus : {len(rows)}")

        by_decision = Counter()
        by_asset = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            asset = row.get("asset") or row.get("symbol") or row.get("name")
            decision = row.get("decision") or row.get("signal") or "?"
            by_decision[decision] += 1
            if asset:
                by_asset[asset] = row

        report.emit("Décisions signals_latest :")
        for decision, count in by_decision.most_common():
            report.emit(f"  {decision:15s} : {count}")

        report.emit("")
        report.emit("Dernier signal par actif :")
        for asset in ASSETS:
            row = by_asset.get(asset)
            if not row:
                report.emit(f"  {asset:10s} ABSENT")
                continue

            decision = row.get("decision", "?")
            bid = row.get("bid", "?")
            ask = row.get("ask", "?")
            mid = row.get("mid", "?")
            spread = row.get("spread", "?")
            age = row.get("age_sec", row.get("age", "?"))
            reason = row.get("reason", row.get("why", row.get("context_reason", "")))
            ctx = row.get("context_score", "?")
            phase = row.get("phase", "?")
            vwap_bias = row.get("vwap_bias", "?")

            report.emit(
                f"  {asset:10s} decision={decision} bid={bid} ask={ask} mid={mid} "
                f"spread={spread} age={age} ctx={ctx} phase={phase} vwap={vwap_bias} reason={reason}"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default=None, help="Chemin du log à analyser. Par défaut : dernier log 07D.")
    parser.add_argument("--save", action="store_true", help="Sauvegarde le rapport dans reports/.")
    parser.add_argument("--tail-events", type=int, default=8, help="Nombre d'événements récents par actif.")
    parser.add_argument("--tail-global", type=int, default=80, help="Nombre d'événements globaux récents.")
    parser.add_argument("--arm-mult", type=float, default=1.5, help="Curseur simulé V24.3.2 LIMIT_ARMING_DISTANCE.")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else latest_log()
    if not log_path:
        print("ERREUR : aucun log BOT_PIVOT_07D_24_7_DEMO_*.log trouvé dans logs/")
        sys.exit(1)

    report = Report()
    audit_log(log_path, args, report)
    audit_state_files(report)

    text = report.text()
    print(text)

    if args.save:
        reports_dir = Path("reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = reports_dir / f"BOT_PIVOT_AUDIT_V243_{stamp}.txt"
        out.write_text(text, encoding="utf-8")
        print("")
        print(f"RAPPORT_SAUVEGARDE={out}")


if __name__ == "__main__":
    main()
