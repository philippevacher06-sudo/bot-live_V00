# BOT_PIVOT_05_cycle_engine.py
# Module 05 final — moteur de cycle 5 niveaux en simulation
# Aucun ordre réel. Aucune API broker.

import argparse, json, time, uuid
from datetime import datetime, timezone
import BOT_PIVOT_00_config as CFG

STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"
SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"
EVENTS_FILE = CFG.DATA_DIR / "cycles" / "cycle_events.jsonl"

def utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def event(e):
    e["event_utc"] = utc()
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")

def parse_assets(txt):
    return [x.strip().upper() for x in txt.replace(";", ",").split(",") if x.strip()]

def size_for(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        return float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01)) * float(CFG.LEVEL_MULTIPLIERS.get(level, 1))

def tp_for(level, coeff=1.0):
    return float(getattr(CFG, "BASE_TP_EUR", 0.10)) * float(CFG.LEVEL_MULTIPLIERS.get(level, 1)) * coeff

def pnl(direction, entry, current, size):
    return (current - entry) * size if direction == "BUY" else (entry - current) * size

def drift_coeff(direction, entry, current):
    if direction == "BUY":
        drift = max(0.0, entry - current)
    else:
        drift = max(0.0, current - entry)

    drift_pct = drift / entry if entry else 0.0
    ref = float(getattr(CFG, "REF_DRIFT_PCT", 0.002))
    coeff = drift_pct / ref if ref > 0 else 1.0
    coeff = max(float(getattr(CFG, "DRIFT_COEFF_MIN", 1.0)), coeff)
    coeff = min(float(getattr(CFG, "DRIFT_COEFF_MAX", 2.5)), coeff)
    return drift, drift_pct, coeff

def tradable_signal(s):
    if not s:
        return False
    if s.get("decision") not in ["BUY", "SELL"]:
        return False
    if not s.get("spread_ok"):
        return False
    if s.get("mid") is None:
        return False
    if float(s.get("age_sec", 999999)) > float(getattr(CFG, "MAX_TICK_AGE_SEC", 12)):
        return False
    return True

def load_signals():
    raw = load(SIGNALS_FILE, {"signals": []})
    return {s["asset"]: s for s in raw.get("signals", []) if s.get("asset")}

def empty_slot():
    return {"status": "IDLE", "cycle": None, "last_completed_cycle": None}

def open_level(asset, direction, level, entry, coeff=1.0, previous=None):
    cycle_id = previous.get("cycle_id") if previous else str(uuid.uuid4())[:12]
    levels_done = previous.get("levels_done", []) if previous else []

    return {
        "cycle_id": cycle_id,
        "asset": asset,
        "direction": direction,
        "level": level,
        "status": "OPEN",
        "entry_price": entry,
        "entry_utc": utc(),
        "entry_ts": time.time(),
        "size": size_for(asset, level),
        "tp_eur": tp_for(level, coeff),
        "drift_coeff": coeff,
        "levels_done": levels_done,
        "source": "BOT_PIVOT_05_SIMULATION"
    }

def close_record(c, current, p, reason):
    return {
        "level": c["level"],
        "direction": c["direction"],
        "entry_price": c["entry_price"],
        "exit_price": current,
        "size": c["size"],
        "tp_eur": c["tp_eur"],
        "pnl_eur": p,
        "entry_utc": c["entry_utc"],
        "exit_utc": utc(),
        "close_reason": reason
    }

def process_asset(asset, slot, sig, capital):
    max_level = int(getattr(CFG, "MAX_LEVEL", 5))
    max_life = float(getattr(CFG, "MAX_POSITION_LIFE_SEC_LEVEL_1_TO_4", 120))
    stop_level5 = capital * float(getattr(CFG, "LEVEL_5_STOP_LOSS_PCT", 0.01))

    c = slot.get("cycle")

    # 1. Pas de cycle ouvert : ouvrir niveau 1 seulement si signal tradable
    if not c:
        if tradable_signal(sig):
            entry = float(sig["mid"])
            direction = sig["decision"]
            newc = open_level(asset, direction, 1, entry, 1.0)
            slot["status"] = "IN_POSITION"
            slot["cycle"] = newc

            event({"event": "OPEN_LEVEL_1_SIM", "asset": asset, "direction": direction, "entry": entry})

            return f"{asset:10s} | OPEN_L1      | {direction:4s} | entry={entry:.6f} | size={newc['size']:.6f} | tp={newc['tp_eur']:.4f}"

        return f"{asset:10s} | IDLE         | aucun signal"

    # 2. Cycle ouvert : besoin du prix courant
    if not sig or sig.get("mid") is None:
        return f"{asset:10s} | HOLD         | pas de prix"

    current = float(sig["mid"])
    level = int(c["level"])
    direction = c["direction"]
    entry = float(c["entry_price"])
    size = float(c["size"])
    tp = float(c["tp_eur"])
    age = time.time() - float(c["entry_ts"])
    p = pnl(direction, entry, current, size)

    # 3. TP atteint : fermeture complète du cycle
    if p >= tp:
        rec = close_record(c, current, p, "TP_HIT_SIM")
        c.setdefault("levels_done", []).append(rec)

        slot["last_completed_cycle"] = {
            "cycle_id": c["cycle_id"],
            "asset": asset,
            "direction": direction,
            "result": "TP_SUCCESS",
            "final_level": level,
            "completed_utc": utc(),
            "levels_done": c["levels_done"]
        }
        slot["status"] = "IDLE"
        slot["cycle"] = None

        event({"event": "TP_HIT_SIM", "asset": asset, "level": level, "pnl": p})

        return f"{asset:10s} | CLOSE_TP     | L{level} | {direction:4s} | pnl={p:.4f} | tp={tp:.4f}"

    # 4. Niveau 5 : pas de timeout, pas de niveau 6, stop 1 %
    if level >= max_level:
        if p <= -stop_level5:
            rec = close_record(c, current, p, "LEVEL5_STOP_1PCT_SIM")
            c.setdefault("levels_done", []).append(rec)

            slot["last_completed_cycle"] = {
                "cycle_id": c["cycle_id"],
                "asset": asset,
                "direction": direction,
                "result": "LEVEL5_STOP",
                "final_level": 5,
                "completed_utc": utc(),
                "levels_done": c["levels_done"]
            }
            slot["status"] = "IDLE"
            slot["cycle"] = None

            event({"event": "LEVEL5_STOP_1PCT_SIM", "asset": asset, "pnl": p, "stop": stop_level5})

            return f"{asset:10s} | STOP_L5      | L5 | {direction:4s} | pnl={p:.4f} | stop=-{stop_level5:.2f}"

        return f"{asset:10s} | HOLD_L5      | L5 | {direction:4s} | pnl={p:.4f} | pas de timeout"

    # 5. Niveaux 1 à 4 : timeout 120 sec puis niveau suivant
    if age >= max_life:
        rec = close_record(c, current, p, "TIMEOUT_120S_SIM")
        c.setdefault("levels_done", []).append(rec)

        drift, drift_pct, coeff = drift_coeff(direction, entry, current)
        new_level = level + 1
        newc = open_level(asset, direction, new_level, current, coeff, previous=c)

        slot["status"] = "IN_POSITION"
        slot["cycle"] = newc

        event({
            "event": "TIMEOUT_NEXT_LEVEL_SIM",
            "asset": asset,
            "old_level": level,
            "new_level": new_level,
            "pnl": p,
            "drift": drift,
            "coeff": coeff
        })

        return f"{asset:10s} | NEXT_LEVEL   | L{level}->L{new_level} | {direction:4s} | pnl={p:.4f} | coeff={coeff:.3f} | size={newc['size']:.6f} | tp={newc['tp_eur']:.4f}"

    return f"{asset:10s} | HOLD         | L{level} | {direction:4s} | pnl={p:.4f} | tp={tp:.4f} | age={age:.1f}s"

def status(assets):
    state = load(STATE_FILE, {"assets": {}})
    sigs = load_signals()

    print()
    print("=" * 130)
    print("BOT_PIVOT_05 — STATUS")
    print("=" * 130)

    for asset in assets:
        slot = state.get("assets", {}).get(asset, empty_slot())
        c = slot.get("cycle")
        if not c:
            print(f"{asset:10s} | IDLE")
            continue

        sig = sigs.get(asset, {})
        current = sig.get("mid")
        p = "--"
        if current is not None:
            p = f"{pnl(c['direction'], float(c['entry_price']), float(current), float(c['size'])):.4f}"

        age = time.time() - float(c["entry_ts"])

        print(
            f"{asset:10s} | {slot.get('status')} | "
            f"L{c['level']} | {c['direction']} | "
            f"entry={float(c['entry_price']):.6f} | "
            f"size={float(c['size']):.6f} | "
            f"tp={float(c['tp_eur']):.4f} | "
            f"pnl={p} | age={age:.1f}s"
        )

    print("=" * 130)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default=",".join(CFG.ASSETS))
    parser.add_argument("--capital", type=float, default=3500.0)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    assets = parse_assets(args.assets)

    state = load(STATE_FILE, {"assets": {}})

    if "assets" not in state:
        state["assets"] = {}

    if args.reset:
        for asset in assets:
            state["assets"][asset] = empty_slot()
        state["updated_utc"] = utc()
        save(STATE_FILE, state)
        print("Reset effectué pour :", ", ".join(assets))
        return

    if args.status:
        status(assets)
        return

    sigs = load_signals()

    print()
    print("=" * 130)
    print("BOT_PIVOT_05 — CYCLE ENGINE SIMULATION")
    print("=" * 130)

    for asset in assets:
        slot = state["assets"].setdefault(asset, empty_slot())
        print(process_asset(asset, slot, sigs.get(asset), args.capital))

    state["updated_utc"] = utc()
    save(STATE_FILE, state)

    print("=" * 130)
    print(f"État : {STATE_FILE}")

if __name__ == "__main__":
    main()
