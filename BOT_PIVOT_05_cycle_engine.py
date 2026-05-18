import time
import logging
from typing import Dict, Any, List

log = logging.getLogger("CYCLE_ENGINE")

# --- PARAMÈTRES DU PANIER CROSS-HEDGE ---
# On fixe les tailles et les objectifs selon tes règles.
# MAIN_ASSET est par défaut l'US500, HEDGE_ASSET est l'US100.
BASKET_CONFIG = {
    "MAIN_ASSET": "US500",
    "HEDGE_ASSET": "US100",
    "GRID_STEP_POINTS": 3.0,
    "LEVELS": {
        1: {"size": 0.07, "target_eur": 1.00, "is_hedge": False},
        2: {"size": 0.14, "target_eur": 2.00, "is_hedge": False},
        3: {"size": 0.21, "target_eur": 4.00, "is_hedge": False},
        4: {"size": 0.08, "target_eur": 1.00, "is_hedge": True} # L4 : Le Hedge de survie
    }
}

class CycleEngine:
    def __init__(self, broker_client, state_manager):
        self.broker = broker_client
        self.state = state_manager
        
    def _calculate_distance(self, entry_price: float, current_price: float, direction: str) -> float:
        """Calcule la distance en points CONTRE notre position."""
        if direction == "SELL":
            return current_price - entry_price # Si SELL, le prix monte = perte
        elif direction == "BUY":
            return entry_price - current_price # Si BUY, le prix baisse = perte
        return 0.0

    def evaluate_basket(self, open_positions: List[Dict], current_market_prices: Dict[str, Dict[str, float]], signal_direction: str):
        """
        Le coeur du réacteur : évalue l'état actuel du panier et prend la décision
        d'ouvrir un nouveau niveau ou de tout fermer.
        """
        num_positions = len(open_positions)
        
        # --- SCENARIO 1 : PANIER VIDE ---
        if num_positions == 0:
            if signal_direction:
                log.info(f"🛒 Début d'un nouveau panier. Ouverture L1 ({BASKET_CONFIG['MAIN_ASSET']}) à la {signal_direction}.")
                self._execute_level(1, signal_direction, current_market_prices)
            return

        # --- SCENARIO 2 : PANIER EN COURS ---
        global_pnl = sum(float(p.get("profitAndLoss", 0)) for p in open_positions)
        
        # Sécurité : Si on a plus de 4 positions, on ne fait rien (pas de L5)
        if num_positions > 4:
            log.warning("⚠️ Panier plein (>4 positions). En attente de résolution.")
            current_target = BASKET_CONFIG["LEVELS"][4]["target_eur"] # On vise la sortie de survie
        else:
            current_target = BASKET_CONFIG["LEVELS"][num_positions]["target_eur"]
            
        log.info(f"📊 État Panier: {num_positions} Leg(s) | PnL Global = {global_pnl:.2f}€ | Objectif actuel = +{current_target}€")

        # -- VÉRIFICATION DU TAKE PROFIT GLOBAL --
        if global_pnl >= current_target:
            log.info(f"🎯 OBJECTIF ATTEINT ({global_pnl:.2f}€ >= {current_target}€). Fermeture de tout le panier.")
            self._close_all_positions(open_positions)
            return

        # -- VÉRIFICATION DU DÉCLENCHEMENT DU NIVEAU SUIVANT --
        if global_pnl < 0 and num_positions < 4:
            
            # On identifie la dernière position ouverte (L_actuel)
            # Hypothèse : la liste open_positions est triée par ordre chronologique
            latest_pos = open_positions[-1] 
            entry_price = float(latest_pos.get("level", 0))
            pos_direction = latest_pos.get("direction")
            epic = latest_pos.get("epic")
            
            # On récupère le prix actuel pour l'actif de la dernière position
            if epic in current_market_prices:
                 # Simplification: on prend le milieu (bid/offer) pour l'évaluation de distance
                current_price = (current_market_prices[epic]["bid"] + current_market_prices[epic]["offer"]) / 2.0 
            else:
                 log.warning(f"⚠️ Prix introuvable pour {epic}. Impossible d'évaluer la distance.")
                 return

            distance = self._calculate_distance(entry_price, current_price, pos_direction)
            
            # Si le marché est allé contre nous d'au moins GRID_STEP_POINTS
            if distance >= BASKET_CONFIG["GRID_STEP_POINTS"]:
                next_level = num_positions + 1
                log.warning(f"⚠️ Marché contre nous de {distance:.1f} pts (Seuil: {BASKET_CONFIG['GRID_STEP_POINTS']}).")
                
                # Le panier US500 d'origine est toujours dans le sens de L1
                # On récupère le sens de la toute première position
                first_pos_direction = open_positions[0].get("direction") 
                
                self._execute_level(next_level, first_pos_direction, current_market_prices)

    def _execute_level(self, level: int, base_direction: str, current_prices: Dict[str, Dict[str, float]]):
        """Prépare et envoie l'ordre au broker pour un niveau spécifique."""
        config = BASKET_CONFIG["LEVELS"].get(level)
        if not config:
            return
            
        is_hedge = config["is_hedge"]
        target_asset = BASKET_CONFIG["HEDGE_ASSET"] if is_hedge else BASKET_CONFIG["MAIN_ASSET"]
        
        # Si c'est le hedge (L4), la direction est l'inverse de la direction de base
        if is_hedge:
            trade_direction = "BUY" if base_direction == "SELL" else "SELL"
            log.info(f"🚨 DÉCLENCHEMENT HEDGE DE SURVIE (L{level}) : {target_asset} en {trade_direction}")
        else:
            trade_direction = base_direction
            log.info(f"📈 Déclenchement Renfort (L{level}) : {target_asset} en {trade_direction}")
            
        size = config["size"]
        
        # Appel à la fonction d'exécution de ton broker (à adapter selon ta classe exacte)
        # On suppose que self.broker.execute_market_order gère les prix, SL de sécurité, etc.
        try:
             # Exemple générique d'appel
             self.broker.execute_market_order(epic=target_asset, direction=trade_direction, size=size)
             log.info(f"✅ Ordre L{level} envoyé avec succès.")
        except Exception as e:
             log.error(f"❌ Échec de l'ouverture du L{level} : {e}")

    def _close_all_positions(self, open_positions: List[Dict]):
        """Boucle de fermeture sécurisée pour vider le panier."""
        for pos in open_positions:
            deal_id = pos.get("dealId")
            epic = pos.get("epic")
            try:
                # Appel générique, à adapter selon ta méthode exacte
                self.broker.close_position(deal_id) 
                log.info(f"   ✔️ Position fermée : {epic} (ID: {deal_id})")
            except Exception as e:
                log.error(f"   ❌ Échec fermeture de {epic} ({deal_id}) : {e}")
