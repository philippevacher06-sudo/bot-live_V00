# BOT_PIVOT_03_tick_stream.py
# Module 03 — WebSocket tick stream Capital.com
#
# Rôle :
# - se connecter au WebSocket Capital.com
# - s'abonner aux prix temps réel
# - recevoir bid / ask / spread
# - apprendre le spread médian par actif
# - écrire les ticks en JSONL dans data/ticks/
#
# Ce module ne trade pas.

import argparse
import asyncio
import json
import logging
import os
import statistics
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import websockets

import BOT_PIVOT_00_config as CFG


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

log = logging.getLogger("BOT_PIVOT_03_TICK_STREAM")


# ============================================================
# OUTILS
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_dotenv_files() -> None:
    """
    Charge les variables simples KEY=VALUE depuis :
    - .env local
    - ~/.env
    sans écraser les variables déjà présentes.
    """
    for path in [Path(".env"), Path.home() / ".env"]:
        if not path.exists():
            continue

        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def parse_assets(raw: str) -> List[str]:
    return [
        item.strip().upper()
        for item in raw.replace(";", ",").split(",")
        if item.strip()
    ]


def build_stream_url(session_payload: Dict[str, Any]) -> str:
    """
    Capital.com renvoie parfois streamingHost avec un slash final.
    La documentation indique l'URL /connect.
    """
    host = (
        session_payload.get("streamingHost")
        or session_payload.get("streamEndpoint")
        or "wss://api-streaming-capital.backend-capital.com/"
    )

    host = str(host).strip()

    if host.endswith("/connect"):
        return host

    return host.rstrip("/") + "/connect"


# ============================================================
# SESSION CAPITAL.COM
# ============================================================

def create_session() -> Dict[str, Any]:
    load_dotenv_files()

    api_key = os.environ.get("CAPITAL_API_KEY")
    identifier = (
        os.environ.get("CAPITAL_IDENTIFIER")
        or os.environ.get("CAPITAL_LOGIN")
        or os.environ.get("CAPITAL_EMAIL")
    )
    password = os.environ.get("CAPITAL_PASSWORD")

    if not api_key or not identifier or not password:
        raise RuntimeError(
            "Variables manquantes. Il faut CAPITAL_API_KEY, "
            "CAPITAL_IDENTIFIER ou CAPITAL_LOGIN, et CAPITAL_PASSWORD "
            "dans ~/.env ou .env."
        )

    base_url = CFG.BASE_URL.rstrip("/")
    url = f"{base_url}/api/v1/session"

    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "identifier": identifier,
        "password": password,
        "encryptedPassword": False,
    }

    r = requests.post(url, headers=headers, json=payload, timeout=20)

    if r.status_code >= 400:
        raise RuntimeError(
            f"Erreur session Capital.com HTTP {r.status_code}: {r.text[:500]}"
        )

    cst = r.headers.get("CST")
    security_token = r.headers.get("X-SECURITY-TOKEN")

    if not cst or not security_token:
        raise RuntimeError(
            "Session créée mais CST ou X-SECURITY-TOKEN absent dans les headers."
        )

    try:
        body = r.json()
    except Exception:
        body = {}

    stream_url = build_stream_url(body)

    return {
        "cst": cst,
        "security_token": security_token,
        "stream_url": stream_url,
        "body": body,
        "created_utc": utc_now_iso(),
    }


# ============================================================
# COLLECTEUR DE TICKS
# ============================================================

class TickCollector:
    def __init__(self, assets: List[str], max_spread_samples: int = 2000):
        self.assets = assets
        self.max_spread_samples = max_spread_samples

        self.tick_count = defaultdict(int)
        self.last_tick: Dict[str, Dict[str, Any]] = {}
        self.spreads = defaultdict(lambda: deque(maxlen=max_spread_samples))

        CFG.ensure_directories()
        CFG.TICKS_DIR.mkdir(parents=True, exist_ok=True)

        date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.tick_file = CFG.TICKS_DIR / f"ticks_{date_tag}.jsonl"

    def on_quote(self, payload: Dict[str, Any]) -> None:
        epic = payload.get("epic")

        if not epic:
            return

        bid = payload.get("bid")
        ask = payload.get("ofr")

        if bid is None or ask is None:
            return

        try:
            bid = float(bid)
            ask = float(ask)
        except Exception:
            return

        if bid <= 0 or ask <= 0:
            return

        spread = ask - bid
        mid = (bid + ask) / 2.0
        timestamp = payload.get("timestamp")

        tick = {
            "received_utc": utc_now_iso(),
            "epic": epic,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": spread,
            "timestamp": timestamp,
        }

        self.tick_count[epic] += 1
        self.last_tick[epic] = tick

        if spread >= 0:
            self.spreads[epic].append(spread)

        with self.tick_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(tick, ensure_ascii=False) + "\n")

    def median_spread(self, epic: str) -> Optional[float]:
        values = list(self.spreads.get(epic, []))

        if not values:
            return None

        return statistics.median(values)

    def print_summary(self) -> None:
        print()
        print("=" * 118)
        print("TICKS LIVE — Module 03")
        print("=" * 118)
        print("ACTIF      | TICKS | BID          | ASK          | MID          | SPREAD       | SPREAD MED   | AGE")
        print("-" * 118)

        now = time.time()

        for epic in self.assets:
            tick = self.last_tick.get(epic)
            count = self.tick_count.get(epic, 0)

            if not tick:
                print(f"{epic:10s} | {count:5d} | --")
                continue

            median = self.median_spread(epic)
            received_text = tick.get("received_utc", "")
            age = "?"

            try:
                dt = datetime.fromisoformat(received_text.replace("Z", "+00:00"))
                age_sec = max(0.0, now - dt.timestamp())
                age = f"{age_sec:.1f}s"
            except Exception:
                pass

            print(
                f"{epic:10s} | "
                f"{count:5d} | "
                f"{tick['bid']:<12.6f} | "
                f"{tick['ask']:<12.6f} | "
                f"{tick['mid']:<12.6f} | "
                f"{tick['spread']:<12.6f} | "
                f"{(median if median is not None else 0):<12.6f} | "
                f"{age}"
            )

        print("=" * 118)
        print(f"Fichier ticks : {self.tick_file}")
        print("=" * 118)


# ============================================================
# WEBSOCKET
# ============================================================

async def ping_loop(ws, cst: str, security_token: str, interval_sec: int = 300) -> None:
    correlation = 100000

    while True:
        await asyncio.sleep(interval_sec)

        correlation += 1
        msg = {
            "destination": "ping",
            "correlationId": str(correlation),
            "cst": cst,
            "securityToken": security_token,
        }

        await ws.send(json.dumps(msg))
        log.info("[PING] envoyé au WebSocket")


async def summary_loop(collector: TickCollector, interval_sec: int) -> None:
    while True:
        await asyncio.sleep(interval_sec)
        collector.print_summary()


async def run_stream(assets: List[str], seconds: int, print_every: int) -> None:
    session = create_session()

    cst = session["cst"]
    security_token = session["security_token"]
    stream_url = session["stream_url"]

    collector = TickCollector(assets)

    log.info("============================================================")
    log.info("BOT_PIVOT_03_TICK_STREAM")
    log.info(f"Actifs       : {', '.join(assets)}")
    log.info(f"Nb actifs    : {len(assets)}")
    log.info(f"Stream URL   : {stream_url}")
    log.info(f"Durée test   : {seconds} sec")
    log.info("============================================================")

    subscribe_msg = {
        "destination": "marketData.subscribe",
        "correlationId": "1",
        "cst": cst,
        "securityToken": security_token,
        "payload": {
            "epics": assets
        },
    }

    start = time.time()

    async with websockets.connect(stream_url, ping_interval=None, close_timeout=10) as ws:
        await ws.send(json.dumps(subscribe_msg))
        log.info("[SUBSCRIBE] envoyé")

        ping_task = asyncio.create_task(ping_loop(ws, cst, security_token))
        summary_task = asyncio.create_task(summary_loop(collector, print_every))

        try:
            while True:
                if seconds > 0 and time.time() - start >= seconds:
                    log.info("Durée de test atteinte.")
                    break

                raw = await asyncio.wait_for(ws.recv(), timeout=30)

                try:
                    msg = json.loads(raw)
                except Exception:
                    log.warning(f"Message non JSON : {raw[:200]}")
                    continue

                destination = msg.get("destination")
                status = msg.get("status")
                payload = msg.get("payload", {})

                if destination == "marketData.subscribe":
                    log.info(f"[SUBSCRIBE RESPONSE] status={status} payload={payload}")
                    continue

                if destination == "quote":
                    collector.on_quote(payload)
                    continue

                if destination == "ping":
                    log.info(f"[PING RESPONSE] status={status}")
                    continue

                if status and status != "OK":
                    log.warning(f"[MESSAGE] {msg}")
                    continue

        finally:
            ping_task.cancel()
            summary_task.cancel()

            try:
                await asyncio.gather(ping_task, summary_task, return_exceptions=True)
            except Exception:
                pass

            collector.print_summary()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BOT_PIVOT_03 — WebSocket tick stream Capital.com"
    )

    parser.add_argument(
        "--assets",
        default=",".join(CFG.ASSETS),
        help="Liste d'actifs séparés par virgule",
    )

    parser.add_argument(
        "--seconds",
        type=int,
        default=60,
        help="Durée du test en secondes. 0 = illimité.",
    )

    parser.add_argument(
        "--print-every",
        type=int,
        default=10,
        help="Affichage résumé toutes les N secondes.",
    )

    args = parser.parse_args()
    assets = parse_assets(args.assets)

    if len(assets) > 40:
        raise RuntimeError("Capital.com limite le WebSocket à 40 instruments maximum.")

    asyncio.run(run_stream(assets, args.seconds, args.print_every))


if __name__ == "__main__":
    main()
