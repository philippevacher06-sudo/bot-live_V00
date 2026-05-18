BOT-PIVOT V24.2 -- BOLLINGER / MARGIN / LEVEL GUARD

Base:
- Built from V24.1 source archive BOT_PIVOT_V24_1_SOURCE_BEFORE_V24_2_20260513_194416.tar.gz.
- Keeps V24_BROKER_UPL_TP_PATCH_V1: basket TP is still decided only from Capital.com position.upl.

Main changes:
1. BOLLINGER_SCALP_CLAMP is neutralized. Raw Bollinger L1 is no longer moved toward current price.
2. If raw Bollinger L1 is too far, the basket is rejected with BASKET_REJECT_BOLLINGER_TOO_FAR.
3. Full basket levels are computed once and validated before sending the first broker LIMIT.
4. Anti-marketable LIMIT guard:
   - BUY LIMIT must be below the current low side by a safety distance.
   - SELL LIMIT must be above the current high side by a safety distance.
5. Anti-collapsed levels guard:
   - BUY: L1 > L2 > L3 with minimum step spacing.
   - SELL: L1 < L2 < L3 with minimum step spacing.
6. PRICE_AUDIT logs stream price, snapshot price, Bollinger bands, raw/final L1, L1/L2/L3 and distance to market.
7. Global margin guard:
   - MAX_MARGIN_CFD_EUR default 3000.
   - MIN_AVAILABLE_TO_TRADE_EUR default 500.
   - Blocks new baskets with BASKET_REJECT_MARGIN_GUARD.
   - Cancels pending limits under pressure with MARGIN_GUARD_CANCEL_PENDING.
8. OIL_CRUDE base size reduced from 12 to 4.
9. Ghost pending without workingDealId can be marked locally when no broker working order is found.
10. Cycle engine has an early Bollinger-width gate when signal data already contains M5 BB fields.

Runtime env knobs:
- V242_REJECT_BOLLINGER_TOO_FAR=1
- MAX_MARGIN_CFD_EUR=3000
- MIN_AVAILABLE_TO_TRADE_EUR=500
- V242_LEVEL_MIN_STEP_RATIO=0.95
- V242_MARKETABLE_MIN_DISTANCE=<global override>
- V242_MARKETABLE_MIN_DISTANCE_<ASSET>=<asset override>
- V242_LEVEL_MIN_STEP=<global override>
- V242_LEVEL_MIN_STEP_<ASSET>=<asset override>

Install on server:
1. Copy/extract this folder on the Linux server.
2. Run:
   ./install_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.sh
3. Before relaunch, verify manually in Capital.com demo:
   positions ouvertes = 0
   ordres en attente = 0
4. Run:
   cd /home/philippe_vacher06/bot-pivot/live
   ./verify_V24_2_BOLLINGER_MARGIN_LEVEL_GUARD.sh
   ./relance_V24_2_DEMO.sh

Expected key logs:
- PRICE_AUDIT
- BASKET_REJECT_BOLLINGER_TOO_FAR
- BASKET_REJECT_MARKETABLE_LIMIT
- BASKET_REJECT_LEVELS_COLLAPSED
- BASKET_REJECT_MARGIN_GUARD
- MARGIN_GUARD_CANCEL_PENDING
- BASKET_TP_OK ... source=BROKER_POSITION_UPL
- BASKET_TP_BLOCKED_BROKER_UPL
- BASKET_TP_BLOCKED_NO_BROKER_UPL
