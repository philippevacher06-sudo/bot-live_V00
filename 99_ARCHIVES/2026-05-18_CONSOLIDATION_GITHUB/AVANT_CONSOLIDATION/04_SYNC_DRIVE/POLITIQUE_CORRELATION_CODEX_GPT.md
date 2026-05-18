# Politique Correlation Codex / GPT - bot-live_V00

Statut : regle de synchronisation documentaire
Projet : bot-live_V00
Date : 2026-05-18

## Principe

GPT et Codex ne doivent pas dependre de la memoire implicite des chats.

La correlation entre GPT et Codex se fait par fichiers officiels.

## Regle BAV

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
- espace de consultation utilisateur ;
- pont simple entre GPT et Codex ;
- support de reprise lorsque le chat devient trop lourd.

### GitHub memoire Markdown versionnee

```text
philippevacher06-sudo/bot-live_V00
```

Role :
- versionner la memoire Markdown ;
- suivre les diffs ;
- conserver l'historique ;
- preparer les reprises propres ;
- rendre les decisions auditables.

## Role de GPT

GPT est l'atelier strategique.

Il sert a :
- clarifier la doctrine ;
- analyser les arbitrages ;
- produire les syntheses longues ;
- formuler les hypotheses ;
- preparer les consignes vers Codex ;
- maintenir la coherence strategique du projet.

GPT ne doit pas :
- modifier le code ;
- agir sur SSH ;
- agir sur le broker ;
- transmettre une consigne implicite a Codex ;
- traiter le chat comme memoire durable.

## Role de Codex

Codex est l'atelier technique.

Il sert a :
- lire le code ;
- analyser les logs ;
- verifier SSH, tmux, broker et etat local ;
- proposer des microtouches ;
- appliquer des patchs controles apres validation ;
- produire des diffs ;
- documenter les tests ;
- retourner vers GPT les diagnostics et risques.

Codex ne doit pas :
- patcher sans diagnostic ;
- modifier la doctrine strategique ;
- contredire les regles maitresses sans alerte ;
- agir sur le broker sans demande claire ;
- stocker un secret en clair.

## Flux GPT vers Codex

GPT ne transmet rien a Codex tant qu'un paquet explicite n'a pas ete valide.

Fichier cible :

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
```

Contenu attendu :

```text
Date :
Statut :
Objet :
Sources utilisees :
Decision ou arbitrage :
Regles concernees :
Consigne Codex :
Contraintes :
Questions ouvertes :
```

## Flux Codex vers GPT

Codex doit retourner vers GPT par un paquet structure.

Fichier cible :

```text
04_SYNC_DRIVE/PAQUET_SESSION_CODEX_VERS_GPT.md
```

Contenu attendu :

```text
Date :
Resume technique :
Fichiers lus :
Fichiers touches :
Diagnostics :
Patchs :
Tests :
Risques :
Questions pour GPT :
```

## Regle de non-transmission implicite

Une discussion GPT ne vaut pas consigne Codex.

Une analyse Codex ne vaut pas decision GPT.

Une decision devient durable seulement si elle est inscrite dans les fichiers officiels.

Une consigne devient transmissible seulement si elle est inscrite dans un paquet explicite valide.

## Regle de priorite documentaire

Priorite des sources :

```text
1. 00_COMMUN_SOURCE_DE_VERITE/
2. 00_PILOTE_MEMOIRE/
3. 04_SYNC_DRIVE/
4. 02_PROJET_BOT_LIVE_GPT/
5. 01_PROJET_BOT_LIVE_CODEX/
6. 03_SSH_BOT_LIVE/
```

## Gestion des contradictions

Si Codex detecte une contradiction entre le code, les logs et les regles maitresses :

- il doit la signaler ;
- il ne doit pas corriger silencieusement si la contradiction est strategique ;
- il doit proposer une microtouche ou une question pour GPT ;
- GPT doit arbitrer si la contradiction touche la doctrine.

Si GPT detecte une contradiction dans la doctrine :

- il doit identifier la regle concernee ;
- il doit proposer une decision ou une question ouverte ;
- il ne doit pas demander de patch avant validation documentaire.

## Regle anti-secret

Aucun espace officiel ne doit contenir :

- mot de passe ;
- cle API ;
- token ;
- code 2FA ;
- secret broker ;
- identifiant sensible complet.

Les fichiers peuvent contenir les noms de variables ou les procedures, mais jamais les valeurs sensibles.

## Statut de la phase actuelle

La phase actuelle reste :

```text
01 - Demarrage documentaire GPT
```

Actions autorisees :

- creer ou mettre a jour des fichiers memoire Markdown dans GitHub officiel ;
- lire les fichiers officiels Drive ou GitHub ;
- proposer des contenus documentaires ;
- structurer la future synchronisation GPT / Codex.

Actions interdites :

- patch code ;
- action SSH ;
- action broker ;
- transmission operationnelle a Codex ;
- creation de fichiers hors espaces officiels.

## Regle finale

La synchronisation GPT / Codex doit toujours etre explicite, lisible et reversible.

Aucune decision importante ne doit rester seulement dans le chat.
