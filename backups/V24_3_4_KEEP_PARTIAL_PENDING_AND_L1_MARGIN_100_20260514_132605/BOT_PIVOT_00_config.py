# BOT_PIVOT_00_config.py
# Configuration centrale du BOT-PIVOT
# Stratégie : Zones + RangePositionTick + Cycle séquentiel 5 niveaux

import os
from pathlib import Path


# ============================================================
# IDENTITÉ DU BOT
# ============================================================

BOT_NAME = "BOT_PIVOT"
BOT_VERSION = "0.1"
STRATEGY_NAME = "Zones + RangePositionTick + Cycle 5 niveaux"


# ============================================================
# DOSSIERS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"
ZONES_DIR = DATA_DIR / "zones"
TICKS_DIR = DATA_DIR / "ticks"

LOG_DIR = BASE_DIR / "logs"
BACKUP_DIR = BASE_DIR / "backup"


# ============================================================
# API CAPITAL.COM
# ============================================================

BASE_URL = "https://demo-api-capital.backend-capital.com"

# Les identifiants seront lus depuis le fichier .env ou l'environnement :
# CAPITAL_API_KEY
# CAPITAL_IDENTIFIER
# CAPITAL_PASSWORD


# ============================================================
# ACTIFS
# ============================================================

# On inclut US30 car tu l'as utilisé dans tes exemples.
ASSETS = [
    "US500",
    "US100",
    "US30",
    "DE40",
    "FR40",
    "UK100",
    "J225",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "EURJPY",
    "GOLD",
    "SILVER",
    "OIL_CRUDE",
    "BTCUSD",
    "ETHUSD",
]


# ============================================================
# HISTORIQUE POUR LES ZONES
# ============================================================

# L'historique sert uniquement à construire les zones.
# Le trading réel se fera au tick.
HISTORY_RESOLUTION = "MINUTE_15"
HISTORY_DAYS = 30

# Recalcul des zones une fois par jour.
ZONES_REFRESH_HOUR_UTC = 6


# ============================================================
# CALCUL DES ZONES SUPPORT / RÉSISTANCE
# ============================================================

MAX_ZONES_PER_ASSET = 10

# Découpage de la plage de prix en paliers pour compter
# les zones les plus souvent touchées.
PRICE_BUCKETS = 500

# Marge de contact autour d'une zone.
# Exemple : 0.0005 = 0,05 % du prix.
ZONE_TOUCH_MARGIN_PCT = 0.0005

# Taille minimale et maximale d'une zone.
MIN_ZONE_WIDTH_PCT = 0.0005
MAX_ZONE_WIDTH_PCT = 0.0040


# ============================================================
# WEBSOCKET / TICKS
# ============================================================

# Le trading réel se fait au tick.
TICK_HISTORY_MINUTES = 14

# Si le dernier tick est trop vieux, on interdit le trading.
# V24.3 demo : 20s est plus cohérent avec une collecte ticks de 45s,
# tout en restant assez frais pour du scalp.
MAX_TICK_AGE_SEC = float(os.getenv("MAX_TICK_AGE_SEC", "20"))

# Fréquence de boucle du bot.
MAIN_LOOP_SLEEP_SEC = 0.20


# ============================================================
# RANGEPOSITIONTICK
# ============================================================

# RangePositionTick =
# position du prix actuel dans le range tick des 14 dernières minutes.
RANGE_LOOKBACK_MINUTES = 14

# Signal BUY : prix très bas dans son range récent.
RANGE_BUY_THRESHOLD = 20.0

# Signal SELL : prix très haut dans son range récent.
RANGE_SELL_THRESHOLD = 80.0

# Micro-confirmation au tick :
# nombre minimal de ticks de retournement avant entrée.
MICRO_REVERSAL_MIN_TICKS = 2


# ============================================================
# CYCLE SÉQUENTIEL 5 NIVEAUX
# ============================================================

MAX_LEVEL = 5

# Niveaux 1 à 4 :
# fermeture obligatoire après 120 secondes si TP non touché.
MAX_POSITION_LIFE_SEC_LEVEL_1_TO_4 = 120

# Niveau 5 :
# pas de fermeture automatique à 120 secondes.
LEVEL_5_HAS_TIME_LIMIT = False

# Stop loss niveau 5 :
# 1 % du capital.
LEVEL_5_STOP_LOSS_PCT = 0.01

# TP de base niveau 1.
BASE_TP_EUR = 0.20

LEVEL_MULTIPLIERS = {
    1: 1,
    2: 2,
    3: 4,
    4: 8,
    5: 16,
}

# TP de base par niveau :
# niveau 1 = 0,10 €
# niveau 2 = 0,20 €
# niveau 3 = 0,40 €
# niveau 4 = 0,80 €
# niveau 5 = 1,60 €
#
# Ensuite, le TP peut être ajusté par la dérive réelle.


# ============================================================
# TAILLES DE BASE
# ============================================================

# IMPORTANT :
# Ces tailles sont des tailles de départ provisoires.
# Elles devront être validées avec les tailles minimales réelles
# acceptées par Capital.com pour chaque actif.
BASE_SIZE_BY_ASSET = {
    "US500": 0.15,
    "US100": 0.042,
    "US30": 0.024,
    "DE40": 0.051,
    "FR40": 0.15,
    "UK100": 0.12,
    "J225": 0.30,

    "EURUSD": 1500,
    "GBPUSD": 1200,
    "USDJPY": 1800,
    "EURJPY": 1800,

    "GOLD": 0.27,
    "SILVER": 15,
    # V24.2: OIL was too heavy for a ~3.5k EUR demo account.
    # L1/L2/L3 now become 4 / 8 / 12 instead of 12 / 24 / 36.
    "OIL_CRUDE": 4,

    "BTCUSD": 0.0018,
    "ETHUSD": 0.06,
}


# ============================================================
# DÉRIVE POUR AJUSTEMENT DU TP
# ============================================================

# Référence :
# 0.002 = 0,20 %
REF_DRIFT_PCT = 0.002

# Bornes de sécurité du coefficient de dérive.
DRIFT_COEFF_MIN = 1.0
DRIFT_COEFF_MAX = 2.5


# ============================================================
# SPREAD ADAPTATIF
# ============================================================

# Pas de spread fixe inventé par actif.
# Le bot apprend le spread réel au tick.
SPREAD_MODE = "LEARN"

# Nombre minimum de ticks avant d'autoriser un trade.
SPREAD_LEARNING_MIN_TICKS = 150

# Spread autorisé :
# spread actuel <= spread médian observé × ce multiplicateur.
SPREAD_MAX_MULTIPLIER = 2.5


# ============================================================
# SÉCURITÉS GLOBALES
# ============================================================

# Mode sécurité :
# True = le bot calcule et affiche, mais n'envoie pas d'ordre réel.
DRY_RUN = True

# Perte journalière maximale globale.
MAX_DAILY_LOSS_EUR = 20.0

# Pause après échec complet d'un cycle niveau 5.
COOLDOWN_AFTER_FAILED_CYCLE_SEC = 1800

# Une seule position active par actif.
ONE_POSITION_PER_ASSET = True

# Pas de niveau 6.
ALLOW_LEVEL_ABOVE_5 = False


# ============================================================
# FONCTIONS UTILITAIRES
# ============================================================

def ensure_directories() -> None:
    for path in [
        DATA_DIR,
        HISTORY_DIR,
        ZONES_DIR,
        TICKS_DIR,
        LOG_DIR,
        BACKUP_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def get_base_size(asset: str) -> float:
    return BASE_SIZE_BY_ASSET.get(asset, 0.01)


def get_level_multiplier(level: int) -> float:
    if level not in LEVEL_MULTIPLIERS:
        raise ValueError(f"Niveau invalide : {level}")
    return LEVEL_MULTIPLIERS[level]


def get_base_tp_for_level(level: int) -> float:
    return TP_EUR_BY_LEVEL.get(level, BASE_TP_EUR * get_level_multiplier(level))


def get_level5_stop_loss_eur(capital_eur: float) -> float:
    return capital_eur * LEVEL_5_STOP_LOSS_PCT


def adverse_drift(direction: str, entry_price: float, cut_price: float) -> float:
    direction = direction.upper()

    if direction == "SELL":
        return max(0.0, cut_price - entry_price)

    if direction == "BUY":
        return max(0.0, entry_price - cut_price)

    raise ValueError(f"Direction invalide : {direction}")


def drift_coefficient(direction: str, entry_price: float, cut_price: float) -> float:
    if entry_price <= 0:
        return 1.0

    drift = adverse_drift(direction, entry_price, cut_price)
    drift_pct = drift / entry_price

    coeff = drift_pct / REF_DRIFT_PCT

    coeff = max(DRIFT_COEFF_MIN, coeff)
    coeff = min(DRIFT_COEFF_MAX, coeff)

    return coeff


def adjusted_tp_for_level(level: int, direction: str, entry_price: float, cut_price: float) -> float:
    base_tp = get_base_tp_for_level(level)
    coeff = drift_coefficient(direction, entry_price, cut_price)
    return base_tp * coeff


def size_for_level(asset: str, level: int) -> float:
    base_size = get_base_size(asset)
    multiplier = get_level_multiplier(level)
    return base_size * multiplier


def describe_cycle() -> list:
    rows = []

    for level in range(1, MAX_LEVEL + 1):
        rows.append({
            "level": level,
            "multiplier": get_level_multiplier(level),
            "base_tp_eur": get_base_tp_for_level(level),
            "time_limit_sec": (
                MAX_POSITION_LIFE_SEC_LEVEL_1_TO_4
                if level < 5
                else None
            ),
            "level5_stop_pct": LEVEL_5_STOP_LOSS_PCT if level == 5 else None,
        })

    return rows


if __name__ == "__main__":
    ensure_directories()

    print("============================================================")
    print(f"{BOT_NAME} {BOT_VERSION}")
    print(STRATEGY_NAME)
    print("============================================================")
    print(f"Dossier base        : {BASE_DIR}")
    print(f"Nombre d'actifs     : {len(ASSETS)}")
    print(f"Actifs              : {', '.join(ASSETS)}")
    print(f"Historique zones    : {HISTORY_RESOLUTION} sur {HISTORY_DAYS} jours")
    print(f"Trading réel        : WebSocket tick")
    print(f"Range tick          : {RANGE_LOOKBACK_MINUTES} minutes")
    print(f"Spread              : {SPREAD_MODE}")
    print(f"DRY_RUN             : {DRY_RUN}")
    print("------------------------------------------------------------")
    print("Cycle :")

    for row in describe_cycle():
        if row["level"] < 5:
            print(
                f"Niveau {row['level']} | "
                f"x{row['multiplier']} | "
                f"TP base {row['base_tp_eur']:.2f} € | "
                f"durée max {row['time_limit_sec']} sec"
            )
        else:
            print(
                f"Niveau {row['level']} | "
                f"x{row['multiplier']} | "
                f"TP base {row['base_tp_eur']:.2f} € | "
                f"pas de limite 120 sec | "
                f"stop {row['level5_stop_pct'] * 100:.1f} % capital"
            )

    print("------------------------------------------------------------")
    print("Test stop niveau 5 avec capital 3500 € :")
    print(f"Stop niveau 5 = {get_level5_stop_loss_eur(3500):.2f} €")
    print("Dossiers OK.")


# V23 — TP explicite par niveau
TP_EUR_BY_LEVEL = {
    # V24.1 — TP logiciel panier : 0,20 € par jambe ouverte.
    # 1 jambe  = 0,20 €
    # 2 jambes = 0,40 €
    # 3 jambes = 0,60 €
    # niveaux 4/5 conservés par sécurité si un ancien flux les appelle.
    1: 0.20,
    2: 0.40,
    3: 0.60,
    4: 0.80,
    5: 1.00,
}

MIN_CONTEXT_SCORE_ENTRY = 3

MIN_CONTEXT_SCORE_NEXT_LEVEL = 3

MIN_CONTEXT_SCORE_KEEP = 2

CLOSE_WEAK_CONTEXT_AFTER_SEC = 300


# V23.1 — sortie rapide si le contexte invalide la position
EARLY_INVALIDATION_LOSS_EUR = 0.50
EARLY_WEAK_LOSS_EUR = 0.80


# V23.2 — entrée plus stricte si VWAP contraire
MIN_CONTEXT_SCORE_ENTRY_VWAP_AGAINST = 4
