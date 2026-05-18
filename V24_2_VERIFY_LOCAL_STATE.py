#!/usr/bin/env python3
"""Verify BOT-PIVOT local state before a V24.2 restart."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"__error__": str(exc), "__path__": str(path)}
    return default


def first_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def main() -> int:
    root = Path(__file__).resolve().parent
    cycle_path = first_existing(
        root / "data" / "cycles" / "cycle_state.json",
        root / "data_sample" / "cycles" / "cycle_state.json",
    )
    exec_path = first_existing(
        root / "data" / "execution" / "cycle_execution_state.json",
        root / "data_sample" / "execution" / "cycle_execution_state.json",
    )

    cycle_state = load_json(cycle_path, {"assets": {}})
    exec_state = load_json(exec_path, {"active": {}})

    errors = []

    if "__error__" in cycle_state:
        errors.append(f"CYCLE_STATE_READ_ERROR {cycle_state['__path__']}: {cycle_state['__error__']}")
    if "__error__" in exec_state:
        errors.append(f"EXEC_STATE_READ_ERROR {exec_state['__path__']}: {exec_state['__error__']}")

    assets = cycle_state.get("assets", {}) if isinstance(cycle_state, dict) else {}
    active = exec_state.get("active", {}) if isinstance(exec_state, dict) else {}
    if not isinstance(assets, dict):
        assets = {}
    if not isinstance(active, dict):
        active = {}

    cycle_non_idle = []
    cycle_without_exec = []
    for asset, slot in assets.items():
        if not isinstance(slot, dict):
            continue
        status = str(slot.get("status") or "IDLE").upper()
        cycle = slot.get("cycle")
        if status != "IDLE" or cycle:
            cycle_non_idle.append(asset)
            if asset not in active:
                cycle_without_exec.append(asset)

    exec_active = list(active.keys())
    pending_without_working_id = []
    for asset, record in active.items():
        if not isinstance(record, dict):
            continue
        levels = record.get("levels")
        if isinstance(levels, dict):
            for level_key, rec in levels.items():
                if not isinstance(rec, dict):
                    continue
                status = str(rec.get("status") or "")
                if status.startswith("PENDING_LIMIT") and not rec.get("workingDealId"):
                    pending_without_working_id.append(f"{asset}:L{level_key}")
        else:
            status = str(record.get("status") or "")
            if status.startswith("PENDING_LIMIT") and not record.get("workingDealId"):
                pending_without_working_id.append(f"{asset}:single")

    if cycle_non_idle:
        errors.append("CYCLE non-IDLE = " + ", ".join(cycle_non_idle))
    if exec_active:
        errors.append("EXEC active = " + ", ".join(exec_active))
    if pending_without_working_id:
        errors.append("PENDING without workingDealId = " + ", ".join(pending_without_working_id))
    if cycle_without_exec:
        errors.append("CYCLE without EXEC active = " + ", ".join(cycle_without_exec))

    print("V24.2 LOCAL STATE VERIFY")
    print(f"cycle_state: {cycle_path}")
    print(f"exec_state : {exec_path}")

    if errors:
        print("STATUS: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("STATUS: OK")
    print("CYCLE non-IDLE = []")
    print("EXEC active = []")
    return 0


if __name__ == "__main__":
    sys.exit(main())
