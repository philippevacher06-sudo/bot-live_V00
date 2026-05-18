# BOT_PIVOT_05_cycle_engine.py
# Cycle engine BOT-PIVOT — simulation
# Sécurité ajoutée :
# - aucune décision de cycle si le tick est trop vieux
# - pas de CLOSE_TP sur vieux prix
# - pas de NEXT_LEVEL sur vieux prix
# - pas d'ouverture de niveau sur vieux prix

import json
import uuid
import argparse
from pathlib import Path
from datetime import datetime, timezone

import BOT_PIVOT_00_config as CFG

SIGNALS_FILE = CFG.DATA_DIR / "ticks" / "signals_latest.json"
STATE_FILE = CFG.DATA_DIR / "cycles" / "cycle_state.json"

MAX_TICK_AGE_SEC = float(getattr(CFG, "MAX_TICK_AGE_SEC", 12.0))
MAX_LEVEL = int(getattr(CFG, "MAX_LEVEL", 5))
MAX_LIFE_SEC = float(getattr(CFG, "MAX_POSITION_LIFE_SEC_LEVEL_1_TO_4", 120.0))
BASE_TP_EUR = float(getattr(CFG, "BASE_TP_EUR", 0.10))
REF_DRIFT_PCT = float(getattr(CFG, "REF_DRIFT_PCT", 0.002))
DRIFT_COEFF_MIN = float(getattr(CFG, "DRIFT_COEFF_MIN", 1.0))
DRIFT_COEFF_MAX = float(getattr(CFG, "DRIFT_COEFF_MAX", 2.5))


def utc():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def age_sec_from(value):
    dt = parse_dt(value)
    if not dt:
        return 0.0
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds())


def load_json(path, default):
    if not Path(path).exists():
        return default
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def assets_list(raw):
    if not raw or raw.upper() == "ALL":
        return list(CFG.ASSETS)
    return [x.strip().upper() for x in raw.replace(";", ",").split(",") if x.strip()]


def default_state():
    return {
        "updated_utc": utc(),
        "assets": {
            asset: {
                "status": "IDLE",
                "cycle": None,
                "last_event": "INIT",
                "last_event_utc": utc(),
            }
            for asset in CFG.ASSETS
        },
    }


def normalize_state(state):
    if not isinstance(state, dict):
        state = default_state()

    state.setdefault("assets", {})

    for asset in CFG.ASSETS:
        state["assets"].setdefault(
            asset,
            {
                "status": "IDLE",
                "cycle": None,
                "last_event": "INIT",
                "last_event_utc": utc(),
            },
        )

    return state


def load_signals():
    raw = load_json(SIGNALS_FILE, {})

    if isinstance(raw, dict):
        if isinstance(raw.get("signals"), dict):
            return raw["signals"]
        if isinstance(raw.get("signals"), list):
            return {
                str(x.get("asset") or x.get("epic")).upper(): x
                for x in raw["signals"]
                if isinstance(x, dict)
            }
        if isinstance(raw.get("assets"), dict):
            return raw["assets"]

        # Cas où les actifs sont directement à la racine du JSON
        direct = {}
        for k, v in raw.items():
            if str(k).upper() in CFG.ASSETS and isinstance(v, dict):
                direct[str(k).upper()] = v
        if direct:
            return direct

    if isinstance(raw, list):
        return {
            str(x.get("asset") or x.get("epic")).upper(): x
            for x in raw
            if isinstance(x, dict)
        }

    return {}


def val(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def signal_decision(sig):
    return str(val(sig, ["decision", "signal", "action"], "WAIT")).upper()


def signal_mid(sig):
    x = val(sig, ["mid", "price", "current_price", "last_mid"], None)
    try:
        return float(x)
    except Exception:
        return None


def signal_age(sig):
    x = val(sig, ["age", "age_sec", "tick_age_sec", "last_tick_age_sec"], None)
    try:
        return float(x)
    except Exception:
        return None


def as_bool(x):
    if isinstance(x, bool):
        return x
    if isinstance(x, str):
        return x.strip().lower() in ("true", "1", "yes", "ok")
    return None


def signal_reason(sig):
    return str(val(sig, ["reason", "raison", "why"], ""))


def signal_spread_ok(sig):
    x = val(sig, ["spr_ok", "SprOK", "spread_ok", "spreadOK", "spread_allowed"], None)
    b = as_bool(x)
    if b is not None:
        return b

    reason = signal_reason(sig)
    if "SPREAD_TOO_HIGH" in reason:
        return False
    if "spread=LEARNING" in reason:
        return False

    return True


def is_fresh(sig):
    if not sig:
        return False, "signal_absent"

    age = signal_age(sig)
    mid = signal_mid(sig)

    if mid is None:
        return False, "prix_indisponible"

    if age is None:
        return False, "age_tick_indisponible"

    if age > MAX_TICK_AGE_SEC:
        return False, f"tick_trop_ancien_{age:.1f}s>{MAX_TICK_AGE_SEC:.1f}s"

    if not signal_spread_ok(sig):
        reason = signal_reason(sig)
        if "SPREAD_TOO_HIGH" in reason:
            return False, "spread_trop_eleve"
        if "spread=LEARNING" in reason:
            return False, "spread_learning_insuffisant"
        return False, "spread_non_valide"

    return True, "tick_et_spread_ok"


def level_multiplier(level):
    multipliers = getattr(CFG, "LEVEL_MULTIPLIERS", {})
    try:
        return float(multipliers.get(int(level), 2 ** (int(level) - 1)))
    except Exception:
        return float(2 ** (int(level) - 1))


def base_size(asset):
    if hasattr(CFG, "get_base_size"):
        return float(CFG.get_base_size(asset))

    if hasattr(CFG, "BASE_SIZES"):
        return float(CFG.BASE_SIZES[asset])

    if hasattr(CFG, "ASSET_BASE_SIZE"):
        return float(CFG.ASSET_BASE_SIZE[asset])

    raise RuntimeError(f"Taille de base introuvable pour {asset}")


def size_for(asset, level):
    return float(base_size(asset) * level_multiplier(level))


def tp_for(level, coeff=1.0):
    return float(BASE_TP_EUR * level_multiplier(level) * coeff)


def pnl_eur(direction, entry_price, current_price, size):
    if direction == "BUY":
        return (current_price - entry_price) * size
    return (entry_price - current_price) * size


def adverse_drift(direction, entry_price, close_price):
    if direction == "BUY":
        return max(0.0, entry_price - close_price)
    return max(0.0, close_price - entry_price)


def drift_coeff(direction, entry_price, close_price):
    drift = adverse_drift(direction, entry_price, close_price)
    if entry_price <= 0:
        return 1.0

    pct = drift / entry_price
    raw = pct / REF_DRIFT_PCT if REF_DRIFT_PCT > 0 else 1.0
    return max(DRIFT_COEFF_MIN, min(DRIFT_COEFF_MAX, raw))


def level_open_utc(cycle):
    return (
        cycle.get("level_open_utc")
        or cycle.get("opened_utc")
        or cycle.get("open_utc")
        or cycle.get("created_utc")
    )


def cycle_age_sec(cycle):
    return age_sec_from(level_open_utc(cycle))


def new_cycle(asset, direction, price, level=1, coeff=1.0, cycle_id=None):
    now = utc()
    return {
        "asset": asset,
        "cycle_id": cycle_id or str(uuid.uuid4())[:12],
        "level": int(level),
        "direction": direction,
        "entry_price": float(price),
        "size": float(size_for(asset, level)),
        "tp_eur": float(tp_for(level, coeff)),
        "drift_coeff": float(coeff),
        "created_utc": now,
        "opened_utc": now,
        "level_open_utc": now,
    }


def set_idle(state, asset, event):
    state["assets"][asset] = {
        "status": "IDLE",
        "cycle": None,
        "last_event": event,
        "last_event_utc": utc(),
    }


def set_position(state, asset, cycle, event):
    state["assets"][asset] = {
        "status": "IN_POSITION",
        "cycle": cycle,
        "last_event": event,
        "last_event_utc": utc(),
    }


def show_status(state, assets):
    print()
    print("=" * 130)
    print("BOT_PIVOT_05 — STATUS CYCLE ENGINE")
    print("=" * 130)

    for asset in assets:
        slot = state["assets"].get(asset, {})
        cycle = slot.get("cycle")

        if slot.get("status") != "IN_POSITION" or not cycle:
            print(f"{asset:10s} | IDLE")
            continue

        age = cycle_age_sec(cycle)
        print(
            f"{asset:10s} | IN_POSITION "
            f"L{int(cycle['level'])} "
            f"{cycle['direction']} "
            f"entry={float(cycle['entry_price']):.6f} "
            f"size={float(cycle['size']):.6f} "
            f"tp={float(cycle['tp_eur']):.4f} "
            f"age={age:.1f}s"
        )

    print("=" * 130)


def run_engine(assets, capital):
    state = normalize_state(load_json(STATE_FILE, default_state()))
    signals = load_signals()

    print()
    print("=" * 130)
    print("BOT_PIVOT_05 — CYCLE ENGINE SIMULATION")
    print("=" * 130)

    for asset in assets:
        slot = state["assets"].get(asset, {})
        cycle = slot.get("cycle")
        status = slot.get("status", "IDLE")
        sig = signals.get(asset, {})

        fresh, fresh_reason = is_fresh(sig)
        decision = signal_decision(sig)
        current_price = signal_mid(sig)

        # 1. Pas de position active
        if status != "IN_POSITION" or not cycle:
            if decision in ("BUY", "SELL"):
                if not fresh:
                    print(f"{asset:10s} | IDLE_UNSAFE  | signal {decision} ignoré | {fresh_reason}")
                    set_idle(state, asset, "IDLE_STALE")
                    continue

                c = new_cycle(asset, decision, current_price, level=1)
                set_position(state, asset, c, "OPEN_L1")
                print(
                    f"{asset:10s} | OPEN_L1      | "
                    f"{decision:4s} | "
                    f"entry={current_price:.6f} | "
                    f"size={float(c['size']):.6f} | "
                    f"tp={float(c['tp_eur']):.4f}"
                )
            else:
                print(f"{asset:10s} | IDLE         | aucun signal")
                set_idle(state, asset, "IDLE")
            continue

        # 2. Position active mais tick non exploitable
        level = int(cycle["level"])
        direction = cycle["direction"]
        entry = float(cycle["entry_price"])
        size = float(cycle["size"])
        tp = float(cycle["tp_eur"])

        if not fresh:
            print(
                f"{asset:10s} | HOLD_UNSAFE_TICK | "
                f"L{level} | {direction:4s} | "
                f"aucune décision | {fresh_reason}"
            )
            # On ne modifie pas le cycle
            continue

        pnl = pnl_eur(direction, entry, current_price, size)
        age = cycle_age_sec(cycle)

        # 3. TP sur tous niveaux, y compris L5
        if pnl >= tp:
            print(
                f"{asset:10s} | CLOSE_TP     | "
                f"L{level} | {direction:4s} | "
                f"pnl={pnl:.4f} | tp={tp:.4f}"
            )
            set_idle(state, asset, "CLOSE_TP")
            continue

        # 4. Niveau 5 : pas de timeout, seulement TP ou stop sécurité
        if level >= MAX_LEVEL:
            stop_loss = float(capital) * 0.01
            if pnl <= -stop_loss:
                print(
                    f"{asset:10s} | CLOSE_STOP_1PCT | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f} | stop=-{stop_loss:.2f}"
                )
                set_idle(state, asset, "CLOSE_STOP_1PCT")
            else:
                print(
                    f"{asset:10s} | HOLD_L5      | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f} | pas de timeout"
                )
            continue

        # 5. Niveaux 1 à 4 : timeout après 120 secondes
        if age >= MAX_LIFE_SEC:
            next_level = level + 1

            if next_level > MAX_LEVEL:
                print(
                    f"{asset:10s} | HOLD_MAX     | "
                    f"L{level} | {direction:4s} | "
                    f"pnl={pnl:.4f}"
                )
                continue

            coeff = drift_coeff(direction, entry, current_price)
            c = new_cycle(
                asset,
                direction,
                current_price,
                level=next_level,
                coeff=coeff,
                cycle_id=cycle.get("cycle_id"),
            )
            set_position(state, asset, c, "NEXT_LEVEL")

            print(
                f"{asset:10s} | NEXT_LEVEL   | "
                f"L{level}->L{next_level} | "
                f"{direction:4s} | "
                f"pnl={pnl:.4f} | "
                f"coeff={coeff:.3f} | "
                f"size={float(c['size']):.6f} | "
                f"tp={float(c['tp_eur']):.4f}"
            )
            continue

        # 6. Maintien normal
        print(
            f"{asset:10s} | HOLD         | "
            f"L{level} | {direction:4s} | "
            f"pnl={pnl:.4f} | "
            f"tp={tp:.4f} | "
            f"age={age:.1f}s"
        )

    state["updated_utc"] = utc()
    save_json(STATE_FILE, state)

    print("=" * 130)
    print("État :", STATE_FILE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--assets", default="ALL")
    parser.add_argument("--capital", type=float, default=3500.0)
    args = parser.parse_args()

    assets = assets_list(args.assets)

    if args.reset:
        state = default_state()
        save_json(STATE_FILE, state)
        print("Cycle state réinitialisé :", STATE_FILE)
        return

    state = normalize_state(load_json(STATE_FILE, default_state()))

    if args.status:
        show_status(state, assets)
        return

    run_engine(assets, args.capital)


if __name__ == "__main__":
    main()
