# Routage Clavardages - bot-live_V00

Statut : regle de circulation entre chats
Projet : bot-live_V00
Date : 2026-05-18

## Principe

Les clavardages servent a travailler, reflechir, analyser et decider.

Ils ne sont pas la memoire durable du projet.

La memoire durable est dans les fichiers officiels :

```text
TRADING/bot-live_V00
philippevacher06-sudo/bot-live_V00
```

## Regle BAV

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

## Phase actuelle

La phase actuelle est :

```text
Demarrage documentaire GPT
Doctrine / memoire / architecture projet
Aucune action code
Aucune action SSH
Aucune action broker
Aucune consigne operationnelle Codex
```

## Quand rester dans le meme chat GPT

On reste dans le meme chat GPT lorsque :

- le sujet reste le demarrage documentaire ;
- on valide progressivement les fichiers memoire ;
- on ne traite pas encore de logs techniques ;
- on ne prepare pas encore de patch ;
- on ne donne aucune consigne operationnelle a Codex ;
- la conversation reste lisible et controlee.

## Quand ouvrir un nouveau chat GPT

Ouvrir un nouveau chat GPT devient recommande lorsque :

- le chat devient trop long ou trop lent ;
- un nouveau domaine strategique commence ;
- une synthese de reprise est necessaire ;
- on passe du cadrage documentaire a une vraie analyse strategique ;
- on commence une session dediee aux regles maitresses ;
- on commence une session dediee aux arbitrages ;
- on commence une session dediee aux hypotheses a tester ;
- on prepare explicitement un paquet GPT vers Codex.

## Chats GPT recommandes

```text
01 - Demarrage documentaire GPT
02 - Doctrine strategique
03 - Decisions et arbitrages
04 - Analyse logs et hypotheses
05 - Regles a valider
06 - Syntheses sessions
07 - Preparation GPT vers Codex
```

## Quand ouvrir un chat Codex

Un chat Codex ne doit etre ouvert que lorsque l'objectif devient technique.

Exemples :

- lire ou cartographier le code ;
- analyser des logs ;
- verifier SSH, tmux ou broker ;
- diagnostiquer un comportement du bot ;
- proposer une microtouche ;
- appliquer un patch valide ;
- lancer ou documenter un test.

## Chats Codex recommandes

```text
01 - Validation architecture V00
02 - Memoire permanente Codex GPT
03 - Sync Drive GitHub
04 - SSH bot-live sante terminal
05 - Cartographie code bot-live
06 - Diagnostics logs
07 - Patches microtouches
08 - Tests validation
```

## Regle de correlation entre chats

Les chats ne se synchronisent pas automatiquement.

Ils doivent etre relies par les fichiers :

```text
00_PILOTE_MEMOIRE/
00_COMMUN_SOURCE_DE_VERITE/
04_SYNC_DRIVE/
```

Une information importante presente seulement dans un chat n'est pas durable.

## Message type pour nouveau chat GPT

```text
Demarrage session GPT strategique - bot-live_V00.

Lis d'abord :
- 00_PILOTE_MEMOIRE/INDEX_PILOTE.md
- 00_PILOTE_MEMOIRE/MODE_GPT.md
- 00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
- 00_PILOTE_MEMOIRE/ROUTAGE_CLAVARDAGES.md
- 00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
- 00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md

Applique la regle BAV.
Ne considere pas le chat comme memoire durable.
Ne transmets rien a Codex sans paquet valide.
```

## Message type pour nouveau chat Codex

```text
Demarrage session Codex - bot-live_V00.

Lis d'abord :
- 00_PILOTE_MEMOIRE/INDEX_PILOTE.md
- 00_PILOTE_MEMOIRE/MODE_CODEX.md
- 00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
- 00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
- 00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
- 00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
- 04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md

N'applique aucun patch sans diagnostic.
Ne modifie pas le bot sans validation explicite.
Respecte la regle BAV.
```

## Regle de passage GPT vers Codex

GPT ne transmet rien a Codex tant qu'un fichier explicite n'a pas ete valide.

Fichier cible :

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
```

ou son equivalent Markdown versionne dans GitHub.

## Regle de passage Codex vers GPT

Codex doit revenir vers GPT par un paquet structure.

Fichier cible :

```text
04_SYNC_DRIVE/PAQUET_SESSION_CODEX_VERS_GPT.md
```

Le retour doit contenir :

```text
Resume technique :
Fichiers lus :
Fichiers touches :
Diagnostics :
Patchs :
Tests :
Risques :
Questions pour GPT :
```

## Regle anti-saturation

Quand un chat devient trop lourd, GPT doit proposer :

- un resume de reprise ;
- les fichiers a relire ;
- le nom du nouveau chat ;
- la phase exacte du projet ;
- les actions interdites et autorisees.

## Statut actuel

Pour le moment, on reste dans le chat courant.

Nom logique du chat courant :

```text
01 - Demarrage documentaire GPT
```

Aucune transmission Codex n'est active.
