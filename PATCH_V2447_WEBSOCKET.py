import sys

filename = "BOT_PIVOT_03_tick_stream.py"

try:
    with open(filename, "r") as f:
        content = f.read()
except Exception as e:
    print(f"Erreur de lecture: {e}")
    sys.exit(1)

# Ciblage chirurgical de la ligne 230 avec pathlib
old_segment = '        with self.tick_file.open("a", encoding="utf-8") as f:'
new_segment = """        # Injection RAM Flash V2447 Hyper-Vitesse
        try:
            import json, time
            ram_file = f"data/ticks/live_price_{asset}.json"
            with open(ram_file, "w") as rf:
                json.dump({
                    "price": float(tick.get("bid", 0) + tick.get("ask", 0)) / 2,
                    "time": time.time(),
                    "bid": tick.get("bid"),
                    "ask": tick.get("ask")
                }, rf)
        except Exception:
            pass
        with self.tick_file.open("a", encoding="utf-8") as f:"""

if old_segment in content:
    content = content.replace(old_segment, new_segment)
    with open(filename, "w") as f:
        f.write(content)
    print("SUCCÈS : Le WebSocket a été patché ! Il écrit maintenant les prix flash en RAM.")
else:
    # Au cas où les guillemets simples/doubles diffèrent
    old_segment_alt = "        with self.tick_file.open('a', encoding='utf-8') as f:"
    if old_segment_alt in content:
        content = content.replace(old_segment_alt, new_segment)
        with open(filename, "w") as f:
            f.write(content)
        print("SUCCÈS : Le WebSocket a été patché ! (Variante guillemets simples)")
    else:
        print("ERREUR : Impossible de remplacer la ligne. Vérifie la syntaxe exacte.")
