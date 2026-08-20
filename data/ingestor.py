from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy as np
import pandas as pd

from config import settings

try:
    import MetaTrader5 as mt5  # type: ignore[import]
except ImportError:  # pragma: no cover - optional dependency
    mt5 = None  # type: ignore[assignment]


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

        # Insert a reliable bull flag breakout structure into the tail of the synthetic series.
        if points >= 150:
            anchor = float(price[-151])
            impulse = np.linspace(anchor, anchor + 0.0080, 20)
            consolidation = impulse[-1] + np.linspace(-0.0012, -0.0003, 40)
            consolidation = consolidation + np.sin(np.linspace(0, 4 * np.pi, 40)) * 0.00005
            breakout = consolidation[-1] + np.linspace(0.0010, 0.0045, 35)
            followthrough = breakout[-1] + np.linspace(0.0002, 0.0007, 15)
            pattern_segment = np.concatenate([impulse, consolidation, breakout, followthrough])
            price[-110:] = pattern_segment

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

    def _require_mt5_module(self) -> Any:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 is not installed. Install it to fetch real market data.")
        return cast(Any, mt5)

    def _resolve_mt5_timeframe(self) -> int:
        mt5_module = self._require_mt5_module()
        mapping: dict[str, int] = {
            "1m": mt5_module.TIMEFRAME_M1,
            "5m": mt5_module.TIMEFRAME_M5,
            "15m": mt5_module.TIMEFRAME_M15,
            "15min": mt5_module.TIMEFRAME_M15,
            "30m": mt5_module.TIMEFRAME_M30,
            "30min": mt5_module.TIMEFRAME_M30,
            "1h": mt5_module.TIMEFRAME_H1,
            "1H": mt5_module.TIMEFRAME_H1,
            "4h": mt5_module.TIMEFRAME_H4,
            "1d": mt5_module.TIMEFRAME_D1,
        }

        if self.timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe for MT5 ingestion: {self.timeframe}")
        return mapping[self.timeframe]

    def _bars_per_day(self) -> int:
        if self.timeframe in {"1m"}:
            return 1440
        if self.timeframe in {"5m"}:
            return 288
        if self.timeframe in {"15m", "15min"}:
            return 96
        if self.timeframe in {"30m", "30min"}:
            return 48
        if self.timeframe in {"1h", "1H"}:
            return 24
        if self.timeframe in {"4h", "4H"}:
            return 6
        if self.timeframe in {"1d", "1D"}:
            return 1
        raise ValueError(f"Unsupported timeframe for bar calculation: {self.timeframe}")

    def _resolve_mt5_symbol(self, mt5_module: Any, symbol: str) -> str:
        """Resolve a configured pair to the broker's exact MT5 symbol name."""
        requested = symbol.strip().upper()
        if mt5_module.symbol_info(requested) is not None:
            if hasattr(mt5_module, "symbol_select"):
                mt5_module.symbol_select(requested, True)
            return requested

        symbols_get = getattr(mt5_module, "symbols_get", None)
        if symbols_get is None:
            raise RuntimeError(f"Symbol {requested} not found in MT5 and symbol discovery is unavailable")

        normalized_requested = "".join(character for character in requested if character.isalnum())
        candidates = cast(list[Any], symbols_get() or [])
        matches: list[str] = []
        for candidate in candidates:
            candidate_name = str(getattr(candidate, "name", candidate))
            normalized_candidate = "".join(character for character in candidate_name.upper() if character.isalnum())
            if normalized_candidate == normalized_requested or normalized_candidate.startswith(normalized_requested):
                matches.append(candidate_name)

        if not matches:
            raise RuntimeError(f"Symbol {requested} not found in MT5; configure the broker symbol name")

        resolved = sorted(matches, key=lambda name: (len(name), name))[0]
        if hasattr(mt5_module, "symbol_select") and not mt5_module.symbol_select(resolved, True):
            raise RuntimeError(f"MT5 could not select resolved symbol {resolved} for {requested}")
        return resolved

    def _fetch_mt5_frame(self, days: int, symbol: str = "EURUSD") -> pd.DataFrame:
        mt5_module = self._require_mt5_module()
        if not settings.mt5_account or not settings.mt5_password or not settings.mt5_server:
            raise RuntimeError("MT5 credentials are not configured in .env")

        if not mt5_module.initialize(
            login=settings.mt5_account,
            password=settings.mt5_password,
            server=settings.mt5_server,
        ):
            raise RuntimeError(f"MT5 initialization failed: {mt5_module.last_error()}")

        try:
            bars = max(days, 1) * self._bars_per_day()
            resolved_symbol = self._resolve_mt5_symbol(mt5_module, symbol)
            rates = mt5_module.copy_rates_from_pos(resolved_symbol, self._resolve_mt5_timeframe(), 0, bars)
            if rates is None or len(rates) == 0:
                raise RuntimeError(f"MT5 returned no OHLCV bars for {resolved_symbol}")

            frame = pd.DataFrame(rates)
            if len(frame) > 1:
                frame = frame.iloc[:-1].copy()
            frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
            frame = frame.set_index("time")[ ["open", "high", "low", "close", "tick_volume"] ]
            frame = frame.rename(columns={"tick_volume": "volume"})
            return self._validate_frame(frame)
        finally:
            mt5_module.shutdown()

    def fetch_ohlcv(self, symbol: str = "EURUSD", days: int = 90, source: str = "local") -> pd.DataFrame:
        """Fetch OHLCV data from the configured source with retries and validation."""
        if source not in {"local", "mt5"}:
            raise ValueError(f"Unsupported data source: {source}")

        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                if source == "local":
                    frame = self._build_synthetic_frame(days)
                else:
                    frame = self._fetch_mt5_frame(days, symbol=symbol)
                return frame
            except Exception as exc:  # pragma: no cover - resilience path
                last_error = exc
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Failed to fetch OHLCV after {self.max_retries} attempts: {exc}") from exc
        raise RuntimeError(f"Unable to fetch OHLCV data: {last_error}")


def fetch_local_ohlcv(days: int = 90, symbol: str = "EURUSD") -> pd.DataFrame:
    return DataIngestor().fetch_ohlcv(symbol=symbol, days=days, source="local")


def fetch_mt5_ohlcv(days: int = 90, timeframe: str = "15m", symbol: str = "EURUSD") -> pd.DataFrame:
    return DataIngestor(timeframe=timeframe).fetch_ohlcv(symbol=symbol, days=days, source="mt5")
