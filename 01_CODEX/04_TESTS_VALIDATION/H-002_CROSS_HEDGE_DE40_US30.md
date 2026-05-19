# H-002 — Cross-Hedge DE40 / US30 — Specification strategique V2446I

Statut : SPECIFICATION DOCUMENTAIRE — AUCUN PATCH CODE APPLIQUE  
Date : 2026-05-19  
Projet : BOT-PIVOT / bot-live_V00  
Famille : V2446I Cross-Hedge  
Strategie source : H-001 US500 / US100  
Strategie cible : H-002 DE40 / US30  
Publication : GPT apres validation explicite Philippe `OK VALIDATION GITHUB`

---

## 1. Objectif

H-002 transpose la structure cross-hedge H-001 sur une nouvelle paire :

- actif principal : DE40 ;
- actif hedge / secours : US30 ;
- L1 / L2 / L3 sur DE40 ;
- L4 opposee sur US30 ;
- aucune L5 ;
- aucune repetition de L4 ;
- fermeture globale de toutes les jambes ;
- TP / STOP sur `broker_upl` cumule DE40 + US30.

---

## 2. Structure du panier

| Jambe | Actif | Sens | Taille | Role |
|---|---|---|---|---|
| L1 | DE40 | sens signal principal | 0.02 | entree initiale |
| L2 | DE40 | meme sens que L1 | 0.04 | renfort adverse |
| L3 | DE40 | meme sens que L1 | 0.08 | dernier renfort principal |
| L4 | US30 | sens oppose au panier DE40 | 0.05 | hedge de secours unique |

Regle absolue :

```text
Une seule L4 US30 maximum.
Aucun renfort US30.
Aucune reouverture L4 tant que le panier complet n'est pas revenu FLAT.
```

---

## 3. Tailles explicites

H-002 n'utilise pas le modele additif :

```text
BASE_SIZE + n × SIZE_STEP
```

Car ce modele ne permet pas :

```text
0.02 / 0.04 / 0.08
```

H-002 impose donc un mode de tailles explicites :

```text
DE40_L1_SIZE = 0.02
DE40_L2_SIZE = 0.04
DE40_L3_SIZE = 0.08
US30_L4_SIZE = 0.05
```

---

## 4. Adverse step

H-002 utilise un adverse step absolu en points.

```text
DE40_ADVERSE_STEP_POINTS = 12
```

Le mode `STEP_PCT` ne doit pas etre utilise pour H-002.

Regle :

```text
L2 autorisee seulement si le prix DE40 a avance de 12 points contre L1.
L3 autorisee seulement si le prix DE40 a avance de 12 points contre L2.
L4 US30 autorisee seulement apres L3 pleine et condition hedge validee.
```

---

## 5. Take Profit progressif

Le TP est logiciel et calcule sur le `broker_upl` cumule.

Avant L4 :

| Panier | TP attendu |
|---|---|
| L1 seule | +1.00 € |
| L1 + L2 | +2.00 € |
| L1 + L2 + L3 | +4.00 € |

Apres L4 :

```text
TP panier cumule DE40 + US30 = +1.00 €
```

Important :

```text
Le TP dynamique doit etre calcule AVANT toute decision de fermeture.
Aucun TP fixe statique ne doit ecraser le TP progressif.
```

---

## 6. Stops logiciels

Les stops logiciels de perte sont releves de +50 %.

```text
STOP_L1_EUR = -4.50
BASKET_MAX_LOSS_EUR = -22.50
```

Ces stops sont logiciels et doivent etre evalues sur le `broker_upl`.

Apres L4 :

```text
STOP / TP = broker_upl cumule DE40 + US30
```

Ne sont pas modifies par cette regle :

- le time-stop ;
- le stop garanti broker ;
- `V244_STOP_DISTANCE` ;
- les airbags broker.

---

## 7. Time-stop

```text
TIME_STOP_SEC = 7200
```

Le time-stop est inconditionnel.

A 7200 secondes depuis L1 :

```text
fermeture totale du panier
```

Quel que soit le resultat :

- panier perdant ;
- panier gagnant ;
- panier neutre.

La condition `total_upl < 0` ne doit pas exister dans la logique cible.

---

## 8. Verite PnL

La source de verite est :

```text
broker_upl Capital.com
```

Pour H-002 :

```text
broker_upl cumule = broker_upl(DE40) + broker_upl(US30)
```

Le MID est interdit comme decision finale.

Le PnL local peut servir au diagnostic, mais ne doit pas fermer un panier s'il contredit le broker.

---

## 9. Fermeture globale

La fermeture globale doit fermer toutes les jambes du panier :

```text
DE40 L1
DE40 L2
DE40 L3
US30 L4
```

Aucune jambe hedge ne doit rester orpheline.

Regle :

```text
close_all H-002 = close DE40 + close US30
```

---

## 10. Verrous obligatoires

### Verrou L4 unique

Avant toute ouverture US30 :

```text
si une position US30 existe deja pour ce panier :
    refuser toute nouvelle L4
```

### Verrou aucun L5

Apres L4 :

```text
aucune nouvelle jambe autorisee
```

### Verrou FLAT

Tant que le panier n'est pas revenu totalement FLAT :

```text
aucune nouvelle sequence H-002
```

---

## 11. Parametres H-002 cible

```text
MAIN_ASSET = DE40
HEDGE_ASSET = US30

DE40_L1_SIZE = 0.02
DE40_L2_SIZE = 0.04
DE40_L3_SIZE = 0.08
US30_L4_SIZE = 0.05

DE40_ADVERSE_STEP_POINTS = 12

STOP_L1_EUR = -4.50
BASKET_MAX_LOSS_EUR = -22.50

TIME_STOP_SEC = 7200

L4_UNIQUE = true
ALLOW_L5 = false
PNL_SOURCE = BROKER_UPL_CUMULATED
```

---

## 12. Scenarios de validation H002

### H002-S01 — Ouverture L1 DE40

Signal DE40 valide.  
Aucune position existante.  
Resultat attendu :

```text
ouvrir DE40 L1 size 0.02
```

### H002-S02 — L2 apres adverse step

L1 ouverte.  
Prix contre L1 de 12 points.  
Resultat attendu :

```text
ouvrir DE40 L2 size 0.04
```

### H002-S03 — L3 apres second adverse step

L1 + L2 ouvertes.  
Prix contre L2 de 12 points.  
Resultat attendu :

```text
ouvrir DE40 L3 size 0.08
```

### H002-S04 — L4 US30 opposee

L1 + L2 + L3 ouvertes.  
Condition hedge validee.  
Resultat attendu :

```text
ouvrir une seule US30 L4 size 0.05 en sens oppose
```

### H002-S05 — Refus renfort US30

US30 L4 existe deja.  
Nouvelle boucle.  
Resultat attendu :

```text
aucun nouvel ordre US30
```

### H002-S06 — Refus L5

L1 + L2 + L3 + L4 ouvertes.  
Nouvelle condition adverse.  
Resultat attendu :

```text
aucune L5
aucun nouvel ordre
```

### H002-S07 — TP L1

L1 seule.  
broker_upl DE40 >= +1.00 €.  
Resultat attendu :

```text
fermer DE40 L1
```

### H002-S08 — TP L1+L2

L1 + L2 ouvertes.  
broker_upl DE40 cumule >= +2.00 €.  
Resultat attendu :

```text
fermer DE40 L1 + L2
```

### H002-S09 — TP L1+L2+L3

L1 + L2 + L3 ouvertes.  
broker_upl DE40 cumule >= +4.00 €.  
Resultat attendu :

```text
fermer DE40 L1 + L2 + L3
```

### H002-S10 — TP apres L4

L1 + L2 + L3 + L4 ouvertes.  
broker_upl cumule DE40 + US30 >= +1.00 €.  
Resultat attendu :

```text
fermer DE40 + US30
```

### H002-S11 — Stop L1

L1 seule.  
broker_upl DE40 <= -4.50 €.  
Resultat attendu :

```text
fermer DE40 L1
```

### H002-S12 — Stop panier global

Panier ouvert.  
broker_upl cumule DE40 + US30 <= -22.50 €.  
Resultat attendu :

```text
fermer toutes les jambes DE40 + US30
```

### H002-S13 — Time-stop panier perdant

Temps depuis L1 >= 7200 s.  
Panier perdant.  
Resultat attendu :

```text
fermer toutes les jambes DE40 + US30
```

### H002-S14 — Time-stop panier gagnant

Temps depuis L1 >= 7200 s.  
Panier gagnant.  
Resultat attendu :

```text
fermer toutes les jambes DE40 + US30
```

---

## 13. Statut

Cette specification est documentaire.

Elle ne declenche pas :

- patch code ;
- relance serveur ;
- ordre broker ;
- modification de logique runtime ;
- changement automatique des sources de verite connexes.

Les modifications des fichiers de decisions, des regles maitresses, des fixtures H-001/H-002
et du code doivent faire l'objet de validations separees.
