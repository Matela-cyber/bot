"""Average True Range indicator."""

from typing import Literal

import numpy as np
import pandas as pd


def calculate_atr(
    data: pd.DataFrame,
    period: int = 14,
    smoothing: Literal["rma", "sma", "ema"] = "rma",
) -> pd.Series:
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if period < 1:
        raise ValueError("period must be at least 1")
    if smoothing not in {"rma", "sma", "ema"}:
        raise ValueError("smoothing must be 'rma', 'sma', or 'ema'")
    required = {"high", "low", "close"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            f"missing required columns: {', '.join(sorted(missing))}")

    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    close = pd.to_numeric(data["close"], errors="coerce")
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(),
         (low - previous_close).abs()],
        axis=1,
    ).max(axis=1, skipna=False)
    if not true_range.empty:
        true_range.iloc[0] = (high.iloc[0] - low.iloc[0])

    if smoothing == "rma":
        return true_range.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    if smoothing == "ema":
        return true_range.ewm(span=period, adjust=False, min_periods=period).mean()
    return true_range.rolling(window=period, min_periods=period).mean()


def atr_pips(atr_value: float, digits: int = 5) -> float:
    if not np.isfinite(atr_value) or digits < 1:
        return float("nan")
    pip_size = 10 ** (-(digits - 1 if digits in {3, 5} else digits))
    return float(atr_value / pip_size)
