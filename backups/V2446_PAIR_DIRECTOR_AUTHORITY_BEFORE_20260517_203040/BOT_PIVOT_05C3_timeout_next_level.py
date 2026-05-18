# 05C-3 — timeout 120 sec puis passage niveau suivant
# Aucun ordre réel.

import json, time, uuid
from datetime import datetime, timezone
import BOT_PIVOT_00_config as CFG

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
EVENTS_FILE = CFG.DATA_DIR / "cycles" / "cycle_events.jsonl"

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def event(e):
    e["event_utc"] = utc_now()
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

def pnl(direction, entry, current, size):
    return (current - entry) * size if direction == "BUY" else (entry - current) * size

def drift_coeff(direction, entry, current):
    if direction == "BUY":
        drift = max(0.0, entry - current)
    else:
        drift = max(0.0, current - entry)

    drift_pct = drift / entry if entry else 0.0
    ref = float(getattr(CFG, "REF_DRIFT_PCT", 0.002))
    cmin = float(getattr(CFG, "DRIFT_COEFF_MIN", 1.0))
    cmax = float(getattr(CFG, "DRIFT_COEFF_MAX", 2.5))
    coeff = drift_pct / ref if ref > 0 else 1.0
    coeff = max(cmin, min(cmax, coeff))

    return drift, drift_pct, coeff

def size_for(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        base = float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01))
        mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
        return base * mult

def tp_for(level, coeff):
    base = float(getattr(CFG, "BASE_TP_EUR", 0.10))
    mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
    return base * mult * coeff

def main():
    state = load(STATE_FILE, {"assets": {}})
    sigs = load(SIGNALS_FILE, {"signals": []})
    sigs = {s["asset"]: s for s in sigs.get("signals", []) if s.get("asset")}

    max_life = float(getattr(CFG, "MAX_POSITION_LIFE_SEC_LEVEL_1_TO_4", 120))
    max_level = int(getattr(CFG, "MAX_LEVEL", 5))

    print()
    print("=" * 130)
    print("05C-3 — TIMEOUT 120 SEC → NIVEAU SUIVANT")
    print("=" * 130)
    print("ACTIF      | ACTION        | OLD | NEW | DIR  | EXIT/CURRENT | PNL €    | DRIFT | COEFF | NEW SIZE  | NEW TP €")
    print("-" * 130)

    for asset, slot in state.get("assets", {}).items():
        c = slot.get("cycle")
        if not c:
            continue

        s = sigs.get(asset, {})
        current = s.get("mid")
        if current is None:
            print(f"{asset:10s} | HOLD          | pas de prix")
            continue

        level = int(c["level"])
        direction = c["direction"]
        entry = float(c["entry_price"])
        current = float(current)
        size = float(c["size"])
        tp = float(c["tp_eur"])
        age = time.time() - float(c["entry_ts"])
        p = pnl(direction, entry, current, size)

        if level >= max_level:
            print(f"{asset:10s} | HOLD_LEVEL5   | {level:>3} | --  | {direction:4s} | {current:<12.6f} | {p:<8.4f} | --    | --    | --        | --")
            continue

        if age < max_life:
            print(f"{asset:10s} | HOLD          | {level:>3} | --  | {direction:4s} | {current:<12.6f} | {p:<8.4f} | age={age:.1f}s")
            continue

        # fermeture niveau courant
        done = {
            "level": level,
            "direction": direction,
            "entry_price": entry,
            "exit_price": current,
            "size": size,
            "tp_eur": tp,
            "pnl_eur": p,
            "entry_utc": c["entry_utc"],
            "exit_utc": utc_now(),
            "close_reason": "TIMEOUT_120S_SIM"
        }
        c.setdefault("levels_done", []).append(done)

        drift, drift_pct, coeff = drift_coeff(direction, entry, current)
        new_level = level + 1
        new_size = size_for(asset, new_level)
        new_tp = tp_for(new_level, coeff)

        new_cycle = {
            "cycle_id": c.get("cycle_id", str(uuid.uuid4())[:12]),
            "asset": asset,
            "direction": direction,
            "level": new_level,
            "status": "OPEN",
            "entry_price": current,
            "entry_utc": utc_now(),
            "entry_ts": time.time(),
            "size": new_size,
            "tp_eur": new_tp,
            "drift_coeff": coeff,
            "levels_done": c["levels_done"],
            "source": "05C3_TIMEOUT_SIM"
        }

        slot["status"] = "IN_POSITION"
        slot["cycle"] = new_cycle

        event({
            "event": "TIMEOUT_NEXT_LEVEL_SIM",
            "asset": asset,
            "old_level": level,
            "new_level": new_level,
            "direction": direction,
            "exit_price": current,
            "pnl_eur": p,
            "adverse_drift_points": drift,
            "adverse_drift_pct": drift_pct,
            "drift_coeff": coeff,
            "new_size": new_size,
            "new_tp_eur": new_tp
        })

        print(f"{asset:10s} | NEXT_LEVEL    | {level:>3} | {new_level:>3} | {direction:4s} | {current:<12.6f} | {p:<8.4f} | {drift:<5.3f} | {coeff:<5.3f} | {new_size:<9.6f} | {new_tp:<.4f}")

    state["updated_utc"] = utc_now()
    save(STATE_FILE, state)
    print("=" * 130)
    print(f"État mis à jour : {STATE_FILE}")

if __name__ == "__main__":
    main()
