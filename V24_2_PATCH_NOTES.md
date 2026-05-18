# BOT-PIVOT V24.2 — BOLLINGER / MARGIN / LEVEL GUARD

Version préparée depuis l'archive V24.1 `BOT_PIVOT_V24_1_SOURCE_BEFORE_V24_2_20260513_194416.tar.gz`.

## Principe conservé

- Le patch `V24_BROKER_UPL_TP_PATCH_V1` est conservé.
- Le TP panier reste validé uniquement par `Capital.com position.upl`.
- Aucun TP broker individuel par jambe ne doit être ajouté.
- La logique LIMIT L1/L2/L3, `BASKET_KEEP`, stop broker airbag et annulation pending sont conservées.

## Corrections V24.2 installées

### 1. Clamp Bollinger neutralisé

`BOLLINGER_SCALP_CLAMP` ne rapproche plus L1 vers le prix courant.

Nouveau comportement :

- le niveau Bollinger brut est conservé ;
- si L1 est trop loin du marché, le panier est rejeté ;
- log attendu : `BASKET_REJECT_BOLLINGER_TOO_FAR`.

### 2. Anti-LIMIT marketable

Avant tout envoi broker, la fonction `v242_validate_bollinger_limit_levels()` vérifie :

BUY :

- `L1 < bid - gap`
- `L2 <= L1 - min_step`
- `L3 <= L2 - min_step`

SELL :

- `L1 > ask + gap`
- `L2 >= L1 + min_step`
- `L3 >= L2 + min_step`

Logs possibles :

- `BASKET_REJECT_MARKETABLE_LIMIT`
- `BASKET_REJECT_LEVELS_COLLAPSED`
- `BASKET_REJECT_BAD_LIMIT_LEVELS`
- `BASKET_REJECT_PRICE_AUDIT_FAIL`

### 3. PRICE_AUDIT complet

Avant `LIMIT_REQUEST`, le bot logue :

- stream bid/ask
- snapshot bid/ask Capital.com
- BB basse / médiane / haute M5
- L1/L2/L3
- raw_L1 / final_L1
- distance L1 au marché
- niveau payload envoyé

Log attendu : `PRICE_AUDIT` / événement `V242_PRICE_AUDIT`.

### 4. Garde-fou marge globale

Avant nouveau panier :

- si marge estimée >= `MAX_MARGIN_CFD_EUR` → rejet ;
- si disponible < `MIN_AVAILABLE_TO_TRADE_EUR` → rejet.

Valeurs par défaut :

```bash
MAX_MARGIN_CFD_EUR=3000
MIN_AVAILABLE_TO_TRADE_EUR=500
```

Logs :

- `BASKET_REJECT_MARGIN_GUARD`
- `MARGIN_GUARD_CANCEL_PENDING`

La marge utilisée est estimée par :

```text
balance/account value - available
```

### 5. Nettoyage pending sous pression marge

Si un panier actif garde des LIMIT en attente et que la marge est sous pression :

- le bot annule les LIMIT restants ;
- il conserve les jambes ouvertes ;
- si aucune jambe n'est ouverte, il remet le cycle à IDLE.

### 6. OIL_CRUDE réduit

Dans `BOT_PIVOT_00_config.py` :

```python
"OIL_CRUDE": 4
```

au lieu de 12.

### 7. Guard LIMIT non-mutant

`v24sa_guard_limit_side()` ne déplace plus automatiquement un niveau LIMIT. En V24.2, le bot rejette avant envoi plutôt que de corriger un mauvais prix.

## Variables utiles

```bash
MAX_MARGIN_CFD_EUR=3000
MIN_AVAILABLE_TO_TRADE_EUR=500
V242_MARGIN_GUARD_ENABLED=1
V242_LEVEL_MIN_STEP_RATIO=0.80
```

## Contrôle avant relance

Côté state local :

```text
CYCLE non-IDLE = []
EXEC active    = []
```

Côté Capital.com :

```text
Positions ouvertes : 0
Ordres en attente  : 0
```

## Contrôle logs après relance

À surveiller :

```bash
grep -nE "PRICE_AUDIT|BASKET_REJECT_BOLLINGER_TOO_FAR|BASKET_REJECT_MARKETABLE_LIMIT|BASKET_REJECT_LEVELS_COLLAPSED|BASKET_REJECT_MARGIN_GUARD|MARGIN_GUARD_CANCEL_PENDING|BASKET_TP_OK|BASKET_TP_BLOCKED|Traceback|ERROR|Exception" logs/BOT_PIVOT_07D_24_7_DEMO_*.log | tail -300
```
