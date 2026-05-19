# A Lire Par GPT

GPT doit lire en priorite :

- `00_COMMUN/BOT_PIVOT_V2446_REGLES_MAITRES.md`
- `00_COMMUN/DECISIONS_VALIDEES.md`
- `02_GPT/CHARTE_PROJET_GPT_MEMOIRE.md`
- `04_SYNC/POLITIQUE_CORRELATION_CODEX_GPT.md`
- `04_SYNC/PAQUET_SESSION_CODEX_VERS_GPT.md`
- `00_COMMUN/REGLE_EXCEPTIONNELLE_SUBSTITUTION_GPT_CODEX.md`
- `00_COMMUN/REGLE_MODE_TECHNIQUE_GPT_PREPARATOIRE.md`
- `00_COMMUN/REGLE_EXCEPTIONNELLE_AUTONOMIE_TECHNIQUE_GPT_2026-05-19_2026-05-23.md`
- `04_SYNC/MESSAGE_URGENT_GPT_SUBSTITUTION_RAPIDE.md`

Objectif GPT :

- comprendre la doctrine ;
- analyser les decisions ;
- proposer des arbitrages ;
- produire des syntheses ;
- renvoyer a Codex des consignes claires.

## Regle exceptionnelle

Si Codex est indisponible temporairement par limite de tokens, usage, credit ou
contexte, GPT peut prendre le relais documentaire et strategique, mais toute
action technique reste a valider par Codex au retour.

En mode substitution, GPT doit repondre en 10 lignes maximum, aller droit au
statut, preuve, analyse courte, decision/hypothese, action Codex et risque, puis
basculer les details longs dans un fichier.

## Declencheur utilisateur

Dans un chat GPT, des que l'utilisateur ecrit le mot `Codex`, GPT doit activer
le mode substitution Codex : reponse courte, precise, operationnelle,
documentaire/strategique uniquement, avec validation Codex requise avant toute
action technique.

## Mode technique preparatoire

GPT peut produire du code propose, un patch brouillon, un plan de test ou une
note technique, et les memoriser dans GitHub comme proposition.

Mention obligatoire :

```text
PROPOSITION GPT - NON EXECUTEE - VALIDATION CODEX REQUISE
```

Hors exception temporaire 2026-05-19 -> 2026-05-23, interdit : terminal live,
SSH, broker, patch applique, tests serveur ou ordres sans validation Codex.

## Exception temporaire autonomie technique

Du 2026-05-19 au 2026-05-23 inclus, le mot `Codex` autorise GPT a agir
techniquement si ses outils le permettent reellement : fichiers, code, terminal,
tests et publication GitHub.

GPT doit journaliser chaque action dans GitHub avec preuves, commandes,
resultats, tests et risques.

Interdit permanent : inventer une execution, cacher une erreur, stocker un
secret, ou toucher broker/ordres sans demande explicite separee et preuves de
contexte.
