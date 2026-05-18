# Architecture Canonique - bot-live_V00

Statut : architecture officielle simplifiee
Date : 2026-05-18
Source : consolidation Codex apres audit GitHub / local

## Principe

GitHub est la source commune principale du projet `bot-live_V00`.

Le chat sert a travailler. Les fichiers servent a memoriser. Le pilote sert a router.

## Structure active

```text
00_PILOTE/      pilotage court : architecture, modes, routage
00_COMMUN/      source de verite : etat, decisions, regles, questions
01_CODEX/       technique : diagnostic, patchs, tests, retours
02_GPT/         strategie : doctrine, analyses utiles, arbitrages
03_SSH/         SSH, tmux, chemins, broker, scripts
04_SYNC/        paquets de synchronisation GPT / Codex
05_EXTENSIONS/  GitHub, Drive, Codex et connecteurs
06_SECRETS/     politique secrets et acces sans valeurs sensibles
99_ARCHIVES/    ancien socle et documents secondaires
```

## Navigation prioritaire

```text
README.md
00_COMMUN/ETAT_COURANT_PROJET.md
00_PILOTE/ARCHITECTURE_CANONIQUE_BOT_LIVE_V00.md
00_PILOTE/INDEX_PILOTE.md
00_COMMUN/BOT_PIVOT_V2446_REGLES_MAITRES.md
00_COMMUN/DECISIONS_VALIDEES.md
```

## Doctrine courte

- Codex = atelier technique.
- GPT = miroir strategique.
- GitHub = memoire commune versionnee.
- Drive = secondaire, lecture et appoint.
- SSH / broker = zone sensible, action uniquement explicite.
- Pas de secret en clair.
- Pas de patch sans diagnostic, sauvegarde et test.

## Archive

L'ancienne architecture GitHub a ete conservee dans :

```text
99_ARCHIVES/2026-05-18_CONSOLIDATION_GITHUB/AVANT_CONSOLIDATION/
```
