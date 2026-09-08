"""Canonical CSV backtest-data loader API."""

from pathlib import Path

import pandas as pd


class HistoricalDataError(RuntimeError):
    """Raised when a CSV data file is invalid."""


def load_data(
        input_dir: str | Path = "data/backtest_data",
    pairs: list[str] | None = None,
        timeframes: tuple[str, ...] = ("5m", "15m", "1h"),
):
    """Load canonical backtest CSV files by symbol and timeframe."""
    directory = Path(input_dir)
    imported = {}
    selected = {pair.upper() for pair in pairs} if pairs else None
    for path in sorted(directory.glob("*_*.csv")):
        parts = path.stem.split("_")
        if len(parts) < 2:
            continue
        symbol, timeframe = parts[0].upper(), parts[1]
        if timeframe not in timeframes or (selected and symbol not in selected):
            continue
        frame = pd.read_csv(path, parse_dates=["time"])
        if "time" not in frame.columns:
            raise HistoricalDataError(f"Missing time column in {path}")
        frame["time"] = pd.to_datetime(
            frame["time"], utc=True, errors="coerce")
        imported[f"{symbol}_{timeframe}"] = frame.dropna(
            subset=["time"]).set_index("time").sort_index()
    return imported


def import_backtest_data(
    input_dir: str | Path = "data/backtest_data",
    pairs: list[str] | None = None,
    timeframes: tuple[str, ...] = ("15m", "1h"),
):
    """Backward-compatible alias for :func:`load_data`."""
    return load_data(input_dir=input_dir, pairs=pairs, timeframes=timeframes)


__all__ = ["HistoricalDataError", "import_backtest_data", "load_data"]
