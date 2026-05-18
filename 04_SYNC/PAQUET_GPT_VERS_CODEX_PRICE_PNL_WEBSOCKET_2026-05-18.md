# PAQUET GPT VERS CODEX — V2446 PRICE / PNL / WEBSOCKET

Date : 2026-05-18

## Objet

Centraliser le travail realise dans le chat GPT sur le controle prix / PnL / WebSocket du BOT-PIVOT V2446.

But : permettre a Codex de reprendre le diagnostic sans relire tout le chat.

## Paires concernees

```text
H-001 : US500 principal / US100 confirmation-hedge
H-002 : DE40 principal / US30 confirmation-hedge
```

Scripts locaux observes :

```text
run_V2446_ADVERSE_STEPS_US500_US100.sh
run_V2446_ADVERSE_STEPS_DE40_US30.sh
```

Runner actif observe :

```text
BOT_PIVOT_24_4_forced_audit_runner.py
```

## Regle absolue

```text
broker_upl = source de verite
```

Le PnL local ne doit jamais valider seul un TP.

```text
TP autorise seulement si broker_upl confirme le gain.
```

## Regles prix / PnL

```text
BUY  : entree broker au ASK / sortie theorique au BID
SELL : entree broker au BID / sortie theorique a l ASK
```

Le MID ne doit pas servir a valider le TP.

## Diagnostic local cree par GPT

Fichier local cree :

```text
tools/V2446_price_pnl_truth_audit.py
```

Dossier de logs :

```text
logs/price_truth/
```

Backup cree lors du patch V2 :

```text
tools/V2446_price_pnl_truth_audit_V1_BACKUP.py
```

Actifs couverts :

```text
US500, US100, DE40, US30
```

Donc H-001 et H-002 sont inclus dans l audit.

## Donnees loggees par position ouverte

```text
ts
event
asset
epic
side
dealId
size
entry_broker
ws_bid
ws_ask
ws_mid
ws_age_sec
ws_source_file
ws_status
rest_bid
rest_ask
rest_mid
broker_upl
pnl_local_bid_ask
gap_broker_local
tp_decision_basis
```

## Formule locale utilisee

```text
BUY  : pnl_local_bid_ask = (current_bid - entry_broker) * size
SELL : pnl_local_bid_ask = (entry_broker - current_ask) * size
```

## Resultat V1

Le diagnostic a correctement recupere :

```text
entry_broker
rest_bid
rest_ask
rest_mid
broker_upl
pnl_local_bid_ask
gap_broker_local
```

Exemple observe sur US500 SELL :

```text
entry_broker = 7362.4
rest_ask = 7363.8
size = 0.14
broker_upl = -0.17
pnl_local_bid_ask = -0.196
gap_broker_local = 0.026
```

Lecture : calcul SELL coherent car sortie theorique a l ASK.

## Probleme V1

Les champs WebSocket etaient vides :

```text
ws_bid = null
ws_ask = null
ws_mid = null
```

Le fichier initialement lu etait :

```text
data/ticks/signals_latest.json
```

Mais il etait stale :

```text
created_utc = 2026-05-16T08:33:14+00:00
signal US500 = NO_TICKS
```

Conclusion : `signals_latest.json` n est pas une source WebSocket live valide dans l etat actuel.

## Patch V2 applique localement

Objectifs :

```text
1. Chercher plusieurs JSON recents dans data/ticks.
2. Ajouter ws_status.
3. Ajouter ws_source_file.
4. Eviter plusieurs appels REST par position : 1 seul REST par actif par cycle.
```

Resultat technique :

```text
PATCH_V2_OK
Compilation Python OK
```

## Resultat V2

Le diagnostic fonctionne toujours pour REST / broker / PnL local.

Mais WebSocket reste absent :

```text
ws_status = MISSING
ws_bid = null
ws_ask = null
ws_mid = null
ws_source_file = null
```

Exemple observe :

```text
asset = US500
side = SELL
entry_broker = 7384.4
rest_bid = 7385.9
rest_ask = 7386.3
broker_upl = -0.13
pnl_local_bid_ask = -0.152
gap_broker_local = 0.022
ws_status = MISSING
```

## Verification des fichiers ticks

Aucun fichier tick live recent n a ete trouve dans `data/ticks`.

Fichiers recents observes seulement cote execution :

```text
data/execution/V2442_NETTING_STATE_DE40.json
data/execution/V2442_NETTING_STATE_US500.json
data/execution/v2446_adverse_steps_state_US500.json
```

## Verification des process actifs

Process observes :

```text
run_V2446_ADVERSE_STEPS_US500_US100.sh
BOT_PIVOT_24_4_forced_audit_runner.py
run_V2446_ADVERSE_STEPS_DE40_US30.sh
BOT_PIVOT_24_4_forced_audit_runner.py
tools/V2446_price_pnl_truth_audit.py
```

Process absent :

```text
BOT_PIVOT_03_tick_stream.py
```

Conclusion :

```text
Le WebSocket tick stream ne tourne pas actuellement.
```

## Sessions tmux observees

```text
bot_live
price_truth
v2446_h001
v2446_h002_de40_us30
```

## Action suivante pour Codex

Relancer ou reintegrer proprement le flux tick/WebSocket pour les actifs :

```text
US500, US100, DE40, US30
```

Puis verifier que le diagnostic affiche :

```text
ws_status = OK
```

et que les fichiers ticks sont de nouveau alimentes dans :

```text
data/ticks/
```

## Statut final

```text
Diagnostic prix / PnL cree localement.
H-001 et H-002 inclus.
REST Capital.com OK.
Positions broker OK.
broker_upl OK.
pnl_local_bid_ask OK.
gap broker/local OK.
WebSocket local MISSING car tick_stream absent.
Aucune modification strategique.
Aucun seuil modifie.
Aucune nouvelle paire ajoutee.
```

## Fichier GitHub deja cree pour H-002

```text
04_SYNC/NOTE_H002_PRICE_TRUTH_AUDIT_2026-05-18.md
```

Commit associe :

```text
47f5ea0bb05101fd3dfe2cf36b4d573a77a37247
```
