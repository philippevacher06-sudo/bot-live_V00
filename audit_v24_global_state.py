#!/usr/bin/env python3
from pathlib import Path
import os,json,requests

def load_dotenv(path='.env'):
    p=Path(path)
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_dotenv()
import BOT_PIVOT_06G2_execution_secure as G
headers=G.login(); base=getattr(G,'BASE_URL','https://demo-api-capital.backend-capital.com/api/v1').rstrip('/')
positions=requests.get(base+'/positions',headers=headers,timeout=20).json().get('positions',[]) or []
orders=requests.get(base+'/workingorders',headers=headers,timeout=20).json().get('workingOrders',[]) or []
print('='*100); print('POSITIONS BROKER'); print('='*100)
if not positions: print('Aucune position broker ouverte')
for p in positions:
    m=p.get('market',{}) or {}; pos=p.get('position',{}) or {}
    print(json.dumps({'epic':m.get('epic') or pos.get('epic'),'name':m.get('instrumentName'),'dealId':pos.get('dealId'),'direction':pos.get('direction'),'size':pos.get('size'),'level':pos.get('level'),'upl':pos.get('upl')},indent=2,ensure_ascii=False))
print(); print('='*100); print('WORKING ORDERS BROKER'); print('='*100)
if not orders: print('Aucun ordre pending broker')
for w in orders:
    wo=w.get('workingOrderData',{}) or {}; md=w.get('marketData',{}) or {}
    print(json.dumps({'epic':wo.get('epic') or md.get('epic'),'name':md.get('instrumentName'),'dealId':wo.get('dealId'),'direction':wo.get('direction'),'size':wo.get('orderSize'),'level':wo.get('orderLevel'),'stopDistance':wo.get('stopDistance'),'guaranteedStop':wo.get('guaranteedStop'),'createdDate':wo.get('createdDate')},indent=2,ensure_ascii=False))
print(); print('='*100); print('LOCAL STATE / EXEC STATE'); print('='*100)
try:
    st=json.loads(Path(G.B.STATE_FILE).read_text()); non=[a for a,s in st.get('assets',{}).items() if s.get('status')!='IDLE']; print('STATE actifs non-IDLE =',len(non),non)
except Exception as e: print('STATE ERREUR =',e)
try:
    ex=json.loads(Path(G.B.EXEC_STATE_FILE).read_text()); act=list((ex.get('active',{}) or {}).keys()); print('EXEC active =',len(act),act)
except Exception as e: print('EXEC_STATE ERREUR =',e)
