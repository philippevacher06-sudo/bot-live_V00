# BOT_PIVOT_05C2_close_tp.py
# Mini-module 05C-2 — fermer en simulation si PnL >= TP
# Aucun ordre réel.

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import BOT_PIVOT_00_config as CFG

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
EVENTS_FILE = CFG.DATA_DIR / "cycles" / "cycle_events.jsonl"

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def append_event(event):
    event["event_utc"] = utc_now()
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def simulated_pnl(direction, entry, current, size):
    if direction == "BUY":
        return (current - entry) * size
    return (entry - current) * size

def main():
    state = load_json(STATE_FILE, {"assets": {}})
    signals_data = load_json(SIGNALS_FILE, {"signals": []})
    signals = {s["asset"]: s for s in signals_data.get("signals", []) if s.get("asset")}

    print()
    print("=" * 120)
    print("05C-2 — FERMETURE TP EN SIMULATION")
    print("=" * 120)
    print("ACTIF      | ACTION      | LVL | DIR  | ENTRY        | CURRENT      | TP €   | PNL €")
    print("-" * 120)

    for asset, slot in state.get("assets", {}).items():
        cycle = slot.get("cycle")

        if not cycle:
            continue

        sig = signals.get(asset, {})
        current = sig.get("mid")

        if current is None:
            print(f"{asset:10s} | HOLD        | --  | --   | pas de prix actuel")
            continue

        entry = float(cycle["entry_price"])
        current = float(current)
        size = float(cycle["size"])
        direction = cycle["direction"]
        tp = float(cycle["tp_eur"])
        pnl = simulated_pnl(direction, entry, current, size)

        if pnl >= tp:
            level_done = {
                "level": cycle["level"],
                "direction": direction,
                "entry_price": entry,
                "exit_price": current,
                "size": size,
                "tp_eur": tp,
                "pnl_eur": pnl,
                "entry_utc": cycle["entry_utc"],
                "exit_utc": utc_now(),
                "close_reason": "TP_HIT_SIM"
            }

            cycle.setdefault("levels_done", []).append(level_done)

            slot["last_completed_cycle"] = {
                "cycle_id": cycle["cycle_id"],
                "asset": asset,
                "direction": direction,
                "result": "TP_SUCCESS",
                "final_level": cycle["level"],
                "completed_utc": utc_now(),
                "levels_done": cycle["levels_done"]
            }

            slot["status"] = "IDLE"
            slot["cycle"] = None

            append_event({
                "event": "TP_HIT_SIM",
                "asset": asset,
                "cycle_id": level_done.get("cycle_id"),
                "level": level_done["level"],
                "direction": direction,
                "entry_price": entry,
                "exit_price": current,
                "size": size,
                "tp_eur": tp,
                "pnl_eur": pnl
            })

            print(f"{asset:10s} | CLOSE_TP    | {level_done['level']:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {tp:<6.4f} | {pnl:<.4f}")

        else:
            print(f"{asset:10s} | HOLD        | {cycle['level']:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {tp:<6.4f} | {pnl:<.4f}")

    state["updated_utc"] = utc_now()
    save_json(STATE_FILE, state)

    print("=" * 120)
    print(f"État mis à jour : {STATE_FILE}")

if __name__ == "__main__":
    main()
