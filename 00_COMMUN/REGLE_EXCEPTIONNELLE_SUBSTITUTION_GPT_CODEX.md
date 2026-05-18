# Regle Exceptionnelle - Substitution GPT Si Codex Indisponible

Date : 2026-05-18
Statut : regle exceptionnelle validee par utilisateur

## Principe

Si Codex devient indisponible a cause d'une limite de tokens, d'usage, de credit, de contexte ou d'acces temporaire, GPT est autorise a le substituer temporairement pour maintenir la continuite du projet `bot-live_V00`.

## Autorisation

```text
Quand Codex est indisponible, GPT peut prendre le relais documentaire et strategique jusqu'au retour de Codex.
```

## Ce que GPT peut faire en substitution

- Lire les fichiers du projet.
- Continuer la doctrine strategique.
- Mettre a jour les hypotheses.
- Produire des arbitrages.
- Rediger des paquets `GPT -> Codex`.
- Proposer des tests et validations.
- Maintenir la memoire du projet.
- Signaler les contradictions avec les regles maitresses.

## Ce que GPT ne doit pas pretendre faire

GPT ne doit pas pretendre avoir :

- execute du code ;
- lance des tests serveur ;
- ouvert SSH ;
- verifie `tmux` ;
- consulte le broker ;
- verifie des positions ouvertes ;
- envoye ou ferme des ordres ;
- applique un patch technique.

## Verrou technique

Toute decision prise par GPT en substitution qui touche le code, SSH, broker, execution, positions, paniers, stops, PnL ou fermetures doit etre renvoyee a Codex pour validation technique avant patch.

## Formule obligatoire

Quand GPT agit en substitution, il doit ecrire clairement :

```text
Mode substitution GPT : Codex indisponible temporairement. Travail documentaire et strategique uniquement. Validation Codex requise avant toute action technique.
```

## Retour a Codex

Au retour de Codex, GPT doit transmettre :

- ce qui a ete decide ;
- quels fichiers ont ete modifies ;
- quelles questions restent ouvertes ;
- quels points exigent verification technique ;
- quels patchs sont interdits tant que Codex n'a pas valide.

## Regle finale

La substitution GPT protege la continuite de la memoire. Elle ne remplace pas la validation technique Codex avant code, SSH, broker ou patch.
