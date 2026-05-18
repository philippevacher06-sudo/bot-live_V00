#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

echo "============================================================"
echo "PATCH 7 - V24.4.3 CLOSE WINNERS ETH ONLY"
echo "============================================================"

TS=$(date +"%Y%m%d_%H%M%S")
RUNNER="BOT_PIVOT_24_4_forced_audit_runner.py"

cp -f "$RUNNER" "$RUNNER.before_v2443_close_winners_$TS"

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


if "from datetime import datetime, timezone" not in src:
    src = replace_once(src, "import traceback\n", "import traceback\nfrom datetime import datetime, timezone\n")


config_anchor = 'REQUIRE_ACCOUNT_NETTING = os.getenv("V244_REQUIRE_ACCOUNT_NETTING", "1") == "1"\n'
config_insert = '''

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
'''

if "CLOSE_WINNERS_ENABLED" not in src:
    src = replace_once(src, config_anchor, config_anchor + config_insert)


if '"createdDateUTC":' not in src:
    src = replace_once(
        src,
        '''        "guaranteedStop": bool(pos.get("guaranteedStop") or item.get("guaranteedStop")),
        "raw": item,
''',
        '''        "guaranteedStop": bool(pos.get("guaranteedStop") or item.get("guaranteedStop")),
        "createdDateUTC": pos.get("createdDateUTC") or item.get("createdDateUTC"),
        "createdDate": pos.get("createdDate") or item.get("createdDate"),
        "raw": item,
''',
    )


api_delete_body = '''
def api_delete(headers: Dict[str, str], path: str) -> Tuple[int, Any]:
    url = BASE + path
    blocked = _demo_guard(url)
    if blocked:
        return 0, blocked

    try:
        r = requests.delete(url, headers=ensure_headers(headers), timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"text": r.text}
        return int(r.status_code), data
    except Exception as e:
        return 0, {
            "REQUEST_EXCEPTION": True,
            "method": "DELETE",
            "path": path,
            "exception": repr(e),
        }
'''

if "def api_delete(" not in src:
    marker = "\n\n# ======================================================================\n# ACCOUNT / EXECUTION GUARDS"
    if marker not in src:
        marker = "\n\n# ======================================================================\n# POSITIONS / NETTING / MARGE"
    src = replace_once(src, marker, "\n\n" + api_delete_body.rstrip() + marker)


close_winners_block = r'''

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
'''

if "def close_winning_basket_if_needed(" not in src:
    marker = "\n# ======================================================================\n# NO DIRECT LOSS CLOSE SAFETY"
    src = replace_once(src, marker, close_winners_block + marker)


if "close_winners_enabled=CLOSE_WINNERS_ENABLED" not in src:
    src = replace_once(
        src,
        '''        allow_direct_loss_close=ALLOW_DIRECT_LOSS_CLOSE,
        allow_opposite_netting=ALLOW_OPPOSITE_NETTING,
''',
        '''        allow_direct_loss_close=ALLOW_DIRECT_LOSS_CLOSE,
        allow_opposite_netting=ALLOW_OPPOSITE_NETTING,
        close_winners_enabled=CLOSE_WINNERS_ENABLED,
        win_basket_tp_eur=WIN_BASKET_TP_EUR,
        win_min_position_upl=WIN_MIN_POSITION_UPL,
        win_basket_margin_pct=WIN_BASKET_MARGIN_PCT,
        win_min_age_sec=WIN_MIN_AGE_SEC,
        win_close_on_wait=WIN_CLOSE_ON_WAIT,
        win_close_on_signal_reversal=WIN_CLOSE_ON_SIGNAL_REVERSAL,
''',
    )


if "close_winning_basket_if_needed(" not in src.split("def main()", 1)[1]:
    src = replace_once(
        src,
        '''            if bias not in ("BUY", "SELL"):
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="NO_M15_VWAP_BTC_SIGNAL",
                    signal=signal,
                )
                time.sleep(SLEEP_SEC)
                continue
''',
        '''            closed_count, close_info = close_winning_basket_if_needed(headers, positions, signal)
            if closed_count > 0:
                log(
                    "RUNNER_LOOP_PAUSE_AFTER_WINNER_CLOSE",
                    asset=ASSET,
                    closed_count=closed_count,
                    close_info=close_info,
                    wait_sec=CLOSE_THEN_WAIT_SEC,
                )
                time.sleep(CLOSE_THEN_WAIT_SEC)
                continue

            if bias not in ("BUY", "SELL"):
                log(
                    "RUNNER_OPEN_BLOCKED",
                    asset=ASSET,
                    reason="NO_M15_VWAP_BTC_SIGNAL",
                    signal=signal,
                )
                time.sleep(SLEEP_SEC)
                continue
''',
    )


path.write_text(src, encoding="utf-8")
PY

echo "============================================================"
echo "COMPILATION"
echo "============================================================"
python3 -m py_compile "$RUNNER"

echo "============================================================"
echo "CONTROLES PATCH 7"
echo "============================================================"
grep -nE "CLOSE_WINNERS_ENABLED|RUNNER_WINNING_BASKET_DECISION|RUNNER_WINNER_CLOSE_REQUEST|RUNNER_WINNER_CLOSE_RESULT|RUNNER_WINNING_BASKET_CLOSE_SUMMARY|api_delete|DELETE_POSITION_FAILED" "$RUNNER" | head -260 || true

echo "PATCH 7 OK"

