# Synthese Demarrage Documentaire GPT - 2026-05-18

Statut : synthese de session GPT
Projet : bot-live_V00
Phase : 01 - Demarrage documentaire GPT

## 1. Objet de la session

Cette session a servi a demarrer proprement le projet GPT strategique `bot-live_V00`.

L'objectif n'etait pas de modifier le bot, de patcher du code, d'agir sur SSH, d'intervenir sur le broker ou de transmettre une consigne operationnelle a Codex.

L'objectif etait de construire la memoire durable du projet autour de la regle BAV.

## 2. Regle BAV confirmee

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

Aucune decision importante ne doit rester seulement dans le chat.

Une decision devient durable seulement lorsqu'elle est inscrite dans un fichier memoire officiel.

## 3. Espaces officiels valides

### Drive documentaire officiel

```text
TRADING/bot-live_V00
```

Role :
- coffre documentaire lisible ;
- support de consultation utilisateur ;
- pont documentaire simple entre GPT et Codex.

### GitHub memoire Markdown versionnee officielle

```text
philippevacher06-sudo/bot-live_V00
```

Role :
- versionner les fichiers Markdown ;
- suivre les diffs ;
- conserver l'historique ;
- rendre les decisions auditables ;
- permettre une reprise propre entre sessions.

## 4. Decisions validees pendant la session

### 2026-05-18 - Coffre Drive officiel

Decision :
`TRADING/bot-live_V00` devient le coffre Drive officiel du projet `bot-live_V00`.

### 2026-05-18 - Depot GitHub officiel

Decision :
`philippevacher06-sudo/bot-live_V00` devient le depot GitHub officiel pour la memoire Markdown versionnee du projet `bot-live_V00`.

## 5. Fichiers crees dans GitHub

### Source de verite commune

```text
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

### Pilote memoire

```text
00_PILOTE_MEMOIRE/INDEX_PILOTE.md
00_PILOTE_MEMOIRE/MODE_GPT.md
00_PILOTE_MEMOIRE/MODE_CODEX.md
00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
00_PILOTE_MEMOIRE/ROUTAGE_CLAVARDAGES.md
00_PILOTE_MEMOIRE/COMMANDES_UTILISATEUR.md
```

### Synchronisation GPT / Codex

```text
04_SYNC_DRIVE/POLITIQUE_CORRELATION_CODEX_GPT.md
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
04_SYNC_DRIVE/PAQUET_SESSION_CODEX_VERS_GPT.md
```

### Memoire strategique GPT

```text
02_PROJET_BOT_LIVE_GPT/CHARTE_PROJET_GPT_MEMOIRE.md
02_PROJET_BOT_LIVE_GPT/00_INDEX_GPT/INDEX_GPT.md
02_PROJET_BOT_LIVE_GPT/01_DOCTRINE_STRATEGIQUE/DOCTRINE_GPT.md
```

## 6. Statut de Codex

Aucune transmission operationnelle vers Codex n'est active.

Les fichiers suivants sont seulement des modeles documentaires non operationnels :

```text
04_SYNC_DRIVE/PAQUET_SESSION_GPT_VERS_CODEX.md
04_SYNC_DRIVE/PAQUET_SESSION_CODEX_VERS_GPT.md
```

Codex ne doit pas interpreter ces fichiers comme une demande de patch, de test, d'action SSH, d'action broker ou de modification du bot.

## 7. Actions explicitement interdites dans cette phase

```text
Patch code : interdit
Action SSH : interdite
Action broker : interdite
Modification technique du bot : interdite
Transmission operationnelle a Codex : inactive
Creation de fichiers hors espaces officiels : interdite
```

## 8. Source de verite BOT-PIVOT V2446

Le fichier central est :

```text
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

Il contient notamment :

- la doctrine generale ;
- les 50 regles maitresses V2446 ;
- les interdictions strategiques ;
- le protocole Codex avant modification ;
- le protocole de synchronisation GPT / Codex ;
- la checklist rapide avant session.

Toute future analyse strategique ou technique devra etre comparee a ce fichier.

## 9. Questions ouvertes restantes

Les questions ouvertes sont conservees dans :

```text
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
```

Points encore ouverts notamment :

- GitHub doit-il devenir la source prioritaire pour les fichiers Markdown versionnes, avec Drive comme coffre documentaire lisible ?
- Le code Linux sera-t-il copie dans Codex ou analyse via SSH ?
- Quel est le script exact de reconciliation broker ?
- Quels scripts de lancement sont encore actifs ?
- Quelles anciennes methodes doivent etre archivees ou abandonnees ?
- Quel format final GPT doit-il produire par defaut : Markdown brut, document Drive, ou les deux ?
- Quelle procedure standard doit suivre le retour Codex vers GPT apres diagnostic technique ?
- A quel moment une proposition GPT devient-elle une decision validee ?
- Qui met a jour `00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md` selon le type de decision ?

## 10. Phase actuelle

```text
01 - Demarrage documentaire GPT
```

Cette phase peut continuer tant que l'objectif reste documentaire.

## 11. Prochaine suite logique

Prochaine action recommandee :

```text
Creer les premiers fichiers vides ou modeles dans les dossiers GPT suivants :
02_PROJET_BOT_LIVE_GPT/03_DECISIONS_ET_ARBITRAGES/
02_PROJET_BOT_LIVE_GPT/05_HYPOTHESES_A_TESTER/
02_PROJET_BOT_LIVE_GPT/06_REGLES_A_VALIDER/
```

Puis, lorsque la base documentaire sera suffisante, ouvrir eventuellement une nouvelle session GPT specialisee :

```text
02 - Doctrine strategique
```

## 12. Regle de reprise

Pour reprendre ce projet dans un nouveau chat GPT, lire en priorite :

```text
00_PILOTE_MEMOIRE/INDEX_PILOTE.md
00_PILOTE_MEMOIRE/MODE_GPT.md
00_PILOTE_MEMOIRE/ROUTAGE_FICHIERS.md
00_PILOTE_MEMOIRE/ROUTAGE_CLAVARDAGES.md
00_COMMUN_SOURCE_DE_VERITE/DECISIONS_VALIDEES.md
00_COMMUN_SOURCE_DE_VERITE/QUESTIONS_OUVERTES_GLOBALES.md
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
04_SYNC_DRIVE/POLITIQUE_CORRELATION_CODEX_GPT.md
02_PROJET_BOT_LIVE_GPT/CHARTE_PROJET_GPT_MEMOIRE.md
02_PROJET_BOT_LIVE_GPT/00_INDEX_GPT/INDEX_GPT.md
02_PROJET_BOT_LIVE_GPT/01_DOCTRINE_STRATEGIQUE/DOCTRINE_GPT.md
```

## 13. Conclusion

La base documentaire GitHub du projet `bot-live_V00` est maintenant amorcee proprement.

Le projet dispose d'une premiere architecture de memoire durable, d'une separation GPT / Codex, d'une source de verite V2446, et de modeles de synchronisation.

Aucune action technique n'a ete declenchee.
Aucune consigne operationnelle n'a ete envoyee a Codex.
