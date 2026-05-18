# Doctrine Strategique - Phase 02

Statut : valide par Philippe
Projet : bot-live_V00
Date : 2026-05-18
Bloc : 02_PROJET_BOT_LIVE_GPT
Role : miroir strategique GPT

## 1. Cadre general

La phase 02 ouvre le travail de doctrine strategique du projet `bot-live_V00`.

GitHub est la source commune principale entre GPT et Codex.
Le chat reste un atelier de travail.
La memoire durable doit etre conservee dans les fichiers du projet.

Codex reste l'atelier technique : code, logs, patchs, tests, SSH, broker.
GPT reste le miroir strategique : doctrine, arbitrages, hypotheses, decisions, syntheses et consignes vers Codex.

## 2. Doctrine centrale V2446 a respecter

```text
M15 = signal maitre
M5 = confirmation du M15
M1 = timing fin uniquement, jamais signal principal
Maximum 5 legs
Controle directionnel strict a partir de L3
Pas de retournement sans FLAT broker confirme
TP dynamique selon le nombre de legs
PnL realiste Capital.com : BUY sorti au BID, SELL sorti a l'ASK
UPL broker fiable prioritaire
Microtouches uniquement : petits changements, testables, reversibles
```

## 3. Tension strategique principale

La difficulte centrale de la V2446 n'est pas seulement technique.
Elle est doctrinale.

Le bot doit rester assez actif pour faire du scalping reel, mais il ne doit pas redevenir impulsif.
La regle `Pas de preuve, pas de trade` ne doit pas devenir une excuse pour ne jamais trader.
Elle ne doit pas non plus etre affaiblie silencieusement.

La doctrine validee est donc :

```text
Pas de preuve, pas de trade.
Mais preuve ne veut pas dire certitude.
Preuve veut dire alignement minimal documente.
```

## 4. Definition de la preuve suffisante

Une preuve suffisante d'entree n'est pas un signal parfait.
C'est un alignement minimal entre :

```text
1. Signal maitre M15 clair
2. Confirmation M5 coherente
3. Prix situe dans une zone acceptable d'intervention
4. Absence de contradiction directionnelle forte
5. Risque panier compatible avec les regles V2446
6. Log capable d'expliquer pourquoi le trade est accepte
```

Cette definition doit permettre au bot de trader sans abaisser silencieusement le niveau de qualite.

## 5. Doctrine d'entree

La doctrine d'entree doit eviter trois erreurs :

```text
Erreur 1 : entrer trop tot
Erreur 2 : entrer a contre-sens du vrai mouvement
Erreur 3 : refuser tous les signaux par exces de prudence
```

Regle strategique :

```text
M15 donne le camp principal.
M5 confirme que le camp M15 est encore valide.
M1 sert uniquement au timing fin.
M1 ne doit jamais inverser seul la decision.
```

Si M15 et M5 sont alignes, le bot peut chercher une entree dans ce sens.
Si M1 contredit legerement, il peut retarder l'entree, mais il ne doit pas inverser la doctrine.
Si M15 et M5 divergent, le signal est fragile ou interdit, sauf regle explicite validee plus tard.

## 6. Doctrine de panier

La V2446 est un bot de construction de panier, pas seulement un bot entree/sortie.

Structure strategique du panier :

```text
L1 = tentative initiale
L2 = renfort controle
L3 = seuil critique strategique
L4/L5 = niveaux extremes encadres
```

A partir de L3, le bot doit verifier si le scenario initial est encore vivant.
Si l'alignement M15/M5 est rompu a partir de L3, le panier doit etre coupe immediatement, sans attendre le stop global.

Principe valide :

```text
L3 = seuil de verite directionnelle.
```

## 7. Doctrine de retournement

Avec `hedgingMode=False`, aucun retournement direct ne doit etre autorise.

Regle :

```text
Pas de SELL vers BUY direct.
Pas de BUY vers SELL direct.
Retour FLAT obligatoire.
FLAT confirme broker, pas seulement suppose localement.
```

Le bot ne retourne pas une position.
Il ferme, verifie l'etat broker, puis seulement ensuite il peut reconstruire.

## 8. Doctrine de sortie

Le TP ne doit pas redevenir un TP fixe simple.
La sortie reste dynamique selon le nombre de legs.

Regle V2446 conservee :

```text
2 legs -> +1 EUR
3 legs -> +2 EUR
4 legs -> +4 EUR
5 legs -> +8 EUR
```

Le calcul de PnL doit rester compatible avec Capital.com :

```text
BUY valorise a la sortie au BID
SELL valorise a la sortie a l'ASK
UPL broker prioritaire si fiable
```

## 9. Doctrine des microtouches

Codex ne doit pas transformer une decision strategique en refonte globale.

Regle de travail :

```text
Une modification = une intention
Une intention = une zone du bot
Une zone modifiee = un test cible
Un test = un resultat lisible
```

Interdiction strategique :

```text
Ne pas corriger les signaux, le panier, le TP et le broker dans le meme patch.
```

La boucle de progression reste :

```text
Observer -> Diagnostiquer -> Decider -> Patch minimal -> Tester -> Mesurer -> Documenter
```

## 10. Axes de travail GPT pour la phase 02

### Axe A - Preuve minimale d'entree

Definir precisement :

```text
Signal BUY acceptable
Signal SELL acceptable
Cas d'attente
Cas de refus
Cas ou une imperfection mineure reste acceptable
```

### Axe B - Invalidation directionnelle

Definir precisement :

```text
Invalidation avant L3 = prudence, attente ou refus de renfort
Invalidation a partir de L3 = coupe stricte si M15/M5 sont rompus
Invalidation apres retournement fort = fermeture panier avant stop global
```

### Axe C - Consignes propres vers Codex

Toute consigne Codex issue de GPT doit suivre ce format :

```text
Contexte :
Decision strategique :
Regles V2446 concernees :
Comportement attendu :
Interdictions :
Test minimal demande :
Logs attendus :
```

## 11. Decision structurante validee

```text
La V2446 ne doit pas chercher a predire parfaitement le marche.
Elle doit chercher a entrer uniquement quand le scenario M15/M5 est suffisamment coherent,
puis couper sans discuter quand ce scenario est invalide a partir de L3.
```

Formule operationnelle :

```text
Entree = preuve suffisante, pas certitude.
Maintien = coherence du scenario.
Renfort = adverse step controle.
L3 = seuil de verite.
Sortie = TP dynamique ou invalidation directionnelle.
```

## 12. Consigne strategique initiale vers Codex

```text
Codex, lire BOT_PIVOT_V2446_REGLES_MAITRES.md avant toute action.

Objectif strategique phase 02 :
verifier que le comportement reel du bot respecte la doctrine suivante :

- M15 reste le signal maitre ;
- M5 confirme M15 ;
- M1 ne declenche pas seul une inversion ;
- aucun retournement BUY/SELL ou SELL/BUY sans FLAT broker confirme ;
- a partir de L3, si l'alignement M15/M5 est rompu, le panier complet doit etre ferme ;
- le TP reste dynamique selon le nombre de legs ;
- le PnL de fermeture doit respecter BID/ASK ou UPL broker fiable ;
- tout changement doit etre une microtouche testable.

Ne pas patcher immediatement.
Commencer par produire un diagnostic :
1. ou le code respecte deja ces regles ;
2. ou le code est ambigu ;
3. ou le code contredit les regles ;
4. quels logs manquent pour prouver les decisions.
```

## 13. Premier chantier ouvert

Le premier chantier strategique propre de la phase 02 est :

```text
Definir precisement la preuve suffisante d'entree M15/M5,
afin que le bot trade reellement sans redevenir impulsif.
```
