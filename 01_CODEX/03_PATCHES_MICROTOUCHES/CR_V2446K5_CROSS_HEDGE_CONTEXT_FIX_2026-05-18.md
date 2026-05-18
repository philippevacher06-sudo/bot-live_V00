# CR — V2446K5 CROSS HEDGE CONTEXT FIX — 2026-05-18

## Contexte

Codex étant indisponible, Philippe a autorisé GPT à assurer une correction temporaire locale, conformément à la règle exceptionnelle de substitution.

Objectif strict : corriger uniquement le blocage technique empêchant le hedge L4 de partir, sans modifier la stratégie, les règles maîtresses, les TP, les stops ni les tailles.

## Diagnostic

H002 est bien présent localement et configuré ainsi :

- actif principal : DE40 ;
- actif de confirmation : US30 ;
- actif hedge L4 : US30 ;
- taille hedge L4 : 0.05.

Le hedge L4 était bien déclenché, mais échouait avant l’envoi effectif de l’ordre. Le problème venait de la récupération fragile du contexte d’exécution dans `v2446_adverse_steps_patch.py`.

## Correction locale appliquée

Un backup local a été créé avant modification.

Marqueur ajouté dans le fichier :

```text
V2446K5_CROSS_HEDGE_HEADERS_FIX
```

Principe de la correction :

1. lire d’abord le contexte transmis au gate adverse-step ;
2. accepter les formes de contexte encapsulées ;
3. ne garder l’inspection du frame parent qu’en solution de secours ;
4. conserver les événements de suivi :
   - `RUNNER_CROSS_HEDGE_TRIGGER` ;
   - `RUNNER_CROSS_HEDGE_EXECUTED` ;
   - `RUNNER_CROSS_HEDGE_ERROR`.

## Validation locale

Compilation validée :

```bash
python3 -m py_compile v2446_adverse_steps_patch.py
echo $?
```

Résultat :

```text
0
```

Contrôle des marqueurs validé dans le fichier local.

## Ce qui n’a pas été modifié

Aucune modification sur :

- doctrine V2446 ;
- règles maîtresses ;
- TP panier ;
- stop L1 ;
- stop panier ;
- tailles ;
- logique H001/H002 ;
- audit prix/PNL ;
- code GitHub.

La correction a été appliquée uniquement dans le terminal local de Philippe. Cette fiche documente l’intervention après validation explicite `OK VALIDATION GITHUB`.

## Étape suivante

Redémarrer le bot concerné pour charger le patch local, puis surveiller les événements L4.

Résultat attendu :

```text
RUNNER_CROSS_HEDGE_TRIGGER
RUNNER_CROSS_HEDGE_EXECUTED
```

Statut : patch local appliqué et compilé. Compte-rendu publié dans GitHub.
