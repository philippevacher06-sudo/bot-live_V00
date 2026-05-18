PACK PATCH BOT-PIVOT V24.1 SCALP ACTIVE SAFETY

À faire sur le serveur :

1) Stopper le bot :
   tmux send-keys -t botpivot24 C-c
   sleep 3
   ps aux | grep -E "BOT_PIVOT|run_BOT" | grep -v grep || echo "OK : aucun process BOT-PIVOT actif"

2) Copier/dézipper ce pack dans :
   /home/philippe_vacher06/bot-pivot/live

3) Lancer le patch :
   cd /home/philippe_vacher06/bot-pivot/live
   source venv/bin/activate
   python patch_v24_scalp_active_safety.py

4) Vérifier compilation + marqueurs :
   bash check_v24_patch.sh

5) Auditer broker/state avant relance :
   python audit_v24_broker_state.py

Ne pas relancer le bot tant que l'audit broker/state n'est pas propre.
