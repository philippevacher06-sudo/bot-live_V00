# Plan Patch H-001 Cross Hedge

Statut : plan uniquement, aucun patch
Date : 2026-05-18

## Objet

Preparer une future microtouche technique pour `PANIER_CROSS_HEDGE_US500_US100_V1`, sans modifier le bot maintenant.

## Interdictions actuelles

- Ne pas modifier le code du bot.
- Ne pas lancer de test serveur.
- Ne pas toucher au SSH.
- Ne pas envoyer d'ordre broker.
- Ne pas patcher tant que les tests offline H-001 ne sont pas ecrits.

## Modules a inspecter quand le code sera disponible

| Domaine | A chercher |
|---|---|
| Configuration instruments | US500, US100, tailles, points |
| Signaux MTF | M15, M5, M1, statut directionnel, logs |
| Entrees | Conditions L1 |
| Paniers | Etat panier, legs, direction initiale, age depuis L1 |
| Legs | L2/L3, adverse step, maximum legs |
| Hedge / locks | Logique multi-instrument ou opposee |
| Broker | Positions, `upl`, PnL broker, fermeture globale |
| PnL | Broker vs local, BUY au BID, SELL a l'ASK |
| Stops | Stop global, time stop, time slip |
| Logs | Acceptation, refus, ajout leg, fermeture |
| Tests | Signaux, paniers, broker, PnL, stops |

## Sequence recommandee

1. Cartographie code sans modification.
2. Ecriture des tests offline H001-S01 a H001-S13.
3. Verification SSH/broker plus tard avec autorisation explicite.
4. Microtouche courte et reversible seulement apres tests et verification.

## Verrous de refus du patch

Refuser ou bloquer si :

- le code ne distingue pas panier principal et hedge ;
- le PnL broker cumule US500+US100 n'est pas disponible ou fiable ;
- le bot peut ouvrir L5 ;
- le bot peut renforcer US100 ;
- la fermeture globale ne ferme pas toutes les jambes ;
- le time slip ne part pas de L1 ;
- le patch exige une refonte large ;
- SSH/broker n'a pas ete verifie alors que le bot est actif.

## Definition de pret pour patch

H-001 devient pret pour patch seulement si :

- cartographie code faite ;
- tests offline H-001 ecrits ;
- fixtures reliees aux tests ;
- scenarios critiques passent offline ;
- contexte SSH/broker verifie avec autorisation ;
- point de retour ou sauvegarde confirme ;
- microtouche courte et reversible.

```text
PLAN SEULEMENT - aucun patch autorise a ce stade.
```
