# BOT_PIVOT_05B_open_level1.py
# Mini-module 05B — ouvrir niveau 1 en simulation depuis les signaux BUY / SELL

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import BOT_PIVOT_00_config as CFG

SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
CYCLE_DIR = CFG.DATA_DIR / "cycles"
STATE_FILE = CYCLE_DIR / "cycle_state.json"

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_size(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        base = float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01))
        mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
        return base * mult

def get_tp(level):
    base = float(getattr(CFG, "BASE_TP_EUR", 0.10))
    mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
    return base * mult

def is_tradable(signal):
    if signal.get("decision") not in ["BUY", "SELL"]:
        return False
    if not signal.get("spread_ok"):
        return False
    if signal.get("mid") is None:
        return False
    max_age = float(getattr(CFG, "MAX_TICK_AGE_SEC", 12))
    if float(signal.get("age_sec", 999999)) > max_age:
        return False
    return True

def load_signals():
    data = load_json(SIGNALS_FILE, {"signals": []})
    return data.get("signals", [])

def load_state():
    state = load_json(STATE_FILE, {"assets": {}})
    if "assets" not in state:
        state["assets"] = {}
    return state

def main():
    CYCLE_DIR.mkdir(parents=True, exist_ok=True)

    signals = [s for s in load_signals() if is_tradable(s)]
    state = load_state()

    print()
    print("=" * 120)
    print("05B — OUVERTURE NIVEAU 1 EN SIMULATION")
    print("=" * 120)
    print("ACTIF      | ACTION        | DIR  | ENTRY        | SIZE       | TP €")
    print("-" * 120)

    if not signals:
        print("Aucun signal tradable.")
    else:
        for s in signals:
            asset = s["asset"]
            direction = s["decision"]
            entry = float(s["mid"])

            slot = state["assets"].get(asset, {"status": "IDLE", "cycle": None})

            if slot.get("status") == "IN_POSITION":
                c = slot.get("cycle", {})
                print(f"{asset:10s} | DEJA_OUVERT   | {c.get('direction','--'):4s} | {float(c.get('entry_price',0)):<12.6f} | {float(c.get('size',0)):<10.6f} | {float(c.get('tp_eur',0)):<.4f}")
                state["assets"][asset] = slot
                continue

            level = 1
            cycle = {
                "cycle_id": str(uuid.uuid4())[:12],
                "asset": asset,
                "direction": direction,
                "level": level,
                "status": "OPEN",
                "entry_price": entry,
                "entry_utc": utc_now(),
                "entry_ts": time.time(),
                "size": get_size(asset, level),
                "tp_eur": get_tp(level),
                "drift_coeff": 1.0,
                "levels_done": [],
                "source": "05B_SIMULATION"
            }

            state["assets"][asset] = {
                "status": "IN_POSITION",
                "cycle": cycle
            }

            print(f"{asset:10s} | OPEN_LEVEL_1 | {direction:4s} | {entry:<12.6f} | {cycle['size']:<10.6f} | {cycle['tp_eur']:<.4f}")

    state["updated_utc"] = utc_now()
    save_json(STATE_FILE, state)

    print("=" * 120)
    print(f"État écrit : {STATE_FILE}")

if __name__ == "__main__":
    main()
