# Index Pilote Memoire - bot-live_V00

Statut : pilote commun GPT / Codex
Date : 2026-05-18

## Role

Le pilote memoire sert a organiser le projet `bot-live_V00`.

Il evite que les informations importantes restent bloquees dans un seul chat.
Il indique quoi lire, ou ecrire, quel mode utiliser et comment synchroniser GPT, Codex, Drive et GitHub.

## Regle centrale BAV

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

## Espaces officiels

### Drive documentaire

```text
TRADING/bot-live_V00
```

Role :
- coffre documentaire lisible ;
- support de synchronisation GPT / Codex ;
- espace de consultation utilisateur.

### GitHub memoire Markdown versionnee

```text
philippevacher06-sudo/bot-live_V00
```

Role :
- memoire Markdown versionnee ;
- suivi des diffs ;
- historique des decisions ;
- base durable lisible par GPT et Codex.

## Modes de travail

### Mode GPT

GPT est l'atelier strategique.

Il sert a :
- clarifier la doctrine ;
- analyser les decisions ;
- produire les syntheses longues ;
- formuler les hypotheses ;
- arbitrer les choix strategiques ;
- preparer les consignes applicables par Codex.

### Mode Codex

Codex est l'atelier technique.

Il sert a :
- lire et cartographier le code ;
- analyser les logs ;
- verifier SSH, Linux, tmux et broker ;
- proposer des microtouches ;
- appliquer des patchs controles ;
- produire les diffs ;
- lancer ou documenter les tests.

## Regle de separation

Cette phase de demarrage GPT ne transmet aucune consigne operationnelle a Codex tant qu'un paquet explicite `GPT vers Codex` n'est pas valide.

Sont interdits dans cette phase :
- patch code ;
- action SSH ;
- action broker ;
- modification technique du bot ;
- consigne implicite a Codex.

## Fichiers prioritaires du pilote

```text
00_PILOTE_MEMOIRE/INDEX_PILOTE.md
00_PILOTE_MEMOIRE/MODE_GPT.md
00_PILOTE_MEMOIRE/MODE_CODEX.md
00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
00_PILOTE_MEMOIRE/ROUTAGE_CLAVARDAGES.md
00_PILOTE_MEMOIRE/COMMANDES_UTILISATEUR.md
```

## Sources de verite prioritaires

```text
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

## Synchronisation

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
04_SYNC_DRIVE/PAQUET_SESSION_CODEX_VERS_GPT.md
04_SYNC_DRIVE/POLITIQUE_CORRELATION_CODEX_GPT.md
```

## Regle de controle

Aucune decision importante ne doit rester uniquement dans le chat.

Une decision devient durable seulement lorsqu'elle est inscrite dans un fichier memoire officiel.
