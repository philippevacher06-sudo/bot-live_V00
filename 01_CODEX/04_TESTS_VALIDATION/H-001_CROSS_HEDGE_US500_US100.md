# H-001 - PANIER_CROSS_HEDGE_US500_US100_V1

Statut : a tester avant patch
Date : 2026-05-18

## Panier principal

Le panier principal se construit uniquement sur US500 :

- L1 US500 taille 0.07, TP panier +1 EUR ;
- L2 US500 taille 0.14, ouverte automatiquement a 3 points adverses apres L1, TP L1+L2 +2 EUR ;
- L3 US500 taille 0.21, ouverte automatiquement a 3 points adverses apres L2, TP L1+L2+L3 +4 EUR.

## L4 secours

Si L3 est executee et que le panier US500 reste perdant, L4 peut s'ouvrir sur US100 :

- L4 US100 taille 0.08 ;
- declenchement automatique a 3 points adverses US500 apres L3 ;
- si panier US500 BUY -> L4 US100 SELL ;
- si panier US500 SELL -> L4 US100 BUY.

L4 est une jambe de secours, pas une martingale.

## Verrous

- Aucun L5 autorise.
- Aucun renfort US100 autorise.
- PnL broker reel cumule prioritaire.
- Stop global : PnL broker cumule US500+US100 <= -15 EUR -> fermeture totale.
- TP apres L4 : PnL broker cumule US500+US100 >= +1 EUR -> fermeture totale.
- Time slip : 7200 secondes depuis L1 US500 posee -> fermeture totale.
- Rupture M15/M5 a partir de L3 : pas de coupe immediate automatique ; gestion de risque stricte.

## Scenarios offline

| ID | Scenario | Attendu |
|---|---|---|
| H001-S01 | L1 US500 | Ouvre US500 0.07, TP +1 EUR |
| H001-S02 | L2 US500 | A 3 points adverses apres L1, ouvre US500 0.14, TP +2 EUR |
| H001-S03 | L3 US500 | A 3 points adverses apres L2, ouvre US500 0.21, TP +4 EUR |
| H001-S04 | L4 US100 | A 3 points adverses US500 apres L3, ouvre US100 0.08 oppose |
| H001-S04A | Hedge BUY | US500 BUY -> US100 SELL |
| H001-S04B | Hedge SELL | US500 SELL -> US100 BUY |
| H001-S05 | L4 sans L3 | Refus |
| H001-S06 | L3+ M15/M5 rompu | Pas de coupe immediate ; risque strict actif |
| H001-S07 | L5 | Refus |
| H001-S08 | Renfort US100 | Refus |
| H001-S09 | Gain global | PnL broker cumule >= +1 EUR -> ferme tout |
| H001-S10 | Stop global | PnL broker cumule <= -15 EUR -> ferme tout |
| H001-S11 | PnL local divergent | Broker prioritaire |
| H001-S12 | Logs | Decisions reconstructibles |
| H001-S13 | Time slip | 7200 s depuis L1 -> ferme tout |

## Statut

```text
A TESTER - ne pas patcher sans validation offline puis broker.
```
