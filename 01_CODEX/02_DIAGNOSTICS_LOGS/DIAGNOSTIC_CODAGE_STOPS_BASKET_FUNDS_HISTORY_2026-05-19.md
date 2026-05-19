# Diagnostic Codage Stops Basket - funds history

Date : 2026-05-19
Statut : diagnostic bloquant avant patch

## Objet

Verifier le signalement utilisateur :

```text
le codage n'est pas bon, les stops ne sont pas bons, le declenchement Basket
n'est pas bon
```

Source utilisateur analysee :

```text
C:\Users\phila\Downloads\funds_history_18.05.2026-19.05.2026.csv
```

Contraintes appliquees :

- aucun code modifie ;
- aucun test serveur lance ;
- aucune action SSH effectuee ;
- analyse locale CSV + lecture GitHub du code versionne uniquement.

## Resume CSV

Le fichier contient 94 lignes `TRADE` traitees entre le 2026-05-18 et le
2026-05-19 UTC.

| Actif | Lignes | Somme EURd | Min | Max | Negatives | Observation |
|---|---:|---:|---:|---:|---:|---|
| DE40 | 40 | -4.40 | -3.20 | 1.56 | 22 | pertes repetees, stop douteux |
| US500 | 17 | -9.70 | -4.17 | 1.18 | 11 | perte individuelle sous -3 EUR |
| US100 | 31 | 38.75 | -0.15 | 7.85 | 1 | 30 clotures dans la meme seconde |
| US30 | 6 | 0.61 | -0.49 | 1.13 | 3 | 6 clotures en 80 ms environ |

Signaux forts :

- `US100` : 30 lignes a `2026-05-19 08:36:39 UTC`, total environ `+30.90 EURd`.
- `US30` : 6 lignes entre `2026-05-19 08:36:32.934593 UTC` et
  `08:36:33.013656 UTC`.
- `US500` : cloture `-4.17 EURd` a `2026-05-19 07:46:58 UTC`.
- `DE40` : cloture `-3.20 EURd` a `2026-05-19 00:04:07 UTC`.

Conclusion CSV :

```text
Le comportement observe n'est pas compatible avec un hedge unique proprement
verrouille. Il ressemble a un declenchement repete ou a une fermeture Basket
qui agit sur un groupe de positions deja accumulees.
```

## Code GitHub relu

Fichiers relus :

- `run_V2446_ADVERSE_STEPS_US500_US100.sh`
- `BOT_PIVOT_24_4_forced_audit_runner.py`
- `v2446_adverse_steps_patch.py`
- `BOT_PIVOT_06G2_execution_secure.py`
- `BOT_PIVOT_06G_execution_from_cycle_state.py`
- `04_SYNC/NOTE_H002_PRICE_TRUTH_AUDIT_2026-05-18.md`

Le fichier `run_V2446_ADVERSE_STEPS_DE40_US30.sh` n'est pas present dans GitHub
`main` au moment de la lecture, alors que la note H002 indique un script local
observe sous ce nom. H002 ne peut donc pas etre auditee completement sans SSH ou
sans importer le script exact.

## Constats de codage

### 1. Le hedge L4 US100 contourne les verrous du runner

Dans `v2446_adverse_steps_patch.py`, quand `len(ps) >= 3`, le patch ouvre un
hedge US100 directement :

```text
hedge_asset = "US100"
hedge_side = SELL si panier BUY, sinon BUY
hedge_size = 0.08
requests.post(... /positions ...)
forceOpen = True
```

Problemes :

- aucun controle d'une L4 US100 deja ouverte ;
- aucun verrou "un seul hedge" ;
- aucun controle `broker_upl` cumule US500+US100 avant ouverture ;
- aucune verification que le prix/PnL H001 est PASS ;
- bypass de `open_market_netting_safe` et donc des gardes spread/marge/rate/director ;
- `forceOpen=True` alors que la doctrine projet rappelle `hedgingMode=False` ;
- stop hard-code en prix `hedge_price +/- 150`, pas en PnL broker cumule.

Ce point explique plausiblement la rafale `US100` du CSV.

### 2. Le TP dynamique Basket est calcule trop tard

Dans `BOT_PIVOT_24_4_forced_audit_runner.py`, la fermeture Basket V2446I teste
d'abord :

```text
if count > 0 and total_upl >= tp:
    close_reason = "BASKET_TAKE_PROFIT_REACHED"
```

Ensuite seulement, si `close_reason is None`, le code recalcule le TP dynamique :

```text
count == 1 -> tp = 1.00
count == 2 -> tp = 2.00
count == 3 -> tp = 4.00
count >= 4 -> tp = 1.00
```

Problemes :

- le seuil reel de fermeture est le `tp` initial, souvent `V2446I_BASKET_TAKE_PROFIT_EUR=1`,
  pas le TP dynamique attendu pour 2 ou 3 jambes ;
- le bloc TP dynamique est duplique deux fois ;
- la decision de fermeture peut donc partir trop tot ;
- la logique ne prouve pas qu'elle cumule le hedge avec le principal.

Ce point explique un declenchement Basket non conforme.

### 3. Les stops ne sont pas alignes sur la doctrine PnL broker cumule

Le runner US500/US100 exporte :

```text
V2446I_L1_STOP_LOSS_EUR=3
V2446I_BASKET_MAX_LOSS_EUR=15
V244_STOP_DISTANCE=25
```

Mais plusieurs chemins de code utilisent encore des stops de prix broker :

- `stopDistance=STOP_DISTANCE` dans l'ouverture marche du runner ;
- `stopLevel = hedge_price +/- 150` dans le hedge direct US100 ;
- airbag global par distance de prix dans `BOT_PIVOT_06G2_execution_secure.py`.

La doctrine attend :

```text
BUY controle au BID
SELL controle a l'ASK
decision finale TP/stop/sortie sur broker_upl reel cumule
```

Le CSV montre des pertes individuelles sous le stop L1 attendu autour de
`-3 EUR` :

- US500 `-4.17 EURd` ;
- DE40 `-3.20 EURd`.

Ces lignes ne prouvent pas seules le chemin de code exact, mais elles confirment
que les stops doivent etre consideres NON CONFORMES tant que le lien avec
`broker_upl` cumule n'est pas prouve.

### 4. Le garde-fou de frequence est pratiquement desactive

Le runner H001 exporte :

```text
V244_TARGET_OPENINGS_PER_MIN=99999
```

Donc le rate limiter ne protege presque plus contre une rafale. Si le verrou
adverse-step ou hedge L4 se trompe, le runner peut accumuler des ordres.

### 5. L'identite d'actif est fragile

Dans `BOT_PIVOT_24_4_forced_audit_runner.py`, `_v2446i_asset()` tente de changer
l'actif vers `US100` en inspectant les frames Python et une variable locale
historique `eth_positions`.

Problemes :

- l'actif logique depend d'un nom de variable et du contexte d'appel ;
- le runner reste fortement marque par l'ancien vocabulaire ETH/BTC ;
- le filtrage des positions peut changer selon la pile d'appel ;
- cela rend le calcul Basket/PnL/stop difficile a auditer.

## Decision technique

Le signalement utilisateur est confirme.

Statut :

```text
CODAGE NON CONFORME / STOPS NON CONFORMES / DECLENCHEMENT BASKET NON CONFORME
```

Tout patch H001/H002 reste bloque tant que les points suivants ne sont pas
securises :

- audit prix/PnL H001/H002 PASS ;
- etat SSH/tmux/process verifie ;
- positions ouvertes et pending orders verifies ;
- script exact H002 `DE40/US30` recupere et versionne ;
- logs autour de `2026-05-19 08:36:32-39 UTC` recuperes ;
- microtouche de correction limitee definie avant edition.

## Microtouches a preparer, sans application immediate

Ordre recommande :

1. Bloquer toute ouverture L4 si une position hedge existe deja.
2. Supprimer l'ouverture directe `requests.post` du hedge et repasser par une
   fonction d'execution controlee.
3. Calculer le TP dynamique avant le test `total_upl >= tp`.
4. Cumuler explicitement le `broker_upl` principal + hedge pour TP/stop/sortie.
5. Remplacer le hack `_v2446i_asset()` par une configuration explicite
   `main_asset` / `hedge_asset`.
6. Retirer ou durcir `V244_TARGET_OPENINGS_PER_MIN=99999`.
7. Refuser tout patch H002 tant que `run_V2446_ADVERSE_STEPS_DE40_US30.sh` n'est
   pas relu depuis SSH ou GitHub.
