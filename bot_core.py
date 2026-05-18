import json
import sys
import logging

# Config des logs : Format compact sur une seule ligne
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("V2447_Kernel")

class BotKernel:
    def __init__(self, asset):
        self.asset = asset
        self.config = self._load_config()
        self.protected_deals = ["00601567-0055-311e-0000-000084ad1031"] # Ton deal GOLD historique

    def _load_config(self):
        """Charge la matrice JSON globale"""
        try:
            with open("config_assets.json", "r") as f:
                matrix = json.load(f)
            asset_data = matrix.get(self.asset)
            if not asset_data:
                logger.error(f"Asset {self.asset} absent de config_assets.json")
                sys.exit(1)
            return asset_data
        except Exception as e:
            logger.error(f"Erreur chargement JSON: {e}")
            sys.exit(1)

    def calculate_dynamic_step(self, current_level):
        """Formule mathématique unique à 0.07%"""
        return abs(current_level) * 0.0007

    def universal_cascade_filter(self, broker_positions):
        """Filtre chirurgical en RAM"""
        clean_positions = [p for p in broker_positions if p.get('dealId') not in self.protected_deals]
        local_basket = [p for p in clean_positions if p.get('symbol') == self.asset]
        return {"count": len(local_basket), "basket": local_basket}

    def execute_logic(self, current_price, raw_broker_positions):
        """Boucle d'exécution ultra-rapide"""
        step = self.calculate_dynamic_step(current_price)
        filtered = self.universal_cascade_filter(raw_broker_positions)
        logger.info(
            f"RUNNER_BASKET | Asset: {self.asset} | Price: {current_price:.4f} "
            f"| Step(0.07%): {step:.4f} | Active_Legs: {filtered['count']}"
        )
        return filtered

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python bot_core.py [ASSET] [FAKED_PRICE]")
        sys.exit(1)
        
    input_asset = sys.argv[1]
    faked_market_price = float(sys.argv[2])
    
    # Simulation de positions chez le broker pour le test
    mock_broker_positions = [
        {"dealId": "00601567-0055-311e-0000-000084ad1031", "symbol": "GOLD", "size": 0.81},
        {"dealId": "BOT_NEW_GOLD_DEAL", "symbol": "GOLD", "size": 0.01},
        {"dealId": "ETH_POSITION_1", "symbol": "ETHUSD", "size": 0.1},
        {"dealId": "US500_POSITION_1", "symbol": "US500", "size": 0.06},
    ]
    
    bot = BotKernel(asset=input_asset)
    bot.execute_logic(current_price=faked_market_price, raw_broker_positions=mock_broker_positions)
