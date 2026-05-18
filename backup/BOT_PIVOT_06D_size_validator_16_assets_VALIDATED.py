# BOT_PIVOT_06D_size_validator.py
# Validation tailles BOT-PIVOT vs tailles minimum broker sur les 16 actifs
# Aucun ordre réel.

import json
import BOT_PIVOT_00_config as CFG

MARKET_DIR = CFG.DATA_DIR / "markets"

def get_market_data(asset):
    f = MARKET_DIR / f"market_{asset}.json"
    if not f.exists():
        return None

    data = json.loads(f.read_text(encoding="utf-8"))
    market = data.get("market", data)
    rules = market.get("dealingRules", {})
    instrument = market.get("instrument", {})
    snapshot = market.get("snapshot", {})

    min_deal = rules.get("minDealSize")

    if isinstance(min_deal, dict):
        min_size = min_deal.get("value")
    else:
        min_size = min_deal or instrument.get("minDealSize")

    status = (
        snapshot.get("marketStatus")
        or market.get("marketStatus")
        or instrument.get("marketStatus")
        or "UNKNOWN"
    )

    return {
        "min_size": float(min_size) if min_size is not None else None,
        "status": status,
    }

def size_for(asset, level):
    try:
        return float(CFG.size_for_level(asset, level))
    except Exception:
        base = float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.01))
        mult = float(CFG.LEVEL_MULTIPLIERS.get(level, 1))
        return base * mult

def main():
    assets = CFG.ASSETS

    print()
    print("=" * 145)
    print("06D — VALIDATION TAILLES BOT VS BROKER — 16 ACTIFS")
    print("=" * 145)
    print("ACTIF      | MARKET    | MIN BROKER | L1         | L2         | L3         | L4         | L5         | STATUS")
    print("-" * 145)

    errors = []

    for asset in assets:
        md = get_market_data(asset)
        sizes = [size_for(asset, lvl) for lvl in range(1, 6)]

        if md is None:
            market_status = "UNKNOWN"
            min_size = None
            status = "JSON MANQUANT"
            errors.append(asset)

        else:
            market_status = md["status"]
            min_size = md["min_size"]

            if min_size is None:
                status = "MIN MANQUANT"
                errors.append(asset)
            elif any(s < min_size for s in sizes):
                status = "TAILLE ERREUR"
                errors.append(asset)
            elif market_status != "TRADEABLE":
                status = "MARCHÉ FERMÉ"
            else:
                status = "OK"

        print(
            f"{asset:10s} | "
            f"{market_status:9s} | "
            f"{str(min_size):10s} | "
            f"{sizes[0]:10.6f} | "
            f"{sizes[1]:10.6f} | "
            f"{sizes[2]:10.6f} | "
            f"{sizes[3]:10.6f} | "
            f"{sizes[4]:10.6f} | "
            f"{status}"
        )

    print("=" * 145)

    if errors:
        print("VALIDATION : ERREUR TAILLES sur :", ", ".join(errors))
        print("Ces actifs restent dans le bot, mais seront bloqués à l'exécution réelle tant que la taille n'est pas corrigée.")
    else:
        print("VALIDATION : OK — toutes les tailles sont compatibles broker.")

if __name__ == "__main__":
    main()
