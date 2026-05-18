# V2446I ETH-BTC Cascade Patch Kit

Ce kit applique les regles V2446I suivantes sur la VM, dans
`/home/philippe_vacher06/bot-pivot/live`.

## Regles codees

Parametres par defaut:

```text
V2446I_L1_MAX_MARGIN_EUR      = 10.0
V2446I_L1_STOP_LOSS_EUR       = 3.0
V2446I_BASKET_MAX_LOSS_EUR    = 15.0
V2446I_BASKET_TAKE_PROFIT_EUR = 5.0
V2446I_MAX_LEGS               = 5
V2446I_STEP_PCT               = 0.0007
V2446I_RESET_COOLDOWN_SEC     = 300
V2446I_TIME_STOP_SEC          = 14400
```

Logique:

```text
0 position ETH:
  ouverture L1 seulement via le flux existant BTC/ETH du runner
  blocage si cooldown actif

1 position ETH:
  total_upl <= -3 EUR => fermeture totale
  total_upl >= +5 EUR => fermeture totale

2 a 5 positions ETH:
  total_upl <= -15 EUR => fermeture totale
  total_upl >= +5 EUR => fermeture totale
  age panier > 4h et PnL < 0 => fermeture totale

Toutes phases:
  positions ETH >= 5 => aucun renfort
  signal inverse contre panier actif => bloque, pas de retournement direct
  step adverse dynamique = prix courant * 0.07 %
```

Exemples de step:

```text
prix 2000  => step 1.40
prix 6000  => step 4.20
prix 8000  => step 5.60
prix 2400  => step 1.68
prix 80    => step 0.056
prix 155   => step 0.1085
prix 1.08  => step 0.000756
```

## Doubles maitres

```text
ETHUSD    -> BTCUSD
US500     -> US100
FR40      -> DE40
EURUSD    -> GBPUSD
USDJPY    -> EURJPY
GOLD      -> SILVER
OIL_CRUDE -> OIL_BRENT/BRENT
J225      -> USDJPY
```

## Limite importante sur la marge L1

Le runner actuel ne montre pas, dans les extraits fournis, une fonction fiable de
pre-estimation de marge avant ouverture. Le patch ajoute donc un controle
configurable:

- si `V2446I_MARGIN_EUR_PER_1_SIZE` est defini, la marge estimee vaut
  `size * V2446I_MARGIN_EUR_PER_1_SIZE`;
- sinon le patch loggue que la marge est inconnue et applique le cap de taille
  `V2446I_L1_MAX_SIZE` si defini.

Pour une validation stricte de la marge 10 EUR, il faudra calibrer
`V2446I_MARGIN_EUR_PER_1_SIZE` avec les donnees Capital.com reelles.

## Installation sur la VM

Copier le contenu de ce dossier sur la VM dans le dossier live, puis:

```bash
cd /home/philippe_vacher06/bot-pivot/live
bash install_v2446i_cascade.sh
```

Le script:

1. sauvegarde les fichiers cibles;
2. applique les patchs;
3. compile les deux fichiers Python;
4. redemarre proprement le tmux runner;
5. affiche les logs de verification.

## Verification attendue

Chercher notamment:

```text
RUNNER_V2446I_CASCADE_RULES_ACTIVE
RUNNER_V2446I_DYNAMIC_STEP ... step_pct=0.0007
RUNNER_ETH_BASKET_DECISION ... tp=5.0 ... max_open_positions=5
RUNNER_V2446I_OPEN_BLOCKED_MAX_LEGS
RUNNER_V2446I_HARD_CLOSE_ALL_START
RUNNER_V2446I_HARD_CLOSE_RESULT
RUNNER_V2446I_HARD_CLOSE_ALL_DONE
RUNNER_RESET_COOLDOWN_ACTIVE
```

Si `Traceback`, `RUNNER_EXCEPTION`, `TypeError` ou `NameError` apparait,
ne pas continuer: coller les logs pour diagnostic.
