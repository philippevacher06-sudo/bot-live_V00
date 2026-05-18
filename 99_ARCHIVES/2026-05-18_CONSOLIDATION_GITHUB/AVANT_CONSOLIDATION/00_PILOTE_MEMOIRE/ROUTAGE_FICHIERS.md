# Routage Fichiers - bot-live_V00

Statut : regle de classement documentaire
Projet : bot-live_V00
Date : 2026-05-18

## Principe

Le routage fichiers sert a eviter que les informations importantes restent dispersees dans les chats.

Chaque information importante doit avoir un chemin cible clair.

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

Usage :
- coffre documentaire lisible ;
- support de consultation ;
- espace simple pour l'utilisateur ;
- pont documentaire GPT / Codex.

### GitHub memoire Markdown versionnee

```text
philippevacher06-sudo/bot-live_V00
```

Usage :
- fichiers Markdown versionnes ;
- historique des decisions ;
- suivi des diffs ;
- memoire durable structuree.

## 00_PILOTE_MEMOIRE/

Chemin :

```text
00_PILOTE_MEMOIRE/
```

Contenu attendu :
- index pilote ;
- mode GPT ;
- mode Codex ;
- routage fichiers ;
- routage clavardages ;
- commandes utilisateur ;
- checklists debut et fin de session ;
- etat de synchronisation GPT / Codex.

Role :
organiser la methode de travail et eviter la perte d'information entre chats, Drive, GitHub, GPT et Codex.

## 00_COMMUN_SOURCE_DE_VERITE/

Chemin :

```text
00_COMMUN_SOURCE_DE_VERITE/
```

Contenu attendu :
- decisions validees ;
- questions ouvertes globales ;
- regles maitresses BOT-PIVOT ;
- etat courant du projet ;
- glossaire ;
- protocole memoire permanente.

Role :
conserver ce qui fait reference pour tout le projet.

Tout changement strategique majeur doit etre compare a ce dossier.

## 01_PROJET_BOT_LIVE_CODEX/

Chemin :

```text
01_PROJET_BOT_LIVE_CODEX/
```

Contenu attendu :
- cartographie du code ;
- diagnostics techniques ;
- analyses de logs ;
- patchs proposes ;
- patchs appliques ;
- tests de validation ;
- journal Codex ;
- risques residuels ;
- retours techniques vers GPT.

Role :
documenter le travail technique de Codex.

Important :
ce dossier ne doit pas recevoir de patch code directement dans cette phase de demarrage documentaire GPT.

## 02_PROJET_BOT_LIVE_GPT/

Chemin :

```text
02_PROJET_BOT_LIVE_GPT/
```

Contenu attendu :
- doctrine strategique ;
- decisions et arbitrages ;
- hypotheses a tester ;
- syntheses de sessions ;
- regles a valider ;
- analyses longues ;
- preparation des consignes vers Codex.

Role :
documenter le travail strategique de GPT.

## 03_SSH_BOT_LIVE/

Chemin :

```text
03_SSH_BOT_LIVE/
```

Contenu attendu :
- informations sur le terminal SSH ;
- chemins Linux ;
- environnement virtuel ;
- sessions tmux ;
- scripts de lancement ;
- etat process bot ;
- reconciliation broker ;
- procedures operationnelles.

Role :
documenter le terrain operationnel.

Important :
aucune action SSH n'est autorisee dans la phase actuelle de demarrage documentaire GPT.

## 04_SYNC_DRIVE/

Chemin :

```text
04_SYNC_DRIVE/
```

Contenu attendu :
- paquet GPT vers Codex ;
- paquet Codex vers GPT ;
- politique de correlation GPT / Codex ;
- resume a donner a GPT ;
- etat de synchronisation Drive / GitHub.

Role :
servir de pont explicite entre GPT et Codex.

Regle :
aucune transmission operationnelle a Codex n'existe tant qu'un paquet `GPT vers Codex` n'est pas valide explicitement.

## 05_EXTENSIONS_MODULES/

Chemin :

```text
05_EXTENSIONS_MODULES/
```

Contenu attendu :
- Drive ;
- GitHub ;
- spreadsheets ;
- documents ;
- navigateur ;
- modules utiles ;
- procedures d'installation ou d'activation.

Role :
documenter les outils et extensions utilises autour du projet.

## 06_SECURITE_ACCES_SECRETS/

Chemin :

```text
06_SECURITE_ACCES_SECRETS/
```

Contenu attendu :
- politique de securite ;
- noms de variables d'environnement ;
- procedures d'acces sans valeurs sensibles ;
- rappels anti-secret.

Interdiction :
ne jamais stocker dans ce dossier :
- mot de passe ;
- cle API ;
- token ;
- code 2FA ;
- identifiant sensible complet ;
- secret broker.

## Regle de classement rapide

```text
Decision validee -> 00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
Question ouverte -> 00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
Regle maitre -> 00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
Doctrine GPT -> 02_PROJET_BOT_LIVE_GPT/
Diagnostic Codex -> 01_PROJET_BOT_LIVE_CODEX/
Etat SSH -> 03_SSH_BOT_LIVE/
Transmission GPT/Codex -> 04_SYNC_DRIVE/
Regle de pilotage -> 00_PILOTE_MEMOIRE/
Securite / secrets -> 06_SECURITE_ACCES_SECRETS/
```

## Regle de controle

Avant toute mise a jour documentaire, verifier :

- le type d'information ;
- le dossier cible ;
- le fichier cible ;
- si la decision est validee ou seulement proposee ;
- si une question doit rester ouverte ;
- si Codex doit etre informe ou non.

## Statut de la phase actuelle

La phase actuelle reste :

```text
Demarrage documentaire GPT
Aucune action code
Aucune action SSH
Aucune action broker
Aucune consigne operationnelle Codex
```
