import sys

filename = "BOT_PIVOT_24_4_forced_audit_runner.py"

try:
    with open(filename, "r") as f:
        content = f.read()
except Exception as e:
    print(f"Erreur de lecture: {e}")
    sys.exit(1)

changes = 0

# 1. On s'assure que le module 'os' est bien disponible pour lire les variables
if "import os" not in content:
    content = "import os\n" + content

# 2. On remplace les chaînes de caractères codées en dur par os.getenv()
if '"ETHUSD"' in content or "'ETHUSD'" in content:
    content = content.replace('"ETHUSD"', 'os.getenv("ASSET", "ETHUSD")')
    content = content.replace("'ETHUSD'", "os.getenv('ASSET', 'ETHUSD')")
    changes += 1

if '"BTCUSD"' in content or "'BTCUSD'" in content:
    content = content.replace('"BTCUSD"', 'os.getenv("CONFIRM", "BTCUSD")')
    content = content.replace("'BTCUSD'", "os.getenv('CONFIRM', 'BTCUSD')")
    changes += 1

if "NO_ETH_POSITION" in content:
    content = content.replace("NO_ETH_POSITION", "NO_MAIN_ASSET_POSITION")
    changes += 1

if changes > 0:
    with open(filename, "w") as f:
        f.write(content)
    print("SUCCÈS : Les fantômes ETHUSD et BTCUSD ont été supprimés et remplacés par le paramétrage dynamique !")
else:
    print("INFO : Aucun mot codé en dur trouvé.")
