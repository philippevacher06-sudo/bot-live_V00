# Journal Codex - Mode Technique GPT Preparatoire

Date : 2026-05-19
Statut : intervention documentaire publiee GitHub

## Objectif

Traiter la demande utilisateur voulant que le mot `Codex` rende GPT technique et
capable de produire du code.

## Decision appliquee

- GPT peut produire du code propose, des patchs brouillons, des plans de test et
  des notes techniques.
- GPT peut memoriser ces propositions dans GitHub.
- Toute proposition doit porter `PROPOSITION GPT - NON EXECUTEE - VALIDATION CODEX REQUISE`.
- GPT ne peut pas toucher au terminal live, SSH, broker, scripts actifs, tests
  serveur ou ordres sans validation Codex.

## Contradiction signalee

Donner a GPT le droit d'appliquer ou publier du code comme operationnel depuis le
terminal contredirait les regles maitresses V2446 et le protocole SSH/broker
avant patch.

## Fichiers GitHub modifies ou crees

- `00_COMMUN/REGLE_EXCEPTIONNELLE_SUBSTITUTION_GPT_CODEX.md`
- `00_COMMUN/REGLE_MODE_TECHNIQUE_GPT_PREPARATOIRE.md`
- `00_COMMUN/DECISIONS_VALIDEES.md`
- `04_SYNC/A_LIRE_PAR_GPT.md`
- `04_SYNC/MESSAGE_URGENT_GPT_SUBSTITUTION_RAPIDE.md`
- `01_CODEX/09_JOURNAL_CODEX/2026-05-19_MODE_TECHNIQUE_GPT_PREPARATOIRE.md`

## Contraintes

- Aucun code bot modifie.
- Aucun test lance.
- Aucune action SSH effectuee.
