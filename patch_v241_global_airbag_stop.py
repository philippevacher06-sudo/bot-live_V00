from pathlib import Path
from datetime import datetime, timezone
import shutil
import re

p = Path("BOT_PIVOT_06G2_execution_secure.py")

ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = Path("data") / f"backup_v241_global_airbag_stop_{ts}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup / p.name)

txt = p.read_text()

helpers = r'''

# ============================================================
# V24.1 — Stop broker airbag global panier
# ============================================================

def v241_stop_airbag_step_mult():
    # Distance supplémentaire au-delà de L3.
    # 1.5 = stop sous/au-dessus de L3 à 1,5 step.
    return max(0.5, v241_env_float_local("STOP_AIRBAG_STEP_MULT", 1.5))


def v241_stop_airbag_spread_mult():
    # Sécurité minimale liée au spread.
    return max(1.0, v241_env_float_local("STOP_AIRBAG_SPREAD_MULT", 3.0))


def v241_broker_min_stop_distance(asset):
    """
    Lecture prudente des règles broker Capital.com.
    Selon les marchés, le nom de règle peut varier.
    """
    try:
        market = B._market_json(asset)
        rules = market.get("dealingRules", {}) or {}

        keys = [
            "minGuaranteedStopDistance",
            "minStopDistance",
            "minStopOrProfitDistance",
            "minGuaranteedStopOrProfitDistance",
            "minNormalStopOrLimitDistance",
        ]

        vals = []

        for k in keys:
            if k in rules:
                value, unit = B._rule_value(rules.get(k))
                if value is not None:
                    vals.append(float(value))

        return max(vals) if vals else 0.0

    except Exception:
        return 0.0


def v241_round_stop_distance(asset, distance):
    """
    Arrondit le stopDistance au pas broker si disponible.
    """
    distance = float(distance)

    try:
        market = B._market_json(asset)
        rules = market.get("dealingRules", {}) or {}
        step_value, step_unit = B._rule_value(rules.get("minStepDistance"))

        if step_value is not None:
            return float(B._round_up_to_step(distance, float(step_value)))

    except Exception:
        pass

    return round(distance, 10)


def v241_apply_global_airbag_stop(asset, direction, payload, bollinger_levels, current_level):
    """
    Applique un stopDistance global panier.

    BUY :
    - L1/L2/L3 partagent un stop théorique sous L3.

    SELL :
    - L1/L2/L3 partagent un stop théorique au-dessus de L3.

    Le broker reçoit un stopDistance propre à chaque jambe,
    mais le niveau de stop final est aligné autour du même airbag global.
    """
    direction = str(direction).upper()
    current_level = int(current_level)

    l1 = float(bollinger_levels["L1"])
    l2 = float(bollinger_levels["L2"])
    l3 = float(bollinger_levels["L3"])
    entry_level = float(payload["level"])

    step = abs(l2 - l1)
    if step <= 0:
        step = abs(l3 - l1) / 2.0

    try:
        raw_bid, raw_ask = v24_market_bid_ask(asset)
        spread = abs(float(raw_ask) - float(raw_bid))
    except Exception:
        spread = 0.0

    min_stop = v241_broker_min_stop_distance(asset)

    extra = max(
        float(step) * v241_stop_airbag_step_mult(),
        float(spread) * v241_stop_airbag_spread_mult(),
        float(min_stop),
    )

    if direction == "BUY":
        global_stop_level = l3 - extra
        stop_distance = entry_level - global_stop_level
    else:
        global_stop_level = l3 + extra
        stop_distance = global_stop_level - entry_level

    stop_distance = max(float(stop_distance), float(min_stop), 0.00000001)
    stop_distance = v241_round_stop_distance(asset, stop_distance)

    # On impose uniquement stopDistance.
    # stopLevel éventuel supprimé pour éviter conflit payload broker.
    payload.pop("stopLevel", None)
    payload["stopDistance"] = float(stop_distance)

    print(
        f"{asset:10s} | GLOBAL_AIRBAG_STOP | L{current_level:<3} | {direction:4s} | "
        f"entry={entry_level:.6f} stopLevel≈{global_stop_level:.6f} "
        f"stopDistance={stop_distance:.6f} step={step:.6f} spread={spread:.6f} minStop={min_stop:.6f}"
    )

    try:
        event({
            "event": "V24_GLOBAL_AIRBAG_STOP",
            "asset": asset,
            "direction": direction,
            "level": current_level,
            "entry_level": entry_level,
            "global_stop_level": global_stop_level,
            "stop_distance": stop_distance,
            "step": step,
            "spread": spread,
            "min_stop": min_stop,
            "stop_airbag_step_mult": v241_stop_airbag_step_mult(),
            "stop_airbag_spread_mult": v241_stop_airbag_spread_mult(),
        })
    except Exception:
        pass

    return payload

'''

if "def v241_apply_global_airbag_stop(" not in txt:
    marker = "def build_limit_payload_secure("
    if marker not in txt:
        raise SystemExit("Impossible de trouver build_limit_payload_secure")
    txt = txt.replace(marker, helpers + "\n" + marker, 1)
else:
    print("INFO: helpers stop airbag déjà présents")


old = '''    payload["level"] = float(bollinger_levels[bollinger_key])

    # V24.1 BOT-PIVOT BOLLINGER :
    # aucun TP broker individuel par jambe.
    # La sortie se fait uniquement par TP logiciel cumulé du panier :
    # 1 jambe ouverte = +0.20 €
    # 2 jambes ouvertes = +0.40 €
    # 3 jambes ouvertes = +0.60 €
    for k in ("profitDistance", "profitLevel", "profitAmount", "takeProfitLevel"):
        payload.pop(k, None)



    return payload
'''

new = '''    payload["level"] = float(bollinger_levels[bollinger_key])

    # V24.1 — stop broker airbag global panier.
    # Le stop doit protéger l'ensemble du panier, pas couper L1 trop tôt.
    payload = v241_apply_global_airbag_stop(
        asset=asset,
        direction=direction,
        payload=payload,
        bollinger_levels=bollinger_levels,
        current_level=level,
    )

    # V24.1 BOT-PIVOT BOLLINGER :
    # aucun TP broker individuel par jambe.
    # La sortie se fait uniquement par TP logiciel cumulé du panier :
    # 1 jambe ouverte = +0.20 €
    # 2 jambes ouvertes = +0.40 €
    # 3 jambes ouvertes = +0.60 €
    for k in ("profitDistance", "profitLevel", "profitAmount", "takeProfitLevel"):
        payload.pop(k, None)

    return payload
'''

if old not in txt:
    print("WARN: bloc build_limit_payload_secure non trouvé exactement, tentative regex")

    pattern = r'''(payload\["level"\]\s*=\s*float\(bollinger_levels\[bollinger_key\]\)\s*\n)(.*?)(\s*return payload)'''
    replacement = r'''\1
    # V24.1 — stop broker airbag global panier.
    payload = v241_apply_global_airbag_stop(
        asset=asset,
        direction=direction,
        payload=payload,
        bollinger_levels=bollinger_levels,
        current_level=level,
    )

    # V24.1 BOT-PIVOT BOLLINGER :
    # aucun TP broker individuel par jambe.
    for k in ("profitDistance", "profitLevel", "profitAmount", "takeProfitLevel"):
        payload.pop(k, None)
\3'''
    txt2, n = re.subn(pattern, replacement, txt, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("Impossible de patcher build_limit_payload_secure")
    txt = txt2
else:
    txt = txt.replace(old, new, 1)


# Nettoyage metadata trompeuse : broker_tp_eur ne doit plus faire croire à un TP broker.
txt = txt.replace(
    '"broker_tp_distance": payload.get("profitDistance"),\n          "broker_tp_eur": cycle.get("broker_tp_eur", 0.20),',
    '"broker_tp_distance": None,\n              "software_tp_note": "NO_BROKER_TP__BASKET_SOFTWARE_TP_ONLY",',
)

txt = txt.replace(
    '    c["broker_tp_eur"] = 0.20\n',
    '    c["software_leg_reference_tp_eur"] = float(0.20 * level)\n',
)

p.write_text(txt)

print("Backup :", backup)
print("PATCH GLOBAL AIRBAG STOP TERMINÉ")
