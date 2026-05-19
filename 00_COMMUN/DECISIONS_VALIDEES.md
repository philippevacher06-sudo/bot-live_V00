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

## 2026-05-18 - Classement GitHub V2446 H-001

Decision : le modele canonique actuel V2446 est `run_V2446_ADVERSE_STEPS_US500_US100.sh`.

Paire canonique : `US500 / US100 - H-001`.

Classement :

```text
ACTIF CANONIQUE
- run_V2446_ADVERSE_STEPS_US500_US100.sh

ACTIF HISTORIQUE NON CANONIQUE
- run_V2446_ADVERSE_STEPS_ETH_BTC.sh

ACTIFS SECONDAIRES A HARMONISER
- run_V2446_ADVERSE_STEPS_EURUSD_GBPUSD.sh
- run_V2446_ADVERSE_STEPS_FR40_DE40.sh
- run_V2446_ADVERSE_STEPS_GOLD_SILVER.sh
- run_V2446_ADVERSE_STEPS_J225_USDJPY.sh
- run_V2446_ADVERSE_STEPS_OIL_CRUDE_OIL_BRENT.sh
- run_V2446_ADVERSE_STEPS_USDJPY_EURJPY.sh

NOYAU PYTHON V2446
- BOT_PIVOT_24_4_forced_audit_runner.py
- BOT_PIVOT_06G2_execution_secure.py
- v2446_adverse_steps_patch.py
- BOT_PIVOT_00D_pair_director_authority.py
- BOT_PIVOT_00B_pnl_eur.py
- BOT_PIVOT_00_config.py

RUNTIME LOCAL A DESINDEXER PLUS TARD, SANS SUPPRESSION SAUVAGE
- data/
- logs/
- backup/
- backups/
```

Regle : aucun nettoyage, deplacement ou suppression Git sans validation explicite separee.

## 2026-05-19 - Discipline urgente des reponses GPT en substitution

Decision : lorsque GPT remplace temporairement Codex, ses reponses dans le chat
doivent tenir en 10 lignes maximum, sauf demande explicite de document complet.

Architecture imposee : statut, preuve ou fichier source, analyse courte,
decision/hypothese/question ouverte, action Codex requise, risque ou prochaine
verification.

Raison : GPT doit rester rapide, precis et utile en mode substitution, sans
alourdir le chat ni pretendre effectuer des actions techniques.

Fichier de message urgent :

```text
04_SYNC/MESSAGE_URGENT_GPT_SUBSTITUTION_RAPIDE.md
```

## 2026-05-19 - Declencheur utilisateur Codex dans GPT

Decision : dans un chat GPT lie au projet, des que l'utilisateur ecrit le mot
`Codex`, GPT doit activer le mode substitution Codex.

Effet attendu : reponse courte, precise, operationnelle, raisonnee comme Codex,
mais limitee au documentaire et strategique tant qu'une validation technique
Codex n'a pas eu lieu.

Limite : ce declencheur ne donne pas a GPT le droit de pretendre avoir execute
du code, lance SSH, verifie broker, applique un patch, lance des tests serveur
ou envoye/ferme des ordres.

## 2026-05-19 - Mode technique GPT preparatoire, sans terminal live

Decision : le mot `Codex` autorise GPT a devenir technique dans la preparation :
diagnostic de code, proposition de patch, extrait de code, plan de test et
memoire GitHub.

Limite verrouillee : GPT ne peut pas utiliser le terminal live, SSH, tmux, le
broker, les scripts actifs, appliquer un patch ou presenter du code comme
operationnel valide sans validation Codex.

Mention obligatoire pour toute proposition technique GPT :

```text
PROPOSITION GPT - NON EXECUTEE - VALIDATION CODEX REQUISE
```

Fichier de regle :

```text
00_COMMUN/REGLE_MODE_TECHNIQUE_GPT_PREPARATOIRE.md
```
