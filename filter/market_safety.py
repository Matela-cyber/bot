"""Market-safety filters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from indicators.atr import calculate_atr


class WeekendFilter:
    def __init__(self, config: Any) -> None:
        self.config = config
        self.timezone = ZoneInfo(
            getattr(config, "local_timezone", "Africa/Johannesburg"))

    def should_trade(self, current_time: datetime) -> bool:
        local = current_time.astimezone(self.timezone)
        cutoff = int(getattr(self.config, "friday_cutoff_hour", 17))
        return local.weekday() < 5 and not (local.weekday() == 4 and local.hour >= cutoff)

    def should_close_all(self, current_time: datetime) -> bool:
        local = current_time.astimezone(self.timezone)
        cutoff = int(getattr(self.config, "friday_cutoff_hour", 17))
        close_time = local.replace(
            hour=cutoff, minute=0, second=0, microsecond=0) - timedelta(minutes=30)
        return (local.weekday() == 4 and local >= close_time) or local.weekday() == 5


class LowLiquidityFilter:
    def __init__(self, config: Any) -> None:
        self.config = config

    def should_trade(self, current_time: datetime) -> bool:
        if not getattr(self.config, "low_liquidity_filter_enabled", True):
            return True
        hour = current_time.astimezone(timezone.utc).hour
        start = int(getattr(self.config, "low_liquidity_block_start_utc", 22))
        end = int(getattr(self.config, "low_liquidity_block_end_utc", 2))
        return not (hour >= start or hour < end if start > end else start <= hour < end)


class AdaptiveVolatilityFilter:
    def __init__(self, config: Any) -> None:
        self.config = config

    def should_trade(self, data: pd.DataFrame) -> bool:
        if len(data) < 30:
            return False
        atr = calculate_atr(data, period=14)
        current_atr = float(atr.iloc[-1])
        baseline_atr = float(atr.iloc[-21:-1].mean())
        if not np.isfinite(current_atr) or not np.isfinite(baseline_atr) or baseline_atr <= 0:
            return False
        if current_atr > baseline_atr * 3.0:
            return False
        if "volume" in data.columns:
            volume = pd.to_numeric(data["volume"], errors="coerce")
            baseline_volume = float(volume.iloc[-21:-1].mean())
            if np.isfinite(baseline_volume) and baseline_volume > 0 and volume.iloc[-1] > baseline_volume * 4.0:
                return False
        return True


class MarketShockFilter:
    def __init__(self, config: Any | None = None) -> None:
        self.config = config

    def should_trade(self, data: pd.DataFrame) -> bool:
        if data is None or data.empty or len(data) < 20:
            return False

        close = pd.to_numeric(data["close"], errors="coerce")
        high = pd.to_numeric(data["high"], errors="coerce")
        low = pd.to_numeric(data["low"], errors="coerce")
        if close.empty or high.empty or low.empty:
            return False

        recent = data.iloc[-20:]
        recent_range = (recent["high"] - recent["low"]).abs()
        baseline_range = recent_range.iloc[:-
                                           1].mean() if len(recent_range) > 1 else 0.0
        current_range = float(
            recent_range.iloc[-1]) if len(recent_range) else 0.0

        if not np.isfinite(current_range) or not np.isfinite(baseline_range) or baseline_range <= 0:
            return False

        recent_body = (recent["close"] - recent["open"]).abs()
        baseline_body = recent_body.iloc[:-
                                         1].mean() if len(recent_body) > 1 else 0.0
        current_body = float(recent_body.iloc[-1]) if len(recent_body) else 0.0

        if current_range > baseline_range * 3.0 and current_body > baseline_body * 2.5:
            return False

        if "volume" in data.columns:
            volume = pd.to_numeric(data["volume"], errors="coerce")
            recent_volume = volume.iloc[-20:]
            baseline_volume = recent_volume.iloc[:-
                                                 1].mean() if len(recent_volume) > 1 else 0.0
            current_volume = float(
                recent_volume.iloc[-1]) if len(recent_volume) else 0.0
            if np.isfinite(current_volume) and np.isfinite(baseline_volume) and baseline_volume > 0 and current_volume > baseline_volume * 4.0:
                return False

        return True
