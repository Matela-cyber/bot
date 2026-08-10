import pandas as pd
import numpy as np

from structure.smart_money import SmartMoneyConcepts


def make_candles(values):
    # values: list of (open, high, low, close, volume)
    idx = pd.date_range("2026-01-01", periods=len(values), freq="15min")
    df = pd.DataFrame(values, columns=["open", "high", "low", "close", "volume"], index=idx)
    return df


def test_bos_detection_bull():
    # Create frame where last close breaks above prev swing high
    values = [
        (1.0, 1.01, 0.99, 1.005, 100),
        (1.005, 1.02, 1.00, 1.015, 100),
        (1.015, 1.03, 1.01, 1.025, 100),
    ]
    frame = make_candles(values)
    swings = {"highs": [{"price": 1.015, "index": 1}, {"price": 1.02, "index": 2}], "lows": [{"price": 0.99, "index": 0}, {"price": 1.0, "index": 1}]}
    smc = SmartMoneyConcepts()
    res = smc.detect_bos(frame, swings)
    assert isinstance(res, dict)
    assert res["status"] == "bull"


def test_choch_detection_bull():
    # Construct swings with lower lows then a breakout
    values = [
        (1.0, 1.01, 0.99, 0.995, 100),
        (0.995, 1.00, 0.98, 0.985, 120),
        (0.985, 0.995, 0.975, 1.01, 200),
    ]
    frame = make_candles(values)
    swings = {
        "highs": [{"price": 1.00, "index": 0}, {"price": 0.995, "index": 1}, {"price": 0.995, "index": 2}],
        "lows": [{"price": 0.99, "index": 0}, {"price": 0.98, "index": 1}, {"price": 0.975, "index": 2}],
    }
    smc = SmartMoneyConcepts()
    res = smc.detect_choch(frame, swings)
    assert res["status"] == "bull"


def test_order_block_detection():
    # Create data with a clear impulse candle
    vals = []
    for i in range(30):
        vals.append((1.0, 1.001, 0.999, 1.0005, 100))
    # Insert impulse
    vals[-5] = (1.0005, 1.0205, 1.0000, 1.0190, 500)
    frame = make_candles(vals)
    smc = SmartMoneyConcepts()
    res = smc.detect_order_block(frame, {})
    assert res["status"] in ("bull", "bear")
    assert res["zone_high"] is not None


def test_fvg_detection_and_fill():
    # Build three candles with bullish gap: c0 high < c2 low
    values = [
        (1.0, 1.001, 0.999, 1.0005, 100),
        (1.0005, 1.002, 1.000, 1.0015, 100),
        (1.002, 1.010, 1.003, 1.009, 100),
    ]
    frame = make_candles(values)
    smc = SmartMoneyConcepts()
    res = smc.detect_fvg(frame)
    assert res["status"] == "bull"
    assert res["size_pips"] >= 0.0002


def test_liquidity_detection():
    values = [
        (1.0, 1.01, 0.99, 1.005, 100),
        (1.005, 1.02, 1.00, 1.015, 100),
        (1.015, 1.03, 1.01, 1.025, 100),
    ]
    frame = make_candles(values)
    swings = {"highs": [{"price": 1.03, "index": 2}], "lows": [{"price": 0.99, "index": 0}]}
    smc = SmartMoneyConcepts()
    res = smc.detect_liquidity(frame, swings)
    assert res["nearest_high"] == 1.03
    assert res["nearest_low"] == 0.99


def test_analyze_combination_and_edgecases():
    smc = SmartMoneyConcepts()
    empty = smc.analyze(pd.DataFrame(), {})
    assert empty["score"] == 0.5 or empty["score"] >= 0.0
