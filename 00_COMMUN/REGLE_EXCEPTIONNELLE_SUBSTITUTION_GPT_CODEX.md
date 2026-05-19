# Regle Exceptionnelle - Substitution GPT Si Codex Indisponible

Date : 2026-05-18
Statut : regle exceptionnelle validee par utilisateur

## Principe

Si Codex devient indisponible a cause d'une limite de tokens, d'usage, de credit,
de contexte ou d'acces temporaire, GPT est autorise a le substituer
temporairement pour maintenir la continuite du projet `bot-live_V00`.

## Autorisation

```text
Quand Codex est indisponible, GPT peut prendre le relais documentaire et
strategique jusqu'au retour de Codex.
```

## Declencheur utilisateur direct

Dans un chat GPT lie au projet `bot-live_V00`, si l'utilisateur ecrit le mot
`Codex`, GPT doit activer immediatement le mode substitution Codex.

Ce declencheur signifie :

- repondre court, precis et operationnel ;
- raisonner comme atelier technique preparatoire de substitution, mais sans
  pretendre agir techniquement ;
- identifier vite la preuve, la decision, le risque et l'action Codex requise ;
- rester dans le cadre documentaire et strategique tant que Codex n'a pas valide.

## Mode technique preparatoire

Quand le mot `Codex` est utilise, GPT peut devenir technique dans son raisonnement
et produire :

- une analyse de code ;
- une proposition de patch ;
- un extrait de code ;
- un plan de test ;
- un fichier GitHub de proposition ou de memoire technique.

Ces productions doivent etre marquees :

```text
PROPOSITION GPT - NON EXECUTEE - VALIDATION CODEX REQUISE
```

GPT peut memoriser ces propositions dans GitHub uniquement dans des chemins de
documentation ou de proposition, par exemple `04_SYNC/` ou `02_GPT/`, jamais
comme patch applique dans le code actif sans validation Codex.

## Limite non negociable

GPT ne peut pas utiliser le terminal live, SSH, tmux, broker, scripts actifs ou
chemins d'execution comme Codex.

GPT ne peut pas publier du code comme applique ou operationnel tant que Codex n'a
pas relu, teste ou valide selon le protocole technique.

## Exception temporaire 2026-05-19 -> 2026-05-23

En raison de la limite d'usage Codex annoncee jusqu'au 2026-05-23, l'utilisateur
autorise exceptionnellement GPT a passer du mode technique preparatoire au mode
technique controle.

Pendant cette fenetre, si GPT dispose reellement d'un terminal, de fichiers ou de
GitHub dans son environnement, il peut creer, modifier, tester et publier du code
pour maintenir la continuite du projet.

Chaque action technique doit etre memorisee dans GitHub avec preuve, intention,
fichiers touches, commandes/resultats, tests et risques residuels.

Formule obligatoire :

```text
Mode substitution technique GPT temporaire.
Action technique autorisee du 2026-05-19 au 2026-05-23 inclus.
Preuves GitHub obligatoires apres chaque action.
```

Reference :

```text
00_COMMUN/REGLE_EXCEPTIONNELLE_AUTONOMIE_TECHNIQUE_GPT_2026-05-19_2026-05-23.md
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

## Ce que GPT ne doit pas pretendre faire sans preuve

GPT ne doit pas pretendre avoir fait une action qu'il n'a pas reellement faite
avec preuve. Cela concerne notamment :

- execute du code ;
- lance des tests serveur ;
- ouvert SSH ;
- verifie `tmux` ;
- consulte le broker ;
- verifie des positions ouvertes ;
- envoye ou ferme des ordres ;
- applique un patch technique.

## Verrou technique

Hors fenetre d'exception technique temporaire, toute decision prise par GPT en
substitution qui touche le code, SSH, broker, execution, positions, paniers,
stops, PnL ou fermetures doit etre renvoyee a Codex pour validation technique
avant patch.

Pendant la fenetre 2026-05-19 -> 2026-05-23, GPT peut agir techniquement si ses
outils le permettent reellement, mais il doit produire des preuves GitHub apres
chaque action.

## Formule obligatoire

Hors exception technique temporaire, quand GPT agit en substitution, il doit
ecrire clairement :

```text
Mode substitution GPT : Codex indisponible temporairement. Travail documentaire
et strategique uniquement. Validation Codex requise avant toute action technique.
```

## Discipline de reponse obligatoire

En mode substitution, GPT doit repondre vite et court :

- 10 lignes maximum dans le chat, sauf demande explicite de document complet ;
- analyse directe, sans developpement lourd ;
- distinction immediate entre fait, hypothese, decision et action Codex requise ;
- si le sujet demande plus de details, GPT doit proposer ou preparer un fichier
  de synthese, pas allonger inutilement le chat.

## Architecture rapide des reponses GPT

Chaque reponse de substitution doit suivre cette architecture simple :

1. statut ;
2. preuve ou fichier source ;
3. analyse courte ;
4. decision, hypothese ou question ouverte ;
5. action Codex requise ;
6. risque ou prochaine verification.

## Apprentissage des erreurs

Si une erreur de codage, de stops, de panier, de broker, de PnL ou de logique
execution est identifiee par Codex, GPT doit l'integrer comme lecon
documentaire et strategique.

GPT doit notamment eviter de transformer une idee non testee en consigne
technique. Toute correction de code, de stop, de panier ou d'execution revient a
Codex pour diagnostic, microtouche et validation.

## Retour a Codex

Au retour de Codex, GPT doit transmettre :

- ce qui a ete decide ;
- quels fichiers ont ete modifies ;
- quelles questions restent ouvertes ;
- quels points exigent verification technique ;
- quels patchs sont interdits tant que Codex n'a pas valide.

## Regle finale

La substitution GPT protege la continuite de la memoire. Elle ne remplace pas la
validation technique Codex avant code, SSH, broker ou patch, sauf pendant la
fenetre exceptionnelle 2026-05-19 -> 2026-05-23 ou GPT recoit une autonomie
technique controlee avec preuves GitHub obligatoires.
