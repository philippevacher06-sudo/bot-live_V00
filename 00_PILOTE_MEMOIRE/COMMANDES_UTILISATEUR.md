# Commandes Utilisateur - Pilote Memoire

Statut : commandes de pilotage utilisateur
Projet : bot-live_V00
Date : 2026-05-18

## Principe

Ce fichier liste les commandes simples que l'utilisateur peut donner a GPT ou Codex pour piloter le projet `bot-live_V00`.

Ces commandes servent a eviter les ambiguites entre :

- travail dans le chat ;
- sauvegarde documentaire ;
- preparation vers Codex ;
- cloture de session ;
- changement de chat ;
- mise a jour des fichiers memoire.

## Regle BAV

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

## Commandes de demarrage GPT

```text
Demarre session GPT doctrine
Demarre session GPT arbitrage
Demarre session GPT synthese
Demarre session GPT regles a valider
Demarre session GPT analyse hypotheses
Demarre session GPT preparation vers Codex
```

Usage :
ces commandes ouvrent ou cadrent une session strategique GPT.

GPT doit alors relire les fichiers prioritaires du projet et confirmer la phase active.

## Commandes de demarrage Codex

```text
Demarre session Codex architecture
Demarre session Codex SSH
Demarre session Codex diagnostic logs
Demarre session Codex cartographie code
Demarre session Codex patch
Demarre session Codex tests
```

Usage :
ces commandes sont reservees aux futures sessions techniques Codex.

Elles ne doivent pas etre interpretees comme actives dans une session GPT documentaire.

## Commandes de sauvegarde documentaire

```text
Sauvegarde dans le projet
Sauvegarde dans le projet GPT
Sauvegarde dans le projet Codex
Mets a jour les decisions validees
Mets a jour les questions ouvertes
Mets a jour le pilote memoire
Mets a jour la source de verite
```

Usage :
ces commandes demandent une mise a jour de fichiers memoire officiels.

Avant toute ecriture, GPT ou Codex doit indiquer :

- le fichier cible ;
- le contenu propose ;
- si une validation explicite est necessaire.

## Commandes de synchronisation GPT / Codex

```text
Prepare paquet vers Codex
Prepare paquet vers GPT
Verifie la synchro Codex GPT
Liste les fichiers de synchronisation
Lis le paquet Codex vers GPT
Lis le paquet GPT vers Codex
```

Usage :
ces commandes servent a creer ou lire les paquets explicites entre GPT et Codex.

Regle :
aucune transmission operationnelle vers Codex n'existe tant que l'utilisateur n'a pas valide le paquet correspondant.

## Commandes de controle

```text
Liste memoire active
Quels fichiers dois-tu lire ?
Quels fichiers vas-tu modifier ?
Quelle est la source de verite ?
Sommes-nous en mode GPT ou Codex ?
Quelle est la phase active ?
Quelles actions sont interdites maintenant ?
Quelles questions restent ouvertes ?
Quelles decisions sont validees ?
```

Usage :
ces commandes permettent de verifier que le projet reste propre, lisible et conforme a la doctrine.

## Commandes de cloture

```text
Cloture session
Resume ce qui a ete sauvegarde
Liste les fichiers modifies
Liste les commits GitHub
Liste les prochaines actions
Prepare le resume de reprise
Dis-moi s'il faut ouvrir un nouveau chat
```

Usage :
ces commandes servent a terminer proprement une session et a eviter que des informations restent seulement dans le chat.

## Commandes anti-derive

```text
Stop, on reste documentaire
Stop, pas de Codex maintenant
Stop, pas de code
Stop, pas de SSH
Stop, pas de broker
Reviens a la regle BAV
Reviens a la source de verite
```

Usage :
ces commandes permettent de recentrer immediatement la session si elle commence a deriver vers une action non souhaitee.

## Commande de validation

```text
je valide
```

Usage :
lorsque GPT propose une ecriture documentaire, cette commande autorise l'ecriture dans le fichier officiel indique.

Cette validation ne vaut que pour l'action precise qui vient d'etre proposee.

Elle ne vaut pas validation globale pour d'autres fichiers, patchs ou transmissions.

## Commande de refus

```text
je ne valide pas
```

Usage :
cette commande bloque l'ecriture ou l'action proposee.

GPT ou Codex doit alors corriger la proposition ou demander une nouvelle orientation.

## Regle de prudence

Si une commande est ambigue, GPT ou Codex doit reformuler l'action prevue avant d'ecrire ou de modifier quoi que ce soit.

## Statut actuel

La phase actuelle reste :

```text
01 - Demarrage documentaire GPT
```

Actions autorisees :

- creation ou mise a jour de fichiers memoire Markdown dans GitHub officiel ;
- lecture des fichiers Drive ou GitHub officiels ;
- proposition de contenus documentaires.

Actions interdites :

- patch code ;
- action SSH ;
- action broker ;
- transmission operationnelle a Codex ;
- creation de fichiers hors espaces officiels.
