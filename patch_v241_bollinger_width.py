from pathlib import Path
from datetime import datetime, timezone
import shutil
import re

p = Path("BOT_PIVOT_06G2_execution_secure.py")

ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = Path("data") / f"backup_v241_bollinger_width_{ts}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup / p.name)

txt = p.read_text()

helpers = r'''

# ============================================================
# V24.1 — Filtre largeur Bollinger minimale par actif
# ============================================================

V241_MIN_BB_WIDTH_BY_ASSET = {
    "US500": 10.0,
    "US100": 30.0,
    "US30": 50.0,
    "DE40": 30.0,
    "FR40": 15.0,
    "FRA40": 15.0,
    "UK100": 20.0,
    "J225": 100.0,

    "EURUSD": 0.00040,
    "GBPUSD": 0.00050,
    "USDJPY": 0.080,
    "EURJPY": 0.100,

    "GOLD": 8.0,
    "SILVER": 1.0,
    "OIL_CRUDE": 0.50,
    "OIL_BRENT": 0.50,

    "BTCUSD": 150.0,
    "ETHUSD": 15.0,
}


def v241_env_float_local(name, default):
    import os
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


def v241_min_bb_width(asset):
    import os
    asset = str(asset).upper()

    # Override possible sans modifier le code :
    # MIN_BB_WIDTH_BTCUSD=200
    env_name = f"MIN_BB_WIDTH_{asset}"
    try:
        if os.environ.get(env_name) is not None:
            return float(os.environ.get(env_name))
    except Exception:
        pass

    return float(V241_MIN_BB_WIDTH_BY_ASSET.get(asset, 0.0))


def v241_bb_width_spread_mult():
    # Sécurité complémentaire :
    # la Bollinger doit être au moins 3 fois plus large que le spread.
    return max(1.0, v241_env_float_local("MIN_BB_WIDTH_SPREAD_MULT", 3.0))


def v241_bb_width_check(asset, lower, upper):
    lower = float(lower)
    upper = float(upper)
    width = abs(upper - lower)

    min_absolute = v241_min_bb_width(asset)

    try:
        raw_bid, raw_ask = v24_market_bid_ask(asset)
        spread = abs(float(raw_ask) - float(raw_bid))
    except Exception:
        spread = 0.0

    min_spread = spread * v241_bb_width_spread_mult()
    required = max(float(min_absolute), float(min_spread))

    return {
        "ok": width >= required,
        "width": float(width),
        "min_absolute": float(min_absolute),
        "spread": float(spread),
        "min_spread": float(min_spread),
        "required": float(required),
    }

'''

if "V241_MIN_BB_WIDTH_BY_ASSET" not in txt:
    marker = "def build_limit_payload_secure("
    if marker not in txt:
        raise SystemExit("Impossible de trouver build_limit_payload_secure")
    txt = txt.replace(marker, helpers + "\n" + marker, 1)

if "bb_width_required_m5" not in txt:
    pattern = r'(enriched\["bb_middle_m5"\]\s*=\s*float\(bands\["middle"\]\)\s*\n)'

    insert = r'''\1
    # V24.1 — filtre Bollinger trop serrée.
    # Refuse le panier si l'écartement BB haute/basse est insuffisant
    # ou trop proche du spread réel.
    bb_check = v241_bb_width_check(
        asset,
        enriched["bb_lower_m5"],
        enriched["bb_upper_m5"],
    )

    enriched["bb_width_m5"] = float(bb_check["width"])
    enriched["bb_min_absolute_width_m5"] = float(bb_check["min_absolute"])
    enriched["bb_spread_m5_check"] = float(bb_check["spread"])
    enriched["bb_min_spread_width_m5"] = float(bb_check["min_spread"])
    enriched["bb_width_required_m5"] = float(bb_check["required"])

    if not bb_check["ok"]:
        print(
            f"{asset:10s} | BOLLINGER_WIDTH_TOO_SMALL | --  | {str(enriched.get('direction', '--')):4s} | "
            f"--         | FILTER    | "
            f"width={bb_check['width']:.5f} required={bb_check['required']:.5f} "
            f"abs_min={bb_check['min_absolute']:.5f} spread={bb_check['spread']:.5f}"
        )

        event({
            "event": "V24_BOLLINGER_WIDTH_TOO_SMALL",
            "asset": asset,
            "cycle_id": enriched.get("cycle_id"),
            "direction": enriched.get("direction"),
            "bb_lower_m5": enriched.get("bb_lower_m5"),
            "bb_upper_m5": enriched.get("bb_upper_m5"),
            "bb_width_m5": bb_check["width"],
            "bb_width_required_m5": bb_check["required"],
            "bb_min_absolute_width_m5": bb_check["min_absolute"],
            "bb_spread_m5_check": bb_check["spread"],
            "bb_min_spread_width_m5": bb_check["min_spread"],
        })

        raise RuntimeError(
            f"BOLLINGER_WIDTH_TOO_SMALL {asset}: "
            f"width={bb_check['width']:.5f} required={bb_check['required']:.5f}"
        )
'''

    txt2, n = re.subn(pattern, insert, txt, count=1)
    if n != 1:
        raise SystemExit("Impossible d'insérer le filtre après bb_middle_m5")
    txt = txt2
else:
    print("INFO: filtre largeur Bollinger déjà présent")

p.write_text(txt)

print("Backup :", backup)
print("PATCH BOLLINGER WIDTH TERMINÉ")
