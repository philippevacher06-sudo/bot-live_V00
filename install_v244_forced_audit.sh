#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

printf '\n============================================================\n'
printf 'V24.4 FORCED AUDIT — INSTALLATION COMPLETE\n'
printf '============================================================\n'

printf '\n[1/8] STOP DES ANCIENNES INSTANCES\n'
tmux kill-session -t botpivot_v244_pair_clean 2>/dev/null || true
tmux kill-session -t botpivot_v244_clean 2>/dev/null || true
tmux kill-session -t botpivot_v244_pair 2>/dev/null || true
tmux kill-session -t botpivot_v244_audit 2>/dev/null || true
tmux kill-session -t v244_forced_runner 2>/dev/null || true

pkill -f "run_BOT_PIVOT" 2>/dev/null || true
pkill -f "BOT_PIVOT_03_tick_stream" 2>/dev/null || true
pkill -f "BOT_PIVOT_06H_execution_demo_guarded" 2>/dev/null || true
pkill -f "BOT_PIVOT_24_4_forced_audit_runner" 2>/dev/null || true
sleep 2

printf '\nProcessus BOT restants éventuels :\n'
ps aux | grep -E "BOT_PIVOT|run_BOT_PIVOT|tick_stream|forced_audit_runner" | grep -v grep || true

printf '\n[2/8] BACKUP\n'
TS=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="backups/BEFORE_V244_FULL_FORCED_AUDIT_${TS}"
mkdir -p "$BACKUP_DIR"
cp -f BOT_PIVOT_06G2_execution_secure.py "$BACKUP_DIR/" 2>/dev/null || true
cp -f BOT_PIVOT_24_4_forced_audit_sampling.py "$BACKUP_DIR/" 2>/dev/null || true
cp -f BOT_PIVOT_24_4_forced_audit_runner.py "$BACKUP_DIR/" 2>/dev/null || true
cp -f run_BOT_PIVOT_07D_SCALP_ACTIVE.sh "$BACKUP_DIR/" 2>/dev/null || true
echo "BACKUP=$BACKUP_DIR"

printf '\n[3/8] CREATION MODULE BOT_PIVOT_24_4_forced_audit_sampling.py\n'
cat > BOT_PIVOT_24_4_forced_audit_sampling.py <<'PY'
# BOT_PIVOT_24_4_forced_audit_sampling.py
# V24.4 — audit expérimental forcé ETHUSD
# Objectif : information / audit, pas performance.

from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

FORCED_AUDIT_ENABLED = os.getenv("V244_FORCED_AUDIT_ENABLED", "1") == "1"
DEMO_ONLY_LOCK = os.getenv("V244_DEMO_ONLY_LOCK", "1") == "1"

TRADED_ASSET = os.getenv("V244_TRADED_ASSET", "ETHUSD").upper()
CONFIRM_ASSET = os.getenv("V244_CONFIRM_ASSET", "BTCUSD").upper()

TARGET_OPENINGS_PER_MIN = int(os.getenv("V244_TARGET_OPENINGS_PER_MIN", "2"))
CLOSE_PAIR_RATIO_MIN = float(os.getenv("V244_CLOSE_PAIR_RATIO_MIN", "1.67"))

MARGIN_MAX_EUR = float(os.getenv("V244_MARGIN_MAX_EUR", "3000"))
MARGIN_SOFT_EUR = float(os.getenv("V244_MARGIN_SOFT_EUR", "2600"))

EXCLUDED_ASSETS = {
    x.strip().upper()
    for x in os.getenv("V244_EXCLUDED_ASSETS", "GOLD").split(",")
    if x.strip()
}

AUDIT_DIR = Path(os.getenv("V244_AUDIT_DIR", "logs/v24_4_forced_audit"))
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = Path(os.getenv("V244_STATE_FILE", "data/execution/v24_4_forced_audit_state.json"))
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

SIZE_SEQUENCE = [
    float(x.strip())
    for x in os.getenv("V244_SIZE_SEQUENCE", "0.06,0.10,0.12,0.18").split(",")
    if x.strip()
]

SIDE_MODE = os.getenv("V244_SIDE_MODE", "ALTERNATE").upper()


def now_ts() -> float:
    return time.time()


def audit_log(event: str, **kw: Any) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day = time.strftime("%Y%m%d", time.gmtime())
    payload = {"ts_utc": ts, "event": event}
    payload.update(kw)
    line = " | ".join(f"{k}={v}" for k, v in payload.items())
    p = AUDIT_DIR / f"V24_4_FORCED_AUDIT_{day}.log"
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {"opens": [], "seq": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"opens": [], "seq": 0}


def save_state(st: Dict[str, Any]) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def is_excluded_asset(asset: str) -> bool:
    return str(asset or "").upper() in EXCLUDED_ASSETS


def safety_banner() -> None:
    audit_log(
        "SAFETY_LOCK",
        mode="DEMO_ONLY" if DEMO_ONLY_LOCK else "UNLOCKED",
        forced_audit_enabled=FORCED_AUDIT_ENABLED,
        traded_asset=TRADED_ASSET,
        confirm_asset=CONFIRM_ASSET,
        target_openings_per_min=TARGET_OPENINGS_PER_MIN,
        close_pair_ratio_min=CLOSE_PAIR_RATIO_MIN,
        margin_max=MARGIN_MAX_EUR,
        margin_soft=MARGIN_SOFT_EUR,
        excluded_assets=",".join(sorted(EXCLUDED_ASSETS)) if EXCLUDED_ASSETS else "--",
        size_sequence=",".join(str(x) for x in SIZE_SEQUENCE),
    )


def count_opens_last_60s() -> int:
    st = load_state()
    t = now_ts()
    return sum(1 for o in st.get("opens", []) if t - float(o.get("ts", 0)) <= 60)


def register_open(asset: str, side: str, size: float, reason: str, extra: Optional[Dict[str, Any]] = None) -> None:
    asset = str(asset or "").upper()
    if is_excluded_asset(asset):
        audit_log("AUDIT_OPEN_IGNORED", asset=asset, reason="EXCLUDED_ASSET")
        return

    st = load_state()
    t = now_ts()
    opens = st.setdefault("opens", [])
    opens.append({
        "ts": t,
        "asset": asset,
        "side": side,
        "size": float(size),
        "reason": reason,
        "extra": extra or {},
    })
    st["opens"] = [o for o in opens if t - float(o.get("ts", 0)) <= 600]
    save_state(st)

    audit_log(
        "AUDIT_OPEN_REGISTER",
        asset=asset,
        side=side,
        size=size,
        reason=reason,
        openings_last_60s=count_opens_last_60s(),
    )


def next_forced_order() -> Tuple[str, float, int]:
    st = load_state()
    seq = int(st.get("seq", 0) or 0)

    if SIDE_MODE == "BUY_ONLY":
        side = "BUY"
    elif SIDE_MODE == "SELL_ONLY":
        side = "SELL"
    else:
        side = "BUY" if seq % 2 == 0 else "SELL"

    size = SIZE_SEQUENCE[seq % len(SIZE_SEQUENCE)] if SIZE_SEQUENCE else 0.06

    st["seq"] = seq + 1
    save_state(st)

    return side, float(size), seq


def missing_openings() -> int:
    return max(0, TARGET_OPENINGS_PER_MIN - count_opens_last_60s())


def _nested_position(rec: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(rec.get("position"), dict):
        return rec["position"]
    return rec


def rec_asset(rec: Dict[str, Any]) -> str:
    pos = _nested_position(rec)
    for k in ("asset", "epic", "market", "symbol"):
        if rec.get(k):
            return str(rec.get(k)).upper()
        if pos.get(k):
            return str(pos.get(k)).upper()
    return ""


def rec_id(rec: Dict[str, Any]) -> str:
    pos = _nested_position(rec)
    for k in ("brokerDealId", "dealId", "deal_id", "id", "ref"):
        if rec.get(k):
            return str(rec.get(k))
        if pos.get(k):
            return str(pos.get(k))
    return "UNKNOWN"


def rec_size(rec: Dict[str, Any]) -> float:
    pos = _nested_position(rec)
    for k in ("size", "deal_size", "quantity", "qty"):
        try:
            if rec.get(k) is not None:
                return abs(float(rec.get(k)))
        except Exception:
            pass
        try:
            if pos.get(k) is not None:
                return abs(float(pos.get(k)))
        except Exception:
            pass
    return 0.0


def rec_upl(rec: Dict[str, Any]) -> float:
    pos = _nested_position(rec)
    for k in ("broker_upl", "upl", "profit", "pnl", "internal_pnl", "pnl_eur"):
        try:
            if rec.get(k) is not None:
                return float(rec.get(k))
        except Exception:
            pass
        try:
            if pos.get(k) is not None:
                return float(pos.get(k))
        except Exception:
            pass
    return 0.0


def select_close_pair_from_records(asset: str, records: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    asset = str(asset or "").upper()

    if not FORCED_AUDIT_ENABLED:
        return None

    if is_excluded_asset(asset):
        audit_log("AUDIT_CLOSE_PAIR_SKIP", asset=asset, reason="EXCLUDED_ASSET")
        return None

    clean = []
    for r in records or []:
        rr = dict(r)
        rr["_id"] = rec_id(rr)
        rr["_asset"] = rec_asset(rr) or asset
        rr["_size"] = rec_size(rr)
        rr["_upl"] = rec_upl(rr)

        if rr["_asset"] != asset:
            continue
        if rr["_id"] == "UNKNOWN":
            continue
        if rr["_size"] <= 0:
            continue

        clean.append(rr)

    if len(clean) < 2:
        audit_log("AUDIT_CLOSE_PAIR_NONE", asset=asset, reason="NOT_ENOUGH_RECORDS", count=len(clean))
        return None

    best = None
    best_ratio = 0.0

    for weak in clean:
        for strong in clean:
            if weak["_id"] == strong["_id"]:
                continue

            weak_size = weak["_size"]
            strong_size = strong["_size"]
            ratio = strong_size / weak_size if weak_size else 0.0

            if ratio >= CLOSE_PAIR_RATIO_MIN and ratio > best_ratio:
                best_ratio = ratio
                best = (weak, strong)

    if not best:
        audit_log(
            "AUDIT_CLOSE_PAIR_NONE",
            asset=asset,
            reason="NO_VALID_WEAK_STRONG_RATIO",
            ratio_min=CLOSE_PAIR_RATIO_MIN,
            records=len(clean),
            sizes=",".join(str(x["_size"]) for x in clean),
        )
        return None

    weak, strong = best

    audit_log(
        "AUDIT_CLOSE_PAIR_SELECT",
        asset=asset,
        weak_id=weak["_id"],
        weak_size=weak["_size"],
        weak_upl=weak["_upl"],
        strong_id=strong["_id"],
        strong_size=strong["_size"],
        strong_upl=strong["_upl"],
        ratio=round(best_ratio, 3),
        pair_upl=round(weak["_upl"] + strong["_upl"], 4),
        reason="VALID_WEAK_STRONG_PAIR",
    )

    return weak, strong


def register_close_pair(asset: str, weak: Dict[str, Any], strong: Dict[str, Any], reason: str) -> None:
    weak_size = rec_size(weak)
    strong_size = rec_size(strong)
    ratio = strong_size / weak_size if weak_size else 0.0

    audit_log(
        "AUDIT_CLOSE_PAIR_EXECUTE",
        asset=asset,
        weak_id=rec_id(weak),
        weak_size=weak_size,
        weak_upl=rec_upl(weak),
        strong_id=rec_id(strong),
        strong_size=strong_size,
        strong_upl=rec_upl(strong),
        ratio=round(ratio, 3),
        pair_upl=round(rec_upl(weak) + rec_upl(strong), 4),
        reason=reason,
    )


if __name__ == "__main__":
    safety_banner()
    print("V24.4 forced audit module OK")
PY

python3 -m py_compile BOT_PIVOT_24_4_forced_audit_sampling.py
python3 BOT_PIVOT_24_4_forced_audit_sampling.py

printf '\n[4/8] PATCH 06G2 : IMPORT + BLOCAGE ANCIENS LIMIT + FERMETURE PAIRE\n'
python3 - <<'PY'
from pathlib import Path

p = Path("BOT_PIVOT_06G2_execution_secure.py")
s = p.read_text(encoding="utf-8")

import_block = r'''
# V24.4 — audit expérimental ETHUSD
try:
    import BOT_PIVOT_24_4_forced_audit_sampling as FAS244
    FAS244.safety_banner()
except Exception as e:
    FAS244 = None
    print(f"V24.4_FORCED_AUDIT_IMPORT_FAIL | {e}")

'''

if "import BOT_PIVOT_24_4_forced_audit_sampling as FAS244" not in s:
    marker = "def pos_deal_id"
    idx = s.find(marker)
    if idx == -1:
        raise SystemExit("ERREUR : def pos_deal_id introuvable")
    s = s[:idx] + import_block + s[idx:]

target = "def v24_open_basket_limits_secure(headers, asset, cycle, market_status):"
idx = s.find(target)
if idx == -1:
    raise SystemExit("ERREUR : v24_open_basket_limits_secure introuvable")
line_end = s.find("\n", idx)
insert_at = line_end + 1

block_open_patch = r'''
    # V24.4 — blocage total de l'ancienne ouverture basket LIMIT L1/L2/L3
    try:
        import os
        if os.getenv("V244_DISABLE_CLASSIC_BASKET_OPEN", "1") == "1":
            try:
                event({
                    "event": "V244_CLASSIC_BASKET_OPEN_BLOCKED",
                    "asset": asset,
                    "reason": "EXPERIMENTAL_MODE_NO_CLASSIC_L1_L2_L3",
                    "cycle_direction": cycle.get("direction") if isinstance(cycle, dict) else None,
                    "cycle_level": cycle.get("level") if isinstance(cycle, dict) else None,
                })
            except Exception:
                pass

            print(f"{asset:10s} | V244_BLOCK_OPEN | ancien panier LIMIT L1/L2/L3 bloqué")

            try:
                status_pos, positions_now, _ = fetch_positions(headers)
            except Exception:
                positions_now = []

            return False, {
                "reason": "V244_CLASSIC_BASKET_OPEN_DISABLED",
                "asset": asset,
                "mode": "V24.4_FORCED_AUDIT_RUNNER_ONLY"
            }, positions_now
    except Exception as e:
        try:
            event({
                "event": "V244_CLASSIC_BASKET_BLOCK_EXCEPTION",
                "asset": asset,
                "exception": str(e),
            })
        except Exception:
            pass

'''

if "V244_CLASSIC_BASKET_OPEN_BLOCKED" not in s:
    s = s[:insert_at] + block_open_patch + s[insert_at:]

target = "def v24_close_basket_secure(headers, asset, basket_exec, reason):"
idx = s.find(target)
if idx == -1:
    raise SystemExit("ERREUR : v24_close_basket_secure introuvable")
line_end = s.find("\n", idx)
insert_at = line_end + 1

pair_close_patch = r'''
    # V24.4 — fermeture expérimentale par paire faible/forte
    try:
        if FAS244 is not None and getattr(FAS244, "FORCED_AUDIT_ENABLED", False):
            records = []

            if isinstance(basket_exec, dict):
                for key in ("records", "legs", "positions", "open", "items"):
                    val = basket_exec.get(key)
                    if isinstance(val, list):
                        records = val
                        break

                if not records:
                    for key in ("L1", "L2", "L3", "l1", "l2", "l3"):
                        val = basket_exec.get(key)
                        if isinstance(val, dict):
                            records.append(val)

            pair = FAS244.select_close_pair_from_records(asset, records)

            if pair:
                weak, strong = pair
                pair_records = [weak, strong]

                event({
                    "event": "V244_CLOSE_PAIR_MODE",
                    "asset": asset,
                    "reason": reason,
                    "weak_id": weak.get("brokerDealId") or weak.get("dealId"),
                    "strong_id": strong.get("brokerDealId") or strong.get("dealId"),
                    "weak_size": weak.get("size"),
                    "strong_size": strong.get("size"),
                })

                ok_all = True
                info = {
                    "event": "V244_CLOSE_PAIR_RESULT",
                    "asset": asset,
                    "reason": reason,
                    "closed": [],
                }
                last_positions_after = None

                for rec in pair_records:
                    deal_id = rec.get("brokerDealId") or rec.get("dealId")
                    if not deal_id:
                        ok_all = False
                        info["closed"].append({
                            "ok": False,
                            "reason": "MISSING_DEAL_ID",
                            "rec": rec,
                        })
                        continue

                    ok, close_info, positions_after = close_deal_secure(
                        headers=headers,
                        asset=asset,
                        deal_id=deal_id,
                        reason=f"V244_PAIR_CLOSE_{reason}",
                        old_exec=rec,
                    )

                    info["closed"].append({
                        "ok": ok,
                        "deal_id": deal_id,
                        "close_info": close_info,
                    })

                    if positions_after is not None:
                        last_positions_after = positions_after

                    if not ok:
                        ok_all = False

                FAS244.register_close_pair(asset, weak, strong, reason=reason)
                event(info)
                return ok_all, info, last_positions_after
    except Exception as e:
        try:
            event({
                "event": "V244_CLOSE_PAIR_EXCEPTION",
                "asset": asset,
                "reason": reason,
                "exception": str(e),
            })
        except Exception:
            pass

'''

if "V244_CLOSE_PAIR_MODE" not in s:
    s = s[:insert_at] + pair_close_patch + s[insert_at:]

p.write_text(s, encoding="utf-8")
print("Patch 06G2 OK")
PY

python3 -m py_compile BOT_PIVOT_06G2_execution_secure.py

printf '\n[5/8] CREATION RUNNER EXPERIMENTAL DEDIE\n'
cat > BOT_PIVOT_24_4_forced_audit_runner.py <<'PY'
# BOT_PIVOT_24_4_forced_audit_runner.py
# Runner expérimental séparé.
# Ne lance pas les anciens paniers LIMIT.
# Ouvre ETHUSD via open_cycle_secure pour produire 2 ouvertures/minute.
# Ferme par paire faible/forte si une paire valide existe.

from __future__ import annotations

import os
import time
import uuid
import traceback

import BOT_PIVOT_06G2_execution_secure as G
import BOT_PIVOT_24_4_forced_audit_sampling as FAS

ASSET = os.getenv("V244_TRADED_ASSET", "ETHUSD").upper()
SLEEP_SEC = float(os.getenv("V244_RUNNER_SLEEP_SEC", "20"))
TARGET_OPENINGS_PER_MIN = int(os.getenv("V244_TARGET_OPENINGS_PER_MIN", "2"))
MAX_POSITIONS = int(os.getenv("V244_MAX_OPEN_POSITIONS", "12"))


def log(event, **kw):
    FAS.audit_log(event, **kw)


def broker_positions(headers):
    status, positions, raw = G.fetch_positions(headers)
    return positions or []


def positions_for_asset(asset, positions):
    return [p for p in positions or [] if G.pos_epic(p) == asset]


def normalize_broker_item(item):
    pos = item.get("position", {}) if isinstance(item, dict) else {}
    deal_id = G.pos_deal_id(item)
    size = pos.get("size") or item.get("size") or pos.get("dealSize") or item.get("dealSize")
    upl = pos.get("upl") or pos.get("profit") or item.get("upl") or item.get("profit") or 0.0

    return {
        "asset": ASSET,
        "dealId": deal_id,
        "brokerDealId": deal_id,
        "size": size,
        "broker_upl": upl,
        "raw": item,
    }


def close_pair_if_available(headers, positions):
    items = positions_for_asset(ASSET, positions)
    records = [normalize_broker_item(x) for x in items]
    pair = FAS.select_close_pair_from_records(ASSET, records)

    if not pair:
        return positions

    weak, strong = pair
    closed = []

    for rec in (weak, strong):
        deal_id = rec.get("brokerDealId") or rec.get("dealId")
        if not deal_id:
            closed.append({"deal_id": None, "ok": False, "reason": "MISSING_DEAL_ID"})
            continue

        ok, info, positions_after = G.close_deal_secure(
            headers=headers,
            asset=ASSET,
            deal_id=deal_id,
            reason="V244_FORCED_AUDIT_PAIR_CLOSE",
            old_exec=rec,
        )
        closed.append({"deal_id": deal_id, "ok": ok, "info": info})

        if positions_after is not None:
            positions = positions_after

    FAS.register_close_pair(ASSET, weak, strong, reason="V244_FORCED_AUDIT_PAIR_CLOSE")
    log("RUNNER_CLOSE_PAIR_DONE", asset=ASSET, closed=closed)
    return positions


def open_one(headers, positions):
    side, size, seq = FAS.next_forced_order()

    cycle = {
        "cycle_id": f"V244_FORCED_{int(time.time())}_{seq}_{uuid.uuid4().hex[:6]}",
        "asset": ASSET,
        "epic": ASSET,
        "direction": side,
        "side": side,
        "level": 1,
        "size": size,
        "source": "V24.4_FORCED_AUDIT_RUNNER",
        "strategy": "FORCED_AUDIT_SAMPLE",
        "reason": "MINIMUM_2_OPENINGS_PER_MINUTE",
    }

    log("RUNNER_OPEN_ATTEMPT", asset=ASSET, side=side, size=size, seq=seq, reason="MINIMUM_2_OPENINGS_PER_MINUTE")

    ok, record, positions_after = G.open_cycle_secure(
        headers=headers,
        asset=ASSET,
        cycle=cycle,
        market_status="FORCED_AUDIT",
        before_positions=positions,
    )

    log("RUNNER_OPEN_RESULT", asset=ASSET, side=side, size=size, ok=ok, record=record)

    if ok:
        FAS.register_open(asset=ASSET, side=side, size=size, reason="FORCED_AUDIT_SAMPLE", extra={"seq": seq, "record": record})

    return positions_after if positions_after is not None else positions


def main():
    FAS.safety_banner()
    log("RUNNER_START", asset=ASSET, target_openings_per_min=TARGET_OPENINGS_PER_MIN, sleep_sec=SLEEP_SEC, max_positions=MAX_POSITIONS)

    headers = G.login()
    log("RUNNER_LOGIN_OK", asset=ASSET)

    while True:
        try:
            positions = broker_positions(headers)
            asset_positions = positions_for_asset(ASSET, positions)

            log(
                "RUNNER_STATUS",
                asset=ASSET,
                open_positions=len(asset_positions),
                openings_last_60s=FAS.count_opens_last_60s(),
                missing_openings=FAS.missing_openings(),
            )

            positions = close_pair_if_available(headers, positions)
            asset_positions = positions_for_asset(ASSET, positions)

            if len(asset_positions) >= MAX_POSITIONS:
                log("RUNNER_OPEN_BLOCKED", asset=ASSET, reason="MAX_POSITIONS_REACHED", open_positions=len(asset_positions), max_positions=MAX_POSITIONS)
                time.sleep(SLEEP_SEC)
                continue

            missing = FAS.missing_openings()
            for _ in range(missing):
                positions = open_one(headers, positions)
                time.sleep(2)

            time.sleep(SLEEP_SEC)

        except Exception as e:
            log("RUNNER_EXCEPTION", asset=ASSET, exception=str(e), traceback=traceback.format_exc().replace("\n", " / "))
            if "429" in str(e) or "too-many" in str(e).lower() or "session" in str(e).lower():
                time.sleep(120)
                headers = G.login()
                log("RUNNER_RELOGIN_OK", asset=ASSET)
            else:
                time.sleep(20)


if __name__ == "__main__":
    main()
PY

python3 -m py_compile BOT_PIVOT_24_4_forced_audit_runner.py

printf '\n[6/8] AJOUT CONFIG ENV\n'
cat >> run_BOT_PIVOT_07D_SCALP_ACTIVE.sh <<'EOF2'

# ============================================================
# V24.4 — MODE EXPERIMENTAL : BLOQUER ANCIENS LIMIT
# ============================================================
export V244_FORCED_AUDIT_ENABLED=1
export V244_DEMO_ONLY_LOCK=1
export V244_TRADED_ASSET=ETHUSD
export V244_CONFIRM_ASSET=BTCUSD
export V244_EXCLUDED_ASSETS="GOLD"
export V244_CLOSE_PAIR_RATIO_MIN=1.67
export V244_MARGIN_MAX_EUR=3000
export V244_MARGIN_SOFT_EUR=2600
export V244_AUDIT_DIR=logs/v24_4_forced_audit
export V244_DISABLE_CLASSIC_BASKET_OPEN=1
EOF2

printf '\n[7/8] COMPILATION FINALE\n'
python3 -m py_compile BOT_PIVOT_24_4_forced_audit_sampling.py
python3 -m py_compile BOT_PIVOT_24_4_forced_audit_runner.py
python3 -m py_compile BOT_PIVOT_06G2_execution_secure.py

printf '\n[8/8] VERIFICATION PATCH\n'
grep -nE "V244_CLASSIC_BASKET_OPEN_BLOCKED|V244_CLOSE_PAIR_MODE|import BOT_PIVOT_24_4_forced_audit_sampling" BOT_PIVOT_06G2_execution_secure.py | head -80 || true

printf '\n============================================================\n'
printf 'INSTALLATION TERMINEE\n'
printf '============================================================\n'
printf 'IMPORTANT : annule les ordres ETH visibles dans Capital.com avant lancement.\n'
printf 'Puis lance uniquement le runner dédié :\n\n'
printf 'tmux new -s v244_forced_runner\n'
printf 'cd /home/philippe_vacher06/bot-pivot/live\n'
printf 'source venv/bin/activate\n'
printf 'export V244_FORCED_AUDIT_ENABLED=1\n'
printf 'export V244_DEMO_ONLY_LOCK=1\n'
printf 'export V244_TRADED_ASSET=ETHUSD\n'
printf 'export V244_EXCLUDED_ASSETS=GOLD\n'
printf 'export V244_DISABLE_CLASSIC_BASKET_OPEN=1\n'
printf 'python3 BOT_PIVOT_24_4_forced_audit_runner.py\n'
