# Fixtures H-001 Cross Hedge

Statut : fixtures documentaires offline
Date : 2026-05-18

## Regles communes

| Champ | Valeur |
|---|---|
| Instrument principal | US500 |
| Instrument hedge | US100 |
| L1 | US500 0.07 |
| L2 | US500 0.14 |
| L3 | US500 0.21 |
| L4 | US100 0.08 |
| Step L2 | 3 points adverses US500 apres L1 |
| Step L3 | 3 points adverses US500 apres L2 |
| Step L4 | 3 points adverses US500 apres L3 |
| TP L1 | +1 EUR |
| TP L1+L2 | +2 EUR |
| TP L1+L2+L3 | +4 EUR |
| TP apres L4 | +1 EUR broker cumule US500+US100 |
| Stop global apres L4 | -15 EUR broker cumule US500+US100 |
| Time slip | 7200 secondes depuis L1 |
| Direction L4 si US500 BUY | US100 SELL |
| Direction L4 si US500 SELL | US100 BUY |

## Fixtures

### FIX-H001-01 - Cycle BUY complet

```text
L1 US500 BUY 0.07
US500 -3 points -> L2 US500 BUY 0.14
US500 -3 points apres L2 -> L3 US500 BUY 0.21
US500 -3 points apres L3 -> L4 US100 SELL 0.08
```

### FIX-H001-02 - Cycle SELL complet

```text
L1 US500 SELL 0.07
US500 +3 points -> L2 US500 SELL 0.14
US500 +3 points apres L2 -> L3 US500 SELL 0.21
US500 +3 points apres L3 -> L4 US100 BUY 0.08
```

### FIX-H001-03 - Tentative L5 refusee

Etat : L1+L2+L3+L4 deja ouverts.
Attendu : L5 refusee, log explicite, aucun ordre envoye.

### FIX-H001-04 - Renfort US100 refuse

Etat : L4 US100 deja ouverte.
Attendu : second ordre US100 refuse.

### FIX-H001-05 - Sortie gain

Etat : L1/L2/L3 US500 + L4 US100.
PnL broker cumule : +1.00 EUR.
Attendu : fermeture totale.

### FIX-H001-06 - Stop global

Etat : L1/L2/L3 US500 + L4 US100.
PnL broker cumule : -15.00 EUR.
Attendu : fermeture totale.

### FIX-H001-07 - Time slip

Age depuis L1 : 7200 secondes.
Attendu : fermeture totale de l'etat panier courant.

### FIX-H001-08 - PnL local divergent

```text
pnl_local_calcule = +1.20 EUR
pnl_broker_cumule = -0.30 EUR
```

Attendu : pas de fermeture gain ; broker prioritaire.

### FIX-H001-09 - Rupture M15/M5 apres L3

Etat : L3 ouverte, signal M15/M5 invalide la direction initiale, stop et time slip non atteints.
Attendu : pas de coupe immediate automatique ; logs et verrous de risque actifs.
