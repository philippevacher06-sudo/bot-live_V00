import os

file_path = "v2446_adverse_steps_patch.py"

with open(file_path, "r") as f:
    lines = f.readlines()

# 1. Sécurité : on fait une sauvegarde
os.system(f"cp {file_path} {file_path}.backup_avant_l4")

# 2. Le code à injecter
patch_code = """
    # ==========================================================
    # 🚀 PATCH PANIER CROSS-HEDGE : BIFURCATION L4 SUR US100 🚀
    # ==========================================================
    if len(ps) >= 3:
        _audit("RUNNER_CROSS_HEDGE_TRIGGER", msg="L3 plein. Blocage US500 et exécution Hedge US100.", open_positions=len(ps))
        
        hedge_asset = "US100"
        hedge_side = "SELL" if s == "BUY" else "BUY"
        hedge_size = 0.08
        
        import inspect, requests
        frame = inspect.currentframe()
        headers = frame.f_back.f_locals.get('headers') or frame.f_locals.get('kwargs', {}).get('headers') or frame.f_locals.get('headers')
        
        if headers:
            try:
                url_price = f"https://demo-api-capital.backend-capital.com/api/v1/markets/{hedge_asset}"
                res_price = requests.get(url_price, headers=headers, timeout=5).json()
                hedge_price = res_price['snapshot']['offer'] if hedge_side == "BUY" else res_price['snapshot']['bid']
                
                sl = hedge_price - 150 if hedge_side == "BUY" else hedge_price + 150
                
                url_pos = "https://demo-api-capital.backend-capital.com/api/v1/positions"
                payload = {
                    "epic": hedge_asset,
                    "direction": hedge_side,
                    "size": hedge_size,
                    "orderType": "MARKET",
                    "guaranteedStop": True,
                    "stopLevel": round(sl, 2),
                    "forceOpen": True
                }
                res = requests.post(url_pos, json=payload, headers=headers, timeout=5)
                _audit("RUNNER_CROSS_HEDGE_EXECUTED", payload=payload, status=res.status_code, response=res.text)
            except Exception as e:
                _audit("RUNNER_CROSS_HEDGE_ERROR", error=str(e))
        else:
            _audit("RUNNER_CROSS_HEDGE_ERROR", error="Headers API introuvables.")
        
        return False, {"reason": "HEDGE_L4_EXECUTED_NO_MORE_US500", "current_level": c, "target_level": target}
    # ==========================================================
"""

# 3. On cherche la bonne ligne et on greffe le code
new_lines = []
patched = False
for line in lines:
    if 'RUNNER_ADVERSE_STEP_OPEN_ALLOWED' in line and not patched:
        new_lines.append(patch_code)
        patched = True
    new_lines.append(line)

# 4. On sauvegarde
if patched:
    with open(file_path, "w") as f:
        f.writelines(new_lines)
    print("\n✅ SUCCÈS TOTAL : Le patch L4 (Hedge US100) a été greffé dans ton bot !")
    print("Ton fichier d'origine a été sauvegardé sous le nom : v2446_adverse_steps_patch.py.backup_avant_l4\n")
else:
    print("\n❌ ERREUR : Le script n'a pas trouvé l'endroit où injecter le code.\n")
