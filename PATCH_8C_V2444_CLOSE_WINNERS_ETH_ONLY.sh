#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

RUNNER="BOT_PIVOT_24_4_forced_audit_runner.py"
TS=$(date +"%Y%m%d_%H%M%S")
cp -f "$RUNNER" "$RUNNER.before_v2444_8C_$TS"

python3 <<'PY'
from pathlib import Path

p = Path("BOT_PIVOT_24_4_forced_audit_runner.py")
s = p.read_text(encoding="utf-8")

if "NO_LOSS_CLOSE_HARD_GUARD" not in s:
    raise RuntimeError("Applique PATCH 8A avant PATCH 8C")

if "from datetime import datetime, timezone" not in s:
    s = s.replace("import traceback\n", "import traceback\nfrom datetime import datetime, timezone\n", 1)

if "CLOSE_WINNERS_ENABLED" not in s:
    anchor = 'REQUIRE_ACCOUNT_NETTING = os.getenv("V244_REQUIRE_ACCOUNT_NETTING", "1") == "1"\n'
    s = s.replace(anchor, anchor + '''
CLOSE_WINNERS_ENABLED = os.getenv("V244_CLOSE_WINNERS_ENABLED", "0") == "1"
WIN_BASKET_TP_EUR = float(os.getenv("V244_WIN_BASKET_TP_EUR", "1.00"))
WIN_MIN_POSITION_UPL = float(os.getenv("V244_WIN_MIN_POSITION_UPL", "0.05"))
WIN_MIN_AGE_SEC = float(os.getenv("V244_WIN_MIN_AGE_SEC", "60"))
WIN_REQUIRE_TOTAL_ETH_UPL_POSITIVE = os.getenv("V244_WIN_REQUIRE_TOTAL_ETH_UPL_POSITIVE", "1") == "1"
WIN_MAX_CLOSES_PER_LOOP = int(os.getenv("V244_WIN_MAX_CLOSES_PER_LOOP", "5"))
CLOSE_THEN_WAIT_SEC = float(os.getenv("V244_CLOSE_THEN_WAIT_SEC", "10"))

''', 1)

if '"createdDateUTC":' not in s:
    s = s.replace(
'''        "guaranteedStop": bool(pos.get("guaranteedStop") or item.get("guaranteedStop")),
        "raw": item,
''',
'''        "guaranteedStop": bool(pos.get("guaranteedStop") or item.get("guaranteedStop")),
        "createdDateUTC": pos.get("createdDateUTC") or item.get("createdDateUTC"),
        "createdDate": pos.get("createdDate") or item.get("createdDate"),
        "raw": item,
''',
        1
    )

block = r'''

# ======================================================================
# CLOSE ETH WINNERS ONLY
# ======================================================================

def _winner_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _winner_age_sec(position: Dict[str, Any]) -> Optional[float]:
    raw = position.get("raw", {}) if isinstance(position.get("raw"), dict) else {}
    raw_pos = raw.get("position", {}) if isinstance(raw.get("position"), dict) else {}
    ts = position.get("createdDateUTC") or raw_pos.get("createdDateUTC")

    if not ts:
        return None

    text = str(ts).replace("Z", "")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return max(0.0, time.time() - datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            pass

    return None


def _eth_total_upl(positions: List[Dict[str, Any]]) -> float:
    return sum(_winner_float(p.get("upl")) for p in positions if str(p.get("epic") or "").upper() == ASSET)


def close_winning_basket_if_needed(
    headers: Dict[str, str],
    positions: List[Dict[str, Any]],
    signal: Dict[str, Any],
) -> Tuple[int, Dict[str, Any]]:
    if not CLOSE_WINNERS_ENABLED:
        return 0, {"stage": "CLOSE_WINNERS_DISABLED"}

    total_eth_upl = _eth_total_upl(positions)

    candidates = []
    for pos in positions:
        epic = str(pos.get("epic") or "").upper()
        deal_id = pos.get("dealId")
        upl = _winner_float(pos.get("upl"))
        age = _winner_age_sec(pos)

        if epic in PROTECTED_ASSETS:
            log("RUNNER_WINNER_CLOSE_SKIP_PROTECTED", asset=ASSET, protected_epic=epic, dealId=deal_id)
            continue

        if epic != ASSET or not deal_id:
            continue

        if upl <= 0:
            continue

        if upl < WIN_MIN_POSITION_UPL:
            continue

        if WIN_MIN_AGE_SEC > 0 and (age is None or age < WIN_MIN_AGE_SEC):
            log("RUNNER_WINNER_CLOSE_SKIP_TOO_YOUNG", asset=ASSET, dealId=deal_id, upl=upl, age_sec=age)
            continue

        item = dict(pos)
        item["age_sec"] = age
        candidates.append(item)

    candidates.sort(key=lambda p: _winner_float(p.get("upl")), reverse=True)

    total_win_upl = sum(_winner_float(p.get("upl")) for p in candidates)
    total_eth_ok = total_eth_upl > 0 or not WIN_REQUIRE_TOTAL_ETH_UPL_POSITIVE
    should_close = bool(candidates and total_win_upl >= WIN_BASKET_TP_EUR and total_eth_ok)

    decision = {
        "should_close": should_close,
        "candidate_count": len(candidates),
        "candidate_dealIds": [p.get("dealId") for p in candidates],
        "total_winning_upl": total_win_upl,
        "total_eth_upl": total_eth_upl,
        "total_eth_ok": total_eth_ok,
        "win_basket_tp_eur": WIN_BASKET_TP_EUR,
        "win_min_position_upl": WIN_MIN_POSITION_UPL,
        "win_min_age_sec": WIN_MIN_AGE_SEC,
        "signal_bias": signal.get("bias"),
    }

    log("RUNNER_WINNING_BASKET_DECISION", asset=ASSET, **decision)

    if not should_close:
        return 0, {"stage": "NO_WINNING_BASKET_TO_CLOSE", "decision": decision}

    closed = 0
    results = []

    for pos in candidates[: max(1, WIN_MAX_CLOSES_PER_LOOP)]:
        deal_id = pos.get("dealId")
        upl = _winner_float(pos.get("upl"))

        if upl <= 0:
            log("RUNNER_WINNER_CLOSE_REFUSED_NOT_PROFITABLE", asset=ASSET, dealId=deal_id, upl=upl)
            continue

        log("RUNNER_WINNER_CLOSE_REQUEST", asset=ASSET, dealId=deal_id, upl=upl, size=pos.get("size"), direction=pos.get("direction"))

        status, data = api_delete(headers, f"/positions/{deal_id}")

        log("RUNNER_WINNER_CLOSE_RESPONSE", asset=ASSET, dealId=deal_id, status=status, response=data)

        result = {
            "dealId": deal_id,
            "upl": upl,
            "status": status,
            "response": data,
        }

        if status == 200 and isinstance(data, dict) and data.get("dealReference"):
            confirm_ok, confirm = confirm_reference(headers, data.get("dealReference"))
            after_positions = asset_positions(headers, ASSET)
            still_visible = str(deal_id) in position_ids(after_positions)
            ok = confirm_ok and not still_visible
            result.update({"confirm_ok": confirm_ok, "confirm": confirm, "still_visible": still_visible, "ok": ok})
            if ok:
                closed += 1
        else:
            result["ok"] = False

        log("RUNNER_WINNER_CLOSE_RESULT", asset=ASSET, ok=result.get("ok"), info=result)
        results.append(result)

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

if "def close_winning_basket_if_needed(" not in s:
    marker = "\n# ======================================================================\n# RATE LIMITER"
    if marker not in s:
        marker = "\n# ======================================================================\n# NO DIRECT LOSS CLOSE SAFETY"
    s = s.replace(marker, block + marker, 1)

main_part = s.split("def main()", 1)[1]
if "close_winning_basket_if_needed(headers, positions, signal)" not in main_part:
    s = s.replace(
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
                log("RUNNER_LOOP_PAUSE_AFTER_WINNER_CLOSE", asset=ASSET, closed_count=closed_count, close_info=close_info, wait_sec=CLOSE_THEN_WAIT_SEC)
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
        1
    )

if "close_winners_enabled=CLOSE_WINNERS_ENABLED" not in s:
    s = s.replace(
'''        allow_opposite_netting=ALLOW_OPPOSITE_NETTING,
''',
'''        allow_opposite_netting=ALLOW_OPPOSITE_NETTING,
        close_winners_enabled=CLOSE_WINNERS_ENABLED,
        win_basket_tp_eur=WIN_BASKET_TP_EUR,
        win_min_position_upl=WIN_MIN_POSITION_UPL,
        win_min_age_sec=WIN_MIN_AGE_SEC,
''',
        1
    )

p.write_text(s, encoding="utf-8")
PY

python3 -m py_compile "$RUNNER"
grep -nE "CLOSE_WINNERS_ENABLED|RUNNER_WINNING_BASKET_DECISION|RUNNER_WINNER_CLOSE_REQUEST|RUNNER_WINNER_CLOSE_RESULT|close_winning_basket_if_needed" "$RUNNER" | head -120
echo "PATCH 8C OK"
