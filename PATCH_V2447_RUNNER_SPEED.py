import sys

filename = "BOT_PIVOT_24_4_forced_audit_runner.py"

try:
    with open(filename, "r") as f:
        content = f.read()
except Exception as e:
    print(f"Erreur de lecture: {e}")
    sys.exit(1)

# Localisation de la fonction cible
target_line = "def get_price_bars(headers: Dict[str, str], epic: str) -> List[Dict[str, Any]]:"

# Code ultra-rapide à injecter au tout début de la fonction
speed_injection = """def get_price_bars(headers: Dict[str, str], epic: str) -> List[Dict[str, Any]]:
    # Court-circuit V2447 Hyper-Vitesse via RAM Flash WebSocket
    import os, json
    asset_env = os.getenv("ASSET", "")
    # Si l'epic demandé correspond à notre actif en cours, on tente de lire le flash
    if asset_env and asset_env in epic:
        ram_file = f"data/ticks/live_price_{asset_env}.json"
        if os.path.exists(ram_file):
            try:
                with open(ram_file, "r") as rf:
                    data = json.load(rf)
                # On simule une structure de "bar" minimale pour que le reste du bot ne crashe pas
                return [{"snapshotTime": "", "openPrice": {"bid": data["bid"], "ask": data["ask"]}, "closePrice": {"bid": data["bid"], "ask": data["ask"]}, "highPrice": {"bid": data["bid"], "ask": data["ask"]}, "lowPrice": {"bid": data["bid"], "ask": data["ask"]}}]
            except Exception:
                pass
"""

if target_line in content:
    content = content.replace(target_line, speed_injection)
    with open(filename, "w") as f:
        f.write(content)
    print("SUCCÈS : Le Runner principal est maintenant branché en direct sur le WebSocket Flash !")
else:
    print("ERREUR : Impossible de localiser la fonction get_price_bars.")
