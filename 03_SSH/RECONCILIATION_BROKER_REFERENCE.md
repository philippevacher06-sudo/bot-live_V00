# Reconciliation Broker Reference - bot-live_V00

Statut : reference documentaire
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier documente la logique de reconciliation broker a respecter avant toute action technique importante.

## Principe

L'etat broker prime sur l'etat local.

Si l'etat local et l'etat broker divergent, ne pas patcher ou relancer sans diagnostic.

## Script connu a verifier

```bash
python3 BOT_PIVOT_06G1_reconcile_broker.py
```

## Points a verifier

```text
positions ouvertes
ordres pending
etat local cycle
etat execution
hedgingMode=False
coherence paniers / legs / broker
```

## Regle

Aucun patch sensible ne doit etre fait pendant qu'un panier ou un ordre pending est actif, sauf urgence documentee et validation explicite.
