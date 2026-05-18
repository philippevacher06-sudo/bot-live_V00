# BOT_PIVOT_05D_level5_guard.py
# Mini-module 05D — contrôle niveau 5
# Aucun ordre réel.
# Teste : pas de niveau 6, pas de timeout, stop -1 % capital.

import json
import time
from datetime import datetime, timezone
import BOT_PIVOT_00_config as CFG

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def pnl(direction, entry, current, size):
    if direction == "BUY":
        return (current - entry) * size
    return (entry - current) * size

def main():
    capital = 3500.0
    stop_level5 = capital * float(getattr(CFG, "LEVEL_5_STOP_LOSS_PCT", 0.01))
    max_level = int(getattr(CFG, "MAX_LEVEL", 5))

    state = load(STATE_FILE, {"assets": {}})
    sigs = load(SIGNALS_FILE, {"signals": []})
    sigs = {s["asset"]: s for s in sigs.get("signals", []) if s.get("asset")}

    print()
    print("=" * 120)
    print("05D — CONTRÔLE NIVEAU 5")
    print("=" * 120)
    print(f"Capital test : {capital:.2f} € | Stop niveau 5 : -{stop_level5:.2f} €")
    print("-" * 120)
    print("ACTIF      | ACTION          | LVL | DIR  | ENTRY        | CURRENT      | SIZE       | PNL €      | INFO")
    print("-" * 120)

    for asset, slot in state.get("assets", {}).items():
        c = slot.get("cycle")
        if not c:
            continue

        level = int(c["level"])
        direction = c["direction"]
        entry = float(c["entry_price"])
        size = float(c["size"])

        sig = sigs.get(asset, {})
        current = sig.get("mid")

        if current is None:
            print(f"{asset:10s} | HOLD            | {level:>3} | {direction:4s} | pas de prix")
            continue

        current = float(current)
        p = pnl(direction, entry, current, size)

        if level < max_level:
            print(f"{asset:10s} | NOT_LEVEL5      | {level:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {size:<10.6f} | {p:<10.4f} | niveau inférieur")
            continue

        if level > max_level:
            slot["status"] = "ERROR"
            print(f"{asset:10s} | ERROR_LEVEL_6   | {level:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {size:<10.6f} | {p:<10.4f} | niveau interdit")
            continue

        # Ici level == 5 : pas de timeout, pas de niveau 6.
        if p <= -stop_level5:
            slot["last_completed_cycle"] = {
                "cycle_id": c.get("cycle_id"),
                "asset": asset,
                "direction": direction,
                "result": "LEVEL5_STOP_1PCT_SIM",
                "final_level": 5,
                "closed_utc": utc_now(),
                "pnl_eur": p,
                "stop_level5_eur": stop_level5,
            }
            slot["status"] = "IDLE"
            slot["cycle"] = None

            print(f"{asset:10s} | CLOSE_STOP_1PCT | {level:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {size:<10.6f} | {p:<10.4f} | stop niveau 5")
        else:
            print(f"{asset:10s} | HOLD_LEVEL5     | {level:>3} | {direction:4s} | {entry:<12.6f} | {current:<12.6f} | {size:<10.6f} | {p:<10.4f} | pas de timeout, pas de niveau 6")

    state["updated_utc"] = utc_now()
    save(STATE_FILE, state)

    print("=" * 120)
    print(f"État mis à jour : {STATE_FILE}")

if __name__ == "__main__":
    main()
