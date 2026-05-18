Source actuelle BOT-PIVOT V24.1 SCALP ACTIVE avant V24.2.

État validé :
- TP panier corrigé par V24_BROKER_UPL_TP_PATCH_V1.
- TP_OK doit utiliser Capital.com position.upl.
- Bot arrêté.
- cycle_state et exec_state nettoyés.

Objectif V24.2 :
1. Neutraliser BOLLINGER_SCALP_CLAMP.
2. Rejeter si Bollinger trop loin au lieu de rapprocher le niveau.
3. Ajouter anti-LIMIT marketable.
4. Interdire L1/L2/L3 identiques ou trop proches.
5. Ajouter audit prix complet.
6. Ajouter garde-fou marge globale.
7. Réduire OIL_CRUDE.
8. Corriger pending fantômes sans workingDealId.
9. Nettoyer le filtre EURJPY/Bollinger width.
10. Fournir scripts install / verify / relance.
