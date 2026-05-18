#!/usr/bin/env bash
set -euo pipefail
cd /home/philippe_vacher06/bot-pivot/live

cat >> .v2445_full_eth_basket_apply.py <<'PY'

_v2445_previous_close_winning_basket_if_needed = globals().get("close_winning_basket_if_needed")

def close_winning_basket_if_needed(*args, **kwargs):
    if not _v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True):
        if callable(_v2445_previous_close_winning_basket_if_needed):
            return _v2445_previous_close_winning_basket_if_needed(*args, **kwargs)
        return False

    asset = str(_v2445_os.getenv("V244_TRADED_ASSET", globals().get("TRADED_ASSET", "ETHUSD"))).upper()
    tp = _v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0)
    min_age = _v2445_float("V244_FULL_BASKET_MIN_AGE_SEC", 0.0)

    positions = _v2445_extract_positions(args, kwargs)
    eth_positions = [p for p in positions if _v2445_epic(p) == asset]
    total_upl = sum(_v2445_upl(p) for p in eth_positions)
    deal_ids = [_v2445_deal_id(p) for p in eth_positions if _v2445_deal_id(p)]
    too_young = [_v2445_deal_id(p) for p in eth_positions if _v2445_age(p) < min_age]

    reasons = []
    if not eth_positions: reasons.append("NO_ETH_POSITION")
    if total_upl < tp: reasons.append("TOTAL_UPL_BELOW_TP")
    if too_young: reasons.append("POSITION_TOO_YOUNG")

    ok = not reasons
    _v2445_log("RUNNER_ETH_BASKET_DECISION", asset=asset, ok=ok, reasons=reasons,
               open_eth_count=len(eth_positions), dealIds=deal_ids,
               total_upl=round(total_upl, 4), tp=tp, min_age_sec=min_age,
               max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12))

    if not ok:
        return False

    _v2445_log("RUNNER_ETH_BASKET_CLOSE_ALL_START", asset=asset,
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
            _v2445_log("RUNNER_ETH_BASKET_CLOSE_RESULT", asset=asset, dealId=did,
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

    _v2445_log("RUNNER_ETH_BASKET_CLOSE_ALL_DONE", asset=asset, ok=all_ok,
               total_upl=round(total_upl, 4), count=len(eth_positions))
    return True

_v2445_log("RUNNER_V2445_FULL_ETH_BASKET_PATCH_ACTIVE",
           max_open_positions=_v2445_int("V244_MAX_OPEN_POSITIONS", 12),
           full_eth_basket_close_enabled=_v2445_bool("V244_CLOSE_FULL_ETH_BASKET_ENABLED", True),
           full_eth_basket_tp_eur=_v2445_float("V244_FULL_ETH_BASKET_TP_EUR", 1.0))
# === V2445_FULL_ETH_BASKET_TP_END ===
'''

original = p.read_text()
backup = p.with_name(p.name + ".bak." + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".v2445")
backup.write_text(original)

s = original
if b in s and e in s:
    s = re.sub(re.escape(b) + r".*?" + re.escape(e) + r"\n?", "", s, flags=re.S)

m = re.search(r'\nif\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:', s)
if not m:
    raise SystemExit("ERREUR: bloc if __name__ == '__main__' introuvable")

s = s[:m.start()] + "\n\n" + code + "\n" + s[m.start():]
p.write_text(s)

print("OK patch V2445 applique")
print("backup:", backup)
PY

python3 .v2445_full_eth_basket_apply.py
python3 -m py_compile BOT_PIVOT_24_4_forced_audit_runner.py

echo "OK 3/3 applique et compile"
