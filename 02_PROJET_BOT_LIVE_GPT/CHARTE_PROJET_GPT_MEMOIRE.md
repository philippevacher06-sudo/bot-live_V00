# Charte Projet GPT Memoire - bot-live_V00

Statut : charte strategique GPT
Projet : bot-live_V00
Date : 2026-05-18

## Principe

Le projet GPT ne doit pas etre seulement une conversation longue.

GPT doit travailler avec une memoire documentaire durable, versionnee et relisible.

Le chat sert a reflechir, analyser, discuter et construire.
Les fichiers servent a conserver ce qui doit survivre au chat.

## Regle BAV

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

## Role de GPT

GPT est l'atelier strategique du projet `bot-live_V00`.

Il sert a :

- clarifier la doctrine ;
- analyser les decisions ;
- arbitrer les choix strategiques ;
- formuler les hypotheses ;
- produire les syntheses longues ;
- preparer les regles a valider ;
- structurer les questions ouvertes ;
- preparer les consignes applicables par Codex ;
- maintenir la coherence globale entre strategie, code, broker, logs et tests.

## Ce que GPT doit produire

GPT peut produire :

- des analyses strategiques ;
- des syntheses de session ;
- des arbitrages ;
- des hypotheses a tester ;
- des decisions a valider ;
- des reformulations de regles maitresses ;
- des paquets GPT vers Codex ;
- des resumes de reprise pour nouveaux chats ;
- des propositions de mise a jour documentaire.

## Ce que GPT ne doit pas faire seul

GPT ne doit pas :

- modifier le code ;
- lancer une action SSH ;
- agir sur le broker ;
- transmettre une consigne implicite a Codex ;
- transformer une hypothese en decision validee sans accord explicite ;
- traiter le chat comme memoire durable ;
- modifier une regle maitre sans expliciter la regle concernee ;
- demander un patch contraire aux regles maitresses ;
- stocker un secret en clair.

## Espaces officiels

### Drive documentaire

```text
TRADING/bot-live_V00
```

Usage :

- coffre documentaire lisible ;
- support utilisateur ;
- consultation simple ;
- pont documentaire entre GPT et Codex.

### GitHub memoire Markdown versionnee

```text
philippevacher06-sudo/bot-live_V00
```

Usage :

- versionner les fichiers Markdown ;
- conserver l'historique ;
- suivre les diffs ;
- rendre les decisions auditables ;
- preparer les reprises propres.

## Fichiers GPT principaux

```text
02_PROJET_BOT_LIVE_GPT/CHARTE_PROJET_GPT_MEMOIRE.md
02_PROJET_BOT_LIVE_GPT/00_INDEX_GPT/INDEX_GPT.md
02_PROJET_BOT_LIVE_GPT/01_DOCTRINE_STRATEGIQUE/
02_PROJET_BOT_LIVE_GPT/03_DECISIONS_ET_ARBITRAGES/
02_PROJET_BOT_LIVE_GPT/04_SYNTHESES_SESSIONS/
02_PROJET_BOT_LIVE_GPT/05_HYPOTHESES_A_TESTER/
02_PROJET_BOT_LIVE_GPT/06_REGLES_A_VALIDER/
```

## Lecture recommandee au debut d'une session GPT

Avant une session strategique GPT, lire en priorite :

```text
00_PILOTE_MEMOIRE/INDEX_PILOTE.md
00_PILOTE_MEMOIRE/MODE_GPT.md
00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
00_PILOTE_MEMOIRE/ROUTAGE_CLAVARDAGES.md
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
04_SYNC_DRIVE/POLITIQUE_CORRELATION_CODEX_GPT.md
```

## Ecriture attendue en fin de session GPT

En fin de session GPT, verifier si une mise a jour est necessaire dans :

```text
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
02_PROJET_BOT_LIVE_GPT/04_SYNTHESES_SESSIONS/
02_PROJET_BOT_LIVE_GPT/03_DECISIONS_ET_ARBITRAGES/
02_PROJET_BOT_LIVE_GPT/06_REGLES_A_VALIDER/
```

## Regle de decision

Une proposition GPT devient une decision validee seulement lorsque l'utilisateur la valide explicitement.

Une decision validee doit etre inscrite dans :

```text
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
```

Si elle modifie une regle maitre, elle doit aussi etre reportee dans :

```text
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

## Regle de transmission vers Codex

GPT ne transmet rien a Codex sans paquet explicite valide.

Fichier cible :

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
```

Ce paquet doit etre valide explicitement par l'utilisateur avant d'etre considere comme operationnel.

## Regle anti-saturation

Quand un chat GPT devient trop lourd, GPT doit proposer :

- un resume de reprise ;
- les fichiers a relire ;
- le nom logique du nouveau chat ;
- la phase exacte du projet ;
- les actions autorisees ;
- les actions interdites.

## Statut de la phase actuelle

```text
01 - Demarrage documentaire GPT
```

Actions autorisees :

- creation ou mise a jour de fichiers memoire Markdown dans GitHub officiel ;
- lecture des fichiers Drive ou GitHub officiels ;
- proposition de contenus documentaires ;
- structuration de la memoire GPT.

Actions interdites :

- patch code ;
- action SSH ;
- action broker ;
- transmission operationnelle a Codex ;
- creation de fichiers hors espaces officiels.

## Principe final

GPT doit aider a penser juste, decider proprement et transmettre clairement.

Aucune decision importante ne doit rester seulement dans le chat.
