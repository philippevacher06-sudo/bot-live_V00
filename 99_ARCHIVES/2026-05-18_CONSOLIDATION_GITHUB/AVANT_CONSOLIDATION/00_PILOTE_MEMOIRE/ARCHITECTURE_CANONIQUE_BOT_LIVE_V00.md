# Architecture Canonique - bot-live_V00

Statut : architecture canonique
Projet : bot-live_V00
Date : 2026-05-18
Source : synthese Codex validee par Philippe

## Objectif

Creer une memoire de projet durable pour BOT-PIVOT / bot-live, avec Codex cote technique, GPT cote strategie, et GitHub comme source commune principale.

## Regle fondamentale

```text
Le chat n'est pas la memoire durable.
La memoire durable est dans les fichiers.
Les clavardages sont des ateliers specialises.
GitHub est la source commune versionnee entre Codex et GPT.
Drive reste secondaire, utile en lecture et en appoint.
```

## Projet Codex local

```text
C:/Users/phila/Documents/Codex/bot-live_V00
```

## Blocs principaux

### 1. 00_PILOTE_MEMOIRE

Role : mini systeme de pilotage du projet.

Contenu : modes Codex/GPT, routage des clavardages, routage des fichiers, checklists debut/fin de session, commandes utilisateur.

### 2. 00_COMMUN_SOURCE_DE_VERITE

Role : verite commune du projet.

Contenu : regles maitresses, decisions validees, questions ouvertes, etat courant, glossaire, protocole memoire.

### 3. 01_PROJET_BOT_LIVE_CODEX

Role : atelier technique Codex.

Contenu : cartographie code, diagnostics logs, patchs microtouches, tests validation, broker, signaux, paniers, PnL/risk/stops, journal Codex.

### 4. 02_PROJET_BOT_LIVE_GPT

Role : miroir strategique GPT.

Contenu : doctrine, analyses, decisions/arbitrages, syntheses, hypotheses, regles a valider, consignes GPT.

### 5. 03_SSH_BOT_LIVE

Role : moteur operationnel.

Contenu : etat terminal SSH, acces non sensibles, chemins Linux, tmux/process, checklist sante terminal, reconciliation broker, nettoyage anciennes methodes.

### 6. 04_SYNC_DRIVE

Role historique : synchro Drive.

Role actuel : zone de transition/synchronisation.

Decision : GitHub remplace Drive comme source principale. Drive reste secondaire.

### 7. 05_EXTENSIONS_MODULES

Role : etat des modules.

Contenu : Google Drive installe, GitHub installe, Spreadsheets/Documents/Browser disponibles.

### 8. 06_SECURITE_ACCES_SECRETS

Role : politique de securite.

Regle : ne pas stocker de donnees sensibles dans les fichiers memoire.

### 9. 07_APPRENTISSAGE_PERFORMANCE

Role prevu : amelioration continue.

Boucle : observer -> comprendre -> decider -> tester -> mesurer -> ameliorer.

A creer ou consolider apres les 8 premiers axes.

### 10. 99_ARCHIVES

Role : archives, snapshots, anciennes methodes.

## Clavardages Codex crees ou prevus

1. Validation architecture V00
2. Sync Drive GitHub
3. SSH bot-live sante terminal
4. Projet GPT doctrine strategie
5. Cartographie code bot-live
6. Diagnostics logs
7. Patches microtouches
8. Tests validation
9. Apprentissage performance

## Role des clavardages

Chaque clavardage est un atelier specialise.

Ils ne se synchronisent pas automatiquement entre eux.

Ils sont relies par les fichiers du projet et GitHub.

## Role de Codex

- lire le code ;
- diagnostiquer ;
- preparer ou appliquer des micro-patchs ;
- produire les diffs ;
- tester ;
- verifier SSH/broker ;
- mettre a jour les fichiers memoire.

## Role de GPT

- doctrine ;
- strategie ;
- analyses longues ;
- decisions et arbitrages ;
- hypotheses ;
- syntheses ;
- preparation des consignes vers Codex.

## Regle GitHub

GitHub devient la source commune principale.

Toute decision durable doit finir dans GitHub.

Si une information reste seulement dans un chat ou seulement dans Drive, elle n'est pas encore la source commune definitive.

## Regle de fin de session Codex

Mettre a jour au minimum :

```text
JOURNAL_CODEX.md
PAQUET_SESSION_CODEX_VERS_GPT.md si GPT doit relire
QUESTIONS_OUVERTES_GLOBALES.md si un point reste ouvert
```

## Regle de fin de session GPT

Mettre a jour ou produire :

```text
PAQUET_SESSION_GPT_VERS_CODEX.md
synthese strategique
decisions/arbitrages
questions ouvertes
propositions de regles a valider
```

## Doctrine trading centrale

- M15 est le signal maitre ;
- M5 confirme M15 ;
- M1 ne devient jamais signal principal ;
- maximum 5 legs ;
- controle directionnel strict a partir de L3 ;
- pas de retournement sans FLAT broker confirme ;
- TP dynamique selon legs ;
- PnL realiste Capital.com : BUY au BID, SELL a l'ASK ;
- UPL broker fiable prioritaire ;
- pas de patch sans preuve, diagnostic, sauvegarde et test.

## Regle de simplification

Ce fichier est l'entree canonique courte.

Les autres fichiers detaillent seulement si necessaire.

Navigation prioritaire : README -> architecture canonique -> index pilote -> source de verite V2446.
