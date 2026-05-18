# BOT_PIVOT_01_historical.py
# Module 01 — Historique M15 Capital.com
# Rôle : télécharger l'historique nécessaire au calcul des zones.
# Important : ce module ne trade pas.

import os
import csv
import json
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

import requests

import BOT_PIVOT_00_config as CFG


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

log = logging.getLogger("BOT_PIVOT_01_HISTORICAL")


# ============================================================
# CONSTANTES
# ============================================================

BAR_MINUTES = {
    "MINUTE": 1,
    "MINUTE_5": 5,
    "MINUTE_15": 15,
    "MINUTE_30": 30,
    "HOUR": 60,
    "HOUR_4": 240,
    "DAY": 1440,
    "WEEK": 10080,
}


# ============================================================
# ENV
# ============================================================

def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value

    except Exception as exc:
        log.warning(f"Impossible de charger {path}: {exc}")


def first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


# ============================================================
# TEMPS
# ============================================================

def utc_now_floor_minute() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(second=0, microsecond=0)


def cap_time(dt: datetime) -> str:
    """
    Format Capital.com :
    YYYY-MM-DDTHH:MM:SS
    basé sur UTC, sans suffixe Z.
    """
    return dt.astimezone(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S")


# ============================================================
# CLIENT CAPITAL.COM
# ============================================================

class CapitalHistoricalClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.cst = first_env("CAPITAL_CST", "CST")
        self.security_token = first_env(
            "CAPITAL_SECURITY_TOKEN",
            "X_SECURITY_TOKEN",
            "X-SECURITY-TOKEN",
            "SECURITY_TOKEN",
        )

    def login(self) -> None:
        api_key = first_env("CAPITAL_API_KEY", "X_CAP_API_KEY", "API_KEY")
        identifier = first_env("CAPITAL_IDENTIFIER", "CAPITAL_LOGIN", "IDENTIFIER", "LOGIN")
        password = first_env("CAPITAL_PASSWORD", "CAPITAL_API_PASSWORD", "PASSWORD")

        if not api_key or not identifier or not password:
            raise RuntimeError(
                "Identifiants Capital.com manquants.\n"
                "Crée ou vérifie ton fichier .env avec :\n"
                "CAPITAL_API_KEY=...\n"
                "CAPITAL_IDENTIFIER=...\n"
                "CAPITAL_PASSWORD=...\n"
            )

        url = f"{self.base_url}/api/v1/session"

        headers = {
            "X-CAP-API-KEY": api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "identifier": identifier,
            "password": password,
            "encryptedPassword": False,
        }

        log.info("Connexion Capital.com démo...")

        response = self.session.post(
            url,
            headers=headers,
            json=payload,
            timeout=20,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Erreur login Capital.com {response.status_code}: {response.text}"
            )

        self.cst = response.headers.get("CST")
        self.security_token = response.headers.get("X-SECURITY-TOKEN")

        if not self.cst or not self.security_token:
            raise RuntimeError("Connexion OK mais tokens CST / X-SECURITY-TOKEN absents.")

        log.info("Connexion OK.")

    def ensure_session(self) -> None:
        if self.cst and self.security_token:
            return
        self.login()

    def auth_headers(self) -> Dict[str, str]:
        self.ensure_session()

        return {
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token,
            "Content-Type": "application/json",
        }

    def get_prices_once(
        self,
        epic: str,
        resolution: str,
        start_utc: datetime,
        end_utc: datetime,
        max_points: int = 1000,
        retry: bool = True,
    ) -> List[Dict[str, Any]]:

        url = f"{self.base_url}/api/v1/prices/{epic}"

        params = {
            "resolution": resolution,
            "max": max_points,
            "from": cap_time(start_utc),
            "to": cap_time(end_utc),
        }

        response = self.session.get(
            url,
            headers=self.auth_headers(),
            params=params,
            timeout=30,
        )

        if response.status_code in (401, 403) and retry:
            log.warning(f"{epic} : session expirée, reconnexion...")
            self.cst = None
            self.security_token = None
            self.login()

            return self.get_prices_once(
                epic=epic,
                resolution=resolution,
                start_utc=start_utc,
                end_utc=end_utc,
                max_points=max_points,
                retry=False,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"{epic} : erreur historique {response.status_code}: {response.text}"
            )

        data = response.json()
        return data.get("prices", [])

    def get_prices_range(
        self,
        epic: str,
        resolution: str,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[Dict[str, Any]]:

        resolution = resolution.upper()

        if resolution not in BAR_MINUTES:
            raise ValueError(
                f"Résolution invalide : {resolution}. "
                f"Valeurs possibles : {', '.join(BAR_MINUTES.keys())}"
            )

        bar_minutes = BAR_MINUTES[resolution]

        # On prend 950 bougies par bloc pour rester sous la limite 1000.
        chunk_bars = 950
        chunk_delta = timedelta(minutes=bar_minutes * chunk_bars)

        all_prices: List[Dict[str, Any]] = []
        cursor = start_utc

        while cursor < end_utc:
            chunk_end = min(cursor + chunk_delta, end_utc)

            log.info(
                f"{epic} : {resolution} "
                f"{cap_time(cursor)} -> {cap_time(chunk_end)}"
            )

            prices = self.get_prices_once(
                epic=epic,
                resolution=resolution,
                start_utc=cursor,
                end_utc=chunk_end,
                max_points=1000,
            )

            all_prices.extend(prices)

            cursor = chunk_end + timedelta(seconds=1)

            # Respect prudent des limites API.
            time.sleep(0.15)

        return deduplicate_raw_prices(all_prices)


# ============================================================
# NORMALISATION
# ============================================================

def price_value(block: Dict[str, Any], side: str) -> Optional[float]:
    value = block.get(side)

    if value is None:
        return None

    try:
        return float(value)
    except Exception:
        return None


def mid_value(block: Dict[str, Any]) -> Optional[float]:
    bid = price_value(block, "bid")
    ask = price_value(block, "ask")

    if bid is not None and ask is not None:
        return (bid + ask) / 2.0

    if bid is not None:
        return bid

    if ask is not None:
        return ask

    return None


def normalize_candle(raw: Dict[str, Any]) -> Dict[str, Any]:
    open_block = raw.get("openPrice", {}) or {}
    high_block = raw.get("highPrice", {}) or {}
    low_block = raw.get("lowPrice", {}) or {}
    close_block = raw.get("closePrice", {}) or {}

    return {
        "snapshotTime": raw.get("snapshotTime"),
        "snapshotTimeUTC": raw.get("snapshotTimeUTC"),

        "open_bid": price_value(open_block, "bid"),
        "open_ask": price_value(open_block, "ask"),
        "open_mid": mid_value(open_block),

        "high_bid": price_value(high_block, "bid"),
        "high_ask": price_value(high_block, "ask"),
        "high_mid": mid_value(high_block),

        "low_bid": price_value(low_block, "bid"),
        "low_ask": price_value(low_block, "ask"),
        "low_mid": mid_value(low_block),

        "close_bid": price_value(close_block, "bid"),
        "close_ask": price_value(close_block, "ask"),
        "close_mid": mid_value(close_block),

        "volume": raw.get("lastTradedVolume"),
    }


def deduplicate_raw_prices(prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_time: Dict[str, Dict[str, Any]] = {}

    for item in prices:
        ts = item.get("snapshotTimeUTC") or item.get("snapshotTime")
        if not ts:
            continue
        by_time[ts] = item

    return [by_time[key] for key in sorted(by_time.keys())]


def normalize_prices(prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candles = [normalize_candle(item) for item in prices]

    candles = [
        c for c in candles
        if c.get("snapshotTimeUTC")
        and c.get("high_mid") is not None
        and c.get("low_mid") is not None
        and c.get("close_mid") is not None
    ]

    candles.sort(key=lambda x: x["snapshotTimeUTC"])
    return candles


# ============================================================
# SAUVEGARDE
# ============================================================

def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_csv(path: Path, candles: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not candles:
        return

    fields = list(candles[0].keys())

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(candles)


def download_asset(
    client: CapitalHistoricalClient,
    epic: str,
    resolution: str,
    days: int,
    write_csv: bool = True,
) -> bool:

    end_utc = utc_now_floor_minute()
    start_utc = end_utc - timedelta(days=days)

    try:
        raw_prices = client.get_prices_range(
            epic=epic,
            resolution=resolution,
            start_utc=start_utc,
            end_utc=end_utc,
        )

        candles = normalize_prices(raw_prices)

        payload = {
            "module": "BOT_PIVOT_01_historical",
            "bot": CFG.BOT_NAME,
            "strategy": CFG.STRATEGY_NAME,
            "epic": epic,
            "resolution": resolution,
            "days": days,
            "from_utc": cap_time(start_utc),
            "to_utc": cap_time(end_utc),
            "raw_count": len(raw_prices),
            "candle_count": len(candles),
            "candles": candles,
        }

        json_path = CFG.HISTORY_DIR / f"{epic}_{resolution}_{days}d.json"
        csv_path = CFG.HISTORY_DIR / f"{epic}_{resolution}_{days}d.csv"

        save_json(json_path, payload)

        if write_csv:
            save_csv(csv_path, candles)

        log.info(f"[OK] {epic} : {len(candles)} bougies -> {json_path}")
        return True

    except Exception as exc:
        log.error(f"[ERREUR] {epic} : {exc}")
        return False


# ============================================================
# CLI
# ============================================================

def parse_assets(raw: str) -> List[str]:
    return [
        item.strip().upper()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    ]


def main() -> None:
    CFG.ensure_directories()

    load_env_file(Path(".env"))
    load_env_file(Path.home() / ".env")

    parser = argparse.ArgumentParser(
        description="BOT_PIVOT_01 — téléchargement historique M15 pour zones"
    )

    parser.add_argument(
        "--assets",
        default=",".join(CFG.ASSETS),
        help="Liste d'actifs séparés par virgule",
    )

    parser.add_argument(
        "--resolution",
        default=CFG.HISTORY_RESOLUTION,
        choices=list(BAR_MINUTES.keys()),
        help="Résolution historique",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=CFG.HISTORY_DAYS,
        help="Nombre de jours d'historique",
    )

    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Ne pas générer les fichiers CSV",
    )

    args = parser.parse_args()

    assets = parse_assets(args.assets)

    log.info("============================================================")
    log.info("BOT_PIVOT_01_HISTORICAL")
    log.info("Rôle : historique pour calcul des zones")
    log.info(f"Base URL   : {CFG.BASE_URL}")
    log.info(f"Actifs     : {', '.join(assets)}")
    log.info(f"Résolution : {args.resolution}")
    log.info(f"Jours      : {args.days}")
    log.info(f"Sortie     : {CFG.HISTORY_DIR}")
    log.info("============================================================")

    client = CapitalHistoricalClient(base_url=CFG.BASE_URL)

    ok_count = 0
    error_count = 0

    for epic in assets:
        success = download_asset(
            client=client,
            epic=epic,
            resolution=args.resolution,
            days=args.days,
            write_csv=not args.no_csv,
        )

        if success:
            ok_count += 1
        else:
            error_count += 1

        time.sleep(0.25)

    log.info("============================================================")
    log.info(f"TERMINÉ — OK: {ok_count} | ERREURS: {error_count}")
    log.info("============================================================")

    if error_count:
        log.warning(
            "Si certains actifs échouent, il faudra vérifier leur EPIC exact chez Capital.com."
        )


if __name__ == "__main__":
    main()
