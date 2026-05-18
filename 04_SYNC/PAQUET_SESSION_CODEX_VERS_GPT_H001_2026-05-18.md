# Paquet Session Codex Vers GPT - H-001

Date : 2026-05-18
Statut : paquet documentaire GitHub, aucun patch bot

## Resume

Codex a prepare la strategie `PANIER_CROSS_HEDGE_US500_US100_V1` comme hypothese a tester avant patch.

## Points principaux

- Panier principal uniquement US500 : L1 0.07, L2 0.14, L3 0.21.
- Steps automatiques : L2 a 3 points adverses apres L1, L3 a 3 points adverses apres L2.
- L4 secours US100 0.08 a 3 points adverses US500 apres L3.
- Direction L4 : US500 BUY -> US100 SELL ; US500 SELL -> US100 BUY.
- Aucun L5.
- Aucun renfort US100.
- Sortie gain apres L4 : PnL broker cumule US500+US100 >= +1 EUR.
- Stop global : PnL broker cumule <= -15 EUR.
- Time slip : 7200 secondes depuis L1.
- L3+ : rupture M15/M5 = gestion de risque stricte, pas coupe immediate automatique.

## Fichiers publies

- `00_COMMUN/AMENDEMENT_V2446_L3_H001_2026-05-18.md`
- `01_CODEX/04_TESTS_VALIDATION/H-001_CROSS_HEDGE_US500_US100.md`
- `01_CODEX/04_TESTS_VALIDATION/FIXTURES_H001_CROSS_HEDGE.md`
- `01_CODEX/03_PATCHES_MICROTOUCHES/PLAN_PATCH_H001_CROSS_HEDGE.md`
- `04_SYNC/PAQUET_SESSION_CODEX_VERS_GPT_H001_2026-05-18.md`

## Contraintes respectees

- Aucun code modifie.
- Aucun test serveur lance.
- Aucun SSH touche.
- Aucun secret publie.

## Limite publication

Le poste local ne dispose pas de `git`, `gh`, `winget`, `choco` ou `scoop`; la publication a donc ete faite via le connecteur GitHub fichier par fichier, pas par commit local/PR.
