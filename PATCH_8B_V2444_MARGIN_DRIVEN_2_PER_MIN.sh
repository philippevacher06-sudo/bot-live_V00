#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

RUNNER="BOT_PIVOT_24_4_forced_audit_runner.py"
TS=$(date +"%Y%m%d_%H%M%S")
cp -f "$RUNNER" "$RUNNER.before_v2444_8B_$TS"

python3 <<'PY'
from pathlib import Path
import re

p = Path("BOT_PIVOT_24_4_forced_audit_runner.py")
s = p.read_text(encoding="utf-8")

s = re.sub(
    r'MAX_NET_EXPOSURE\s*=\s*float\(os\.getenv\("V244_MAX_NET_EXPOSURE",\s*"[^"]+"\)\)',
    'MAX_NET_EXPOSURE = float(os.getenv("V244_MAX_NET_EXPOSURE", "0"))',
    s,
)

s = re.sub(
    r'MAX_OPEN_POSITIONS\s*=\s*int\(os\.getenv\("V244_MAX_OPEN_POSITIONS",\s*"[^"]+"\)\)',
    'MAX_OPEN_POSITIONS = int(os.getenv("V244_MAX_OPEN_POSITIONS", "200"))',
    s,
)

if "MARGIN_DRIVEN_MODE" not in s:
    anchor = 'REQUIRE_ACCOUNT_NETTING = os.getenv("V244_REQUIRE_ACCOUNT_NETTING", "1") == "1"\n'
    s = s.replace(anchor, anchor + '''
MARGIN_DRIVEN_MODE = os.getenv("V244_MARGIN_DRIVEN_MODE", "1") == "1"
''', 1)

new_func = r'''
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
'''

s = re.sub(
    r"^def net_exposure_allows_order\(.*?\n(?=^def |\n# ======================================================================|^if __name__ == \"__main__\":)",
    new_func.strip() + "\n\n",
    s,
    flags=re.S | re.M,
)

if "margin_driven_mode=MARGIN_DRIVEN_MODE" not in s:
    s = s.replace(
        "max_net_exposure=MAX_NET_EXPOSURE,",
        'max_net_exposure=MAX_NET_EXPOSURE,\n        margin_driven_mode=MARGIN_DRIVEN_MODE,',
        1,
    )

p.write_text(s, encoding="utf-8")
PY

python3 -m py_compile "$RUNNER"
grep -nE "MARGIN_DRIVEN_MODE|MARGIN_DRIVEN_NET_CAP_DISABLED|MAX_NET_EXPOSURE|MAX_OPEN_POSITIONS" "$RUNNER" | head -100
echo "PATCH 8B OK"
