# RAPPORT D’AUDIT EXTERNE CLAUDE — BOT-PIVOT V2446

Date : 2026-05-19  
Projet : BOT-PIVOT / bot-live_V00  
Dépôt : philippevacher06-sudo/bot-live_V00  
Mode : relecture externe en lecture seule  
Rapport source : Claude  
Synthèse et intégration : GPT  
Validation publication GitHub : OK VALIDATION GITHUB

---

## 1. Statut général

Claude a effectué une relecture technique externe du dépôt GitHub public.

Aucune modification n’a été effectuée par Claude :

- aucun commit ;
- aucune Pull Request ;
- aucun merge ;
- aucune modification directe.

Le dépôt a été analysé en lecture seule.

---

## 2. Sécurité / secrets

Conclusion Claude : aucun secret exposé détecté.

Les identifiants Capital.com semblent lus depuis les variables d’environnement ou depuis un fichier `.env` non versionné.

Aucun fichier sensible de type `.env`, `.pem` ou `.key` n’a été détecté dans les commits analysés.

Point de vigilance : les logs et backups versionnés peuvent contenir des informations opérationnelles sensibles : dealIds, prix, PnL, soldes.

---

## 3. Anomalies critiques

### C1 — TP dynamique non réellement appliqué

Claude constate que la décision réelle de fermeture utilise encore un TP statique issu de :

`V2446I_BASKET_TAKE_PROFIT_EUR`

Le bloc de TP dynamique est appliqué après la décision de fermeture, donc trop tard.

Conséquence : le TP dynamique V2446 n’est pas réellement décisionnel.

Priorité : C1 doit être corrigé avant tout nouveau patch d’exécution.

---

### C2 — Bloc TP dynamique dupliqué

Claude constate un copier-coller du bloc TP dynamique.

Conséquence : pas forcément d’effet fonctionnel immédiat, mais signe d’un patch empilé et fragile.

Priorité : nettoyage à intégrer avec la correction C1.

---

### C3 — Script H002 absent

Le script attendu :

`run_V2446_ADVERSE_STEPS_DE40_US30.sh`

n’existe pas dans le dépôt selon l’audit Claude.

À la place, Claude observe un script :

`run_V2446_ADVERSE_STEPS_FR40_DE40.sh`

Ce script ne correspond pas à la paire officielle H002.

Décision : H002 doit être clarifié avant test sérieux.

---

## 4. Anomalies moyennes

### M1 — PnL local encore basé sur MID

Le module :

`BOT_PIVOT_00B_pnl_eur.py`

semble encore utiliser un prix unique / MID sur certains chemins classiques.

Risque : écart possible avec le PnL réel broker.

Rappel doctrine :

- BUY doit être valorisé à la sortie au BID ;
- SELL doit être valorisé à la sortie à l’ASK ;
- la source de vérité prioritaire doit rester `broker_upl`.

---

### M2 — Matching actif / epic fragile

Le matching entre actif interne et epic broker semble basé sur une comparaison chaîne exacte.

Risque : si l’epic Capital.com diffère du nom interne, le bot peut ne pas retrouver les positions ouvertes.

Conséquence possible : pas de TP, pas de stop, pas de cap legs.

---

### M3 — `V2446I_TIME_STOP_SEC` incohérent

Claude observe une incohérence entre certains scripts :

- US500 : 7200 s ;
- règle attendue / autre script : 14400 s.

À clarifier : override volontaire ou dérive non maîtrisée.

---

### M4 — `MAX_OPEN_POSITIONS` incohérent

Le cap opérationnel semble protégé par `V2446I_MAX_LEGS`, mais le global historique reste incohérent.

Priorité : nettoyage secondaire.

---

### M5 — Logs et backups lourds versionnés

Claude signale de nombreux fichiers suivis sous :

- `logs/` ;
- `backups/` ;
- `backup/`.

Risque : exposition de données opérationnelles.

Priorité : nettoyage Git à prévoir après stabilisation technique.

---

## 5. Points conformes

Claude confirme que l’isolation H001/H002 est globalement cohérente sur plusieurs fichiers :

- `V244_STATE_FILE` ;
- `V244_LOCK_FILE` ;
- `V2446_ADVERSE_STATE_FILE` ;
- `V244_AUDIT_DIR`.

Les locks par actif permettent des runs parallèles sans collision directe.

Le garde-fou anti-yoyo est cohérent avec `hedgingMode=False`.

---

## 6. Question doctrinale tranchée

Claude constate que le `total_upl` du panier ne somme que les positions de l’actif principal.

Le leg hedge semble exclu du TP / stop global.

Décision stratégique Philippe / GPT :

Le TP / stop panier cross-hedge doit intégrer le PnL broker réel cumulé de toutes les jambes du panier, y compris le hedge.

Donc :

H001 :

`PnL global = PnL US500 + PnL US100`

H002 :

`PnL global = PnL DE40 + PnL US30`

Source de vérité :

`broker_upl`

---

## 7. Statut recommandé

H001 et H002 restent BLOCKED tant que l’audit prix / PnL n’est pas PASS.

Aucun patch exécution / TP / stop / legs ne doit être appliqué avant :

1. correction de C1 ;
2. clarification ou création du script H002 ;
3. vérification WebSocket ;
4. audit prix / PnL complet ;
5. validation explicite Philippe.

---

## 8. Décision de gouvernance

Aucune modification GitHub ne doit être effectuée sans validation explicite de Philippe par :

`OK VALIDATION GITHUB`

---

## 9. Priorité de travail proposée

Ordre recommandé :

1. Produire une proposition technique courte pour corriger C1.
2. Vérifier si le chemin classique 05x peut encore déclencher une fermeture.
3. Clarifier H002 : DE40 / US30.
4. Réintégrer le PnL hedge dans le calcul global cross-hedge.
5. Nettoyer les duplications TP dynamique.
6. Traiter les logs/backups versionnés.

---

## 10. Conclusion

Le dépôt peut être utilisé comme base d’analyse publique en lecture, mais la logique V2446 reste bloquée techniquement sur les points critiques C1 et C3.

Le prochain travail ne doit pas être un patch global. La priorité est une correction courte, ciblée et vérifiable du TP dynamique décisionnel, puis une clarification stricte de H002.
