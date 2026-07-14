from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DataIngestor:
    """Production-style OHLCV ingestion layer with validation and retries."""

    timeframe: str = "15min"
    max_retries: int = 3

    def _build_synthetic_frame(self, days: int) -> pd.DataFrame:
        points = max(days, 1) * 96
        index = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=points, freq=self.timeframe)
        base = np.linspace(1.0800, 1.0880, points)
        noise = np.sin(np.linspace(0, 8 * np.pi, points)) * 0.0004
        trend = np.where(np.arange(points) < points // 2, 0.00005, -0.00003)
        price = base + noise + trend

        open_series = price.copy()
        close_series = price + np.where(np.arange(points) % 5 == 0, 0.00015, -0.00005)
        high_series = np.maximum(open_series, close_series) + 0.0002
        low_series = np.minimum(open_series, close_series) - 0.0002

        return pd.DataFrame(
            {
                "open": open_series,
                "high": high_series,
                "low": low_series,
                "close": close_series,
                "volume": 1000 + (np.arange(points) % 100) * 10,
            },
            index=index,
        )

    def _validate_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        required_columns = {"open", "high", "low", "close", "volume"}
        missing = required_columns.difference(frame.columns)
        if missing:
            raise ValueError(f"OHLCV frame is missing required columns: {sorted(missing)}")

        frame = frame.copy()
        frame = frame.sort_index()
        frame = frame.astype({"open": "float64", "high": "float64", "low": "float64", "close": "float64", "volume": "float64"})
        if frame.empty:
            raise ValueError("OHLCV frame is empty")
        if not (frame["high"] >= frame["low"]).all():
            raise ValueError("OHLCV frame contains invalid high/low values")
        if not ((frame["high"] >= frame["open"]) & (frame["high"] >= frame["close"])).all():
            raise ValueError("OHLCV frame contains invalid high values")
        if not ((frame["low"] <= frame["open"]) & (frame["low"] <= frame["close"])).all():
            raise ValueError("OHLCV frame contains invalid low values")
        return frame

    def fetch_ohlcv(self, days: int = 90, source: str = "local") -> pd.DataFrame:
        """Fetch OHLCV data from the configured source with retries and validation."""
        if source != "local":
            raise ValueError(f"Unsupported data source: {source}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                frame = self._build_synthetic_frame(days)
                return self._validate_frame(frame)
            except Exception as exc:  # pragma: no cover - resilience path
                last_error = exc
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Failed to fetch OHLCV after {self.max_retries} attempts: {exc}") from exc
        raise RuntimeError(f"Unable to fetch OHLCV data: {last_error}")


def fetch_local_ohlcv(days: int = 90) -> pd.DataFrame:
    return DataIngestor().fetch_ohlcv(days=days, source="local")
