# Sessions Tmux Reference - bot-live_V00

Statut : reference documentaire
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier documente les sessions tmux connues ou attendues pour le bot live.

Il ne lance aucune session.

## Session connue

```text
botpivot24
```

## Commandes de reference

Lister les sessions :

```bash
tmux ls
```

Attacher une session :

```bash
tmux attach -t botpivot24
```

Detacher une session tmux sans tuer le bot :

```text
CTRL+B puis D
```

## Regle

Ne jamais tuer ou relancer une session tmux sans verification prealable de l'etat broker, des positions et des ordres pending.
