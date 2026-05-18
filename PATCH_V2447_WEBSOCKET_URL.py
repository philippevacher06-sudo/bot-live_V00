import sys

filename = "BOT_PIVOT_03_tick_stream.py"

try:
    with open(filename, "r") as f:
        content = f.read()
except Exception as e:
    print(f"Erreur de lecture: {e}")
    sys.exit(1)

# On remplace la ligne de l'URL pour qu'elle lise la variable d'environnement ou bascule intelligemment
old_url = 'base_url = CFG.BASE_URL.rstrip("/")'
new_url = """# Alignement URL V2447
    import os
    # Si CAPITAL_URL est dans le .env, on l'utilise, sinon on cherche dans les variables système
    base_url = os.getenv("CAPITAL_URL", "").rstrip("/")
    if not base_url:
        base_url = "https://api-capital.backend.capital.com" if "demo" not in os.getenv("CAPITAL_LOGIN", "").lower() and "demo" not in os.getenv("CAPITAL_IDENTIFIER", "").lower() else "https://demo-api-capital.backend.capital.com"
"""

if old_url in content:
    content = content.replace(old_url, new_url)
    with open(filename, "w") as f:
        f.write(content)
    print("SUCCÈS : L'URL du WebSocket a été dynamisée par rapport à tes identifiants !")
else:
    print("INFO : Déjà patché ou structure différente.")
