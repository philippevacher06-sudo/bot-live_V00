#!/usr/bin/env python3
from pathlib import Path
from collections import defaultdict
import sys,re
assets=['US500','US100','US30','DE40','FR40','FRA40','UK100','J225','EURUSD','GBPUSD','USDJPY','EURJPY','GOLD','SILVER','OIL_CRUDE','BTCUSD','ETHUSD']
log_path=Path(sys.argv[1]) if len(sys.argv)>1 else sorted(Path('logs').glob('BOT_PIVOT_07D_24_7_DEMO_*.log'),key=lambda p:p.stat().st_mtime,reverse=True)[0]
lines=log_path.read_text(errors='ignore').splitlines(); stats={a:defaultdict(int) for a in assets}
events=['OPEN_L1','LIMIT_OK','LIMIT_REJECT','BASKET_NEW','BASKET_REJECT','BASKET_FILL','PNL_AUDIT_TOTAL','BASKET_TP_OK','BASKET_TP_FAIL','BASKET_PENDING_CANCEL','BASKET_PARTIAL_PENDING_CANCEL','BASKET_EMPTY_RESET_BLOCKED','V24_LIMIT_SIDE_GUARD','V24_STOP_GUARD','V24_WORKING_ORDER_RETRY','SCALP_ACTIVE_GUARD_CANCEL']
for line in lines:
    for a in assets:
        if a not in line: continue
        if re.search(rf'{a}\s+\|\s+BUY\s+\|',line) or re.search(rf'{a}\s+\|\s+SELL\s+\|',line): stats[a]['SIGNALS']+=1
        for ev in events:
            if ev in line: stats[a][ev]+=1
print('LOG =',log_path)
print('ACTIF      SIG OPEN NEW FILL TP_OK TP_FAIL PEND PART REJ L_REJ SIDE STOP RETRY')
print('-'*86); tot=defaultdict(int)
for a in assets:
    vals=[stats[a]['SIGNALS'],stats[a]['OPEN_L1'],stats[a]['BASKET_NEW'],stats[a]['BASKET_FILL'],stats[a]['BASKET_TP_OK'],stats[a]['BASKET_TP_FAIL'],stats[a]['BASKET_PENDING_CANCEL'],stats[a]['BASKET_PARTIAL_PENDING_CANCEL'],stats[a]['BASKET_REJECT'],stats[a]['LIMIT_REJECT'],stats[a]['V24_LIMIT_SIDE_GUARD'],stats[a]['V24_STOP_GUARD'],stats[a]['V24_WORKING_ORDER_RETRY']]
    keys=['sig','open','new','fill','tpok','tpfail','pend','part','rej','lrej','side','stop','retry']
    for k,v in zip(keys,vals): tot[k]+=v
    print(f'{a:10s} {vals[0]:3d} {vals[1]:4d} {vals[2]:3d} {vals[3]:4d} {vals[4]:5d} {vals[5]:7d} {vals[6]:4d} {vals[7]:4d} {vals[8]:3d} {vals[9]:5d} {vals[10]:4d} {vals[11]:4d} {vals[12]:5d}')
print('-'*86)
print(f"{'TOTAL':10s} {tot['sig']:3d} {tot['open']:4d} {tot['new']:3d} {tot['fill']:4d} {tot['tpok']:5d} {tot['tpfail']:7d} {tot['pend']:4d} {tot['part']:4d} {tot['rej']:3d} {tot['lrej']:5d} {tot['side']:4d} {tot['stop']:4d} {tot['retry']:5d}")
