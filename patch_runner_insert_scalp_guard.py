#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import shutil
RUN = Path('run_BOT_PIVOT_07D_24_7_DEMO.sh')
if not RUN.exists(): raise SystemExit('Runner introuvable')
s = RUN.read_text()
if 'BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD.py' in s:
    print('SKIP runner guard déjà présent')
    raise SystemExit(0)
lines = s.splitlines(True)
out=[]; inserted=False
for line in lines:
    if not inserted and ('BOT_PIVOT_06' in line or '06G2' in line):
        out.append('\necho "MODULE 00Z — SCALP ACTIVE GUARD"\n')
        out.append('python BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD.py || true\n')
        inserted=True
    out.append(line)
if not inserted:
    out.append('\necho "MODULE 00Z — SCALP ACTIVE GUARD"\n')
    out.append('python BOT_PIVOT_00Z_SCALP_ACTIVE_GUARD.py || true\n')
b = RUN.with_suffix(RUN.suffix + '.bak_guard_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
shutil.copy2(RUN,b)
RUN.write_text(''.join(out))
print('Runner patché:', RUN)
print('Backup:', b)
