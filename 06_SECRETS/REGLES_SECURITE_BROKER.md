# Regles Securite Broker - bot-live_V00

Statut : reference securite broker
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier fixe les regles de securite broker pour le projet `bot-live_V00`.

## Broker connu

```text
Capital.com demo
hedgingMode=False
```

## Regles principales

- L'etat broker prime sur l'etat local.
- Aucune action broker ne doit etre implicite.
- Aucune fermeture, ouverture ou relance ne doit etre faite sans validation explicite.
- Les tokens broker ne doivent jamais etre stockes en clair.
- Les calculs de PnL doivent respecter BID/ASK.
- Si `upl` broker est fiable, il doit etre considere comme source prioritaire pour les fermetures.

## Avant action sensible

Verifier :

```text
positions ouvertes
ordres pending
etat local
etat execution
session broker
hedgingMode=False
```

## Regle finale

La securite broker passe avant la vitesse de patch ou de test.
