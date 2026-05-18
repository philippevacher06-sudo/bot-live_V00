# BOT_PIVOT_00B_pnl_eur.py
# Conversion P&L brut -> EUR pour BOT-PIVOT

import json
from pathlib import Path
import BOT_PIVOT_00_config as CFG

SIGNALS_FILE = CFG.DATA_DIR / "ticks" / "signals_latest.json"

ASSET_PNL_CURRENCY = {
    # Indices EUR
    "DE40": "EUR",
    "FR40": "EUR",

    # Indices USD
    "US500": "USD",
    "US100": "USD",
    "US30": "USD",

    # Indice GBP
    "UK100": "GBP",

    # Japon / JPY
    "J225": "JPY",

    # Forex
    "EURUSD": "USD",
    "GBPUSD": "USD",
    "USDJPY": "JPY",
    "EURJPY": "JPY",

    # Matières premières / crypto en USD
    "GOLD": "USD",
    "SILVER": "USD",
    "OIL_CRUDE": "USD",
    "BTCUSD": "USD",
    "ETHUSD": "USD",
}

FALLBACK_EURUSD = 1.17
FALLBACK_EURJPY = 185.0
FALLBACK_GBPUSD = 1.35


def load_json(path, default):
    try:
        p = Path(path)
        if not p.exists():
            return default
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_signals():
    raw = load_json(SIGNALS_FILE, {})
    if isinstance(raw, dict):
        if isinstance(raw.get("signals"), dict):
            return raw["signals"]
        if isinstance(raw.get("assets"), dict):
            return raw["assets"]

        direct = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                direct[str(k).upper()] = v
        return direct
    return {}


def val(d, keys, default=None):
    if not isinstance(d, dict):
        return default
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default


def signal_mid(sig):
    x = val(sig, ["mid", "price", "current_price", "last_mid"], None)
    try:
        return float(x)
    except Exception:
        return None


def mid_for(asset, signals=None):
    if signals is None:
        signals = load_signals()

    sig = signals.get(asset) or signals.get(asset.upper()) or {}
    x = signal_mid(sig)
    if x and x > 0:
        return x
    return None


def asset_currency(asset):
    return ASSET_PNL_CURRENCY.get(str(asset).upper(), "EUR")


def raw_to_eur_rate_for_asset(asset, signals=None):
    """
    Retourne le coefficient à appliquer au P&L brut pour obtenir un P&L EUR.
    Exemple :
    - USD -> EUR : 1 / EURUSD
    - JPY -> EUR : 1 / EURJPY
    - GBP -> EUR : GBPUSD / EURUSD
    """
    ccy = asset_currency(asset)

    if ccy == "EUR":
        return 1.0

    eurusd = mid_for("EURUSD", signals) or FALLBACK_EURUSD
    eurjpy = mid_for("EURJPY", signals) or FALLBACK_EURJPY
    gbpusd = mid_for("GBPUSD", signals) or FALLBACK_GBPUSD

    if ccy == "USD":
        return 1.0 / eurusd

    if ccy == "JPY":
        return 1.0 / eurjpy

    if ccy == "GBP":
        return gbpusd / eurusd

    return 1.0


def raw_pnl(direction, entry_price, current_price, size):
    direction = str(direction).upper()
    entry_price = float(entry_price)
    current_price = float(current_price)
    size = float(size)

    if direction == "BUY":
        return (current_price - entry_price) * size
    return (entry_price - current_price) * size


def pnl_eur(asset, direction, entry_price, current_price, size, signals=None):
    raw = raw_pnl(direction, entry_price, current_price, size)
    rate = raw_to_eur_rate_for_asset(asset, signals)
    return raw * rate


def profit_distance_for_target_eur(asset, size, target_eur, signals=None):
    """
    Convertit un objectif EUR en distance de prix.
    distance = target_eur / (size × taux_conversion_du_PnL_brut_vers_EUR)
    """
    size = float(size)
    target_eur = float(target_eur)

    if size <= 0:
        raise RuntimeError(f"Taille invalide pour {asset}: {size}")

    rate = raw_to_eur_rate_for_asset(asset, signals)

    if rate <= 0:
        raise RuntimeError(f"Taux conversion invalide pour {asset}: {rate}")

    return target_eur / (size * rate)


def describe_asset(asset, signals=None):
    ccy = asset_currency(asset)
    rate = raw_to_eur_rate_for_asset(asset, signals)
    return ccy, rate
