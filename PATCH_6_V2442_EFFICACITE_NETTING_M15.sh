#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

echo "============================================================"
echo "PATCH 6/5 - V24.4.2 EFFICACITE NETTING M15"
echo "============================================================"

TS=$(date +"%Y%m%d_%H%M%S")
RUNNER="BOT_PIVOT_24_4_forced_audit_runner.py"

cp -f "$RUNNER" "$RUNNER.before_v2442_efficiency_$TS"

python3 <<'PY'
from __future__ import annotations

import re
from pathlib import Path

path = Path("BOT_PIVOT_24_4_forced_audit_runner.py")
src = path.read_text(encoding="utf-8")


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Bloc introuvable:\n{old[:300]}")
    return text.replace(old, new, 1)


def replace_func(text: str, name: str, new_body: str) -> str:
    pattern = re.compile(
        rf"^def {re.escape(name)}\(.*?\n(?=^def |\n# ======================================================================|^if __name__ == \"__main__\":)",
        re.S | re.M,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"Fonction {name} introuvable ou ambigue: {len(matches)}")
    m = matches[0]
    return text[: m.start()] + new_body.rstrip() + "\n\n" + text[m.end() :]


config_old = """COUNT_PROTECTED_MARGIN = os.getenv("V244_COUNT_PROTECTED_MARGIN", "1") == "1"

ALLOW_DIRECT_LOSS_CLOSE = os.getenv("V244_ALLOW_DIRECT_LOSS_CLOSE", "0") == "1"
ALLOW_OPPOSITE_NETTING = os.getenv("V244_ALLOW_OPPOSITE_NETTING", "1") == "1"
"""

config_new = """COUNT_PROTECTED_MARGIN = os.getenv("V244_COUNT_PROTECTED_MARGIN", "1") == "1"

# Efficacite / garde-fous d'execution.
# Le signal reste M15, donc par defaut on n'autorise qu'une execution par bougie
# M15 confirmee. Cela evite de rejouer 20 a 30 fois le meme signal.
ONE_ORDER_PER_SIGNAL_BAR = os.getenv("V244_ONE_ORDER_PER_SIGNAL_BAR", "1") == "1"
REQUIRE_CLOSED_SIGNAL_BAR = os.getenv("V244_REQUIRE_CLOSED_SIGNAL_BAR", "1") == "1"
MAX_NET_EXPOSURE = float(os.getenv("V244_MAX_NET_EXPOSURE", "1.00"))

# Filtre de spread. 0 desactive la contrainte correspondante.
MAX_SPREAD_ABS = float(os.getenv("V244_MAX_SPREAD_ABS", "0"))
MAX_SPREAD_BPS = float(os.getenv("V244_MAX_SPREAD_BPS", "25"))

# La marge broker reste souveraine. Ici on ajoute un garde-fou sur le disponible.
ACCOUNT_AVAILABLE_BUFFER_RATIO = float(os.getenv("V244_ACCOUNT_AVAILABLE_BUFFER_RATIO", "0.90"))
ACCOUNT_CACHE_TTL_SEC = float(os.getenv("V244_ACCOUNT_CACHE_TTL_SEC", "10"))
REQUIRE_ACCOUNT_NETTING = os.getenv("V244_REQUIRE_ACCOUNT_NETTING", "1") == "1"

ALLOW_DIRECT_LOSS_CLOSE = os.getenv("V244_ALLOW_DIRECT_LOSS_CLOSE", "0") == "1"
ALLOW_OPPOSITE_NETTING = os.getenv("V244_ALLOW_OPPOSITE_NETTING", "1") == "1"
"""

if "ONE_ORDER_PER_SIGNAL_BAR" not in src:
    src = replace_once(src, config_old, config_new)


load_state_new = '''
def default_state() -> Dict[str, Any]:
    return {
        "active_bias": None,
        "sequence_count": 0,
        "last_signal_ts": None,
        "last_traded_bar_ts": None,
    }


def load_state() -> Dict[str, Any]:
    state = default_state()

    if STATE_FILE.exists():
        try:
            loaded = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception as e:
            log("RUNNER_STATE_LOAD_ERROR", asset=ASSET, state_file=str(STATE_FILE), exception=repr(e))

    try:
        state["sequence_count"] = int(state.get("sequence_count") or 0)
    except Exception:
        state["sequence_count"] = 0

    return state
'''

src = replace_func(src, "load_state", load_state_new)


helper_block = r'''

# ======================================================================
# ACCOUNT / EXECUTION GUARDS
# ======================================================================

_account_snapshot_cache: Dict[str, Any] = {
    "ts": 0.0,
    "session": None,
    "preferences": None,
}


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def get_account_session(headers: Dict[str, str], *, force: bool = False) -> Dict[str, Any]:
    now = time.time()
    cached = _account_snapshot_cache.get("session")
    if cached is not None and not force and now - float(_account_snapshot_cache.get("ts") or 0.0) <= ACCOUNT_CACHE_TTL_SEC:
        return cached

    status, data = api_get(headers, "/session")
    if status != 200 or not isinstance(data, dict):
        log("RUNNER_ACCOUNT_SESSION_ERROR", asset=ASSET, status=status, response=data)
        return {}

    _account_snapshot_cache["ts"] = now
    _account_snapshot_cache["session"] = data
    return data


def get_account_available(headers: Dict[str, str]) -> float:
    session = get_account_session(headers)
    info = session.get("accountInfo", {}) if isinstance(session.get("accountInfo"), dict) else {}
    available = safe_float(info.get("available"), -1.0)
    if available >= 0:
        return available

    status, data = api_get(headers, "/accounts")
    if status != 200 or not isinstance(data, dict):
        log("RUNNER_ACCOUNTS_ERROR", asset=ASSET, status=status, response=data)
        return 0.0

    for account in data.get("accounts", []) or []:
        if isinstance(account, dict) and account.get("preferred"):
            bal = account.get("balance", {}) if isinstance(account.get("balance"), dict) else {}
            return safe_float(bal.get("available"), 0.0)

    return 0.0


def get_account_preferences(headers: Dict[str, str], *, force: bool = False) -> Dict[str, Any]:
    cached = _account_snapshot_cache.get("preferences")
    if cached is not None and not force:
        return cached

    status, data = api_get(headers, "/accounts/preferences")
    if status != 200 or not isinstance(data, dict):
        log("RUNNER_ACCOUNT_PREFERENCES_ERROR", asset=ASSET, status=status, response=data)
        return {}

    _account_snapshot_cache["preferences"] = data
    return data


def assert_account_netting(headers: Dict[str, str]) -> None:
    prefs = get_account_preferences(headers, force=True)
    hedging = bool(prefs.get("hedgingMode"))

    log("RUNNER_ACCOUNT_MODE", asset=ASSET, hedgingMode=hedging, preferences=prefs)

    if hedging and REQUIRE_ACCOUNT_NETTING:
        lock_runner(
            "HEDGING_MODE_ENABLED",
            hedgingMode=hedging,
            preferences=prefs,
            rule="V2442_REQUIRES_NETTING_HEDGINGMODE_FALSE",
        )
        raise RuntimeError("Compte en hedgingMode=true alors que V24.4.2 exige le netting")


def current_crypto_leverage(headers: Dict[str, str], fallback: float = 2.0) -> float:
    prefs = get_account_preferences(headers)
    leverages = prefs.get("leverages", {}) if isinstance(prefs.get("leverages"), dict) else {}
    crypto = leverages.get("CRYPTOCURRENCIES", {}) if isinstance(leverages.get("CRYPTOCURRENCIES"), dict) else {}
    lev = safe_float(crypto.get("current"), fallback)
    return lev or fallback


def usable_signal_bars(bars: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if REQUIRE_CLOSED_SIGNAL_BAR and len(bars) > 1:
        return bars[:-1]
    return bars


def signal_bar_already_traded(state: Dict[str, Any], signal: Dict[str, Any]) -> bool:
    if not ONE_ORDER_PER_SIGNAL_BAR:
        return False
    bar_ts = signal.get("signal_bar_ts")
    return bool(bar_ts and state.get("last_traded_bar_ts") == bar_ts)


def mark_signal_bar_traded(state: Dict[str, Any], signal: Dict[str, Any]) -> Dict[str, Any]:
    bar_ts = signal.get("signal_bar_ts")
    if bar_ts:
        state["last_traded_bar_ts"] = bar_ts
    return state


def sync_state_with_broker_exposure(state: Dict[str, Any], net: float, net_side: str) -> Dict[str, Any]:
    if net_side == "FLAT" and (state.get("active_bias") is not None or int(state.get("sequence_count") or 0) != 0):
        log(
            "RUNNER_STATE_RESET_ON_FLAT_EXPOSURE",
            asset=ASSET,
            previous_state=state,
            net_exposure=net,
            net_side=net_side,
        )
        state["active_bias"] = None
        state["sequence_count"] = 0
        save_state(state)
    return state


def projected_net_after_order(net: float, side: str, size: float) -> float:
    if side == "BUY":
        return round(net + size, 10)
    if side == "SELL":
        return round(net - size, 10)
    return net


def net_exposure_allows_order(net: float, side: str, size: float) -> Tuple[bool, Dict[str, Any]]:
    projected = projected_net_after_order(net, side, size)
    ok = abs(projected) <= MAX_NET_EXPOSURE
    info = {
        "ok": ok,
        "net_before": net,
        "side": side,
        "size": size,
        "net_after_projected": projected,
        "max_net_exposure": MAX_NET_EXPOSURE,
    }
    log("RUNNER_NET_EXPOSURE_CHECK", asset=ASSET, **info)
    return ok, info


def spread_allows_order(headers: Dict[str, str]) -> Tuple[bool, Dict[str, Any]]:
    q = get_latest_mid(headers, ASSET)
    bid = safe_float(q.get("bid"))
    offer = safe_float(q.get("offer"))
    mid = safe_float(q.get("mid"))
    spread = max(0.0, offer - bid) if bid and offer else 0.0
    spread_bps = (spread / mid * 10000.0) if mid else 0.0

    abs_ok = True if MAX_SPREAD_ABS <= 0 else spread <= MAX_SPREAD_ABS
    bps_ok = True if MAX_SPREAD_BPS <= 0 else spread_bps <= MAX_SPREAD_BPS
    ok = bool(mid and abs_ok and bps_ok)

    info = {
        "ok": ok,
        "bid": bid,
        "offer": offer,
        "mid": mid,
        "spread": spread,
        "spread_bps": spread_bps,
        "max_spread_abs": MAX_SPREAD_ABS,
        "max_spread_bps": MAX_SPREAD_BPS,
    }
    log("RUNNER_SPREAD_CHECK", asset=ASSET, **info)
    return ok, info
'''

insert_marker = "\n# ======================================================================\n# POSITIONS / NETTING / MARGE"
if "def assert_account_netting" not in src:
    src = replace_once(src, insert_marker, helper_block + insert_marker)


margin_allows_order_new = '''
def margin_allows_order(headers: Dict[str, str], side: str, size: float) -> Tuple[bool, Dict[str, Any]]:
    positions = all_positions(headers)
    eth_positions = [p for p in positions if p.get("epic") == ASSET]
    net = net_exposure(eth_positions)
    net_side = net_side_from_exposure(net)

    current_margin = 0.0
    current_asset_margin = 0.0
    details = []

    for p in positions:
        epic = p.get("epic")
        if epic in PROTECTED_ASSETS and not COUNT_PROTECTED_MARGIN:
            continue
        m = estimate_position_margin(p)
        current_margin += m
        if epic == ASSET:
            current_asset_margin += m
        details.append({
            "epic": epic,
            "dealId": p.get("dealId"),
            "direction": p.get("direction"),
            "size": p.get("size"),
            "level": p.get("level"),
            "leverage": p.get("leverage"),
            "margin_est": m,
        })

    q = get_latest_mid(headers, ASSET)
    level = safe_float(q.get("mid") or q.get("offer") or q.get("bid"))
    leverage = current_crypto_leverage(headers, fallback=2.0)

    projected_net = projected_net_after_order(net, side, size)
    projected_asset_margin = abs(projected_net) * level / (leverage or 1.0)
    projected = max(0.0, current_margin - current_asset_margin + projected_asset_margin)

    available = get_account_available(headers)
    new_margin_delta = max(0.0, projected - current_margin)

    hard_limit = MAX_MARGIN_EST * MARGIN_BUFFER_RATIO
    fixed_limit_ok = projected <= hard_limit
    available_ok = new_margin_delta <= (available * ACCOUNT_AVAILABLE_BUFFER_RATIO)
    ok = fixed_limit_ok and available_ok

    info = {
        "ok": ok,
        "side": side,
        "size": size,
        "current_margin_est": current_margin,
        "current_asset_margin_est": current_asset_margin,
        "projected_asset_margin_est": projected_asset_margin,
        "projected_margin_est": projected,
        "new_margin_delta_est": new_margin_delta,
        "account_available": available,
        "account_available_buffer_ratio": ACCOUNT_AVAILABLE_BUFFER_RATIO,
        "fixed_limit_ok": fixed_limit_ok,
        "available_ok": available_ok,
        "max_margin_est": MAX_MARGIN_EST,
        "buffer_ratio": MARGIN_BUFFER_RATIO,
        "hard_limit": hard_limit,
        "level": level,
        "leverage": leverage,
        "net_exposure": net,
        "net_side": net_side,
        "projected_net_exposure": projected_net,
        "details": details,
    }

    log("RUNNER_MARGIN_CHECK", asset=ASSET, **info)
    return ok, info
'''

src = replace_func(src, "margin_allows_order", margin_allows_order_new)


compute_signal_new = '''
def compute_m15_vwap_signal(headers: Dict[str, str]) -> Dict[str, Any]:
    eth_bars = usable_signal_bars(get_price_bars(headers, ASSET))
    btc_bars = usable_signal_bars(get_price_bars(headers, CONFIRM_ASSET))

    eth_vwap = compute_vwap_series(eth_bars)
    btc_vwap = compute_vwap_series(btc_bars)

    eth_bias = vwap_bias(eth_vwap)
    btc_bias = vwap_bias(btc_vwap)

    if eth_bias in ("BUY", "SELL") and eth_bias == btc_bias:
        final_bias = eth_bias
        reason = "ETH_BTC_VWAP_ALIGNED"
    else:
        final_bias = "WAIT"
        reason = "ETH_BTC_NOT_ALIGNED"

    signal = {
        "asset": ASSET,
        "confirm_asset": CONFIRM_ASSET,
        "timeframe": SIGNAL_TIMEFRAME,
        "bias": final_bias,
        "reason": reason,
        "eth_bias": eth_bias,
        "btc_bias": btc_bias,
        "eth_vwap": eth_vwap,
        "btc_vwap": btc_vwap,
        "signal_bar_ts": eth_vwap.get("last_time") if isinstance(eth_vwap, dict) else None,
        "confirm_bar_ts": btc_vwap.get("last_time") if isinstance(btc_vwap, dict) else None,
        "closed_bar_required": REQUIRE_CLOSED_SIGNAL_BAR,
    }

    log("RUNNER_M15_VWAP_SIGNAL", **signal)
    return signal
'''

src = replace_func(src, "compute_m15_vwap_signal", compute_signal_new)


open_market_new = '''
def open_market_netting_safe(
    headers: Dict[str, str],
    side: str,
    size: float,
    signal: Dict[str, Any],
    state: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    if side not in ("BUY", "SELL"):
        return False, {"stage": "INVALID_SIDE", "side": side}

    if side == "SELL" and not ALLOW_OPPOSITE_NETTING:
        return False, {"stage": "OPPOSITE_NETTING_DISABLED"}

    spread_ok, spread_info = spread_allows_order(headers)
    if not spread_ok:
        return False, {
            "stage": "SPREAD_BLOCKED",
            "spread_info": spread_info,
        }

    margin_ok, margin_info = margin_allows_order(headers, side, size)
    if not margin_ok:
        return False, {
            "stage": "MARGIN_BLOCKED",
            "margin_info": margin_info,
        }

    positions_before = asset_positions(headers, ASSET)
    before_ids = position_ids(positions_before)

    client_ref = f"V2442_NETTING_{int(time.time())}_{side}_{uuid.uuid4().hex[:6]}"

    # Capital.com documente POST /positions comme un ordre au marche.
    # On evite les champs non documentes pour rester en netting.
    payload = {
        "epic": ASSET,
        "direction": side,
        "size": float(size),
        "guaranteedStop": GUARANTEED_STOP,
        "stopDistance": STOP_DISTANCE,
    }

    log(
        "RUNNER_NETTING_OPEN_REQUEST",
        asset=ASSET,
        side=side,
        size=size,
        client_ref=client_ref,
        payload=payload,
        signal=signal,
        state=state,
        spread_info=spread_info,
        margin_info=margin_info,
    )

    status, data = api_post(headers, "/positions", payload)

    log(
        "RUNNER_NETTING_OPEN_RESPONSE",
        asset=ASSET,
        side=side,
        size=size,
        status=status,
        response=data,
    )

    if status not in (200, 201) or not isinstance(data, dict) or not data.get("dealReference"):
        return False, {
            "stage": "POST_POSITION_FAILED",
            "status": status,
            "response": data,
            "payload": payload,
        }

    deal_ref = data["dealReference"]
    confirm_ok, confirm = confirm_reference(headers, deal_ref)

    if not confirm_ok:
        return False, {
            "stage": "CONFIRM_NOT_ACCEPTED",
            "dealReference": deal_ref,
            "confirm": confirm,
            "payload": payload,
        }

    resolved_ok, real_deal_id, visible_position, resolve_debug = resolve_real_deal_id(headers, confirm)

    positions_after = asset_positions(headers, ASSET)
    after_ids = position_ids(positions_after)
    net_after = net_exposure(positions_after)

    if not resolved_ok:
        log(
            "RUNNER_NETTING_NO_NEW_DEAL_VISIBLE_AFTER_ACCEPT",
            asset=ASSET,
            side=side,
            size=size,
            before_ids=sorted(before_ids),
            after_ids=sorted(after_ids),
            net_after=net_after,
            confirm=confirm,
            resolve_debug=resolve_debug,
            note="POSSIBLE_NETTING_REDUCTION",
        )

        return True, {
            "stage": "ORDER_ACCEPTED_POSSIBLE_NETTING_REDUCTION",
            "dealReference": deal_ref,
            "real_deal_id": None,
            "confirm": confirm,
            "positions_before": positions_before,
            "positions_after": positions_after,
            "net_after": net_after,
            "resolve_debug": resolve_debug,
            "payload": payload,
        }

    return True, {
        "stage": "OPEN_CONFIRMED_AND_VISIBLE",
        "dealReference": deal_ref,
        "real_deal_id": real_deal_id,
        "confirm": confirm,
        "position": visible_position,
        "positions_before": positions_before,
        "positions_after": positions_after,
        "net_after": net_after,
        "resolve_debug": resolve_debug,
        "payload": payload,
    }
'''

src = replace_func(src, "open_market_netting_safe", open_market_new)


main_new = '''
def main() -> None:
    FAS.safety_banner()

    if ASSET in PROTECTED_ASSETS:
        raise RuntimeError(f"{ASSET} est protege, impossible de le trader")

    refuse_if_lock_present()

    log(
        "RUNNER_V2442_NETTING_M15_START",
        asset=ASSET,
        confirm_asset=CONFIRM_ASSET,
        protected_assets=list(PROTECTED_ASSETS),
        mode="NETTING_NO_HEDGE",
        signal_timeframe=SIGNAL_TIMEFRAME,
        base_size=BASE_SIZE,
        size_step=SIZE_STEP,
        max_size=MAX_SIZE,
        target_openings_per_min=TARGET_OPENINGS_PER_MIN,
        max_open_positions=MAX_OPEN_POSITIONS,
        max_net_exposure=MAX_NET_EXPOSURE,
        max_margin_est=MAX_MARGIN_EST,
        margin_buffer_ratio=MARGIN_BUFFER_RATIO,
        account_available_buffer_ratio=ACCOUNT_AVAILABLE_BUFFER_RATIO,
        one_order_per_signal_bar=ONE_ORDER_PER_SIGNAL_BAR,
        require_closed_signal_bar=REQUIRE_CLOSED_SIGNAL_BAR,
        max_spread_abs=MAX_SPREAD_ABS,
        max_spread_bps=MAX_SPREAD_BPS,
        guaranteed_stop=GUARANTEED_STOP,
        stop_distance=STOP_DISTANCE,
        allow_direct_loss_close=ALLOW_DIRECT_LOSS_CLOSE,
        allow_opposite_netting=ALLOW_OPPOSITE_NETTING,
    )

    headers = ensure_headers(G.login())
    log("RUNNER_LOGIN_OK", asset=ASSET)
    assert_account_netting(headers)

    state = load_state()
    save_state(state)

    while True:
        try:
            if is_locked():
                log("RUNNER_HALTED_BY_LOCK", asset=ASSET, lock_file=str(LOCK_FILE))
                time.sleep(60)
                continue

            positions = asset_positions(headers, ASSET)
            net = net_exposure(positions)
            net_side = net_side_from_exposure(net)
            state = sync_state_with_broker_exposure(state, net, net_side)

            signal = compute_m15_vwap_signal(headers)
            bias = signal.get("bias")

            rate_ok, rate_info = can_open_now()

            log(
                "RUNNER_STATUS",
                asset=ASSET,
                confirm_asset=CONFIRM_ASSET,
                signal_bias=bias,
                signal_reason=signal.get("reason"),
                signal_bar_ts=signal.get("signal_bar_ts"),
                eth_bias=signal.get("eth_bias"),
                btc_bias=signal.get("btc_bias"),
                open_positions=len(positions),
                open_dealIds=[p.get("dealId") for p in positions],
                net_exposure=net,
                net_side=net_side,
                opens_last_60s=opens_last_60s(),
                rate_ok=rate_ok,
                rate_info=rate_info,
                state=state,
            )

            if bias not in ("BUY", "SELL"):
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="NO_M15_VWAP_BTC_SIGNAL",
                    signal=signal,
                )
                time.sleep(SLEEP_SEC)
                continue

            if signal_bar_already_traded(state, signal):
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="SIGNAL_BAR_ALREADY_TRADED",
                    signal_bar_ts=signal.get("signal_bar_ts"),
                    state=state,
                )
                time.sleep(SLEEP_SEC)
                continue

            state = update_sequence_for_signal(state, bias)
            save_state(state)

            side = bias
            size = next_ladder_size(state)

            same_side_as_net = net_side == side
            opposite_to_net = net_side in ("BUY", "SELL") and side == opposite_side(net_side)

            net_ok, net_info = net_exposure_allows_order(net, side, size)
            if not net_ok:
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="MAX_NET_EXPOSURE_REACHED",
                    net_info=net_info,
                )
                time.sleep(SLEEP_SEC)
                continue

            if len(positions) >= MAX_OPEN_POSITIONS and same_side_as_net:
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="MAX_OPEN_POSITIONS_REACHED_SAME_SIDE",
                    open_positions=len(positions),
                    max_open_positions=MAX_OPEN_POSITIONS,
                    side=side,
                    net_side=net_side,
                    net_exposure=net,
                )
                time.sleep(SLEEP_SEC)
                continue

            if opposite_to_net:
                log(
                    "RUNNER_OPPOSITE_NETTING_SEQUENCE",
                    asset=ASSET,
                    previous_net_side=net_side,
                    new_signal_side=side,
                    rule="NO_DELETE_SEND_OPPOSITE_ORDER_FROM_0_05_SEQUENCE",
                    next_size=size,
                )

            if not rate_ok:
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason=rate_info.get("reason"),
                    rate_info=rate_info,
                )
                time.sleep(SLEEP_SEC)
                continue

            ok, info = open_market_netting_safe(
                headers=headers,
                side=side,
                size=size,
                signal=signal,
                state=state,
            )

            log(
                "RUNNER_OPEN_RESULT",
                asset=ASSET,
                side=side,
                size=size,
                ok=ok,
                info=info,
            )

            if ok:
                register_open_window()
                state = mark_signal_bar_traded(state, signal)
                state = advance_ladder(state)

                try:
                    FAS.register_open(
                        asset=ASSET,
                        side=side,
                        size=size,
                        reason="V2442_M15_VWAP_BTC_NETTING_ORDER",
                        extra=info,
                    )
                except Exception as e:
                    log(
                        "RUNNER_FAS_REGISTER_OPEN_EXCEPTION",
                        asset=ASSET,
                        exception=repr(e),
                        info=info,
                    )

            time.sleep(SLEEP_SEC)

        except Exception as e:
            msg = str(e)
            log(
                "RUNNER_EXCEPTION",
                asset=ASSET,
                exception=msg,
                traceback=traceback.format_exc().replace("\\n", " / "),
            )

            if "429" in msg or "too-many" in msg.lower() or "session" in msg.lower():
                time.sleep(120)
                headers = ensure_headers(G.login())
                log("RUNNER_RELOGIN_OK", asset=ASSET)
                assert_account_netting(headers)
            else:
                time.sleep(20)
'''

src = replace_func(src, "main", main_new)

path.write_text(src, encoding="utf-8")
PY

echo "============================================================"
echo "COMPILATION"
echo "============================================================"
python3 -m py_compile "$RUNNER"

echo "============================================================"
echo "CONTROLES PATCH 6"
echo "============================================================"
if grep -nE '"forceOpen"|"orderType"' "$RUNNER"; then
  echo "ERREUR: champs d'ordre non documentes encore presents dans le payload"
  exit 1
fi

grep -nE "ONE_ORDER_PER_SIGNAL_BAR|REQUIRE_CLOSED_SIGNAL_BAR|MAX_NET_EXPOSURE|MAX_SPREAD_BPS|RUNNER_ACCOUNT_MODE|SIGNAL_BAR_ALREADY_TRADED|RUNNER_SPREAD_CHECK|RUNNER_NET_EXPOSURE_CHECK" "$RUNNER" | head -260 || true

echo "PATCH 6/5 OK"
