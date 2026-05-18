# Strategie Globale BOT-PIVOT V2446

Statut : strategie validee par Philippe
Projet : bot-live_V00
Date : 2026-05-18
Bloc : 02_PROJET_BOT_LIVE_GPT/STRATEGIE
Role : orientation strategique GPT

## 1. Objet du fichier

Ce fichier contient la strategie globale validee pour BOT-PIVOT V2446.

Il ne modifie pas la doctrine deja posee.
Il ne constitue pas une consigne de patch.
Il sert a fixer l'orientation strategique avant toute transmission technique vers Codex.

## 2. Strategie globale validee

BOT-PIVOT V2446 doit fonctionner comme un bot de scalping par scenario M15/M5.

Le bot ne doit pas chercher a predire parfaitement le marche.
Il doit chercher a entrer uniquement quand le scenario est suffisamment coherent, puis gerer le panier tant que ce scenario reste vivant.

## 3. Repartition des timeframes

```text
M15 choisit le camp strategique.
M5 confirme que ce camp est encore jouable.
M1 sert uniquement au timing fin.
```

M1 ne doit pas devenir signal principal.
M1 ne doit pas inverser seul une decision M15/M5.

## 4. Strategie de panier

Le panier construit progressivement seulement si le scenario reste vivant.

```text
L1 = entree initiale sur preuve minimale documentee.
L2 = renfort controle si adverse step atteint et scenario encore valide.
L3 = seuil de verite directionnelle.
L4/L5 = niveaux extremes encadres, jamais mecaniques.
```

A partir de L3, le bot doit verifier strictement si l'alignement M15/M5 reste valide.

## 5. Invalidation directionnelle

A partir de L3, toute invalidation M15/M5 impose la coupe complete du panier.

Le bot ne doit pas attendre le stop global si le scenario initial est strategiquement casse.

## 6. Retournement directionnel

Aucun retournement directionnel n'est autorise sans FLAT broker confirme.

```text
Pas de SELL vers BUY direct.
Pas de BUY vers SELL direct.
Retour FLAT obligatoire.
FLAT confirme cote broker, pas seulement localement.
```

## 7. Priorites strategiques avant consigne Codex

```text
1. Definir les cas BUY, SELL, WAIT, REFUS et ENTREE RETARDEE.
2. Definir l'invalidation avant L3 et a partir de L3.
3. Borner strictement le role du M1 au timing fin.
4. Verifier que les renforts ne sont pas mecaniques mais conditionnes par le scenario.
5. Exiger des logs explicables pour entree, refus, renfort, maintien, coupe et blocage broker.
```

## 8. Precision importante

Cette strategie est une orientation validee.
Elle ne remplace pas les regles maitresses V2446.
Elle ne modifie pas la doctrine strategique phase 02.
Elle sert de document de travail strategique pour GPT avant transmission eventuelle a Codex.
