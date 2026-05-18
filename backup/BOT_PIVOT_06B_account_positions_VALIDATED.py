# BOT_PIVOT_06B_account_positions.py
# Module 06B — lecture compte + positions ouvertes
# Aucun ordre réel. Lecture uniquement.

import os
import json
import requests
from pathlib import Path

import BOT_PIVOT_00_config as CFG

ENV_FILE = Path(".env")

def load_env():
    if not ENV_FILE.exists():
        raise FileNotFoundError(".env introuvable")

    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def mask(value):
    if not value:
        return "--"
    value = str(value)
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]

def login():
    api_key = os.environ.get("CAPITAL_API_KEY")
    identifier = (
        os.environ.get("CAPITAL_IDENTIFIER")
        or os.environ.get("CAPITAL_LOGIN")
        or os.environ.get("CAPITAL_EMAIL")
    )
    password = os.environ.get("CAPITAL_PASSWORD")

    if not api_key or not identifier or not password:
        raise RuntimeError("Variables .env manquantes")

    url = f"{CFG.BASE_URL}/api/v1/session"

    headers = {
        "X-CAP-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "identifier": identifier,
        "password": password,
        "encryptedPassword": False,
    }

    r = requests.post(url, json=payload, headers=headers, timeout=15)

    if r.status_code not in (200, 201):
        raise RuntimeError(f"Login refusé HTTP {r.status_code} : {r.text[:300]}")

    cst = r.headers.get("CST")
    token = r.headers.get("X-SECURITY-TOKEN")

    if not cst or not token:
        raise RuntimeError("Tokens CST / X-SECURITY-TOKEN absents")

    return {
        "X-CAP-API-KEY": api_key,
        "CST": cst,
        "X-SECURITY-TOKEN": token,
        "Content-Type": "application/json",
    }

def get_json(headers, endpoint):
    url = f"{CFG.BASE_URL}{endpoint}"
    r = requests.get(url, headers=headers, timeout=15)

    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text[:500]}

    return r.status_code, data

def money(x):
    if x is None:
        return "--"
    try:
        return f"{float(x):.2f}"
    except Exception:
        return str(x)

def main():
    load_env()
    headers = login()

    print()
    print("=" * 120)
    print("06B — COMPTE + POSITIONS OUVERTES")
    print("=" * 120)
    print("SESSION : OK")
    print("CST     :", mask(headers.get("CST")))
    print("TOKEN   :", mask(headers.get("X-SECURITY-TOKEN")))
    print("-" * 120)

    # 1. Session active
    status, session_data = get_json(headers, "/api/v1/session")
    print("GET /session :", status)

    account_id = session_data.get("currentAccountId") or session_data.get("accountId")
    if account_id:
        print("Compte actif :", mask(account_id))

    print("-" * 120)

    # 2. Comptes
    status, accounts_data = get_json(headers, "/api/v1/accounts")
    print("GET /accounts :", status)

    accounts = accounts_data.get("accounts", [])

    if not accounts:
        print("Aucun compte retourné ou format inattendu.")
        print(json.dumps(accounts_data, ensure_ascii=False, indent=2)[:1000])
    else:
        print()
        print("COMPTES")
        print("-" * 120)
        print("ID          | NOM / TYPE              | DEVISE | BALANCE    | DISPONIBLE | P&L")
        print("-" * 120)

        for a in accounts:
            balance = a.get("balance", {}) or {}

            print(
                f"{mask(a.get('accountId')):11s} | "
                f"{str(a.get('accountName') or a.get('accountType') or '--')[:23]:23s} | "
                f"{str(a.get('currency') or balance.get('currency') or '--'):6s} | "
                f"{money(balance.get('balance')):10s} | "
                f"{money(balance.get('available')):10s} | "
                f"{money(balance.get('profitLoss')):8s}"
            )

    print("-" * 120)

    # 3. Préférences compte
    status, pref_data = get_json(headers, "/api/v1/accounts/preferences")
    print("GET /accounts/preferences :", status)

    if status == 200:
        print("hedgingMode :", pref_data.get("hedgingMode", "--"))
        print("leverages   :", json.dumps(pref_data.get("leverages", {}), ensure_ascii=False)[:500])
    else:
        print(json.dumps(pref_data, ensure_ascii=False, indent=2)[:800])

    print("-" * 120)

    # 4. Positions ouvertes
    status, pos_data = get_json(headers, "/api/v1/positions")
    print("GET /positions :", status)

    positions = pos_data.get("positions", [])

    if not positions:
        print()
        print("POSITIONS OUVERTES : aucune position ouverte.")
    else:
        print()
        print("POSITIONS OUVERTES")
        print("-" * 120)
        print("EPIC       | DIR  | SIZE       | ENTRY        | DEAL ID       | P&L")
        print("-" * 120)

        for item in positions:
            p = item.get("position", {}) or {}
            m = item.get("market", {}) or {}

            epic = m.get("epic") or p.get("epic") or "--"
            direction = p.get("direction", "--")
            size = p.get("size", "--")
            level = p.get("level", p.get("openLevel", "--"))
            deal_id = p.get("dealId", "--")
            profit_loss = p.get("profitLoss", "--")

            print(
                f"{str(epic)[:10]:10s} | "
                f"{str(direction)[:4]:4s} | "
                f"{str(size)[:10]:10s} | "
                f"{str(level)[:12]:12s} | "
                f"{mask(deal_id):13s} | "
                f"{str(profit_loss)[:10]:10s}"
            )

    print("=" * 120)
    print("06B VALIDÉ si : compte lu + préférences lues + positions lues.")
    print("Aucun ordre n'a été envoyé.")

if __name__ == "__main__":
    main()
