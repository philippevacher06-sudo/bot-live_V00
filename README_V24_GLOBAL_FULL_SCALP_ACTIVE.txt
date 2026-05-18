PACK GLOBAL — BOT-PIVOT V24.1 SCALP ACTIVE

Objectif : 50 à 100 trades/jour, 16 actifs, marge cible autour de 3000 €.

Corrige / ajoute :
1. Matching taille broker tolérant.
2. BASKET_EMPTY_RESET protégé par audit broker.
3. Nettoyage pending après TP_FAIL / TP_OK.
4. Nettoyage pending de panier partiel.
5. LIMIT guard : BUY LIMIT sous BID, SELL LIMIT au-dessus ASK.
6. STOP guard : guaranteedStop=false sur actifs problématiques.
7. Retry broker après error.validation.limit.price / error.invalid.stoploss.*.
8. Cache M15/zones plus long.
9. Tick stream et pause configurables pour SCALP ACTIVE.
10. Guard marge/sélection : orphelins, vieux pending, pression pending.
11. Scan tunnel signaux -> paniers -> fills -> TP.

Commandes :
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate
tmux send-keys -t botpivot24 C-c
sleep 3
unzip -o v24_global_full_scalp_active_pack.zip
bash install_v24_global_full_patch.sh

Relance :
tmux send-keys -t botpivot24 "cd /home/philippe_vacher06/bot-pivot/live && source venv/bin/activate && ./run_BOT_PIVOT_07D_SCALP_ACTIVE.sh" C-m

Surveillance :
LOG=$(ls -t logs/BOT_PIVOT_07D_24_7_DEMO_*.log | head -1)
grep -nE "V24_LIMIT_SIDE_GUARD|V24_STOP_GUARD|V24_WORKING_ORDER_RETRY|BASKET_EMPTY_RESET_BLOCKED|BASKET_PARTIAL_PENDING_CANCEL|BASKET_TP_FAIL|BASKET_TP_OK|LIMIT_REJECT|BASKET_REJECT|SCALP_ACTIVE_GUARD|ERROR|Exception|Traceback" "$LOG" | tail -350
python audit_v24_global_state.py
python scan_v24_activity_funnel.py
