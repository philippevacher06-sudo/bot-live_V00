from pathlib import Path
from datetime import datetime, timezone
import shutil
import re

ROOT = Path(".")
ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = ROOT / "data" / f"backup_v241_core_patch_{ts}"
backup.mkdir(parents=True, exist_ok=True)

files = [
    Path("BOT_PIVOT_00_config.py"),
    Path("BOT_PIVOT_05_cycle_engine.py"),
    Path("BOT_PIVOT_06G2_execution_secure.py"),
]

for f in files:
    shutil.copy2(f, backup / f.name)

print("Backup :", backup)

# ============================================================
# 1) CONFIG — TP V24.1 officiel : 0.20 € par jambe
# ============================================================
p = Path("BOT_PIVOT_00_config.py")
txt = p.read_text()

txt = txt.replace("BASE_TP_EUR = 0.30", "BASE_TP_EUR = 0.20")

txt = re.sub(
    r"TP_EUR_BY_LEVEL\s*=\s*\{\s*1:\s*[^}]+?\n\}",
    """TP_EUR_BY_LEVEL = {
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
}""",
    txt,
    count=1,
    flags=re.S,
)

p.write_text(txt)


# ============================================================
# 2) MOTEUR 05 — marquer les cycles comme pilotés par 06G2
# ============================================================
p = Path("BOT_PIVOT_05_cycle_engine.py")
txt = p.read_text()

old = '''        "level_open_utc": now,
    }'''
new = '''        "level_open_utc": now,

        # V24.1 :
        # Le moteur 05 crée seulement l'autorisation d'entrée.
        # Toute la vie réelle du panier broker L1/L2/L3 est pilotée par 06G2.
        "basket_mode": "V24_BASKET_LIMIT",
        "execution_owner": "BOT_PIVOT_06G2",
    }'''

if old not in txt:
    print("WARN: insertion new_cycle non trouvée ou déjà patchée")
else:
    txt = txt.replace(old, new, 1)

old = '''        tp = float(cycle["tp_eur"])

        if not fresh:'''
new = '''        tp = float(cycle["tp_eur"])

        # V24.1 :
        # Si le cycle est un panier broker V24.1, le moteur 05 ne doit plus
        # déclencher CLOSE_TP / CLOSE_CONTEXT / NEXT_LEVEL.
        # Le 06G2 devient la seule source de vérité pour open/pending/close.
        if (
            cycle.get("basket_mode") == "V24_BASKET_LIMIT"
            or cycle.get("execution_owner") == "BOT_PIVOT_06G2"
        ):
            print(
                f"{asset:10s} | HOLD_BASKET_EXEC_OWNER | "
                f"L{level} | {direction:4s} | "
                f"pilotage panier délégué à 06G2"
            )
            set_position(state, asset, cycle, "BASKET_EXEC_OWNER_06G2")
            continue

        if not fresh:'''

if old not in txt:
    print("WARN: insertion garde 05 non trouvée ou déjà patchée")
else:
    txt = txt.replace(old, new, 1)

p.write_text(txt)


# ============================================================
# 3) 06G2 — expiration paniers vides / ratés + marge TP configurable
# ============================================================
p = Path("BOT_PIVOT_06G2_execution_secure.py")
txt = p.read_text()

helpers = r'''

# ============================================================
# V24.1 — garde-fous paniers LIMIT ratés / vides
# ============================================================

def v241_env_float(name, default):
    import os
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return float(default)


def v24_pending_basket_max_age_sec():
    # Un panier LIMIT non exécuté ne doit pas bloquer la marge trop longtemps.
    return max(30.0, v241_env_float("PENDING_BASKET_MAX_AGE_SEC", 180.0))


def v24_tp_safety_margin_eur():
    # Le PnL est déjà conservateur : BUY au BID, SELL à l'ASK.
    # On ne rajoute pas 0,05 € par défaut, sinon le +0,20 devient +0,25.
    return max(0.0, v241_env_float("V24_TP_SAFETY_MARGIN_EUR", 0.0))


def v24_age_sec_from_iso(iso_text):
    from datetime import datetime, timezone
    if not iso_text:
        return 0.0
    try:
        s = str(iso_text).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
    except Exception:
        return 0.0


def v24_cancel_all_pending_limits(headers, asset, levels, reason):
    cancel_results = []

    for level_key, rec in list(levels.items()):
        if not str(rec.get("status", "")).startswith("PENDING_LIMIT"):
            continue

        working_id = rec.get("workingDealId")

        if not working_id:
            try:
                resolved_id, resolve_reason, resolve_response = resolve_working_order_id(headers, rec)
            except Exception as e:
                resolved_id, resolve_reason, resolve_response = None, f"RESOLVE_EXCEPTION:{e}", None

            if resolved_id:
                rec["workingDealId"] = resolved_id
                rec["workingDealId_source"] = resolve_reason
                rec["workingDealId_resolved_utc"] = utc()
                working_id = resolved_id
            else:
                cancel_results.append({
                    "level": level_key,
                    "ok": False,
                    "reason": "NO_WORKING_ID_TO_CANCEL",
                    "resolve_reason": resolve_reason,
                })
                continue

        try:
            ok_cancel, cancel_info = cancel_working_order_secure(
                headers=headers,
                asset=asset,
                working_id=working_id,
                reason=reason,
                old_exec=rec,
            )
        except Exception as e:
            ok_cancel, cancel_info = False, {"exception": str(e)}

        rec["cancel_requested_utc"] = utc()
        rec["cancel_reason"] = reason
        rec["status"] = "CANCELLED_PENDING_LIMIT" if ok_cancel else "CANCEL_FAILED_PENDING_LIMIT"

        cancel_results.append({
            "level": level_key,
            "ok": bool(ok_cancel),
            "workingDealId": working_id,
            "info": cancel_info,
        })

    return cancel_results

'''

if "def v24_pending_basket_max_age_sec()" not in txt:
    txt = txt.replace("def v24_process_basket(", helpers + "\ndef v24_process_basket(", 1)
else:
    print("INFO: helpers V24.1 déjà présents")

txt = txt.replace(
    "tp_safety_margin = 0.05",
    "tp_safety_margin = v24_tp_safety_margin_eur()",
    1,
)

old = '''    pending_count = len([
        rec for rec in levels.values()
        if str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])
'''
new = '''    pending_count = len([
        rec for rec in levels.values()
        if str(rec.get("status", "")).startswith("PENDING_LIMIT")
    ])

    active_exec["last_pending_count"] = int(pending_count)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_basket_age_sec"] = float(v24_age_sec_from_iso(active_exec.get("created_utc")))
    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)

    # V24.1 — panier vide : rien d'ouvert, rien en attente.
    # Il ne doit surtout pas rester protégé par BASKET_KEEP.
    if open_count <= 0 and pending_count <= 0:
        reason = "V24_BASKET_EMPTY_RESET"
        exec_state.setdefault("cancelled", []).append({
            **active_exec,
            "cancelled_reason": reason,
            "cancelled_utc": utc(),
        })
        exec_state.setdefault("active", {}).pop(asset, None)
        reset_cycle_idle(asset, reason)
        B.save_json(B.EXEC_STATE_FILE, exec_state)

        print(
            f"{asset:10s} | BASKET_EMPTY_RESET | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | open=0 pending=0 -> EXEC supprimé"
        )
        return True, positions

    # V24.1 — panier raté : aucune jambe ouverte, ordres LIMIT encore en attente.
    # Si le cycle moteur est repassé IDLE ou si le panier est trop vieux,
    # on annule les LIMIT pour libérer la marge.
    if open_count <= 0 and pending_count > 0:
        age_sec = v24_age_sec_from_iso(active_exec.get("created_utc"))
        max_age = v24_pending_basket_max_age_sec()
        cycle_missing = bool(cycle.get("cycle_missing"))

        if cycle_missing or age_sec >= max_age:
            reason = "V24_PENDING_BASKET_SIGNAL_LOST_CANCEL" if cycle_missing else "V24_PENDING_BASKET_EXPIRED_CANCEL"

            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            active_exec["cancel_results"] = cancel_results
            active_exec["cancelled_reason"] = reason
            active_exec["cancelled_utc"] = utc()
            active_exec["last_basket_age_sec"] = float(age_sec)

            exec_state.setdefault("cancelled", []).append(active_exec)
            exec_state.setdefault("active", {}).pop(asset, None)
            reset_cycle_idle(asset, reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_PENDING_CANCEL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"open=0 pending={pending_count} age={age_sec:.1f}s max={max_age:.1f}s reason={reason}"
            )
            return True, positions
'''

if old not in txt:
    print("WARN: bloc pending_count non trouvé ou déjà patché")
else:
    txt = txt.replace(old, new, 1)

old = '''                          "basket_mode": True,
                      }'''
new = '''                          "basket_mode": True,
                          "cycle_missing": True,
                      }'''

if old not in txt:
    print("WARN: synthetic cycle_missing non trouvé ou déjà patché")
else:
    txt = txt.replace(old, new, 1)

p.write_text(txt)

print()
print("PATCH V24.1 CORE TERMINÉ")
