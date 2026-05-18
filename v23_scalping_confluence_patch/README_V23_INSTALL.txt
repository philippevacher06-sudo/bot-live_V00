BOT-PIVOT V23 — SCALPING CONFLUENCE DEMO

Objectif : installer une version plus sélective avant relance.

Contenu :
- install_v23_scalping_confluence.sh : lance l'installation complète.
- patch_v23_scalping_confluence.py : patche la config, le module 04, le module 05, et crée BOT_PIVOT_04B_context_score.py.
- audit_v23.sh : vérifie les tailles, les TP, la compilation et le nouveau score de contexte.

Procédure conseillée sur le serveur :

1) Copier ou importer le ZIP dans :
   /home/philippe_vacher06/bot-pivot/live

2) Dézipper :
   unzip v23_scalping_confluence_patch.zip

3) Installer :
   cd /home/philippe_vacher06/bot-pivot/live
   source venv/bin/activate
   bash v23_scalping_confluence_patch/install_v23_scalping_confluence.sh

4) Auditer sans relancer le bot :
   bash v23_scalping_confluence_patch/audit_v23.sh

Ne relance pas le 24/7 avant validation de l'audit.

Ce patch applique :
- TP L1 = 0.30 €, L2 = 0.60 €, L3 = 1.50 €, L4 = 3.00 €, L5 = 6.00 €.
- Tailles L1 x3 par rapport aux tailles actuelles validées.
- Score d'entrée basé sur VWAP approximé, Camarilla, phase et micro-réaction.
- Entrée L1 seulement si score >= 3.
- NEXT_LEVEL seulement si score >= 3 et signal encore dans le même sens.
- Sortie de scalp si la position dort trop longtemps avec contexte faible.

Des sauvegardes .BAK_V23_YYYYMMDD_HHMMSS sont créées automatiquement avant patch.
