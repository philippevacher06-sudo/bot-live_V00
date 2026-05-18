# BOT_PIVOT_05C_check_pnl.py
# Mini-module 05C-1 — vérifier les cycles ouverts et calculer le PnL simulé
# Aucun ordre. Aucune fermeture. Lecture seulement.

import json
import time
from pathlib import Path

import BOT_PIVOT_00_config as CFG

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"

def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def simulated_pnl(direction, entry, current, size):
    if direction == "BUY":
        return (current - entry) * size
    return (entry - current) * size

def main():
    state = load_json(STATE_FILE, {"assets": {}})
    signals_data = load_json(SIGNALS_FILE, {"signals": []})

    signals = {}
    for s in signals_data.get("signals", []):
        if s.get("asset"):
            signals[s["asset"]] = s

    print()
    print("=" * 130)
    print("05C-1 — ÉTAT DES CYCLES / PNL SIMULÉ")
    print("=" * 130)
    print("ACTIF      | STATUS      | LVL | DIR  | ENTRY        | CURRENT      | SIZE       | TP €   | PNL €    | AGE")
    print("-" * 130)

    any_open = False

    for asset, slot in state.get("assets", {}).items():
        cycle = slot.get("cycle")

        if not cycle:
            continue

        any_open = True

        sig = signals.get(asset, {})
        current = sig.get("mid")

        if current is None:
            print(f"{asset:10s} | IN_POSITION | {cycle.get('level')}   | {cycle.get('direction')} | pas de prix actuel")
            continue

        entry = float(cycle["entry_price"])
        current = float(current)
        size = float(cycle["size"])
        direction = cycle["direction"]
        tp = float(cycle["tp_eur"])
        pnl = simulated_pnl(direction, entry, current, size)
        age = time.time() - float(cycle["entry_ts"])

        print(
            f"{asset:10s} | "
            f"{slot.get('status','?'):11s} | "
            f"{cycle.get('level'):>3} | "
            f"{direction:4s} | "
            f"{entry:<12.6f} | "
            f"{current:<12.6f} | "
            f"{size:<10.6f} | "
            f"{tp:<6.4f} | "
            f"{pnl:<8.4f} | "
            f"{age:.1f}s"
        )

    if not any_open:
        print("Aucun cycle ouvert.")

    print("=" * 130)
    print(f"State : {STATE_FILE}")

if __name__ == "__main__":
    main()
