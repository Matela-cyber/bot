"""Relative Strength Index indicator."""

from typing import Any

import numpy as np
import pandas as pd


def calculate_rsi(data: pd.DataFrame, period: int = 14) -> pd.Series:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if period < 1:
        raise ValueError("period must be at least 1")
    if "close" not in data.columns:
        raise ValueError("missing required column: close")

    close = pd.to_numeric(data["close"], errors="coerce")
    change = close.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    average_gain = gain.ewm(
        alpha=1 / period, adjust=False, min_periods=period).mean()
    average_loss = loss.ewm(
        alpha=1 / period, adjust=False, min_periods=period).mean()

    relative_strength = average_gain / average_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + relative_strength))
    no_loss = average_loss == 0
    no_gain = average_gain == 0
    result = result.mask(no_loss & ~no_gain, 100.0)
    result = result.mask(no_gain & ~no_loss, 0.0)
    result = result.mask(no_loss & no_gain, 50.0)
    return result.rename("rsi")


def rsi_signal(rsi_value: Any, threshold: float = 50) -> str:
    try:
        value = float(rsi_value)
        threshold_value = float(threshold)
    except (TypeError, ValueError, OverflowError):
        return "neutral"
    if not np.isfinite(value) or not np.isfinite(threshold_value):
        return "neutral"
    if value > threshold_value:
        return "bull"
    if value < threshold_value:
        return "bear"
    return "neutral"
