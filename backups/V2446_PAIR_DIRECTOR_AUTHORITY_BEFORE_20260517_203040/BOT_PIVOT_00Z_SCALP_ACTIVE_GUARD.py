#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guard broker/state/marge : annule orphelins et vieux pending sous pression."""
from pathlib import Path
from datetime import datetime, timezone
import os, json, requests

def load_dotenv(path='.env'):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def env_bool(k, d=False):
    return str(os.getenv(k, str(d))).lower() in ('1','true','yes','y','on')

def env_int(k, d):
    try: return int(float(os.getenv(k, str(d))))
    except Exception: return int(d)

def env_float(k, d):
    try: return float(os.getenv(k, str(d)))
    except Exception: return float(d)

def age_sec(created):
    if not created: return 0.0
    try:
        s = str(created).replace('Z', '+00:00')
        if '+' not in s and len(s) >= 19: s += '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc)-dt).total_seconds())
    except Exception:
        return 0.0

def main():
    if not env_bool('V24_MARGIN_SELECTION_ENABLED', True):
        print('SCALP_ACTIVE_GUARD | disabled')
        return
    load_dotenv()
    import BOT_PIVOT_06G2_execution_secure as G
    headers = G.login()
    base = getattr(G, 'BASE_URL', 'https://demo-api-capital.backend-capital.com/api/v1').rstrip('/')
    positions = requests.get(base + '/positions', headers=headers, timeout=20).json().get('positions', []) or []
    orders = requests.get(base + '/workingorders', headers=headers, timeout=20).json().get('workingOrders', []) or []
    try:
        ex = json.loads(Path(G.B.EXEC_STATE_FILE).read_text())
    except Exception:
        ex = {'active': {}}
    active_assets = set((ex.get('active', {}) or {}).keys())
    max_pending = env_int('V24_MAX_BROKER_PENDING_ORDERS', 18)
    orphan_age = env_float('V24_ORPHAN_PENDING_MAX_AGE_SEC', 0)
    print(f"SCALP_ACTIVE_GUARD | positions={len(positions)} pending={len(orders)} exec_active={len(active_assets)} max_pending={max_pending}")
    rows = []
    for w in orders:
        wo = w.get('workingOrderData', {}) or {}
        md = w.get('marketData', {}) or {}
        epic = wo.get('epic') or md.get('epic')
        rows.append({
            'dealId': wo.get('dealId'), 'epic': epic, 'direction': wo.get('direction'),
            'level': wo.get('orderLevel'), 'createdDate': wo.get('createdDate'),
            'age': age_sec(wo.get('createdDate')), 'orphan': epic not in active_assets,
        })
    to_cancel = []
    for r in rows:
        if r['orphan'] and r['age'] >= orphan_age:
            r['reason'] = 'SCALP_ACTIVE_ORPHAN_PENDING_CLEANUP'
            to_cancel.append(r)
    if len(rows) > max_pending:
        excess = len(rows) - max_pending
        candidates = sorted([r for r in rows if r not in to_cancel], key=lambda r: (not r['orphan'], -r['age']))
        for r in candidates[:excess]:
            r['reason'] = 'SCALP_ACTIVE_PENDING_PRESSURE_OLDEST_WEAK'
            to_cancel.append(r)
    seen = set()
    for r in to_cancel:
        deal_id = r.get('dealId')
        if not deal_id or deal_id in seen: continue
        seen.add(deal_id)
        try:
            resp = requests.delete(base + '/workingorders/' + deal_id, headers=headers, timeout=20)
            print(f"SCALP_ACTIVE_GUARD_CANCEL | {r.get('epic')} {r.get('direction')} level={r.get('level')} age={r.get('age'):.1f}s reason={r.get('reason')} HTTP={resp.status_code}")
        except Exception as e:
            print(f"SCALP_ACTIVE_GUARD_CANCEL_FAIL | {deal_id} | {e}")
if __name__ == '__main__': main()
