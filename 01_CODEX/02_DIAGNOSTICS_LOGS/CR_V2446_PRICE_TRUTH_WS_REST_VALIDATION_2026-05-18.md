# CR — V2446 PRICE TRUTH WS/REST VALIDATION — 2026-05-18

## Contexte

Après correction locale du bloc L4 cross-hedge, il restait un verrou prioritaire : valider la concordance des prix entre le bot et Capital.com avant toute nouvelle étape stratégique.

Objectif : vérifier que les prix utilisés par le bot sont cohérents avec les prix REST Capital.com, puis préparer la comparaison visuelle avec la plateforme.

## Problème initial

L’audit `tools/V2446_price_pnl_truth_audit.py` retournait des lignes avec :

```text
ws_bid = null
ws_ask = null
ws_mid = null
```

Le REST Capital.com répondait correctement, mais la partie WebSocket n’était pas validée.

## Diagnostic

Le flux WebSocket ne tournait plus au départ :

- aucun processus `BOT_PIVOT_03_tick_stream.py` actif ;
- `signals_latest.json` était ancien ;
- les anciens signaux indiquaient `NO_TICKS`.

Le flux a été relancé avec `BOT_PIVOT_03_tick_stream.py` sur les 4 actifs prioritaires :

```text
US500
US100
DE40
US30
```

Après relance, les ticks live ont bien été écrits dans :

```text
data/ticks/ticks_20260518.jsonl
```

## Correction locale de l’outil d’audit

L’outil `V2446_price_pnl_truth_audit.py` lisait les fichiers JSON classiques, mais pas correctement les ticks live JSONL.

Correction locale ajoutée :

```text
V2446_PRICE_TRUTH_JSONL_TICKS_FIX
```

Puis ajout d’un mode snapshot même sans position ouverte :

```text
V2446_PRICE_TRUTH_SNAPSHOT_WITHOUT_POSITION
```

Objectif : écrire un snapshot prix WebSocket/REST même lorsqu’aucune position n’est ouverte, afin de valider la concordance bot ↔ REST ↔ plateforme visible.

## Validation technique locale

Compilation validée :

```bash
python3 -m py_compile tools/V2446_price_pnl_truth_audit.py
```

Résultat :

```text
0
```

Test de lecture WebSocket validé :

```text
WS_KEYS = ['DE40', 'US100', 'US30', 'US500']
```

Les 4 actifs prioritaires sont bien lus depuis le fichier JSONL live.

## Résultat snapshot WS/REST

Nouveau log généré :

```text
logs/price_truth/V2446_PRICE_TRUTH_AUDIT_20260518_221212.jsonl
```

Résultats observés :

```text
US500 : gap BID/ASK/MID = 0.0 / 0.0 / 0.0
US100 : gap BID/ASK/MID = -0.4 / -0.4 / -0.4
DE40  : gap BID/ASK/MID = -0.2 / -0.2 / -0.2
US30  : gap BID/ASK/MID = 0.0 / 0.0 / 0.0
```

Interprétation :

- WebSocket bot : OK ;
- REST Capital.com : OK ;
- lecture JSONL live : OK ;
- snapshot sans position : OK ;
- écarts US100 et DE40 faibles, compatibles avec un léger décalage temporel entre tick WebSocket et appel REST.

## Statut prix

```text
Prix bot ↔ REST Capital.com : VALIDÉ techniquement
Prix bot ↔ plateforme visible : à confirmer visuellement
```

La comparaison plateforme visible reste à faire manuellement sur Capital.com avec BID/ASK affichés.

## Statut PnL

L’audit PnL a montré que le calcul local brut prix × taille n’est pas directement comparable au `broker_upl`, probablement à cause de la conversion devise / valorisation broker.

Décision maintenue :

```text
broker_upl reste la source de vérité pour TP/STOP.
```

Le PnL local brut ne doit pas déclencher les décisions critiques sans conversion contrôlée.

## Ce qui n’a pas été modifié

Aucune modification sur :

- doctrine V2446 ;
- règles maîtresses ;
- stratégie ;
- TP panier ;
- stop L1 ;
- stop panier ;
- tailles ;
- logique H001/H002 ;
- code GitHub.

Les corrections ont été appliquées localement dans le terminal de Philippe. Cette fiche documente l’intervention après validation explicite `OK VALIDATION GITHUB`.

## Étape suivante

1. Confirmer visuellement sur la plateforme Capital.com que les prix affichés sont cohérents avec le snapshot WS/REST.
2. Relancer H001/H002 sous surveillance contrôlée.
3. Surveiller en priorité :
   - `RUNNER_CROSS_HEDGE_TRIGGER` ;
   - `RUNNER_CROSS_HEDGE_EXECUTED` ;
   - absence de l’ancien blocage L4 ;
   - `broker_upl` utilisé comme vérité TP/STOP.

## Décision

Le verrou WebSocket/REST est levé techniquement.

La suite peut passer à la relance contrôlée H001/H002, sous réserve de la confirmation visuelle plateforme.
