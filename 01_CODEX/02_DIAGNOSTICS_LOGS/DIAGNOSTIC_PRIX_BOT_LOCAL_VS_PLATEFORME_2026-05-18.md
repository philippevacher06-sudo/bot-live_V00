# Diagnostic Prix Bot Local Vs Plateforme

Date : 2026-05-18
Statut : bloquant avant tout patch trading

## Signalement utilisateur

Les resultats des tests recents sont mauvais. Suspicion principale :

```text
Le prix vu par le bot local ne correspond pas au prix vu sur la plateforme.
```

## Decision immediate

Mettre en pause toute evolution strategique ou patch H-001 tant que la chaine de prix n'est pas auditee.

## Risque

Si le bot ne voit pas le meme prix que la plateforme, alors tous les calculs suivants peuvent etre faux :

- declenchement L1/L2/L3/L4 ;
- adverse step ;
- stop ;
- time slip ;
- TP panier ;
- PnL BUY au BID ;
- PnL SELL a l'ASK ;
- `upl` broker ;
- logs de decision ;
- comparaison backtest / reel.

## Causes possibles a verifier

- Bot utilisant `mid`, `last` ou `close` pendant que la plateforme affiche BID ou ASK.
- BUY valorise au mauvais cote de prix.
- SELL valorise au mauvais cote de prix.
- Instrument mal mappe : cash/future, mauvais epic, mauvais suffixe ou mauvais compte demo/live.
- Prix retarde, cache, websocket stale ou snapshot non rafraichi.
- Timestamp different entre bot et plateforme.
- Decalage de fuseau horaire dans les logs.
- Spread ignore ou arrondi trop agressif.
- Conversion point/pip/tick incorrecte.
- Donnees M1/M5/M15 construites depuis une source differente du prix execution.
- PnL local utilise alors que le PnL broker devrait primer.

## Audit minimal requis

Pour un meme instant, capturer : instrument, epic, compte demo/live, timestamp UTC, BID, ASK, MID, spread, source prix et fraicheur quote cote bot et cote plateforme.

## Regle de validation

Le diagnostic doit prouver clairement :

- quel prix le bot lit ;
- quel prix la plateforme affiche ;
- quel cote de prix est utilise pour BUY ;
- quel cote de prix est utilise pour SELL ;
- si l'ecart est normal, par exemple spread, ou anormal ;
- si le PnL broker `upl` est disponible et prioritaire.

## Verrou

```text
Tant que ce diagnostic est bloque, ne pas valider H-001 et ne pas patcher la logique execution, paniers, stops, PnL ou fermetures.
```
