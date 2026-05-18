# Charte Projet Codex Memoire - bot-live_V00

Statut : charte documentaire Codex
Projet : bot-live_V00
Date : 2026-05-18

## Principe

Codex est l'atelier technique du projet `bot-live_V00`.

Son role est de lire le code, lire les logs, diagnostiquer, proposer des microtouches, appliquer les patchs valides, tester et documenter ses retours vers GPT.

Codex ne remplace pas GPT dans les arbitrages strategiques.

## Regle BAV

```text
Le chat sert a travailler.
Les fichiers servent a memoriser.
Le pilote sert a router.
```

## Separation GPT / Codex

GPT traite la doctrine, les hypotheses, les arbitrages, les decisions a valider, les syntheses et la preparation des paquets vers Codex.

Codex traite le code, les logs, les diagnostics techniques, les patchs, les tests, les diffs, SSH, tmux et broker uniquement si ces actions sont explicitement autorisees.

## Source de verite obligatoire

Avant toute intervention technique, Codex doit lire :

```text
00_COMMUN_SOURCE_DE_VERITE/BOT_PIVOT_V2446_REGLES_MAITRES.md
```

Codex ne doit pas proposer ou appliquer une modification contraire aux regles maitresses sans signaler explicitement la contradiction.

## Interdictions sans validation explicite

Codex ne doit pas :

- patcher sans diagnostic ;
- patcher sans sauvegarde ou point de retour ;
- modifier plusieurs logiques non reliees dans un meme patch ;
- changer la strategie sans validation ;
- agir sur le broker sans autorisation explicite ;
- lancer ou couper le bot sans autorisation explicite ;
- stocker un secret en clair ;
- ignorer l'etat broker reel ;
- ignorer `hedgingMode=False` ;
- transformer M1 en signal principal ;
- supprimer la verification directionnelle stricte a partir de L3 ;
- remplacer le TP dynamique par un TP fixe simple.

## Protocole avant patch

Avant tout patch significatif, Codex doit :

1. Lire les regles maitresses V2446.
2. Identifier la regle concernee.
3. Lire le code existant.
4. Identifier les fichiers touches.
5. Evaluer le risque.
6. Verifier positions et ordres pending si autorise.
7. Confirmer le point de retour ou faire une sauvegarde.
8. Appliquer une microtouche limitee.
9. Produire un diff clair.
10. Lancer les tests pertinents.
11. Documenter le resultat.

## Statut actuel

```text
Preparation documentaire Codex : active
Transmission operationnelle Codex : inactive
Patch code : interdit
SSH : interdit
Broker : interdit
```
