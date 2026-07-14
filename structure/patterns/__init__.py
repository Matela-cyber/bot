from __future__ import annotations

from typing import Any

import pandas as pd

from structure.candlestick_validator import analyze_candlestick_confirmation
from structure.pattern_validator import PatternValidator
from structure.xgboost_validator import XGBoostValidator
from structure.patterns.ascending_channel import AscendingChannelPattern
from structure.patterns.bear_flat import BearFlatPattern
from structure.patterns.bear_flag import BearFlagPattern
from structure.patterns.bear_triangle import BearTrianglePattern
from structure.patterns.bull_flat import BullFlatPattern
from structure.patterns.bull_flag import BullFlagPattern
from structure.patterns.bull_triangle import BullTrianglePattern
from structure.patterns.descending_channel import DescendingChannelPattern
from structure.patterns.double_bottom import DoubleBottomPattern
from structure.patterns.double_top import DoubleTopPattern
from structure.patterns.expanding_triangle import ExpandingTrianglePattern
from structure.patterns.falling_wedge import FallingWedgePattern
from structure.patterns.head_and_shoulders import HeadAndShouldersPattern
from structure.patterns.inverse_head_and_shoulders import InverseHeadAndShouldersPattern
from structure.patterns.rising_wedge import RisingWedgePattern


def _recent_trend(frame: pd.DataFrame, window: int = 15) -> float:
    if len(frame) < window:
        return 0.0
    return float(frame["close"].iloc[-1] - frame["close"].iloc[-window])


def _trend_strength(frame: pd.DataFrame, windows: tuple[int, ...] = (20, 60)) -> float:
    values: list[float] = []
    for window in windows:
        if len(frame) >= window:
            values.append(float(frame["close"].iloc[-1] - frame["close"].iloc[-window]))
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _range_contraction(frame: pd.DataFrame, window: int = 10) -> float:
    ranges = frame["high"] - frame["low"]
    if len(ranges) < window * 2:
        return 0.0
    recent_mean = float(ranges.iloc[-window:].mean())
    prior_mean = float(ranges.iloc[-window * 2 : -window].mean())
    return (prior_mean - recent_mean) / prior_mean if prior_mean > 0 else 0.0


def detect_patterns(frame: pd.DataFrame, swings: dict[str, list[Any]]) -> list[dict[str, Any]]:
    pattern_classes = [
        BullFlagPattern(),
        BearFlagPattern(),
        BullFlatPattern(),
        BearFlatPattern(),
        BullTrianglePattern(),
        BearTrianglePattern(),
        ExpandingTrianglePattern(),
        RisingWedgePattern(),
        FallingWedgePattern(),
        AscendingChannelPattern(),
        DescendingChannelPattern(),
        HeadAndShouldersPattern(),
        InverseHeadAndShouldersPattern(),
        DoubleTopPattern(),
        DoubleBottomPattern(),
    ]

    validator = PatternValidator()
    xgb_validator = XGBoostValidator()
    results: list[dict[str, Any]] = []
    for detector in pattern_classes:
        pattern = detector.detect(frame, swings)
        if not pattern:
            continue
        confirmation = analyze_candlestick_confirmation(frame)
        pattern["candlestick_confirmation"] = confirmation
        pattern["candlestick_strength"] = confirmation.strength
        pattern["candlestick_bonus"] = confirmation.confirmed
        pattern["trend_strength"] = _recent_trend(frame)
        pattern["range_contraction"] = _range_contraction(frame)
        pattern["ml_score"] = xgb_validator.score(
            {
                "direction": pattern.get("direction"),
                "breakout_strength": pattern.get("breakout_strength"),
                "candlestick_strength": confirmation.strength,
                "trend_strength": pattern["trend_strength"],
                "range_contraction": pattern["range_contraction"],
            }
        )
        if pattern["ml_score"] == 0.0:
            pattern["ml_score"] = 0.5
        pattern["confidence"] = validator.score(pattern)
        if validator.is_accepted(pattern):
            results.append(pattern)

    return results
