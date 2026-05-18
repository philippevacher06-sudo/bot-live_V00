BOT-PIVOT V24.3 DEMO - STORM / MAX LOSS / TUNING / REPORT

Base conservee :
- TP panier uniquement sur Capital.com position.upl.
- LIMIT L1/L2/L3 avec PRICE_AUDIT.
- Anti marketable limit.
- Anti niveaux ecrases.
- Pending cancel et partial pending cancel.
- OIL_CRUDE base size 4.
- Ticks 45s et spread learning 150.

Ajouts V24.3 demo :
- STORM_GUARD avant entree, pendant pending, apres fill.
- Max loss logiciel panier base broker_upl, pas PnL interne.
- MAX_TICK_AGE_SEC par defaut 20s.
- Tuning BOLLINGER_TOO_FAR uniquement sur US30, ETHUSD, EURUSD, EURJPY.
- Reporting automatique V24_3_NIGHTLY_REPORT.py.
- Tableau risque panier V24_3_RISK_BASKET_REPORT.py.

Variables utiles :
- V243_STORM_GUARD_ENABLED=true
- V243_STORM_SPREAD_MULT=3.0
- V243_STORM_MOVE_STEP_MULT=2.5
- V243_STORM_RANGE_STEP_MULT=3.0
- V243_STORM_GLOBAL_ALERT_COUNT=4
- V243_MAX_LOSS_GUARD_ENABLED=true
- V243_MAX_LOSS_1_OPEN_EUR=1.50
- V243_MAX_LOSS_2_OPEN_EUR=3.00
- V243_MAX_LOSS_3_OPEN_EUR=5.00
- MAX_TICK_AGE_SEC=20

Commandes :

python3 -m py_compile BOT_PIVOT_06G2_execution_secure.py BOT_PIVOT_04_signal_tick.py
./run_BOT_PIVOT_07D_SCALP_ACTIVE.sh
./report_V24_3_DEMO.sh

Cette version reste DEMO/experimental. Ne pas utiliser en reel sans audit du risque panier,
des stops broker, de la marge, et du comportement du STORM_GUARD.
