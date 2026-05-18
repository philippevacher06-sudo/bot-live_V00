# BOT-PIVOT V2446 - Regles Maitres

Statut : reference projet
Version documentaire : V2446
Date de creation : 2026-05-18
Auteur fonctionnel : Philippe Vacher
Usage : document commun ChatGPT / Codex / bot live

Ce fichier est la reference strategique et technique du projet BOT-PIVOT V2446.
Toute modification de code, de configuration, de lancement, de signaux, de gestion
de panier ou de logique broker doit etre comparee a ce document avant application.

Doctrine generale :

- Pas de preuve, pas de trade.
- Pas de modification lourde sans diagnostic.
- Pas de patch sans sauvegarde.
- Pas de changement contraire aux regles maitresses sans alerte explicite.
- Microtouches verifiables : petits changements, lisibles, testables, reversibles.

## 1. Contexte Projet

BOT-PIVOT est un bot de scalping en demo sur Capital.com. La version de reference
actuelle est la V2446.

Chemin principal Linux :

```bash
/home/philippe_vacher06/bot-pivot/live
```

Environnement Python :

```bash
source venv/bin/activate
```

Scripts de lancement connus :

```bash
./run_BOT_PIVOT_07D_SCALP_ACTIVE.sh
./run_BOT_PIVOT_07D_24_7_DEMO.sh
```

Univers de trading :

- US500
- US100
- US30
- DE40
- FR40
- UK100
- J225
- EURUSD
- GBPUSD
- USDJPY
- EURJPY
- GOLD
- SILVER
- OIL_CRUDE
- BTCUSD
- ETHUSD

Broker :

- Capital.com
- Compte demo
- `hedgingMode=False`

Implication majeure de `hedgingMode=False` : le bot doit gerer tres strictement
l'etat reel broker, les paniers, les legs, les locks, les fermetures et la
synchronisation. Aucun retournement logique ne doit supposer que deux directions
opposees peuvent coexister proprement sans validation broker.

## 2. Architecture De Travail ChatGPT / Codex

Objectif :

- ChatGPT sert a conserver l'analyse strategique, les diagnostics, les syntheses,
  les decisions fonctionnelles et les discussions longues.
- Codex sert a lire le code, proposer des patchs, appliquer des microtouches,
  produire les diffs, lancer les tests et verifier la coherence technique.
- Ce fichier sert de verite commune.

Methode recommandee si aucune synchronisation directe automatique n'existe :

- Conserver une copie de ce fichier dans le projet ChatGPT.
- Conserver une copie identique dans le dossier bot utilise par Codex.
- Avant toute session Codex, verifier que ce fichier est la derniere version.
- Apres toute decision strategique validee dans ChatGPT, mettre a jour ce fichier.
- Apres tout patch Codex qui change une regle ou revele une contrainte, mettre a
  jour ce fichier ou demander validation avant modification.

Emplacement recommande cote bot :

```bash
/home/philippe_vacher06/bot-pivot/live/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

## 3. Les 50 Regles Maitresses V2446

### A. Gouvernance et doctrine

1. Le fichier `BOT_PIVOT_V2446_REGLES_MAITRES.md` est la reference absolue de la V2446.
2. Toute modification du code doit etre relue a la lumiere de ces regles avant application.
3. Toute contradiction entre le code et ce document doit etre signalee explicitement.
4. Aucun changement strategique implicite ne doit etre introduit dans un patch technique.
5. Les changements doivent etre faits par microtouches : petits, lisibles, testables et reversibles.
6. Pas de refonte globale sans diagnostic prealable et accord explicite.
7. Pas de correction opportuniste qui modifie plusieurs comportements non relies.
8. Pas de patch sans sauvegarde ou point de retour clair.
9. Pas de trade sans preuve suffisante dans les signaux, les logs ou l'etat broker.
10. Le bot ne doit pas devenir une accumulation confuse de corrections contradictoires.

### B. Securite operationnelle avant patch

11. Avant toute modification importante, verifier l'absence de positions ouvertes.
12. Avant toute modification importante, verifier l'absence d'ordres pending.
13. Si necessaire, lancer ou consulter le script de reconciliation broker avant patch.
14. Ne pas modifier une logique d'execution pendant qu'un panier reel ou demo est actif, sauf urgence documentee.
15. L'etat local du bot ne doit jamais etre considere comme suffisant si l'etat broker n'a pas ete confirme.
16. En cas de divergence entre etat local et etat broker, l'etat broker prime.
17. Toute incertitude sur un risque broker doit bloquer le patch ou declencher une alerte explicite.

### C. Signaux et timeframes

18. Le signal maitre de la V2446 est le M15.
19. Le M5 sert de confirmation au signal M15.
20. Le M1 ne doit pas devenir le signal principal.
21. Le M1 peut aider au timing fin, mais ne doit pas inverser la doctrine M15/M5.
22. Le bot doit eviter les entrees impulsives de qualite insuffisante.
23. Une entree doit etre justifiee par un alignement clair entre signal maitre et confirmation.
24. Un signal faible, ambigu ou contradictoire ne doit pas forcer un trade.
25. Les modifications de scoring ne doivent pas abaisser silencieusement le niveau minimal de preuve.
26. Les logs de signaux doivent permettre de comprendre pourquoi un trade a ete accepte ou refuse.
27. Toute modification des signaux multi-timeframes doit etre documentee dans ce fichier ou soumise a validation.

### D. Paniers, legs et direction

28. La gestion des paniers est centrale dans BOT-PIVOT V2446.
29. Le nombre maximal de legs actifs dans un panier est 5.
30. La logique de leg doit tenir compte de l'adverse step.
31. La logique de leg doit tenir compte du prix courant.
32. La logique de leg doit tenir compte du niveau du panier.
33. La logique de leg doit tenir compte de la direction initiale du panier.
34. La logique de leg doit tenir compte de l'etat broker reel.
35. A partir de L3, une verification directionnelle stricte est obligatoire.
36. A partir de L3, si l'alignement M15/M5 est rompu, le panier doit etre coupe immediatement.
37. A partir de L3, il ne faut pas attendre le stop global si la direction strategique est invalidee.

### E. Retournements, FLAT et hedging false

38. Aucun passage direct d'un panier SELL a un panier BUY ne doit etre effectue sans retour prealable a un etat FLAT reel.
39. Aucun passage direct d'un panier BUY a un panier SELL ne doit etre effectue sans retour prealable a un etat FLAT reel.
40. L'etat FLAT doit etre confirme cote broker, pas seulement suppose cote bot.
41. `hedgingMode=False` interdit toute logique qui s'appuie sur une coexistence durable et non maitrisee de directions opposees.
42. Les locks, paniers opposes ou transitions directionnelles doivent etre traites comme des zones de risque eleve.

### F. Take profit, stops et PnL

43. Le take profit n'est pas un TP fixe simple.
44. Le take profit doit etre dynamique et progressif selon le nombre de legs actifs.
45. Regle TP validee : 2 legs -> +1 EUR, 3 legs -> +2 EUR, 4 legs -> +4 EUR, 5 legs -> +8 EUR.
46. Le stop L1 est autour de -3 EUR.
47. La perte panier maximale est autour de -15 EUR.
48. Le time stop est de 14 400 secondes.
49. Les calculs de PnL doivent rester realistes et compatibles Capital.com : BUY sorti au BID, SELL sorti a l'ASK.
50. Si le broker fournit un `upl` fiable, il doit etre considere comme source prioritaire de verite pour la fermeture.

### G. Logs, diagnostics et tests

Les logs doivent permettre de reconstruire les decisions de trading, distinguer
signal maitre, confirmation, timing et execution, et montrer les raisons d'entree,
de refus, d'ajout de leg et de fermeture de panier.

Les tests doivent couvrir en priorite les zones modifiees, avec non-regression
strategique lorsque la modification touche les signaux, paniers, PnL, stops,
fermetures, execution broker ou logs.

Le resume final d'une intervention doit lister : intention, fichiers touches,
tests effectues, risques residuels et prochaine verification recommandee.

## 4. Interdictions Strategiques

Sont interdits sans validation explicite :

- Transformer M1 en signal principal.
- Abaisser silencieusement les filtres de qualite d'entree.
- Autoriser un retournement direct BUY/SELL ou SELL/BUY sans FLAT broker confirme.
- Depasser 5 legs actifs.
- Supprimer la verification directionnelle stricte a partir de L3.
- Remplacer le TP dynamique par un TP fixe simple.
- Ignorer le BID/ASK dans les calculs de PnL.
- Ignorer un `upl` broker fiable au profit d'un calcul local moins fiable.
- Modifier les fermetures broker sans test ou diagnostic.
- Faire une refonte large sous couvert d'un correctif ponctuel.

## 5. Protocole Codex Avant Modification

Avant tout patch significatif, Codex doit appliquer cette sequence :

- Lire ce fichier.
- Identifier la regle concernee.
- Lire le code existant avant de proposer une solution.
- Verifier si le patch touche les signaux, paniers, broker, PnL, stops ou logs.
- Si oui, classer le patch en risque moyen ou eleve.
- Verifier l'absence de positions ou pending orders si le contexte live/demo est
  accessible.
- Faire une sauvegarde ou confirmer le point de retour disponible.
- Appliquer une microtouche limitee.
- Produire un diff clair.
- Lancer les tests pertinents ou expliquer pourquoi ils ne peuvent pas etre lances.
- Resumer l'impact et les risques residuels.

## 6. Protocole De Synchronisation ChatGPT / Codex

Quand une decision strategique est prise dans ChatGPT :

- Ajouter ou modifier la regle correspondante dans ce fichier.
- Copier la version a jour dans le dossier BOT-PIVOT utilise par Codex.
- Demander a Codex de relire le fichier avant toute intervention.

Quand Codex decouvre une contradiction dans le code :

- Ne pas corriger silencieusement si la contradiction est strategique.
- Signaler la contradiction.
- Proposer une microtouche de correction.
- Attendre validation si la correction change le comportement strategique.

Quand Codex applique un patch :

- Garder le diff court.
- Garder les noms, structures et conventions existantes autant que possible.
- Ne pas repartir a zero.
- Ne pas casser ce qui fonctionne deja.
- Documenter le test et la verification.

## 7. Checklist Rapide Avant Session

```text
[ ] Le fichier maitre est-il a jour ?
[ ] Le dossier de travail est-il le bon ?
[ ] Le bot tourne-t-il actuellement dans tmux ?
[ ] Y a-t-il des positions ouvertes ?
[ ] Y a-t-il des ordres pending ?
[ ] Le broker est-il reconcilie avec l'etat local ?
[ ] Le patch touche-t-il signaux, paniers, PnL, stops, broker ou logs ?
[ ] Une sauvegarde ou un point de retour existe-t-il ?
[ ] Le test minimal est-il defini ?
[ ] Le diff final sera-t-il court et lisible ?
```

## 8. Commandes De Reference

Aller dans le dossier live :

```bash
cd /home/philippe_vacher06/bot-pivot/live
```

Activer l'environnement :

```bash
source venv/bin/activate
```

Lancer une version scalp active :

```bash
./run_BOT_PIVOT_07D_SCALP_ACTIVE.sh
```

Lancer une version demo 24/7 :

```bash
./run_BOT_PIVOT_07D_24_7_DEMO.sh
```

Consulter les sessions tmux :

```bash
tmux ls
```

Entrer dans une session tmux :

```bash
tmux attach -t <nom_session>
```

## 9. Principe Final

BOT-PIVOT V2446 doit etre stabilise par preuves, microtouches et verifications.
La vitesse de codage n'est pas l'objectif principal. L'objectif principal est de
maintenir une chaine de travail fiable entre strategie, code, broker, logs et tests.
