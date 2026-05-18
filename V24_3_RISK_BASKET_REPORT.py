#!/usr/bin/env python3
import os

import BOT_PIVOT_00_config as CFG
import BOT_PIVOT_00B_pnl_eur as PNL


BOLLINGER_STEPS = {
    "US500": 5.0,
    "US100": 15.0,
    "US30": 25.0,
    "DE40": 15.0,
    "FR40": 7.0,
    "UK100": 10.0,
    "J225": 50.0,
    "EURUSD": 0.00030,
    "GBPUSD": 0.00035,
    "USDJPY": 0.050,
    "EURJPY": 0.060,
    "GOLD": 5.0,
    "SILVER": 0.5,
    "OIL_CRUDE": 0.25,
    "BTCUSD": 50.0,
    "ETHUSD": 5.0,
}


def env_float(name, default):
    try:
        return float(str(os.getenv(name, default)).replace(",", "."))
    except Exception:
        return float(default)


def base_size(asset):
    if hasattr(CFG, "BASE_SIZE_BY_ASSET"):
        return float(CFG.BASE_SIZE_BY_ASSET.get(asset, 0.0))
    if hasattr(CFG, "BASE_SIZES"):
        return float(CFG.BASE_SIZES.get(asset, 0.0))
    return 0.0


def risk_for(asset):
    cursor = env_float("BOLLINGER_CURSOR", 1.0)
    step = float(BOLLINGER_STEPS.get(asset, 0.0)) * cursor
    size1 = base_size(asset)
    sizes = [size1, size1 * 2.0, size1 * 3.0]
    stop_mult = env_float("STOP_AIRBAG_STEP_MULT", 8.0)
    extra = max(step * stop_mult, 1e-12)

    # Global stop is beyond L3. Distances from L1/L2/L3 to that stop.
    distances = [2.0 * step + extra, step + extra, extra]
    rate = PNL.raw_to_eur_rate_for_asset(asset)
    risks = [abs(distances[i] * sizes[i] * rate) for i in range(3)]

    return {
        "asset": asset,
        "base_size": size1,
        "l1": sizes[0],
        "l2": sizes[1],
        "l3": sizes[2],
        "step": step,
        "extra": extra,
        "d1": distances[0],
        "d2": distances[1],
        "d3": distances[2],
        "r1": risks[0],
        "r12": risks[0] + risks[1],
        "r123": sum(risks),
        "ccy": PNL.asset_currency(asset),
        "rate": rate,
    }


def main():
    print("V24.3 - RISK BASKET REPORT")
    print("Hypothese: L1/L2/L3 remplis puis stop airbag touche.")
    print()
    print(
        f"{'ACTIF':10s} {'L1':>10s} {'L2':>10s} {'L3':>10s} "
        f"{'STEP':>12s} {'STOP_L1':>12s} {'RISK_L1':>12s} "
        f"{'RISK_1+2':>12s} {'RISK_1+2+3':>14s}"
    )
    print("-" * 120)

    total_worst = 0.0
    for asset in CFG.ASSETS:
        row = risk_for(asset)
        total_worst += row["r123"]
        print(
            f"{asset:10s} "
            f"{row['l1']:10.6f} {row['l2']:10.6f} {row['l3']:10.6f} "
            f"{row['step']:12.6f} {row['d1']:12.6f} "
            f"{row['r1']:12.4f} {row['r12']:12.4f} {row['r123']:14.4f}"
        )

    print("-" * 120)
    print(f"Somme worst-case theorique si tous les paniers L1+L2+L3 stoppent: {total_worst:.2f} EUR")
    print("Note: estimation theorique, hors slippage/gap et hors exigences exactes de marge broker.")


if __name__ == "__main__":
    main()
