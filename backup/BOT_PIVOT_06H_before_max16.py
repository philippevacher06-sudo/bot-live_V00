# BOT_PIVOT_06H_execution_demo_guarded.py
# Wrapper sécurisé pour envoyer de vrais ordres sur compte DEMO Capital.com
# Version 24/7 :
# - pas de login si aucun cycle actif et aucun deal réel à gérer
# - URL DEMO obligatoire
# - verrou explicite OK_ENVOI_DEMO
# - limite du nombre de cycles actifs
# - parse_confirm sécurisé

import json
import argparse
from pathlib import Path

import BOT_PIVOT_00_config as CFG
import BOT_PIVOT_06G_execution_from_cycle_state as G


UNLOCK_VALUE = "OK_ENVOI_DEMO"


def assets_list(raw):
    if not raw or str(raw).upper() == "ALL":
        return list(CFG.ASSETS)
    return [
        x.strip().upper()
        for x in str(raw).replace(";", ",").split(",")
        if x.strip()
    ]


def safe_parse_confirm(confirm):
    if not isinstance(confirm, dict):
        return None

    if confirm.get("dealId"):
        return confirm.get("dealId")

    affected = confirm.get("affectedDeals") or []
    if affected and isinstance(affected, list):
        first = affected[0] or {}
        if isinstance(first, dict):
            return first.get("dealId")

    return None


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def count_active_cycles(assets):
    state_file = CFG.DATA_DIR / "cycles" / "cycle_state.json"
    state = load_json(state_file, {})
    slots = state.get("assets", {}) if isinstance(state, dict) else {}

    active = []

    for asset in assets:
        slot = slots.get(asset, {})
        cycle = slot.get("cycle")
        status = str(slot.get("status", "")).upper()

        if status == "IN_POSITION" and isinstance(cycle, dict):
            active.append({
                "asset": asset,
                "level": cycle.get("level"),
                "direction": cycle.get("direction"),
                "size": cycle.get("size"),
                "cycle_id": cycle.get("cycle_id"),
            })

    return active


def count_real_exec_deals():
    exec_file = CFG.DATA_DIR / "execution" / "cycle_execution_state.json"
    state = load_json(exec_file, {"active": {}, "closed": []})
    active = state.get("active", {}) if isinstance(state, dict) else {}

    real_deals = []

    for asset, deal in active.items():
        if not isinstance(deal, dict):
            continue

        # Les faux deals DRY_RUN ne nécessitent pas de login broker.
        if deal.get("dry_run") is True:
            continue

        real_deals.append({
            "asset": asset,
            "dealId": deal.get("dealId"),
            "level": deal.get("level"),
            "direction": deal.get("direction"),
            "size": deal.get("size"),
        })

    return real_deals


def ensure_demo_url():
    base_url = str(getattr(CFG, "BASE_URL", ""))
    if "demo-api-capital" not in base_url:
        raise RuntimeError(f"REFUS : BASE_URL n'est pas l'URL DEMO : {base_url}")
    return base_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default="ALL")
    parser.add_argument("--real-demo", action="store_true")
    parser.add_argument("--unlock", default="")
    parser.add_argument("--max-cycles", type=int, default=3)
    args = parser.parse_args()

    assets = assets_list(args.assets)

    print()
    print("=" * 160)
    print("06H — EXECUTION DEMO GARDEE")
    print("=" * 160)

    base_url = ensure_demo_url()
    print("BASE_URL :", base_url)

    active_cycles = count_active_cycles(assets)
    real_deals = count_real_exec_deals()

    print("Cycles actifs détectés :", len(active_cycles))
    for c in active_cycles:
        print(
            f"- {c['asset']:10s} "
            f"L{c['level']} "
            f"{c['direction']} "
            f"size={c['size']} "
            f"cycle={c['cycle_id']}"
        )

    print("Deals réels DEMO suivis :", len(real_deals))
    for d in real_deals:
        print(
            f"- {d['asset']:10s} "
            f"L{d['level']} "
            f"{d['direction']} "
            f"size={d['size']} "
            f"dealId={d['dealId']}"
        )

    if not args.real_demo:
        print()
        print("MODE : DRY_RUN via 06G")
        print("Aucun ordre réel démo ne sera envoyé.")
        G.SEND_REAL_ORDERS = False
        G.execute_from_cycle(None, assets)
        return

    if args.unlock != UNLOCK_VALUE:
        raise RuntimeError(
            "REFUS : verrou manquant. Pour envoyer en DEMO, ajouter : "
            f"--unlock {UNLOCK_VALUE}"
        )

    if len(active_cycles) > args.max_cycles:
        raise RuntimeError(
            f"REFUS : {len(active_cycles)} cycles actifs > limite autorisée {args.max_cycles}. "
            "Réduire les actifs ou augmenter volontairement --max-cycles."
        )

    # Point essentiel pour le 24/7 :
    # s'il n'y a rien à ouvrir et rien à fermer, on ne fait PAS de login REST.
    if len(active_cycles) == 0 and len(real_deals) == 0:
        print()
        print("MODE : ORDRES DEMO ACTIFS")
        print("Aucun cycle actif + aucun deal réel suivi.")
        print("Aucun login Capital.com. Aucun ordre envoyé.")
        return

    print()
    print("MODE : ORDRES DEMO ACTIFS")
    print("Verrou reçu :", args.unlock)
    print("Limite cycles :", args.max_cycles)
    print("Envoi/gestion possible uniquement sur compte DEMO.")

    G.SEND_REAL_ORDERS = True
    G.parse_confirm = safe_parse_confirm

    G.load_env()
    headers = G.login()
    G.execute_from_cycle(headers, assets)


if __name__ == "__main__":
    main()
