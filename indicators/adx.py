"""ADX calculation module."""

from __future__ import annotations

import pandas as pd


def calculate_adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (ADX) with stable zero-division handling."""
    if frame.empty:
        return pd.Series(dtype=float)

    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["close"].astype(float)

    up_move = high.diff()
    down_move = low.diff()

    plus_dm = pd.Series(0.0, index=frame.index)
    minus_dm = pd.Series(0.0, index=frame.index)

    plus_condition = (up_move > down_move) & (up_move > 0)
    minus_condition = (down_move > up_move) & (down_move > 0)

    plus_dm = pd.Series(up_move.where(plus_condition, 0.0), index=frame.index)
    minus_dm = pd.Series(down_move.where(minus_condition, 0.0), index=frame.index)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period, min_periods=period).mean()

    plus_di = 100 * (plus_dm.rolling(window=period, min_periods=period).sum() / atr.replace(0, pd.NA))
    minus_di = 100 * (minus_dm.rolling(window=period, min_periods=period).sum() / atr.replace(0, pd.NA))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, pd.NA)
    dx = dx.fillna(0.0)

    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)
