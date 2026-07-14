from __future__ import annotations

import numpy as np
import pandas as pd


def prepare_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    """Validate, normalize, and enrich OHLCV data for downstream analysis."""
    if data is None or data.empty:
        raise ValueError("OHLCV data is empty")

    frame = data.copy()
    frame = frame.sort_index()
    frame = frame.astype({"open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"})

    required_columns = {"open", "high", "low", "close", "volume"}
    missing = required_columns.difference(frame.columns)
    if missing:
        raise ValueError(f"OHLCV frame is missing required columns: {sorted(missing)}")

    frame["ret"] = frame["close"].pct_change()
    frame["log_ret"] = np.log(frame["close"] / frame["close"].shift(1))
    frame["hl_range"] = frame["high"] - frame["low"]
    frame["oc_range"] = frame["close"] - frame["open"]
    frame = frame.dropna()
    return frame
