# NOTE H-001 - Blocage validation prix bot local vs plateforme

Date : 2026-05-18

## Contexte

L'utilisateur signale un probleme de validation de prix correspondant entre :

```text
- le prix visible sur la plateforme Capital.com ;
- le prix lu par le bot local ;
- le comportement observe pour H-001.
```

## Strategie concernee

```text
H-001 = PANIER_CROSS_HEDGE_US500_US100_V1
US500 principal : L1/L2/L3
US100 hedge : L4
```

## Statut

```text
BLOQUANT POUR VALIDATION H-001
```

H-001 ne doit pas etre declaree PASS tant que l'audit prix n'est pas conforme pour :

```text
US500
US100
```

## Points a prouver

Pour le meme instant UTC, verifier pour US500 et US100 :

```text
prix bot local WebSocket
prix bot local REST / snapshot broker
prix plateforme visible
BID
ASK
MID
spread
fraicheur quote
compte demo/live
broker_upl si position ouverte
```

## Regle PnL a confirmer

```text
BUY  : PnL theorique controle au BID
SELL : PnL theorique controle a l'ASK
Decision finale TP / stop / sortie : broker_upl reel cumule prioritaire
```

## Risques H-001 si prix non conforme

- L1/L2/L3 US500 peuvent etre declenchees au mauvais niveau.
- L4 US100 peut etre declenchee trop tot ou trop tard.
- Le TP global +1 EUR apres hedge peut etre valide a tort par un PnL local.
- Le stop global -15 EUR peut etre lu trop tard ou sur une mauvaise base.
- Le time slip depuis L1 peut etre coherent en temps mais faux en prix/PnL.

## Verrou

```text
Ne pas patcher, valider ou deployer H-001 tant que US500 et US100 ne passent pas l'audit prix bot local vs plateforme.
```

## Contraintes de cette note

```text
Aucun code modifie.
Aucun test serveur lance.
Aucune action SSH effectuee.
```
