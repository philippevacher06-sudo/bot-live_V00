# Decisions Validees - bot-live_V00

## 2026-05-18 - Coffre Drive officiel

Decision : `TRADING/bot-live_V00` reste le coffre Drive documentaire secondaire.

Raison : Drive aide a la consultation, mais ne remplace pas GitHub pour la memoire versionnee.

## 2026-05-18 - Depot GitHub officiel

Decision : `philippevacher06-sudo/bot-live_V00` est le depot GitHub officiel pour la memoire Markdown versionnee.

Raison : GitHub conserve les diffs, l'historique et la source commune Codex / GPT.

## 2026-05-18 - Doctrine strategique phase 02

Decision : la doctrine strategique phase 02 est validee dans :

```text
02_GPT/DOCTRINE_STRATEGIQUE_PHASE_02.md
```

## 2026-05-18 - Consolidation architecture GitHub

Decision : l'architecture active GitHub est simplifiee en dossiers courts :

```text
00_PILOTE/
00_COMMUN/
01_CODEX/
02_GPT/
03_SSH/
04_SYNC/
05_EXTENSIONS/
06_SECRETS/
99_ARCHIVES/
```

Raison : reduire les doublons, clarifier la navigation et faire de GitHub la source commune principale.

Archive : l'ancienne structure a ete conservee sous :

```text
99_ARCHIVES/2026-05-18_CONSOLIDATION_GITHUB/AVANT_CONSOLIDATION/
```

## 2026-05-18 - Suppression coupe immediate automatique L3+

Decision : supprimer la regle stricte qui imposait une coupe immediate automatique du panier a partir de L3 lorsque l'alignement M15/M5 est rompu.

Nouvelle doctrine :

- la verification directionnelle a partir de L3 reste obligatoire ;
- une rupture M15/M5 ne coupe plus automatiquement le panier pour cette seule raison ;
- elle active une gestion de risque stricte : logs, aucun renfort non valide, maximum de legs, PnL broker prioritaire, stop global et time stop/time slip ;
- cette decision permet de tester H-001 avec L4 US100 de protection.

Fichier d'amendement :

```text
00_COMMUN/AMENDEMENT_V2446_L3_H001_2026-05-18.md
```
