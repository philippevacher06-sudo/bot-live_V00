#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch cadence/cache : M15 cache long, tick stream plus court, pause plus courte, lanceur scalp actif."""
from pathlib import Path
from datetime import datetime
import shutil, re

TAG = datetime.now().strftime("%Y%m%d_%H%M%S")

def backup(p):
    b = p.with_suffix(p.suffix + ".bak_cadence_" + TAG)
    shutil.copy2(p, b)
    print("Backup:", b)

def patch_file(p):
    s = p.read_text(errors="ignore")
    old = s
    if p.suffix == ".sh":
        s = re.sub(r'(?m)^(\s*)sleep\s+30\s*$', r'\1sleep "${CYCLE_PAUSE_SEC:-5}"', s)
        s = s.replace("Pause 30s", 'Pause ${CYCLE_PAUSE_SEC:-5}s')
    if p.suffix == ".py":
        need_os = False
        pats = [
            (r'(\bDURATION_SEC\s*=\s*)90\b', r'\1int(os.getenv("TICK_STREAM_DURATION_SEC", "25"))'),
            (r'(\bSTREAM_DURATION_SEC\s*=\s*)90\b', r'\1int(os.getenv("TICK_STREAM_DURATION_SEC", "25"))'),
            (r'(\bduration_sec\s*=\s*)90\b', r'\1int(os.getenv("TICK_STREAM_DURATION_SEC", "25"))'),
            (r'(default\s*=\s*)90(\s*[,\)])', r'\1int(os.getenv("TICK_STREAM_DURATION_SEC", "25"))\2'),
        ]
        for pat, rep in pats:
            ns = re.sub(pat, rep, s)
            if ns != s:
                need_os = True
                s = ns
        if need_os and "import os" not in s:
            if "import sys" in s:
                s = s.replace("import sys", "import sys\nimport os", 1)
            else:
                s = "import os\n" + s
    if s != old:
        backup(p)
        p.write_text(s)
        print("PATCH cadence:", p)
        return True
    return False

def create_launcher():
    out = Path("run_BOT_PIVOT_07D_SCALP_ACTIVE.sh")
    out.write_text('''#!/usr/bin/env bash
set -e
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

export V24_SCALP_ACTIVE=true
export V24_TARGET_TRADES_MIN=${V24_TARGET_TRADES_MIN:-50}
export V24_TARGET_TRADES_MAX=${V24_TARGET_TRADES_MAX:-100}
export V24_MARGIN_BUDGET_EUR=${V24_MARGIN_BUDGET_EUR:-3000}

export HISTORY_MAX_AGE_SEC=${HISTORY_MAX_AGE_SEC:-86400}
export ZONES_MAX_AGE_SEC=${ZONES_MAX_AGE_SEC:-43200}
export MARKETS_MAX_AGE_SEC=${MARKETS_MAX_AGE_SEC:-7200}
export TICK_STREAM_DURATION_SEC=${TICK_STREAM_DURATION_SEC:-25}
export CYCLE_PAUSE_SEC=${CYCLE_PAUSE_SEC:-5}

export BOLLINGER_CURSOR=${BOLLINGER_CURSOR:-0.8}
export PENDING_BASKET_MAX_AGE_SEC=${PENDING_BASKET_MAX_AGE_SEC:-60}
export PARTIAL_BASKET_PENDING_MAX_AGE_SEC=${PARTIAL_BASKET_PENDING_MAX_AGE_SEC:-90}
export STOP_AIRBAG_STEP_MULT=${STOP_AIRBAG_STEP_MULT:-3.5}
export STOP_AIRBAG_SPREAD_MULT=${STOP_AIRBAG_SPREAD_MULT:-3}
export TREND_ENTRY_CURSOR=${TREND_ENTRY_CURSOR:-1.0}
export SAFETY_EXIT_CURSOR=${SAFETY_EXIT_CURSOR:-1.1}
export V24_PNL_AUDIT=true
export V24_TP_SAFETY_MARGIN_EUR=${V24_TP_SAFETY_MARGIN_EUR:-0}

export V24_LIMIT_STOP_RETRY=${V24_LIMIT_STOP_RETRY:-true}
export V24_LIMIT_GUARD_SPREAD_MULT=${V24_LIMIT_GUARD_SPREAD_MULT:-1.5}
export V24_DISABLE_GUARANTEED_STOP_ASSETS=${V24_DISABLE_GUARANTEED_STOP_ASSETS:-EURJPY,USDJPY,GOLD,OIL_CRUDE,OIL_BRENT,BTCUSD,ETHUSD,J225,SILVER}

export V24_MARGIN_SELECTION_ENABLED=${V24_MARGIN_SELECTION_ENABLED:-true}
export V24_MAX_BROKER_PENDING_ORDERS=${V24_MAX_BROKER_PENDING_ORDERS:-18}
export V24_ORPHAN_PENDING_MAX_AGE_SEC=${V24_ORPHAN_PENDING_MAX_AGE_SEC:-0}

./run_BOT_PIVOT_07D_24_7_DEMO.sh
''')
    out.chmod(0o755)
    print("Lanceur créé:", out)

count = 0
for p in list(Path('.').glob('run_BOT_PIVOT_07D_24_7_DEMO.sh')) + list(Path('.').glob('BOT_PIVOT_03*.py')) + list(Path('.').glob('BOT_PIVOT_07*.py')):
    if p.is_file():
        try:
            if patch_file(p):
                count += 1
        except Exception as e:
            print("WARN:", p, e)
create_launcher()
print("Fichiers cadence patchés:", count)
