# Regles Completes V2446I

1. Le programme ne trade jamais un actif seul.
2. Chaque actif a un double maitre obligatoire.
3. Le double maitre donne le sens.
4. Le M15 du double donne la direction principale.
5. Le M5 du double confirme l'entree.
6. Le M1 est supprime de cette strategie.
7. Une entree est autorisee seulement si M15 et M5 du double sont alignes.
8. Si M15 et M5 ne sont pas alignes, le bot ne rentre pas.
9. Une fois un panier ouvert, le sens du panier est verrouille.
10. Un panier BUY interdit toute entree SELL.
11. Un panier SELL interdit toute entree BUY.
12. Un signal inverse devient une alerte de risque, pas une entree opposee.
13. Le retournement direct est interdit.
14. La premiere position L1 doit avoir une marge cible maximum de 10 EUR.
15. Si une seule position est ouverte et atteint -3 EUR, le bot ferme tout.
16. Le panier peut avoir 5 positions maximum.
17. Si le panier atteint -15 EUR de perte cumulee, le bot ferme tout.
18. Si le panier atteint +5 EUR de gain cumule, le bot ferme tout.
19. Le step entre deux positions est dynamique.
20. Le step vaut 0.07 % du prix courant.
21. Formule: dynamic_step = current_price * 0.0007.
22. Exemple prix 2000: step = 1.40.
23. Exemple prix 6000: step = 4.20.
24. Exemple prix 8000: step = 5.60.
25. Un renfort est autorise seulement si le palier adverse est atteint.
26. Pour un panier SELL, le palier adverse est au-dessus du dernier niveau.
27. Pour un panier BUY, le palier adverse est en-dessous du dernier niveau.
28. Le double M15 et M5 doit rester dans le sens du panier pour renforcer.
29. Si le double devient inverse, le bot ne renforce pas.
30. Si le double devient inverse, le panier passe en defense.
31. Si le nombre de positions maximum est atteint, aucun renfort supplementaire.
32. Si le panier est trop vieux et perdant, TIME_STOP ferme le panier.
33. Apres fermeture, le broker doit confirmer 0 position sur l'actif.
34. Le reset exige 2 lectures broker consecutives a 0 position.
35. Si une position reapparait entre les 2 lectures, le reset est annule.
36. Apres reset, un cooldown bloque la reouverture immediate.
37. Les logs doivent donner la raison de chaque entree, blocage, renfort, fermeture et reset.
38. Les paires maitres sont:
39. ETHUSD -> BTCUSD.
40. US500 -> US100.
41. FR40 -> DE40.
42. EURUSD -> GBPUSD.
43. USDJPY -> EURJPY.
44. GOLD -> SILVER.
45. OIL_CRUDE -> OIL_BRENT/BRENT.
46. J225 -> USDJPY.
47. Au debut, seuls ETHUSD/BTCUSD et US500/US100 doivent etre codes live.
48. Les autres paires sont preparees puis validees separement.
49. La strategie cherche peu de trades, mais des paniers bornes.
50. La perte maximale doit etre bornee avant toute optimisation de signal.
