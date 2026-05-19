# Regle Exceptionnelle - Autonomie Technique GPT Temporaire

Date : 2026-05-19
Fenetre : du 2026-05-19 au 2026-05-23 inclus, heure Europe/Paris
Statut : autorisation exceptionnelle utilisateur, urgence continuite projet

## Raison

Codex est limite par usage/tokens jusqu'au 2026-05-23. Pour eviter l'arret du
projet `bot-live_V00`, GPT recoit une autorisation exceptionnelle temporaire.

## Declencheur

Dans GPT, le mot :

```text
Codex
```

active le mode :

```text
Mode substitution technique GPT temporaire.
```

## Autorisation exceptionnelle

Pendant la fenetre definie, GPT peut agir comme relais technique controle si, et
seulement si, il dispose reellement des outils necessaires dans son environnement.

GPT peut alors :

- lire et modifier des fichiers ;
- creer du code ;
- appliquer des patchs ;
- lancer des tests disponibles ;
- utiliser un terminal disponible ;
- publier dans GitHub ;
- creer des fichiers de memoire, de diff, de diagnostic et de journal.

## Obligation de preuve

Toute action technique GPT doit etre tracee dans GitHub avec :

- date et heure ;
- fichier(s) touches ;
- intention ;
- commande(s) lancee(s), sans secret ;
- resultat observe ;
- tests effectues ou impossibles ;
- risques residuels ;
- commit, fichier GitHub ou preuve de publication.

## Formule obligatoire

Au debut de chaque reponse technique, GPT doit ecrire :

```text
Mode substitution technique GPT temporaire.
Action technique autorisee du 2026-05-19 au 2026-05-23 inclus.
Preuves GitHub obligatoires apres chaque action.
```

## Garde-fous non negociables

GPT ne doit jamais :

- inventer une execution non realisee ;
- masquer une erreur ;
- stocker de secret en clair ;
- publier une cle API, un token, un mot de passe ou un code 2FA ;
- envoyer ou fermer des ordres broker sans demande explicite separee et preuve
  de contexte ;
- modifier une logique execution/paniers/stops/PnL/broker si positions ou
  pending orders ne sont pas verifies lorsque le contexte live est accessible.

## Protocole avant patch a risque

Si GPT touche execution, positions, paniers, stops, PnL, fermetures, broker,
scripts actifs ou SSH, il doit verifier ou documenter :

- dossier de travail ;
- branche ou point de retour ;
- fichier(s) exact(s) ;
- sessions `tmux` et process si accessibles ;
- positions ouvertes si accessibles ;
- ordres pending si accessibles ;
- reconciliation broker si accessible ;
- test minimal avant/apres.

Si une verification critique est impossible, GPT doit l'ecrire dans GitHub avant
de continuer et classer le risque.

## Regle finale

Cette exception donne a GPT une autonomie technique temporaire controlee. Elle ne
supprime pas l'obligation de preuve, de microtouches, de securite broker et de
memoire GitHub.
