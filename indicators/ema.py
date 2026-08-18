"""EMA calculation module."""
import pandas as pd


def calculate_ema(frame: pd.DataFrame, period: int = 50) -> pd.Series:
    """Calculate exponential moving average."""
    return frame["close"].ewm(span=period, adjust=False).mean()
