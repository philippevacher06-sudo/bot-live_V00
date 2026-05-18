#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch BOT-PIVOT V24.1 SCALP ACTIVE — sécurité broker/state.

Objectif :
- corriger le matching trop strict des working orders Capital.com,
- empêcher BASKET_EMPTY_RESET si le broker garde encore position/ordre,
- nettoyer les ordres pending orphelins,
- annuler les pending restants après TP_OK / TP_FAIL,
- annuler les pending restants d'un panier partiel trop vieux.

À lancer depuis : /home/philippe_vacher06/bot-pivot/live
"""
from pathlib import Path
from datetime import datetime
import re
import sys

TARGET = Path("BOT_PIVOT_06G2_execution_secure.py")


def fail(msg: str) -> None:
    print(f"ERREUR PATCH : {msg}")
    sys.exit(1)


def replace_once(s: str, old: str, new: str, label: str, already_marker: str | None = None) -> str:
    if already_marker and already_marker in s:
        print(f"SKIP {label} : déjà présent ({already_marker})")
        return s
    if old not in s:
        fail(f"bloc introuvable : {label}")
    print(f"OK {label}")
    return s.replace(old, new, 1)


def main() -> None:
    if not TARGET.exists():
        fail(f"fichier introuvable : {TARGET}. Lance ce script depuis le dossier live.")

    s = TARGET.read_text(encoding="utf-8")
    backup = TARGET.with_suffix(TARGET.suffix + f".bak_scalp_active_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup.write_text(s, encoding="utf-8")
    print(f"Backup créé : {backup}")

    # ============================================================
    # 1) Remplacer working_order_matches_exec par version tolérante
    #    + ajouter helpers broker cleanup.
    # ============================================================
    if "def v24_cancel_broker_pending_for_asset" in s and "size_tol" in s:
        print("SKIP matching/helpers : déjà présents")
    else:
        pattern = r'def working_order_matches_exec\(item, active_exec\):.*?\n\ndef resolve_working_order_id'
        new_block = r'''def working_order_matches_exec(item, active_exec):
    """
    Match prudent et tolérant :
    - asset / epic
    - direction
    - niveau LIMIT prioritaire
    - taille avec tolérance broker

    Capital.com peut arrondir une taille locale 0.4499999999 en 0.44.
    Un matching trop strict crée des ordres orphelins.
    """
    d = working_order_data(item)

    epic = d.get("epic") or item.get("epic")
    direction = d.get("direction") or item.get("direction")
    size = d.get("orderSize") or d.get("size") or item.get("orderSize") or item.get("size")
    level = d.get("orderLevel") or d.get("level") or item.get("orderLevel") or item.get("level")

    if epic != active_exec.get("asset"):
        return False

    if str(direction).upper() != str(active_exec.get("direction")).upper():
        return False

    # Le niveau LIMIT est le critère prioritaire après asset/direction.
    try:
        expected_level = float(active_exec.get("limit_price"))
        actual_level = float(level)
        level_tol = max(1e-8, abs(expected_level) * 1e-7)
        if abs(actual_level - expected_level) > level_tol:
            return False
    except Exception:
        return False

    # Tolérance de taille volontairement souple à cause des arrondis broker.
    try:
        expected_size = float(active_exec.get("size"))
        actual_size = float(size)
        size_tol = max(0.02, abs(expected_size) * 0.03, 1e-9)
        if abs(actual_size - expected_size) > size_tol:
            return False
    except Exception:
        return False

    return True


def v24_env_float_safe(name, default):
    try:
        import os
        return float(os.getenv(name, str(default)))
    except Exception:
        return float(default)


def v24_partial_basket_pending_max_age_sec():
    """
    Durée maximale des pending restants quand une jambe est déjà ouverte.
    En SCALP ACTIVE, L2/L3 ne doivent pas traîner trop longtemps.
    """
    return max(10.0, v24_env_float_safe("PARTIAL_BASKET_PENDING_MAX_AGE_SEC", 90.0))


def v24_broker_positions_for_asset_from_list(positions, asset, direction=None):
    """
    Filtre les positions broker pour un actif.
    Utilisé avant tout reset local dangereux.
    """
    out = []
    for p in positions or []:
        if not isinstance(p, dict):
            continue

        m = p.get("market", {}) or {}
        pos = p.get("position", {}) or {}

        epic = m.get("epic") or pos.get("epic") or p.get("epic") or ""
        name = m.get("instrumentName") or ""

        if epic != asset and asset not in str(epic) and asset not in str(name):
            continue

        if direction:
            pdir = pos.get("direction") or p.get("direction") or ""
            if str(pdir).upper() != str(direction).upper():
                continue

        out.append(p)

    return out


def v24_broker_pending_orders_for_asset(headers, asset, direction=None):
    """
    Relit directement /workingorders côté broker pour savoir si un actif
    a encore des ordres LIMIT en attente.
    """
    status, data = B.api_get(headers, "/api/v1/workingorders")
    items = normalize_working_orders_response(data)
    out = []

    for item in items:
        if not isinstance(item, dict):
            continue

        d = working_order_data(item)
        m = item.get("marketData", {}) or item.get("market", {}) or {}

        epic = d.get("epic") or item.get("epic") or m.get("epic") or ""
        name = m.get("instrumentName") or ""

        if epic != asset and asset not in str(epic) and asset not in str(name):
            continue

        odir = d.get("direction") or item.get("direction") or ""
        if direction and str(odir).upper() != str(direction).upper():
            continue

        out.append(item)

    return out, status, data


def v24_cancel_broker_pending_for_asset(headers, asset, direction=None, reason="V24_BROKER_PENDING_CLEANUP"):
    """
    Annule tous les working orders broker encore actifs pour l'actif.
    Sert de filet de sécurité contre les ordres orphelins.
    """
    orders, status, raw = v24_broker_pending_orders_for_asset(
        headers=headers,
        asset=asset,
        direction=direction,
    )

    results = []

    for item in orders:
        working_id = working_order_deal_id(item)
        d = working_order_data(item)

        if not working_id:
            results.append({
                "ok": False,
                "reason": "NO_WORKING_ID_FOR_BROKER_PENDING_CLEANUP",
                "item": item,
            })
            continue

        try:
            ok_cancel, cancel_info = cancel_working_order_secure(
                headers=headers,
                asset=asset,
                working_id=working_id,
                reason=reason,
                old_exec={
                    "asset": asset,
                    "direction": d.get("direction") or direction,
                    "size": d.get("orderSize") or d.get("size"),
                    "limit_price": d.get("orderLevel") or d.get("level"),
                    "workingDealId": working_id,
                },
            )
        except Exception as e:
            ok_cancel, cancel_info = False, {"exception": str(e)}

        results.append({
            "working_id": working_id,
            "ok": bool(ok_cancel),
            "info": cancel_info,
        })

    return results



def resolve_working_order_id'''
        s2, n = re.subn(pattern, new_block, s, count=1, flags=re.S)
        if n != 1:
            fail("remplacement working_order_matches_exec/helpers non effectué")
        s = s2
        print("OK matching tolérant + helpers broker cleanup")

    # ============================================================
    # 2) TP panier : annuler les pending restants après TP_OK / TP_FAIL.
    # ============================================================
    old_tp = '''        if ok:
            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": "V24_BASKET_GLOBAL_TP",
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

            reset_cycle_idle(asset, "V24_BASKET_GLOBAL_TP")

            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_TP_OK | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
            )

            return True, positions_after

        print(
            f"{asset:10s} | BASKET_TP_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
        )
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions
'''
    new_tp = '''        if ok:
            # TP atteint : les positions sont fermées.
            # On nettoie aussi les LIMIT restants du panier côté broker.
            try:
                tp_pending_cancel_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason="V24_BASKET_GLOBAL_TP_CANCEL_REMAINING_PENDING",
                )
                active_exec["tp_pending_cancel_results"] = tp_pending_cancel_results
            except Exception as e:
                active_exec["tp_pending_cancel_error"] = str(e)

            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": "V24_BASKET_GLOBAL_TP",
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

            reset_cycle_idle(asset, "V24_BASKET_GLOBAL_TP")

            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_TP_OK | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
            )

            return True, positions_after

        # TP atteint mais fermeture échouée :
        # on garde le panier actif pour retry, mais on annule les pending restants
        # afin d'éviter L2/L3 tardifs et libérer la marge.
        try:
            tp_fail_cancel_results = v24_cancel_broker_pending_for_asset(
                headers=headers,
                asset=asset,
                direction=direction,
                reason="V24_BASKET_TP_FAIL_CANCEL_PENDING_TO_FREE_MARGIN",
            )
            active_exec["tp_fail_pending_cancel_results"] = tp_fail_cancel_results
        except Exception as e:
            active_exec["tp_fail_pending_cancel_error"] = str(e)

        active_exec["last_tp_fail_utc"] = utc()
        active_exec["last_tp_fail_pnl_eur"] = float(pnl_total)
        active_exec["last_tp_fail_target_eur"] = float(target)

        exec_state.setdefault("active", {})[asset] = active_exec

        print(
            f"{asset:10s} | BASKET_TP_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} target={target:.4f}"
        )
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions
'''
    s = replace_once(
        s,
        old_tp,
        new_tp,
        "TP_OK/TP_FAIL cleanup pending restants",
        already_marker="V24_BASKET_TP_FAIL_CANCEL_PENDING_TO_FREE_MARGIN",
    )

    # ============================================================
    # 3) Panier partiel : open > 0 et pending > 0, annuler pending trop vieux.
    # ============================================================
    old_partial_anchor = '''    active_exec["last_pending_count"] = int(pending_count)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_basket_age_sec"] = float(v24_age_sec_from_iso(active_exec.get("created_utc")))
    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)

    # V24.1 — panier vide : rien d'ouvert, rien en attente.
'''
    new_partial_anchor = '''    active_exec["last_pending_count"] = int(pending_count)
    active_exec["last_open_count"] = int(open_count)
    active_exec["last_basket_age_sec"] = float(v24_age_sec_from_iso(active_exec.get("created_utc")))
    exec_state.setdefault("active", {})[asset] = active_exec
    B.save_json(B.EXEC_STATE_FILE, exec_state)

    # V24.1 SCALP ACTIVE — panier partiel :
    # une position est ouverte, mais L2/L3 restent en attente.
    # Ces pending restants ne doivent pas traîner trop longtemps,
    # sinon ils bloquent la marge et peuvent entrer trop tard.
    if open_count > 0 and pending_count > 0:
        age_sec = v24_age_sec_from_iso(active_exec.get("created_utc"))
        partial_max_age = v24_partial_basket_pending_max_age_sec()

        if age_sec >= partial_max_age:
            reason = "V24_PARTIAL_BASKET_PENDING_EXPIRED_CANCEL"

            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason=reason + "_BROKER_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["partial_pending_cancel_results"] = cancel_results
            active_exec["partial_pending_broker_cleanup_results"] = broker_cleanup_results
            active_exec["partial_pending_cancel_utc"] = utc()
            active_exec["partial_pending_cancel_reason"] = reason
            active_exec["last_basket_age_sec"] = float(age_sec)

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_PARTIAL_PENDING_CANCEL | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"open={open_count} pending={pending_count} age={age_sec:.1f}s "
                f"max={partial_max_age:.1f}s reason={reason}"
            )

            return True, positions

    # V24.1 — panier vide : rien d'ouvert, rien en attente.
'''
    s = replace_once(
        s,
        old_partial_anchor,
        new_partial_anchor,
        "panier partiel : annulation pending restants",
        already_marker="BASKET_PARTIAL_PENDING_CANCEL",
    )

    # ============================================================
    # 4) Protéger BASKET_EMPTY_RESET par confirmation broker.
    # ============================================================
    old_empty = '''    # V24.1 — panier vide : rien d'ouvert, rien en attente.
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
'''
    new_empty = '''    # V24.1 — panier vide localement.
    # Sécurité critique : avant de supprimer EXEC_STATE, on vérifie le broker.
    if open_count <= 0 and pending_count <= 0:
        broker_positions_left = v24_broker_positions_for_asset_from_list(
            positions=positions,
            asset=asset,
            direction=None,
        )

        broker_pending_left, broker_pending_status, broker_pending_raw = v24_broker_pending_orders_for_asset(
            headers=headers,
            asset=asset,
            direction=direction,
        )

        if broker_positions_left or broker_pending_left:
            reason = "V24_BASKET_EMPTY_RESET_BLOCKED_BROKER_NOT_EMPTY"

            cleanup_results = []
            if broker_pending_left:
                cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason="V24_ORPHAN_WORKING_ORDER_CLEANUP_BEFORE_RESET",
                )

            active_exec["empty_reset_blocked_reason"] = reason
            active_exec["empty_reset_blocked_utc"] = utc()
            active_exec["broker_positions_left_count"] = len(broker_positions_left)
            active_exec["broker_pending_left_count"] = len(broker_pending_left)
            active_exec["orphan_pending_cleanup_results"] = cleanup_results

            exec_state.setdefault("active", {})[asset] = active_exec
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_EMPTY_RESET_BLOCKED | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | "
                f"broker_positions={len(broker_positions_left)} "
                f"broker_pending={len(broker_pending_left)} "
                f"cleanup={len(cleanup_results)}"
            )

            return True, positions

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
            f"--         | {market_status:9s} | broker confirmé vide -> EXEC supprimé"
        )
        return True, positions
'''
    s = replace_once(
        s,
        old_empty,
        new_empty,
        "BASKET_EMPTY_RESET protégé broker",
        already_marker="BASKET_EMPTY_RESET_BLOCKED",
    )

    # ============================================================
    # 5) Renforcer BASKET_PENDING_CANCEL avec sweep broker réel.
    # ============================================================
    old_pending_cancel = '''            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            active_exec["cancel_results"] = cancel_results
'''
    new_pending_cancel = '''            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=reason,
            )

            # Filet de sécurité broker : même si le matching local rate
            # à cause d'un arrondi de taille, on annule aussi les vrais
            # working orders encore présents côté Capital.com.
            try:
                broker_cleanup_results = v24_cancel_broker_pending_for_asset(
                    headers=headers,
                    asset=asset,
                    direction=direction,
                    reason=reason + "_BROKER_SWEEP",
                )
            except Exception as e:
                broker_cleanup_results = [{"ok": False, "exception": str(e)}]

            active_exec["cancel_results"] = cancel_results
            active_exec["broker_cleanup_results"] = broker_cleanup_results
'''
    s = replace_once(
        s,
        old_pending_cancel,
        new_pending_cancel,
        "BASKET_PENDING_CANCEL avec broker sweep",
        already_marker="reason + \"_BROKER_SWEEP\"",
    )

    TARGET.write_text(s, encoding="utf-8")
    print("\nPATCH TERMINÉ : V24.1 SCALP ACTIVE SAFETY")
    print("- matching tolérant")
    print("- reset protégé broker")
    print("- cleanup ordres orphelins")
    print("- pending restants annulés après TP/TP_FAIL")
    print("- panier partiel nettoyé après délai")


if __name__ == "__main__":
    main()
