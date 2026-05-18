# BOT_PIVOT_05A_read_signals.py
# Mini-module 05A — lire les signaux BUY / SELL du module 04
# Aucun ordre. Aucun cycle. Lecture seulement.

import json
from pathlib import Path
import BOT_PIVOT_00_config as CFG

SIGNALS_FILE = CFG.TICKS_DIR / "signals_latest.json"

def load_signals():
    if not SIGNALS_FILE.exists():
        raise FileNotFoundError(f"Fichier introuvable : {SIGNALS_FILE}")

    data = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
    return data.get("signals", [])

def is_tradable(signal):
    decision = signal.get("decision")
    if decision not in ["BUY", "SELL"]:
        return False

    if not signal.get("spread_ok"):
        return False

    max_age = float(getattr(CFG, "MAX_TICK_AGE_SEC", 12))
    age = float(signal.get("age_sec", 999999))

    if age > max_age:
        return False

    if signal.get("mid") is None:
        return False

    return True

def main():
    signals = load_signals()
    tradables = [s for s in signals if is_tradable(s)]

    print()
    print("=" * 110)
    print("05A — SIGNAUX TRADABLES BUY / SELL")
    print("=" * 110)
    print("ACTIF      | DECISION | MID          | AGE   | SPREAD OK | ZONE")
    print("-" * 110)

    if not tradables:
        print("Aucun signal BUY / SELL tradable actuellement.")
    else:
        for s in tradables:
            zone = s.get("chosen_zone") or {}
            zone_txt = "--"
            if zone:
                zone_txt = f"{zone.get('scope','?')}:{zone.get('type','?')}"
                if zone.get("psycho_level") is not None:
                    zone_txt += f":{zone.get('psycho_level')}"

            print(
                f"{s.get('asset','?'):10s} | "
                f"{s.get('decision','?'):8s} | "
                f"{float(s.get('mid')):<12.6f} | "
                f"{float(s.get('age_sec',0)):<5.1f} | "
                f"{str(s.get('spread_ok')):<9s} | "
                f"{zone_txt}"
            )

    print("=" * 110)
    print(f"Source : {SIGNALS_FILE}")

if __name__ == "__main__":
    main()
