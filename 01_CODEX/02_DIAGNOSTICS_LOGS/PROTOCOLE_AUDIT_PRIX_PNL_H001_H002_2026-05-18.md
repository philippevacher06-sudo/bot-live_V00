# Protocole Audit Prix / PnL H001 H002

Date : 2026-05-18
Statut : protocole bloquant avant patch

## Objet

Etablir la verite prix et PnL pour H001 et H002 avant toute modification de code,
test serveur ou action SSH supplementaire.

Strategies concernees :

| ID | Principal | Confirmation / hedge |
|---|---|---|
| H001 | US500 | US100 |
| H002 | DE40 | US30 |

## Sources lues

- `04_SYNC/NOTE_H001_PRICE_VALIDATION_BLOCKER_2026-05-18.md` depuis GitHub.
- `04_SYNC/NOTE_H002_PRICE_TRUTH_AUDIT_2026-05-18.md` depuis GitHub.
- `01_CODEX/02_DIAGNOSTICS_LOGS/DIAGNOSTIC_PRIX_BOT_LOCAL_VS_PLATEFORME_2026-05-18.md` depuis GitHub et miroir local long.
- `01_CODEX/04_TESTS_VALIDATION/H-001_CROSS_HEDGE_US500_US100.md` depuis GitHub et miroir local long.
- `00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md`.

## Regles non negociables

- BUY : controle theorique de sortie au BID.
- SELL : controle theorique de sortie a l'ASK.
- MID : informatif seulement, jamais preuve suffisante pour fermer.
- TP, stop et sortie : decision finale sur `broker_upl` reel cumule.
- Si `broker_upl` manque, est stale, incoherent ou non cumulable, le patch est bloque.
- Si WebSocket, REST broker et plateforme visible ne pointent pas vers le meme
  compte, le meme instrument et le meme instant UTC, le patch est bloque.

## Protocole d'audit

### Phase 0 - Cadrage sans SSH

But : preparer l'audit sans toucher au serveur.

- confirmer les paires : H001 = US500/US100, H002 = DE40/US30 ;
- confirmer le compte vise : demo ou live, un seul par releve ;
- preparer une horloge UTC visible pour les captures ;
- preparer un modele de releve plateforme et un modele de releve bot local ;
- lister les fichiers GitHub ou seront conservees les preuves ;
- ne pas modifier le code, ne pas lancer de test serveur, ne pas envoyer d'ordre.

### Phase 1 - Releve plateforme visible

Pour chaque actif `US500`, `US100`, `DE40`, `US30`, capturer au meme instant UTC :

- compte demo/live visible ;
- nom instrument plateforme ;
- epic / identifiant broker si visible ;
- timestamp UTC de capture ;
- BID ;
- ASK ;
- MID recalcule = `(BID + ASK) / 2` ;
- spread = `ASK - BID` ;
- position ouverte si presente : side, size, prix entree, PnL affiche ;
- capture ecran ou export horodate.

### Phase 2 - Releve bot local / broker

Pour les memes actifs et le meme instant UTC, relever :

- prix WebSocket : `ws_bid`, `ws_ask`, `ws_mid`, timestamp, age quote ;
- prix REST broker : `rest_bid`, `rest_ask`, `rest_mid`, timestamp, age snapshot ;
- position broker : side, size, `dealId`, prix entree broker ;
- `broker_upl` par position ;
- `broker_upl` cumule par strategie ;
- PnL local calcule BID/ASK ;
- ecart `broker_upl - pnl_local_bid_ask` ;
- source effective utilisee par la decision TP/stop/sortie.

Note H002 deja lue : le controle REST/broker existe, mais le WebSocket etait
observe `MISSING` tant que `BOT_PIVOT_03_tick_stream.py` ne tournait pas. Ce
point reste bloquant tant que la source WebSocket live n'est pas retablie puis
comparee.

### Phase 3 - Comparaison stricte

Pour chaque actif :

- comparer plateforme BID vs WebSocket BID vs REST BID ;
- comparer plateforme ASK vs WebSocket ASK vs REST ASK ;
- verifier que MID et spread expliquent les ecarts normaux ;
- verifier que les timestamps sont en UTC et suffisamment proches ;
- verifier que le compte demo/live est identique ;
- verifier que l'epic correspond au bon instrument, sans confusion cash/future ;
- verifier que BUY est controle au BID et SELL a l'ASK ;
- verifier que le PnL local ne peut pas declencher seul TP/stop/sortie ;
- verifier que le `broker_upl` cumule est disponible pour H001 et H002.

### Phase 4 - Conclusion

Statuts possibles :

- `PASS` : toutes les preuves sont coherentes et conservees.
- `FAIL` : divergence prix/PnL prouvee.
- `BLOCKED` : preuve manquante, stale, non comparable, ou source absente.

Tant que le statut global H001 ou H002 n'est pas `PASS`, aucun patch ne doit etre
applique sur execution, positions, paniers, stops, PnL, fermetures, legs ou
hedge.

## Matrice PASS / FAIL

| ID | Controle | PASS | FAIL / BLOCKED |
|---|---|---|---|
| AUD-001 | Compte | meme compte demo/live partout | compte ambigu ou different |
| AUD-002 | Instrument | nom + epic coherents | cash/future/suffixe/epic incertain |
| AUD-003 | Timestamp UTC | plateforme, WS et REST synchrones | timezone local, horloge absente, ecart non explique |
| AUD-004 | BID | plateforme BID = WS/REST dans tolerance documentee | divergence non expliquee |
| AUD-005 | ASK | plateforme ASK = WS/REST dans tolerance documentee | divergence non expliquee |
| AUD-006 | MID | MID recalcule et informatif | MID utilise comme preuve de sortie |
| AUD-007 | Spread | spread coherente et conservee | spread ignoree ou impossible a verifier |
| AUD-008 | WebSocket | `ws_bid/ws_ask/ws_mid` presents et frais | WS missing, stale ou non horodate |
| AUD-009 | REST broker | snapshot REST present et frais | REST missing, stale ou non horodate |
| AUD-010 | Plateforme visible | capture/releve lisible conserve | pas de preuve plateforme |
| AUD-011 | BUY au BID | PnL BUY controle au BID | BUY controle au MID/ASK/last/close |
| AUD-012 | SELL a l'ASK | PnL SELL controle a l'ASK | SELL controle au MID/BID/last/close |
| AUD-013 | broker_upl | disponible par position et cumulable | absent, stale, non cumulable ou contradictoire |
| AUD-014 | Decision sortie | TP/stop/sortie base sur `broker_upl` cumule | decision basee sur PnL local seul |
| AUD-015 | H001 | US500 et US100 PASS | un des deux actifs FAIL/BLOCKED |
| AUD-016 | H002 | DE40 et US30 PASS | un des deux actifs FAIL/BLOCKED |

## Modele releve plateforme

| Champ | Valeur |
|---|---|
| Audit ID |  |
| Strategie | H001 ou H002 |
| Actif | US500 / US100 / DE40 / US30 |
| Compte | demo / live |
| Horodatage UTC capture |  |
| Nom instrument plateforme |  |
| Epic / identifiant visible |  |
| BID plateforme |  |
| ASK plateforme |  |
| MID recalcule |  |
| Spread |  |
| Position ouverte | oui / non |
| Side position | BUY / SELL / NA |
| Size |  |
| Prix entree visible |  |
| PnL plateforme visible |  |
| Fichier preuve GitHub |  |
| Commentaire |  |

## Modele releve bot local

| Champ | Valeur |
|---|---|
| Audit ID |  |
| Strategie | H001 ou H002 |
| Actif | US500 / US100 / DE40 / US30 |
| Compte configure | demo / live |
| Horodatage UTC log |  |
| Epic / mapping bot |  |
| Source WS active | oui / non |
| ws_bid |  |
| ws_ask |  |
| ws_mid |  |
| ws_timestamp_utc |  |
| ws_age_ms |  |
| rest_bid |  |
| rest_ask |  |
| rest_mid |  |
| rest_timestamp_utc |  |
| rest_age_ms |  |
| dealId |  |
| side broker | BUY / SELL / NA |
| size broker |  |
| entry_broker |  |
| broker_upl position |  |
| broker_upl cumule strategie |  |
| pnl_local_bid_ask |  |
| gap_broker_local |  |
| decision_basis | broker_upl / local / none |
| Fichier preuve GitHub |  |
| Commentaire |  |

## Preuves a conserver dans GitHub

Chemin recommande :

```text
01_CODEX/02_DIAGNOSTICS_LOGS/price_truth_2026-05-18/
```

Preuves minimales :

- fiche protocole audit H001/H002 ;
- captures plateforme visibles, avec timestamp UTC dans le nom ou le contenu ;
- exports ou releves plateforme au format Markdown/CSV si possible ;
- logs WebSocket bruts pour US500, US100, DE40, US30 ;
- snapshots REST broker bruts ou extraits nettoyes sans secret ;
- logs positions avec `dealId`, side, size, entry, `broker_upl` ;
- tableau d'ecarts BID/ASK/MID/spread par actif ;
- tableau de PnL local vs `broker_upl` ;
- conclusion PASS/FAIL/BLOCKED signee par date ;
- mention explicite des sources absentes, par exemple WebSocket `MISSING`.

Ne jamais conserver en clair :

- mot de passe ;
- cle API ;
- token ;
- code 2FA ;
- cookie de session ;
- entete d'authentification.

## Decision bloquante

Tout patch H001/H002 est bloque tant que ces conditions ne sont pas toutes PASS :

- H001 : US500 et US100 prouves coherents entre plateforme visible, WebSocket,
  REST broker et compte cible.
- H002 : DE40 et US30 prouves coherents entre plateforme visible, WebSocket,
  REST broker et compte cible.
- Les timestamps sont en UTC et comparables.
- Le spread explique les ecarts normaux.
- BUY est controle au BID.
- SELL est controle a l'ASK.
- Le `broker_upl` reel cumule est disponible et prioritaire pour TP, stop et
  sortie.
- Les preuves sont conservees dans GitHub sans secret.

Si un seul point manque, le statut est `BLOCKED` et aucun patch execution,
positions, paniers, stops, PnL, fermetures, legs ou hedge ne doit etre lance.
