#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

RUNNER="BOT_PIVOT_24_4_forced_audit_runner.py"
TS=$(date +"%Y%m%d_%H%M%S")
cp -f "$RUNNER" "$RUNNER.before_v2444_8A_$TS"

python3 <<'PY'
from pathlib import Path
import re

p = Path("BOT_PIVOT_24_4_forced_audit_runner.py")
s = p.read_text(encoding="utf-8")

if "NO_LOSS_CLOSE_HARD_GUARD" not in s:
    anchor = 'ALLOW_OPPOSITE_NETTING = os.getenv("V244_ALLOW_OPPOSITE_NETTING", "1") == "1"\n'
    s = s.replace(anchor, anchor + '''
NO_LOSS_CLOSE_HARD_GUARD = os.getenv("V244_NO_LOSS_CLOSE_HARD_GUARD", "1") == "1"
DISABLE_CLOSE_BY_AGE = os.getenv("V244_DISABLE_CLOSE_BY_AGE", "1") == "1"
''', 1)

api_delete = r'''
def api_delete(headers: Dict[str, str], path: str) -> Tuple[int, Any]:
    url = BASE + path
    blocked = _demo_guard(url)
    if blocked:
        return 0, blocked

    if NO_LOSS_CLOSE_HARD_GUARD and path.startswith("/positions/"):
        deal_id = path.rsplit("/", 1)[-1]
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
'''

if "def api_delete(" in s:
    s = re.sub(
        r"^def api_delete\(.*?\n(?=^def |\n# ======================================================================|^if __name__ == \"__main__\":)",
        api_delete.strip() + "\n\n",
        s,
        flags=re.S | re.M,
    )
else:
    marker = "\n# ======================================================================\n# POSITIONS / NETTING / MARGE"
    s = s.replace(marker, "\n\n" + api_delete.strip() + "\n" + marker, 1)

# Neutralise toute ancienne fonction qui ferme par age si elle existe encore.
def repl_age(m):
    name = m.group(1)
    body = m.group(0)
    if "RUNNER_CLOSE_BY_AGE" not in body and "RUNNER_POSITION_AGE" not in body:
        return body
    return f'''def {name}(*args: Any, **kwargs: Any) -> Any:
    log("RUNNER_CLOSE_BY_AGE_DISABLED", asset=ASSET, function="{name}")
    return False, {{"stage": "CLOSE_BY_AGE_DISABLED"}}

'''

s = re.sub(
    r"^def ([A-Za-z_][A-Za-z0-9_]*)\(.*?\n(?=^def |\n# ======================================================================|^if __name__ == \"__main__\":)",
    repl_age,
    s,
    flags=re.S | re.M,
)

p.write_text(s, encoding="utf-8")
PY

python3 -m py_compile "$RUNNER"
grep -nE "NO_LOSS_CLOSE_HARD_GUARD|RUNNER_DELETE_BLOCKED_LOSS_OR_FLAT|RUNNER_CLOSE_BY_AGE_DISABLED" "$RUNNER" | head -80
echo "PATCH 8A OK"
