# CR FIN DE SESSION GPT — V2446 H001/H002 — 2026-05-18 SOIR

## Objet

Compte-rendu court de fin de session pour reprise avec Codex le 2026-05-19 matin.

Travail réalisé : audit prix WebSocket/REST, relance H001/H002, diagnostic H002 DE40/US30, identification du prochain blocage opérationnel.

## Règle de session

Aucune doctrine modifiée.
Aucune règle maîtresse modifiée.
Aucun patch stratégique validé.
Les corrections réalisées ce soir sont des corrections locales d’audit / exécution, à reprendre proprement par Codex.

## État technique validé

### 1. WebSocket relancé

Le flux `BOT_PIVOT_03_tick_stream.py` a été relancé sur les 4 actifs prioritaires :

- US500 ;
- US100 ;
- DE40 ;
- US30.

Les ticks live sont bien écrits dans :

```text
data/ticks/ticks_20260518.jsonl
```

### 2. Audit price truth corrigé localement

L’outil local :

```text
tools/V2446_price_pnl_truth_audit.py
```

a reçu deux corrections locales :

```text
V2446_PRICE_TRUTH_JSONL_TICKS_FIX
V2446_PRICE_TRUTH_SNAPSHOT_WITHOUT_POSITION
```

Objectif : lire les ticks `.jsonl` live et produire un snapshot prix même sans position ouverte.

Validation locale :

```text
WS_KEYS = ['DE40', 'US100', 'US30', 'US500']
```

### 3. Concordance prix WS/REST validée techniquement

Nouveau log :

```text
logs/price_truth/V2446_PRICE_TRUTH_AUDIT_20260518_221212.jsonl
```

État observé :

```text
PRICE_TRUTH_SNAPSHOT
ws_status = OK
ws_source_file = data/ticks/ticks_20260518.jsonl
```

Les écarts WS/REST sont globalement faibles. Des écarts ponctuels apparaissent sur US100, DE40 ou US30, mais ils sont cohérents avec un décalage instantané entre dernier tick WebSocket et appel REST.

Décision technique :

```text
Prix bot ↔ REST Capital.com : VALIDÉ techniquement, sous réserve de latence instantanée.
```

La comparaison visuelle avec la plateforme Capital.com reste à confirmer.

### 4. PnL

Le calcul local brut prix × taille n’est pas directement comparable au `broker_upl`, probablement à cause de la valorisation broker / conversion devise.

Décision maintenue :

```text
broker_upl reste la source de vérité TP/STOP.
```

## Relance H001

Session active :

```text
v2446_h001
```

État observé :

- H001 tourne ;
- US500/US100 alignés en BUY ;
- pas de position ouverte ;
- cooldown FLAT actif ;
- aucun crash relevé.

Exemple d’état :

```text
RUNNER_V2446J_BTC_M5_FILTER | asset=US500 | confirm_asset=US100 | m15_bias=BUY | btc_m5_bias=BUY | aligned=True
RUNNER_BASKET_DECISION | reasons=['NO_MAIN_ASSET_POSITION']
RUNNER_RESET_COOLDOWN_ACTIVE
```

Statut H001 :

```text
H001 lancé / à surveiller demain.
```

## Relance H002

Session active :

```text
v2446_h002_de40_us30
```

État observé :

- H002 tourne ;
- DE40/US30 alignés en BUY ;
- login OK ;
- compte Capital.com en netting confirmé : `hedgingMode=False` ;
- aucune position ouverte ;
- cooldown FLAT actif après relance.

Exemple d’état :

```text
RUN V2446 LIVE ISOLATED DE40/US30
RUNNER_V2446I_CASCADE_RULES_ACTIVE | asset=DE40
RUNNER_V2446J_BTC_M5_CONFIRM_ACTIVE | confirm_asset=US30
RUNNER_LOGIN_OK | asset=DE40
RUNNER_ACCOUNT_MODE | hedgingMode=False
RUNNER_RESET_COOLDOWN_STARTED | reason=BROKER_FLAT_EXPOSURE
```

Statut H002 :

```text
H002 lancé / ne plante pas.
```

## Blocage H002 identifié

Avant la dernière relance, H002 tentait bien d’ouvrir DE40 BUY, mais Capital.com rejetait les ordres.

Payload observé :

```text
guaranteedStop=True
stopDistance=25.0
```

Erreur broker répétée :

```text
error.invalid.stoploss.maxvalue
```

Conclusion :

```text
Le stop garanti DE40 à 25 points est rejeté par Capital.com.
```

Hypothèse opérationnelle :

```text
DE40 nécessite un stop garanti plus large, probablement autour de 40 points ou plus.
```

## Micro-correction proposée localement

Correction proposée côté script H002 uniquement :

```text
run_V2446_ADVERSE_STEPS_DE40_US30.sh
```

Paramètre ciblé :

```text
export V244_STOP_DISTANCE=25
```

Proposition :

```text
export V244_STOP_DISTANCE=40
```

Important : au moment de l’arrêt de session, le test effectif d’un nouvel ordre avec `stopDistance=40` n’est pas encore validé, car H002 était en `RESET_COOLDOWN_ACTIVE`.

Il faut donc vérifier demain :

```text
1. que la config H002 contient bien V244_STOP_DISTANCE=40 ;
2. que le startup log affiche stop_distance=40.0 ;
3. que le prochain NETTING_OPEN_REQUEST contient stopDistance=40.0 ;
4. que le broker ne renvoie plus error.invalid.stoploss.maxvalue ;
5. si 40 est encore rejeté, tester 50.
```

## L4 cross-hedge

La correction locale précédente du contexte/headers L4 a été appliquée et compilée avec succès.

Mais le L4 n’a pas encore été retesté en réel ce soir, car H002 ne parvient pas encore à ouvrir L1 DE40 à cause du rejet broker sur stop garanti.

Statut :

```text
L4 cross-hedge : correction locale prête, validation réelle en attente.
```

## Points d’attention Codex demain matin

### Priorité 1 — stabiliser H002 DE40

Vérifier / corriger :

```text
run_V2446_ADVERSE_STEPS_DE40_US30.sh
V244_STOP_DISTANCE=40
```

Puis relancer H002 et observer le premier ordre DE40.

Critère PASS :

```text
RUNNER_NETTING_OPEN_RESPONSE status=200
```

ou au minimum :

```text
plus d’erreur error.invalid.stoploss.maxvalue
```

### Priorité 2 — nettoyer les libellés hérités

Les logs utilisent encore des libellés historiques ETH/BTC ou BTC_M5 alors que les actifs sont DE40/US30 ou US500/US100.

Exemples :

```text
RUNNER_V2446J_BTC_M5_FILTER
ETH_BTC_VWAP_ALIGNED_BTC_M5_ALIGNED
eth_bias / btc_bias
```

Ce n’est pas bloquant pour l’exécution, mais c’est gênant pour l’audit.

À renommer plus tard en :

```text
MAIN_CONFIRM_M15_ALIGNED
CONFIRM_M5_ALIGNED
main_bias / confirm_bias
```

### Priorité 3 — garder price_truth actif

Conserver :

```text
v2446_tick_stream
v2446_price_truth
```

afin de surveiller en continu :

```text
PRICE_TRUTH_SNAPSHOT
ws_status=OK
gap_bid_ws_rest
gap_ask_ws_rest
```

### Priorité 4 — ne pas patcher la stratégie avant preuve

Avant toute modification stratégique, vérifier :

- ordre broker accepté ;
- position réellement ouverte ;
- `broker_upl` lu correctement ;
- TP/STOP basés sur `broker_upl` ;
- L4 cross-hedge déclenché seulement après conditions prévues.

## État final de fin de soirée

```text
WebSocket : OK
Price truth : OK
Prix WS/REST : OK
H001 : lancé, cooldown FLAT actif
H002 : lancé, cooldown FLAT actif
Blocage H002 précédent : stop garanti DE40 trop proche à 25
Patch proposé : stopDistance DE40 à 40, test réel encore à confirmer
L4 cross-hedge : non retesté en réel
GitHub code : non modifié
Doctrine : non modifiée
```

## Reprise demain matin

Commande de reprise utile :

```bash
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate

tmux ls

grep -nE "V244_GUARANTEED_STOP|V244_STOP_DISTANCE" run_V2446_ADVERSE_STEPS_DE40_US30.sh

grep -RIn "NETTING_OPEN_REQUEST|NETTING_OPEN_RESPONSE|OPEN_RESULT|invalid.stoploss|dealReference|dealId|PRICE_TRUTH_SNAPSHOT|Traceback|ERROR" \
logs/v24_4_forced_audit_DE40_US30 logs/v24_4_forced_audit logs/price_truth/*.jsonl | tail -160
```

Décision de fin de session :

```text
Arrêt analyse ce soir.
Reprise demain matin avec Codex sur H002 stopDistance DE40 et validation réelle du prochain ordre.
```
