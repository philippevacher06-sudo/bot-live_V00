import sys

filename = "BOT_PIVOT_24_4_forced_audit_runner.py"

print(f"Ouverture de {filename}...")
try:
    with open(filename, "r") as f:
        content = f.read()
except Exception as e:
    print(f"Erreur de lecture: {e}")
    sys.exit(1)

# Le grand nettoyage sémantique (Priorité 1)
changes = 0

# 1. Variables de comptage
if "open_eth_count" in content:
    content = content.replace("open_eth_count", "open_positions_count")
    changes += 1

# 2. Logs de décision
if "RUNNER_ETH_BASKET_DECISION" in content:
    content = content.replace("RUNNER_ETH_BASKET_DECISION", "RUNNER_BASKET_DECISION")
    changes += 1

# 3. Nettoyage des commentaires et balises ETH_BTC (comme vu dans le grep)
if "V2446I_ETH_BTC_CASCADE_RULES" in content:
    content = content.replace("V2446I_ETH_BTC_CASCADE_RULES", "V2446I_CASCADE_RULES")
    changes += 1

if "RUNNER_ETH_BASKET" in content:
    content = content.replace("RUNNER_ETH_BASKET", "RUNNER_BASKET")
    changes += 1

if changes > 0:
    with open(filename, "w") as f:
        f.write(content)
    print(f"SUCCÈS : Patch appliqué ! Le fichier est maintenant agnostique (ETH a été nettoyé).")
else:
    print("INFO : Rien à remplacer, le fichier est déjà propre ou les mots n'ont pas été trouvés.")
