# BOT_PIVOT_06A_session_check.py
# Module 06A — test connexion REST Capital.com
# Aucun ordre réel. Aucun trade.

import os
import requests
from pathlib import Path

import BOT_PIVOT_00_config as CFG

ENV_FILE = Path(".env")

def load_env():
    if not ENV_FILE.exists():
        print("ERREUR : fichier .env introuvable")
        return

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

def mask(value):
    if not value:
        return "MANQUANT"
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]

def main():
    load_env()

    api_key = os.environ.get("CAPITAL_API_KEY")
    identifier = (
        os.environ.get("CAPITAL_IDENTIFIER")
        or os.environ.get("CAPITAL_LOGIN")
        or os.environ.get("CAPITAL_EMAIL")
    )
    password = os.environ.get("CAPITAL_PASSWORD")

    print()
    print("=" * 90)
    print("06A — TEST SESSION REST CAPITAL.COM")
    print("=" * 90)
    print("BASE_URL    :", CFG.BASE_URL)
    print("API_KEY     :", mask(api_key))
    print("IDENTIFIANT :", mask(identifier))
    print("PASSWORD    :", "OK" if password else "MANQUANT")
    print("-" * 90)

    if not api_key or not identifier or not password:
        print("ERREUR : variable .env manquante.")
        print("Il faut CAPITAL_API_KEY + CAPITAL_LOGIN/CAPITAL_IDENTIFIER + CAPITAL_PASSWORD")
        return

    url = f"{CFG.BASE_URL}/api/v1/session"

    payload = {
        "identifier": identifier,
        "password": password,
        "encryptedPassword": False
    }

    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
    except Exception as e:
        print("ERREUR REQUÊTE :", repr(e))
        return

    print("HTTP STATUS :", r.status_code)

    cst = r.headers.get("CST")
    token = r.headers.get("X-SECURITY-TOKEN")

    if r.status_code in (200, 201) and cst and token:
        print("SESSION     : OK")
        print("CST         :", mask(cst))
        print("SEC TOKEN   :", mask(token))
        print("-" * 90)
        print("06A VALIDÉ : connexion REST opérationnelle.")
    else:
        print("SESSION     : ÉCHEC")
        print("Réponse     :", r.text[:500])

    print("=" * 90)

if __name__ == "__main__":
    main()
