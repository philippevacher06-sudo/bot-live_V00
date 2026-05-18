filename = "BOT_PIVOT_03_tick_stream.py"

with open(filename, "r") as f:
    content = f.read()

# On remplace le bloc problématique par une détection propre utilisant le os global
old_block = """# Alignement URL V2447
    import os
    # Si CAPITAL_URL est dans le .env, on l'utilise, sinon on cherche dans les variables système
    base_url = os.getenv("CAPITAL_URL", "").rstrip("/")
    if not base_url:
        base_url = "https://api-capital.backend.capital.com" if "demo" not in os.getenv("CAPITAL_LOGIN", "").lower() and "demo" not in os.getenv("CAPITAL_IDENTIFIER", "").lower() else "https://demo-api-capital.backend.capital.com" """

# Version ultra-pro sans ré-importation de 'os' à l'intérieur
new_block = """# Alignement URL V2447 net
    base_url = os.environ.get("CAPITAL_URL", "").rstrip("/")
    if not base_url:
        login_check = (os.environ.get("CAPITAL_LOGIN") or os.environ.get("CAPITAL_IDENTIFIER") or "").lower()
        base_url = "https://demo-api-capital.backend.capital.com" if "demo" in login_check else "https://api-capital.backend.capital.com" """

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filename, "w") as f:
        f.write(content)
    print("SUCCÈS : Le conflit avec la variable 'os' a été supprimé !")
else:
    # Au cas où les espaces diffèrent, on fait un remplacement plus large ou préventif
    print("INFO : Bloc introuvable au format exact, application du correctif global...")
    # Sécurité au cas où : on s'assure juste que 'import os' est bien au tout début du fichier global
    if "import os" not in content:
        content = "import os\n" + content
        with open(filename, "w") as f:
            f.write(content)
