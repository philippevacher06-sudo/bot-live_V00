
import os
import importlib.util

os.environ["V244_TRADED_ASSET"] = "US500"
os.environ["V244_CONFIRM_ASSET"] = "US100"

def bars(direction, n=30, start=100.0):
    out = []
    for i in range(n):
        price = start + i if direction == "BUY" else start - i
        out.append({
            "snapshotTimeUTC": f"2026-05-17T10:{i:02d}:00",
            "closePrice": {"bid": price - 0.1, "ask": price + 0.1},
            "lastTradedVolume": 1.0,
        })
    return out

spec = importlib.util.spec_from_file_location("runner_us_shadow", "BOT_PIVOT_24_4_forced_audit_runner.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def aligned(headers, epic):
    if epic == "US500" and mod.SIGNAL_TIMEFRAME == "MINUTE_15":
        return bars("BUY", start=5000)
    if epic == "US100" and mod.SIGNAL_TIMEFRAME == "MINUTE_15":
        return bars("BUY", start=18000)
    if epic == "US100" and mod.SIGNAL_TIMEFRAME == "MINUTE_5":
        return bars("BUY", start=18000)
    return []

mod.get_price_bars = aligned
sig = mod.compute_m15_vwap_signal({})
print("CASE_US500_US100_M15_M5_ALIGNED", sig.get("bias"), sig.get("reason"), sig.get("confirm_asset"), sig.get("btc_m5_bias"))
print("PASS US500_US100_M15_M5_ALIGNED" if sig.get("bias") == "BUY" and sig.get("confirm_asset") == "US100" and sig.get("btc_m5_bias") == "BUY" else "FAIL US500_US100_M15_M5_ALIGNED")

def inverse(headers, epic):
    if epic == "US500" and mod.SIGNAL_TIMEFRAME == "MINUTE_15":
        return bars("BUY", start=5000)
    if epic == "US100" and mod.SIGNAL_TIMEFRAME == "MINUTE_15":
        return bars("BUY", start=18000)
    if epic == "US100" and mod.SIGNAL_TIMEFRAME == "MINUTE_5":
        return bars("SELL", start=18000)
    return []

mod.get_price_bars = inverse
sig2 = mod.compute_m15_vwap_signal({})
print("CASE_US100_M5_INVERSE", sig2.get("bias"), sig2.get("reason"), sig2.get("m15_bias"), sig2.get("btc_m5_bias"))
print("PASS US100_M5_INVERSE_BLOCKS" if sig2.get("bias") == "WAIT" and sig2.get("reason") == "BTC_M5_NOT_ALIGNED" else "FAIL US100_M5_INVERSE_BLOCKS")
