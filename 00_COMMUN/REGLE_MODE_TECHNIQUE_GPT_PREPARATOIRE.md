# Regle - Mode Technique GPT Preparatoire

Date : 2026-05-19
Statut : verrou de securite valide par Codex

## Declencheur

Dans GPT, le mot utilisateur :

```text
Codex
```

active un mode technique preparatoire.

## Ce que cela autorise

GPT peut raisonner technique et produire :

- diagnostic de code depuis les fichiers disponibles ;
- proposition de patch ;
- extrait de code ;
- plan de test ;
- note de risque ;
- paquet `GPT -> Codex` ;
- fichier GitHub de proposition ou de memoire technique.

Chaque sortie technique GPT doit porter la mention :

```text
PROPOSITION GPT - NON EXECUTEE - VALIDATION CODEX REQUISE
```

## Publication GitHub autorisee

GPT peut publier ou demander de publier ses propositions dans GitHub uniquement
comme memoire ou brouillon, par exemple :

```text
04_SYNC/
02_GPT/
01_CODEX/03_PATCHES_MICROTOUCHES/PROPOSITIONS_GPT/
```

La publication doit indiquer clairement :

- aucun terminal execute ;
- aucun SSH ouvert ;
- aucun broker verifie ;
- aucun patch applique ;
- tests non lances sauf preuve contraire par Codex.

## Ce que cela n'autorise pas

Le mot `Codex` ne donne pas a GPT le droit de :

- modifier le terminal live ;
- ouvrir ou piloter SSH ;
- lancer `tmux` ;
- verifier ou manipuler le broker ;
- appliquer un patch dans le bot actif ;
- lancer des tests serveur ;
- envoyer ou fermer des ordres ;
- presenter une proposition comme code operationnel valide.

## Regle finale

GPT peut devenir technique dans la preparation. Codex reste obligatoire pour
l'execution, le terminal, le broker, les tests serveur et la validation finale.
