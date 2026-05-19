# Journal Codex - Consigne GPT Substitution Rapide

Date : 2026-05-19
Statut : intervention documentaire publiee GitHub

## Objectif

Corriger la derive de reponses GPT trop longues et trop lentes en mode
substitution Codex.

## Decision utilisateur

- GPT doit repondre en 10 lignes maximum en mode substitution, sauf demande
  explicite de document complet.
- GPT doit utiliser une architecture courte : statut, preuve, analyse,
  decision/hypothese, action Codex, risque.
- GPT doit apprendre des erreurs de codage detectees et ne jamais pretendre
  corriger techniquement sans validation Codex.

## Fichiers GitHub modifies ou crees

- `00_COMMUN/REGLE_EXCEPTIONNELLE_SUBSTITUTION_GPT_CODEX.md`
- `00_COMMUN/DECISIONS_VALIDEES.md`
- `04_SYNC/A_LIRE_PAR_GPT.md`
- `04_SYNC/MESSAGE_URGENT_GPT_SUBSTITUTION_RAPIDE.md`
- `01_CODEX/09_JOURNAL_CODEX/2026-05-19_CONSIGNE_GPT_SUBSTITUTION_RAPIDE.md`

## Contraintes

- Aucun code modifie.
- Aucun test lance.
- Aucune action SSH effectuee.
