# Commandes Reference SSH - bot-live_V00

Statut : reference documentaire
Projet : bot-live_V00
Date : 2026-05-18

## Objet

Ce fichier regroupe des commandes de reference pour les futures sessions techniques.

Ces commandes ne sont pas executees dans la phase documentaire.

## Aller dans le dossier live

```bash
cd /home/philippe_vacher06/bot-pivot/live
```

## Activer l'environnement Python

```bash
source venv/bin/activate
```

## Lister les sessions tmux

```bash
tmux ls
```

## Entrer dans une session tmux

```bash
tmux attach -t <nom_session>
```

## Regle de securite

Avant toute commande modifiant l'etat du bot, verifier :

```text
positions ouvertes
ordres pending
etat local
etat broker
sauvegarde disponible
```
