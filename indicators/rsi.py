"""RSI calculation module."""

from __future__ import annotations

import pandas as pd


def calculate_rsi(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index with zero-division protection."""
    if frame.empty:
        return pd.Series(dtype=float)

    delta = frame["close"].astype(float).diff()
    gain = delta.clip(lower=0).rolling(window=period, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).rolling(window=period, min_periods=period).mean()

    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)
