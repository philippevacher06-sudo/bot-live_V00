# BOT_PIVOT_24_4_forced_audit_runner.py
# V24.4.2 — NETTING M15 VWAP ETH/BTC
#
# Règles stratégiques :
# - ETHUSD exécuté.
# - BTCUSD confirmation obligatoire.
# - Signal M15 uniquement.
# - VWAP ETH + VWAP BTC.
# - Compte Capital.com en netting, pas en hedging.
# - Changement BUY -> SELL : pas de DELETE, on envoie des ordres SELL progressifs.
# - Changement SELL -> BUY : pas de DELETE, on envoie des ordres BUY progressifs.
# - Jamais de fermeture directe volontaire d'une position perdante.
# - Taille départ 0.05, palier +0.05.
# - Marge = contrainte absolue.
# - GOLD protégé, jamais fermé.

from __future__ import annotations

import os
import time
import json
import uuid
import math
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

import BOT_PIVOT_06G2_execution_secure as G
import BOT_PIVOT_24_4_forced_audit_sampling as FAS


# ======================================================================
# CONFIG
# ======================================================================

ASSET = os.getenv("V244_TRADED_ASSET", os.getenv("ASSET", "ETHUSD")).upper()
CONFIRM_ASSET = os.getenv("V244_CONFIRM_ASSET", os.getenv("CONFIRM", "BTCUSD")).upper()
PROTECTED_ASSETS = {"GOLD"}

BASE = os.getenv(
    "CAPITAL_BASE_URL",
    "https://demo-api-capital.backend-capital.com/api/v1"
).rstrip("/")

SLEEP_SEC = float(os.getenv("V244_RUNNER_SLEEP_SEC", "10"))

SIGNAL_TIMEFRAME = os.getenv("V244_SIGNAL_TIMEFRAME", "MINUTE_15")
SIGNAL_BARS = int(os.getenv("V244_SIGNAL_BARS", "96"))
VWAP_SLOPE_LOOKBACK = int(os.getenv("V244_VWAP_SLOPE_LOOKBACK", "4"))
VWAP_FLAT_TOLERANCE = float(os.getenv("V244_VWAP_FLAT_TOLERANCE", "0.0"))

BASE_SIZE = float(os.getenv("V244_BASE_SIZE", "0.05"))
SIZE_STEP = float(os.getenv("V244_SIZE_STEP", "0.05"))
MAX_SIZE = float(os.getenv("V244_MAX_SIZE", "1.00"))

TARGET_OPENINGS_PER_MIN = int(os.getenv("V244_TARGET_OPENINGS_PER_MIN", "2"))
MAX_OPEN_POSITIONS = int(os.getenv("V244_MAX_OPEN_POSITIONS", "200"))

STOP_DISTANCE = float(os.getenv("V244_STOP_DISTANCE", "25"))
GUARANTEED_STOP = os.getenv("V244_GUARANTEED_STOP", "1") == "1"
CONFIRM_POLL_SEC = float(os.getenv("V244_CONFIRM_POLL_SEC", "1"))

POSITION_BACKOFFS = [
    float(x.strip())
    for x in os.getenv("V244_POSITION_BACKOFFS", "1,1.5,2,3,5,8").split(",")
    if x.strip()
]

MAX_MARGIN_EST = float(os.getenv("V244_MAX_MARGIN_EST", "3000"))
MARGIN_BUFFER_RATIO = float(os.getenv("V244_MARGIN_BUFFER_RATIO", "0.95"))
COUNT_PROTECTED_MARGIN = os.getenv("V244_COUNT_PROTECTED_MARGIN", "1") == "1"

# Efficacite / garde-fous d'execution.
# Le signal reste M15, donc par defaut on n'autorise qu'une execution par bougie
# M15 confirmee. Cela evite de rejouer 20 a 30 fois le meme signal.
ONE_ORDER_PER_SIGNAL_BAR = os.getenv("V244_ONE_ORDER_PER_SIGNAL_BAR", "1") == "1"
REQUIRE_CLOSED_SIGNAL_BAR = os.getenv("V244_REQUIRE_CLOSED_SIGNAL_BAR", "1") == "1"
MAX_NET_EXPOSURE = float(os.getenv("V244_MAX_NET_EXPOSURE", "0"))

# Filtre de spread. 0 desactive la contrainte correspondante.
MAX_SPREAD_ABS = float(os.getenv("V244_MAX_SPREAD_ABS", "0"))
MAX_SPREAD_BPS = float(os.getenv("V244_MAX_SPREAD_BPS", "25"))

# La marge broker reste souveraine. Ici on ajoute un garde-fou sur le disponible.
ACCOUNT_AVAILABLE_BUFFER_RATIO = float(os.getenv("V244_ACCOUNT_AVAILABLE_BUFFER_RATIO", "0.90"))
ACCOUNT_CACHE_TTL_SEC = float(os.getenv("V244_ACCOUNT_CACHE_TTL_SEC", "10"))
REQUIRE_ACCOUNT_NETTING = os.getenv("V244_REQUIRE_ACCOUNT_NETTING", "1") == "1"

MARGIN_DRIVEN_MODE = os.getenv("V244_MARGIN_DRIVEN_MODE", "1") == "1"


# V24.4.3 - fermeture defensive des gagnantes ETH uniquement.
# Desactive par defaut tant que l'export explicite n'est pas present.
CLOSE_WINNERS_ENABLED = os.getenv("V244_CLOSE_WINNERS_ENABLED", "0") == "1"
WIN_BASKET_TP_EUR = float(os.getenv("V244_WIN_BASKET_TP_EUR", "1.00"))
WIN_MIN_POSITION_UPL = float(os.getenv("V244_WIN_MIN_POSITION_UPL", "0.05"))
WIN_BASKET_MARGIN_PCT = float(os.getenv("V244_WIN_BASKET_MARGIN_PCT", "0.15"))
WIN_MIN_AGE_SEC = float(os.getenv("V244_WIN_MIN_AGE_SEC", "60"))
WIN_CLOSE_ON_WAIT = os.getenv("V244_WIN_CLOSE_ON_WAIT", "1") == "1"
WIN_CLOSE_ON_SIGNAL_REVERSAL = os.getenv("V244_WIN_CLOSE_ON_SIGNAL_REVERSAL", "1") == "1"
WIN_MAX_CLOSES_PER_LOOP = int(os.getenv("V244_WIN_MAX_CLOSES_PER_LOOP", "5"))
CLOSE_THEN_WAIT_SEC = float(os.getenv("V244_CLOSE_THEN_WAIT_SEC", "5"))

ALLOW_DIRECT_LOSS_CLOSE = os.getenv("V244_ALLOW_DIRECT_LOSS_CLOSE", "0") == "1"
ALLOW_OPPOSITE_NETTING = os.getenv("V244_ALLOW_OPPOSITE_NETTING", "1") == "1"

NO_LOSS_CLOSE_HARD_GUARD = os.getenv("V244_NO_LOSS_CLOSE_HARD_GUARD", "1") == "1"
DISABLE_CLOSE_BY_AGE = os.getenv("V244_DISABLE_CLOSE_BY_AGE", "1") == "1"

LOCK_FILE = Path(os.getenv("V244_LOCK_FILE", "data/execution/V244_FORCED_RUNNER_LOCK"))
STATE_FILE = Path(os.getenv("V244_STATE_FILE", "data/execution/V2442_NETTING_STATE.json"))

_open_ts_window: List[float] = []


# ======================================================================
# LOG / LOCK / STATE
# ======================================================================

def log(event: str, **kw: Any) -> None:
    try:
        FAS.audit_log(event, **kw)
    except Exception:
        print(event, kw)



# === V244_PROTECTED_DEAL_IDS_START ===
def _v244_protected_deal_ids():
    raw = os.getenv("V244_PROTECTED_DEAL_IDS", "")
    return set(x.strip() for x in raw.replace(";", ",").split(",") if x.strip())

def _v244_deal_id_from_position(pos):
    if not isinstance(pos, dict):
        return None
    for k in ("dealId", "deal_id", "id"):
        v = pos.get(k)
        if v:
            return str(v)
    for k in ("position", "deal", "confirm", "info"):
        child = pos.get(k)
        if isinstance(child, dict):
            v = _v244_deal_id_from_position(child)
            if v:
                return v
    return None

def _v244_is_protected_deal_id(deal_id):
    return bool(deal_id) and str(deal_id) in _v244_protected_deal_ids()
# === V244_PROTECTED_DEAL_IDS_END ===

def ensure_headers(headers: Dict[str, str]) -> Dict[str, str]:
    h = dict(headers or {})
    h.setdefault("Content-Type", "application/json")
    h.setdefault("Accept", "application/json")
    return h



def default_state() -> Dict[str, Any]:
    return {
        "active_bias": None,
        "sequence_count": 0,
        "last_signal_ts": None,
        "last_traded_bar_ts": None,
    }



def default_state() -> Dict[str, Any]:
    return {
        "active_bias": None,
        "sequence_count": 0,
        "last_signal_ts": None,
        "last_traded_bar_ts": None,
    }



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

def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def lock_runner(reason: str, **kw: Any) -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w", encoding="utf-8") as f:
        f.write(f"reason={reason}\n")
        f.write(f"ts_utc={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        for k, v in kw.items():
            try:
                f.write(f"{k}={json.dumps(v, ensure_ascii=False)}\n")
            except Exception:
                f.write(f"{k}={repr(v)}\n")
    log("RUNNER_LOCKED", asset=ASSET, reason=reason, **kw)


def is_locked() -> bool:
    return LOCK_FILE.exists()


def refuse_if_lock_present() -> None:
    if is_locked():
        log("RUNNER_LOCK_PRESENT_AT_START", asset=ASSET, lock_file=str(LOCK_FILE))
        raise RuntimeError(f"LOCK actif : {LOCK_FILE}")


# ======================================================================
# API CAPITAL.COM DEMO
# ======================================================================

def _demo_guard(url: str) -> Optional[Dict[str, Any]]:
    if "demo-api-capital" not in url:
        return {
            "BLOCKED": True,
            "reason": "DEMO_ONLY_URL_REQUIRED",
            "url": url,
        }
    return None


def api_get(headers: Dict[str, str], path: str) -> Tuple[int, Any]:
    url = BASE + path
    blocked = _demo_guard(url)
    if blocked:
        return 0, blocked

    try:
        r = requests.get(url, headers=ensure_headers(headers), timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
        return int(r.status_code), data
    except Exception as e:
        return 0, {
            "REQUEST_EXCEPTION": True,
            "method": "GET",
            "path": path,
            "exception": repr(e),
        }


def api_post(headers: Dict[str, str], path: str, payload: Dict[str, Any]) -> Tuple[int, Any]:
    url = BASE + path
    blocked = _demo_guard(url)
    if blocked:
        return 0, blocked

    try:
        r = requests.post(url, headers=ensure_headers(headers), json=payload, timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
        return int(r.status_code), data
    except Exception as e:
        return 0, {
            "REQUEST_EXCEPTION": True,
            "method": "POST",
            "path": path,
            "payload": payload,
            "exception": repr(e),
        }




def api_delete(headers: Dict[str, str], path: str) -> Tuple[int, Any]:
    url = BASE + path
    blocked = _demo_guard(url)
    if blocked:
        return 0, blocked

    if NO_LOSS_CLOSE_HARD_GUARD and path.startswith("/positions/"):
        deal_id = path.rsplit("/", 1)[-1]
        if _v244_is_protected_deal_id(deal_id):
            log("RUNNER_DELETE_BLOCKED_PROTECTED_DEAL_ID", asset=ASSET, dealId=deal_id)
            return 0, {"BLOCKED": True, "reason": "PROTECTED_DEAL_ID", "dealId": deal_id}
        visible = None

        for pos in all_positions(headers):
            if str(pos.get("dealId")) == str(deal_id):
                visible = pos
                break

        if visible is None:
            log("RUNNER_DELETE_BLOCKED_NOT_VISIBLE", asset=ASSET, dealId=deal_id)
            return 0, {"BLOCKED": True, "reason": "POSITION_NOT_VISIBLE", "dealId": deal_id}

        epic = str(visible.get("epic") or "").upper()
        upl = float(visible.get("upl") or 0.0)

        if epic in PROTECTED_ASSETS:
            log("RUNNER_DELETE_BLOCKED_PROTECTED_ASSET", asset=ASSET, epic=epic, dealId=deal_id, upl=upl)
            return 0, {"BLOCKED": True, "reason": "PROTECTED_ASSET", "epic": epic, "dealId": deal_id, "upl": upl}

        if upl <= 0 and not ALLOW_DIRECT_LOSS_CLOSE:
            log("RUNNER_DELETE_BLOCKED_LOSS_OR_FLAT", asset=ASSET, epic=epic, dealId=deal_id, upl=upl)
            return 0, {"BLOCKED": True, "reason": "LOSS_OR_FLAT_DELETE_FORBIDDEN", "epic": epic, "dealId": deal_id, "upl": upl}

    try:
        r = requests.delete(url, headers=ensure_headers(headers), timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
        return int(r.status_code), data
    except Exception as e:
        return 0, {"REQUEST_EXCEPTION": True, "method": "DELETE", "path": path, "exception": repr(e)}


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

    if MARGIN_DRIVEN_MODE and MAX_NET_EXPOSURE <= 0:
        info = {
            "ok": True,
            "mode": "MARGIN_DRIVEN_NET_CAP_DISABLED",
            "net_before": net,
            "side": side,
            "size": size,
            "net_after_projected": projected,
            "rule": "2_OPENINGS_PER_MIN_UNTIL_MARGIN_BLOCKED",
        }
        log("RUNNER_NET_EXPOSURE_CHECK", asset=ASSET, **info)
        return True, info

    ok = abs(projected) <= MAX_NET_EXPOSURE
    info = {
        "ok": ok,
        "mode": "EXPLICIT_NET_CAP",
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

# ======================================================================
# POSITIONS / NETTING / MARGE
# ======================================================================

def get_positions_raw(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    status, data = api_get(headers, "/positions")
    if status != 200:
        log("RUNNER_GET_POSITIONS_ERROR", asset=ASSET, status=status, response=data)
        raise RuntimeError(f"GET /positions failed status={status} data={data}")

    positions = data.get("positions", []) if isinstance(data, dict) else []
    log("RUNNER_GET_POSITIONS_OK", asset=ASSET, total_positions=len(positions), raw=data)
    return positions


def position_epic(item: Dict[str, Any]) -> str:
    market = item.get("market", {}) if isinstance(item.get("market"), dict) else {}
    position = item.get("position", {}) if isinstance(item.get("position"), dict) else {}
    return str(market.get("epic") or position.get("epic") or item.get("epic") or "").upper()


def normalize_position(item: Dict[str, Any]) -> Dict[str, Any]:
    market = item.get("market", {}) if isinstance(item.get("market"), dict) else {}
    pos = item.get("position", {}) if isinstance(item.get("position"), dict) else {}

    def fnum(v: Any, default: float = 0.0) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    return {
        "epic": str(market.get("epic") or pos.get("epic") or item.get("epic") or "").upper(),
        "dealId": pos.get("dealId") or item.get("dealId"),
        "dealReference": pos.get("dealReference") or item.get("dealReference"),
        "workingOrderId": pos.get("workingOrderId") or item.get("workingOrderId"),
        "size": fnum(pos.get("size") or item.get("size")),
        "direction": str(pos.get("direction") or item.get("direction") or "").upper(),
        "level": fnum(pos.get("level") or item.get("level")),
        "upl": fnum(pos.get("upl") or item.get("upl")),
        "leverage": fnum(pos.get("leverage") or item.get("leverage"), 1.0),
        "guaranteedStop": bool(pos.get("guaranteedStop") or item.get("guaranteedStop")),
        "createdDateUTC": pos.get("createdDateUTC") or item.get("createdDateUTC"),
        "createdDate": pos.get("createdDate") or item.get("createdDate"),
        "raw": item,
    }


def all_positions(headers: Dict[str, str]) -> List[Dict[str, Any]]:
    return [normalize_position(x) for x in get_positions_raw(headers)]


def asset_positions(headers: Dict[str, str], asset: str = ASSET) -> List[Dict[str, Any]]:
    a = str(asset or ASSET).upper()
    out = []
    for p in all_positions(headers):
        if str(p.get("epic") or "").upper() != a:
            continue
        did = _v244_deal_id_from_position(p)
        if _v244_is_protected_deal_id(did):
            log("RUNNER_POSITION_IGNORED_PROTECTED_DEAL", asset=ASSET, epic=a, dealId=did)
            continue
        out.append(p)
    return out


def position_ids(positions: List[Dict[str, Any]]) -> set:
    return {str(p.get("dealId")) for p in positions if p.get("dealId")}


def net_exposure(positions: List[Dict[str, Any]]) -> float:
    net = 0.0
    for p in positions:
        size = float(p.get("size") or 0.0)
        direction = str(p.get("direction") or "").upper()
        if direction == "BUY":
            net += size
        elif direction == "SELL":
            net -= size
    return round(net, 10)


def net_side_from_exposure(net: float) -> str:
    if net > 0:
        return "BUY"
    if net < 0:
        return "SELL"
    return "FLAT"


def opposite_side(side: str) -> str:
    return "SELL" if side == "BUY" else "BUY"


def estimate_position_margin(p: Dict[str, Any]) -> float:
    size = abs(float(p.get("size") or 0.0))
    level = abs(float(p.get("level") or 0.0))
    leverage = abs(float(p.get("leverage") or 1.0)) or 1.0
    return (size * level) / leverage


def estimate_used_margin(headers: Dict[str, str]) -> Tuple[float, List[Dict[str, Any]]]:
    positions = all_positions(headers)
    details = []
    total = 0.0

    for p in positions:
        epic = p.get("epic")
        if epic in PROTECTED_ASSETS and not COUNT_PROTECTED_MARGIN:
            continue

        m = estimate_position_margin(p)
        total += m
        details.append({
            "epic": epic,
            "dealId": p.get("dealId"),
            "direction": p.get("direction"),
            "size": p.get("size"),
            "level": p.get("level"),
            "leverage": p.get("leverage"),
            "margin_est": m,
        })

    return total, details


def estimate_new_order_margin(headers: Dict[str, str], side: str, size: float) -> float:
    prices = get_latest_mid(headers, ASSET)
    level = prices.get("mid") or prices.get("offer") or prices.get("bid") or 0.0
    leverage = 2.0
    return abs(float(size) * float(level)) / leverage





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


# ======================================================================
# PRIX / VWAP / SIGNAL M15
# ======================================================================

def _mid_from_price_obj(obj: Dict[str, Any]) -> Optional[float]:
    if not isinstance(obj, dict):
        return None

    bid = obj.get("bid")
    ask = obj.get("ask") or obj.get("offer")

    try:
        if bid is not None and ask is not None:
            return (float(bid) + float(ask)) / 2.0
        if bid is not None:
            return float(bid)
        if ask is not None:
            return float(ask)
    except Exception:
        return None

    return None


def get_latest_mid(headers: Dict[str, str], epic: str) -> Dict[str, float]:
    status, data = api_get(headers, f"/markets/{epic}")
    if status != 200 or not isinstance(data, dict):
        return {"bid": 0.0, "offer": 0.0, "mid": 0.0}

    snap = data.get("snapshot", {}) if isinstance(data.get("snapshot"), dict) else {}
    bid = snap.get("bid")
    offer = snap.get("offer") or snap.get("ask")

    try:
        bid_f = float(bid or 0.0)
        offer_f = float(offer or 0.0)
        mid = (bid_f + offer_f) / 2.0 if bid_f and offer_f else bid_f or offer_f
    except Exception:
        bid_f = offer_f = mid = 0.0

    return {"bid": bid_f, "offer": offer_f, "mid": mid}


def get_price_bars(headers: Dict[str, str], epic: str) -> List[Dict[str, Any]]:
    # Court-circuit V2447 Hyper-Vitesse via RAM Flash WebSocket
    import os, json
    asset_env = os.getenv("ASSET", "")
    # Si l'epic demandé correspond à notre actif en cours, on tente de lire le flash
    if asset_env and asset_env in epic:
        ram_file = f"data/ticks/live_price_{asset_env}.json"
        if os.path.exists(ram_file):
            try:
                with open(ram_file, "r") as rf:
                    data = json.load(rf)
                # On simule une structure de "bar" minimale pour que le reste du bot ne crashe pas
                return [{"snapshotTime": "", "openPrice": {"bid": data["bid"], "ask": data["ask"]}, "closePrice": {"bid": data["bid"], "ask": data["ask"]}, "highPrice": {"bid": data["bid"], "ask": data["ask"]}, "lowPrice": {"bid": data["bid"], "ask": data["ask"]}}]
            except Exception:
                pass

    path = f"/prices/{epic}?resolution={SIGNAL_TIMEFRAME}&max={SIGNAL_BARS}"
    status, data = api_get(headers, path)

    if status != 200 or not isinstance(data, dict):
        log("RUNNER_PRICE_BARS_ERROR", epic=epic, status=status, response=data)
        return []

    prices = data.get("prices") or []
    if not isinstance(prices, list):
        prices = []

    log("RUNNER_PRICE_BARS_OK", epic=epic, count=len(prices), timeframe=SIGNAL_TIMEFRAME)
    return prices


def extract_bar_price_and_volume(bar: Dict[str, Any]) -> Optional[Tuple[float, float, str]]:
    if not isinstance(bar, dict):
        return None

    close_obj = (
        bar.get("closePrice")
        or bar.get("close")
        or bar.get("lastPrice")
        or {}
    )

    price = _mid_from_price_obj(close_obj)

    if price is None:
        for key in ("close", "last", "price"):
            try:
                if bar.get(key) is not None:
                    price = float(bar.get(key))
                    break
            except Exception:
                pass

    if price is None:
        return None

    vol = (
        bar.get("lastTradedVolume")
        or bar.get("volume")
        or bar.get("tickVolume")
        or 1.0
    )

    try:
        vol_f = float(vol)
        if vol_f <= 0:
            vol_f = 1.0
    except Exception:
        vol_f = 1.0

    ts = str(
        bar.get("snapshotTimeUTC")
        or bar.get("snapshotTime")
        or bar.get("time")
        or ""
    )

    return float(price), vol_f, ts


def compute_vwap_series(bars: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = []
    volumes = []
    times = []

    for bar in bars:
        extracted = extract_bar_price_and_volume(bar)
        if not extracted:
            continue
        p, v, ts = extracted
        prices.append(p)
        volumes.append(v)
        times.append(ts)

    if len(prices) < max(10, VWAP_SLOPE_LOOKBACK + 2):
        return {
            "ok": False,
            "reason": "NOT_ENOUGH_BARS",
            "count": len(prices),
        }

    cum_pv = 0.0
    cum_v = 0.0
    vwaps = []

    for p, v in zip(prices, volumes):
        cum_pv += p * v
        cum_v += v
        vwaps.append(cum_pv / cum_v if cum_v else p)

    last_price = prices[-1]
    last_vwap = vwaps[-1]
    prev_vwap = vwaps[-1 - VWAP_SLOPE_LOOKBACK]
    slope = last_vwap - prev_vwap

    return {
        "ok": True,
        "count": len(prices),
        "last_price": last_price,
        "last_vwap": last_vwap,
        "prev_vwap": prev_vwap,
        "slope": slope,
        "last_time": times[-1] if times else None,
    }


def vwap_bias(v: Dict[str, Any]) -> str:
    if not v.get("ok"):
        return "WAIT"

    price = float(v.get("last_price"))
    vwap = float(v.get("last_vwap"))
    slope = float(v.get("slope"))

    if price > vwap and slope >= -VWAP_FLAT_TOLERANCE:
        return "BUY"

    if price < vwap and slope <= VWAP_FLAT_TOLERANCE:
        return "SELL"

    return "WAIT"





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


# ======================================================================
# CONFIRM / DEAL ID RESOLUTION
# ======================================================================

def extract_deal_candidates(confirm: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = []

    main = confirm.get("dealId")
    if main:
        candidates.append({
            "source": "confirm.dealId",
            "dealId": str(main),
            "status": confirm.get("status"),
        })

    affected = confirm.get("affectedDeals") or []
    if isinstance(affected, list):
        for i, item in enumerate(affected):
            if isinstance(item, dict) and item.get("dealId"):
                candidates.append({
                    "source": f"affectedDeals[{i}].dealId",
                    "dealId": str(item.get("dealId")),
                    "status": item.get("status"),
                })

    seen = set()
    unique = []
    for c in candidates:
        did = c.get("dealId")
        if did and did not in seen:
            unique.append(c)
            seen.add(did)

    return unique


def confirm_reference(headers: Dict[str, str], deal_ref: str) -> Tuple[bool, Dict[str, Any]]:
    time.sleep(CONFIRM_POLL_SEC)

    status, data = api_get(headers, f"/confirms/{deal_ref}")

    epic = data.get("epic") if isinstance(data, dict) else None
    epic_ok = (not epic) or str(epic).upper() == ASSET

    ok = (
        status == 200
        and isinstance(data, dict)
        and data.get("dealStatus") == "ACCEPTED"
        and epic_ok
        and bool(data.get("dealId") or data.get("affectedDeals"))
    )

    log(
        "RUNNER_CONFIRM_RESULT",
        asset=ASSET,
        dealReference=deal_ref,
        status=status,
        ok=ok,
        epic_present=bool(epic),
        epic=epic,
        confirm=data,
    )

    return ok, data if isinstance(data, dict) else {"raw": data}


def resolve_real_deal_id(headers: Dict[str, str], confirm: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Dict[str, Any]]:
    candidates = extract_deal_candidates(confirm)
    candidate_ids = [c["dealId"] for c in candidates if c.get("dealId")]

    log(
        "RUNNER_DEAL_ID_CANDIDATES",
        asset=ASSET,
        candidates=candidates,
        dealReference=confirm.get("dealReference"),
    )

    if not candidate_ids:
        return False, None, None, {
            "reason": "NO_DEAL_ID_CANDIDATES",
            "confirm": confirm,
        }

    last_positions = []

    for attempt, delay in enumerate(POSITION_BACKOFFS, start=1):
        time.sleep(delay)
        positions = asset_positions(headers, ASSET)
        last_positions = positions
        visible_ids = [str(p.get("dealId")) for p in positions if p.get("dealId")]

        log(
            "RUNNER_RESOLVE_DEAL_ID_ATTEMPT",
            asset=ASSET,
            attempt=attempt,
            delay=delay,
            candidate_ids=candidate_ids,
            visible_ids=visible_ids,
        )

        for p in positions:
            did = str(p.get("dealId"))
            if did in candidate_ids:
                log(
                    "RUNNER_REAL_DEAL_ID_RESOLVED",
                    asset=ASSET,
                    real_deal_id=did,
                    matched_position=p,
                    attempt=attempt,
                )
                return True, did, p, {
                    "attempt": attempt,
                    "candidate_ids": candidate_ids,
                    "visible_ids": visible_ids,
                }

    return False, None, None, {
        "reason": "NO_CANDIDATE_VISIBLE_AFTER_BACKOFF",
        "candidate_ids": candidate_ids,
        "last_positions": last_positions,
        "confirm": confirm,
    }


# ======================================================================
# SIZE LADDER / NETTING ORDER
# ======================================================================

def update_sequence_for_signal(state: Dict[str, Any], bias: str) -> Dict[str, Any]:
    previous = state.get("active_bias")

    if bias not in ("BUY", "SELL"):
        return state

    if previous != bias:
        log(
            "RUNNER_SIGNAL_SIDE_CHANGED",
            previous_bias=previous,
            new_bias=bias,
            rule="NETTING_OPPOSITE_SEQUENCE_RESTARTS_AT_0_05",
        )
        state["active_bias"] = bias
        state["sequence_count"] = 0

    return state


def next_ladder_size(state: Dict[str, Any]) -> float:
    n = int(state.get("sequence_count") or 0)
    size = BASE_SIZE + (n * SIZE_STEP)
    size = min(size, MAX_SIZE)
    return round(size, 2)


def advance_ladder(state: Dict[str, Any]) -> Dict[str, Any]:
    state["sequence_count"] = int(state.get("sequence_count") or 0) + 1
    state["last_signal_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save_state(state)
    return state





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


# ======================================================================
# RATE LIMITER
# ======================================================================

def prune_open_window(now: Optional[float] = None) -> None:
    now = now or time.time()
    cutoff = now - 60.0
    while _open_ts_window and _open_ts_window[0] < cutoff:
        _open_ts_window.pop(0)


def opens_last_60s() -> int:
    prune_open_window()
    return len(_open_ts_window)


def can_open_now() -> Tuple[bool, Dict[str, Any]]:
    now = time.time()
    prune_open_window(now)

    count = len(_open_ts_window)

    if count >= TARGET_OPENINGS_PER_MIN:
        return False, {
            "reason": "RATE_LIMIT_REACHED",
            "opens_last_60s": count,
            "target_openings_per_min": TARGET_OPENINGS_PER_MIN,
            "window": list(_open_ts_window),
        }

    return True, {
        "reason": "RATE_LIMIT_OK",
        "opens_last_60s": count,
        "target_openings_per_min": TARGET_OPENINGS_PER_MIN,
    }


def register_open_window() -> None:
    _open_ts_window.append(time.time())
    prune_open_window()



# ======================================================================
# CLOSE WINNERS ETH ONLY
# ======================================================================

def parse_capital_utc_ts(value: Any) -> Optional[float]:
    if not value:
        return None

    s = str(value).strip().replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).timestamp()
        except Exception:
            pass

    return None


def position_age_sec(position: Dict[str, Any]) -> Optional[float]:
    ts = position.get("createdDateUTC")
    raw_pos = {}
    raw = position.get("raw", {}) if isinstance(position.get("raw"), dict) else {}
    if isinstance(raw.get("position"), dict):
        raw_pos = raw.get("position", {})

    if not ts:
        ts = raw_pos.get("createdDateUTC") or raw_pos.get("createdDate")

    parsed = parse_capital_utc_ts(ts)
    if parsed is None:
        return None

    return max(0.0, time.time() - parsed)


def winning_close_candidates(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = []

    for p in positions:
        epic = str(p.get("epic") or "").upper()
        deal_id = p.get("dealId")
        upl = safe_float(p.get("upl"))
        age = position_age_sec(p)

        if epic in PROTECTED_ASSETS:
            log("RUNNER_WINNER_CLOSE_SKIP_PROTECTED", asset=ASSET, protected_epic=epic, dealId=deal_id)
            continue

        if epic != ASSET:
            continue

        if not deal_id:
            log("RUNNER_WINNER_CLOSE_SKIP_NO_DEALID", asset=ASSET, position=p)
            continue

        if upl <= 0:
            continue

        if upl < WIN_MIN_POSITION_UPL:
            log(
                "RUNNER_WINNER_CLOSE_SKIP_SMALL_UPL",
                asset=ASSET,
                dealId=deal_id,
                upl=upl,
                min_upl=WIN_MIN_POSITION_UPL,
            )
            continue

        if WIN_MIN_AGE_SEC > 0 and (age is None or age < WIN_MIN_AGE_SEC):
            log(
                "RUNNER_WINNER_CLOSE_SKIP_TOO_YOUNG",
                asset=ASSET,
                dealId=deal_id,
                upl=upl,
                age_sec=age,
                min_age_sec=WIN_MIN_AGE_SEC,
            )
            continue

        c = dict(p)
        c["age_sec"] = age
        candidates.append(c)

    candidates.sort(key=lambda x: safe_float(x.get("upl")), reverse=True)
    return candidates


def winning_basket_decision(
    candidates: List[Dict[str, Any]],
    positions: List[Dict[str, Any]],
    signal: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    total_upl = sum(safe_float(p.get("upl")) for p in candidates)
    total_margin = sum(estimate_position_margin(p) for p in candidates)
    margin_pct = (total_upl / total_margin * 100.0) if total_margin > 0 else 0.0

    net = net_exposure(positions)
    net_side = net_side_from_exposure(net)
    bias = str(signal.get("bias") or "WAIT").upper()

    reasons = []
    if total_upl >= WIN_BASKET_TP_EUR:
        reasons.append("BASKET_TP_EUR")

    if WIN_BASKET_MARGIN_PCT > 0 and margin_pct >= WIN_BASKET_MARGIN_PCT:
        reasons.append("BASKET_MARGIN_PCT")

    if WIN_CLOSE_ON_WAIT and bias == "WAIT":
        reasons.append("SIGNAL_WAIT")

    if (
        WIN_CLOSE_ON_SIGNAL_REVERSAL
        and net_side in ("BUY", "SELL")
        and bias in ("BUY", "SELL")
        and bias == opposite_side(net_side)
    ):
        reasons.append("SIGNAL_REVERSAL")

    ok = bool(candidates and reasons)
    info = {
        "ok": ok,
        "reasons": reasons,
        "candidate_count": len(candidates),
        "candidate_dealIds": [p.get("dealId") for p in candidates],
        "candidate_upls": [p.get("upl") for p in candidates],
        "total_upl": total_upl,
        "total_margin_est": total_margin,
        "basket_margin_pct": margin_pct,
        "win_basket_tp_eur": WIN_BASKET_TP_EUR,
        "win_basket_margin_pct": WIN_BASKET_MARGIN_PCT,
        "win_min_position_upl": WIN_MIN_POSITION_UPL,
        "win_min_age_sec": WIN_MIN_AGE_SEC,
        "signal_bias": bias,
        "net_exposure": net,
        "net_side": net_side,
    }

    log("RUNNER_WINNING_BASKET_DECISION", asset=ASSET, **info)
    return ok, info


def close_winner_position(headers: Dict[str, str], position: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    epic = str(position.get("epic") or "").upper()
    deal_id = position.get("dealId")
    upl = safe_float(position.get("upl"))

    if epic != ASSET or epic in PROTECTED_ASSETS:
        return False, {
            "stage": "REFUSED_NOT_TRADABLE_ASSET",
            "epic": epic,
            "dealId": deal_id,
        }

    if not deal_id:
        return False, {
            "stage": "REFUSED_NO_DEAL_ID",
            "position": position,
        }

    if upl <= 0:
        log(
            "RUNNER_WINNER_CLOSE_REFUSED_NOT_PROFITABLE",
            asset=ASSET,
            dealId=deal_id,
            upl=upl,
            rule="NEVER_CLOSE_LOSING_POSITION",
        )
        return False, {
            "stage": "REFUSED_NOT_PROFITABLE",
            "dealId": deal_id,
            "upl": upl,
        }

    log(
        "RUNNER_WINNER_CLOSE_REQUEST",
        asset=ASSET,
        dealId=deal_id,
        direction=position.get("direction"),
        size=position.get("size"),
        upl=upl,
        age_sec=position.get("age_sec"),
    )

    status, data = api_delete(headers, f"/positions/{deal_id}")

    log(
        "RUNNER_WINNER_CLOSE_RESPONSE",
        asset=ASSET,
        dealId=deal_id,
        status=status,
        response=data,
    )

    if status != 200 or not isinstance(data, dict) or not data.get("dealReference"):
        return False, {
            "stage": "DELETE_POSITION_FAILED",
            "dealId": deal_id,
            "status": status,
            "response": data,
        }

    deal_ref = data.get("dealReference")
    confirm_ok, confirm = confirm_reference(headers, deal_ref)

    after_positions = asset_positions(headers, ASSET)
    still_visible = str(deal_id) in position_ids(after_positions)

    ok = confirm_ok and not still_visible

    info = {
        "stage": "WINNER_CLOSE_CONFIRMED" if ok else "WINNER_CLOSE_SENT_BUT_STILL_VISIBLE_OR_UNCONFIRMED",
        "dealId": deal_id,
        "dealReference": deal_ref,
        "upl": upl,
        "status": status,
        "response": data,
        "confirm_ok": confirm_ok,
        "confirm": confirm,
        "still_visible": still_visible,
        "positions_after": after_positions,
    }

    log("RUNNER_WINNER_CLOSE_RESULT", asset=ASSET, ok=ok, info=info)
    return ok, info


def close_winning_basket_if_needed(
    headers: Dict[str, str],
    positions: List[Dict[str, Any]],
    signal: Dict[str, Any],
) -> Tuple[int, Dict[str, Any]]:
    if not CLOSE_WINNERS_ENABLED:
        return 0, {
            "stage": "CLOSE_WINNERS_DISABLED",
        }

    candidates = winning_close_candidates(positions)
    should_close, decision = winning_basket_decision(candidates, positions, signal)

    if not should_close:
        return 0, {
            "stage": "NO_WINNING_BASKET_TO_CLOSE",
            "decision": decision,
        }

    closed = 0
    results = []

    for p in candidates[: max(1, WIN_MAX_CLOSES_PER_LOOP)]:
        ok, info = close_winner_position(headers, p)
        results.append(info)
        if ok:
            closed += 1

    summary = {
        "stage": "WINNING_BASKET_CLOSE_ATTEMPTED",
        "closed_count": closed,
        "attempted_count": len(results),
        "decision": decision,
        "results": results,
    }

    log("RUNNER_WINNING_BASKET_CLOSE_SUMMARY", asset=ASSET, **summary)
    return closed, summary

# ======================================================================
# NO DIRECT LOSS CLOSE SAFETY
# ======================================================================

def direct_close_is_allowed(position: Dict[str, Any]) -> bool:
    upl = float(position.get("upl") or 0.0)

    if upl < 0 and not ALLOW_DIRECT_LOSS_CLOSE:
        log(
            "RUNNER_DIRECT_LOSS_CLOSE_FORBIDDEN",
            asset=ASSET,
            dealId=position.get("dealId"),
            upl=upl,
            rule="NO_DELETE_ON_LOSING_POSITION",
        )
        return False

    return True


# ======================================================================
# MAIN
# ======================================================================




def main() -> None:
    FAS.safety_banner()

    if ASSET in PROTECTED_ASSETS and not _v244_protected_deal_ids():
        raise RuntimeError(f"{ASSET} est protege, impossible de le trader sans V244_PROTECTED_DEAL_IDS")
    if ASSET in PROTECTED_ASSETS and _v244_protected_deal_ids():
        log("RUNNER_PROTECTED_ASSET_ALLOWED_WITH_PROTECTED_DEALS", asset=ASSET, protected_deal_ids=sorted(_v244_protected_deal_ids()))

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
        margin_driven_mode=MARGIN_DRIVEN_MODE,
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
        close_winners_enabled=CLOSE_WINNERS_ENABLED,
        win_basket_tp_eur=WIN_BASKET_TP_EUR,
        win_min_position_upl=WIN_MIN_POSITION_UPL,
        win_basket_margin_pct=WIN_BASKET_MARGIN_PCT,
        win_min_age_sec=WIN_MIN_AGE_SEC,
        win_close_on_wait=WIN_CLOSE_ON_WAIT,
        win_close_on_signal_reversal=WIN_CLOSE_ON_SIGNAL_REVERSAL,
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

            closed_count, close_info = close_winning_basket_if_needed(headers, positions, signal)
            if closed_count > 0:
                log(
                    "RUNNER_LOOP_PAUSE_AFTER_WINNER_CLOSE",
                    asset=ASSET,
                    closed_count=closed_count,
                    close_info=close_info,
                    wait_sec=CLOSE_THEN_WAIT_SEC,
                )
                time.sleep(CLOSE_THEN_WAIT_SEC)
                # V2446B:
                # Ancien comportement: continue ici, donc aucune nouvelle entrée après une position ETH ouverte.
                # Nouveau comportement: si le panier n'est pas prêt à fermer, on continue la boucle logique
                # vers open_market_netting_safe(), afin que V2446 teste le prochain palier adverse.
                log(
                    "RUNNER_BASKET_NOT_READY_OPEN_FLOW_CONTINUES",
                    asset=ASSET,
                    close_info=close_info,
                )
                pass

            if bias not in ("BUY", "SELL"):
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="NO_M15_VWAP_BTC_SIGNAL",
                    signal=signal,
                )
                time.sleep(SLEEP_SEC)
                continue

            if signal_bar_already_traded(state, signal) and os.getenv("V244_ENTRY_MODE", "").upper().strip() != "ADVERSE_PRICE_STEPS":
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
                traceback=traceback.format_exc().replace("\n", " / "),
            )

            if "429" in msg or "too-many" in msg.lower() or "session" in msg.lower():
                time.sleep(120)
                headers = ensure_headers(G.login())
                log("RUNNER_RELOGIN_OK", asset=ASSET)
                assert_account_netting(headers)
            else:
                time.sleep(20)







# === V2445_FULL_ETH_BASKET_TP_START ===
import os as _v2445_os, time as _v2445_time
from datetime import datetime as _v2445_dt, timezone as _v2445_tz

def _v2445_bool(name, default=False):
    v = _v2445_os.getenv(name)
    return default if v is None else str(v).strip().lower() in ("1","true","yes","on","y")

def _v2445_float(name, default):
    try: return float(_v2445_os.getenv(name, str(default)))
    except Exception: return float(default)

def _v2445_int(name, default):
    try: return int(float(_v2445_os.getenv(name, str(default))))
    except Exception: return int(default)

_v2445_os.environ.setdefault("V244_MAX_OPEN_POSITIONS", "12")
_v2445_os.environ.setdefault("V244_MARGIN_DRIVEN_MODE", "1")
_v2445_os.environ.setdefault("V244_MAX_NET_EXPOSURE", "0")
_v2445_os.environ.setdefault("V244_CLOSE_FULL_ETH_BASKET_ENABLED", "1")
_v2445_os.environ.setdefault("V244_FULL_ETH_BASKET_TP_EUR", _v2445_os.getenv("V244_WIN_BASKET_TP_EUR", "1.0"))

try:
    MAX_OPEN_POSITIONS = _v2445_int("V244_MAX_OPEN_POSITIONS", 12)
    max_open_positions = MAX_OPEN_POSITIONS
    MARGIN_DRIVEN_MODE = True
    MAX_NET_EXPOSURE = 0.0
except Exception:
    pass

def _v2445_log(event, **fields):
    for name in ("audit", "audit_event", "log_event", "write_audit_event", "write_audit", "audit_log"):
        fn = globals().get(name)
        if callable(fn):
            for call in (
                lambda: fn(event, **fields),
                lambda: fn({"event": event, **fields}),
                lambda: fn(**{"event": event, **fields}),
            ):
                try:
                    call()
                    return
                except Exception:
                    pass
    ts = _v2445_dt.now(_v2445_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("ts_utc=%s | event=%s | %s" % (ts, event, " | ".join(f"{k}={v}" for k,v in fields.items())), flush=True)

def _v2445_get(obj, *keys):
    if obj is None:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if obj.get(k) not in (None, ""):
                return obj.get(k)
        for parent in ("position", "market", "raw"):
            child = obj.get(parent)
            if isinstance(child, dict):
                v = _v2445_get(child, *keys)
                if v not in (None, ""):
                    return v
    for k in keys:
        if hasattr(obj, k):
            v = getattr(obj, k)
            if v not in (None, ""):
                return v
    return None

def _v2445_num(v, default=0.0):
    try: return float(str(v).replace(",", "."))
    except Exception: return float(default)

def _v2445_epic(pos):
    return str(_v2445_get(pos, "epic", "instrumentEpic", "symbol") or "").upper()

def _v2445_deal_id(pos):
    return str(_v2445_get(pos, "dealId", "deal_id", "id") or "")

def _v2445_upl(pos):
    return _v2445_num(_v2445_get(pos, "upl", "profit", "profitAndLoss", "pnl"), 0.0)

def _v2445_created_ts(pos):
    raw = _v2445_get(pos, "createdDateUTC", "createdDate", "openTime", "created_at")
    if not raw:
        return None
    try:
        txt = str(raw).replace("Z", "+00:00")
        dt = _v2445_dt.fromisoformat(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_v2445_tz.utc)
        return dt.timestamp()
    except Exception:
        return None

def _v2445_age(pos):
    ts = _v2445_created_ts(pos)
    return 999999.0 if ts is None else max(0.0, _v2445_time.time() - ts)

def _v2445_positions_from_result(res):
    if isinstance(res, list):
        return res
    if isinstance(res, dict):
        for k in ("positions", "open_positions", "data"):
            v = res.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                vv = _v2445_positions_from_result(v)
                if vv:
                    return vv
    return []

def _v2445_extract_positions(args, kwargs):
    for k in ("positions", "open_positions", "asset_positions", "positions_after"):
        v = kwargs.get(k)
        if isinstance(v, list):
            return v
    for a in args:
        if isinstance(a, list):
            return a
        if isinstance(a, dict):
            v = _v2445_positions_from_result(a)
            if v:
                return v
    for name in ("get_open_positions", "get_positions", "api_get_positions", "fetch_positions"):
        fn = globals().get(name)
        if callable(fn):
            try:
                v = _v2445_positions_from_result(fn())
                if v:
                    return v
            except Exception:
                pass
    return []

def _v2445_result_ok(res):
    if res is None:
        return True
    if hasattr(res, "status_code"):
        return 200 <= int(res.status_code) < 300
    if isinstance(res, dict):
        st = res.get("status") or res.get("status_code")
        if st is not None:
            try: return 200 <= int(st) < 300
            except Exception: pass
        if res.get("errorCode") or res.get("error"):
            return False
    return True

def _v2445_try_close(pos):
    deal_id = _v2445_deal_id(pos)
    if not deal_id:
        return False, "NO_DEAL_ID"
    calls = []
    for name in ("close_position", "close_position_by_deal_id", "api_close_position", "delete_position"):
        fn = globals().get(name)
        if callable(fn):
            calls.append((name + "(pos)", lambda fn=fn: fn(pos)))
            calls.append((name + "(deal_id)", lambda fn=fn: fn(deal_id)))
            calls.append((name + "(dealId=)", lambda fn=fn: fn(dealId=deal_id)))
    fn = globals().get("api_delete")
    if callable(fn):
        for path in (f"/api/v1/positions/{deal_id}", f"/positions/{deal_id}", f"positions/{deal_id}", deal_id):
            calls.append((f"api_delete({path})", lambda fn=fn, headers=headers, path=path: fn(headers, path)))
    last = "NO_CLOSE_FUNCTION"
    for label, call in calls:
        try:
            res = call()
            if _v2445_result_ok(res):
                return True, {"method": label, "response": res}
            last = {"method": label, "response": res}
        except Exception as exc:
            last = {"method": label, "error": repr(exc)}
    return False, last

_v2445_previous_close_winning_basket_if_needed = globals().get("close_winning_basket_if_needed")

def close_winning_basket_if_needed(*args, **kwargs):
    if not _v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True):
        if callable(_v2445_previous_close_winning_basket_if_needed):
            return _v2445_previous_close_winning_basket_if_needed(*args, **kwargs)
        return 0, {"stage": "CLOSE_WINNERS_DISABLED_NO_PREVIOUS"}

    asset = str(_v2445_os.getenv("V244_TRADED_ASSET", globals().get("TRADED_ASSET", os.getenv("ASSET", "ETHUSD")))).upper()
    tp = _v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0)
    min_age = _v2445_float("V244_FULL_BASKET_MIN_AGE_SEC", 0.0)

    positions = _v2445_extract_positions(args, kwargs)
    eth_positions = [p for p in positions if _v2445_epic(p) == asset]
    total_upl = sum(_v2445_upl(p) for p in eth_positions)
    deal_ids = [_v2445_deal_id(p) for p in eth_positions if _v2445_deal_id(p)]
    too_young = [_v2445_deal_id(p) for p in eth_positions if _v2445_age(p) < min_age]

    reasons = []
    if not eth_positions: reasons.append("NO_MAIN_ASSET_POSITION")
    if total_upl < tp: reasons.append("TOTAL_UPL_BELOW_TP")
    if too_young: reasons.append("POSITION_TOO_YOUNG")

    ok = not reasons
    _v2445_log("RUNNER_BASKET_DECISION", asset=asset, ok=ok, reasons=reasons,
               open_positions_count=len(eth_positions), dealIds=deal_ids,
               total_upl=round(total_upl, 4), tp=tp, min_age_sec=min_age,
               max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12))

    if not ok:
        return 0, {"stage": "ETH_BASKET_NOT_READY", "reasons": reasons,
                   "total_upl": round(total_upl, 4), "tp": tp}

    _v2445_log("RUNNER_BASKET_CLOSE_ALL_START", asset=asset,
               reason="TOTAL_ETH_BASKET_TP_REACHED", total_upl=round(total_upl, 4),
               tp=tp, count=len(eth_positions), dealIds=deal_ids)

    allow_names = ("ALLOW_DIRECT_LOSS_CLOSE", "V244_ALLOW_DIRECT_LOSS_CLOSE", "allow_direct_loss_close")
    old_globals = {n: globals().get(n, None) for n in allow_names}
    old_env = _v2445_os.environ.get("V244_ALLOW_DIRECT_LOSS_CLOSE")
    globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = True
    globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = set(deal_ids)
    for n in allow_names:
        globals()[n] = True
    _v2445_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = "1"

    all_ok = True
    try:
        for pos in eth_positions:
            did = _v2445_deal_id(pos)
            ok_close, info = _v2445_try_close(pos)
            all_ok = all_ok and bool(ok_close)
            _v2445_log("RUNNER_BASKET_CLOSE_RESULT", asset=asset, dealId=did,
                       upl=round(_v2445_upl(pos), 4), ok=ok_close, info=info)
    finally:
        globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = False
        globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = set()
        for n, v in old_globals.items():
            if v is None and n in globals():
                try: del globals()[n]
                except Exception: pass
            else:
                globals()[n] = v
        if old_env is None:
            _v2445_os.environ.pop("V244_ALLOW_DIRECT_LOSS_CLOSE", None)
        else:
            _v2445_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = old_env

    _v2445_log("RUNNER_BASKET_CLOSE_ALL_DONE", asset=asset, ok=all_ok,
               total_upl=round(total_upl, 4), count=len(eth_positions))
    closed_count = len(eth_positions) if all_ok else 0
    return closed_count, {"stage": "ETH_BASKET_CLOSED_ALL", "ok": all_ok,
                          "closed_count": closed_count,
                          "total_upl": round(total_upl, 4),
                          "count": len(eth_positions), "dealIds": deal_ids}

_v2445_log("RUNNER_V2445_FULL_ETH_BASKET_PATCH_ACTIVE",
           max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12),
           full_eth_basket_close_enabled=_v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True),
           full_eth_basket_tp_eur=_v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0))
# === V2445_FULL_ETH_BASKET_TP_END ===


# === V2446_ADVERSE_PRICE_STEPS_START ===
try:
    import v2446_adverse_steps_patch as _v2446_steps_patch
    _v2446_steps_patch.install(globals())
except Exception as _v2446_exc:
    try:
        print("RUNNER_V2446_ADVERSE_STEP_PATCH_INSTALL_FAILED", repr(_v2446_exc), flush=True)
    except Exception:
        pass
# === V2446_ADVERSE_PRICE_STEPS_END ===


# === V2446I_CASCADE_RULES_START ===
# V2446I hard floors + anti-yoyo wrapper.
# This block deliberately wraps existing runner functions instead of replacing the
# whole loop. It is idempotent and controlled by V2446I_CASCADE_ENABLED.
import os as _v2446i_os
import time as _v2446i_time


def _v2446i_bool(name, default=True):
    v = _v2446i_os.getenv(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _v2446i_float(name, default):
    try:
        return float(_v2446i_os.getenv(name, str(default)))
    except Exception:
        return float(default)


def _v2446i_optional_float(name):
    v = _v2446i_os.getenv(name)
    if v is None or str(v).strip() == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _v2446i_int(name, default):
    try:
        return int(float(_v2446i_os.getenv(name, str(default))))
    except Exception:
        return int(default)


def _v2446i_log(event, **kw):
    try:
        fn = globals().get("log")
        if callable(fn):
            fn(event, **kw)
    except Exception:
        pass

    try:
        ts = _v2446i_time.strftime("%Y-%m-%dT%H:%M:%SZ", _v2446i_time.gmtime())
        parts = [f"ts_utc={ts}", f"event={event}"]
        for k, v in kw.items():
            parts.append(f"{k}={v}")
        print(" | ".join(parts), flush=True)
    except Exception:
        pass


def _v2446i_asset():
    return str(_v2446i_os.getenv("V244_TRADED_ASSET", globals().get("ASSET", os.getenv("ASSET", "ETHUSD")))).upper()


def _v2446i_epic(pos):
    fn = globals().get("_v2445_epic")
    if callable(fn):
        try:
            return str(fn(pos)).upper()
        except Exception:
            pass
    if not isinstance(pos, dict):
        return ""
    return str(
        pos.get("epic")
        or pos.get("market", {}).get("epic")
        or pos.get("instrument", {}).get("epic")
        or ""
    ).upper()


def _v2446i_deal_id(pos):
    fn = globals().get("_v2445_deal_id")
    if callable(fn):
        try:
            return fn(pos)
        except Exception:
            pass
    if not isinstance(pos, dict):
        return None
    return pos.get("dealId") or pos.get("deal_id") or pos.get("position", {}).get("dealId")


def _v2446i_direction(pos):
    if not isinstance(pos, dict):
        return None
    return str(
        pos.get("direction")
        or pos.get("side")
        or pos.get("position", {}).get("direction")
        or ""
    ).upper() or None


def _v2446i_upl(pos):
    fn = globals().get("_v2445_upl")
    if callable(fn):
        try:
            return float(fn(pos))
        except Exception:
            pass
    if not isinstance(pos, dict):
        return 0.0
    for k in ("upl", "profit", "profitLoss", "unrealizedProfitLoss"):
        try:
            v = pos.get(k)
            if v is not None:
                return float(v)
        except Exception:
            pass
    try:
        return float(pos.get("position", {}).get("upl") or 0.0)
    except Exception:
        return 0.0


def _v2446i_age(pos):
    fn = globals().get("_v2445_age")
    if callable(fn):
        try:
            return float(fn(pos))
        except Exception:
            pass
    return 0.0


def _v2446i_result_ok(res):
    if res is None:
        return True

    if isinstance(res, tuple) and res:
        try:
            return 200 <= int(res[0]) < 300
        except Exception:
            return False

    if hasattr(res, "status_code"):
        try:
            return 200 <= int(res.status_code) < 300
        except Exception:
            return False

    if isinstance(res, dict):
        st = res.get("status") or res.get("status_code")
        if st is not None:
            try:
                return 200 <= int(st) < 300
            except Exception:
                return False
        if res.get("errorCode") or res.get("error"):
            return False

    fn = globals().get("_v2445_result_ok")
    if callable(fn):
        try:
            return bool(fn(res))
        except Exception:
            return False

    return True


def _v2446i_extract_positions(args, kwargs):
    fn = globals().get("_v2445_extract_positions")
    if callable(fn):
        try:
            out = fn(args, kwargs)
            if isinstance(out, list):
                return out
        except Exception:
            pass
    for v in list(kwargs.values()) + list(args):
        if isinstance(v, list):
            return v
    return []


def _v2446i_extract_headers(args, kwargs):
    h = kwargs.get("headers")
    if isinstance(h, dict):
        return h
    if args and isinstance(args[0], dict):
        return args[0]
    return None


def _v2446i_eth_positions(positions):
    asset = _v2446i_asset()
    out = []
    for p in (positions or []):
        if _v2446i_epic(p) != asset:
            continue
        did = _v2446i_deal_id(p) or _v244_deal_id_from_position(p)
        if _v244_is_protected_deal_id(did):
            _v2446i_log("RUNNER_V2446I_POSITION_IGNORED_PROTECTED_DEAL", asset=asset, dealId=did)
            continue
        out.append(p)
    return out


def _v2446i_try_close(pos, headers):
    deal_id = _v2446i_deal_id(pos)
    if not deal_id:
        return False, "NO_DEAL_ID"

    calls = []

    def add(label, fn):
        calls.append((label, fn))

    for name in ("close_position", "close_position_by_deal_id", "api_close_position", "delete_position"):
        fn = globals().get(name)
        if callable(fn):
            if headers:
                add(name + "(headers,pos)", lambda fn=fn, headers=headers, pos=pos: fn(headers, pos))
                add(name + "(headers,deal_id)", lambda fn=fn, headers=headers, deal_id=deal_id: fn(headers, deal_id))
                add(name + "(headers=headers,deal_id=)", lambda fn=fn, headers=headers, deal_id=deal_id: fn(headers=headers, deal_id=deal_id))
                add(name + "(headers=headers,dealId=)", lambda fn=fn, headers=headers, deal_id=deal_id: fn(headers=headers, dealId=deal_id))
            add(name + "(pos)", lambda fn=fn, pos=pos: fn(pos))
            add(name + "(deal_id)", lambda fn=fn, deal_id=deal_id: fn(deal_id))
            add(name + "(dealId=)", lambda fn=fn, deal_id=deal_id: fn(dealId=deal_id))

    fn = globals().get("api_delete")
    if callable(fn) and headers:
        # api_delete() already prefixes /api/v1 in this runner. The canonical close path is /positions/{dealId}.
        add(f"api_delete(/positions/{deal_id})", lambda fn=fn, headers=headers, deal_id=deal_id: fn(headers, f"/positions/{deal_id}"))

    last = "NO_CLOSE_FUNCTION"
    attempts = []

    for label, call in calls:
        try:
            res = call()
            ok = _v2446i_result_ok(res)
            attempts.append({"method": label, "ok": ok, "response": res})
            if ok:
                return True, {"method": label, "response": res, "attempts_tail": attempts[-5:]}
            last = {"method": label, "response": res}
        except Exception as exc:
            last = {"method": label, "error": repr(exc)}
            attempts.append({"method": label, "ok": False, "error": repr(exc)})

    return False, {"last": last, "attempts_tail": attempts[-12:]}


def _v2446i_start_cooldown(reason):
    now = _v2446i_time.time()
    current_until = float(globals().get("_V2446I_RESET_COOLDOWN_UNTIL") or 0.0)
    if current_until > now:
        _v2446i_log(
            "RUNNER_RESET_COOLDOWN_ALREADY_ACTIVE",
            asset=_v2446i_asset(),
            reason=reason,
            remaining_sec=round(current_until - now, 2),
            reset_cooldown_until=current_until,
        )
        return

    globals()["_V2446I_RESET_COOLDOWN_UNTIL"] = now + _v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0)
    _v2446i_log(
        "RUNNER_RESET_COOLDOWN_STARTED",
        asset=_v2446i_asset(),
        reason=reason,
        cooldown_sec=_v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0),
        reset_cooldown_until=globals().get("_V2446I_RESET_COOLDOWN_UNTIL"),
    )


def _v2446i_close_all(headers, eth_positions, reason, total_upl):
    asset = _v2446i_asset()
    deal_ids = [_v2446i_deal_id(p) for p in eth_positions if _v2446i_deal_id(p)]
    _v2446i_log(
        "RUNNER_V2446I_HARD_CLOSE_ALL_START",
        asset=asset,
        reason=reason,
        total_upl=round(total_upl, 4),
        count=len(eth_positions),
        dealIds=deal_ids,
    )

    allow_names = ("ALLOW_DIRECT_LOSS_CLOSE", "V244_ALLOW_DIRECT_LOSS_CLOSE", "allow_direct_loss_close")
    old_globals = {n: globals().get(n, None) for n in allow_names}
    old_env = _v2446i_os.environ.get("V244_ALLOW_DIRECT_LOSS_CLOSE")
    old_in_progress = globals().get("_V2445_FULL_BASKET_CLOSE_IN_PROGRESS", False)
    old_allowed = globals().get("_V2445_FULL_BASKET_ALLOWED_DEAL_IDS", set())

    globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = True
    globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = set(deal_ids)
    for n in allow_names:
        globals()[n] = True
    _v2446i_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = "1"

    all_ok = True
    try:
        for pos in eth_positions:
            did = _v2446i_deal_id(pos)
            ok_close, info = _v2446i_try_close(pos, headers)
            all_ok = all_ok and bool(ok_close)
            _v2446i_log(
                "RUNNER_V2446I_HARD_CLOSE_RESULT",
                asset=asset,
                dealId=did,
                upl=round(_v2446i_upl(pos), 4),
                ok=ok_close,
                info=info,
            )
    finally:
        globals()["_V2445_FULL_BASKET_CLOSE_IN_PROGRESS"] = old_in_progress
        globals()["_V2445_FULL_BASKET_ALLOWED_DEAL_IDS"] = old_allowed
        for n, v in old_globals.items():
            if v is None and n in globals():
                try:
                    del globals()[n]
                except Exception:
                    pass
            else:
                globals()[n] = v
        if old_env is None:
            _v2446i_os.environ.pop("V244_ALLOW_DIRECT_LOSS_CLOSE", None)
        else:
            _v2446i_os.environ["V244_ALLOW_DIRECT_LOSS_CLOSE"] = old_env

    _v2446i_log(
        "RUNNER_V2446I_HARD_CLOSE_ALL_DONE",
        asset=asset,
        ok=all_ok,
        reason=reason,
        total_upl=round(total_upl, 4),
        count=len(eth_positions),
    )
    if all_ok:
        _v2446i_start_cooldown(reason)
    return len(eth_positions) if all_ok else 0, {
        "stage": "V2446I_HARD_CLOSE_ALL",
        "ok": all_ok,
        "reason": reason,
        "closed_count": len(eth_positions) if all_ok else 0,
        "total_upl": round(total_upl, 4),
        "dealIds": deal_ids,
    }



_v2446i_previous_close_winning_basket_if_needed = globals().get("close_winning_basket_if_needed")


def close_winning_basket_if_needed(*args, **kwargs):
    if not _v2446i_bool("V2446I_CASCADE_ENABLED", True):
        if callable(_v2446i_previous_close_winning_basket_if_needed):
            return _v2446i_previous_close_winning_basket_if_needed(*args, **kwargs)
        return 0, {"stage": "V2446I_DISABLED_NO_PREVIOUS_CLOSE"}

    headers = _v2446i_extract_headers(args, kwargs)
    positions = _v2446i_extract_positions(args, kwargs)
    eth_positions = _v2446i_eth_positions(positions)
    total_upl = sum(_v2446i_upl(p) for p in eth_positions)
    count = len(eth_positions)

    tp = _v2446i_float("V2446I_BASKET_TAKE_PROFIT_EUR", 5.0)
    l1_stop = abs(_v2446i_float("V2446I_L1_STOP_LOSS_EUR", 3.0))
    max_loss = abs(_v2446i_float("V2446I_BASKET_MAX_LOSS_EUR", 15.0))
    max_legs = _v2446i_int("V2446I_MAX_LEGS", 5)
    time_stop = _v2446i_float("V2446I_TIME_STOP_SEC", 14400.0)
    max_age = max([_v2446i_age(p) for p in eth_positions] or [0.0])

    reasons = []
    close_reason = None
    if not eth_positions:
        reasons.append("NO_MAIN_ASSET_POSITION")
    if count > 0 and total_upl >= tp:
        close_reason = "BASKET_TAKE_PROFIT_REACHED"
    elif count == 1 and total_upl <= -l1_stop:
        close_reason = "L1_STOP_LOSS_REACHED"
    elif count >= 2 and total_upl <= -max_loss:
        close_reason = "BASKET_MAX_LOSS_REACHED"
    elif count > 0 and time_stop > 0 and max_age >= time_stop and total_upl < 0:
        close_reason = "TIME_STOP_LOSS_REACHED"

    if close_reason is None:
        if count > 0 and total_upl < tp:
            reasons.append("TOTAL_UPL_BELOW_TP")
        if count >= max_legs:
            reasons.append("MAX_LEGS_REACHED")

    _v2446i_log(
        "RUNNER_BASKET_DECISION",
        asset=_v2446i_asset(),
        ok=bool(close_reason),
        close_reason=close_reason,
        reasons=reasons,
        open_positions_count=count,
        dealIds=[_v2446i_deal_id(p) for p in eth_positions if _v2446i_deal_id(p)],
        total_upl=round(total_upl, 4),
        tp=tp,
        l1_stop=-l1_stop,
        basket_max_loss=-max_loss,
        max_age_sec=round(max_age, 2),
        time_stop_sec=time_stop,
        max_open_positions=max_legs,
    )

    if close_reason:
        return _v2446i_close_all(headers, eth_positions, close_reason, total_upl)

    return 0, {
        "stage": "V2446I_BASKET_NOT_READY",
        "reasons": reasons,
        "total_upl": round(total_upl, 4),
        "tp": tp,
        "max_open_positions": max_legs,
    }


_v2446i_previous_open_market_netting_safe = globals().get("open_market_netting_safe")


def _v2446i_l1_margin_estimate(size):
    per_one = _v2446i_optional_float("V2446I_MARGIN_EUR_PER_1_SIZE")
    if per_one is None:
        return None
    try:
        return float(size) * per_one
    except Exception:
        return None


def open_market_netting_safe(*args, **kwargs):
    if not _v2446i_bool("V2446I_CASCADE_ENABLED", True):
        if callable(_v2446i_previous_open_market_netting_safe):
            return _v2446i_previous_open_market_netting_safe(*args, **kwargs)
        return False, {"reason": "V2446I_DISABLED_NO_PREVIOUS_OPEN"}

    if not callable(_v2446i_previous_open_market_netting_safe):
        return False, {"reason": "NO_PREVIOUS_OPEN_MARKET_NETTING_SAFE"}

    headers = kwargs.get("headers")
    if not isinstance(headers, dict) and args and isinstance(args[0], dict):
        headers = args[0]
    side = str(kwargs.get("side") or (args[1] if len(args) > 1 else "")).upper()
    size = kwargs.get("size", args[2] if len(args) > 2 else None)
    asset = _v2446i_asset()
    max_legs = _v2446i_int("V2446I_MAX_LEGS", 5)
    l1_max_margin = _v2446i_float("V2446I_L1_MAX_MARGIN_EUR", 10.0)
    l1_max_size = _v2446i_optional_float("V2446I_L1_MAX_SIZE")

    positions = []
    fn_pos = globals().get("asset_positions")
    if callable(fn_pos) and headers:
        try:
            positions = fn_pos(headers, asset)
        except Exception as exc:
            _v2446i_log("RUNNER_V2446I_POSITION_READ_ERROR", asset=asset, exception=repr(exc))
    eth_positions = _v2446i_eth_positions(positions)
    count = len(eth_positions)

    cooldown_until = float(globals().get("_V2446I_RESET_COOLDOWN_UNTIL") or 0.0)
    now = _v2446i_time.time()
    if cooldown_until > now and count == 0:
        _v2446i_log(
            "RUNNER_RESET_COOLDOWN_ACTIVE",
            asset=asset,
            side=side,
            remaining_sec=round(cooldown_until - now, 2),
        )
        return False, {"reason": "RESET_COOLDOWN_ACTIVE", "remaining_sec": round(cooldown_until - now, 2)}
    if cooldown_until and cooldown_until <= now:
        globals()["_V2446I_RESET_COOLDOWN_UNTIL"] = 0.0
        _v2446i_log("RUNNER_RESET_COOLDOWN_DONE", asset=asset)

    if count >= max_legs:
        _v2446i_log(
            "RUNNER_V2446I_OPEN_BLOCKED_MAX_LEGS",
            asset=asset,
            side=side,
            open_positions_count=count,
            max_legs=max_legs,
        )
        return False, {"reason": "MAX_LEGS_REACHED", "open_positions_count": count, "max_legs": max_legs}

    existing_sides = sorted(set(filter(None, [_v2446i_direction(p) for p in eth_positions])))
    if count > 0 and side in ("BUY", "SELL") and existing_sides and side not in existing_sides:
        _v2446i_log(
            "RUNNER_V2446I_OPEN_BLOCKED_ANTI_YOYO",
            asset=asset,
            requested_side=side,
            existing_sides=existing_sides,
            open_positions_count=count,
        )
        return False, {"reason": "ANTI_YOYO_SIDE_LOCK", "existing_sides": existing_sides}

    if count == 0:
        margin_est = _v2446i_l1_margin_estimate(size)
        if l1_max_size is not None:
            try:
                if float(size) > l1_max_size:
                    _v2446i_log(
                        "RUNNER_V2446I_L1_SIZE_REDUCED",
                        asset=asset,
                        side=side,
                        old_size=size,
                        new_size=l1_max_size,
                    )
                    kwargs["size"] = l1_max_size
                    size = l1_max_size
                    margin_est = _v2446i_l1_margin_estimate(size)
            except Exception:
                pass
        _v2446i_log(
            "RUNNER_V2446I_L1_MARGIN_CHECK",
            asset=asset,
            side=side,
            size=size,
            margin_estimate_eur=margin_est,
            max_margin_eur=l1_max_margin,
            margin_policy="ESTIMATED_IF_V2446I_MARGIN_EUR_PER_1_SIZE_SET",
        )
        if margin_est is not None and margin_est > l1_max_margin:
            return False, {
                "reason": "L1_MARGIN_TOO_HIGH",
                "margin_estimate_eur": margin_est,
                "max_margin_eur": l1_max_margin,
            }

    return _v2446i_previous_open_market_netting_safe(*args, **kwargs)


_v2446i_previous_sync_state_with_broker_exposure = globals().get("sync_state_with_broker_exposure")


def sync_state_with_broker_exposure(state, net, net_side):
    net_side_u = str(net_side).upper()
    had_state = bool((state or {}).get("active_bias")) or int((state or {}).get("sequence_count") or 0) != 0

    if callable(_v2446i_previous_sync_state_with_broker_exposure):
        state2 = _v2446i_previous_sync_state_with_broker_exposure(state, net, net_side)
    else:
        state2 = state or {}

    if net_side_u != "FLAT":
        globals()["_V2446I_FLAT_COOLDOWN_STARTED"] = False
        return state2

    try:
        if isinstance(state2, dict):
            state2["active_bias"] = None
            state2["sequence_count"] = 0
            fn_save = globals().get("save_state")
            if callable(fn_save):
                fn_save(state2)
    except Exception as exc:
        _v2446i_log("RUNNER_V2446I_FLAT_STATE_CLEAR_ERROR", asset=_v2446i_asset(), exception=repr(exc))

    if had_state and not globals().get("_V2446I_FLAT_COOLDOWN_STARTED"):
        globals()["_V2446I_FLAT_COOLDOWN_STARTED"] = True
        _v2446i_start_cooldown("BROKER_FLAT_EXPOSURE")
    elif had_state:
        _v2446i_log("RUNNER_RESET_COOLDOWN_FLAT_ALREADY_HANDLED", asset=_v2446i_asset(), net_side=net_side_u)

    return state2



_v2446i_os.environ["V244_PRICE_STEP_POINTS"] = "0.0"
_v2446i_os.environ["V244_MIN_EFFECTIVE_STEP_POINTS"] = "0.0"
_v2446i_os.environ["V244_SPREAD_STEP_MULT"] = _v2446i_os.getenv("V2446I_SPREAD_STEP_MULT", "0.0")
_v2446i_os.environ["V244_MAX_OPEN_POSITIONS"] = _v2446i_os.getenv("V2446I_MAX_LEGS", "5")
_v2446i_os.environ["V244_FULL_ETH_BASKET_TP_EUR"] = _v2446i_os.getenv("V2446I_BASKET_TAKE_PROFIT_EUR", "5.0")
_v2446i_os.environ["V2446I_STEP_PCT"] = _v2446i_os.getenv("V2446I_STEP_PCT", "0.0007")

_v2446i_log(
    "RUNNER_V2446I_CASCADE_RULES_ACTIVE",
    asset=_v2446i_asset(),
    l1_max_margin_eur=_v2446i_float("V2446I_L1_MAX_MARGIN_EUR", 10.0),
    l1_stop_loss_eur=-abs(_v2446i_float("V2446I_L1_STOP_LOSS_EUR", 3.0)),
    basket_max_loss_eur=-abs(_v2446i_float("V2446I_BASKET_MAX_LOSS_EUR", 15.0)),
    basket_take_profit_eur=_v2446i_float("V2446I_BASKET_TAKE_PROFIT_EUR", 5.0),
    max_legs=_v2446i_int("V2446I_MAX_LEGS", 5),
    step_pct=_v2446i_float("V2446I_STEP_PCT", 0.0007),
    step_pct_display="0.07%",
    reset_cooldown_sec=_v2446i_float("V2446I_RESET_COOLDOWN_SEC", 300.0),
    time_stop_sec=_v2446i_float("V2446I_TIME_STOP_SEC", 14400.0),
)
# === V2446I_CASCADE_RULES_END ===



# === V2446J_BTC_M5_CONFIRM_START ===
# BTC M5 confirmation layer for V2446I.
# M15 remains the master signal; BTC M5 can only confirm, never create a direction.
import os as _v2446j_os
import time as _v2446j_time


def _v2446j_bool(name, default=True):
    v = _v2446j_os.getenv(name)
    if v is None:
        return bool(default)
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _v2446j_int(name, default):
    try:
        return int(float(_v2446j_os.getenv(name, str(default))))
    except Exception:
        return int(default)


def _v2446j_log(event, **kw):
    try:
        ts = _v2446j_time.strftime("%Y-%m-%dT%H:%M:%SZ", _v2446j_time.gmtime())
        parts = [f"ts_utc={ts}", f"event={event}"]
        for k, v in kw.items():
            parts.append(f"{k}={v}")
        print(" | ".join(parts), flush=True)
    except Exception:
        pass


def _v2446j_btc_m5_bias(headers):
    old_tf = globals().get("SIGNAL_TIMEFRAME")
    tf = _v2446j_os.getenv("V2446J_BTC_M5_TIMEFRAME", "MINUTE_5")
    try:
        globals()["SIGNAL_TIMEFRAME"] = tf
        bars = usable_signal_bars(get_price_bars(headers, CONFIRM_ASSET))
        vwap = compute_vwap_series(bars)
        bias = vwap_bias(vwap)
        return bias, vwap, tf
    except Exception as exc:
        return "WAIT", {"ok": False, "reason": "BTC_M5_EXCEPTION", "exception": repr(exc)}, tf
    finally:
        globals()["SIGNAL_TIMEFRAME"] = old_tf


_v2446j_previous_compute_m15_vwap_signal = globals().get("compute_m15_vwap_signal")


def compute_m15_vwap_signal(headers):
    if not callable(_v2446j_previous_compute_m15_vwap_signal):
        return {
            "asset": ASSET,
            "confirm_asset": CONFIRM_ASSET,
            "bias": "WAIT",
            "reason": "NO_PREVIOUS_M15_SIGNAL_FUNCTION",
        }

    signal = _v2446j_previous_compute_m15_vwap_signal(headers)

    if not _v2446j_bool("V2446J_BTC_M5_ENABLED", True):
        signal["btc_m5_required"] = False
        return signal

    m15_bias = signal.get("bias")
    btc_m5_bias, btc_m5_vwap, btc_m5_timeframe = _v2446j_btc_m5_bias(headers)

    signal["btc_m5_required"] = True
    signal["btc_m5_timeframe"] = btc_m5_timeframe
    signal["btc_m5_bias"] = btc_m5_bias
    signal["btc_m5_vwap"] = btc_m5_vwap

    aligned = m15_bias in ("BUY", "SELL") and btc_m5_bias == m15_bias

    _v2446j_log(
        "RUNNER_V2446J_BTC_M5_FILTER",
        asset=ASSET,
        confirm_asset=CONFIRM_ASSET,
        m15_bias=m15_bias,
        btc_m5_bias=btc_m5_bias,
        aligned=aligned,
        btc_m5_timeframe=btc_m5_timeframe,
    )

    if not aligned:
        signal["m15_bias_before_btc_m5"] = m15_bias
        signal["bias"] = "WAIT"
        signal["reason"] = "BTC_M5_NOT_ALIGNED"
    else:
        signal["reason"] = str(signal.get("reason")) + "_BTC_M5_ALIGNED"

    return signal


_v2446j_log(
    "RUNNER_V2446J_BTC_M5_CONFIRM_ACTIVE",
    enabled=_v2446j_bool("V2446J_BTC_M5_ENABLED", True),
    confirm_asset=globals().get("CONFIRM_ASSET"),
    btc_m5_timeframe=_v2446j_os.getenv("V2446J_BTC_M5_TIMEFRAME", "MINUTE_5"),
)
# === V2446J_BTC_M5_CONFIRM_END ===




# === V2446K_PAIR_DIRECTOR_AUTHORITY_START ===
# Objectif :
# - ne pas inventer les paires directrices ;
# - utiliser l'asset directeur déjà configuré par CONFIRM_ASSET ;
# - empêcher les renforts contre le directeur ;
# - ne pas fermer automatiquement pour l'instant.

try:
    from BOT_PIVOT_00D_pair_director_authority import (
        assess_pair_director_authority as _v2446k_assess_authority,
    )
except Exception as _v2446k_import_exc:
    _v2446k_assess_authority = None
    globals()["_V2446K_IMPORT_ERROR"] = repr(_v2446k_import_exc)


def _v2446k_bool(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in ("0", "false", "no", "off", "non")


def _v2446k_asset():
    return str(globals().get("ASSET", os.getenv("V244_ASSET", "ETHUSD"))).upper()


def _v2446k_confirm_asset():
    return str(globals().get("CONFIRM_ASSET", os.getenv("V244_CONFIRM_ASSET", "BTCUSD"))).upper()


def _v2446k_log(event, **kw):
    # V2446K2 : log direct stdout.
    # On n'utilise pas le log() global ici, car il peut avaler silencieusement
    # les événements ajoutés tardivement par patch.
    try:
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        parts = [f"ts_utc={ts}", f"event={event}"]
        for k, v in kw.items():
            parts.append(f"{k}={v}")
        print(" | ".join(parts), flush=True)
    except Exception:
        pass


def _v2446k_get_arg(args, kwargs, name, index, default=None):
    if name in kwargs:
        return kwargs.get(name)
    if len(args) > index:
        return args[index]
    return default


def _v2446k_direction(pos):
    fn = globals().get("_v2446i_direction")
    if callable(fn):
        try:
            d = fn(pos)
            if d:
                return str(d).upper()
        except Exception:
            pass

    for k in ("direction", "side", "dealDirection"):
        v = pos.get(k) if isinstance(pos, dict) else None
        if v:
            return str(v).upper()

    p = pos.get("position", {}) if isinstance(pos, dict) else {}
    if isinstance(p, dict):
        for k in ("direction", "side", "dealDirection"):
            v = p.get(k)
            if v:
                return str(v).upper()

    return None


def _v2446k_positions(headers, asset):
    positions = []
    fn_pos = globals().get("asset_positions")
    if callable(fn_pos) and isinstance(headers, dict):
        try:
            positions = fn_pos(headers, asset) or []
        except Exception as exc:
            _v2446k_log(
                "RUNNER_V2446K_POSITION_READ_ERROR",
                asset=asset,
                exception=repr(exc),
            )
            positions = []

    # On réutilise le filtre déjà existant si présent.
    fn_filter = globals().get("_v2446i_eth_positions")
    if callable(fn_filter):
        try:
            positions = fn_filter(positions) or []
        except Exception:
            pass

    return positions


def _v2446k_net_side_from_positions(positions):
    fn_net = globals().get("net_exposure")
    fn_side = globals().get("net_side_from_exposure")

    if callable(fn_net) and callable(fn_side):
        try:
            net = fn_net(positions)
            side = str(fn_side(net)).upper()
            return net, side
        except Exception:
            pass

    sides = sorted(set(filter(None, [_v2446k_direction(p) for p in positions])))
    if len(sides) == 1 and sides[0] in ("BUY", "SELL"):
        return None, sides[0]

    return None, "FLAT"


def _v2446k_signal_value(signal, *keys, default="WAIT"):
    if not isinstance(signal, dict):
        return default
    for k in keys:
        v = signal.get(k)
        if v is not None:
            return v
    return default


_v2446k_previous_open_market_netting_safe = globals().get("open_market_netting_safe")


def open_market_netting_safe(*args, **kwargs):
    if not _v2446k_bool("V2446K_PAIR_DIRECTOR_AUTHORITY_ENABLED", True):
        if callable(_v2446k_previous_open_market_netting_safe):
            return _v2446k_previous_open_market_netting_safe(*args, **kwargs)
        return False, {"reason": "V2446K_DISABLED_NO_PREVIOUS_OPEN"}

    if not callable(_v2446k_previous_open_market_netting_safe):
        return False, {"reason": "V2446K_NO_PREVIOUS_OPEN_MARKET_NETTING_SAFE"}

    headers = _v2446k_get_arg(args, kwargs, "headers", 0, None)
    side = str(_v2446k_get_arg(args, kwargs, "side", 1, "")).upper()
    signal = _v2446k_get_arg(args, kwargs, "signal", 3, {}) or {}

    asset = _v2446k_asset()
    confirm_asset = _v2446k_confirm_asset()

    # Si le module d'autorité n'est pas disponible, on ne bloque pas L1,
    # mais on bloque les renforts par prudence seulement si des positions existent.
    positions = _v2446k_positions(headers, asset)
    open_count = len(positions)

    if open_count <= 0 or side not in ("BUY", "SELL"):
        return _v2446k_previous_open_market_netting_safe(*args, **kwargs)

    net, basket_side = _v2446k_net_side_from_positions(positions)

    if basket_side not in ("BUY", "SELL"):
        _v2446k_log(
            "RUNNER_V2446K_AUTHORITY_SKIPPED_NO_BASKET_SIDE",
            asset=asset,
            confirm_asset=confirm_asset,
            requested_side=side,
            open_positions=open_count,
            net_exposure=net,
            basket_side=basket_side,
        )
        return _v2446k_previous_open_market_netting_safe(*args, **kwargs)

    # V2446K2 :
    # Même si le runner demande un ordre opposé au panier existant,
    # on évalue l'autorité directionnelle pour tracer le conflit.
    # On ne laisse pas partir d'ordre opposé : la fermeture défensive sera codée à part.
    opposite_request_to_basket = side != basket_side

    if _v2446k_assess_authority is None:
        _v2446k_log(
            "RUNNER_REINFORCE_BLOCKED_BY_DIRECTOR",
            asset=asset,
            confirm_asset=confirm_asset,
            requested_side=side,
            basket_side=basket_side,
            open_positions=open_count,
            reason="AUTHORITY_MODULE_IMPORT_FAILED",
            import_error=globals().get("_V2446K_IMPORT_ERROR"),
        )
        return False, {
            "reason": "REINFORCE_BLOCKED_BY_DIRECTOR",
            "stage": "V2446K_AUTHORITY_IMPORT_FAILED",
            "import_error": globals().get("_V2446K_IMPORT_ERROR"),
            "open_positions": open_count,
            "basket_side": basket_side,
        }

    # Noms historiques :
    # - eth_bias = biais de l'actif tradé
    # - btc_bias = biais M15 de l'actif directeur déjà configuré
    # Même si CONFIRM_ASSET n'est pas BTC, on réutilise les champs existants.
    traded_structure = _v2446k_signal_value(
        signal,
        "asset_structure",
        "traded_structure",
        "eth_bias",
        "asset_bias",
        default="WAIT",
    )

    director_m15 = _v2446k_signal_value(
        signal,
        "director_m15",
        "confirm_m15_bias",
        "btc_bias",
        "confirm_bias",
        default="WAIT",
    )

    director_m5 = _v2446k_signal_value(
        signal,
        "director_m5",
        "confirm_m5_bias",
        "btc_m5_bias",
        default=director_m15,
    )

    try:
        decision = _v2446k_assess_authority(
            basket_side=basket_side,
            director_m15=director_m15,
            director_m5=director_m5,
            traded_structure=traded_structure,
            wanted_entry_side=None,
        )
    except Exception as exc:
        _v2446k_log(
            "RUNNER_REINFORCE_BLOCKED_BY_DIRECTOR",
            asset=asset,
            confirm_asset=confirm_asset,
            requested_side=side,
            basket_side=basket_side,
            open_positions=open_count,
            reason="AUTHORITY_ASSESS_EXCEPTION",
            exception=repr(exc),
        )
        return False, {
            "reason": "REINFORCE_BLOCKED_BY_DIRECTOR",
            "stage": "V2446K_AUTHORITY_ASSESS_EXCEPTION",
            "exception": repr(exc),
            "open_positions": open_count,
            "basket_side": basket_side,
        }

    _v2446k_log(
        "PAIR_DIRECTOR_AUTHORITY",
        asset=asset,
        confirm_asset=confirm_asset,
        requested_side=side,
        basket_side=decision.basket_side,
        state=decision.state,
        director_m15=decision.director_m15,
        director_m5=decision.director_m5,
        traded_structure=decision.traded_structure,
        allow_reinforce=decision.allow_reinforce,
        should_close_defensive=decision.should_close_defensive,
        open_positions=open_count,
        net_exposure=net,
        reason=decision.reason,
    )

    if opposite_request_to_basket:
        _v2446k_log(
            "RUNNER_OPEN_BLOCKED_EXISTING_BASKET_SIDE_BY_DIRECTOR",
            asset=asset,
            confirm_asset=confirm_asset,
            requested_side=side,
            basket_side=decision.basket_side,
            authority_state=decision.state,
            director_m15=decision.director_m15,
            director_m5=decision.director_m5,
            traded_structure=decision.traded_structure,
            open_positions=open_count,
            should_close_defensive=decision.should_close_defensive,
            reason=decision.reason,
        )
        return False, {
            "reason": "OPEN_BLOCKED_EXISTING_BASKET_SIDE_BY_DIRECTOR",
            "authority_state": decision.state,
            "authority_reason": decision.reason,
            "requested_side": side,
            "basket_side": decision.basket_side,
            "director_m15": decision.director_m15,
            "director_m5": decision.director_m5,
            "traded_structure": decision.traded_structure,
            "should_close_defensive": decision.should_close_defensive,
            "open_positions": open_count,
            "confirm_asset": confirm_asset,
        }

    if not decision.allow_reinforce:
        _v2446k_log(
            "RUNNER_REINFORCE_BLOCKED_BY_DIRECTOR",
            asset=asset,
            confirm_asset=confirm_asset,
            requested_side=side,
            basket_side=decision.basket_side,
            authority_state=decision.state,
            director_m15=decision.director_m15,
            director_m5=decision.director_m5,
            traded_structure=decision.traded_structure,
            open_positions=open_count,
            should_close_defensive=decision.should_close_defensive,
            reason=decision.reason,
        )
        return False, {
            "reason": "REINFORCE_BLOCKED_BY_DIRECTOR",
            "authority_state": decision.state,
            "authority_reason": decision.reason,
            "director_m15": decision.director_m15,
            "director_m5": decision.director_m5,
            "traded_structure": decision.traded_structure,
            "should_close_defensive": decision.should_close_defensive,
            "open_positions": open_count,
            "basket_side": decision.basket_side,
            "confirm_asset": confirm_asset,
        }

    return _v2446k_previous_open_market_netting_safe(*args, **kwargs)


_v2446k_log(
    "RUNNER_V2446K2_LOG_FIX_ACTIVE",
    enabled=_v2446k_bool("V2446K_PAIR_DIRECTOR_AUTHORITY_ENABLED", True),
    asset=globals().get("ASSET"),
    confirm_asset=globals().get("CONFIRM_ASSET"),
)

_v2446k_log(
    "RUNNER_V2446K_PAIR_DIRECTOR_AUTHORITY_ACTIVE",
    enabled=_v2446k_bool("V2446K_PAIR_DIRECTOR_AUTHORITY_ENABLED", True),
    asset=globals().get("ASSET"),
    confirm_asset=globals().get("CONFIRM_ASSET"),
)
# === V2446K_PAIR_DIRECTOR_AUTHORITY_END ===


if __name__ == "__main__":
    main()
