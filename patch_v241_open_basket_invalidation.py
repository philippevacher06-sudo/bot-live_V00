from pathlib import Path
from datetime import datetime, timezone
import shutil

p = Path("BOT_PIVOT_06G2_execution_secure.py")

ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
backup = Path("data") / f"backup_v241_open_basket_invalidation_{ts}"
backup.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup / p.name)

txt = p.read_text()

helpers = r'''

# ============================================================
# V24.1 — invalidation panier ouvert quand le signal est mort
# ============================================================

def v24_latest_signal_for_asset(asset):
    import json
    from pathlib import Path

    paths = []

    try:
        paths.append(Path(B.CFG.DATA_DIR) / "ticks" / "signals_latest.json")
    except Exception:
        pass

    paths.append(Path("data/ticks/signals_latest.json"))

    seen = set()

    for path in paths:
        try:
            path = Path(path)
            if str(path) in seen:
                continue
            seen.add(str(path))

            if not path.exists():
                continue

            data = json.loads(path.read_text())

            if isinstance(data, dict):
                signals = data.get("signals", [])
            elif isinstance(data, list):
                signals = data
            else:
                signals = []

            for sig in signals:
                if str(sig.get("asset", "")).upper() == str(asset).upper():
                    return sig

        except Exception:
            continue

    return {}


def v24_sig_float(sig, keys, default=None):
    for k in keys:
        try:
            if sig.get(k) is not None:
                return float(sig.get(k))
        except Exception:
            pass
    return default


def v24_sig_text(sig, keys, default=""):
    for k in keys:
        try:
            if sig.get(k) is not None:
                return str(sig.get(k))
        except Exception:
            pass
    return str(default)


def v24_open_signal_lost_grace_sec():
    # Temps minimum avant de fermer un panier ouvert simplement parce que
    # le signal est repassé WAIT / NO_SIGNAL.
    return max(30.0, v241_env_float("V24_OPEN_SIGNAL_LOST_GRACE_SEC", 120.0))


def v24_signal_lost_min_loss_eur():
    # Si signal perdu et perte au moins égale à ce seuil, on coupe.
    return max(0.0, v241_env_float("V24_SIGNAL_LOST_MIN_LOSS_EUR", 0.20))


def v24_opposite_signal_min_loss_eur():
    # Signal franchement opposé : on coupe plus vite.
    return max(0.0, v241_env_float("V24_OPPOSITE_SIGNAL_MIN_LOSS_EUR", 0.10))


def v24_breakout_min_loss_eur():
    # Phase/VWAP opposés ou breakout contre panier.
    return max(0.0, v241_env_float("V24_BREAKOUT_MIN_LOSS_EUR", 0.20))


def v24_signal_max_age_for_invalidation_sec():
    # On n'invalide pas une position sur un signal trop vieux.
    return max(5.0, v241_env_float("V24_INVALIDATION_MAX_SIGNAL_AGE_SEC", 20.0))


def v24_open_basket_invalidation_reason(asset, direction, active_exec, cycle, pnl_total, open_count):
    """
    Décide si un panier déjà ouvert doit être fermé parce que le signal initial
    est mort ou inversé.

    Cas couverts :
    - signal opposé
    - phase opposée + VWAP opposé
    - breakout contre la position
    - signal disparu trop longtemps avec perte
    """
    if open_count <= 0:
        return None

    direction = str(direction).upper()
    sig = v24_latest_signal_for_asset(asset)

    if not sig:
        return None

    decision = v24_sig_text(sig, ["decision", "signal"], "WAIT").upper()
    phase = v24_sig_text(sig, ["phase", "market_phase"], "").upper()
    vwap = v24_sig_text(sig, ["vwap_bias", "vwap", "vwap_direction"], "").upper()
    reason = v24_sig_text(sig, ["reason", "context", "summary"], "")
    signal_age = v24_sig_float(sig, ["age_sec", "tick_age_sec"], None)

    if signal_age is not None and signal_age > v24_signal_max_age_for_invalidation_sec():
        return None

    basket_age = v24_age_sec_from_iso(active_exec.get("created_utc"))

    range_pos = v24_sig_float(
        sig,
        ["range_position", "range_pos", "rpos", "R.Pos", "r_pos"],
        None,
    )

    opposite_decision = (
        (direction == "BUY" and decision == "SELL")
        or
        (direction == "SELL" and decision == "BUY")
    )

    phase_against = (
        (direction == "BUY" and phase == "TREND_DOWN")
        or
        (direction == "SELL" and phase == "TREND_UP")
    )

    vwap_against = (
        (direction == "BUY" and vwap == "SELL")
        or
        (direction == "SELL" and vwap == "BUY")
    )

    breakout_against = False

    if range_pos is not None:
        # SELL en haut puis breakout haussier : danger.
        if direction == "SELL" and range_pos >= 95 and phase == "TREND_UP":
            breakout_against = True

        # BUY en bas puis breakout baissier : danger.
        if direction == "BUY" and range_pos <= 5 and phase == "TREND_DOWN":
            breakout_against = True

    signal_lost = decision in ("WAIT", "IDLE", "NO_SIGNAL", "NONE", "")

    if opposite_decision and pnl_total <= -v24_opposite_signal_min_loss_eur():
        return (
            "V24_OPEN_BASKET_OPPOSITE_SIGNAL_CLOSE"
            f"|decision={decision}|phase={phase}|vwap={vwap}|pnl={pnl_total:.4f}"
        )

    if phase_against and vwap_against and pnl_total <= -v24_breakout_min_loss_eur():
        return (
            "V24_OPEN_BASKET_PHASE_VWAP_AGAINST_CLOSE"
            f"|decision={decision}|phase={phase}|vwap={vwap}|pnl={pnl_total:.4f}"
        )

    if breakout_against and pnl_total <= -v24_breakout_min_loss_eur():
        return (
            "V24_OPEN_BASKET_BREAKOUT_AGAINST_CLOSE"
            f"|range_pos={range_pos}|phase={phase}|pnl={pnl_total:.4f}"
        )

    if signal_lost and basket_age >= v24_open_signal_lost_grace_sec() and pnl_total <= -v24_signal_lost_min_loss_eur():
        return (
            "V24_OPEN_BASKET_SIGNAL_LOST_CLOSE"
            f"|decision={decision}|age={basket_age:.1f}s|phase={phase}|vwap={vwap}|reason={reason}|pnl={pnl_total:.4f}"
        )

    return None

'''

if "def v24_open_basket_invalidation_reason(" not in txt:
    marker = "def v24_process_basket("
    if marker not in txt:
        raise SystemExit("Impossible de trouver def v24_process_basket")
    txt = txt.replace(marker, helpers + "\n" + marker, 1)
else:
    print("INFO: helpers invalidation panier ouvert déjà présents")


marker = '''    # 4. TP panier global.
    tp_safety_margin = v24_tp_safety_margin_eur()
'''

insert = '''    # 4. Invalidation panier ouvert si le signal initial est mort.
    invalidation_reason = v24_open_basket_invalidation_reason(
        asset=asset,
        direction=direction,
        active_exec=active_exec,
        cycle=cycle,
        pnl_total=float(pnl_total),
        open_count=int(open_count),
    )

    if invalidation_reason:
        # On annule d'abord les LIMIT encore en attente, puis on ferme les jambes ouvertes.
        try:
            cancel_results = v24_cancel_all_pending_limits(
                headers=headers,
                asset=asset,
                levels=levels,
                reason=invalidation_reason,
            )
            active_exec["invalidation_cancel_results"] = cancel_results
        except Exception as e:
            active_exec["invalidation_cancel_error"] = str(e)

        ok, close_info, positions_after = v24_close_basket_secure(
            headers=headers,
            asset=asset,
            basket_exec=active_exec,
            reason=invalidation_reason,
        )

        active_exec["invalidation_reason"] = invalidation_reason
        active_exec["invalidation_utc"] = utc()
        active_exec["invalidation_pnl_eur"] = float(pnl_total)
        active_exec["invalidation_open_count"] = int(open_count)

        if ok:
            exec_state.setdefault("closed", []).append({
                **active_exec,
                "closed_reason": invalidation_reason,
                "closed_utc": utc(),
                "close_info": close_info,
            })
            exec_state.setdefault("active", {}).pop(asset, None)

            reset_cycle_idle(asset, invalidation_reason)
            B.save_json(B.EXEC_STATE_FILE, exec_state)

            print(
                f"{asset:10s} | BASKET_INVALIDATION_CLOSE_OK | 1-3 | {direction:4s} | "
                f"--         | {market_status:9s} | pnl={pnl_total:.4f} reason={invalidation_reason}"
            )

            try:
                event({
                    "event": "V24_OPEN_BASKET_INVALIDATION_CLOSE_OK",
                    "asset": asset,
                    "cycle_id": active_exec.get("cycle_id"),
                    "direction": direction,
                    "pnl_total": float(pnl_total),
                    "open_count": int(open_count),
                    "reason": invalidation_reason,
                    "close_info": close_info,
                })
            except Exception:
                pass

            return True, positions_after

        print(
            f"{asset:10s} | BASKET_INVALIDATION_CLOSE_FAIL | 1-3 | {direction:4s} | "
            f"--         | {market_status:9s} | pnl={pnl_total:.4f} reason={invalidation_reason}"
        )

        exec_state.setdefault("active", {})[asset] = active_exec
        B.save_json(B.EXEC_STATE_FILE, exec_state)
        return True, positions

    # 5. TP panier global.
    tp_safety_margin = v24_tp_safety_margin_eur()
'''

if marker not in txt:
    raise SystemExit("Impossible de trouver le marqueur TP panier global")

txt = txt.replace(marker, insert, 1)

p.write_text(txt)

print("Backup :", backup)
print("PATCH INVALIDATION PANIER OUVERT TERMINÉ")
