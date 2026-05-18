# NOTE H-002 — Controle prix / PnL / WebSocket

Date : 2026-05-18

## Paire H-002 concernee

```text
H-002 = DE40 principal / US30 confirmation-hedge
Script local : run_V2446_ADVERSE_STEPS_DE40_US30.sh
Runner observe : BOT_PIVOT_24_4_forced_audit_runner.py
Session tmux observee : v2446_h002_de40_us30
```

## Travail effectue par GPT en substitution temporaire Codex

Un diagnostic local a ete cree pour verifier la verite prix / PnL sans modifier la strategie :

```text
tools/V2446_price_pnl_truth_audit.py
logs/price_truth/
```

Le diagnostic couvre les actifs :

```text
US500, US100, DE40, US30
```

Donc H-002 est incluse dans le controle.

## Donnees loggees

Pour chaque position ouverte, le diagnostic logge :

```text
asset
side
dealId
size
entry_broker
ws_bid / ws_ask / ws_mid
rest_bid / rest_ask / rest_mid
broker_upl
pnl_local_bid_ask
gap_broker_local
tp_decision_basis
```

## Regle de calcul verifiee

```text
BUY  : sortie theorique au BID
SELL : sortie theorique a l ASK
```

Le PnL local ne doit pas valider seul un TP.

Regle critique :

```text
broker_upl = source de verite
TP autorise seulement si broker_upl confirme le gain
```

## Resultat observe

Le controle REST / broker fonctionne.

Le diagnostic recupere correctement :

```text
entry_broker
rest_bid
rest_ask
broker_upl
pnl_local_bid_ask
gap_broker_local
```

Mais le WebSocket local est absent dans l etat actuel :

```text
ws_status = MISSING
ws_bid = null
ws_ask = null
ws_mid = null
```

Cause identifiee :

```text
BOT_PIVOT_03_tick_stream.py ne tourne pas actuellement.
Les process actifs montrent les runners V2446, mais pas le module tick stream.
```

## Action suivante proposee

Lancer le flux tick/WebSocket separement, sans modifier la strategie :

```bash
cd /home/philippe_vacher06/bot-pivot/live
source venv/bin/activate
set -a
source .env
set +a

python3 BOT_PIVOT_03_tick_stream.py --assets "US500,US100,DE40,US30" --seconds 999999 --print-every 5
```

Puis verifier :

```bash
find data/ticks -type f -mmin -5 -ls
tail -5 data/ticks/ticks_*.jsonl
```

## Statut

```text
H-002 incluse dans l audit prix / PnL.
Aucune modification strategique.
Aucun changement de seuil.
Aucune nouvelle paire.
Priorite restante : retablir la source WebSocket live.
```
