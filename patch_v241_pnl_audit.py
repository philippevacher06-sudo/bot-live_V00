from pathlib import Path
from datetime import datetime, timezone
import shutil
import re

p = Path("BOT_PIVOT_06G2_execution_secure.py")

ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = Path("data") / f"backup_v241_pnl_audit_{ts}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup / p.name)

txt = p.read_text()

old_func_pattern = r'''def v24_leg_pnl_eur\(asset, direction, entry_price, current_price, size\):
    """
    PnL panier en euros.
    Utilise la conversion existante de BOT_PIVOT_00B_pnl_eur via profit_distance_for_target_eur.
    """
    entry_price = float\(entry_price\)
    current_price = float\(current_price\)
    size = float\(size\)

    if direction == "BUY":
        price_move = current_price - entry_price
    else:
        price_move = entry_price - current_price

    try:
        one_eur_distance = float\(PNL.profit_distance_for_target_eur\(asset, size, 1.0\)\)
        if one_eur_distance > 0:
            return float\(price_move / one_eur_distance\)
    except Exception:
        pass

    # Fallback brut si conversion indisponible.
    return float\(price_move \* size\)
'''

new_func = r'''def v24_bool_env(name, default=True):
    import os
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "")


def v24_float_or_none(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def v24_position_pnl_candidates(item):
    """
    Recherche prudente des champs PnL éventuellement fournis par Capital.com.
    On ne les utilise pas encore pour fermer : on les logue pour comparaison.
    """
    out = []

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                full = f"{path}.{key}" if path else key
                lk = key.lower()

                if any(s in lk for s in ("pnl", "profit", "loss", "upl", "unreal")):
                    val = v24_float_or_none(v)
                    if val is not None:
                        out.append({"path": full, "value": val})

                if isinstance(v, (dict, list)):
                    walk(v, full)

        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                if isinstance(v, (dict, list)):
                    walk(v, f"{path}[{i}]")

    walk(item)
    return out[:20]


def v24_leg_pnl_detail(asset, direction, entry_price, current_price, size):
    """
    Audit PnL V24.1.

    Prix :
    - BUY valorisé à la sortie au BID / côté bas
    - SELL valorisé à la sortie à l'ASK / côté haut

    Calcul :
    - méthode distance_for_target_eur
    - méthode centrale PNL.pnl_eur
    - brut indicatif
    - PnL retenu = minimum conservateur entre les méthodes EUR disponibles
    """
    entry_price = float(entry_price)
    current_price = float(current_price)
    size = float(size)
    d = str(direction).upper()

    if d == "BUY":
        price_move = current_price - entry_price
    else:
        price_move = entry_price - current_price

    raw_price_times_size = float(price_move * size)

    pnl_distance = None
    one_eur_distance = None
    distance_error = None

    try:
        one_eur_distance = float(PNL.profit_distance_for_target_eur(asset, size, 1.0))
        if one_eur_distance > 0:
            pnl_distance = float(price_move / one_eur_distance)
    except Exception as e:
        distance_error = str(e)

    pnl_module = None
    module_error = None

    try:
        pnl_module = float(PNL.pnl_eur(asset, d, entry_price, current_price, size))
    except Exception as e:
        module_error = str(e)

    eur_candidates = []
    if pnl_distance is not None:
        eur_candidates.append(float(pnl_distance))
    if pnl_module is not None:
        eur_candidates.append(float(pnl_module))

    if eur_candidates:
        # Pour ne pas fermer trop tôt, on retient le plus conservateur.
        pnl_selected = float(min(eur_candidates))
        pnl_source = "CONSERVATIVE_MIN_DISTANCE_MODULE"
    else:
        pnl_selected = float(raw_price_times_size)
        pnl_source = "FALLBACK_RAW_PRICE_TIMES_SIZE"

    return {
        "asset": asset,
        "direction": d,
        "entry_price": float(entry_price),
        "current_price": float(current_price),
        "size": float(size),
        "price_move": float(price_move),
        "raw_price_times_size": float(raw_price_times_size),
        "one_eur_distance": one_eur_distance,
        "pnl_distance_eur": pnl_distance,
        "pnl_module_eur": pnl_module,
        "pnl_selected_eur": pnl_selected,
        "pnl_source": pnl_source,
        "distance_error": distance_error,
        "module_error": module_error,
    }


def v24_leg_pnl_eur(asset, direction, entry_price, current_price, size):
    return float(
        v24_leg_pnl_detail(
            asset=asset,
            direction=direction,
            entry_price=entry_price,
            current_price=current_price,
            size=size,
        )["pnl_selected_eur"]
    )
'''

txt2, n = re.subn(old_func_pattern, new_func, txt, count=1, flags=re.S)
if n != 1:
    raise SystemExit("Impossible de remplacer v24_leg_pnl_eur")
txt = txt2


old_basket_pattern = r'''def v24_basket_current_pnl\(asset, basket_exec\):
    """
    Calcule le PnL global du panier sur les niveaux OPEN_POSITION.
    BUY sort au BID.
    SELL sort à l'ASK.
    """
    raw_bid, raw_ask = v24_market_bid_ask\(asset\)

    # V24 sécurité :
    # Pour éviter une fermeture faussement gagnante à cause d'un bid/ask inversé
    # ou mal interprété, on valorise toujours de façon conservatrice.
    low_side = min\(float\(raw_bid\), float\(raw_ask\)\)
    high_side = max\(float\(raw_bid\), float\(raw_ask\)\)

    total = 0.0
    open_count = 0

    for level_key, rec in basket_exec.get\("levels", {}\).items\(\):
        if rec.get\("status"\) != "OPEN_POSITION":
            continue

        direction = rec.get\("direction"\)
        entry = rec.get\("brokerEntryPrice"\)
        size = rec.get\("size"\)

        if entry is None or size is None:
            continue

        # BUY se ferme au côté bas du spread.
        # SELL se ferme au côté haut du spread.
        current = low_side if direction == "BUY" else high_side
        pnl = v24_leg_pnl_eur\(asset, direction, entry, current, size\)

        rec\["last_pnl_eur"\] = float\(pnl\)
        rec\["last_price_used"\] = float\(current\)
        rec\["last_raw_bid"\] = float\(raw_bid\)
        rec\["last_raw_ask"\] = float\(raw_ask\)
        rec\["last_price_side"\] = "LOW_SIDE_FOR_BUY" if direction == "BUY" else "HIGH_SIDE_FOR_SELL"

        total \+= float\(pnl\)
        open_count \+= 1

    target = float\(0.20 \* open_count\) if open_count > 0 else None

    return total, open_count, target
'''

new_basket = r'''def v24_basket_current_pnl(asset, basket_exec, broker_items=None):
    """
    Calcule le PnL global du panier sur les niveaux OPEN_POSITION.

    Règle prix :
    - BUY sort au BID / côté bas
    - SELL sort à l'ASK / côté haut

    Règle sécurité :
    - PnL retenu = calcul EUR conservateur
    - audit détaillé logué pour comparaison avec Capital.com
    """
    raw_bid, raw_ask = v24_market_bid_ask(asset)

    low_side = min(float(raw_bid), float(raw_ask))
    high_side = max(float(raw_bid), float(raw_ask))

    broker_items = broker_items or []
    broker_by_deal = {}

    for item in broker_items:
        try:
            did = pos_deal_id(item)
            if did:
                broker_by_deal[did] = item
        except Exception:
            pass

    total = 0.0
    open_count = 0
    audit_legs = []

    for level_key, rec in basket_exec.get("levels", {}).items():
        if rec.get("status") != "OPEN_POSITION":
            continue

        direction = rec.get("direction")
        entry = rec.get("brokerEntryPrice")
        size = rec.get("size")

        if entry is None or size is None:
            rec["last_pnl_error"] = "MISSING_ENTRY_OR_SIZE"
            continue

        # BUY se ferme au côté bas du spread.
        # SELL se ferme au côté haut du spread.
        current = low_side if direction == "BUY" else high_side
        price_side = "BID_LOW_SIDE_FOR_BUY" if direction == "BUY" else "ASK_HIGH_SIDE_FOR_SELL"

        detail = v24_leg_pnl_detail(asset, direction, entry, current, size)
        pnl = float(detail["pnl_selected_eur"])

        broker_deal_id = rec.get("brokerDealId") or rec.get("dealId")
        broker_item = broker_by_deal.get(broker_deal_id)
        broker_pnl_candidates = v24_position_pnl_candidates(broker_item) if broker_item else []

        rec["last_pnl_eur"] = float(pnl)
        rec["last_pnl_detail"] = detail
        rec["last_broker_pnl_candidates"] = broker_pnl_candidates
        rec["last_price_used"] = float(current)
        rec["last_raw_bid"] = float(raw_bid)
        rec["last_raw_ask"] = float(raw_ask)
        rec["last_price_side"] = price_side

        total += float(pnl)
        open_count += 1

        audit_legs.append({
            "level": str(level_key),
            "direction": direction,
            "entry": float(entry),
            "size": float(size),
            "raw_bid": float(raw_bid),
            "raw_ask": float(raw_ask),
            "exit_used": float(current),
            "price_side": price_side,
            "pnl_selected_eur": float(pnl),
            "pnl_distance_eur": detail.get("pnl_distance_eur"),
            "pnl_module_eur": detail.get("pnl_module_eur"),
            "raw_price_times_size": detail.get("raw_price_times_size"),
            "pnl_source": detail.get("pnl_source"),
            "broker_pnl_candidates": broker_pnl_candidates[:5],
        })

    target = float(0.20 * open_count) if open_count > 0 else None

    basket_exec["last_pnl_audit"] = {
        "asset": asset,
        "raw_bid": float(raw_bid),
        "raw_ask": float(raw_ask),
        "low_side": float(low_side),
        "high_side": float(high_side),
        "open_count": int(open_count),
        "target": target,
        "total_selected_eur": float(total),
        "legs": audit_legs,
        "checked_utc": utc(),
    }

    if open_count > 0 and v24_bool_env("V24_PNL_AUDIT", True):
        for leg in audit_legs:
            broker_short = ",".join(
                f"{x.get('path')}={x.get('value')}"
                for x in leg.get("broker_pnl_candidates", [])[:3]
            ) or "none"

            print(
                f"{asset:10s} | PNL_AUDIT_LEG | L{leg['level']:<3} | {str(leg['direction']):4s} | "
                f"entry={leg['entry']:.6f} size={leg['size']:.6f} "
                f"bid={leg['raw_bid']:.6f} ask={leg['raw_ask']:.6f} "
                f"exit={leg['exit_used']:.6f} side={leg['price_side']} "
                f"pnl_sel={leg['pnl_selected_eur']:.4f} "
                f"pnl_dist={leg['pnl_distance_eur']} "
                f"pnl_mod={leg['pnl_module_eur']} "
                f"raw={leg['raw_price_times_size']} "
                f"src={leg['pnl_source']} "
                f"broker={broker_short}"
            )

        print(
            f"{asset:10s} | PNL_AUDIT_TOTAL | 1-3 | {str(basket_exec.get('direction', '--')):4s} | "
            f"open={open_count} pnl={total:.4f} target={target}"
        )

        try:
            event({
                "event": "V24_BASKET_PNL_AUDIT",
                "asset": asset,
                "cycle_id": basket_exec.get("cycle_id"),
                "audit": basket_exec.get("last_pnl_audit"),
            })
        except Exception:
            pass

    return total, open_count, target
'''

txt2, n = re.subn(old_basket_pattern, new_basket, txt, count=1, flags=re.S)
if n != 1:
    raise SystemExit("Impossible de remplacer v24_basket_current_pnl")
txt = txt2

txt = txt.replace(
    "pnl_total, open_count, target = v24_basket_current_pnl(asset, active_exec)",
    "pnl_total, open_count, target = v24_basket_current_pnl(asset, active_exec, broker_items=broker_items)",
    1,
)

p.write_text(txt)

print("Backup :", backup)
print("PATCH PNL AUDIT TERMINÉ")
