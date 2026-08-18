"""ATR calculation module."""
import pandas as pd


def calculate_atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()
