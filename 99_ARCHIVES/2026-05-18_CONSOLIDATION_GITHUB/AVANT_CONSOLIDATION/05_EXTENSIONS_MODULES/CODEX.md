# Codex - bot-live_V00

Statut : reference extension
Projet : bot-live_V00
Date : 2026-05-18

## Role

Codex sert d'atelier technique pour le projet `bot-live_V00`.

## Usage

Codex peut etre utilise pour :

- lire le code ;
- lire les logs ;
- diagnostiquer ;
- proposer des microtouches ;
- appliquer des patchs valides ;
- lancer des tests autorises ;
- produire des retours techniques vers GPT.

## Limite

Codex ne doit pas recevoir de consigne operationnelle implicite.

Une transmission Codex doit passer par :

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
```

et etre validee explicitement par l'utilisateur.

## Regle

Aucun patch, aucune action SSH, aucune action broker et aucune relance bot ne sont autorises par la simple existence de ce fichier.
