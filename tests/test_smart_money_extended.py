import pandas as pd

from config import settings
from smc.structure import StructureDetector


def make_candles(values, freq="15min"):
    idx = pd.date_range("2026-01-01", periods=len(values), freq=freq)
    df = pd.DataFrame(values, columns=["open", "high", "low", "close", "volume"], index=idx)
    return df


def test_multi_candle_order_block_detection():
    # build series with 3 small candles, then an impulse
    vals = []
    for _ in range(10):
        vals.append((1.0, 1.001, 0.999, 1.0005, 100))
    # three pre-OB candles
    vals.extend([
        (1.001, 1.002, 1.000, 1.0015, 120),
        (1.0015, 1.003, 1.001, 1.0025, 120),
        (1.0025, 1.004, 1.002, 1.0035, 120),
    ])
    # impulse
    vals.append((1.0035, 1.0300, 1.0030, 1.0280, 800))
    frame = make_candles(vals)
    smc = SmartMoneyConcepts()
    res = smc.detect_order_block(frame, {})
    assert res["candles"] >= 2
    assert res["zone_high"] >= res["zone_low"]


def test_fvg_cluster_detection_and_nearest():
    # Create two gaps in series
    vals = [
        (1.0000, 1.0010, 0.9990, 1.0005, 100),
        (1.0005, 1.0020, 1.0002, 1.0015, 100),
        (1.0035, 1.0060, 1.0030, 1.0050, 100),
        (1.0050, 1.0060, 1.0040, 1.0045, 100),
        (1.0080, 1.0100, 1.0075, 1.0090, 100),
    ]
    frame = make_candles(vals)
    smc = SmartMoneyConcepts()
    res = smc.detect_fvg(frame)
    assert "all_gaps" in res
    assert isinstance(res["all_gaps"], list)
    assert len(res["all_gaps"]) >= 1


def test_timeframe_scaling_changes_thresholds():
    # build minimal 15min frame and 240min frame with same candles
    vals = [
        (1.0, 1.001, 0.999, 1.0005, 100),
        (1.0005, 1.002, 1.000, 1.0015, 100),
        (1.002, 1.010, 1.003, 1.009, 100),
    ]
    frame_15 = make_candles(vals, freq="15min")
    frame_240 = make_candles(vals, freq="4h")
    smc = SmartMoneyConcepts()
    res15 = smc.detect_fvg(frame_15)
    res240 = smc.detect_fvg(frame_240)
    # With larger timeframe scaling, threshold for FVG increases: so fewer gaps expected
    assert (len(res15.get("all_gaps", [])) >= len(res240.get("all_gaps", [])))
